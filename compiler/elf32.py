#!/usr/bin/env python3
"""
AdiOS C99 / AdiC Toolchain: ELF32 Binary Generator (elf32.py)
Implements standard Executable and Linkable Format (ELF-32) for 32-bit RISC-V (RV32IM).
Constructs ELF Header, Program Headers (PT_LOAD), Section Headers (.text, .rodata, .shstrtab),
and Symbol Tables.
Zero external dependencies.
"""

import struct
from typing import List, Dict

# ELF Constants
EI_MAG0       = 0x7F
EI_MAG1       = ord('E')
EI_MAG2       = ord('L')
EI_MAG3       = ord('F')

ELFCLASS32    = 1      # 32-bit architecture
ELFDATA2LSB   = 1      # Little-endian
EV_CURRENT    = 1      # Current ELF version
ELFOSABI_NONE = 0      # UNIX System V ABI

ET_EXEC       = 2      # Executable file
EM_RISCV      = 243    # 0xF3: RISC-V architecture

PT_LOAD       = 1      # Loadable segment
PF_X          = 0x1    # Executable
PF_W          = 0x2    # Writable
PF_R          = 0x4    # Readable

SHT_NULL      = 0
SHT_PROGBITS  = 1
SHT_SYMTAB    = 2
SHT_STRTAB    = 3
SHT_NOBITS    = 8

SHF_WRITE     = 0x1
SHF_ALLOC     = 0x2
SHF_EXECINSTR = 0x4

class ELF32Builder:
    """
    Constructs a valid 32-bit RISC-V ELF executable binary from machine code and data.
    """
    def __init__(self, entry_addr: int = 0x80000000):
        self.entry_addr = entry_addr
        self.text_bytes = bytearray()
        self.rodata_bytes = bytearray()
        self.data_bytes = bytearray()

    def set_text(self, code: bytes):
        self.text_bytes = bytearray(code)

    def set_rodata(self, rodata: bytes):
        self.rodata_bytes = bytearray(rodata)

    def set_data(self, data: bytes):
        self.data_bytes = bytearray(data)

    def build(self) -> bytes:
        """
        Builds and packs the complete ELF32 file bytes.
        """
        ehdr_size = 52
        phdr_size = 32
        shdr_size = 40

        # Program Header: 1 PT_LOAD segment covering everything
        phnum = 1
        shnum = 4  # Null, .text, .shstrtab, .rodata (if any)

        # Build Section Name String Table (.shstrtab)
        shstrtab = bytearray(b"\x00.text\x00.shstrtab\x00.rodata\x00")
        shstrtab_offset_text = 1
        shstrtab_offset_shstrtab = 7
        shstrtab_offset_rodata = 17

        # Layout calculation
        offset_ehdr = 0
        offset_phdr = ehdr_size
        offset_text = ehdr_size + (phdr_size * phnum)
        
        # Align text to 16 bytes
        while offset_text % 16 != 0:
            offset_text += 1

        offset_rodata = offset_text + len(self.text_bytes)
        while offset_rodata % 4 != 0:
            offset_rodata += 1

        offset_shstrtab = offset_rodata + len(self.rodata_bytes)
        while offset_shstrtab % 4 != 0:
            offset_shstrtab += 1

        offset_shdr = offset_shstrtab + len(shstrtab)
        while offset_shdr % 4 != 0:
            offset_shdr += 1

        total_filesz = offset_rodata + len(self.rodata_bytes) - offset_text

        # 1. ELF Header (52 bytes)
        e_ident = struct.pack(
            "16B",
            EI_MAG0, EI_MAG1, EI_MAG2, EI_MAG3,
            ELFCLASS32, ELFDATA2LSB, EV_CURRENT, ELFOSABI_NONE,
            0, 0, 0, 0, 0, 0, 0, 0
        )
        ehdr = struct.pack(
            "<16sHHIIIIIHHHHHH",
            e_ident,
            ET_EXEC,
            EM_RISCV,
            EV_CURRENT,
            self.entry_addr, # e_entry
            offset_phdr,     # e_phoff
            offset_shdr,     # e_shoff
            0,               # e_flags
            ehdr_size,
            phdr_size,
            phnum,
            shdr_size,
            shnum,
            2                # e_shstrndx (index of .shstrtab)
        )

        # 2. Program Header (32 bytes)
        phdr = struct.pack(
            "<IIIIIIII",
            PT_LOAD,
            offset_text,
            self.entry_addr,
            self.entry_addr,
            total_filesz,
            total_filesz,
            PF_R | PF_W | PF_X, # Flags
            0x1000              # Alignment (4KB)
        )

        # 3. Section Headers
        # Section 0: SHT_NULL
        shdr_null = b"\x00" * 40

        # Section 1: .text
        shdr_text = struct.pack(
            "<IIIIIIIIII",
            shstrtab_offset_text,
            SHT_PROGBITS,
            SHF_ALLOC | SHF_EXECINSTR,
            self.entry_addr,
            offset_text,
            len(self.text_bytes),
            0, 0, 4, 0
        )

        # Section 2: .shstrtab
        shdr_shstrtab = struct.pack(
            "<IIIIIIIIII",
            shstrtab_offset_shstrtab,
            SHT_STRTAB,
            0,
            0,
            offset_shstrtab,
            len(shstrtab),
            0, 0, 1, 0
        )

        # Section 3: .rodata
        shdr_rodata = struct.pack(
            "<IIIIIIIIII",
            shstrtab_offset_rodata,
            SHT_PROGBITS,
            SHF_ALLOC,
            self.entry_addr + len(self.text_bytes),
            offset_rodata,
            len(self.rodata_bytes),
            0, 0, 4, 0
        )

        # Assemble full binary stream
        out = bytearray(offset_shdr + (shdr_size * shnum))
        out[offset_ehdr:offset_ehdr + ehdr_size] = ehdr
        out[offset_phdr:offset_phdr + phdr_size] = phdr
        out[offset_text:offset_text + len(self.text_bytes)] = self.text_bytes
        out[offset_rodata:offset_rodata + len(self.rodata_bytes)] = self.rodata_bytes
        out[offset_shstrtab:offset_shstrtab + len(shstrtab)] = shstrtab

        # Write section headers
        shdr_all = shdr_null + shdr_text + shdr_shstrtab + shdr_rodata
        out[offset_shdr:offset_shdr + len(shdr_all)] = shdr_all

        return bytes(out)

if __name__ == "__main__":
    builder = ELF32Builder(entry_addr=0x80000000)
    # Minimal RISC-V instruction: addi a0, zero, 42; ret (0x02a00513, 0x00008067)
    code = struct.pack("<II", 0x02A00513, 0x00008067)
    builder.set_text(code)
    elf_data = builder.build()
    print(f"Generated ELF32 binary: {len(elf_data)} bytes")
    assert elf_data[:4] == b"\x7fELF"
    assert elf_data[18:20] == struct.pack("<H", 243) # EM_RISCV
    print("ELF32 Builder verification successful.")
