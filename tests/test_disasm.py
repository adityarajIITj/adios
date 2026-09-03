#!/usr/bin/env python3
"""
Test Suite: In-Memory RISC-V Disassembler
Verifies correct disassembly of RV32I and RV32M instructions.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from toolchain.disasm import Disassembler

def test_disasm_suite():
    print("[Test Disasm] Testing RV32IM In-Memory Disassembler...")
    dis = Disassembler()

    # 1. Test ADDI / LI
    # addi a0, zero, 42 -> 0x02A00513
    d1 = dis.disassemble_instruction(0x02A00513, 0x80000000)
    assert "42" in d1 and "a0" in d1, f"Failed: {d1}"
    print(f"  -> 0x02A00513: {d1}")

    # 2. Test RV32M MUL
    # mul a0, a1, a2 -> opcode 0x33, f3=0, f7=1, rd=10, rs1=11, rs2=12
    # (0x01 << 25) | (12 << 20) | (11 << 15) | (0 << 12) | (10 << 7) | 0x33 = 0x02C58533
    d2 = dis.disassemble_instruction(0x02C58533, 0x80000004)
    assert "mul" in d2 and "a0, a1, a2" in d2, f"Failed: {d2}"
    print(f"  -> 0x02C58533: {d2}")

    # 3. Test RET
    # jalr x0, ra, 0 -> 0x00008067
    d3 = dis.disassemble_instruction(0x00008067, 0x80000008)
    assert d3 == "ret", f"Failed: {d3}"
    print(f"  -> 0x00008067: {d3}")

    print("\n[Test Disasm] ALL DISASSEMBLER TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_disasm_suite()
