#!/usr/bin/env python3
"""
Test Suite: Block B High-Scale Compiler & Optimizer Pipeline
Verifies:
1. Intermediate Representation (IR / TAC) Generation from AdiPython AST
2. Control Flow Graph (CFG) basic blocks
3. Constant Folding & Constant Propagation
4. Algebraic Simplification & Strength Reduction (mul/div to shifts)
5. Dead Code Elimination (DCE)
6. Linear Scan Register Allocation & Stack Spilling
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from adipython.lexer import Lexer
from adipython.parser import Parser
from adipython.ir import IR_ADD, IR_MUL, IR_SHL, IR_SHR, IR_MOVE
from adipython.ir_gen import IRGenerator
from adipython.optimizer import Optimizer
from adipython.regalloc import LinearScanRegisterAllocator

def test_compiler_block_b_suite():
    print("[Test Compiler Block B] Initializing Compiler & Optimizer Verification...")

    # 1. Test TAC IR Generation
    print("  -> Testing IR / TAC code generation...")
    src1 = """
def compute(a, b):
    x = a * 10 + b
    if x > 50:
        return x * 2
    else:
        return x - 5
"""
    tokens = Lexer(src1).tokenize()
    ast = Parser(tokens).parse()
    gen = IRGenerator()
    mod = gen.generate(ast)

    assert "compute" in mod.functions, "Function 'compute' not in IR module"
    fn = mod.functions["compute"]
    assert len(fn.blocks) >= 3, f"Expected at least 3 basic blocks (entry, then, else), got {len(fn.blocks)}"
    print(f"  -> Generated {len(fn.blocks)} basic blocks in CFG.")
    print("  -> [PASS] IR Generation verified.")

    # 2. Test Constant Folding
    print("  -> Testing Constant Folding Pass...")
    src_const = """
def const_eval():
    val = 10 + 20 * 3
    res = (100 - 40) / 2
    return val + res
"""
    tokens = Lexer(src_const).tokenize()
    ast = Parser(tokens).parse()
    mod = IRGenerator().generate(ast)
    opt = Optimizer()
    opt.optimize_module(mod)

    fn = mod.functions["const_eval"]
    assert opt.stats["constants_folded"] > 0, "No constants were folded"
    print(f"  -> Folded {opt.stats['constants_folded']} constant expressions at compile-time.")

    # Verify that the entire function body was optimized into RETURN $100!
    entry_insts = fn.entry_block.instructions
    ret_insts = [i for i in entry_insts if i.op == "RETURN" and i.src1 and i.src1.is_const()]
    assert len(ret_insts) > 0, "No RETURN constant instruction found"
    assert ret_insts[0].src1.value == 100, f"Expected RETURN $100, got {ret_insts[0].src1.value}"
    print(f"  -> Function collapsed to single instruction: RETURN ${ret_insts[0].src1.value}")
    print("  -> [PASS] Constant Folding verified.")

    # 3. Test Algebraic Simplification & Strength Reduction
    print("  -> Testing Algebraic Simplification & Strength Reduction...")
    src_algebra = """
def fast_math(x):
    y = x * 8
    z = x / 4
    w = x + 0
    return y + z + w
"""
    tokens = Lexer(src_algebra).tokenize()
    ast = Parser(tokens).parse()
    mod = IRGenerator().generate(ast)
    opt = Optimizer()
    opt.optimize_module(mod)

    fn = mod.functions["fast_math"]
    insts = fn.entry_block.instructions
    # Check x * 8 was strength-reduced to SHL by 3
    shl_insts = [i for i in insts if i.op == IR_SHL and i.src2 and i.src2.is_const() and i.src2.value == 3]
    assert len(shl_insts) > 0, "Multiplication by 8 was not reduced to SHL 3"

    # Check x / 4 was strength-reduced to SHR by 2
    shr_insts = [i for i in insts if i.op == IR_SHR and i.src2 and i.src2.is_const() and i.src2.value == 2]
    assert len(shr_insts) > 0, "Division by 4 was not reduced to SHR 2"
    print(f"  -> Strength-reduced multiplications and divisions to shifts ({opt.stats['strengths_reduced']} reductions).")
    print("  -> [PASS] Algebraic Simplification verified.")

    # 4. Test Dead Code Elimination (DCE)
    print("  -> Testing Dead Code Elimination (DCE)...")
    src_dce = """
def unused_vars(a):
    dead1 = a * 999
    dead2 = dead1 + 42
    live = a + 5
    return live
"""
    tokens = Lexer(src_dce).tokenize()
    ast = Parser(tokens).parse()
    mod = IRGenerator().generate(ast)
    opt = Optimizer()
    opt.optimize_module(mod)

    fn = mod.functions["unused_vars"]
    assert opt.stats["dead_instructions_eliminated"] >= 2, f"Expected >= 2 dead instructions removed, got {opt.stats['dead_instructions_eliminated']}"
    print(f"  -> Eliminated {opt.stats['dead_instructions_eliminated']} dead/unused instructions.")
    print("  -> [PASS] Dead Code Elimination verified.")

    # 5. Test Linear Scan Register Allocation
    print("  -> Testing Linear Scan Register Allocation...")
    src_reg = """
def complex_calc(a, b, c, d):
    r1 = a + b
    r2 = c + d
    r3 = r1 * r2
    r4 = r3 + a
    return r4
"""
    tokens = Lexer(src_reg).tokenize()
    ast = Parser(tokens).parse()
    mod = IRGenerator().generate(ast)
    fn = mod.functions["complex_calc"]

    # Test with abundant registers (no spilling)
    regalloc = LinearScanRegisterAllocator()
    alloc_map, spill_map, frame_size = regalloc.allocate(fn)
    assert len(alloc_map) > 0, "No registers allocated"
    assert len(spill_map) == 0, f"Unexpected spill with abundant registers: {spill_map}"
    print(f"  -> Allocated {len(alloc_map)} virtual registers to hardware physical registers.")

    # Test with constrained register pool (forcing spilling)
    constrained_alloc = LinearScanRegisterAllocator(physical_regs=["t0", "t1"])
    alloc_c, spill_c, frame_c = constrained_alloc.allocate(fn)
    assert len(spill_c) > 0, "Constrained allocator failed to spill"
    assert frame_c >= 16, "Stack frame not allocated for spilled registers"
    print(f"  -> Constrained pressure: {len(alloc_c)} mapped, {len(spill_c)} spilled to stack frame ({frame_c} bytes).")
    print("  -> [PASS] Register Allocation & Spilling verified.")

    print("\n[Test Compiler Block B] ALL BLOCK B COMPILER & OPTIMIZER TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_compiler_block_b_suite()
