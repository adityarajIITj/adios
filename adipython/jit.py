#!/usr/bin/env python3
"""
AdiPython Native RV32IM JIT Code Generator
Directly compiles AdiPython AST into 32-bit RISC-V machine code in RAM and executes on the VM.
"""

import struct
from .parser import (
    Program, Assign, AugAssign, FunctionDef, Return, If, While, For,
    ExprStmt, Call, BinaryOp, UnaryOp, Number, String, Identifier
)

JIT_RAM_BASE = 0x82000000 # JIT Executable Code Area in RAM

# RISC-V Register Indices
REG_ZERO = 0
REG_RA   = 1
REG_SP   = 2
REG_FP   = 8  # s0 / fp
REG_A0   = 10 # Function arg 0 / return value
REG_A1   = 11
REG_A2   = 12
REG_A3   = 13
REG_T0   = 5
REG_T1   = 6
REG_T2   = 7
REG_T3   = 28

def encode_r(opcode, funct3, funct7, rd, rs1, rs2):
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode

def encode_i(opcode, funct3, rd, rs1, imm):
    imm12 = imm & 0xFFF
    return (imm12 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode

def encode_s(opcode, funct3, rs1, rs2, imm):
    imm12 = imm & 0xFFF
    imm_hi = (imm12 >> 5) & 0x7F
    imm_lo = imm12 & 0x1F
    return (imm_hi << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (imm_lo << 7) | opcode

def encode_b(opcode, funct3, rs1, rs2, imm):
    imm13 = imm & 0x1FFF
    b12 = (imm13 >> 12) & 1
    b11 = (imm13 >> 11) & 1
    b10_5 = (imm13 >> 5) & 0x3F
    b4_1 = (imm13 >> 1) & 0xF
    return (b12 << 31) | (b10_5 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (b4_1 << 8) | (b11 << 7) | opcode

def encode_u(opcode, rd, imm):
    imm20 = (imm >> 12) & 0xFFFFF
    return (imm20 << 12) | (rd << 7) | opcode

def encode_j(opcode, rd, imm):
    imm21 = imm & 0x1FFFFF
    j20 = (imm21 >> 20) & 1
    j19_12 = (imm21 >> 12) & 0xFF
    j11 = (imm21 >> 11) & 1
    j10_1 = (imm21 >> 1) & 0x3FF
    return (j20 << 31) | (j10_1 << 21) | (j11 << 20) | (j19_12 << 12) | (rd << 7) | opcode

class JITCompiler:
    def __init__(self, vm=None, jit_base=JIT_RAM_BASE):
        self.vm = vm
        self.jit_base = jit_base
        self.current_addr = jit_base
        self.code = bytearray()
        self.local_vars = {} # name -> fp_offset (negative)
        self.local_offset = 0
        self.functions = {}  # name -> entry_address

    def emit32(self, inst):
        self.code.extend(struct.pack("<I", inst & 0xFFFFFFFF))
        self.current_addr += 4

    def emit_li(self, rd, imm):
        imm &= 0xFFFFFFFF
        hi = (imm + 0x800) >> 12
        lo = (imm & 0xFFF) if not (imm & 0x800) else (imm & 0xFFF) - 0x1000
        self.emit32(encode_u(0x37, rd, hi << 12))
        self.emit32(encode_i(0x13, 0x0, rd, rd, lo))

    def emit_addi(self, rd, rs1, imm):
        self.emit32(encode_i(0x13, 0x0, rd, rs1, imm))

    def emit_ret(self):
        # jalr x0, ra, 0
        self.emit32(encode_i(0x67, 0x0, 0, REG_RA, 0))

    def compile_function(self, func_node):
        """Compiles an AdiPython function into native RV32IM machine instructions."""
        func_entry = self.current_addr
        self.functions[func_node.name] = func_entry
        self.local_vars = {}
        self.local_offset = -8 # -4 is saved ra, -8 is saved fp

        # Assign stack offsets for parameters (passed in a0..a7)
        for i, param in enumerate(func_node.params):
            self.local_offset -= 4
            self.local_vars[param] = self.local_offset

        # Prologue: addi sp, sp, -64; sw ra, 60(sp); sw fp, 56(sp); addi fp, sp, 64
        frame_size = 64
        self.emit_addi(REG_SP, REG_SP, -frame_size)
        self.emit32(encode_s(0x23, 0x2, REG_SP, REG_RA, frame_size - 4))
        self.emit32(encode_s(0x23, 0x2, REG_SP, REG_FP, frame_size - 8))
        self.emit_addi(REG_FP, REG_SP, frame_size)

        # Store incoming argument registers into local stack slots
        for i, param in enumerate(func_node.params):
            if i < 8:
                arg_reg = REG_A0 + i
                slot = self.local_vars[param]
                self.emit32(encode_s(0x23, 0x2, REG_FP, arg_reg, slot))

        # Compile body statements
        for stmt in func_node.body:
            self.compile_stmt(stmt, frame_size)

        # Default epilogue if no explicit return
        self.emit_li(REG_A0, 0)
        self.emit_epilogue(frame_size)
        return func_entry

    def emit_epilogue(self, frame_size):
        # Epilogue: lw ra, 60(sp); lw fp, 56(sp); addi sp, sp, 64; ret
        self.emit32(encode_i(0x03, 0x2, REG_RA, REG_SP, frame_size - 4))
        self.emit32(encode_i(0x03, 0x2, REG_FP, REG_SP, frame_size - 8))
        self.emit_addi(REG_SP, REG_SP, frame_size)
        self.emit_ret()

    def compile_stmt(self, stmt, frame_size):
        if isinstance(stmt, Assign):
            # Evaluate expr into a0
            self.compile_expr(stmt.value)
            if stmt.target not in self.local_vars:
                self.local_offset -= 4
                self.local_vars[stmt.target] = self.local_offset
            slot = self.local_vars[stmt.target]
            # sw a0, slot(fp)
            self.emit32(encode_s(0x23, 0x2, REG_FP, REG_A0, slot))

        elif isinstance(stmt, Return):
            if stmt.value:
                self.compile_expr(stmt.value)
            else:
                self.emit_li(REG_A0, 0)
            self.emit_epilogue(frame_size)

        elif isinstance(stmt, ExprStmt):
            self.compile_expr(stmt.expr)

    def compile_expr(self, expr):
        """Compiles expression, placing the result into register a0 (x10)."""
        if isinstance(expr, Number):
            self.emit_li(REG_A0, expr.value)

        elif isinstance(expr, Identifier):
            if expr.name in self.local_vars:
                slot = self.local_vars[expr.name]
                # lw a0, slot(fp)
                self.emit32(encode_i(0x03, 0x2, REG_A0, REG_FP, slot))
            else:
                self.emit_li(REG_A0, 0)

        elif isinstance(expr, BinaryOp):
            # 1. Compile left into a0, push to stack
            self.compile_expr(expr.left)
            self.emit_addi(REG_SP, REG_SP, -4)
            self.emit32(encode_s(0x23, 0x2, REG_SP, REG_A0, 0))

            # 2. Compile right into a0 -> move to a1
            self.compile_expr(expr.right)
            # mv a1, a0 (addi a1, a0, 0)
            self.emit_addi(REG_A1, REG_A0, 0)

            # 3. Pop left into a0
            self.emit32(encode_i(0x03, 0x2, REG_A0, REG_SP, 0))
            self.emit_addi(REG_SP, REG_SP, 4)

            # 4. Perform operation: a0 = a0 (op) a1
            op = expr.op
            if op == "+":
                # add a0, a0, a1
                self.emit32(encode_r(0x33, 0x0, 0x00, REG_A0, REG_A0, REG_A1))
            elif op == "-":
                # sub a0, a0, a1
                self.emit32(encode_r(0x33, 0x0, 0x20, REG_A0, REG_A0, REG_A1))
            elif op == "*":
                # mul a0, a0, a1 (RV32M)
                self.emit32(encode_r(0x33, 0x0, 0x01, REG_A0, REG_A0, REG_A1))
            elif op == "/":
                # div a0, a0, a1 (RV32M)
                self.emit32(encode_r(0x33, 0x4, 0x01, REG_A0, REG_A0, REG_A1))
            elif op == "%":
                # rem a0, a0, a1 (RV32M)
                self.emit32(encode_r(0x33, 0x6, 0x01, REG_A0, REG_A0, REG_A1))
            elif op == "&":
                # and a0, a0, a1
                self.emit32(encode_r(0x33, 0x7, 0x00, REG_A0, REG_A0, REG_A1))
            elif op == "|":
                # or a0, a0, a1
                self.emit32(encode_r(0x33, 0x6, 0x00, REG_A0, REG_A0, REG_A1))
            elif op == "^":
                # xor a0, a0, a1
                self.emit32(encode_r(0x33, 0x4, 0x00, REG_A0, REG_A0, REG_A1))

        elif isinstance(expr, Call):
            # Builtin peek(addr)
            if expr.name == "peek" and len(expr.args) == 1:
                self.compile_expr(expr.args[0])
                # lw a0, 0(a0)
                self.emit32(encode_i(0x03, 0x2, REG_A0, REG_A0, 0))
            # Builtin poke(addr, val)
            elif expr.name == "poke" and len(expr.args) == 2:
                self.compile_expr(expr.args[0])
                self.emit_addi(REG_SP, REG_SP, -4)
                self.emit32(encode_s(0x23, 0x2, REG_SP, REG_A0, 0)) # save addr
                self.compile_expr(expr.args[1])
                self.emit_addi(REG_A1, REG_A0, 0) # val in a1
                self.emit32(encode_i(0x03, 0x2, REG_A0, REG_SP, 0)) # restore addr in a0
                self.emit_addi(REG_SP, REG_SP, 4)
                # sw a1, 0(a0)
                self.emit32(encode_s(0x23, 0x2, REG_A0, REG_A1, 0))

    def write_to_vm(self):
        """Flushes generated machine code bytes directly into VM RAM."""
        if not self.vm: return 0
        ram_off = self.jit_base - 0x80000000
        self.vm.ram[ram_off : ram_off + len(self.code)] = self.code
        # Invalidate instruction cache for this range
        for addr in range(self.jit_base, self.jit_base + len(self.code), 4):
            if addr in self.vm.decode_cache:
                del self.vm.decode_cache[addr]
        return len(self.code)

    def execute_function(self, func_name, args=None, max_steps=10000):
        """Executes a JIT-compiled function on the VM and returns result register a0."""
        if func_name not in self.functions:
            raise ValueError(f"JIT: Function '{func_name}' not compiled")

        entry = self.functions[func_name]
        self.write_to_vm()

        # Set up VM state to call JIT function
        old_pc = self.vm.pc
        self.vm.pc = entry
        self.vm.regs[REG_RA] = 0x80000000 # Return to halt or main
        self.vm.regs[REG_SP] = 0x81000000 # Stack

        # Pass arguments in a0..a7
        if args:
            for i, arg in enumerate(args[:8]):
                self.vm.regs[REG_A0 + i] = int(arg) & 0xFFFFFFFF

        steps = 0
        while steps < max_steps:
            if self.vm.pc == 0x80000000: # Function returned
                break
            self.vm.step()
            steps += 1

        res = self.vm.regs[REG_A0]
        self.vm.pc = old_pc
        return res
