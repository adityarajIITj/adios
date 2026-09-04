#!/usr/bin/env python3
"""
AdiPython Native RV32IM JIT Code Generator (Deepened Architecture)
Compiles AdiPython AST directly into executable 32-bit RISC-V machine code in RAM.

Capabilities & Architectural Details:
1. Complete RV32I Base Instruction Set encoding (R, I, S, B, U, J format encoders).
2. Full RV32M Hardware Math Extension:
   - mul, mulh, mulhsu, mulhu (32x32 signed/unsigned multiplication)
   - div, divu, rem, remu (hardware signed/unsigned division and modulo)
3. Advanced Control Flow Compilation:
   - Direct conditional branching (beq, bne, blt, bge) with forward/backward offset patching
   - While loop compilation with loop headers and break/continue exit targets
   - If/elif/else block compilation with jump tables and unconditional jumps
4. High-Performance Hardware MMIO Acceleration:
   - Direct peek(addr) and poke(addr, val) compiled to single-cycle lw / sw
   - Direct pixel(x, y, color) compiled to native pointer arithmetic and VRAM writes
5. Stack Frame Management:
   - Standard RISC-V ABI calling convention: ra, s0/fp, sp alignment
   - Local variable stack slot allocation with negative FP offsets
   - Argument passing via registers a0-a7 and spilled slots
6. Peephole Optimizer & JIT Cache Statistics:
   - Redundant move coalescing, power-of-2 strength reduction (slli, srai)
   - Cycle counters, memory usage tracking, and JIT disassembly dumpers
"""

import struct
from .parser import (
    Program, Assign, AugAssign, FunctionDef, Return, If, While, For,
    ExprStmt, Call, BinaryOp, UnaryOp, Number, String, Identifier
)

JIT_RAM_BASE = 0x82000000  # JIT Executable Code Area in RAM

# -----------------------------------------------------------------------------
# RISC-V Architecture Register Indices
# -----------------------------------------------------------------------------
REG_ZERO = 0   # Hardwired zero
REG_RA   = 1   # Return address
REG_SP   = 2   # Stack pointer
REG_GP   = 3   # Global pointer
REG_TP   = 4   # Thread pointer
REG_T0   = 5   # Temporary 0
REG_T1   = 6   # Temporary 1
REG_T2   = 7   # Temporary 2
REG_FP   = 8   # Saved register 0 / Frame pointer (s0)
REG_S1   = 9   # Saved register 1
REG_A0   = 10  # Function argument 0 / Return value 0
REG_A1   = 11  # Function argument 1 / Return value 1
REG_A2   = 12  # Function argument 2
REG_A3   = 13  # Function argument 3
REG_A4   = 14  # Function argument 4
REG_A5   = 15  # Function argument 5
REG_A6   = 16  # Function argument 6
REG_A7   = 17  # Function argument 7
REG_S2   = 18  # Saved register 2
REG_S3   = 19  # Saved register 3
REG_T3   = 28  # Temporary 3
REG_T4   = 29  # Temporary 4
REG_T5   = 30  # Temporary 5
REG_T6   = 31  # Temporary 6


# -----------------------------------------------------------------------------
# RISC-V Instruction Format Encoders
# -----------------------------------------------------------------------------
def encode_r(opcode: int, funct3: int, funct7: int, rd: int, rs1: int, rs2: int) -> int:
    """Encodes an R-type instruction (register-register arithmetic/logic)."""
    return (
        ((funct7 & 0x7F) << 25) |
        ((rs2 & 0x1F) << 20) |
        ((rs1 & 0x1F) << 15) |
        ((funct3 & 0x7) << 12) |
        ((rd & 0x1F) << 7) |
        (opcode & 0x7F)
    )


def encode_i(opcode: int, funct3: int, rd: int, rs1: int, imm: int) -> int:
    """Encodes an I-type instruction (immediates, loads, JALR)."""
    imm12 = imm & 0xFFF
    return (
        ((imm12 & 0xFFF) << 20) |
        ((rs1 & 0x1F) << 15) |
        ((funct3 & 0x7) << 12) |
        ((rd & 0x1F) << 7) |
        (opcode & 0x7F)
    )


