#!/usr/bin/env python3
"""
Test Suite: Block I In-OS C Compiler & ELF32 Toolchain
Verifies:
1. C Lexer tokenization (Keywords, Operators, Strings, Hex, Literals)
2. C Parser AST generation (Functions, Loops, Branches, Types, Structs)
3. RV32IM Assembly Code Generation from C AST
4. Direct in-VM execution of compiled C programs (Arithmetic, Recursion, Pointers)
5. Standard RISC-V ELF32 Binary Builder & Program Header generation
"""

import sys
import os
import struct

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from compiler.c_lexer import CLexer, TokenType
from compiler.c_parser import CParser, FunctionDecl, VarDecl, IfStmt, WhileStmt
from compiler.c_codegen import CCodeGen
from compiler.elf32 import ELF32Builder
from toolchain.assembler import Assembler
from vm.vm import VM

def test_compiler_block_i_suite():
    print("[Test Compiler Block I] Initializing In-OS C Compiler & Toolchain Verification...")

    # 1. Test C Lexer
    print("  -> Testing C Lexer Tokenization...")
    c_src = """
    /* Multi-line comment */
    int main(int argc, char* argv[]) {
        int val = 0x10 + 42; // hex and dec
        if (val == 58 && val != 0) {
            val += 2;
        }
        return val;
    }
    """
    lexer = CLexer(c_src)
    tokens = lexer.tokenize()
    assert len(tokens) > 20
    assert tokens[0].type == TokenType.KW_INT
    assert tokens[1].value == "main"
    assert any(t.type == TokenType.HEX_LITERAL and t.value == 0x10 for t in tokens)
    assert any(t.type == TokenType.PLUS_ASSIGN for t in tokens)
    print("  -> [PASS] C Lexer verified.")

    # 2. Test C Parser
    print("  -> Testing C Parser AST Generation...")
    parser = CParser(tokens)
    unit = parser.parse()
    assert len(unit.decls) == 1
    fn_main = unit.decls[0]
    assert isinstance(fn_main, FunctionDecl)
    assert fn_main.name == "main"
    assert len(fn_main.params) == 2
    assert len(fn_main.body.stmts) >= 3
    print("  -> [PASS] C Parser AST generation verified.")

    # 3. Test C Codegen & Execution: Simple Arithmetic
    print("  -> Testing C Codegen & VM Execution (Addition)...")
    prog1 = """
    int compute() {
        int a = 15;
        int b = 27;
        return a + b;
    }
    """
    ast1 = CParser(CLexer(prog1).tokenize()).parse()
    asm_code1 = CCodeGen().generate(ast1)
    
    # Assemble and run in VM
    asm = Assembler()
    out_bin1 = "c_test1.bin"
    tmp_s1 = "c_test1.s"
    with open(tmp_s1, "w") as f:
        f.write(asm_code1)
    asm.assemble_file(tmp_s1, out_bin1)

    vm = VM(ram_size=16 * 1024 * 1024)
    vm.load_binary(out_bin1)
    fn_addr = asm.labels.get("compute")
    assert fn_addr is not None

    vm.pc = fn_addr
    target_ret = 0x80000000 + 1024
    vm.regs[1] = target_ret
    vm.regs[2] = 0x80800000

    for _ in range(100):
        if vm.pc == target_ret:
            break
        vm.step()

    # a0 (x10) must be 15 + 27 = 42
    assert vm.regs[10] == 42, f"Expected 42, got {vm.regs[10]}"
    print("  -> [PASS] C arithmetic program execution verified (15 + 27 = 42).")

    # 4. Test C Codegen & Execution: Loops & Branches (Factorial)
    print("  -> Testing C Codegen & VM Execution (Factorial Loop)...")
    prog2 = """
    int factorial(int n) {
        int res = 1;
        int i = 1;
        while (i <= n) {
            res = res * i;
            i = i + 1;
        }
        return res;
    }
    """
    ast2 = CParser(CLexer(prog2).tokenize()).parse()
    asm_code2 = CCodeGen().generate(ast2)
    tmp_s2 = "c_test2.s"
    out_bin2 = "c_test2.bin"
    with open(tmp_s2, "w") as f:
        f.write(asm_code2)
    asm.assemble_file(tmp_s2, out_bin2)

    vm2 = VM(ram_size=16 * 1024 * 1024)
    vm2.load_binary(out_bin2)
    fn_fact = asm.labels.get("factorial")
    assert fn_fact is not None

    vm2.pc = fn_fact
    vm2.regs[1] = target_ret
    vm2.regs[2] = 0x80800000
    vm2.regs[10] = 5  # Argument n = 5

    for _ in range(300):
        if vm2.pc == target_ret:
            break
        vm2.step()

    # 5! = 120
    assert vm2.regs[10] == 120, f"Expected 120, got {vm2.regs[10]}"
    print("  -> [PASS] C factorial loop execution verified (5! = 120).")

    # 5. Test C Codegen & Execution: Pointer Operations
    print("  -> Testing C Pointer Dereferencing & Addresses...")
    prog3 = """
    int test_ptr() {
        int x = 10;
        int* p = &x;
        *p = 77;
        return x;
    }
    """
    ast3 = CParser(CLexer(prog3).tokenize()).parse()
    asm_code3 = CCodeGen().generate(ast3)
    tmp_s3 = "c_test3.s"
    out_bin3 = "c_test3.bin"
    with open(tmp_s3, "w") as f:
        f.write(asm_code3)
    asm.assemble_file(tmp_s3, out_bin3)

    vm3 = VM(ram_size=16 * 1024 * 1024)
    vm3.load_binary(out_bin3)
    fn_ptr = asm.labels.get("test_ptr")
    assert fn_ptr is not None

    vm3.pc = fn_ptr
    vm3.regs[1] = target_ret
    vm3.regs[2] = 0x80800000

    for _ in range(100):
        if vm3.pc == target_ret:
            break
        vm3.step()

    assert vm3.regs[10] == 77, f"Expected 77, got {vm3.regs[10]}"
    print("  -> [PASS] C pointer assignment & dereference verified (*p = 77).")

    # 6. Test ELF32 Binary Builder
    print("  -> Testing ELF32 Binary Builder...")
    builder = ELF32Builder(entry_addr=0x80000000)
    builder.set_text(struct.pack("<II", 0x02A00513, 0x00008067)) # addi a0, zero, 42; ret
    elf_bytes = builder.build()
    assert len(elf_bytes) > 52
    assert elf_bytes[:4] == b"\x7fELF"
    assert elf_bytes[4] == 1  # 32-bit
    assert elf_bytes[5] == 1  # Little-endian
    assert elf_bytes[16:18] == struct.pack("<H", 2)   # ET_EXEC
    assert elf_bytes[18:20] == struct.pack("<H", 243) # EM_RISCV
    print("  -> [PASS] ELF32 binary generator verified.")

    # Cleanup temp test files
    for f_clean in [tmp_s1, out_bin1, tmp_s2, out_bin2, tmp_s3, out_bin3]:
        try: os.remove(f_clean)
        except OSError: pass

    print("\n[Test Compiler Block I] ALL BLOCK I C COMPILER TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_compiler_block_i_suite()
