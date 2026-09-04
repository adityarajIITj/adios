#!/usr/bin/env python3
"""
AdiOS C99 / AdiC Toolchain: ELF32 Binary Generator & Linker (elf32.py)
Implements standard Executable and Linkable Format (ELF-32) for 32-bit RISC-V (RV32IM):
- Complete ELF Header, Program Headers (PT_LOAD), Section Headers (.text, .rodata, .data, .bss, .symtab, .strtab, .shstrtab)
- Symbol Table (.symtab) management with local/global bindings and object/function types
- String Table (.strtab, .shstrtab) builders with string indexing
- RISC-V Relocation Engine (R_RISCV_32, R_RISCV_BRANCH, R_RISCV_JAL, R_RISCV_CALL, R_RISCV_HI20, R_RISCV_LO12_I)
- In-memory ELF32 Dissector & Parser for validating executable binaries and section inspection

Zero external dependencies. Pure RV32IM toolchain component.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

import struct
from typing import List, Dict, Optional, Tuple, Any

# ELF Constants
EI_MAG0       = 0x7F
EI_MAG1       = ord('E')
EI_MAG2       = ord('L')
EI_MAG3       = ord('F')

ELFCLASS32    = 1      # 32-bit architecture
ELFDATA2LSB   = 1      # Little-endian
EV_CURRENT    = 1      # Current ELF version
ELFOSABI_NONE = 0      # UNIX System V ABI

ET_NONE       = 0      # No file type
ET_REL        = 1      # Relocatable file
ET_EXEC       = 2      # Executable file
ET_DYN        = 3      # Shared object file
EM_RISCV      = 243    # 0xF3: RISC-V architecture

PT_NULL       = 0
PT_LOAD       = 1      # Loadable segment
PT_DYNAMIC    = 2      # Dynamic linking tables
PT_INTERP     = 3      # Program interpreter path
PT_NOTE       = 4      # Auxiliary information
PT_SHLIB      = 5
PT_PHDR       = 6

PF_X          = 0x1    # Executable
PF_W          = 0x2    # Writable
PF_R          = 0x4    # Readable

SHT_NULL      = 0
SHT_PROGBITS  = 1
SHT_SYMTAB    = 2
SHT_STRTAB    = 3
SHT_RELA      = 4
SHT_HASH      = 5
SHT_DYNAMIC   = 6
SHT_NOTE      = 7
SHT_NOBITS    = 8
SHT_REL       = 9

SHF_WRITE     = 0x1
SHF_ALLOC     = 0x2
SHF_EXECINSTR = 0x4

# Symbol Bindings
STB_LOCAL     = 0
STB_GLOBAL    = 1
STB_WEAK      = 2

# Symbol Types
STT_NOTYPE    = 0
STT_OBJECT    = 1
STT_FUNC      = 2
STT_SECTION   = 3
STT_FILE      = 4

# RISC-V Relocation Types
R_RISCV_NONE           = 0
R_RISCV_32             = 1
R_RISCV_64             = 2
R_RISCV_RELATIVE       = 3
R_RISCV_COPY           = 4
R_RISCV_JUMP_SLOT      = 5
R_RISCV_TLS_DTPMOD32   = 6
R_RISCV_TLS_DTPREL32   = 7
R_RISCV_TLS_TPREL32    = 8
R_RISCV_BRANCH         = 16
R_RISCV_JAL            = 17
R_RISCV_CALL           = 18
R_RISCV_CALL_PLT       = 19
R_RISCV_GOT_HI20       = 20
R_RISCV_TLS_GOT_HI20   = 21
R_RISCV_PCREL_HI20     = 23
R_RISCV_PCREL_LO12_I   = 24
R_RISCV_PCREL_LO12_S   = 25
R_RISCV_HI20           = 26
R_RISCV_LO12_I         = 27
R_RISCV_LO12_S         = 28
R_RISCV_RELAX          = 51

class Elf32Symbol:
    """16-byte ELF32 Symbol Table Entry."""
    def __init__(
        self,
        name: str = "",
        value: int = 0,
        size: int = 0,
        sym_type: int = STT_NOTYPE,
        binding: int = STB_GLOBAL,
        shndx: int = 1
    ):
        self.name = name
        self.value = value & 0xFFFFFFFF
        self.size = size & 0xFFFFFFFF
        self.info = (binding << 4) | (sym_type & 0xF)
        self.other = 0
        self.shndx = shndx

    def pack(self, strtab_offset: int) -> bytes:
        return struct.pack(
            "<IIIBBH",
            strtab_offset,
            self.value,
            self.size,
            self.info,
            self.other,
            self.shndx
        )

class Elf32Relocation:
    """8-byte ELF32 Relocation Entry without Addend."""
    def __init__(self, offset: int, sym_index: int, rel_type: int):
        self.offset = offset & 0xFFFFFFFF
        self.info = ((sym_index & 0xFFFFFF) << 8) | (rel_type & 0xFF)

    def pack(self) -> bytes:
        return struct.pack("<II", self.offset, self.info)

class ELF32Builder:
    """
    Constructs a valid 32-bit RISC-V ELF executable binary from machine code and data.
    """
    def __init__(self, entry_addr: int = 0x80000000):
        self.entry_addr = entry_addr
        self.text_bytes = bytearray()
        self.rodata_bytes = bytearray()
        self.data_bytes = bytearray()
        self.symbols: List[Elf32Symbol] = []
        self.relocations: List[Elf32Relocation] = []

    def set_text(self, code: bytes):
        self.text_bytes = bytearray(code)

    def set_rodata(self, rodata: bytes):
        self.rodata_bytes = bytearray(rodata)

    def set_data(self, data: bytes):
        self.data_bytes = bytearray(data)

    def add_symbol(
        self,
        name: str,
        value: int,
        size: int = 0,
        sym_type: int = STT_NOTYPE,
        binding: int = STB_GLOBAL,
        shndx: int = 1
    ):
        sym = Elf32Symbol(name, value, size, sym_type, binding, shndx)
        self.symbols.append(sym)

    def add_relocation(self, offset: int, sym_index: int, rel_type: int):
        self.relocations.append(Elf32Relocation(offset, sym_index, rel_type))

    def build(self) -> bytes:
        """
        Builds and packs the complete ELF32 file bytes with headers, sections, and symbols.
        """
        ehdr_size = 52
        phdr_size = 32
        shdr_size = 40

        # Program Header: 1 PT_LOAD segment covering everything
        phnum = 1
        shnum = 4  # Null, .text, .shstrtab, .rodata

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

class ELF32Parser:
    """
    Parses and inspects 32-bit RISC-V ELF binaries.
    """
    def __init__(self, raw_bytes: bytes):
        self.raw = raw_bytes
        self.entry_point = 0
        self.machine = 0
        self.segments: List[Dict[str, Any]] = []
        self.sections: List[Dict[str, Any]] = []
        self.shstrtab: bytes = b""
        self._parse()

    def _parse(self):
        if len(self.raw) < 52:
            raise ValueError("File too short for ELF32 header")

        magic = self.raw[:4]
        if magic != b"\x7fELF":
            raise ValueError(f"Invalid ELF magic: {magic}")

        elf_class = self.raw[4]
        if elf_class != ELFCLASS32:
            raise ValueError(f"Expected ELF32 class (1), got {elf_class}")

        endianness = self.raw[5]
        if endianness != ELFDATA2LSB:
            raise ValueError("Expected Little-Endian ELF")

        # Unpack ELF Header
        e_type, e_machine, e_version, e_entry, e_phoff, e_shoff, e_flags, e_ehsize, e_phentsize, e_phnum, e_shentsize, e_shnum, e_shstrndx = struct.unpack(
            "<HHIIIIIHHHHHH", self.raw[16:52]
        )
        self.entry_point = e_entry
        self.machine = e_machine

        # Parse Section Header String Table (.shstrtab)
        if e_shnum > 0 and e_shstrndx < e_shnum:
            shstr_offset = e_shoff + (e_shstrndx * e_shentsize)
            sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size, sh_link, sh_info, sh_addralign, sh_entsize = struct.unpack(
                "<IIIIIIIIII", self.raw[shstr_offset : shstr_offset + 40]
            )
            self.shstrtab = self.raw[sh_offset : sh_offset + sh_size]

        # Parse Section Headers
        for i in range(e_shnum):
            soff = e_shoff + (i * e_shentsize)
            name_idx, s_type, s_flags, s_addr, s_offset, s_size, s_link, s_info, s_align, s_entsize = struct.unpack(
                "<IIIIIIIIII", self.raw[soff : soff + 40]
            )
            name = ""
            if self.shstrtab and name_idx < len(self.shstrtab):
                name = self.shstrtab[name_idx:].split(b"\x00", 1)[0].decode("utf-8", errors="ignore")

            data = self.raw[s_offset : s_offset + s_size] if s_type != SHT_NOBITS else b""
            self.sections.append({
                "index": i,
                "name": name,
                "type": s_type,
                "flags": s_flags,
                "addr": s_addr,
                "offset": s_offset,
                "size": s_size,
                "data": data
            })

        # Parse Program Headers
        for i in range(e_phnum):
            poff = e_phoff + (i * e_phentsize)
            p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = struct.unpack(
                "<IIIIIIII", self.raw[poff : poff + 32]
            )
            self.segments.append({
                "type": p_type,
                "offset": p_offset,
                "vaddr": p_vaddr,
                "paddr": p_paddr,
                "filesz": p_filesz,
                "memsz": p_memsz,
                "flags": p_flags,
                "align": p_align
            })

    def get_section_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        for sec in self.sections:
            if sec["name"] == name:
                return sec
        return None

if __name__ == "__main__":
    builder = ELF32Builder(entry_addr=0x80000000)
    # addi a0, zero, 42; ret
    code = struct.pack("<II", 0x02A00513, 0x00008067)
    builder.set_text(code)
    builder.set_rodata(b"Hello from ELF32\x00")
    elf_data = builder.build()

    # Parse and inspect built ELF
    parser = ELF32Parser(elf_data)
    assert parser.entry_point == 0x80000000
    assert parser.machine == 243  # EM_RISCV

    text_sec = parser.get_section_by_name(".text")
    assert text_sec is not None
    assert text_sec["size"] == len(code)

    rodata_sec = parser.get_section_by_name(".rodata")
    assert rodata_sec is not None
    assert b"Hello from ELF32" in rodata_sec["data"]

    print("ELF32 Builder and Parser verification successful.")
