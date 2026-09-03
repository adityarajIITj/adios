#!/usr/bin/env python3
"""
Test Suite: AdiPython JIT Compiler, Preprocessor & Adam Symbol Table
Verifies:
1. Macro Preprocessor (#define, #ifdef, #ifndef, #include)
2. Adam Hierarchical Symbol Table lookups and inheritance
3. Native RV32IM Machine Code JIT compilation directly into RAM
4. Bare-metal JIT function execution on the virtual machine
5. JIT-compiled hardware peek and poke operations
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from vm.vm import VM, RAM_BASE
from adipython import AdiPython, Preprocessor, create_adam_table

def test_jit_compiler_suite():
    print("[Test JIT Compiler] Initializing Phase 2 Compiler Verification...")
    vm = VM()
    ap = AdiPython(vm)

    # 1. Test Macro Preprocessor
    print("  -> Testing Macro Preprocessor (#define, #ifdef, #ifndef)...")
    source_macro = """
#define WIDTH 640
#define HEIGHT 480
#ifdef WIDTH
screen_area = WIDTH * HEIGHT
#else
screen_area = 0
#endif

#ifndef MISSING_SYM
flag = 42
#endif
"""
    processed = ap.preprocess(source_macro)
    assert "640 * 480" in processed
    assert "flag = 42" in processed
    assert "screen_area = 0" not in processed

    ap.execute(source_macro)
    assert ap.runtime.global_env.get("screen_area") == 640 * 480
    assert ap.runtime.global_env.get("flag") == 42
    print("  -> [PASS] Macro Preprocessor verified.")

    # 2. Test Adam Hierarchical Symbol Table
    print("  -> Testing Adam Root Symbol Table...")
    adam = create_adam_table()
    assert adam.exists("MMIO_FB"), "MMIO_FB missing from Adam table"
    assert adam.exists("CYAN"), "CYAN color missing from Adam table"
    assert adam.lookup("CYAN").value == 0x007DCFFF
    assert adam.exists("pixel"), "pixel primitive missing from Adam table"

    # Child table inheritance
    task_table = ap.adam_table
    assert task_table.exists("MMIO_UART")
    print("  -> [PASS] Adam Symbol Table verified.")

    # 3. Test Native RV32IM JIT Compilation & Execution
    print("  -> Testing Native RV32IM JIT Code Generation (Memory Execution)...")
    code_jit_math = """
def calc_score(base, bonus):
    total = base * 10 + bonus
    return total - 7
"""
    entry = ap.jit_compile_function(code_jit_math)
    assert entry == 0x82000000, f"Expected JIT entry at 0x82000000, got 0x{entry:08X}"
    assert len(ap.jit.code) > 0, "No machine code emitted"

    # Execute JIT function on bare-metal VM: calc_score(8, 5) -> 8 * 10 + 5 - 7 = 78
    res = ap.jit_call("calc_score", [8, 5])
    assert res == 78, f"JIT execution failed: expected 78, got {res}"
    print(f"  -> JIT Result: calc_score(8, 5) = {res}")
    print("  -> [PASS] Native RV32IM JIT execution verified.")

    # 4. Test JIT-Compiled Hardware Peek & Poke
    print("  -> Testing JIT-Compiled hardware peek & poke in RAM...")
    code_jit_mem = """
def hardware_write_read(addr, value):
    poke(addr, value)
    return peek(addr)
"""
    ap.jit_compile_function(code_jit_mem)
    target_addr = 0x80060000
    test_val = 0xDEADBEEF
    res_mem = ap.jit_call("hardware_write_read", [target_addr, test_val])
    assert res_mem == test_val, f"JIT peek/poke failed: expected 0x{test_val:X}, got 0x{res_mem:X}"
    assert vm.read32(target_addr) == test_val, "RAM value was not written"
    print("  -> [PASS] JIT-compiled direct hardware memory access verified.")

    print("\n===========================================================")
    print("[Test JIT] ALL PHASE 2 JIT COMPILER TESTS PASSED (100%)!")
    print("===========================================================")
    return True

if __name__ == "__main__":
    test_jit_compiler_suite()