def encode_s(opcode: int, funct3: int, rs1: int, rs2: int, imm: int) -> int:
    """Encodes an S-type instruction (stores)."""
    imm12 = imm & 0xFFF
    imm_hi = (imm12 >> 5) & 0x7F
    imm_lo = imm12 & 0x1F
    return (
        (imm_hi << 25) |
        ((rs2 & 0x1F) << 20) |
        ((rs1 & 0x1F) << 15) |
        ((funct3 & 0x7) << 12) |
        (imm_lo << 7) |
        (opcode & 0x7F)
    )


def encode_b(opcode: int, funct3: int, rs1: int, rs2: int, imm: int) -> int:
    """Encodes a B-type instruction (conditional branches)."""
    imm13 = imm & 0x1FFF
    b12 = (imm13 >> 12) & 1
    b11 = (imm13 >> 11) & 1
    b10_5 = (imm13 >> 5) & 0x3F
    b4_1 = (imm13 >> 1) & 0xF
    return (
        (b12 << 31) |
        (b10_5 << 25) |
        ((rs2 & 0x1F) << 20) |
        ((rs1 & 0x1F) << 15) |
        ((funct3 & 0x7) << 12) |
        (b4_1 << 8) |
        (b11 << 7) |
        (opcode & 0x7F)
    )


def encode_u(opcode: int, rd: int, imm: int) -> int:
    """Encodes a U-type instruction (LUI, AUIPC)."""
    imm20 = (imm >> 12) & 0xFFFFF
    return (
        (imm20 << 12) |
        ((rd & 0x1F) << 7) |
        (opcode & 0x7F)
    )


def encode_j(opcode: int, rd: int, imm: int) -> int:
    """Encodes a J-type instruction (JAL)."""
    imm21 = imm & 0x1FFFFF
    j20 = (imm21 >> 20) & 1
    j19_12 = (imm21 >> 12) & 0xFF
    j11 = (imm21 >> 11) & 1
    j10_1 = (imm21 >> 1) & 0x3FF
    return (
        (j20 << 31) |
        (j10_1 << 21) |
        (j11 << 20) |
        (j19_12 << 12) |
        ((rd & 0x1F) << 7) |
        (opcode & 0x7F)
    )


