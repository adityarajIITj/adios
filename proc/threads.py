#!/usr/bin/env python3
"""
AdiOS Process & Concurrency Subsystem: Kernel Threading & Synchronization (proc/threads.py)
Implements kernel thread execution contexts and POSIX-style synchronization:
- Thread Control Block (TCB) with state machine (READY, RUNNING, BLOCKED, TERMINATED)
- Priority-preemptive multi-hart thread scheduler
- Sleeping Mutex with FIFO lock wait-queue
- Condition Variables (cond_wait, cond_signal, cond_broadcast)
- Counting Semaphores (sem_init, sem_wait, sem_post)
- Thread join and exit coordination

Zero external dependencies. Pure RV32IM bare-metal concurrency engine.
STRICT ZERO EMOJI POLICY.
"""

from enum import Enum
from typing import Dict, List, Tuple, Optional, Any, Callable

class ThreadState(Enum):
    READY      = 1
    RUNNING    = 2
    BLOCKED    = 3
    TERMINATED = 4

class ThreadControlBlock:
    """Kernel Thread Execution Context."""
    def __init__(self, tid: int, pid: int, name: str, entry_fn: Optional[Callable] = None, priority: int = 1, stack_size: int = 8192):
        self.tid = tid
        self.pid = pid
        self.name = name
        self.entry_fn = entry_fn
        self.priority = priority
        self.state = ThreadState.READY
        self.stack_size = stack_size
        self.stack_pointer = 0
        self.registers = [0] * 32
        self.wake_tick = 0
        self.exit_code = 0
        self.joined_by: List[int] = [] # list of tids waiting on join

    def __repr__(self):
        return f"<TCB tid={self.tid} name='{self.name}' state={self.state.name}>"

class Mutex:
    """
    Sleeping Mutex with FIFO wait-queue.
    """
    def __init__(self, name: str = "mutex"):
        self.name = name
        self.locked = False
        self.owner_tid: Optional[int] = None
        self.wait_queue: List[int] = []

    def acquire(self, tid: int) -> bool:
        """
        Attempts to acquire lock.
        Returns True if acquired immediately, False if thread must be blocked.
        """
        if not self.locked:
            self.locked = True
            self.owner_tid = tid
            return True
        else:
            if tid not in self.wait_queue:
                self.wait_queue.append(tid)
            return False

    def release(self, tid: int) -> Optional[int]:
        """
        Releases lock and returns next waiting tid to be unblocked, or None.
        """
        if not self.locked or self.owner_tid != tid:
            return None

        if self.wait_queue:
            next_tid = self.wait_queue.pop(0)
            self.owner_tid = next_tid
            return next_tid
        else:
            self.locked = False
            self.owner_tid = None
            return None

class ConditionVariable:
    """
    Condition Variable for thread coordination.
    """
    def __init__(self, name: str = "condvar"):
        self.name = name
        self.wait_queue: List[int] = []

    def wait(self, tid: int, mutex: Mutex) -> Optional[int]:
        """
        Enqueues thread on condition, releases mutex, and returns next tid to wake from mutex.
        """
        self.wait_queue.append(tid)
        return mutex.release(tid)

    def signal(self) -> Optional[int]:
        """Wakes one waiting thread."""
        if self.wait_queue:
            return self.wait_queue.pop(0)
        return None

    def broadcast(self) -> List[int]:
        """Wakes all waiting threads."""
        woken = list(self.wait_queue)
        self.wait_queue.clear()
        return woken

class CountingSemaphore:
    """
    Dijkstra counting semaphore.
    """
    def __init__(self, initial_value: int = 1):
        self.value = initial_value
        self.wait_queue: List[int] = []

    def wait(self, tid: int) -> bool:
        """Decrements semaphore or blocks calling thread."""
        if self.value > 0:
            self.value -= 1
            return True
        else:
            self.wait_queue.append(tid)
            return False

    def post(self) -> Optional[int]:
        """Increments semaphore and unblocks one waiting thread if present."""
        if self.wait_queue:
            return self.wait_queue.pop(0)
        else:
            self.value += 1
            return None

class ThreadScheduler:
    """
    Multi-threaded priority scheduler.
    """
    def __init__(self):
        self.threads: Dict[int, ThreadControlBlock] = {}
        self.ready_queue: List[int] = []
        self.current_tid: Optional[int] = None
        self.next_tid = 1

    def create_thread(self, pid: int, name: str, entry_fn: Optional[Callable] = None, priority: int = 1) -> ThreadControlBlock:
        tid = self.next_tid
        self.next_tid += 1
        tcb = ThreadControlBlock(tid=tid, pid=pid, name=name, entry_fn=entry_fn, priority=priority)
        self.threads[tid] = tcb
        self.ready_queue.append(tid)
        return tcb

    def schedule_next(self) -> Optional[ThreadControlBlock]:
        """Picks the highest priority ready thread."""
        if not self.ready_queue:
            return None

        # Sort ready queue by priority (higher value = higher priority)
        self.ready_queue.sort(key=lambda t: self.threads[t].priority, reverse=True)
        next_tid = self.ready_queue.pop(0)
        tcb = self.threads[next_tid]
        tcb.state = ThreadState.RUNNING
        self.current_tid = next_tid
        return tcb

    def block_thread(self, tid: int):
        if tid in self.threads:
            self.threads[tid].state = ThreadState.BLOCKED
            if tid in self.ready_queue:
                self.ready_queue.remove(tid)
            if self.current_tid == tid:
                self.current_tid = None

    def unblock_thread(self, tid: int):
        if tid in self.threads:
            tcb = self.threads[tid]
            tcb.state = ThreadState.READY
            if tid not in self.ready_queue:
                self.ready_queue.append(tid)

    def yield_thread(self, tid: int):
        if tid in self.threads:
            tcb = self.threads[tid]
            tcb.state = ThreadState.READY
            if tid not in self.ready_queue:
                self.ready_queue.append(tid)
            if self.current_tid == tid:
                self.current_tid = None

    def terminate_thread(self, tid: int, exit_code: int = 0) -> List[int]:
        """Terminates thread and returns list of threads unblocked by join."""
        if tid not in self.threads:
            return []

        tcb = self.threads[tid]
        tcb.state = ThreadState.TERMINATED
        tcb.exit_code = exit_code

        if tid in self.ready_queue:
            self.ready_queue.remove(tid)
        if self.current_tid == tid:
            self.current_tid = None

        # Unblock any joining threads
        woken = list(tcb.joined_by)
        for w_tid in woken:
            self.unblock_thread(w_tid)
        tcb.joined_by.clear()
        return woken
