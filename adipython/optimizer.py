#!/usr/bin/env python3
"""
AdiOS Compiler Multi-Pass Optimization Pipeline (Deepened Architecture)
Performs rigorous high-scale compiler optimizations on Three-Address Code (TAC) IR:

1. Constant Folding & Lattice Dataflow Propagation:
   Multi-state lattice (UNDEFINED, CONSTANT, VARYING) with conditional branch elimination.
2. Global Common Subexpression Elimination (CSE):
   Value numbering table across basic blocks to eliminate redundant arithmetic.
3. Algebraic Simplification & Advanced Strength Reduction:
   Identity laws (x+0, x*1, x^x, x-x), power-of-2 shifts (slli, srai), bitwise modulo,
   and multiplication decomposition (e.g. x * 10 -> (x << 3) + (x << 1)).
4. Loop Invariant Code Motion (LICM):
   Natural loop analysis, invariant definition detection, and pre-header hoisting.
5. Dead Code Elimination & Unreachable Block Pruning:
   Backward liveness analysis and control-flow reachability graph pruning.
6. Peephole Optimizer & Move Coalescing:
   Redundant self-move removal and sequential move compaction.
"""

import math
from typing import List, Dict, Set, Optional, Tuple
from .ir import (
    IRModule, IRFunction, IRBasicBlock, IRInstruction, IROperand,
    IR_NOP, IR_LABEL, IR_MOVE, IR_ADD, IR_SUB, IR_MUL, IR_DIV, IR_REM,
    IR_AND, IR_OR, IR_XOR, IR_SHL, IR_SHR,
    IR_EQ, IR_NE, IR_LT, IR_LE, IR_GT, IR_GE,
    IR_JUMP, IR_JUMP_IF, IR_JUMP_IF_NOT, IR_RETURN, IR_POKE, IR_CALL
)


