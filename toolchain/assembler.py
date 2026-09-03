#!/usr/bin/env python3
"""
AdiOS Zero-Dependency RV32I/M Assembler & Linker
Compiles RISC-V assembly into a flat bootable binary (adios.bin) loaded at 0x80000000.
"""

import sys
import re
import struct

BASE_ADDR = 0x80000000

REG_NAMES = {
    "zero": 0, "x0": 0,
    "ra": 1,   "x1": 1,
    "sp": 2,   "x2": 2,
    "gp": 3,   "x3": 3,
    "tp": 4,   "x4": 4,
    "t0": 5,   "x5": 5,
    "t1": 6,   "x6": 6,
    "t2": 7,   "x7": 7,
    "s0": 8,   "fp": 8, "x8": 8,
    "s1": 9,   "x9": 9,
    "a0": 10,  "x10": 10,
    "a1": 11,  "x11": 11,
    "a2": 12,  "x12": 12,
    "a3": 13,  "x13": 13,
    "a4": 14,  "x14": 14,
    "a5": 15,  "x15": 15,
    "a6": 16,  "x16": 16,
    "a7": 17,  "x17": 17,
    "s2": 18,  "x18": 18,
    "s3": 19,  "x19": 19,
    "s4": 20,  "x20": 20,
    "s5": 21,  "x21": 21,
    "s6": 22,  "x22": 22,
    "s7": 23,  "x23": 23,
    "s8": 24,  "x24": 24,
    "s9": 25,  "x25": 25,
    "s10": 26, "x26": 26,
    "s11": 27, "x27": 27,
    "t3": 28,  "x28": 28,
    "t4": 29,  "x29": 29,
    "t5": 30,  "x30": 30,
    "t6": 31,  "x31": 31,
}

CSR_NAMES = {
    "mstatus":  0x300,
    "mie":      0x304,
    "mtvec":    0x305,
    "mscratch": 0x340,
    "mepc":     0x341,
    "mcause":   0x342,
    "mip":      0x344,
}

def parse_reg(r):
    r = r.strip().lower().rstrip(',')
    if r in REG_NAMES:
        return REG_NAMES[r]
    if r.startswith('x') and r[1:].isdigit():
        idx = int(r[1:])
        if 0 <= idx < 32:
            return idx
    raise ValueError(f"Invalid register: {r}")

def parse_csr(c):
    c = c.strip().lower().rstrip(',')
    if c in CSR_NAMES:
        return CSR_NAMES[c]
    if c.startswith('0x') or c.isdigit():
        return int(c, 0)
    raise ValueError(f"Invalid CSR: {c}")

def parse_imm(s, labels, cur_addr):
    s = s.strip().rstrip(',')
    if s in labels:
        return labels[s]
    # Handle %hi(label) and %lo(label)
    if s.startswith("%hi(") and s.endswith(")"):
        inner = s[4:-1]
        val = labels[inner] if inner in labels else int(inner, 0)
        return (val + 0x800) >> 12
    if s.startswith("%lo(") and s.endswith(")"):
        inner = s[4:-1]
        val = labels[inner] if inner in labels else int(inner, 0)
        return (val & 0xFFF) if not (val & 0x800) else (val & 0xFFF) - 0x1000

    try:
        return int(s, 0)
    except ValueError:
        return 0

def encode_r(opcode, funct3, funct7, rd, rs1, rs2):
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode

