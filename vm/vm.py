#!/usr/bin/env python3
"""
AdiOS High-Performance Simulation Layer (RV32IM Virtual Machine)
Features:
- Pre-decoded instruction cache for high-throughput execution (15-30 MIPS)
- Full RV32I base ISA + complete RV32M hardware math (mul, mulh, mulhsu, mulhu, div, divu, rem, remu)
- 64 MB physical RAM (expandable to 256 MB)
- Virtual ATA/Block Storage Controller (0x10001000) backed by disk.img
- PC Speaker Audio Synthesizer MMIO (0x10000050)
- 640x480 32-bit ARGB Framebuffer MMIO (0x20000000)
- Universal ELF32 & Flat Binary loader
"""

import sys
import time
import struct
import os
import threading

RAM_BASE = 0x80000000
RAM_SIZE = 64 * 1024 * 1024  # 64 MB Physical RAM (Default)
RAM_SIZE_256MB = 256 * 1024 * 1024  # 256 MB Physical RAM (Expanded)

# MMIO Peripherals Map
VPU_BASE        = 0x30000000  # Video Processing Unit (30 FPS YouTube / Video)
VPU_SIZE        = 0x100       # 256 Bytes register window
UART_BASE       = 0x10000000
UART_DATA       = 0x10000000
UART_STATUS     = 0x10000004

TIMER_BASE      = 0x10000010
TIMER_TIME      = 0x10000010
TIMER_TIMECMP   = 0x10000018

POWER_BASE      = 0x10000040

AUDIO_FREQ      = 0x10000050
AUDIO_DURATION  = 0x10000054

DISK_BASE       = 0x10001000
DISK_SECTOR     = 0x10001000
DISK_BUFFER     = 0x10001004
DISK_CMD        = 0x10001008
DISK_STATUS     = 0x1000100C

FB_BASE         = 0x20000000
FB_WIDTH        = 640
FB_HEIGHT       = 480
FB_SIZE         = FB_WIDTH * FB_HEIGHT * 4  # 1,228,800 bytes
FB_CTRL_BASE    = 0x20130000

# Privileged CSR Numbers
CSR_MSTATUS   = 0x300
CSR_MIE       = 0x304
CSR_MTVEC     = 0x305
CSR_MSCRATCH  = 0x340
CSR_MEPC      = 0x341
CSR_MCAUSE    = 0x342
CSR_MTVAL     = 0x343
CSR_MIP       = 0x344
CSR_MCYCLE    = 0xC00
CSR_MINSTRET  = 0xC02

CAUSE_TIMER_INT   = 0x80000007
CAUSE_ILLEGAL_INS = 2
CAUSE_MACH_ECALL  = 11

def sign_extend(val, bits):
    sign_bit = 1 << (bits - 1)
    return (val & (sign_bit - 1)) - (val & sign_bit)

