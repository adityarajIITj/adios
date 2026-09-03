#!/usr/bin/env python3
"""
AdiOS SMP Subsystem: Multi-Queue Work-Stealing Scheduler (smp_scheduler.py)
Implements scalable multi-core scheduling:
- Per-core local runqueues
- Core CPU affinity bitmasks
- Work-Stealing algorithm for automatic load balancing
Zero external dependencies.
"""

from typing import List, Dict, Optional

class SMPTask:
    """Task scheduled across multi-core topology."""
    def __init__(self, task_id: int, name: str, affinity_mask: int = 0xFF):
        self.task_id = task_id
        self.name = name
        self.affinity_mask = affinity_mask # Bitmask: 1 << hart_id
        self.runs_count = 0

class SMPScheduler:
    """
    Multi-core scheduler managing per-hart queues and work stealing.
    """
    def __init__(self, num_harts: int = 4):
        self.num_harts = num_harts
        self.queues: List[List[SMPTask]] = [[] for _ in range(num_harts)]

    def enqueue_task(self, task: SMPTask, preferred_hart: Optional[int] = None):
        """Enqueues task respecting affinity mask."""
        target = preferred_hart if preferred_hart is not None else 0
        if not (task.affinity_mask & (1 << target)):
            # Find first matching hart
            for h in range(self.num_harts):
                if task.affinity_mask & (1 << h):
                    target = h
                    break
        self.queues[target].append(task)

    def schedule_hart(self, hart_id: int) -> Optional[SMPTask]:
        """Picks next task for core, performing work-stealing if queue is empty."""
        local_q = self.queues[hart_id]
        if local_q:
            task = local_q.pop(0)
            task.runs_count += 1
            return task

        # Work stealing: steal from the most loaded sibling hart
        most_loaded_hart = -1
        max_depth = 0
        for h in range(self.num_harts):
            if h != hart_id and len(self.queues[h]) > max_depth:
                # Check if any task in queue h can run on hart_id
                for t in self.queues[h]:
                    if t.affinity_mask & (1 << hart_id):
                        max_depth = len(self.queues[h])
                        most_loaded_hart = h
                        break

        if most_loaded_hart != -1:
            for i, t in enumerate(self.queues[most_loaded_hart]):
                if t.affinity_mask & (1 << hart_id):
                    stolen = self.queues[most_loaded_hart].pop(i)
                    stolen.runs_count += 1
                    return stolen

        return None

if __name__ == "__main__":
    sched = SMPScheduler(num_harts=4)
    t1 = SMPTask(1, "TaskCore0Pinned", affinity_mask=0b0001)
    t2 = SMPTask(2, "TaskAnyCore", affinity_mask=0b1111)
    t3 = SMPTask(3, "TaskAnyCore2", affinity_mask=0b1111)

    sched.enqueue_task(t1, preferred_hart=0)
    sched.enqueue_task(t2, preferred_hart=0)
    sched.enqueue_task(t3, preferred_hart=0)

    # Core 1 is idle, it should steal t2 or t3
    stolen = sched.schedule_hart(hart_id=1)
    assert stolen is not None
    assert stolen.task_id in (2, 3)
    print("Multi-core work-stealing scheduler verified.")