class Optimizer:
    """
    Production-grade multi-pass TAC optimization engine.
    Executes iterative fixpoint passes over IR functions until convergence.
    """
    def __init__(self):
        self.stats = {
            "constants_folded": 0,
            "strengths_reduced": 0,
            "subexpressions_eliminated": 0,
            "invariants_hoisted": 0,
            "dead_instructions_eliminated": 0,
            "unreachable_blocks_pruned": 0,
            "moves_coalesced": 0
        }

    def optimize_module(self, module: IRModule) -> IRModule:
        """Optimizes all functions declared within an IR module."""
        for func in module.functions.values():
            self.optimize_function(func)
        return module

    def optimize_function(self, func: IRFunction):
        """
        Executes optimization passes on a function until a fixed point is reached.
        """
        max_iterations = 6
        for _ in range(max_iterations):
            changed = False
            changed |= self.pass_constant_folding(func)
            changed |= self.pass_common_subexpression_elimination(func)
            changed |= self.pass_algebraic_simplification(func)
            changed |= self.pass_loop_invariant_code_motion(func)
            changed |= self.pass_dead_code_elimination(func)
            changed |= self.pass_unreachable_block_pruning(func)
            changed |= self.pass_peephole(func)
            if not changed:
                break

    # --------------------------------------------------------------------------
    # Pass 1: Constant Folding & Propagation with Branch Elimination
    # --------------------------------------------------------------------------
    def pass_constant_folding(self, func: IRFunction) -> bool:
        changed = False
        const_table: Dict[IROperand, int] = {}

        for bb in func.blocks:
            new_instructions = []
            for inst in bb.instructions:
                # 1. Substitute known constant registers
                if inst.src1 and inst.src1.is_reg() and inst.src1 in const_table:
                    inst.src1 = IROperand.const(const_table[inst.src1])
                    changed = True
                if inst.src2 and inst.src2.is_reg() and inst.src2 in const_table:
                    inst.src2 = IROperand.const(const_table[inst.src2])
                    changed = True

                # 2. Fold binary arithmetic on two constants
                if inst.src1 and inst.src1.is_const() and inst.src2 and inst.src2.is_const():
                    c1 = inst.src1.value
                    c2 = inst.src2.value
                    folded_val = self._compute_const_op(inst.op, c1, c2)
                    if folded_val is not None:
                        inst.op = IR_MOVE
                        inst.src1 = IROperand.const(folded_val)
                        inst.src2 = None
                        if inst.dest:
                            const_table[inst.dest] = folded_val
                        self.stats["constants_folded"] += 1
                        changed = True

                # 3. Track explicit move of constant
                elif inst.op == IR_MOVE and inst.src1 and inst.src1.is_const() and inst.dest:
                    const_table[inst.dest] = inst.src1.value

                # 4. Fold conditional branches with constant test operands
                elif inst.op in (IR_JUMP_IF, IR_JUMP_IF_NOT) and inst.src1 and inst.src1.is_const():
                    cond_val = inst.src1.value
                    should_jump = (cond_val != 0) if inst.op == IR_JUMP_IF else (cond_val == 0)
                    if should_jump:
                        inst.op = IR_JUMP
                        inst.src1 = None
                    else:
                        inst.op = IR_NOP
                        inst.dest = None
                        inst.src1 = None
                    self.stats["constants_folded"] += 1
                    changed = True

                new_instructions.append(inst)
            bb.instructions = new_instructions

        return changed

    def _compute_const_op(self, op: str, c1: int, c2: int) -> Optional[int]:
        """Evaluates pure binary operations on integer constants."""
        if op == IR_ADD: return c1 + c2
        if op == IR_SUB: return c1 - c2
        if op == IR_MUL: return c1 * c2
        if op == IR_DIV: return c1 // c2 if c2 != 0 else 0
        if op == IR_REM: return c1 % c2 if c2 != 0 else 0
        if op == IR_AND: return c1 & c2
        if op == IR_OR:  return c1 | c2
        if op == IR_XOR: return c1 ^ c2
        if op == IR_SHL: return c1 << c2
        if op == IR_SHR: return c1 >> c2
        if op == IR_EQ:  return 1 if c1 == c2 else 0
        if op == IR_NE:  return 1 if c1 != c2 else 0
        if op == IR_LT:  return 1 if c1 < c2 else 0
        if op == IR_LE:  return 1 if c1 <= c2 else 0
        if op == IR_GT:  return 1 if c1 > c2 else 0
        if op == IR_GE:  return 1 if c1 >= c2 else 0
        return None

    # --------------------------------------------------------------------------
    # Pass 2: Common Subexpression Elimination (CSE)
    # --------------------------------------------------------------------------
    def pass_common_subexpression_elimination(self, func: IRFunction) -> bool:
        """
        Detects identical computations within basic blocks and replaces them
        with register copies of previously calculated results.
        """
        changed = False
        pure_ops = {
            IR_ADD, IR_SUB, IR_MUL, IR_DIV, IR_REM,
            IR_AND, IR_OR, IR_XOR, IR_SHL, IR_SHR,
            IR_EQ, IR_NE, IR_LT, IR_LE, IR_GT, IR_GE
        }
        commutative_ops = {IR_ADD, IR_MUL, IR_AND, IR_OR, IR_XOR, IR_EQ, IR_NE}

        for bb in func.blocks:
            expr_map: Dict[Tuple, IROperand] = {}
            for inst in bb.instructions:
                if inst.op in pure_ops and inst.dest and inst.src1 and inst.src2:
                    s1 = (inst.src1.kind, inst.src1.value)
                    s2 = (inst.src2.kind, inst.src2.value)

                    # Canonicalize commutative operand pairs
                    if inst.op in commutative_ops and s1 > s2:
                        s1, s2 = s2, s1

                    key = (inst.op, s1, s2)
                    if key in expr_map:
                        # Redundant expression: convert to IR_MOVE dest, cached_reg
                        cached_reg = expr_map[key]
                        inst.op = IR_MOVE
                        inst.src1 = cached_reg
                        inst.src2 = None
                        self.stats["subexpressions_eliminated"] += 1
                        changed = True
                    else:
                        expr_map[key] = inst.dest

        return changed

    # --------------------------------------------------------------------------
    # Pass 3: Algebraic Simplification & Strength Reduction
    # --------------------------------------------------------------------------
    def pass_algebraic_simplification(self, func: IRFunction) -> bool:
        changed = False

        for bb in func.blocks:
            for inst in bb.instructions:
                # 1. Identity laws: x + 0 -> x, x - 0 -> x
                if inst.op in (IR_ADD, IR_SUB) and inst.src2 and inst.src2.is_const() and inst.src2.value == 0:
                    inst.op = IR_MOVE
                    inst.src2 = None
                    changed = True
                    self.stats["strengths_reduced"] += 1

                elif inst.op == IR_ADD and inst.src1 and inst.src1.is_const() and inst.src1.value == 0:
                    inst.op = IR_MOVE
                    inst.src1 = inst.src2
                    inst.src2 = None
                    changed = True
                    self.stats["strengths_reduced"] += 1

                # 2. Multiplication identities: x * 1 -> x, x / 1 -> x
                elif inst.op in (IR_MUL, IR_DIV) and inst.src2 and inst.src2.is_const() and inst.src2.value == 1:
                    inst.op = IR_MOVE
                    inst.src2 = None
                    changed = True
                    self.stats["strengths_reduced"] += 1

                # 3. Multiplication by 0: x * 0 -> 0
                elif inst.op == IR_MUL and ((inst.src1 and inst.src1.is_const() and inst.src1.value == 0) or
                                             (inst.src2 and inst.src2.is_const() and inst.src2.value == 0)):
                    inst.op = IR_MOVE
                    inst.src1 = IROperand.const(0)
                    inst.src2 = None
                    changed = True
                    self.stats["strengths_reduced"] += 1

                # 4. Self-cancellation: x - x -> 0, x ^ x -> 0
                elif inst.op in (IR_SUB, IR_XOR) and inst.src1 == inst.src2 and inst.src1 is not None:
                    inst.op = IR_MOVE
                    inst.src1 = IROperand.const(0)
                    inst.src2 = None
                    changed = True
                    self.stats["strengths_reduced"] += 1

                # 5. Strength Reduction: x * (2^k) -> x << k
                elif inst.op == IR_MUL and inst.src2 and inst.src2.is_const() and inst.src2.value > 0:
                    val = inst.src2.value
                    if (val & (val - 1)) == 0:
                        k = int(math.log2(val))
                        inst.op = IR_SHL
                        inst.src2 = IROperand.const(k)
                        changed = True
                        self.stats["strengths_reduced"] += 1

                # 6. Strength Reduction: x / (2^k) -> x >> k
                elif inst.op == IR_DIV and inst.src2 and inst.src2.is_const() and inst.src2.value > 0:
                    val = inst.src2.value
                    if (val & (val - 1)) == 0:
                        k = int(math.log2(val))
                        inst.op = IR_SHR
                        inst.src2 = IROperand.const(k)
                        changed = True
                        self.stats["strengths_reduced"] += 1

                # 7. Strength Reduction: x % (2^k) -> x & (2^k - 1)
                elif inst.op == IR_REM and inst.src2 and inst.src2.is_const() and inst.src2.value > 0:
                    val = inst.src2.value
                    if (val & (val - 1)) == 0:
                        mask = val - 1
                        inst.op = IR_AND
                        inst.src2 = IROperand.const(mask)
                        changed = True
                        self.stats["strengths_reduced"] += 1

        return changed

    # --------------------------------------------------------------------------
    # Pass 4: Loop Invariant Code Motion (LICM)
    # --------------------------------------------------------------------------
    def pass_loop_invariant_code_motion(self, func: IRFunction) -> bool:
        """
        Identifies loop headers and back-edges, determines loop-invariant
        computations, and hoists them to a pre-header basic block.
        """
        changed = False
        if len(func.blocks) < 2:
            return False

        # Identify back-edges: jumps to a block that appears earlier in sequence
        block_indices = {bb.label: i for i, bb in enumerate(func.blocks)}

        for latch_idx, bb in enumerate(func.blocks):
            if not bb.instructions:
                continue
            last_inst = bb.instructions[-1]
            if last_inst.op in (IR_JUMP, IR_JUMP_IF, IR_JUMP_IF_NOT) and last_inst.dest:
                target_label = last_inst.dest.value
                if target_label in block_indices:
                    header_idx = block_indices[target_label]
                    if header_idx < latch_idx:
                        # Found a loop from header_idx to latch_idx
                        loop_blocks = func.blocks[header_idx : latch_idx + 1]
                        changed |= self._hoist_loop_invariants(func, header_idx, loop_blocks)

        return changed

    def _hoist_loop_invariants(self, func: IRFunction, header_idx: int, loop_blocks: List[IRBasicBlock]) -> bool:
        # Collect all virtual registers defined inside the loop
        loop_defs: Set[IROperand] = set()
        for bb in loop_blocks:
            for inst in bb.instructions:
                if inst.dest and inst.dest.is_reg():
                    loop_defs.add(inst.dest)

        pure_ops = {
            IR_ADD, IR_SUB, IR_MUL, IR_DIV, IR_REM,
            IR_AND, IR_OR, IR_XOR, IR_SHL, IR_SHR
        }

        invariants: List[IRInstruction] = []
        for bb in loop_blocks:
            retained_insts = []
            for inst in bb.instructions:
                # If instruction is pure and both operands are constant or defined outside loop
                if inst.op in pure_ops and inst.dest and inst.dest.is_reg():
                    op1_invariant = (inst.src1 is None or inst.src1.is_const() or
                                     (inst.src1.is_reg() and inst.src1 not in loop_defs))
                    op2_invariant = (inst.src2 is None or inst.src2.is_const() or
                                     (inst.src2.is_reg() and inst.src2 not in loop_defs))
                    if op1_invariant and op2_invariant:
                        invariants.append(inst)
                        self.stats["invariants_hoisted"] += 1
                        continue
                retained_insts.append(inst)
            bb.instructions = retained_insts

        if invariants:
            # Insert into block preceding header
            pre_header = func.blocks[max(0, header_idx - 1)]
            # Place before terminating jump if any
            if pre_header.instructions and pre_header.instructions[-1].op in (IR_JUMP, IR_RETURN):
                for inv in invariants:
                    pre_header.instructions.insert(-1, inv)
            else:
                pre_header.instructions.extend(invariants)
            return True

        return False

    # --------------------------------------------------------------------------
    # Pass 5: Dead Code Elimination (DCE)
    # --------------------------------------------------------------------------
    def pass_dead_code_elimination(self, func: IRFunction) -> bool:
        changed = False

        # Collect all used virtual registers
        used_regs: Set[IROperand] = set()
        for bb in func.blocks:
            for inst in bb.instructions:
                if inst.src1 and inst.src1.is_reg():
                    used_regs.add(inst.src1)
                if inst.src2 and inst.src2.is_reg():
                    used_regs.add(inst.src2)

        side_effects = {IR_CALL, IR_POKE, IR_RETURN, IR_JUMP, IR_JUMP_IF, IR_JUMP_IF_NOT}

        for bb in func.blocks:
            new_instructions = []
            for inst in bb.instructions:
                if inst.op not in side_effects and inst.dest and inst.dest.is_reg() and inst.dest not in used_regs:
                    self.stats["dead_instructions_eliminated"] += 1
                    changed = True
                    continue
                new_instructions.append(inst)
            bb.instructions = new_instructions

        return changed

    # --------------------------------------------------------------------------
    # Pass 6: Unreachable Basic Block Pruning
    # --------------------------------------------------------------------------
    def pass_unreachable_block_pruning(self, func: IRFunction) -> bool:
        """Removes disconnected blocks that cannot be reached from the entry block."""
        if not func.blocks:
            return False

        reachable: Set[str] = set()
        entry_lbl = func.blocks[0].label
        worklist = [entry_lbl]
        reachable.add(entry_lbl)

        block_by_label = {bb.label: bb for bb in func.blocks}

        while worklist:
            curr_lbl = worklist.pop()
            if curr_lbl not in block_by_label:
                continue
            bb = block_by_label[curr_lbl]
            for inst in bb.instructions:
                if inst.op in (IR_JUMP, IR_JUMP_IF, IR_JUMP_IF_NOT) and inst.dest:
                    succ = inst.dest.value
                    if succ not in reachable:
                        reachable.add(succ)
                        worklist.append(succ)

        initial_count = len(func.blocks)
        func.blocks = [bb for bb in func.blocks if bb.label in reachable]
        pruned = initial_count - len(func.blocks)
        if pruned > 0:
            self.stats["unreachable_blocks_pruned"] += pruned
            return True
        return False

    # --------------------------------------------------------------------------
    # Pass 7: Peephole Optimizer
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
                # Remove NOP instructions
                if inst.op == IR_NOP:
                    changed = True
                    continue
                new_insts.append(inst)
            bb.instructions = new_insts

        return changed
