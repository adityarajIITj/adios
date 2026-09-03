#!/usr/bin/env python3
"""
Test Suite: Block Q Multi-Core SMP & Microkernel IPC Architecture
Verifies:
1. smp/cpu_core: TicketLock atomic synchronization & fair order
2. smp/cpu_core: Per-CPU data structures & Hart context isolation
3. smp/cpu_core: CLINT MSIP IPI cross-core message execution
4. smp/smp_scheduler: Multi-queue work-stealing & CPU affinity
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from smp.cpu_core import SMPController, TicketLock
from smp.smp_scheduler import SMPScheduler, SMPTask

def test_smp_block_q_suite():
    print("[Test SMP Block Q] Initializing Multi-Core SMP & IPC Verification...")

    # 1. Test TicketLock Atomic Fair Ordering
    print("  -> Testing TicketLock fair FIFO ordering...")
    lock = TicketLock()
    t1 = lock.acquire()
    lock.release()
    t2 = lock.acquire()
    lock.release()
    assert t1 == 0
    assert t2 == 1
    assert lock.now_serving == 2
    print("  -> [PASS] TicketLock ordering verified.")

    # 2. Test Multi-Hart Controller & IPI Dispatch
    print("  -> Testing SMPController & CLINT IPI Engine...")
    smp = SMPController(num_harts=4)
    assert len(smp.harts) == 4

    # Verify per-CPU data isolation
    smp.harts[0].per_cpu.current_tcb_id = 101
    smp.harts[1].per_cpu.current_tcb_id = 202
    assert smp.harts[0].per_cpu.current_tcb_id == 101
    assert smp.harts[1].per_cpu.current_tcb_id == 202

    # Send cross-core IPI from Hart 0 to Hart 3
    ipi_log = []
    def core3_task(payload):
        ipi_log.append(f"Hart3 executed: {payload}")

    smp.send_ipi(src_hart=0, dst_hart=3, func=core3_task, arg="Quantum Core Sync")
    assert smp.clint.msip[3] == 1
    assert smp.clint.msip[0] == 0

    # Process IPI on Hart 3
    smp.process_ipi(hart_id=3)
    assert smp.clint.msip[3] == 0
    assert smp.harts[3].per_cpu.interrupt_count == 1
    assert ipi_log == ["Hart3 executed: Quantum Core Sync"]
    print("  -> [PASS] SMPController & IPI cross-core dispatch verified.")

    # 3. Test Multi-Core Work-Stealing Scheduler
    print("  -> Testing Multi-Core Work-Stealing Scheduler & Affinity...")
    sched = SMPScheduler(num_harts=4)

    # Task pinned strictly to Core 0 (mask 0b0001)
    task_pinned0 = SMPTask(10, "TaskPinned0", affinity_mask=0b0001)
    # Task flexible (can run on any core: mask 0b1111)
    task_flex1 = SMPTask(20, "TaskFlex1", affinity_mask=0b1111)
    task_flex2 = SMPTask(30, "TaskFlex2", affinity_mask=0b1111)

    # All enqueued onto Core 0 initially
    sched.enqueue_task(task_pinned0, preferred_hart=0)
    sched.enqueue_task(task_flex1, preferred_hart=0)
    sched.enqueue_task(task_flex2, preferred_hart=0)

    assert len(sched.queues[0]) == 3
    assert len(sched.queues[2]) == 0

    # Core 2 runs and has an empty queue -> steals from Core 0!
    stolen_task = sched.schedule_hart(hart_id=2)
    assert stolen_task is not None
    assert stolen_task.task_id in (20, 30) # Pinned task must NOT be stolen!
    assert stolen_task.runs_count == 1

    # Core 0 runs its next task -> should be task_pinned0
    c0_task = sched.schedule_hart(hart_id=0)
    assert c0_task.task_id == 10
    print("  -> [PASS] Work-stealing with CPU affinity verified.")

    print("\n[Test SMP Block Q] ALL BLOCK Q MULTI-CORE SMP TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_smp_block_q_suite()
