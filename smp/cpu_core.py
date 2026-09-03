#!/usr/bin/env python3
"""
AdiOS SMP Subsystem: Multi-Core Architecture & IPI Engine (cpu_core.py)
Implements RISC-V Symmetric Multiprocessing (SMP):
- Multi-Hart (Hardware Thread) state & execution context
- Core Local Interruptor (CLINT) & Machine Software Interrupt (MSIP) IPI
- Inter-Processor Interrupt (IPI) message dispatch (smp_call_function)
- Per-CPU data structures & atomic Ticket Locks
Zero external dependencies.
"""

from typing import List, Dict, Callable, Optional, Any, Tuple

class TicketLock:
    """Fair FIFO atomic ticket lock for SMP synchronization."""
    def __init__(self):
        self.ticket = 0
        self.now_serving = 0

    def acquire(self) -> int:
        my_ticket = self.ticket
        self.ticket += 1
        # In single-threaded simulation, progress immediately
        self.now_serving = my_ticket
        return my_ticket

    def release(self):
        self.now_serving += 1

class PerCPUData:
    """Isolated per-hart data cache."""
    def __init__(self, hart_id: int):
        self.hart_id = hart_id
        self.current_tcb_id: Optional[int] = None
        self.interrupt_count = 0
        self.ipi_pending_queue: List[Tuple[Callable, Any]] = []

class Hart:
    """RISC-V Hardware Thread (Hart) model."""
    def __init__(self, hart_id: int):
        self.hart_id = hart_id
        self.pc = 0x80000000
        self.regs = [0] * 32
        self.active = True
        self.per_cpu = PerCPUData(hart_id)

class CLINT:
    """Core Local Interruptor managing MSIP registers and cross-core IPI."""
    def __init__(self, num_harts: int = 4):
        self.num_harts = num_harts
        self.msip = [0] * num_harts # 1 bit per hart

    def trigger_ipi(self, target_hart: int):
        if 0 <= target_hart < self.num_harts:
            self.msip[target_hart] = 1

    def clear_ipi(self, hart_id: int):
        if 0 <= hart_id < self.num_harts:
            self.msip[hart_id] = 0

class SMPController:
    """
    Coordinates multi-hart topology, IPI dispatch, and atomic locks.
    """
    def __init__(self, num_harts: int = 4):
        self.num_harts = num_harts
        self.harts = [Hart(i) for i in range(num_harts)]
        self.clint = CLINT(num_harts)
        self.global_lock = TicketLock()

    def send_ipi(self, src_hart: int, dst_hart: int, func: Callable, arg: Any = None):
        """Sends cross-core function execution via IPI."""
        if 0 <= dst_hart < self.num_harts:
            self.harts[dst_hart].per_cpu.ipi_pending_queue.append((func, arg))
            self.clint.trigger_ipi(dst_hart)

    def process_ipi(self, hart_id: int):
        """Processes all pending IPI requests for the given hart."""
        hart = self.harts[hart_id]
        if self.clint.msip[hart_id]:
            while hart.per_cpu.ipi_pending_queue:
                fn, arg = hart.per_cpu.ipi_pending_queue.pop(0)
                fn(arg)
                hart.per_cpu.interrupt_count += 1
            self.clint.clear_ipi(hart_id)

if __name__ == "__main__":
    smp = SMPController(num_harts=4)
    executed = []
    def remote_call(msg):
        executed.append(msg)

    smp.send_ipi(src_hart=0, dst_hart=2, func=remote_call, arg="SMP Core 2 Active")
    assert smp.clint.msip[2] == 1
    smp.process_ipi(2)
    assert smp.clint.msip[2] == 0
    assert executed == ["SMP Core 2 Active"]
    print("SMP multi-hart controller and IPI engine verified.")