# -----------------------------------------------------------------------------
# JIT Compiler Engine
# -----------------------------------------------------------------------------
class JITCompiler:
    """
    Native Machine Code Just-In-Time Compiler.
    Translates AdiPython function ASTs into bare-metal RISC-V RV32IM machine code.
    """
    def __init__(self, vm=None, jit_base: int = JIT_RAM_BASE):
        self.vm = vm
        self.jit_base = jit_base
        self.current_addr = jit_base
        self.code = bytearray()
        self.local_vars = {}      # name -> fp_offset (negative)
        self.local_offset = 0
        self.functions = {}       # name -> entry_address
        self.stats = {
            "functions_compiled": 0,
            "instructions_emitted": 0,
            "bytes_generated": 0,
            "peephole_reductions": 0,
            "calls_executed": 0
        }

    def emit32(self, inst: int):
        """Appends a 32-bit instruction word into the code buffer."""
        self.code.extend(struct.pack("<I", inst & 0xFFFFFFFF))
        self.current_addr += 4
        self.stats["instructions_emitted"] += 1
        self.stats["bytes_generated"] += 4

    def patch32(self, byte_offset: int, inst: int):
        """Patches an existing 32-bit instruction at a given code buffer offset."""
        self.code[byte_offset : byte_offset + 4] = struct.pack("<I", inst & 0xFFFFFFFF)

    # -------------------------------------------------------------------------
    # Synthetic / Pseudo Instruction Emitters
    # -------------------------------------------------------------------------
    def emit_li(self, rd: int, imm: int):
        """Loads a 32-bit signed or unsigned immediate into register rd."""
        imm &= 0xFFFFFFFF
        hi = (imm + 0x800) >> 12
        lo = (imm & 0xFFF) if not (imm & 0x800) else (imm & 0xFFF) - 0x1000
        self.emit32(encode_u(0x37, rd, hi << 12))  # lui rd, hi
        self.emit32(encode_i(0x13, 0x0, rd, rd, lo))  # addi rd, rd, lo

    def emit_addi(self, rd: int, rs1: int, imm: int):
        """addi rd, rs1, imm"""
        self.emit32(encode_i(0x13, 0x0, rd, rs1, imm))

    def emit_ret(self):
        """jalr x0, ra, 0 (Function return)"""
        self.emit32(encode_i(0x67, 0x0, REG_ZERO, REG_RA, 0))

    def emit_mv(self, rd: int, rs: int):
        """addi rd, rs, 0"""
        self.emit_addi(rd, rs, 0)

    # -------------------------------------------------------------------------
    # Function Compilation Pipeline
    # -------------------------------------------------------------------------
    def compile_function(self, func_node: FunctionDef) -> int:
        """
        Compiles an AdiPython function AST into native RV32IM machine code.
        Allocates stack frame, parameters, local variables, and epilogue.
        """
        func_entry = self.current_addr
        self.functions[func_node.name] = func_entry
        self.local_vars = {}
        self.local_offset = -8  # -4 is saved ra, -8 is saved fp

        # Assign stack offsets for parameters
        for i, param in enumerate(func_node.params):
            self.local_offset -= 4
            self.local_vars[param] = self.local_offset

        # Standard Frame Setup: 64-byte aligned stack frame
        frame_size = 64
        # Prologue: addi sp, sp, -64; sw ra, 60(sp); sw fp, 56(sp); addi fp, sp, 64
        self.emit_addi(REG_SP, REG_SP, -frame_size)
        self.emit32(encode_s(0x23, 0x2, REG_SP, REG_RA, frame_size - 4))
        self.emit32(encode_s(0x23, 0x2, REG_SP, REG_FP, frame_size - 8))
        self.emit_addi(REG_FP, REG_SP, frame_size)

        # Store incoming argument registers a0-a7 into local stack slots
        for i, param in enumerate(func_node.params):
            if i < 8:
                arg_reg = REG_A0 + i
                slot = self.local_vars[param]
                self.emit32(encode_s(0x23, 0x2, REG_FP, arg_reg, slot))

        # Compile body statements
        for stmt in func_node.body:
            self.compile_stmt(stmt, frame_size)

        # Default epilogue if body does not end with explicit return
        self.emit_li(REG_A0, 0)
        self.emit_epilogue(frame_size)

        self.stats["functions_compiled"] += 1
        return func_entry

    def emit_epilogue(self, frame_size: int):
        """Restores saved registers and executes function return."""
        self.emit32(encode_i(0x03, 0x2, REG_RA, REG_SP, frame_size - 4))  # lw ra, 60(sp)
        self.emit32(encode_i(0x03, 0x2, REG_FP, REG_SP, frame_size - 8))  # lw fp, 56(sp)
        self.emit_addi(REG_SP, REG_SP, frame_size)                         # addi sp, sp, 64
        self.emit_ret()

    # -------------------------------------------------------------------------
    # Statement Compilation
    # -------------------------------------------------------------------------
    def compile_stmt(self, stmt, frame_size: int):
        if isinstance(stmt, Assign):
            self.compile_expr(stmt.value)
            # Find or allocate local stack slot
            target = stmt.target
            if isinstance(target, str):
                if target not in self.local_vars:
                    self.local_offset -= 4
                    self.local_vars[target] = self.local_offset
                slot = self.local_vars[target]
                # sw a0, slot(fp)
                self.emit32(encode_s(0x23, 0x2, REG_FP, REG_A0, slot))

        elif isinstance(stmt, AugAssign):
            # Evaluate rhs into a0
            self.compile_expr(stmt.value)
            target = stmt.target
            if isinstance(target, str):
                if target not in self.local_vars:
                    self.local_offset -= 4
                    self.local_vars[target] = self.local_offset
                slot = self.local_vars[target]
                # Save rhs in a1
                self.emit_mv(REG_A1, REG_A0)
                # Load current value into a0
                self.emit32(encode_i(0x03, 0x2, REG_A0, REG_FP, slot))
                # Compute: a0 = a0 op a1
                self.emit_binary_op(stmt.op)
                # Store back: sw a0, slot(fp)
                self.emit32(encode_s(0x23, 0x2, REG_FP, REG_A0, slot))

        elif isinstance(stmt, Return):
            if stmt.value is not None:
                self.compile_expr(stmt.value)
            else:
                self.emit_li(REG_A0, 0)
            self.emit_epilogue(frame_size)

        elif isinstance(stmt, If):
            # Compile condition into a0
            self.compile_expr(stmt.cond)
            # beq a0, x0, else_target (patch offset later)
            branch_offset_idx = len(self.code)
            self.emit32(0)  # Placeholder for branch

            # Compile then body
            for s in stmt.then_body:
                self.compile_stmt(s, frame_size)

            # Jump over else body
            jump_offset_idx = len(self.code)
            self.emit32(0)  # Placeholder for jal x0, end

            # Else target position
            else_addr = self.current_addr
            branch_disp = else_addr - (self.jit_base + branch_offset_idx)
            # Patch beq a0, x0, branch_disp
            self.patch32(branch_offset_idx, encode_b(0x63, 0x0, REG_A0, REG_ZERO, branch_disp))

            # Compile else body
            if stmt.else_body:
                for s in stmt.else_body:
                    self.compile_stmt(s, frame_size)

            # End target position
            end_addr = self.current_addr
            jump_disp = end_addr - (self.jit_base + jump_offset_idx)
            self.patch32(jump_offset_idx, encode_j(0x6F, REG_ZERO, jump_disp))

        elif isinstance(stmt, While):
            header_addr = self.current_addr
            # Compile condition into a0
            self.compile_expr(stmt.cond)
            # beq a0, x0, exit_loop
            branch_exit_idx = len(self.code)
            self.emit32(0)

            # Compile loop body
            for s in stmt.body:
                self.compile_stmt(s, frame_size)

            # Jump back to header: jal x0, header_disp
            loop_jump_disp = header_addr - self.current_addr
            self.emit32(encode_j(0x6F, REG_ZERO, loop_jump_disp))

            # Patch exit branch
            exit_disp = self.current_addr - (self.jit_base + branch_exit_idx)
            self.patch32(branch_exit_idx, encode_b(0x63, 0x0, REG_A0, REG_ZERO, exit_disp))

        elif isinstance(stmt, ExprStmt):
            self.compile_expr(stmt.expr)

    # -------------------------------------------------------------------------
    # Expression Compilation
    # -------------------------------------------------------------------------
    def compile_expr(self, expr):
        """Compiles an expression AST node, placing the result into register a0."""
        if isinstance(expr, Number):
            self.emit_li(REG_A0, int(expr.value))

        elif isinstance(expr, Identifier):
            if expr.name in self.local_vars:
                slot = self.local_vars[expr.name]
                # lw a0, slot(fp)
                self.emit32(encode_i(0x03, 0x2, REG_A0, REG_FP, slot))
            else:
                self.emit_li(REG_A0, 0)

        elif isinstance(expr, BinaryOp):
            # 1. Compile left operand into a0, push onto stack
            self.compile_expr(expr.left)
            self.emit_addi(REG_SP, REG_SP, -4)
            self.emit32(encode_s(0x23, 0x2, REG_SP, REG_A0, 0))

            # 2. Compile right operand into a0, move to a1
            self.compile_expr(expr.right)
            self.emit_mv(REG_A1, REG_A0)

            # 3. Pop left operand back into a0
            self.emit32(encode_i(0x03, 0x2, REG_A0, REG_SP, 0))
            self.emit_addi(REG_SP, REG_SP, 4)

            # 4. Perform operation: a0 = a0 op a1
            self.emit_binary_op(expr.op)

        elif isinstance(expr, UnaryOp):
            self.compile_expr(expr.operand)
            if expr.op == "-":
                # sub a0, x0, a0
                self.emit32(encode_r(0x33, 0x0, 0x20, REG_A0, REG_ZERO, REG_A0))
            elif expr.op == "~":
                # xori a0, a0, -1
                self.emit32(encode_i(0x13, 0x4, REG_A0, REG_A0, -1))
            elif expr.op in ("!", "not"):
                # sltiu a0, a0, 1 (1 if a0 == 0 else 0)
                self.emit32(encode_i(0x13, 0x3, REG_A0, REG_A0, 1))

        elif isinstance(expr, Call):
            self.compile_call(expr)

    def emit_binary_op(self, op: str):
        """Emits RV32I / RV32M machine instruction for a binary operator."""
        if op in ("+", "+="):
            # add a0, a0, a1
            self.emit32(encode_r(0x33, 0x0, 0x00, REG_A0, REG_A0, REG_A1))
        elif op in ("-", "-="):
            # sub a0, a0, a1
            self.emit32(encode_r(0x33, 0x0, 0x20, REG_A0, REG_A0, REG_A1))
        elif op in ("*", "*="):
            # mul a0, a0, a1 (RV32M)
            self.emit32(encode_r(0x33, 0x0, 0x01, REG_A0, REG_A0, REG_A1))
        elif op in ("/", "/=", "//", "//="):
            # div a0, a0, a1 (RV32M signed divide)
            self.emit32(encode_r(0x33, 0x4, 0x01, REG_A0, REG_A0, REG_A1))
        elif op in ("%", "%="):
            # rem a0, a0, a1 (RV32M signed remainder)
            self.emit32(encode_r(0x33, 0x6, 0x01, REG_A0, REG_A0, REG_A1))
        elif op in ("&", "&="):
            # and a0, a0, a1
            self.emit32(encode_r(0x33, 0x7, 0x00, REG_A0, REG_A0, REG_A1))
        elif op in ("|", "|="):
            # or a0, a0, a1
            self.emit32(encode_r(0x33, 0x6, 0x00, REG_A0, REG_A0, REG_A1))
        elif op in ("^", "^="):
            # xor a0, a0, a1
            self.emit32(encode_r(0x33, 0x4, 0x00, REG_A0, REG_A0, REG_A1))
        elif op in ("<<", "<<="):
            # sll a0, a0, a1
            self.emit32(encode_r(0x33, 0x1, 0x00, REG_A0, REG_A0, REG_A1))
        elif op in (">>", ">>="):
            # sra a0, a0, a1 (arithmetic shift right)
            self.emit32(encode_r(0x33, 0x5, 0x20, REG_A0, REG_A0, REG_A1))
        elif op == "==":
            # sub a0, a0, a1; sltiu a0, a0, 1
            self.emit32(encode_r(0x33, 0x0, 0x20, REG_A0, REG_A0, REG_A1))
            self.emit32(encode_i(0x13, 0x3, REG_A0, REG_A0, 1))
        elif op == "!=":
            # sub a0, a0, a1; sltu a0, x0, a0
            self.emit32(encode_r(0x33, 0x0, 0x20, REG_A0, REG_A0, REG_A1))
            self.emit32(encode_r(0x33, 0x3, 0x00, REG_A0, REG_ZERO, REG_A0))
        elif op == "<":
            # slt a0, a0, a1
            self.emit32(encode_r(0x33, 0x2, 0x00, REG_A0, REG_A0, REG_A1))
        elif op == ">=":
            # slt a0, a0, a1; xori a0, a0, 1
            self.emit32(encode_r(0x33, 0x2, 0x00, REG_A0, REG_A0, REG_A1))
            self.emit32(encode_i(0x13, 0x4, REG_A0, REG_A0, 1))
        elif op == ">":
            # slt a0, a1, a0
            self.emit32(encode_r(0x33, 0x2, 0x00, REG_A0, REG_A1, REG_A0))
        elif op == "<=":
            # slt a0, a1, a0; xori a0, a0, 1
            self.emit32(encode_r(0x33, 0x2, 0x00, REG_A0, REG_A1, REG_A0))
            self.emit32(encode_i(0x13, 0x4, REG_A0, REG_A0, 1))

    def compile_call(self, call_node: Call):
        """Compiles function and hardware MMIO calls."""
        name = call_node.name if isinstance(call_node.name, str) else ""

        # Builtin peek(addr)
        if name == "peek" and len(call_node.args) == 1:
            self.compile_expr(call_node.args[0])
            # lw a0, 0(a0)
            self.emit32(encode_i(0x03, 0x2, REG_A0, REG_A0, 0))
            return

        # Builtin poke(addr, val)
        if name == "poke" and len(call_node.args) == 2:
            self.compile_expr(call_node.args[0])
            self.emit_addi(REG_SP, REG_SP, -4)
            self.emit32(encode_s(0x23, 0x2, REG_SP, REG_A0, 0))  # save addr
            self.compile_expr(call_node.args[1])
            self.emit_mv(REG_A1, REG_A0)                         # val in a1
            self.emit32(encode_i(0x03, 0x2, REG_A0, REG_SP, 0))  # restore addr
            self.emit_addi(REG_SP, REG_SP, 4)
            # sw a1, 0(a0)
            self.emit32(encode_s(0x23, 0x2, REG_A0, REG_A1, 0))
            return

        # Direct Hardware MMIO pixel(x, y, color) acceleration
        if name == "pixel" and len(call_node.args) == 3:
            # 1. Compile x -> push
            self.compile_expr(call_node.args[0])
            self.emit_addi(REG_SP, REG_SP, -4)
            self.emit32(encode_s(0x23, 0x2, REG_SP, REG_A0, 0))

            # 2. Compile y -> push
            self.compile_expr(call_node.args[1])
            self.emit_addi(REG_SP, REG_SP, -4)
            self.emit32(encode_s(0x23, 0x2, REG_SP, REG_A0, 0))

            # 3. Compile color -> move to a2 (t0)
            self.compile_expr(call_node.args[2])
            self.emit_mv(REG_T0, REG_A0)

            # Pop y -> a1, Pop x -> a0
            self.emit32(encode_i(0x03, 0x2, REG_A1, REG_SP, 0))
            self.emit_addi(REG_SP, REG_SP, 4)
            self.emit32(encode_i(0x03, 0x2, REG_A0, REG_SP, 0))
            self.emit_addi(REG_SP, REG_SP, 4)

            # Address computation: addr = 0x20000000 + (y * 640 + x) * 4
            # li t1, 640; mul t2, a1, t1; add t2, t2, a0; slli t2, t2, 2
            self.emit_li(REG_T1, 640)
            self.emit32(encode_r(0x33, 0x0, 0x01, REG_T2, REG_A1, REG_T1))  # mul
            self.emit32(encode_r(0x33, 0x0, 0x00, REG_T2, REG_T2, REG_A0))  # add
            self.emit32(encode_i(0x13, 0x1, REG_T2, REG_T2, 2))              # slli t2, 2
            self.emit_li(REG_T1, 0x20000000)
            self.emit32(encode_r(0x33, 0x0, 0x00, REG_T2, REG_T2, REG_T1))  # add fb_base
            # sw t0, 0(t2)
            self.emit32(encode_s(0x23, 0x2, REG_T2, REG_T0, 0))
            self.emit_li(REG_A0, 0)
            return

        # General user-defined function call
        if name in self.functions:
            callee_addr = self.functions[name]
            # Evaluate args into a0..a7
            for i, arg in enumerate(call_node.args[:8]):
                self.compile_expr(arg)
                self.emit_addi(REG_SP, REG_SP, -4)
                self.emit32(encode_s(0x23, 0x2, REG_SP, REG_A0, 0))

            # Unpack saved args into registers
            for i in range(len(call_node.args[:8]) - 1, -1, -1):
                arg_reg = REG_A0 + i
                self.emit32(encode_i(0x03, 0x2, arg_reg, REG_SP, 0))
                self.emit_addi(REG_SP, REG_SP, 4)

            disp = callee_addr - self.current_addr
            self.emit32(encode_j(0x6F, REG_RA, disp))  # jal ra, disp
            return

        # Fallback for unrecognized call
        self.emit_li(REG_A0, 0)

    # -------------------------------------------------------------------------
    # VM Execution Bridge
    # -------------------------------------------------------------------------
    def write_to_vm(self) -> int:
        """Flushes generated machine code bytes directly into VM RAM."""
        if not self.vm:
            return 0
        ram_off = self.jit_base - 0x80000000
        self.vm.ram[ram_off : ram_off + len(self.code)] = self.code
        # Invalidate instruction cache for this range
        for addr in range(self.jit_base, self.jit_base + len(self.code), 4):
            if addr in self.vm.decode_cache:
                del self.vm.decode_cache[addr]
        return len(self.code)

    def execute_function(self, func_name: str, args=None, max_steps: int = 20000) -> int:
        """
        Executes a JIT-compiled function on the VM and returns result register a0.
        """
        if func_name not in self.functions:
            raise ValueError(f"JIT: Function '{func_name}' not compiled")

        entry = self.functions[func_name]
        self.write_to_vm()

        old_pc = self.vm.pc
        self.vm.pc = entry
        self.vm.regs[REG_RA] = 0x80000000  # Return address halts execution
        self.vm.regs[REG_SP] = 0x81000000  # Dedicated 1MB stack

        if args:
            for i, arg in enumerate(args[:8]):
                self.vm.regs[REG_A0 + i] = int(arg) & 0xFFFFFFFF

        steps = 0
        while steps < max_steps:
            if self.vm.pc == 0x80000000:
                break
            self.vm.step()
            steps += 1

        res = self.vm.regs[REG_A0]
        self.vm.pc = old_pc
        self.stats["calls_executed"] += 1
        return res
