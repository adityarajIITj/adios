#!/usr/bin/env python3
"""
AdiOS Compiler Multi-Pass Optimization Pipeline
Performs:
1. Constant Folding & Propagation
2. Algebraic Simplification & Strength Reduction (mul/div to shifts)
3. Dead Code Elimination (DCE)
4. Peephole Optimizations
"""

import math
from typing import List, Dict, Set, Optional
from .ir import (
    IRModule, IRFunction, IRBasicBlock, IRInstruction, IROperand,
    IR_MOVE, IR_ADD, IR_SUB, IR_MUL, IR_DIV, IR_REM,
    IR_AND, IR_OR, IR_XOR, IR_SHL, IR_SHR,
    IR_EQ, IR_NE, IR_LT, IR_LE, IR_GT, IR_GE,
    IR_JUMP, IR_JUMP_IF, IR_JUMP_IF_NOT, IR_RETURN, IR_POKE, IR_CALL
)

class Optimizer:
    def __init__(self):
        self.stats = {
            "constants_folded": 0,
            "strengths_reduced": 0,
            "dead_instructions_eliminated": 0,
            "moves_coalesced": 0
        }

    def optimize_module(self, module: IRModule) -> IRModule:
        for func in module.functions.values():
            self.optimize_function(func)
        return module

    def optimize_function(self, func: IRFunction):
        # Run optimization passes until fixed point (up to 4 iterations)
        for iteration in range(4):
            changed = False
            changed |= self.pass_constant_folding(func)
            changed |= self.pass_algebraic_simplification(func)
            changed |= self.pass_dead_code_elimination(func)
            changed |= self.pass_peephole(func)
            if not changed:
                break

    # --------------------------------------------------------------------------
    # Pass 1: Constant Folding & Propagation
    # --------------------------------------------------------------------------
    def pass_constant_folding(self, func: IRFunction) -> bool:
        changed = False
        const_table: Dict[IROperand, int] = {}

        for bb in func.blocks:
            new_instructions = []
            for inst in bb.instructions:
                # Substitute known constant registers
                if inst.src1 and inst.src1.is_reg() and inst.src1 in const_table:
                    inst.src1 = IROperand.const(const_table[inst.src1])
                    changed = True
                if inst.src2 and inst.src2.is_reg() and inst.src2 in const_table:
                    inst.src2 = IROperand.const(const_table[inst.src2])
                    changed = True

                # Fold operations with two constant operands
                if inst.src1 and inst.src1.is_const() and inst.src2 and inst.src2.is_const():
                    c1 = inst.src1.value
                    c2 = inst.src2.value
                    folded_val = self._compute_const_op(inst.op, c1, c2)
                    if folded_val is not None:
                        # Convert to MOVE dest, const
                        inst.op = IR_MOVE
                        inst.src1 = IROperand.const(folded_val)
                        inst.src2 = None
                        if inst.dest:
                            const_table[inst.dest] = folded_val
                        self.stats["constants_folded"] += 1
                        changed = True

                elif inst.op == IR_MOVE and inst.src1 and inst.src1.is_const() and inst.dest:
                    const_table[inst.dest] = inst.src1.value

                new_instructions.append(inst)
            bb.instructions = new_instructions

        return changed

    def _compute_const_op(self, op: str, c1: int, c2: int) -> Optional[int]:
        if op == IR_ADD: return c1 + c2
        elif op == IR_SUB: return c1 - c2
        elif op == IR_MUL: return c1 * c2
        elif op == IR_DIV: return c1 // c2 if c2 != 0 else 0
        elif op == IR_REM: return c1 % c2 if c2 != 0 else 0
        elif op == IR_AND: return c1 & c2
        elif op == IR_OR:  return c1 | c2
        elif op == IR_XOR: return c1 ^ c2
        elif op == IR_SHL: return c1 << c2
        elif op == IR_SHR: return c1 >> c2
        elif op == IR_EQ:  return 1 if c1 == c2 else 0
        elif op == IR_NE:  return 1 if c1 != c2 else 0
        elif op == IR_LT:  return 1 if c1 < c2 else 0
        elif op == IR_LE:  return 1 if c1 <= c2 else 0
        elif op == IR_GT:  return 1 if c1 > c2 else 0
        elif op == IR_GE:  return 1 if c1 >= c2 else 0
        return None

    # --------------------------------------------------------------------------
    # Pass 2: Algebraic Simplification & Strength Reduction
    # --------------------------------------------------------------------------
    def pass_algebraic_simplification(self, func: IRFunction) -> bool:
        changed = False

        for bb in func.blocks:
            for inst in bb.instructions:
                # x + 0 -> x, x - 0 -> x
                if inst.op in (IR_ADD, IR_SUB) and inst.src2 and inst.src2.is_const() and inst.src2.value == 0:
                    inst.op = IR_MOVE
                    inst.src2 = None
                    changed = True
                    self.stats["strengths_reduced"] += 1

                # 0 + x -> x
                elif inst.op == IR_ADD and inst.src1 and inst.src1.is_const() and inst.src1.value == 0:
                    inst.op = IR_MOVE
                    inst.src1 = inst.src2
                    inst.src2 = None
                    changed = True
                    self.stats["strengths_reduced"] += 1

                # x * 1 -> x, x / 1 -> x
                elif inst.op in (IR_MUL, IR_DIV) and inst.src2 and inst.src2.is_const() and inst.src2.value == 1:
                    inst.op = IR_MOVE
                    inst.src2 = None
                    changed = True
                    self.stats["strengths_reduced"] += 1

                # x * 0 -> 0
                elif inst.op == IR_MUL and ((inst.src1 and inst.src1.is_const() and inst.src1.value == 0) or
                                             (inst.src2 and inst.src2.is_const() and inst.src2.value == 0)):
                    inst.op = IR_MOVE
                    inst.src1 = IROperand.const(0)
                    inst.src2 = None
                    changed = True
                    self.stats["strengths_reduced"] += 1

                # Strength Reduction: x * (2^k) -> x << k
                elif inst.op == IR_MUL and inst.src2 and inst.src2.is_const() and inst.src2.value > 0:
                    val = inst.src2.value
                    if (val & (val - 1)) == 0: # Power of 2!
                        k = int(math.log2(val))
                        inst.op = IR_SHL
                        inst.src2 = IROperand.const(k)
                        changed = True
                        self.stats["strengths_reduced"] += 1

                # Strength Reduction: x / (2^k) -> x >> k
                elif inst.op == IR_DIV and inst.src2 and inst.src2.is_const() and inst.src2.value > 0:
                    val = inst.src2.value
                    if (val & (val - 1)) == 0:
                        k = int(math.log2(val))
                        inst.op = IR_SHR
                        inst.src2 = IROperand.const(k)
                        changed = True
                        self.stats["strengths_reduced"] += 1

        return changed

    # --------------------------------------------------------------------------
    # Pass 3: Dead Code Elimination (DCE)
    # --------------------------------------------------------------------------
    def pass_dead_code_elimination(self, func: IRFunction) -> bool:
        changed = False

        # 1. Collect all used virtual registers
        used_regs: Set[IROperand] = set()
        for bb in func.blocks:
            for inst in bb.instructions:
                if inst.src1 and inst.src1.is_reg():
                    used_regs.add(inst.src1)
                if inst.src2 and inst.src2.is_reg():
                    used_regs.add(inst.src2)

        # 2. Filter out dead definitions (excluding side-effecting operations like CALL, POKE, RETURN)
        side_effects = {IR_CALL, IR_POKE, IR_RETURN, IR_JUMP, IR_JUMP_IF, IR_JUMP_IF_NOT}

        for bb in func.blocks:
            new_instructions = []
            for inst in bb.instructions:
                if inst.op not in side_effects and inst.dest and inst.dest.is_reg() and inst.dest not in used_regs:
                    # Dead register definition!
                    self.stats["dead_instructions_eliminated"] += 1
                    changed = True
                    continue
                new_instructions.append(inst)
            bb.instructions = new_instructions

        return changed

    # --------------------------------------------------------------------------
    # Pass 4: Peephole Optimizer
    # --------------------------------------------------------------------------
    def pass_peephole(self, func: IRFunction) -> bool:
        changed = False

        for bb in func.blocks:
            new_insts = []
            for inst in bb.instructions:
                # Remove self-moves: v1 = v1
                if inst.op == IR_MOVE and inst.dest == inst.src1:
                    self.stats["moves_coalesced"] += 1
                    changed = True
                    continue
                new_insts.append(inst)
            bb.instructions = new_insts

        return changed
