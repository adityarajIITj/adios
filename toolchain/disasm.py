#!/usr/bin/env python3
"""
AdiOS In-Memory RISC-V (RV32IM) Disassembler
Decompiles 32-bit machine code words into formatted human-readable assembly instructions.
Used by the JIT compiler, debugger, and diagnostic utilities.
"""

import struct

ABI_REG_NAMES = [
    "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
    "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
    "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
    "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6"
]

CSR_NAMES = {
    0x300: "mstatus", 0x304: "mie", 0x305: "mtvec", 0x340: "mscratch",
    0x341: "mepc", 0x342: "mcause", 0x343: "mtval", 0x344: "mip",
    0xC00: "mcycle", 0xC02: "minstret"
}

def sign_extend(val, bits):
    sign_bit = 1 << (bits - 1)
    return (val & (sign_bit - 1)) - (val & sign_bit)

class Disassembler:
    def __init__(self, labels=None):
        self.labels = labels or {} # addr -> name

    def reg_name(self, r_idx):
        return ABI_REG_NAMES[r_idx & 0x1F]

    def disassemble_instruction(self, inst, pc=0):
        """Disassembles a single 32-bit instruction word."""
        opcode = inst & 0x7F
        rd     = (inst >> 7) & 0x1F
        funct3 = (inst >> 12) & 0x07
        rs1    = (inst >> 15) & 0x1F
        rs2    = (inst >> 20) & 0x1F
        funct7 = (inst >> 25) & 0x7F

        imm_i = sign_extend(inst >> 20, 12)
        imm_s = sign_extend(((inst >> 25) << 5) | ((inst >> 7) & 0x1F), 12)
        imm_b = sign_extend(((inst >> 31) << 12) | (((inst >> 7) & 1) << 11) | (((inst >> 25) & 0x3F) << 5) | (((inst >> 8) & 0x0F) << 1), 13)
        imm_u = inst & 0xFFFFF000
        imm_j = sign_extend(((inst >> 31) << 20) | (((inst >> 12) & 0xFF) << 12) | (((inst >> 20) & 1) << 11) | (((inst >> 21) & 0x3FF) << 1), 21)

        shamt = (inst >> 20) & 0x1F

        r_d  = self.reg_name(rd)
        r_s1 = self.reg_name(rs1)
        r_s2 = self.reg_name(rs2)

        # LUI
        if opcode == 0x37:
            return f"lui {r_d}, 0x{(imm_u >> 12) & 0xFFFFF:X}"

        # AUIPC
        if opcode == 0x17:
            return f"auipc {r_d}, 0x{(imm_u >> 12) & 0xFFFFF:X}"

        # JAL
        if opcode == 0x6F:
            target = (pc + imm_j) & 0xFFFFFFFF
            lbl = self.labels.get(target, f"0x{target:08X}")
            if rd == 0:
                return f"j {lbl}"
            elif rd == 1:
                return f"jal {lbl}"
            return f"jal {r_d}, {lbl}"

        # JALR
        if opcode == 0x67:
            if rd == 0 and rs1 == 1 and imm_i == 0:
                return "ret"
            if rd == 0 and imm_i == 0:
                return f"jr {r_s1}"
            return f"jalr {r_d}, {imm_i}({r_s1})"

        # Branch
        if opcode == 0x63:
            target = (pc + imm_b) & 0xFFFFFFFF
            lbl = self.labels.get(target, f"0x{target:08X}")
            b_ops = {0: "beq", 1: "bne", 4: "blt", 5: "bge", 6: "bltu", 7: "bgeu"}
            op_name = b_ops.get(funct3, "b_unk")
            if funct3 == 0 and rs2 == 0: return f"beqz {r_s1}, {lbl}"
            if funct3 == 1 and rs2 == 0: return f"bnez {r_s1}, {lbl}"
            return f"{op_name} {r_s1}, {r_s2}, {lbl}"

        # Loads
        if opcode == 0x03:
            l_ops = {0: "lb", 1: "lh", 2: "lw", 4: "lbu", 5: "lhu"}
            return f"{l_ops.get(funct3, 'l_unk')} {r_d}, {imm_i}({r_s1})"

        # Stores
        if opcode == 0x23:
            s_ops = {0: "sb", 1: "sh", 2: "sw"}
            return f"{s_ops.get(funct3, 's_unk')} {r_s2}, {imm_s}({r_s1})"

        # ALU Imm
        if opcode == 0x13:
            if funct3 == 0:
                if rs1 == 0: return f"li {r_d}, {imm_i}"
                if imm_i == 0: return f"mv {r_d}, {r_s1}"
                return f"addi {r_d}, {r_s1}, {imm_i}"
            elif funct3 == 1: return f"slli {r_d}, {r_s1}, {shamt}"
            elif funct3 == 2: return f"slti {r_d}, {r_s1}, {imm_i}"
            elif funct3 == 3: return f"sltiu {r_d}, {r_s1}, {imm_i}"
            elif funct3 == 4: return f"xori {r_d}, {r_s1}, {imm_i}"
            elif funct3 == 5:
                op = "srai" if (funct7 & 0x20) else "srli"
                return f"{op} {r_d}, {r_s1}, {shamt}"
            elif funct3 == 6: return f"ori {r_d}, {r_s1}, {imm_i}"
            elif funct3 == 7: return f"andi {r_d}, {r_s1}, {imm_i}"

        # ALU Reg & RV32M
        if opcode == 0x33:
            if funct7 == 0x01: # RV32M
                m_ops = {0: "mul", 1: "mulh", 2: "mulhsu", 3: "mulhu", 4: "div", 5: "divu", 6: "rem", 7: "remu"}
                return f"{m_ops.get(funct3, 'm_unk')} {r_d}, {r_s1}, {r_s2}"
            else:
                r_ops = {
                    0: "sub" if (funct7 & 0x20) else "add",
                    1: "sll", 2: "slt", 3: "sltu", 4: "xor",
                    5: "sra" if (funct7 & 0x20) else "srl",
                    6: "or", 7: "and"
                }
                return f"{r_ops.get(funct3, 'r_unk')} {r_d}, {r_s1}, {r_s2}"

        # System & CSR
        if opcode == 0x73:
            if funct3 == 0:
                if inst == 0x00000073: return "ecall"
                if inst == 0x00100073: return "ebreak"
                if inst == 0x30200073: return "mret"
                if inst == 0x10500073: return "wfi"
            else:
                csr_num = imm_i & 0xFFF
                csr_str = CSR_NAMES.get(csr_num, f"0x{csr_num:03X}")
                c_ops = {1: "csrrw", 2: "csrrs", 3: "csrrc"}
                return f"{c_ops.get(funct3, 'csr_unk')} {r_d}, {csr_str}, {r_s1}"

        return f".word 0x{inst:08X}"

    def disassemble_range(self, data, start_pc=0x80000000):
        """Disassembles a sequence of bytes into formatted lines."""
        lines = []
        for i in range(0, len(data), 4):
            if i + 4 <= len(data):
                inst = struct.unpack_from("<I", data, i)[0]
                pc = start_pc + i
                asm_text = self.disassemble_instruction(inst, pc)
                lines.append(f"0x{pc:08X}:  {inst:08X}    {asm_text}")
        return "\n".join(lines)
