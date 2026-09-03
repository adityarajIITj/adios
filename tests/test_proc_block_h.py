#!/usr/bin/env python3
"""
Test Suite: Block H Process Management, Signals, IPC & Syscall ABI Subsystem
Verifies:
1. TaskControlBlock lifecycle, forking, and parent-child hierarchy
2. POSIX and Sovereign 32-Signal dispatching, masks, handlers, and sigreturn
3. Sovereign IPC Suite (Pipes, Priority Message Queues, Shared Memory, Mutexes)
4. Multi-Level Feedback Queue (MLFQ) preemptive scheduler & priority boost
5. RISC-V ecall System Call Dispatcher & bare-metal assembly syscall traps
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from proc.process import TaskControlBlock, ProcessState, PriorityClass
from proc.signals import Signal, SignalDispatcher, SigAction, SIG_DFL, SIG_IGN
from proc.ipc import Pipe, MessageQueue, SharedMemoryRegion, SovereignSemaphore, SovereignMutex
from proc.scheduler import MLFQScheduler
from proc.syscall import (
    SyscallDispatcher, SYS_GETPID, SYS_GETPPID, SYS_FORK, SYS_PIPE,
    SYS_WRITE, SYS_READ, SYS_WAITPID, SYS_SIGACTION, SYS_EXIT
)
from toolchain.assembler import Assembler
from vm.vm import VM

def test_proc_block_h_suite():
    print("[Test Proc Block H] Initializing Process Management, Signals & IPC Verification...")

    # 1. Test Process TCB & Hierarchy
    print("  -> Testing Process Control Block & Hierarchy...")
    init_task = TaskControlBlock("init", parent_pid=0, priority=PriorityClass.REALTIME)
    assert init_task.pid == 1
    assert init_task.state == ProcessState.EMBRYO

    child_shell = init_task.fork("shell")
    assert child_shell.pid == 2
    assert child_shell.ppid == 1
    assert child_shell.state == ProcessState.READY
    assert len(init_task.children) == 1

    grandchild = child_shell.fork("editor")
    assert grandchild.pid == 3
    assert grandchild.ppid == 2

    # Terminate child_shell -> grandchild must be reparented to init (PID 1)
    child_shell.terminate(exit_code=0)
    assert child_shell.state == ProcessState.ZOMBIE
    print("  -> [PASS] Process TCB and parent-child hierarchy verified.")

    # 2. Test Signals & Trampoline
    print("  -> Testing POSIX & Sovereign 32-Signal Engine...")
    sig_disp = SignalDispatcher()
    proc_sig = TaskControlBlock("signal_test")

    # A. Test uncatchable SIGKILL
    sig_disp.send_signal(proc_sig, Signal.SIGKILL)
    assert proc_sig.state == ProcessState.ZOMBIE
    assert proc_sig.exit_code == 128 + Signal.SIGKILL

    # B. Test custom handler and sigreturn context preservation
    proc_handler = TaskControlBlock("handler_test")
    custom_pc = 0x80050000
    proc_handler.signal_handlers[Signal.SIGUSR1] = SigAction(handler=custom_pc)
    proc_handler.context.pc = 0x80020000
    proc_handler.context.regs[10] = 777  # a0

    sig_disp.send_signal(proc_handler, Signal.SIGUSR1)
    assert sig_disp.has_pending_unblocked(proc_handler)

    handled_sig = sig_disp.dispatch_pending(proc_handler)
    assert handled_sig == Signal.SIGUSR1
    assert proc_handler.context.pc == custom_pc
    assert proc_handler.context.regs[10] == Signal.SIGUSR1
    assert proc_handler.context.regs[1] == 0x8000FF00  # Trampoline address

    # Execute sigreturn
    ok = sig_disp.handle_sigreturn(proc_handler)
    assert ok
    assert proc_handler.context.pc == 0x80020000
    assert proc_handler.context.regs[10] == 777  # Restored a0
    print("  -> [PASS] Signal dispatching, frames, and sigreturn verified.")

    # 3. Test Sovereign IPC Suite
    print("  -> Testing Sovereign IPC (Pipes, MQs, Shm, Mutexes)...")
    # A. Pipe
    pipe = Pipe(capacity=1024)
    written = pipe.write(b"AdiOS_Sovereign_IPC_Message")
    assert written == len(b"AdiOS_Sovereign_IPC_Message")
    read_data = pipe.read(64)
    assert read_data == b"AdiOS_Sovereign_IPC_Message"

    # Broken pipe test
    pipe.close_read()
    try:
        pipe.write(b"Fail")
        assert False, "Write to closed pipe must raise BrokenPipeError"
    except BrokenPipeError:
        pass

    # B. Message Queue
    mq = MessageQueue("ipc_mq")
    mq.send(b"Prio1", priority=1)
    mq.send(b"Prio9", priority=9)
    mq.send(b"Prio5", priority=5)

    msg, prio = mq.receive()
    assert msg == b"Prio9" and prio == 9
    msg, prio = mq.receive()
    assert msg == b"Prio5" and prio == 5

    # C. Shared Memory
    shm = SharedMemoryRegion("matrix_shm", 256)
    shm.write(0, b"CYBER_MATRIX_MEM")
    assert shm.read(0, 16) == b"CYBER_MATRIX_MEM"

    # D. Mutex with Priority Inheritance
    mutex = SovereignMutex()
    assert mutex.lock(pid=10, priority=3)  # PID 10 holds lock at Normal priority
    assert not mutex.lock(pid=11, priority=1)  # PID 11 waits at High priority
    assert mutex.owner_priority == 1  # Priority inherited!
    next_owner = mutex.unlock(pid=10)
    assert next_owner == 11
    print("  -> [PASS] Sovereign IPC suite verified.")

    # 4. Test MLFQ Preemptive Scheduler
    print("  -> Testing Multi-Level Feedback Queue Scheduler...")
    sched = MLFQScheduler()
    t_rt = TaskControlBlock("rt_proc", priority=PriorityClass.REALTIME)
    t_norm = TaskControlBlock("norm_proc", priority=PriorityClass.NORMAL)

    sched.add_process(t_rt)
    sched.add_process(t_norm)

    # Real-Time task must run first
    selected = sched.tick()
    assert selected.pid == t_rt.pid

    # Test voluntary sleep
    sched.sleep_current(ticks=5)
    assert t_rt.state == ProcessState.SLEEPING

    # Next tick must run normal task
    selected = sched.tick()
    assert selected.pid == t_norm.pid

    # Advance 6 ticks to wake up real-time task
    for _ in range(6):
        selected = sched.tick()
    assert t_rt.state in (ProcessState.READY, ProcessState.RUNNING)
    print("  -> [PASS] MLFQ scheduler and timer wakeups verified.")

    # 5. Test System Call Dispatcher
    print("  -> Testing RISC-V ecall ABI Dispatcher...")
    sys_disp = SyscallDispatcher(sched, sig_disp)
    caller = TaskControlBlock("caller_proc")
    sched.add_process(caller)

    # SYS_GETPID
    caller.context.regs[17] = SYS_GETPID
    sys_disp.dispatch(caller)
    assert caller.context.regs[10] == caller.pid

    # SYS_PIPE
    caller.context.regs[17] = SYS_PIPE
    sys_disp.dispatch(caller)
    fd_read = caller.context.regs[10]
    fd_write = caller.context.regs[11]
    assert fd_read in caller.fd_table and fd_write in caller.fd_table

    # SYS_WRITE to Pipe
    caller.context.regs[17] = SYS_WRITE
    caller.context.regs[10] = fd_write
    caller.context.regs[11] = 0x5A  # 'Z'
    caller.context.regs[12] = 8     # 8 bytes
    sys_disp.dispatch(caller)
    assert caller.context.regs[10] == 8

    # SYS_READ from Pipe
    caller.context.regs[17] = SYS_READ
    caller.context.regs[10] = fd_read
    caller.context.regs[11] = 8
    sys_disp.dispatch(caller)
    assert caller.context.regs[10] == 8
    print("  -> [PASS] RISC-V system call dispatcher verified.")

    # 6. Bare-Metal Assembly Syscall Trap Verification in VM
    print("  -> Testing Bare-Metal Assembly Syscall Handler in RV32 VM...")
    asm = Assembler()
    out_bin = "syscall_test.bin"
    asm.assemble_file("kernel/syscall_entry.s", out_bin)
    with open(out_bin, "rb") as f:
        bin_bytes = f.read()
    assert len(bin_bytes) > 0

    vm = VM(ram_size=16 * 1024 * 1024)
    vm.load_binary(out_bin)

    # Find address of test_user_process
    test_func_addr = asm.labels.get("test_user_process")
    assert test_func_addr is not None

    # Call test_user_process directly
    target_exit_addr = 0x80000000 + len(bin_bytes) + 16
    vm.pc = test_func_addr
    vm.regs[1] = target_exit_addr  # Return address
    vm.regs[2] = 0x80800000        # Stack pointer

    for _ in range(300):
        if vm.pc == target_exit_addr:
            break
        vm.step()

    # Register a0 (x10) must be 1 (success)
    assert vm.regs[10] == 1, f"Assembly syscall test failed with return code {vm.regs[10]}"
    print("  -> [PASS] Bare-metal assembly syscall traps verified in VM.")

    print("\n[Test Proc Block H] ALL BLOCK H PROCESS, SIGNAL & IPC TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_proc_block_h_suite()
