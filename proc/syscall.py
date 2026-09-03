#!/usr/bin/env python3
"""
AdiOS System Call Subsystem: RISC-V ecall ABI Dispatcher (syscall.py)
Implements standard RISC-V register ABI convention (a7=syscall, a0-a5=args, a0=return),
POSIX-compliant error codes, and Ring-0 sovereign hardware acceleration calls.
"""

from typing import Dict, Any, Optional
from proc.process import TaskControlBlock, ProcessState, FileDescriptor
from proc.signals import Signal, SignalDispatcher, SigAction
from proc.ipc import Pipe, MessageQueue, SharedMemoryRegion, SovereignSemaphore
from proc.scheduler import MLFQScheduler

# POSIX Error Codes
EINVAL = 22  # Invalid argument
EPERM  = 1   # Operation not permitted
ESRCH  = 3   # No such process
EBADF  = 9   # Bad file descriptor
EAGAIN = 11  # Resource temporarily unavailable
ENOMEM = 12  # Cannot allocate memory
ECHILD = 10  # No child processes
EPIPE  = 32  # Broken pipe

# Syscall Numbers
SYS_EXIT        = 1
SYS_FORK        = 2
SYS_READ        = 3
SYS_WRITE       = 4
SYS_OPEN        = 5
SYS_CLOSE       = 6
SYS_WAITPID     = 7
SYS_GETPID      = 20
SYS_KILL        = 37
SYS_PIPE        = 42
SYS_GETPPID     = 64
SYS_SIGACTION   = 67
SYS_SLEEP       = 101
SYS_SIGRETURN   = 119
SYS_YIELD       = 124
SYS_MQ_OPEN     = 130
SYS_MQ_SEND     = 131
SYS_MQ_RECV     = 132
SYS_SHM_OPEN    = 140
SYS_SHM_READ    = 141
SYS_SHM_WRITE   = 142
SYS_SEM_INIT    = 150
SYS_SEM_ACQUIRE = 151
SYS_SEM_RELEASE = 152

# Sovereign Ring-0 Hardware Syscalls
SYS_ADI_PEEK        = 200
SYS_ADI_POKE        = 201
SYS_ADI_TONE        = 202
SYS_ADI_ORACLE      = 203
SYS_ADI_FRAMEBUFFER = 204
SYS_ADI_DISK_READ   = 205
SYS_ADI_DISK_WRITE  = 206
SYS_ADI_NET_SEND    = 207

