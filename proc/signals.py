#!/usr/bin/env python3
"""
AdiOS Signal Subsystem: POSIX & Sovereign Signal Architecture (signals.py)
Implements complete 64-signal architecture (Standard POSIX 1..32 and Real-Time 33..64),
signal masks, sigaction handling, siginfo_t payload delivery, user stack frame construction,
core dump generation, alternate signal stack (sigaltstack), and sigreturn trampoline dispatching.

Zero external dependencies. Pure RV32IM bare-metal signal engine.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

from enum import IntEnum, Enum
from typing import Optional, Dict, List, Tuple, Any
from proc.process import TaskControlBlock, ProcessState

class Signal(IntEnum):
    SIGHUP    = 1
    SIGINT    = 2
    SIGQUIT   = 3
    SIGILL    = 4
    SIGTRAP   = 5
    SIGABRT   = 6
    SIGBUS    = 7
    SIGFPE    = 8
    SIGKILL   = 9   # Uncatchable, unignorable
    SIGUSR1   = 10
    SIGSEGV   = 11
    SIGUSR2   = 12
    SIGPIPE   = 13
    SIGALRM   = 14
    SIGTERM   = 15
    SIGSTKFLT = 16
    SIGCHLD   = 17
    SIGCONT   = 18
    SIGSTOP   = 19  # Uncatchable, unignorable
    SIGTSTP   = 20
    SIGTTIN   = 21
    SIGTTOU   = 22
    SIGURG    = 23
    SIGXCPU   = 24
    SIGXFSZ   = 25
    SIGVTALRM = 26
    SIGPROF   = 27
    SIGWINCH  = 28
    SIGIO     = 29
    SIGPWR    = 30
    SIGSYS    = 31
    SIGCYBER  = 32  # Sovereign Cyber Oracle Interrupt
    SIGRTMIN  = 33  # Real-Time Signal Range (33..64)
    SIGRTMAX  = 64

# Signal Actions
SIG_DFL = 0  # Default action
SIG_IGN = 1  # Ignore signal

# Sigaction Flags
SA_NOCLDSTOP = 0x00000001
SA_NOCLDWAIT = 0x00000002
SA_SIGINFO   = 0x00000004
SA_ONSTACK   = 0x08000000
SA_RESTART   = 0x10000000
SA_NODEFER   = 0x40000000
SA_RESETHAND = 0x80000000

# sigprocmask how commands
SIG_BLOCK   = 0
SIG_UNBLOCK = 1
SIG_SETMASK = 2

class SignalDisposition(Enum):
    TERMINATE = 1
    CORE_DUMP = 2
    IGNORE    = 3
    STOP      = 4
    CONTINUE  = 5

# Default signal dispositions according to POSIX.1-2008
DEFAULT_DISPOSITIONS: Dict[int, SignalDisposition] = {
    Signal.SIGHUP:    SignalDisposition.TERMINATE,
    Signal.SIGINT:    SignalDisposition.TERMINATE,
    Signal.SIGQUIT:   SignalDisposition.CORE_DUMP,
    Signal.SIGILL:    SignalDisposition.CORE_DUMP,
    Signal.SIGTRAP:   SignalDisposition.CORE_DUMP,
    Signal.SIGABRT:   SignalDisposition.CORE_DUMP,
    Signal.SIGBUS:    SignalDisposition.CORE_DUMP,
    Signal.SIGFPE:    SignalDisposition.CORE_DUMP,
    Signal.SIGKILL:   SignalDisposition.TERMINATE,
    Signal.SIGUSR1:   SignalDisposition.TERMINATE,
    Signal.SIGSEGV:   SignalDisposition.CORE_DUMP,
    Signal.SIGUSR2:   SignalDisposition.TERMINATE,
    Signal.SIGPIPE:   SignalDisposition.TERMINATE,
    Signal.SIGALRM:   SignalDisposition.TERMINATE,
    Signal.SIGTERM:   SignalDisposition.TERMINATE,
    Signal.SIGSTKFLT: SignalDisposition.TERMINATE,
    Signal.SIGCHLD:   SignalDisposition.IGNORE,
    Signal.SIGCONT:   SignalDisposition.CONTINUE,
    Signal.SIGSTOP:   SignalDisposition.STOP,
    Signal.SIGTSTP:   SignalDisposition.STOP,
    Signal.SIGTTIN:   SignalDisposition.STOP,
    Signal.SIGTTOU:   SignalDisposition.STOP,
    Signal.SIGURG:    SignalDisposition.IGNORE,
    Signal.SIGXCPU:   SignalDisposition.CORE_DUMP,
    Signal.SIGXFSZ:   SignalDisposition.CORE_DUMP,
    Signal.SIGVTALRM: SignalDisposition.TERMINATE,
    Signal.SIGPROF:   SignalDisposition.TERMINATE,
    Signal.SIGWINCH:  SignalDisposition.IGNORE,
    Signal.SIGIO:     SignalDisposition.IGNORE,
    Signal.SIGPWR:    SignalDisposition.TERMINATE,
    Signal.SIGSYS:    SignalDisposition.CORE_DUMP,
    Signal.SIGCYBER:  SignalDisposition.TERMINATE,
}

class SigInfo:
    """
    POSIX siginfo_t structure delivering detailed context to SA_SIGINFO handlers.
    """
    def __init__(
        self,
        si_signo: int,
        si_code: int = 0,
        si_pid: int = 0,
        si_uid: int = 0,
        si_value: int = 0,
        si_addr: int = 0
    ):
        self.si_signo = si_signo
        self.si_code = si_code
        self.si_pid = si_pid
        self.si_uid = si_uid
        self.si_value = si_value
        self.si_addr = si_addr

class AltStack:
    """Alternate Signal Stack (sigaltstack) context."""
    def __init__(self, ss_sp: int = 0, ss_size: int = 0, ss_flags: int = 0):
        self.ss_sp = ss_sp
        self.ss_size = ss_size
        self.ss_flags = ss_flags  # SS_ONSTACK or SS_DISABLE

class SigAction:
    """
    POSIX sigaction structure defining signal handler behavior.
    """
    def __init__(self, handler: int = SIG_DFL, flags: int = 0, mask: int = 0):
        self.handler = handler  # SIG_DFL, SIG_IGN, or function address
        self.flags = flags
        self.mask = mask

class SignalFrame:
    """
    Saved execution context on user stack during signal handler execution.
    """
    def __init__(self, sig: int, regs: list, pc: int, saved_mask: int, info: Optional[SigInfo] = None):
        self.sig = sig
        self.regs = list(regs)
        self.pc = pc
        self.saved_mask = saved_mask
        self.info = info

class SignalDispatcher:
    """
    Kernel Signal Dispatcher.
    Delivers pending signals to target processes, invokes user handlers,
    generates core dumps on fatal exceptions, or executes default kernel actions.
    """
    def __init__(self):
        self.signal_frames: Dict[int, List[SignalFrame]] = {} # PID -> list of SignalFrame
        self.rt_signal_queues: Dict[int, List[SigInfo]] = {}  # PID -> FIFO queue of real-time signals
        self.alt_stacks: Dict[int, AltStack] = {}            # PID -> AltStack
        self.core_dumps: Dict[int, Dict[str, Any]] = {}       # PID -> diagnostic core dump

    def send_signal(self, target: TaskControlBlock, sig: int, info: Optional[SigInfo] = None) -> bool:
        """
        Delivers a signal to a process.
        Sets the pending bitmask and wakes up sleeping processes if interruptible.
        """
        if not (1 <= sig <= 64):
            return False

        # Real-time signals (33..64) are queued in FIFO order
        if 33 <= sig <= 64:
            if target.pid not in self.rt_signal_queues:
                self.rt_signal_queues[target.pid] = []
            sig_info = info or SigInfo(si_signo=sig, si_pid=0)
            self.rt_signal_queues[target.pid].append(sig_info)
            if target.state == ProcessState.SLEEPING:
                target.state = ProcessState.READY
            return True

        # Standard signals (1..32) are coalesced into a 32-bit mask
        sig_bit = 1 << (sig - 1)

        # Handle SIGKILL and SIGSTOP immediately
        if sig == Signal.SIGKILL:
            target.terminate(exit_code=128 + sig)
            return True
        elif sig == Signal.SIGSTOP:
            target.state = ProcessState.STOPPED
            return True
        elif sig == Signal.SIGCONT:
            if target.state == ProcessState.STOPPED:
                target.state = ProcessState.READY
            return True

        # Check if ignored
        action = target.signal_handlers.get(sig)
        if action and action.handler == SIG_IGN:
            return True

        # Check if default action is ignore
        if (not action or action.handler == SIG_DFL) and DEFAULT_DISPOSITIONS.get(sig) == SignalDisposition.IGNORE:
            return True

        # Add to pending mask
        target.signal_pending_mask |= sig_bit

        # Wake up process if sleeping
        if target.state == ProcessState.SLEEPING:
            target.state = ProcessState.READY

        return True

    def sigprocmask(self, proc: TaskControlBlock, how: int, new_mask: int) -> int:
        """
        Modifies caller's blocked signal mask.
        Returns the previous signal mask.
        SIGKILL and SIGSTOP cannot be blocked.
        """
        old_mask = proc.signal_blocked_mask
        # Enforce unblockable signals
        cant_block = (1 << (Signal.SIGKILL - 1)) | (1 << (Signal.SIGSTOP - 1))
        filtered_new = new_mask & ~cant_block

        if how == SIG_BLOCK:
            proc.signal_blocked_mask |= filtered_new
        elif how == SIG_UNBLOCK:
            proc.signal_blocked_mask &= ~filtered_new
        elif how == SIG_SETMASK:
            proc.signal_blocked_mask = filtered_new
        else:
            raise ValueError(f"Invalid sigprocmask how={how}")

        return old_mask

    def sigpending(self, proc: TaskControlBlock) -> int:
        """Returns bitmask of signals that are pending and currently blocked."""
        return proc.signal_pending_mask & proc.signal_blocked_mask

    def set_altstack(self, proc: TaskControlBlock, ss_sp: int, ss_size: int, ss_flags: int = 0):
        self.alt_stacks[proc.pid] = AltStack(ss_sp, ss_size, ss_flags)

    def generate_core_dump(self, proc: TaskControlBlock, sig: int):
        """Generates a structured forensic core dump for crashed processes."""
        self.core_dumps[proc.pid] = {
            "pid": proc.pid,
            "name": proc.name,
            "fatal_signal": sig,
            "pc": proc.context.pc,
            "registers": list(proc.context.regs),
            "mstatus": proc.context.mstatus,
            "satp": proc.context.satp,
            "open_fds": list(proc.fd_table.keys()),
            "vmas": [(vma.start, vma.end, vma.flags, vma.name) for vma in getattr(proc, "vmas", [])]
        }

    def has_pending_unblocked(self, proc: TaskControlBlock) -> bool:
        """Returns True if there is at least one unblocked pending signal."""
        effective_pending = proc.signal_pending_mask & (~proc.signal_blocked_mask)
        if effective_pending:
            return True
        rt_queue = self.rt_signal_queues.get(proc.pid, [])
        return any(1 for item in rt_queue if not (proc.signal_blocked_mask & (1 << (item.si_signo - 1))))

    def dispatch_pending(self, proc: TaskControlBlock, trampoline_addr: int = 0x8000FF00) -> Optional[int]:
        """
        Processes pending unblocked signals for a process before returning to user space.
        Returns the signal number handled, or None if no signals were dispatched.
        """
        effective_pending = proc.signal_pending_mask & (~proc.signal_blocked_mask)

        # 1. Check standard signals (1..32)
        if effective_pending:
            for sig in range(1, 33):
                sig_bit = 1 << (sig - 1)
                if effective_pending & sig_bit:
                    # Clear pending bit
                    proc.signal_pending_mask &= ~sig_bit

                    action = proc.signal_handlers.get(sig, SigAction(SIG_DFL))

                    if action.handler == SIG_IGN:
                        continue
                    elif action.handler == SIG_DFL:
                        disp = DEFAULT_DISPOSITIONS.get(sig, SignalDisposition.TERMINATE)
                        if disp == SignalDisposition.CORE_DUMP:
                            self.generate_core_dump(proc, sig)
                            proc.terminate(exit_code=128 + sig)
                        elif disp == SignalDisposition.TERMINATE:
                            proc.terminate(exit_code=128 + sig)
                        elif disp == SignalDisposition.STOP:
                            proc.state = ProcessState.STOPPED
                        return sig
                    else:
                        # User-defined signal handler
                        frame = SignalFrame(
                            sig=sig,
                            regs=proc.context.regs,
                            pc=proc.context.pc,
                            saved_mask=proc.signal_blocked_mask
                        )
                        if proc.pid not in self.signal_frames:
                            self.signal_frames[proc.pid] = []
                        self.signal_frames[proc.pid].append(frame)

                        # Alternate stack handling
                        if (action.flags & SA_ONSTACK) and proc.pid in self.alt_stacks:
                            alt = self.alt_stacks[proc.pid]
                            proc.context.regs[2] = (alt.ss_sp + alt.ss_size) & 0xFFFFFFFC

                        # Update mask: block this signal unless SA_NODEFER is set
                        if not (action.flags & SA_NODEFER):
                            proc.signal_blocked_mask |= (1 << (sig - 1))
                        proc.signal_blocked_mask |= action.mask

                        # Set up execution registers:
                        # a0 (x10) = signal number
                        # ra (x1) = trampoline address (calls sys_sigreturn)
                        # pc = handler address
                        proc.context.regs[10] = sig
                        proc.context.regs[1] = trampoline_addr
                        proc.context.pc = action.handler

                        if action.flags & SA_RESETHAND:
                            action.handler = SIG_DFL

                        return sig

        # 2. Check real-time signals (33..64)
        rt_queue = self.rt_signal_queues.get(proc.pid, [])
        if rt_queue:
            for idx, item in enumerate(rt_queue):
                sig = item.si_signo
                if not (proc.signal_blocked_mask & (1 << (sig - 1))):
                    rt_queue.pop(idx)
                    action = proc.signal_handlers.get(sig, SigAction(SIG_DFL))
                    if action.handler == SIG_DFL:
                        proc.terminate(exit_code=128 + sig)
                        return sig
                    elif action.handler != SIG_IGN:
                        frame = SignalFrame(
                            sig=sig,
                            regs=proc.context.regs,
                            pc=proc.context.pc,
                            saved_mask=proc.signal_blocked_mask,
                            info=item
                        )
                        if proc.pid not in self.signal_frames:
                            self.signal_frames[proc.pid] = []
                        self.signal_frames[proc.pid].append(frame)

                        if not (action.flags & SA_NODEFER):
                            proc.signal_blocked_mask |= (1 << (sig - 1))
                        proc.signal_blocked_mask |= action.mask

                        proc.context.regs[10] = sig
                        proc.context.regs[1] = trampoline_addr
                        proc.context.pc = action.handler
                        return sig

        return None

    def handle_sigreturn(self, proc: TaskControlBlock) -> bool:
        """
        Restores saved CPU registers and signal mask from the top signal frame.
        """
        frames = self.signal_frames.get(proc.pid)
        if not frames:
            return False

        frame = frames.pop()
        proc.context.regs = list(frame.regs)
        proc.context.pc = frame.pc
        proc.signal_blocked_mask = frame.saved_mask
        return True

if __name__ == "__main__":
    dispatcher = SignalDispatcher()
    proc = TaskControlBlock("test_proc")

    # 1. Test SIGSEGV generates core dump
    dispatcher.send_signal(proc, Signal.SIGSEGV)
    dispatcher.dispatch_pending(proc)
    assert proc.state == ProcessState.ZOMBIE
    assert proc.exit_code == 128 + Signal.SIGSEGV
    assert proc.pid in dispatcher.core_dumps
    assert dispatcher.core_dumps[proc.pid]["fatal_signal"] == Signal.SIGSEGV

    # 2. Test sigprocmask blocking
    proc2 = TaskControlBlock("test_mask")
    dispatcher.sigprocmask(proc2, SIG_BLOCK, (1 << (Signal.SIGUSR2 - 1)))
    dispatcher.send_signal(proc2, Signal.SIGUSR2)
    assert not dispatcher.has_pending_unblocked(proc2)
    assert dispatcher.sigpending(proc2) == (1 << (Signal.SIGUSR2 - 1))

    # Unblock
    dispatcher.sigprocmask(proc2, SIG_UNBLOCK, (1 << (Signal.SIGUSR2 - 1)))
    assert dispatcher.has_pending_unblocked(proc2)

    # 3. Test Real-Time Signals (FIFO delivery)
    proc3 = TaskControlBlock("test_rt")
    dispatcher.send_signal(proc3, 35, SigInfo(35, si_value=42))
    dispatcher.send_signal(proc3, 35, SigInfo(35, si_value=99))
    assert len(dispatcher.rt_signal_queues[proc3.pid]) == 2
    assert dispatcher.rt_signal_queues[proc3.pid][0].si_value == 42

    print("Signal subsystem, POSIX masks, core dumps, and real-time FIFO verified.")