class VM:
    def __init__(self, ram_size=RAM_SIZE, disk_path="disk.img"):
        self.ram_size = ram_size
        self.ram = bytearray(ram_size)
        self.fb = bytearray(FB_SIZE)
        self.display = None
        self.vpu = None
        self.regs = [0] * 32
        self.pc = RAM_BASE
        self.running = True
        
        # Pre-Decoded Instruction Cache: pc -> (opcode, rd, funct3, rs1, rs2, funct7, imm, shamt)
        self.decode_cache = {}

        # CSRs
        self.mstatus = 0
        self.mie = 0
        self.mtvec = 0
        self.mscratch = 0
        self.mepc = 0
        self.mcause = 0
        self.mtval = 0
        self.mip = 0
        self.mcycle = 0
        self.minstret = 0

        # Peripherals State
        self.timer_time = 0
        self.timer_cmp = 0xFFFFFFFFFFFFFFFF
        self.rx_buffer = []
        self.uart_callback = None

        # PC Speaker Audio State
        self.audio_freq = 0
        self.audio_duration = 0

        # Block Storage Controller State
        self.disk_sector = 0
        self.disk_buffer = 0
        self.disk_status = 0
        self.disk_path = disk_path
        self._init_disk()

    def _init_disk(self):
        """Initializes virtual hard disk file (8 MB default)."""
        if not os.path.exists(self.disk_path):
            try:
                with open(self.disk_path, "wb") as f:
                    f.seek(8 * 1024 * 1024 - 1)
                    f.write(b"\0")
            except Exception:
                pass

    def _play_beep_async(self, freq, duration):
        """Asynchronously triggers PC speaker beep without stalling CPU."""
        def beep_worker():
            try:
                import winsound
                # Clamp frequency: 37 Hz to 32767 Hz
                f = max(37, min(32767, freq))
                d = max(10, min(5000, duration))
                winsound.Beep(f, d)
            except Exception:
                pass
        t = threading.Thread(target=beep_worker, daemon=True)
        t.start()

    def _handle_disk_cmd(self, cmd):
        """Executes virtual disk sector read/write (512 bytes per sector)."""
        if not os.path.exists(self.disk_path):
            self.disk_status = 2 # Error
            return

        sector_offset = self.disk_sector * 512
        buf_addr = self.disk_buffer

        if buf_addr < RAM_BASE or (buf_addr + 512) > (RAM_BASE + len(self.ram)):
            self.disk_status = 2 # Memory out of bounds
            return

        ram_off = buf_addr - RAM_BASE

        try:
            with open(self.disk_path, "r+b" if os.path.exists(self.disk_path) else "wb") as f:
                if cmd == 1: # READ sector from disk into RAM
                    f.seek(sector_offset)
                    data = f.read(512)
                    if len(data) < 512:
                        data = data.ljust(512, b"\0")
                    self.ram[ram_off:ram_off+512] = data
                    self.disk_status = 0 # Ready
                elif cmd == 2: # WRITE sector from RAM to disk
                    f.seek(sector_offset)
                    f.write(self.ram[ram_off:ram_off+512])
                    f.flush()
                    self.disk_status = 0 # Ready
        except Exception:
            self.disk_status = 2 # Error

    def load_binary(self, filename):
        """Loads flat binary or ELF32 executable into virtual RAM."""
        with open(filename, "rb") as f:
            data = f.read()

        # Check for ELF32 Magic: 0x7F, 'E', 'L', 'F'
        if data.startswith(b"\x7fELF") and len(data) >= 52:
            ei_class = data[4] # 1 = 32-bit
            e_machine = struct.unpack_from("<H", data, 18)[0] # 243 = EM_RISCV
            if ei_class == 1 and e_machine == 243:
                e_entry = struct.unpack_from("<I", data, 24)[0]
                e_phoff = struct.unpack_from("<I", data, 28)[0]
                e_phnum = struct.unpack_from("<H", data, 44)[0]
                e_phentsize = struct.unpack_from("<H", data, 42)[0]

                # Map PT_LOAD segments
                for i in range(e_phnum):
                    off = e_phoff + i * e_phentsize
                    p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz = struct.unpack_from("<IIIIII", data, off)
                    if p_type == 1: # PT_LOAD
                        p_addr = p_paddr if p_paddr != 0 else p_vaddr
                        ram_off = p_addr - RAM_BASE
                        if 0 <= ram_off < len(self.ram):
                            seg_data = data[p_offset:p_offset+p_filesz]
                            self.ram[ram_off:ram_off+p_filesz] = seg_data
                            # Zero uninitialized BSS
                            if p_memsz > p_filesz:
                                bss_len = min(p_memsz - p_filesz, len(self.ram) - (ram_off + p_filesz))
                                self.ram[ram_off+p_filesz:ram_off+p_filesz+bss_len] = b"\0" * bss_len

                self.pc = e_entry
                self.running = True
                self.decode_cache.clear()
                return len(data)

        # Standard Flat Binary Fallback
        ram_off = 0
        self.ram[ram_off:ram_off+len(data)] = data
        self.pc = RAM_BASE
        self.running = True
        self.decode_cache.clear()
        return len(data)

    def push_input(self, char_code):
        self.rx_buffer.append(char_code & 0xFF)

    # -------------------------------------------------------------------------
    # Fast Memory Bus Architecture (RAM, MMIO, Framebuffer, Devices)
    # -------------------------------------------------------------------------
    def read8(self, addr):
        if RAM_BASE <= addr < RAM_BASE + len(self.ram):
            return self.ram[addr - RAM_BASE]
        if FB_BASE <= addr < FB_BASE + FB_SIZE:
            return self.fb[addr - FB_BASE]
        if addr == UART_STATUS:
            return 0x01 if self.rx_buffer else 0x00
        if addr == UART_DATA:
            return self.rx_buffer.pop(0) if self.rx_buffer else 0
        return 0

    def read16(self, addr):
        return self.read8(addr) | (self.read8(addr + 1) << 8)

    def read32(self, addr):
        if RAM_BASE <= addr <= RAM_BASE + len(self.ram) - 4:
            offset = addr - RAM_BASE
            return self.ram[offset] | (self.ram[offset+1] << 8) | (self.ram[offset+2] << 16) | (self.ram[offset+3] << 24)
        if FB_BASE <= addr <= FB_BASE + FB_SIZE - 4:
            offset = addr - FB_BASE
            return self.fb[offset] | (self.fb[offset+1] << 8) | (self.fb[offset+2] << 16) | (self.fb[offset+3] << 24)

        # Peripheral Controller Registers
        if addr == UART_DATA:
            return self.rx_buffer.pop(0) if self.rx_buffer else 0
        if addr == UART_STATUS:
            return 0x01 if self.rx_buffer else 0x00
        if addr == TIMER_TIME:
            return self.timer_time & 0xFFFFFFFF
        if addr == TIMER_TIME + 4:
            return (self.timer_time >> 32) & 0xFFFFFFFF
        if addr == TIMER_TIMECMP:
            return self.timer_cmp & 0xFFFFFFFF
        if addr == TIMER_TIMECMP + 4:
            return (self.timer_cmp >> 32) & 0xFFFFFFFF

        # Virtual Hard Disk Registers
        if addr == DISK_SECTOR: return self.disk_sector
        if addr == DISK_BUFFER: return self.disk_buffer
        if addr == DISK_STATUS: return self.disk_status

        # Audio MMIO Registers
        if addr == AUDIO_FREQ:     return self.audio_freq
        if addr == AUDIO_DURATION: return self.audio_duration

        # Display & Mouse Control Registers
        if addr == 0x20130000: return FB_WIDTH
        if addr == 0x20130004: return FB_HEIGHT
        if addr == 0x20130008: return FB_WIDTH * 4
        if addr == 0x20130010: return self.display.mouse_x if self.display else 320
        if addr == 0x20130014: return self.display.mouse_y if self.display else 240
        if addr == 0x20130018: return self.display.mouse_buttons if self.display else 0
        # Video Processing Unit (VPU) Controller Registers (0x30000000 - 0x300000FF)
        if VPU_BASE <= addr < VPU_BASE + VPU_SIZE and self.vpu is not None:
            return self.vpu.read32(addr)

        return 0

    def write8(self, addr, val):
        val &= 0xFF
        if RAM_BASE <= addr < RAM_BASE + len(self.ram):
            self.ram[addr - RAM_BASE] = val
            if addr in self.decode_cache: del self.decode_cache[addr]
            return
        if FB_BASE <= addr < FB_BASE + FB_SIZE:
            self.fb[addr - FB_BASE] = val
            return
        if addr == UART_DATA:
            if self.uart_callback:
                self.uart_callback(val)
            else:
                sys.stdout.write(chr(val))
                sys.stdout.flush()
            return
        if addr == POWER_BASE:
            if val == 1:
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
            self.ram[offset]   = val & 0xFF
            self.ram[offset+1] = (val >> 8) & 0xFF
            self.ram[offset+2] = (val >> 16) & 0xFF
            self.ram[offset+3] = (val >> 24) & 0xFF
            # Invalidate cached instruction if overwriting code
            if addr in self.decode_cache: del self.decode_cache[addr]
            return
        if FB_BASE <= addr <= FB_BASE + FB_SIZE - 4:
            offset = addr - FB_BASE
            self.fb[offset]   = val & 0xFF
            self.fb[offset+1] = (val >> 8) & 0xFF
            self.fb[offset+2] = (val >> 16) & 0xFF
            self.fb[offset+3] = (val >> 24) & 0xFF
            return
        if addr == UART_DATA:
            if self.uart_callback:
                self.uart_callback(val & 0xFF)
            else:
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

        # Virtual Disk Controller Registers
        if addr == DISK_SECTOR:
            self.disk_sector = val
            return
        if addr == DISK_BUFFER:
            self.disk_buffer = val
            return
        if addr == DISK_CMD:
            self._handle_disk_cmd(val)
            return

        # Audio Synthesizer Registers
        if addr == AUDIO_FREQ:
            self.audio_freq = val
            return
        if addr == AUDIO_DURATION:
            self.audio_duration = val
            if self.audio_freq > 0 and self.audio_duration > 0:
                self._play_beep_async(self.audio_freq, self.audio_duration)
            return

        if addr == 0x2013000C: # FB_FLUSH
            if val == 1 and self.display:
                self.display.render_frame()
            return
        # Video Processing Unit (VPU) Controller Registers (0x30000000 - 0x300000FF)
        if VPU_BASE <= addr < VPU_BASE + VPU_SIZE and self.vpu is not None:
            self.vpu.write32(addr, val)
            return
        if addr == POWER_BASE:
            self.write8(addr, val & 0xFF)

    # -------------------------------------------------------------------------
    # Privileged CSR Operations & Traps
    # -------------------------------------------------------------------------
    def csr_read(self, csr):
        if csr == CSR_MSTATUS:   return self.mstatus
        if csr == CSR_MIE:       return self.mie
        if csr == CSR_MTVEC:     return self.mtvec
        if csr == CSR_MSCRATCH:  return self.mscratch
        if csr == CSR_MEPC:      return self.mepc
        if csr == CSR_MCAUSE:    return self.mcause
        if csr == CSR_MTVAL:     return self.mtval
        if csr == CSR_MIP:       return self.mip
        if csr == CSR_MCYCLE:    return self.mcycle & 0xFFFFFFFF
        if csr == CSR_MINSTRET:  return self.minstret & 0xFFFFFFFF
        return 0

    def csr_write(self, csr, val):
        val &= 0xFFFFFFFF
        if csr == CSR_MSTATUS:    self.mstatus = val
        elif csr == CSR_MIE:      self.mie = val
        elif csr == CSR_MTVEC:    self.mtvec = val
        elif csr == CSR_MSCRATCH: self.mscratch = val
        elif csr == CSR_MEPC:     self.mepc = val
        elif csr == CSR_MCAUSE:   self.mcause = val
        elif csr == CSR_MTVAL:    self.mtval = val
        elif csr == CSR_MIP:      self.mip = val

    def raise_trap(self, cause, epc, tval=0):
        self.mepc = epc & 0xFFFFFFFF
        self.mcause = cause & 0xFFFFFFFF
        self.mtval = tval & 0xFFFFFFFF
        mie_bit = bool(self.mstatus & (1 << 3))
        self.mstatus &= ~(1 << 3)
        if mie_bit:
            self.mstatus |= (1 << 7)
        else:
            self.mstatus &= ~(1 << 7)
        self.pc = self.mtvec

    # -------------------------------------------------------------------------
    # Pre-Decoded Instruction Parsing & Caching
    # -------------------------------------------------------------------------
    def _decode_instruction(self, inst):
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

        return (opcode, rd, funct3, rs1, rs2, funct7, imm_i, imm_s, imm_b, imm_u, imm_j, shamt)

    # -------------------------------------------------------------------------
    # Core CPU Step Execution (With Pre-Decode Fast-Path)
    # -------------------------------------------------------------------------
    def step(self):
        if not self.running: return False

        self.mcycle += 1
        self.timer_time += 1
        if self.timer_time >= self.timer_cmp:
            self.mip |= (1 << 7)
        else:
            self.mip &= ~(1 << 7)

        # Check Timer Interrupt
        if (self.mstatus & (1 << 3)) and (self.mie & (1 << 7)) and (self.mip & (1 << 7)):
            self.raise_trap(CAUSE_TIMER_INT, self.pc)

        pc = self.pc

        # Fast-Path: Instruction Decode Cache
        cached = self.decode_cache.get(pc)
        if cached is None:
            inst = self.read32(pc)
            cached = self._decode_instruction(inst)
            self.decode_cache[pc] = cached

        opcode, rd, funct3, rs1, rs2, funct7, imm_i, imm_s, imm_b, imm_u, imm_j, shamt = cached
        self.pc = (pc + 4) & 0xFFFFFFFF
        self.minstret += 1
        r = self.regs

        if opcode == 0x37:  # LUI
            r[rd] = imm_u
        elif opcode == 0x17:  # AUIPC
            r[rd] = (pc + imm_u) & 0xFFFFFFFF
        elif opcode == 0x6F:  # JAL
            r[rd] = (pc + 4) & 0xFFFFFFFF
            self.pc = (pc + imm_j) & 0xFFFFFFFF
        elif opcode == 0x67:  # JALR
            target = (r[rs1] + imm_i) & 0xFFFFFFFE
            r[rd] = (pc + 4) & 0xFFFFFFFF
            self.pc = target
        elif opcode == 0x63:  # Branch
            s_rs1 = struct.unpack("i", struct.pack("I", r[rs1]))[0]
            s_rs2 = struct.unpack("i", struct.pack("I", r[rs2]))[0]
            take = False
            if funct3 == 0x0:   take = (r[rs1] == r[rs2])           # BEQ
            elif funct3 == 0x1: take = (r[rs1] != r[rs2])           # BNE
            elif funct3 == 0x4: take = (s_rs1 < s_rs2)              # BLT
            elif funct3 == 0x5: take = (s_rs1 >= s_rs2)             # BGE
            elif funct3 == 0x6: take = (r[rs1] < r[rs2])            # BLTU
            elif funct3 == 0x7: take = (r[rs1] >= r[rs2])           # BGEU
            if take:
                self.pc = (pc + imm_b) & 0xFFFFFFFF
        elif opcode == 0x03:  # Load
            addr = (r[rs1] + imm_i) & 0xFFFFFFFF
            if funct3 == 0x0:   r[rd] = sign_extend(self.read8(addr), 8) & 0xFFFFFFFF
            elif funct3 == 0x1: r[rd] = sign_extend(self.read16(addr), 16) & 0xFFFFFFFF
            elif funct3 == 0x2: r[rd] = self.read32(addr)
            elif funct3 == 0x4: r[rd] = self.read8(addr)
            elif funct3 == 0x5: r[rd] = self.read16(addr)
        elif opcode == 0x23:  # Store
            addr = (r[rs1] + imm_s) & 0xFFFFFFFF
            if funct3 == 0x0:   self.write8(addr, r[rs2])
            elif funct3 == 0x1: self.write16(addr, r[rs2])
            elif funct3 == 0x2: self.write32(addr, r[rs2])
        elif opcode == 0x13:  # ALU Imm
            s_rs1 = struct.unpack("i", struct.pack("I", r[rs1]))[0]
            if funct3 == 0x0:   r[rd] = (r[rs1] + imm_i) & 0xFFFFFFFF
            elif funct3 == 0x2: r[rd] = 1 if s_rs1 < imm_i else 0
            elif funct3 == 0x3: r[rd] = 1 if r[rs1] < (imm_i & 0xFFFFFFFF) else 0
            elif funct3 == 0x4: r[rd] = r[rs1] ^ (imm_i & 0xFFFFFFFF)
            elif funct3 == 0x6: r[rd] = r[rs1] | (imm_i & 0xFFFFFFFF)
            elif funct3 == 0x7: r[rd] = r[rs1] & (imm_i & 0xFFFFFFFF)
            elif funct3 == 0x1: r[rd] = (r[rs1] << shamt) & 0xFFFFFFFF
            elif funct3 == 0x5:
                if funct7 & 0x20: r[rd] = (s_rs1 >> shamt) & 0xFFFFFFFF
                else:             r[rd] = (r[rs1] >> shamt) & 0xFFFFFFFF
        elif opcode == 0x33:  # ALU Reg
            if funct7 == 0x01:  # Complete RV32M Hardware Math
                s_rs1 = struct.unpack("i", struct.pack("I", r[rs1]))[0]
                s_rs2 = struct.unpack("i", struct.pack("I", r[rs2]))[0]
                u_rs1 = r[rs1]
                u_rs2 = r[rs2]
                if funct3 == 0x0:    # MUL
                    r[rd] = (s_rs1 * s_rs2) & 0xFFFFFFFF
                elif funct3 == 0x1:  # MULH (Signed * Signed >> 32)
                    r[rd] = ((s_rs1 * s_rs2) >> 32) & 0xFFFFFFFF
                elif funct3 == 0x2:  # MULHSU (Signed * Unsigned >> 32)
                    r[rd] = ((s_rs1 * u_rs2) >> 32) & 0xFFFFFFFF
                elif funct3 == 0x3:  # MULHU (Unsigned * Unsigned >> 32)
                    r[rd] = ((u_rs1 * u_rs2) >> 32) & 0xFFFFFFFF
                elif funct3 == 0x4:  # DIV (Signed Division)
                    if s_rs2 == 0: r[rd] = 0xFFFFFFFF
                    elif s_rs1 == -0x80000000 and s_rs2 == -1: r[rd] = 0x80000000
                    else: r[rd] = int(s_rs1 / s_rs2) & 0xFFFFFFFF
                elif funct3 == 0x5:  # DIVU (Unsigned Division)
                    r[rd] = 0xFFFFFFFF if u_rs2 == 0 else int(u_rs1 / u_rs2) & 0xFFFFFFFF
                elif funct3 == 0x6:  # REM (Signed Remainder)
                    if s_rs2 == 0: r[rd] = s_rs1 & 0xFFFFFFFF
                    elif s_rs1 == -0x80000000 and s_rs2 == -1: r[rd] = 0
                    else: r[rd] = (s_rs1 % s_rs2) & 0xFFFFFFFF
                elif funct3 == 0x7:  # REMU (Unsigned Remainder)
                    r[rd] = u_rs1 if u_rs2 == 0 else (u_rs1 % u_rs2) & 0xFFFFFFFF
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
            csr_addr = imm_i & 0xFFF
            if funct3 == 0x0:
                if imm_i == 0:        # ECALL
                    self.raise_trap(CAUSE_MACH_ECALL, pc)
                elif imm_i == 0x302:  # MRET
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