def encode_i(opcode, funct3, rd, rs1, imm):
    imm &= 0xFFF
    return (imm << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode

def encode_s(opcode, funct3, rs1, rs2, imm):
    imm &= 0xFFF
    imm11_5 = (imm >> 5) & 0x7F
    imm4_0 = imm & 0x1F
    return (imm11_5 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (imm4_0 << 7) | opcode

def encode_b(opcode, funct3, rs1, rs2, imm):
    imm &= 0x1FFF
    imm12 = (imm >> 12) & 1
    imm10_5 = (imm >> 5) & 0x3F
    imm4_1 = (imm >> 1) & 0x0F
    imm11 = (imm >> 11) & 1
    return (imm12 << 31) | (imm10_5 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (imm4_1 << 8) | (imm11 << 7) | opcode

def encode_u(opcode, rd, imm):
    imm20 = (imm >> 12) & 0xFFFFF
    return (imm20 << 12) | (rd << 7) | opcode

def encode_j(opcode, rd, imm):
    imm &= 0x1FFFFF
    imm20 = (imm >> 20) & 1
    imm10_1 = (imm >> 1) & 0x3FF
    imm11 = (imm >> 11) & 1
    imm19_12 = (imm >> 12) & 0xFF
    return (imm20 << 31) | (imm10_1 << 21) | (imm11 << 20) | (imm19_12 << 12) | (rd << 7) | opcode

import os

class Assembler:
    def __init__(self):
        self.labels = {}

    def load_lines(self, filename):
        base_dir = os.path.dirname(filename)
        with open(filename, "r") as f:
            raw_lines = f.readlines()
        expanded = []
        for line in raw_lines:
            stripped = line.strip()
            if stripped.startswith(".include"):
                inc_rel = stripped.split('"')[1]
                inc_path = os.path.join(base_dir, inc_rel) if base_dir else inc_rel
                expanded.extend(self.load_lines(inc_path))
            else:
                code = stripped.split('#')[0].strip()
                if not code:
                    continue
                if '"' in code:
                    expanded.append(code + "\n")
                else:
                    for sub in code.split(';'):
                        sub = sub.strip()
                        if sub:
                            expanded.append(sub + "\n")
        return expanded

    def assemble_file(self, filename, output_bin):
        lines = self.load_lines(filename)

        # Pass 1: Collect labels and calculate addresses
        addr = BASE_ADDR
        for raw in lines:
            line = raw.strip()
            if not line: continue

            # Check label at start of line
            m = re.match(r'^([a-zA-Z_.][a-zA-Z0-9_.]*)\s*:\s*(.*)$', line)
            if m:
                lbl = m.group(1)
                self.labels[lbl] = addr
                line = m.group(2).strip()
                if not line: continue

            tokens = [t.strip().rstrip(',') for t in re.findall(r'[^\s,]+|"[^"]*"', line) if t.strip()]
            if not tokens: continue
            op = tokens[0]

            if op.startswith('.'):
                if op == ".align":
                    align_bytes = int(tokens[1])
                    addr = (addr + (align_bytes - 1)) & ~(align_bytes - 1)
                elif op in [".word", ".4byte"]:
                    addr += 4 * (len(tokens) - 1)
                elif op in [".byte"]:
                    addr += len(tokens) - 1
                elif op in [".string", ".asciz"]:
                    s = line.split('"', 1)[1].rsplit('"', 1)[0]
                    # decode escape characters
                    s = bytes(s, "utf-8").decode("unicode_escape")
                    addr += len(s) + 1
                elif op == ".ascii":
                    s = line.split('"', 1)[1].rsplit('"', 1)[0]
                    s = bytes(s, "utf-8").decode("unicode_escape")
                    addr += len(s)
                elif op in [".space", ".zero"]:
                    addr += int(tokens[1], 0)
                continue

            # Pseudo expansions length
            if op == "li":
                addr += 8  # lui + addi
            elif op == "la":
                addr += 8  # lui + addi
            elif op == "call":
                addr += 8  # auipc + jalr
            else:
                addr += 4

        # Pass 2: Generate bytes
        addr = BASE_ADDR
        byte_stream = bytearray()

        for raw in lines:
            line = raw.strip()
            if not line: continue
            m = re.match(r'^([a-zA-Z_.][a-zA-Z0-9_.]*)\s*:\s*(.*)$', line)
            if m:
                line = m.group(2).strip()
                if not line: continue

            tokens = [t.strip().rstrip(',') for t in re.findall(r'[^\s,]+|"[^"]*"', line) if t.strip()]
            if not tokens: continue
            op = tokens[0].lower()

            if op.startswith('.'):
                if op == ".align":
                    align_bytes = int(tokens[1])
                    new_addr = (addr + (align_bytes - 1)) & ~(align_bytes - 1)
                    byte_stream.extend(b'\x00' * (new_addr - addr))
                    addr = new_addr
                elif op in [".word", ".4byte"]:
                    for val_str in tokens[1:]:
                        v = parse_imm(val_str, self.labels, addr) & 0xFFFFFFFF
                        byte_stream.extend(struct.pack("<I", v))
                        addr += 4
                elif op in [".byte"]:
                    for val_str in tokens[1:]:
                        v = parse_imm(val_str, self.labels, addr) & 0xFF
                        byte_stream.extend(struct.pack("B", v))
                        addr += 1
                elif op in [".string", ".asciz"]:
                    s = line.split('"', 1)[1].rsplit('"', 1)[0]
                    s = bytes(s, "utf-8").decode("unicode_escape")
                    data = s.encode('utf-8') + b'\x00'
                    byte_stream.extend(data)
                    addr += len(data)
                elif op == ".ascii":
                    s = line.split('"', 1)[1].rsplit('"', 1)[0]
                    s = bytes(s, "utf-8").decode("unicode_escape")
                    data = s.encode('utf-8')
                    byte_stream.extend(data)
                    addr += len(data)
                elif op in [".space", ".zero"]:
                    cnt = int(tokens[1], 0)
                    byte_stream.extend(b'\x00' * cnt)
                    addr += cnt
                continue

            inst_bytes = self.assemble_instruction(op, tokens[1:], addr)
            byte_stream.extend(inst_bytes)
            addr += len(inst_bytes)

        with open(output_bin, "wb") as f:
            f.write(byte_stream)

        print(f"[Toolchain] Successfully assembled '{filename}' -> '{output_bin}' ({len(byte_stream)} bytes)")
        return len(byte_stream)

    def assemble_instruction(self, op, args, addr):
        # Pseudo instructions
        if op == "beqz":
            rs = parse_reg(args[0])
            target = parse_imm(args[1], self.labels, addr)
            return struct.pack("<I", encode_b(0x63, 0x0, rs, 0, target - addr)) # beq rs, x0, target
        if op == "bnez":
            rs = parse_reg(args[0])
            target = parse_imm(args[1], self.labels, addr)
            return struct.pack("<I", encode_b(0x63, 0x1, rs, 0, target - addr)) # bne rs, x0, target
        if op == "bgt":
            rs1 = parse_reg(args[0])
            rs2 = parse_reg(args[1])
            target = parse_imm(args[2], self.labels, addr)
            return struct.pack("<I", encode_b(0x63, 0x4, rs2, rs1, target - addr)) # blt rs2, rs1, target
        if op == "ble":
            rs1 = parse_reg(args[0])
            rs2 = parse_reg(args[1])
            target = parse_imm(args[2], self.labels, addr)
            return struct.pack("<I", encode_b(0x63, 0x5, rs2, rs1, target - addr)) # bge rs2, rs1, target
        if op == "bgtz":
            rs = parse_reg(args[0])
            target = parse_imm(args[1], self.labels, addr)
            return struct.pack("<I", encode_b(0x63, 0x4, 0, rs, target - addr)) # blt x0, rs, target
        if op == "blez":
            rs = parse_reg(args[0])
            target = parse_imm(args[1], self.labels, addr)
            return struct.pack("<I", encode_b(0x63, 0x5, 0, rs, target - addr)) # bge x0, rs, target
        if op == "bltz":
            rs = parse_reg(args[0])
            target = parse_imm(args[1], self.labels, addr)
            return struct.pack("<I", encode_b(0x63, 0x4, rs, 0, target - addr)) # blt rs, x0, target
        if op == "bgez":
            rs = parse_reg(args[0])
            target = parse_imm(args[1], self.labels, addr)
            return struct.pack("<I", encode_b(0x63, 0x5, rs, 0, target - addr)) # bge rs, x0, target
        if op == "nop":
            return struct.pack("<I", encode_i(0x13, 0x0, 0, 0, 0)) # addi x0, x0, 0
        if op == "ret":
            return struct.pack("<I", encode_i(0x67, 0x0, 0, 1, 0)) # jalr x0, ra, 0
        if op == "mv":
            rd = parse_reg(args[0])
            rs1 = parse_reg(args[1])
            return struct.pack("<I", encode_i(0x13, 0x0, rd, rs1, 0)) # addi rd, rs1, 0
        if op == "not":
            rd = parse_reg(args[0])
            rs1 = parse_reg(args[1]) if len(args) > 1 else rd
            return struct.pack("<I", encode_i(0x13, 0x4, rd, rs1, -1)) # xori rd, rs1, -1
        if op == "neg":
            rd = parse_reg(args[0])
            rs1 = parse_reg(args[1]) if len(args) > 1 else rd
            return struct.pack("<I", encode_r(0x33, 0x0, 0x20, rd, 0, rs1)) # sub rd, x0, rs1
        if op == "j":
            target = parse_imm(args[0], self.labels, addr)
            offset = target - addr
            return struct.pack("<I", encode_j(0x6F, 0, offset))
        if op == "jr":
            rs = parse_reg(args[0])
            return struct.pack("<I", encode_i(0x67, 0x0, 0, rs, 0))
        if op == "jal" and len(args) == 1:
            target = parse_imm(args[0], self.labels, addr)
            offset = target - addr
            return struct.pack("<I", encode_j(0x6F, 1, offset)) # jal ra, target
        if op == "call":
            target = parse_imm(args[0], self.labels, addr)
            offset = target - addr
            hi = (offset + 0x800) >> 12
            lo = (offset & 0xFFF) if not (offset & 0x800) else (offset & 0xFFF) - 0x1000
            i1 = encode_u(0x17, 1, hi << 12) # auipc ra, hi
            i2 = encode_i(0x67, 0x0, 1, 1, lo) # jalr ra, ra, lo
            return struct.pack("<II", i1, i2)
        if op == "li":
            rd = parse_reg(args[0])
            imm = parse_imm(args[1], self.labels, addr)
            hi = (imm + 0x800) >> 12
            lo = (imm & 0xFFF) if not (imm & 0x800) else (imm & 0xFFF) - 0x1000
            i1 = encode_u(0x37, rd, hi << 12) # lui rd, hi
            i2 = encode_i(0x13, 0x0, rd, rd, lo) # addi rd, rd, lo
            return struct.pack("<II", i1, i2)
        if op == "la":
            rd = parse_reg(args[0])
            target = parse_imm(args[1], self.labels, addr)
            hi = (target + 0x800) >> 12
            lo = (target & 0xFFF) if not (target & 0x800) else (target & 0xFFF) - 0x1000
            i1 = encode_u(0x37, rd, hi << 12)
            i2 = encode_i(0x13, 0x0, rd, rd, lo)
            return struct.pack("<II", i1, i2)

        # Base Instructions
        if op == "lui":
            rd = parse_reg(args[0])
            imm = parse_imm(args[1], self.labels, addr)
            return struct.pack("<I", encode_u(0x37, rd, imm))
        if op == "auipc":
            rd = parse_reg(args[0])
            imm = parse_imm(args[1], self.labels, addr)
            return struct.pack("<I", encode_u(0x17, rd, imm))
        if op == "jal":
            rd = parse_reg(args[0])
            target = parse_imm(args[1], self.labels, addr)
            return struct.pack("<I", encode_j(0x6F, rd, target - addr))
        if op == "jalr":
            rd = parse_reg(args[0])
            if '(' in args[1]:
                m = re.match(r'([-\w%()]+)\(([\w]+)\)', args[1])
                imm = parse_imm(m.group(1), self.labels, addr)
                rs1 = parse_reg(m.group(2))
            else:
                rs1 = parse_reg(args[1])
                imm = parse_imm(args[2], self.labels, addr) if len(args) > 2 else 0
            return struct.pack("<I", encode_i(0x67, 0x0, rd, rs1, imm))

        # Branches
        branches = {"beq": 0x0, "bne": 0x1, "blt": 0x4, "bge": 0x5, "bltu": 0x6, "bgeu": 0x7}
        if op in branches:
            rs1 = parse_reg(args[0])
            rs2 = parse_reg(args[1])
            target = parse_imm(args[2], self.labels, addr)
            return struct.pack("<I", encode_b(0x63, branches[op], rs1, rs2, target - addr))

        # Loads
        loads = {"lb": 0x0, "lh": 0x1, "lw": 0x2, "lbu": 0x4, "lhu": 0x5}
        if op in loads:
            rd = parse_reg(args[0])
            m = re.match(r'([-\w%()]+)\(([\w]+)\)', args[1])
            imm = parse_imm(m.group(1), self.labels, addr) if m else 0
            rs1 = parse_reg(m.group(2)) if m else parse_reg(args[1])
            return struct.pack("<I", encode_i(0x03, loads[op], rd, rs1, imm))

        # Stores
        stores = {"sb": 0x0, "sh": 0x1, "sw": 0x2}
        if op in stores:
            rs2 = parse_reg(args[0])
            m = re.match(r'([-\w%()]+)\(([\w]+)\)', args[1])
            imm = parse_imm(m.group(1), self.labels, addr) if m else 0
            rs1 = parse_reg(m.group(2)) if m else parse_reg(args[1])
            return struct.pack("<I", encode_s(0x23, stores[op], rs1, rs2, imm))

        # ALU Imm
        alu_imm = {
            "addi": 0x0, "slli": 0x1, "slti": 0x2, "sltiu": 0x3,
            "xori": 0x4, "srli": 0x5, "srai": 0x5, "ori": 0x6, "andi": 0x7
        }
        if op in alu_imm:
            rd = parse_reg(args[0])
            rs1 = parse_reg(args[1])
            imm = parse_imm(args[2], self.labels, addr)
            funct3 = alu_imm[op]
            if op == "srai":
                imm = (imm & 0x1F) | 0x400
            elif op in ["slli", "srli"]:
                imm = imm & 0x1F
            return struct.pack("<I", encode_i(0x13, funct3, rd, rs1, imm))

        # ALU Reg
        alu_reg = {
            "add": (0x0, 0x00), "sub": (0x0, 0x20), "sll": (0x1, 0x00),
            "slt": (0x2, 0x00), "sltu": (0x3, 0x00), "xor": (0x4, 0x00),
            "srl": (0x5, 0x00), "sra": (0x5, 0x20), "or": (0x6, 0x00), "and": (0x7, 0x00),
            "mul": (0x0, 0x01), "mulh": (0x1, 0x01), "mulhsu": (0x2, 0x01), "mulhu": (0x3, 0x01),
            "div": (0x4, 0x01), "divu": (0x5, 0x01), "rem": (0x6, 0x01), "remu": (0x7, 0x01)
        }
        if op in alu_reg:
            rd = parse_reg(args[0])
            rs1 = parse_reg(args[1])
            rs2 = parse_reg(args[2])
            f3, f7 = alu_reg[op]
            return struct.pack("<I", encode_r(0x33, f3, f7, rd, rs1, rs2))

        # System / CSR
        if op == "ecall":
            return struct.pack("<I", 0x00000073)
        if op == "ebreak":
            return struct.pack("<I", 0x00100073)
        if op == "mret":
            return struct.pack("<I", 0x30200073)
        if op == "wfi":
            return struct.pack("<I", 0x10500073)

        # CSR instructions
        csrs = {
            "csrrw": 0x1, "csrrs": 0x2, "csrrc": 0x3,
            "csrw": 0x1, "csrs": 0x2, "csrc": 0x3, "csrr": 0x2
        }
        if op in csrs:
            if op == "csrw":
                csr = parse_csr(args[0])
                rs = parse_reg(args[1])
                return struct.pack("<I", encode_i(0x73, 0x1, 0, rs, csr))
            elif op in ["csrs", "csrc"]:
                csr = parse_csr(args[0])
                rs = parse_reg(args[1])
                funct3 = 0x2 if op == "csrs" else 0x3
                return struct.pack("<I", encode_i(0x73, funct3, 0, rs, csr))
            elif op == "csrr":
                rd = parse_reg(args[0])
                csr = parse_csr(args[1])
                return struct.pack("<I", encode_i(0x73, 0x2, rd, 0, csr)) # csrrs rd, csr, x0
            else:
                rd = parse_reg(args[0])
                csr = parse_csr(args[1])
                rs1 = parse_reg(args[2])
                return struct.pack("<I", encode_i(0x73, csrs[op], rd, rs1, csr))

        raise ValueError(f"Unknown instruction '{op}' at address 0x{addr:08X}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python assembler.py <input.s> <output.bin>")
        sys.exit(1)
    asmb = Assembler()
    asmb.assemble_file(sys.argv[1], sys.argv[2])