class SyscallDispatcher:
    """
    RISC-V System Call Handler.
    Decodes ecall requests from registers, executes kernel routines,
    and places return values in register a0.
    """
    def __init__(self, scheduler: MLFQScheduler, signal_dispatcher: SignalDispatcher, vm_ref=None):
        self.scheduler = scheduler
        self.signal_dispatcher = signal_dispatcher
        self.vm = vm_ref

        # Global IPC Tables
        self.pipes: Dict[int, Pipe] = {}
        self.message_queues: Dict[str, MessageQueue] = {}
        self.shared_mem: Dict[str, SharedMemoryRegion] = {}
        self.semaphores: Dict[int, SovereignSemaphore] = {}
        self._next_ipc_id = 1

    def dispatch(self, proc: TaskControlBlock) -> int:
        """
        Extracts syscall number from a7 (x17) and arguments from a0-a5 (x10-x15).
        Executes handler and places return code in a0 (x10).
        """
        sys_num = proc.context.regs[17]
        a0 = proc.context.regs[10]
        a1 = proc.context.regs[11]
        a2 = proc.context.regs[12]
        a3 = proc.context.regs[13]
        a4 = proc.context.regs[14]
        a5 = proc.context.regs[15]

        ret = 0

        # Dispatch
        if sys_num == SYS_GETPID:
            ret = proc.pid
        elif sys_num == SYS_GETPPID:
            ret = proc.ppid
        elif sys_num == SYS_EXIT:
            proc.terminate(exit_code=a0)
            ret = 0
        elif sys_num == SYS_FORK:
            child = proc.fork()
            self.scheduler.add_process(child)
            ret = child.pid
        elif sys_num == SYS_YIELD:
            self.scheduler.yield_current()
            ret = 0
        elif sys_num == SYS_SLEEP:
            self.scheduler.sleep_current(ticks=a0)
            ret = 0
        elif sys_num == SYS_KILL:
            target_pid, sig_num = a0, a1
            target = self.scheduler.all_processes.get(target_pid)
            if not target:
                ret = -ESRCH
            else:
                ok = self.signal_dispatcher.send_signal(target, sig_num)
                ret = 0 if ok else -EINVAL
        elif sys_num == SYS_SIGACTION:
            sig_num, handler_addr, flags = a0, a1, a2
            if not (1 <= sig_num <= 32) or sig_num in (Signal.SIGKILL, Signal.SIGSTOP):
                ret = -EINVAL
            else:
                proc.signal_handlers[sig_num] = SigAction(handler=handler_addr, flags=flags)
                ret = 0
        elif sys_num == SYS_SIGRETURN:
            ok = self.signal_dispatcher.handle_sigreturn(proc)
            return 0  # Do not overwrite restored a0!
        elif sys_num == SYS_PIPE:
            # Create pipe and allocate 2 file descriptors in process
            pipe = Pipe()
            pipe_id = self._next_ipc_id
            self._next_ipc_id += 1
            self.pipes[pipe_id] = pipe

            fd_read = proc.allocate_fd('PIPE_READ', pipe_id)
            fd_write = proc.allocate_fd('PIPE_WRITE', pipe_id)
            # Store in return registers: a0 = fd_read, a1 = fd_write
            proc.context.regs[10] = fd_read
            proc.context.regs[11] = fd_write
            return 0
        elif sys_num == SYS_WRITE:
            fd, buf_val, count = a0, a1, a2
            f_desc = proc.fd_table.get(fd)
            if not f_desc:
                ret = -EBADF
            elif f_desc.target_type == 'CONSOLE':
                # Write to serial console / stdout
                if self.vm:
                    for b in range(count):
                        self.vm.uart_tx.append(buf_val & 0xFF)
                ret = count
            elif f_desc.target_type == 'PIPE_WRITE':
                pipe = self.pipes.get(f_desc.target_ref)
                if not pipe:
                    ret = -EBADF
                else:
                    data = bytes([buf_val & 0xFF]) * count
                    try:
                        ret = pipe.write(data)
                    except BrokenPipeError:
                        self.signal_dispatcher.send_signal(proc, Signal.SIGPIPE)
                        ret = -EPIPE
            else:
                ret = -EINVAL
        elif sys_num == SYS_READ:
            fd, count = a0, a1
            f_desc = proc.fd_table.get(fd)
            if not f_desc:
                ret = -EBADF
            elif f_desc.target_type == 'PIPE_READ':
                pipe = self.pipes.get(f_desc.target_ref)
                if not pipe:
                    ret = -EBADF
                else:
                    chunk = pipe.read(count)
                    ret = len(chunk)
            else:
                ret = -EINVAL
        elif sys_num == SYS_WAITPID:
            target_pid = a0
            # Scan for zombie child
            zombie = None
            for child in proc.children:
                if (target_pid == -1 or child.pid == target_pid) and child.state == ProcessState.ZOMBIE:
                    zombie = child
                    break
            if zombie:
                ret = zombie.pid
                proc.context.regs[11] = zombie.exit_code  # Place status in a1
                proc.children.remove(zombie)
                self.scheduler.remove_process(zombie.pid)
            else:
                ret = -ECHILD
        elif sys_num == SYS_MQ_OPEN:
            name = f"queue_{a0}"
            if name not in self.message_queues:
                self.message_queues[name] = MessageQueue(name)
            ret = a0
        elif sys_num == SYS_MQ_SEND:
            q_id, val, prio = a0, a1, a2
            mq = self.message_queues.get(f"queue_{q_id}")
            if not mq:
                ret = -EINVAL
            else:
                ok = mq.send(data:=bytes([val & 0xFF]), priority=prio)
                ret = 0 if ok else -EAGAIN
        elif sys_num == SYS_MQ_RECV:
            q_id = a0
            mq = self.message_queues.get(f"queue_{q_id}")
            if not mq or not mq.messages:
                ret = -EAGAIN
            else:
                payload, prio = mq.receive()
                ret = payload[0] if payload else 0
                proc.context.regs[11] = prio
        elif sys_num == SYS_ADI_ORACLE:
            # Consult Cosmic Oracle
            from holy.oracle import consult_oracle
            word = consult_oracle(1)
            ret = len(word)
        elif sys_num == SYS_ADI_TONE:
            # MMIO Speaker Tone
            freq, ms = a0, a1
            if self.vm:
                self.vm.write_u32(0x10000050, freq)
            ret = 0
        else:
            ret = -EINVAL  # Unknown system call

        proc.context.regs[10] = ret
        return ret

if __name__ == "__main__":
    sched = MLFQScheduler()
    sig_disp = SignalDispatcher()
    dispatcher = SyscallDispatcher(sched, sig_disp)

    init_p = TaskControlBlock("init")
    sched.add_process(init_p)

    # Test SYS_GETPID
    init_p.context.regs[17] = SYS_GETPID
    dispatcher.dispatch(init_p)
    assert init_p.context.regs[10] == init_p.pid

    # Test SYS_FORK
    init_p.context.regs[17] = SYS_FORK
    dispatcher.dispatch(init_p)
    child_pid = init_p.context.regs[10]
    assert child_pid > init_p.pid
    assert child_pid in sched.all_processes

    # Test SYS_PIPE & Write
    init_p.context.regs[17] = SYS_PIPE
    dispatcher.dispatch(init_p)
    fd_r = init_p.context.regs[10]
    fd_w = init_p.context.regs[11]

    init_p.context.regs[17] = SYS_WRITE
    init_p.context.regs[10] = fd_w
    init_p.context.regs[11] = 0x42  # Byte 'B'
    init_p.context.regs[12] = 4     # 4 bytes
    dispatcher.dispatch(init_p)
    assert init_p.context.regs[10] == 4

    print("RISC-V System Call ABI Dispatcher verified.")
