#!/usr/bin/env python3
"""
AdiOS Simulation Layer - Pure Python RV32I/M Virtual Machine
Runs anywhere without dependencies.
"""

import sys
import time
import struct
import os

RAM_BASE = 0x80000000
RAM_SIZE = 32 * 1024 * 1024  # 32 MB

UART_BASE   = 0x10000000
UART_DATA   = 0x10000000
UART_STATUS = 0x10000004

TIMER_BASE    = 0x10000010
TIMER_TIME    = 0x10000010
TIMER_TIMECMP = 0x10000018

POWER_BASE  = 0x10000040

CSR_MSTATUS  = 0x300
CSR_MIE      = 0x304
CSR_MTVEC    = 0x305
CSR_MSCRATCH = 0x340
CSR_MEPC     = 0x341
CSR_MCAUSE   = 0x342
CSR_MIP      = 0x344

CAUSE_TIMER_INT  = 0x80000007
CAUSE_MACH_ECALL = 11

def sign_extend(val, bits):
    sign_bit = 1 << (bits - 1)
    return (val & (sign_bit - 1)) - (val & sign_bit)

class VM:
    def __init__(self, ram_size=RAM_SIZE):
        self.ram = bytearray(ram_size)
        self.regs = [0] * 32
        self.pc = RAM_BASE
        
        # CSRs
        self.mstatus = 0
        self.mie = 0
        self.mtvec = 0
        self.mscratch = 0
        self.mepc = 0
        self.mcause = 0
        self.mip = 0

        self.timer_time = 0
        self.timer_cmp = 0xFFFFFFFFFFFFFFFF
        self.running = True
        self.input_buffer = []

    def load_binary(self, filename, addr=RAM_BASE):
        with open(filename, "rb") as f:
            data = f.read()
        offset = addr - RAM_BASE
        self.ram[offset:offset+len(data)] = data
        return len(data)

    def push_input(self, char_code):
        self.input_buffer.append(char_code)

    def read8(self, addr):
        if RAM_BASE <= addr < RAM_BASE + len(self.ram):
            return self.ram[addr - RAM_BASE]
        if addr == UART_DATA:
            return self.input_buffer.pop(0) if self.input_buffer else 0
        if addr == UART_STATUS:
            status = 0x02  # Tx ready
            if self.input_buffer:
                status |= 0x01  # Rx ready
            return status
        return 0

    def read16(self, addr):
        return self.read8(addr) | (self.read8(addr + 1) << 8)

    def read32(self, addr):
        if RAM_BASE <= addr <= RAM_BASE + len(self.ram) - 4:
            offset = addr - RAM_BASE
            return struct.unpack_from("<I", self.ram, offset)[0]
        if addr == UART_DATA:
            return self.input_buffer.pop(0) if self.input_buffer else 0
        if addr == UART_STATUS:
            status = 0x02
            if self.input_buffer: status |= 0x01
            return status
        if addr == TIMER_TIME:
            return self.timer_time & 0xFFFFFFFF
        if addr == TIMER_TIME + 4:
            return (self.timer_time >> 32) & 0xFFFFFFFF
        if addr == TIMER_TIMECMP:
            return self.timer_cmp & 0xFFFFFFFF
        if addr == TIMER_TIMECMP + 4:
            return (self.timer_cmp >> 32) & 0xFFFFFFFF
        return 0

    def write8(self, addr, val):
        val &= 0xFF
        if RAM_BASE <= addr < RAM_BASE + len(self.ram):
            self.ram[addr - RAM_BASE] = val
            return
        if addr == UART_DATA:
            sys.stdout.write(chr(val))
            sys.stdout.flush()
            return
        if addr == POWER_BASE:
            if val == 1:
                print("\n[AdiOS VM] Poweroff signal received. Halting.")
                self.running = False
            elif val == 2:
                print("\n[AdiOS VM] Rebooting...")
                self.pc = RAM_BASE

    def write16(self, addr, val):
        self.write8(addr, val & 0xFF)
        self.write8(addr + 1, (val >> 8) & 0xFF)

    def write32(self, addr, val):
        val &= 0xFFFFFFFF
        if RAM_BASE <= addr <= RAM_BASE + len(self.ram) - 4:
            offset = addr - RAM_BASE
            struct.pack_into("<I", self.ram, offset, val)
            return
        if addr == UART_DATA:
            sys.stdout.write(chr(val & 0xFF))
            sys.stdout.flush()
            return
        if addr == TIMER_TIME:
            self.timer_time = (self.timer_time & 0xFFFFFFFF00000000) | val
            return
        if addr == TIMER_TIME + 4:
            self.timer_time = (self.timer_time & 0x00000000FFFFFFFF) | (val << 32)
            return
        if addr == TIMER_TIMECMP:
            self.timer_cmp = (self.timer_cmp & 0xFFFFFFFF00000000) | val
            return
        if addr == TIMER_TIMECMP + 4:
            self.timer_cmp = (self.timer_cmp & 0x00000000FFFFFFFF) | (val << 32)
            return
        if addr == POWER_BASE:
            self.write8(addr, val & 0xFF)

    def csr_read(self, csr):
        if csr == CSR_MSTATUS:  return self.mstatus
        if csr == CSR_MIE:      return self.mie
        if csr == CSR_MTVEC:    return self.mtvec
        if csr == CSR_MSCRATCH: return self.mscratch
        if csr == CSR_MEPC:     return self.mepc
        if csr == CSR_MCAUSE:   return self.mcause
        if csr == CSR_MIP:      return self.mip
        return 0

    def csr_write(self, csr, val):
        val &= 0xFFFFFFFF
        if csr == CSR_MSTATUS:   self.mstatus = val
        elif csr == CSR_MIE:     self.mie = val
        elif csr == CSR_MTVEC:   self.mtvec = val
        elif csr == CSR_MSCRATCH: self.mscratch = val
        elif csr == CSR_MEPC:    self.mepc = val
        elif csr == CSR_MCAUSE:  self.mcause = val
        elif csr == CSR_MIP:     self.mip = val

    def raise_trap(self, cause, epc):
        self.mepc = epc & 0xFFFFFFFF
        self.mcause = cause & 0xFFFFFFFF
        mie_bit = bool(self.mstatus & (1 << 3))
        self.mstatus &= ~(1 << 3)
        if mie_bit:
            self.mstatus |= (1 << 7)
        else:
            self.mstatus &= ~(1 << 7)
        self.pc = self.mtvec

    def step(self):
        if not self.running: return False

        self.timer_time += 1
        if self.timer_time >= self.timer_cmp:
            self.mip |= (1 << 7)
        else:
            self.mip &= ~(1 << 7)

        if (self.mstatus & (1 << 3)) and (self.mie & (1 << 7)) and (self.mip & (1 << 7)):
            self.raise_trap(CAUSE_TIMER_INT, self.pc)

        inst = self.read32(self.pc)
        pc = self.pc
        self.pc = (self.pc + 4) & 0xFFFFFFFF

        opcode = inst & 0x7F
        rd     = (inst >> 7) & 0x1F
        funct3 = (inst >> 12) & 0x07
        rs1    = (inst >> 15) & 0x1F
        rs2    = (inst >> 20) & 0x1F
        funct7 = (inst >> 25) & 0x7F

        r = self.regs

        if opcode == 0x37:  # LUI
            r[rd] = (inst & 0xFFFFF000)
        elif opcode == 0x17:  # AUIPC
            r[rd] = (pc + (inst & 0xFFFFF000)) & 0xFFFFFFFF
        elif opcode == 0x6F:  # JAL
            imm = sign_extend(
                ((inst >> 31) << 20) |
                (((inst >> 21) & 0x3FF) << 1) |
                (((inst >> 20) & 0x1) << 11) |
                (((inst >> 12) & 0xFF) << 12), 21)
            if rd != 0: r[rd] = self.pc
            self.pc = (pc + imm) & 0xFFFFFFFF
        elif opcode == 0x67:  # JALR
            imm = sign_extend(inst >> 20, 12)
            target = (r[rs1] + imm) & ~1
            if rd != 0: r[rd] = self.pc
            self.pc = target & 0xFFFFFFFF
        elif opcode == 0x63:  # Branch
            imm = sign_extend(
                ((inst >> 31) << 12) |
                (((inst >> 25) & 0x3F) << 5) |
                (((inst >> 8) & 0x0F) << 1) |
                (((inst >> 7) & 0x01) << 11), 13)
            take = False
            s_rs1 = struct.unpack("i", struct.pack("I", r[rs1]))[0]
            s_rs2 = struct.unpack("i", struct.pack("I", r[rs2]))[0]
            if funct3 == 0x0:   take = (r[rs1] == r[rs2])  # BEQ
            elif funct3 == 0x1: take = (r[rs1] != r[rs2])  # BNE
            elif funct3 == 0x4: take = (s_rs1 < s_rs2)      # BLT
            elif funct3 == 0x5: take = (s_rs1 >= s_rs2)     # BGE
            elif funct3 == 0x6: take = (r[rs1] < r[rs2])    # BLTU
            elif funct3 == 0x7: take = (r[rs1] >= r[rs2])   # BGEU
            if take:
                self.pc = (pc + imm) & 0xFFFFFFFF
        elif opcode == 0x03:  # Load
            imm = sign_extend(inst >> 20, 12)
            addr = (r[rs1] + imm) & 0xFFFFFFFF
            if funct3 == 0x0:   r[rd] = struct.unpack("b", bytes([self.read8(addr)]))[0] & 0xFFFFFFFF
            elif funct3 == 0x1: r[rd] = struct.unpack("<h", struct.pack("<H", self.read16(addr)))[0] & 0xFFFFFFFF
            elif funct3 == 0x2: r[rd] = self.read32(addr)
            elif funct3 == 0x4: r[rd] = self.read8(addr)
            elif funct3 == 0x5: r[rd] = self.read16(addr)
        elif opcode == 0x23:  # Store
            imm = sign_extend(((inst >> 25) << 5) | ((inst >> 7) & 0x1F), 12)
            addr = (r[rs1] + imm) & 0xFFFFFFFF
            if funct3 == 0x0:   self.write8(addr, r[rs2])
            elif funct3 == 0x1: self.write16(addr, r[rs2])
            elif funct3 == 0x2: self.write32(addr, r[rs2])
        elif opcode == 0x13:  # ALU Imm
            imm = sign_extend(inst >> 20, 12)
            shamt = (inst >> 20) & 0x1F
            s_rs1 = struct.unpack("i", struct.pack("I", r[rs1]))[0]
            if funct3 == 0x0:   r[rd] = (r[rs1] + imm) & 0xFFFFFFFF
            elif funct3 == 0x2: r[rd] = 1 if s_rs1 < imm else 0
            elif funct3 == 0x3: r[rd] = 1 if r[rs1] < (imm & 0xFFFFFFFF) else 0
            elif funct3 == 0x4: r[rd] = r[rs1] ^ (imm & 0xFFFFFFFF)
            elif funct3 == 0x6: r[rd] = r[rs1] | (imm & 0xFFFFFFFF)
            elif funct3 == 0x7: r[rd] = r[rs1] & (imm & 0xFFFFFFFF)
            elif funct3 == 0x1: r[rd] = (r[rs1] << shamt) & 0xFFFFFFFF
            elif funct3 == 0x5:
                if funct7 & 0x20:
                    r[rd] = (s_rs1 >> shamt) & 0xFFFFFFFF
                else:
                    r[rd] = (r[rs1] >> shamt) & 0xFFFFFFFF
        elif opcode == 0x33:  # ALU Reg
            if funct7 == 0x01:  # RV32M
                s_rs1 = struct.unpack("i", struct.pack("I", r[rs1]))[0]
                s_rs2 = struct.unpack("i", struct.pack("I", r[rs2]))[0]
                if funct3 == 0x0:   r[rd] = (s_rs1 * s_rs2) & 0xFFFFFFFF
                elif funct3 == 0x1: r[rd] = ((s_rs1 * s_rs2) >> 32) & 0xFFFFFFFF
                elif funct3 == 0x4:
                    if s_rs2 == 0: r[rd] = 0xFFFFFFFF
                    elif s_rs1 == -0x80000000 and s_rs2 == -1: r[rd] = 0x80000000
                    else: r[rd] = int(s_rs1 / s_rs2) & 0xFFFFFFFF
                elif funct3 == 0x5:
                    r[rd] = 0xFFFFFFFF if r[rs2] == 0 else int(r[rs1] / r[rs2]) & 0xFFFFFFFF
                elif funct3 == 0x6:
                    r[rd] = s_rs1 if s_rs2 == 0 else (s_rs1 % s_rs2) & 0xFFFFFFFF
                elif funct3 == 0x7:
                    r[rd] = r[rs1] if r[rs2] == 0 else (r[rs1] % r[rs2]) & 0xFFFFFFFF
            else:
                shamt = r[rs2] & 0x1F
                s_rs1 = struct.unpack("i", struct.pack("I", r[rs1]))[0]
                s_rs2 = struct.unpack("i", struct.pack("I", r[rs2]))[0]
                if funct3 == 0x0:
                    if funct7 & 0x20: r[rd] = (r[rs1] - r[rs2]) & 0xFFFFFFFF
                    else:             r[rd] = (r[rs1] + r[rs2]) & 0xFFFFFFFF
                elif funct3 == 0x1:   r[rd] = (r[rs1] << shamt) & 0xFFFFFFFF
                elif funct3 == 0x2:   r[rd] = 1 if s_rs1 < s_rs2 else 0
                elif funct3 == 0x3:   r[rd] = 1 if r[rs1] < r[rs2] else 0
                elif funct3 == 0x4:   r[rd] = r[rs1] ^ r[rs2]
                elif funct3 == 0x5:
                    if funct7 & 0x20: r[rd] = (s_rs1 >> shamt) & 0xFFFFFFFF
                    else:             r[rd] = (r[rs1] >> shamt) & 0xFFFFFFFF
                elif funct3 == 0x6:   r[rd] = r[rs1] | r[rs2]
                elif funct3 == 0x7:   r[rd] = r[rs1] & r[rs2]
        elif opcode == 0x73:  # System / CSR
            csr_addr = inst >> 20
            if funct3 == 0x0:
                if inst == 0x00000073:    # ECALL
                    self.raise_trap(CAUSE_MACH_ECALL, pc)
                elif inst == 0x30200073:  # MRET
                    self.pc = self.mepc
                    mpie = bool(self.mstatus & (1 << 7))
                    if mpie: self.mstatus |= (1 << 3)
                    else:    self.mstatus &= ~(1 << 3)
                    self.mstatus |= (1 << 7)
            else:
                old = self.csr_read(csr_addr)
                wval = rs1 if (funct3 & 0x4) else r[rs1]
                op = funct3 & 0x3
                if op == 1:   self.csr_write(csr_addr, wval)
                elif op == 2: self.csr_write(csr_addr, old | wval)
                elif op == 3: self.csr_write(csr_addr, old & ~wval)
                if rd != 0: r[rd] = old
        else:
            print(f"\n[AdiOS VM] Unknown opcode: 0x{opcode:02X} at PC: 0x{pc:08X}")
            self.running = False
            return False

        r[0] = 0
        return True

def run_interactive(bin_path="adios.bin"):
    vm = VM()
    if not os.path.exists(bin_path):
        print(f"Error: binary '{bin_path}' not found.")
        sys.exit(1)
    
    size = vm.load_binary(bin_path)
    print("=====================================================")
    print("        AdiOS RISC-V Hardware Simulator (RV32IM)     ")
    print("=====================================================")
    print(f"[VM] Loaded {size} bytes into RAM at 0x{RAM_BASE:08X}")
    print("[VM] Virtual RAM: 32 MB | Terminal: MMIO 0x10000000")
    print("[VM] Booting AdiOS...\n")

    import msvcrt
    cycles = 0
    while vm.running:
        if not vm.step():
            break
        cycles += 1
        if (cycles & 0x7FF) == 0:
            while msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch == b'\x03':  # Ctrl+C
                    print("\n[AdiOS VM] Interrupted by host.")
                    return
                if ch == b'\r':
                    ch = b'\n'
                vm.push_input(ord(ch))

    print(f"\n[VM] Stopped. Total cycles: {cycles}")

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "adios.bin"
    run_interactive(path)
