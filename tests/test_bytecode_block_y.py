#!/usr/bin/env python3
"""
Test Suite: Block Y Sovereign Dynamic Bytecode VM & Lisp Engine
Verifies:
1. bytecode/lisp_vm: S-Expression parser and nested form parsing
2. bytecode/lisp_vm: Arithmetic expressions & comparisons compilation
3. bytecode/lisp_vm: Conditional if-expressions with bytecode jump patching
4. bytecode/lisp_vm: Recursive function calls (factorial) & call frames
5. bytecode/lisp_vm: Multi-argument function definition & invocation
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from bytecode.lisp_vm import LispParser, BytecodeCompiler, BytecodeVM, OP_HALT

def test_bytecode_block_y_suite():
    print("[Test Bytecode Block Y] Initializing Bytecode VM & Lisp Verification...")

    # 1. Test S-Expression Parser
    print("  -> Testing Lisp S-Expression Tokenizer & Reader...")
    sexpr = LispParser.parse("(defun add2 (x y) (+ x y))")
    assert sexpr[0] == "defun"
    assert sexpr[1] == "add2"
    assert sexpr[2] == ["x", "y"]
    assert sexpr[3] == ["+", "x", "y"]
    print("  -> [PASS] S-Expression parsing verified.")

    # 2. Test Arithmetic & Logic Bytecode Execution
    print("  -> Testing Arithmetic & Logic Compilation...")
    ast = LispParser.parse("(+ 10 (* 3 (- 12 4)))") # 10 + 3 * 8 = 34
    comp = BytecodeCompiler()
    comp.compile(ast)
    comp.code.append(OP_HALT)

    vm = BytecodeVM(comp.code, comp.constants)
    res = vm.run()
    assert res == 34
    print("  -> [PASS] Arithmetic bytecode execution verified.")

    # 3. Test Conditionals (if)
    print("  -> Testing Conditional (if) Jump Patching...")
    # (if (< 5 10) 42 99)
    ast_if = LispParser.parse("(if (< 5 10) 42 99)")
    comp_if = BytecodeCompiler()
    comp_if.compile(ast_if)
    comp_if.code.append(OP_HALT)

    vm_if = BytecodeVM(comp_if.code, comp_if.constants)
    assert vm_if.run() == 42

    ast_if2 = LispParser.parse("(if (> 5 10) 42 99)")
    comp_if2 = BytecodeCompiler()
    comp_if2.compile(ast_if2)
    comp_if2.code.append(OP_HALT)

    vm_if2 = BytecodeVM(comp_if2.code, comp_if2.constants)
    assert vm_if2.run() == 99
    print("  -> [PASS] Conditional branching verified.")

    # 4. Test Multi-Argument Function Definition
    print("  -> Testing Function Compilation & Multi-Argument Calls...")
    code_fn = """
    (defun hypot2 (a b)
        (+ (* a a) (* b b)))
    """
    comp_fn = BytecodeCompiler()
    comp_fn.compile(LispParser.parse(code_fn))
    # Call (hypot2 3 4) -> 9 + 16 = 25
    comp_fn.compile(LispParser.parse("(hypot2 3 4)"))
    comp_fn.code.append(OP_HALT)

    vm_fn = BytecodeVM(comp_fn.code, comp_fn.constants)
    assert vm_fn.run() == 25
    print("  -> [PASS] Multi-argument function call verified.")

    # 5. Test Recursive Function (Factorial)
    print("  -> Testing Recursive Function Call Frames (Factorial)...")
    code_fact = """
    (defun fact (n)
        (if (< n 2)
            1
            (* n (fact (- n 1)))))
    """
    comp_rec = BytecodeCompiler()
    comp_rec.compile(LispParser.parse(code_fact))
    # Call (fact 5) -> 120
    comp_rec.compile(LispParser.parse("(fact 5)"))
    comp_rec.code.append(OP_HALT)

    vm_rec = BytecodeVM(comp_rec.code, comp_rec.constants)
    fact5 = vm_rec.run()
    assert fact5 == 120

    # Call (fact 6) -> 720
    comp_rec2 = BytecodeCompiler()
    comp_rec2.compile(LispParser.parse(code_fact))
    comp_rec2.compile(LispParser.parse("(fact 6)"))
    comp_rec2.code.append(OP_HALT)
    vm_rec2 = BytecodeVM(comp_rec2.code, comp_rec2.constants)
    assert vm_rec2.run() == 720
    print("  -> [PASS] Recursive factorial & call stack unwinding verified.")

    print("\n[Test Bytecode Block Y] ALL BLOCK Y BYTECODE VM & LISP TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_bytecode_block_y_suite()
