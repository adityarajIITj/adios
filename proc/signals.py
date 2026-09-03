#!/usr/bin/env python3
"""
AdiOS Signal Subsystem: POSIX & Sovereign Signal Architecture (signals.py)
Implements complete 32-signal architecture, signal masks, sigaction handling,
user stack frame construction, and sigreturn trampoline dispatching.
"""

from enum import IntEnum
from typing import Optional, Dict
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

# Signal Actions
SIG_DFL = 0  # Default action
SIG_IGN = 1  # Ignore signal

# Sigaction Flags
SA_RESTART   = 0x10000000
SA_NODEFER   = 0x40000000
SA_RESETHAND = 0x80000000

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
    def __init__(self, sig: int, regs: list, pc: int, saved_mask: int):
        self.sig = sig
        self.regs = list(regs)
        self.pc = pc
        self.saved_mask = saved_mask

class SignalDispatcher:
    """
    Kernel Signal Dispatcher.
    Delivers pending signals to target processes, invokes user handlers,
    or executes default kernel actions.
    """
    def __init__(self):
        self.signal_frames: Dict[int, list] = {} # PID -> list of SignalFrame

    def send_signal(self, target: TaskControlBlock, sig: int) -> bool:
        """
        Delivers a signal to a process.
        Sets the pending bitmask and wakes up sleeping processes if interruptible.
        """
        if not (1 <= sig <= 32):
            return False

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

        # Check if default action is ignore (e.g. SIGCHLD, SIGURG, SIGWINCH)
        if (not action or action.handler == SIG_DFL) and sig in (Signal.SIGCHLD, Signal.SIGURG, Signal.SIGWINCH):
            return True

        # Add to pending mask
        target.signal_pending_mask |= sig_bit

        # Wake up process if sleeping
        if target.state == ProcessState.SLEEPING:
            target.state = ProcessState.READY

        return True

    def has_pending_unblocked(self, proc: TaskControlBlock) -> bool:
        """Returns True if there is at least one unblocked pending signal."""
        effective_pending = proc.signal_pending_mask & (~proc.signal_blocked_mask)
        return bool(effective_pending)

    def dispatch_pending(self, proc: TaskControlBlock, trampoline_addr: int = 0x8000FF00) -> Optional[int]:
        """
        Processes pending unblocked signals for a process before returning to user space.
        Returns the signal number handled, or None if no signals were dispatched.
        """
        effective_pending = proc.signal_pending_mask & (~proc.signal_blocked_mask)
        if not effective_pending:
            return None

        # Find lowest numbered pending signal
        for sig in range(1, 33):
            sig_bit = 1 << (sig - 1)
            if effective_pending & sig_bit:
                # Clear pending bit
                proc.signal_pending_mask &= ~sig_bit

                action = proc.signal_handlers.get(sig, SigAction(SIG_DFL))

                if action.handler == SIG_IGN:
                    continue
                elif action.handler == SIG_DFL:
                    # Execute default action
                    if sig in (Signal.SIGTERM, Signal.SIGINT, Signal.SIGQUIT, Signal.SIGSEGV, Signal.SIGILL, Signal.SIGABRT):
                        proc.terminate(exit_code=128 + sig)
                    elif sig == Signal.SIGTSTP:
                        proc.state = ProcessState.STOPPED
                    return sig
                else:
                    # User-defined signal handler!
                    # Save context frame for sigreturn
                    frame = SignalFrame(
                        sig=sig,
                        regs=proc.context.regs,
                        pc=proc.context.pc,
                        saved_mask=proc.signal_blocked_mask
                    )
                    if proc.pid not in self.signal_frames:
                        self.signal_frames[proc.pid] = []
                    self.signal_frames[proc.pid].append(frame)

                    # Update mask: block this signal unless SA_NODEFER is set
                    if not (action.flags & SA_NODEFER):
                        proc.signal_blocked_mask |= (1 << (sig - 1))
                    proc.signal_blocked_mask |= action.mask

                    # Setup execution frame:
                    # a0 (x10) = signal number
                    # ra (x1) = trampoline address (calls sys_sigreturn)
                    # pc = handler address
                    proc.context.regs[10] = sig
                    proc.context.regs[1] = trampoline_addr
                    proc.context.pc = action.handler

                    if action.flags & SA_RESETHAND:
                        action.handler = SIG_DFL

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
    proc = TaskControlBlock("test_proc")
    dispatcher = SignalDispatcher()

    # Test default SIGINT termination
    dispatcher.send_signal(proc, Signal.SIGINT)
    assert dispatcher.has_pending_unblocked(proc)
    sig_handled = dispatcher.dispatch_pending(proc)
    assert sig_handled == Signal.SIGINT
    assert proc.state == ProcessState.ZOMBIE
    assert proc.exit_code == 130 # 128 + 2

    # Test custom handler and sigreturn
    proc2 = TaskControlBlock("proc2")
    handler_pc = 0x80040000
    proc2.signal_handlers[Signal.SIGUSR1] = SigAction(handler=handler_pc)
    proc2.context.pc = 0x80010000
    proc2.context.regs[10] = 999

    dispatcher.send_signal(proc2, Signal.SIGUSR1)
    dispatcher.dispatch_pending(proc2)
    assert proc2.context.pc == handler_pc
    assert proc2.context.regs[10] == Signal.SIGUSR1

    # Return from handler
    dispatcher.handle_sigreturn(proc2)
    assert proc2.context.pc == 0x80010000
    assert proc2.context.regs[10] == 999
    print("POSIX and Sovereign signal handling verified.")
