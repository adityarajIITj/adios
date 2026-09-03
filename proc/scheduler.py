#!/usr/bin/env python3
"""
AdiOS Process Subsystem: Multi-Level Feedback Queue (MLFQ) Scheduler (scheduler.py)
Implements enterprise-grade preemptive multi-priority scheduling, dynamic quantum decay,
anti-starvation priority boosting, and timer-driven task wakeup.
"""

from typing import Dict, List, Optional
from collections import deque
from proc.process import TaskControlBlock, ProcessState, PriorityClass

PRIORITY_BOOST_TICKS = 1000

class MLFQScheduler:
    """
    Multi-Level Feedback Queue Scheduler with 4 Priority Bands.
    Band 0 (REALTIME): Real-time audio synth & hardware graphics (Quantum 20)
    Band 1 (HIGH):     Interactive UI & Window Manager (Quantum 15)
    Band 2 (NORMAL):   Standard userland computing tasks (Quantum 10)
    Band 3 (IDLE):     Background entropy harvesting & memory compaction (Quantum 5)
    """
    def __init__(self):
        self.queues: List[deque] = [deque(), deque(), deque(), deque()]
        self.all_processes: Dict[int, TaskControlBlock] = {}
        self.current_process: Optional[TaskControlBlock] = None
        self.current_tick: int = 0
        self.ticks_since_boost: int = 0
        self.context_switch_count: int = 0

    def add_process(self, proc: TaskControlBlock):
        """Enrolls a new or forked process into the scheduler."""
        self.all_processes[proc.pid] = proc
        proc.state = ProcessState.READY
        prio_idx = int(proc.priority)
        self.queues[prio_idx].append(proc)

    def remove_process(self, pid: int):
        """Removes a dead or reclaimed process from all scheduler queues."""
        if pid in self.all_processes:
            proc = self.all_processes[pid]
            prio_idx = int(proc.priority)
            if proc in self.queues[prio_idx]:
                self.queues[prio_idx].remove(proc)
            del self.all_processes[pid]
            if self.current_process and self.current_process.pid == pid:
                self.current_process = None

    def tick(self) -> Optional[TaskControlBlock]:
        """
        Invoked on each hardware timer interrupt (e.g. 100 Hz / 10ms).
        Updates quantum, wakes sleeping tasks, performs priority boosting,
        and returns next process to execute.
        """
        self.current_tick += 1
        self.ticks_since_boost += 1

        # 1. Wake up sleeping processes whose timer expired
        self._wake_sleeping_tasks()

        # 2. Priority Boost: Prevent starvation by promoting all tasks to Band 0/1
        if self.ticks_since_boost >= PRIORITY_BOOST_TICKS:
            self._priority_boost()
            self.ticks_since_boost = 0

        # 3. Decrement current process quantum
        if self.current_process and self.current_process.state == ProcessState.RUNNING:
            self.current_process.quantum_left -= 1
            self.current_process.metrics.cpu_time_ticks += 1

            if self.current_process.quantum_left <= 0:
                # Quantum expired: Quantum decay (demote to lower priority queue unless already IDLE)
                curr = self.current_process
                curr.state = ProcessState.READY
                if curr.priority < PriorityClass.IDLE:
                    curr.priority = PriorityClass(curr.priority + 1)
                curr.quantum_left = self._get_quantum_for_priority(curr.priority)
                self.queues[int(curr.priority)].append(curr)
                self.current_process = None

        # 4. Schedule next process if current is None or not running
        if self.current_process is None or self.current_process.state != ProcessState.RUNNING:
            next_proc = self._pick_next_process()
            if next_proc and next_proc != self.current_process:
                self.context_switch_count += 1
                next_proc.state = ProcessState.RUNNING
                next_proc.metrics.context_switches += 1
                self.current_process = next_proc

        return self.current_process

    def _get_quantum_for_priority(self, prio: PriorityClass) -> int:
        if prio == PriorityClass.REALTIME:
            return 20
        elif prio == PriorityClass.HIGH:
            return 15
        elif prio == PriorityClass.NORMAL:
            return 10
        return 5

    def _pick_next_process(self) -> Optional[TaskControlBlock]:
        """Scans queues from highest priority (0) to lowest (3)."""
        for prio_idx in range(4):
            queue = self.queues[prio_idx]
            while queue:
                candidate = queue.popleft()
                if candidate.state == ProcessState.READY:
                    return candidate
                elif candidate.state in (ProcessState.ZOMBIE, ProcessState.DEAD):
                    continue  # Discard dead processes
                else:
                    # Still sleeping or stopped, do not run
                    pass
        return None

    def _wake_sleeping_tasks(self):
        """Wakes any process whose sleep deadline has passed."""
        for proc in self.all_processes.values():
            if proc.state == ProcessState.SLEEPING and proc.sleep_until_tick > 0:
                if self.current_tick >= proc.sleep_until_tick:
                    proc.state = ProcessState.READY
                    proc.sleep_until_tick = 0
                    self.queues[int(proc.priority)].append(proc)

    def _priority_boost(self):
        """Moves all ready tasks from lower queues into HIGH queue to prevent starvation."""
        for prio_idx in (2, 3):
            while self.queues[prio_idx]:
                p = self.queues[prio_idx].popleft()
                p.priority = PriorityClass.HIGH
                p.quantum_left = self._get_quantum_for_priority(p.priority)
                self.queues[1].append(p)

    def sleep_current(self, ticks: int):
        """Blocks current process for specified number of ticks."""
        if self.current_process:
            self.current_process.state = ProcessState.SLEEPING
            self.current_process.sleep_until_tick = self.current_tick + ticks
            self.current_process = None

    def yield_current(self):
        """Voluntary yield: Current process relinquishes CPU without priority penalty."""
        if self.current_process and self.current_process.state == ProcessState.RUNNING:
            curr = self.current_process
            curr.state = ProcessState.READY
            curr.quantum_left = self._get_quantum_for_priority(curr.priority)
            self.queues[int(curr.priority)].append(curr)
            self.current_process = None

if __name__ == "__main__":
    sched = MLFQScheduler()
    p1 = TaskControlBlock("realtime_audio", priority=PriorityClass.REALTIME)
    p2 = TaskControlBlock("window_manager", priority=PriorityClass.HIGH)
    p3 = TaskControlBlock("background_calc", priority=PriorityClass.NORMAL)

    sched.add_process(p1)
    sched.add_process(p2)
    sched.add_process(p3)

    # First tick must pick Real-Time task
    running = sched.tick()
    assert running.pid == p1.pid
    print(f"Tick 1: Selected PID {running.pid} ({running.name})")

    # Run p1 until its quantum expires (20 ticks)
    for _ in range(21):
        running = sched.tick()

    print(f"Post-quantum: PID {running.pid} ({running.name}) scheduled")
    print("MLFQ Scheduler verification successful.")
