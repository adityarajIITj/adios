#!/usr/bin/env python3
"""
AdiOS Compiler Linear Scan Register Allocator
Maps IR virtual registers (%v0, %v1, ...) to RISC-V hardware physical registers.
Allocatable registers:
- Temporaries: t0-t6 (caller-saved)
- Saved:       s0-s11 (callee-saved)
- Arguments:   a0-a7
Spill management: Assigns stack frame offsets when register pressure exceeds capacity.
"""

from typing import List, Dict, Set, Tuple, Optional
from .ir import IRFunction, IRInstruction, IROperand, IR_LABEL

# Allocatable RISC-V Hardware Registers
PHYSICAL_REGS = [
    "t0", "t1", "t2", "t3", "t4", "t5", "t6",
    "s0", "s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8", "s9", "s10", "s11",
    "a0", "a1", "a2", "a3", "a4", "a5", "a6", "a7"
]

class LiveInterval:
    def __init__(self, reg: IROperand, start: int, end: int):
        self.reg = reg
        self.start = start
        self.end = end
        self.assigned_reg: Optional[str] = None
        self.spill_offset: Optional[int] = None

    def __repr__(self) -> str:
        loc = self.assigned_reg if self.assigned_reg else f"stack[{self.spill_offset}]"
        return f"Interval({self.reg}: [{self.start}, {self.end}] -> {loc})"

class LinearScanRegisterAllocator:
    def __init__(self, physical_regs: Optional[List[str]] = None):
        self.physical_regs = physical_regs or list(PHYSICAL_REGS)
        self.active: List[LiveInterval] = []
        self.free_regs: List[str] = []
        self.allocation: Dict[IROperand, str] = {}
        self.spill_offsets: Dict[IROperand, int] = {}
        self.stack_frame_size = 0

    def allocate(self, func: IRFunction) -> Tuple[Dict[IROperand, str], Dict[IROperand, int], int]:
        """Runs linear scan on the function and returns (reg_map, spill_map, stack_frame_size)."""
        instructions = func.linear_instructions()
        intervals = self._compute_live_intervals(instructions)

        # Sort intervals by start instruction index
        sorted_intervals = sorted(intervals.values(), key=lambda i: i.start)

        self.active = []
        self.free_regs = list(self.physical_regs)
        self.allocation = {}
        self.spill_offsets = {}
        curr_spill_offset = 16 # Start above return address & frame pointer

        for interval in sorted_intervals:
            self._expire_old_intervals(interval.start)

            if len(self.active) < len(self.physical_regs) and self.free_regs:
                # Allocate next free register
                phys_reg = self.free_regs.pop(0)
                interval.assigned_reg = phys_reg
                self.allocation[interval.reg] = phys_reg
                self._insert_active(interval)
            else:
                # Spill either current interval or active interval with longest remaining range
                spilled = self._spill_at_interval(interval, curr_spill_offset)
                if spilled:
                    curr_spill_offset += 4

        self.stack_frame_size = (curr_spill_offset + 15) // 16 * 16 # Align to 16 bytes
        return self.allocation, self.spill_offsets, self.stack_frame_size

    def _compute_live_intervals(self, instructions: List[IRInstruction]) -> Dict[IROperand, LiveInterval]:
        intervals: Dict[IROperand, LiveInterval] = {}

        for idx, inst in enumerate(instructions):
            # Check register definition
            if inst.dest and inst.dest.is_reg():
                reg = inst.dest
                if reg not in intervals:
                    intervals[reg] = LiveInterval(reg, idx, idx)
                else:
                    intervals[reg].end = max(intervals[reg].end, idx)

            # Check register uses
            for src in (inst.src1, inst.src2):
                if src and src.is_reg():
                    if src not in intervals:
                        intervals[src] = LiveInterval(src, 0, idx)
                    else:
                        intervals[src].end = max(intervals[src].end, idx)

        return intervals

    def _expire_old_intervals(self, current_start: int):
        """Removes intervals from active list that end before current_start, reclaiming their registers."""
        new_active = []
        for interval in self.active:
            if interval.end < current_start:
                # Register is free!
                if interval.assigned_reg:
                    self.free_regs.append(interval.assigned_reg)
            else:
                new_active.append(interval)
        self.active = new_active

    def _insert_active(self, interval: LiveInterval):
        self.active.append(interval)
        self.active.sort(key=lambda i: i.end)

    def _spill_at_interval(self, current: LiveInterval, spill_offset: int) -> bool:
        """Handles register spilling when all physical registers are active."""
        if not self.active:
            # Spill current interval
            current.spill_offset = spill_offset
            self.spill_offsets[current.reg] = spill_offset
            return True

        last_active = self.active[-1]
        if last_active.end > current.end:
            # Spill last active interval and steal its physical register
            current.assigned_reg = last_active.assigned_reg
            self.allocation[current.reg] = current.assigned_reg

            last_active.assigned_reg = None
            last_active.spill_offset = spill_offset
            self.spill_offsets[last_active.reg] = spill_offset
            if last_active.reg in self.allocation:
                del self.allocation[last_active.reg]

            self.active.pop()
            self._insert_active(current)
            return True
        else:
            # Spill current interval
            current.spill_offset = spill_offset
            self.spill_offsets[current.reg] = spill_offset
            return True