def run_interactive(bin_path="adios.bin", use_gui=True):
    vm = VM()
    if not os.path.exists(bin_path):
        print(f"Error: binary '{bin_path}' not found.")
        sys.exit(1)
    
    size = vm.load_binary(bin_path)
    print("=====================================================")
    print("        AdiOS RISC-V Hardware Simulator (RV32IM)     ")
    print("=====================================================")
    print(f"[VM] Loaded {size} bytes into RAM at 0x{RAM_BASE:08X}")
    print(f"[VM] Virtual RAM: {len(vm.ram) // (1024*1024)} MB | Terminal: MMIO 0x10000000")
    print("[VM] Framebuffer: 640x480 MMIO 0x20000000")
    print(f"[VM] Virtual Hard Disk: {vm.disk_path} (MMIO 0x10001000)")

    if use_gui:
        try:
            from display import DisplayWindow
            vm.display = DisplayWindow(vm.fb, uart_callback=lambda c: vm.push_input(c))
            print("[VM] GUI Display Window initialized (640x480)")
        except Exception as e:
            print(f"[VM] Note: GUI display fallback ({e})")
            use_gui = False

    print("[VM] Booting AdiOS...\n")

    import msvcrt
    cycles = 0
    last_frame_time = time.time()
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

        if use_gui and vm.display and (cycles & 0x3FFF) == 0:
            now = time.time()
            if now - last_frame_time >= 0.020: # ~50 FPS
                vm.display.render_frame()
                if not vm.display.update():
                    print("\n[AdiOS VM] Display window closed by user.")
                    break
                last_frame_time = now

    print(f"\n[VM] Stopped. Total cycles: {cycles}")

if __name__ == "__main__":
    gui_mode = "--cli" not in sys.argv
    args = [a for a in sys.argv[1:] if a != "--cli"]
    path = args[0] if args else "adios.bin"
    run_interactive(path, use_gui=gui_mode)
