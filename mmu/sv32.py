#!/usr/bin/env python3
"""
AdiOS Virtual Memory Subsystem: RISC-V Sv32 Paging Engine (sv32.py)
Implements standard RISC-V Sv32 2-Level Page Table Translation & Hardware Page Faults.
Features:
- Standard Sv32 Page Table Entry (PTE) flag bits (V, R, W, X, U, G, A, D)
- 4 KB Standard Page Translation (VPN[1] -> VPN[0] -> PPN)
- 4 MB Megapage (Superpage) Translation
- Hardware Access Violation & Page Fault Exception Generation
"""

# PTE Flag Bitmasks
PTE_V = 1 << 0  # Valid
PTE_R = 1 << 1  # Readable
PTE_W = 1 << 2  # Writable
PTE_X = 1 << 3  # Executable
PTE_U = 1 << 4  # User mode accessible
PTE_G = 1 << 5  # Global mapping
PTE_A = 1 << 6  # Accessed
PTE_D = 1 << 7  # Dirty

# Access Types for Permission Checking
ACCESS_FETCH = 0  # Instruction fetch
ACCESS_LOAD  = 1  # Memory read
ACCESS_STORE = 2  # Memory write

# RISC-V Exception Codes
EXC_FETCH_PAGE_FAULT = 12
EXC_LOAD_PAGE_FAULT  = 13
EXC_STORE_PAGE_FAULT = 15

PAGE_SIZE = 4096      # 4 KB
MEGAPAGE_SIZE = 4096 * 1024 # 4 MB

class PageFaultException(Exception):
    def __init__(self, cause: int, bad_vaddr: int, message: str):
        super().__init__(f"{message} (vaddr=0x{bad_vaddr:08X}, cause={cause})")
        self.cause = cause
        self.bad_vaddr = bad_vaddr

class PageTableEntry:
    """
    32-bit RISC-V Sv32 Page Table Entry.
    Layout:
      bits 31..20: PPN[1] (12 bits)
      bits 19..10: PPN[0] (10 bits)
      bits  9..8:  RSW    (2 bits)
      bits  7..0:  D, A, G, U, X, W, R, V
    """
    def __init__(self, raw_val: int = 0):
        self.val = raw_val & 0xFFFFFFFF

    @property
    def valid(self) -> bool:
        return bool(self.val & PTE_V)

    @property
    def readable(self) -> bool:
        return bool(self.val & PTE_R)

    @property
    def writable(self) -> bool:
        return bool(self.val & PTE_W)

    @property
    def executable(self) -> bool:
        return bool(self.val & PTE_X)

    @property
    def user(self) -> bool:
        return bool(self.val & PTE_U)

    @property
    def is_leaf(self) -> bool:
        """A leaf PTE has at least one of R, W, X set."""
        return bool(self.val & (PTE_R | PTE_W | PTE_X))

    @property
    def ppn(self) -> int:
        return (self.val >> 10) & 0x3FFFFF

    @property
    def ppn0(self) -> int:
        return (self.val >> 10) & 0x3FF

    @property
    def ppn1(self) -> int:
        return (self.val >> 20) & 0xFFF

    @property
    def paddr(self) -> int:
        """Physical base address corresponding to PPN."""
        return self.ppn << 12

    @classmethod
    def make(cls, ppn: int, flags: int):
        return cls(((ppn & 0x3FFFFF) << 10) | (flags & 0x3FF))

class Sv32MMU:
    """
    RISC-V Sv32 Memory Management Unit.
    Performs 2-level hardware page table walks on physical RAM.
    """
    def __init__(self, ram: bytearray, ram_base: int = 0x80000000):
        self.ram = ram
        self.ram_base = ram_base
        self.enabled = False
        self.root_ppn = 0 # Base PPN of Level 1 Page Table

    def set_satp(self, satp_val: int):
        """
        Updates the Supervisor Address Translation and Protection (satp) register.
        Mode: bit 31 (0 = Bare / No translation, 1 = Sv32).
        ASID: bits 30..22.
        PPN:  bits 21..0.
        """
        mode = (satp_val >> 31) & 1
        self.enabled = (mode == 1)
        self.root_ppn = satp_val & 0x3FFFFF

    def _read_word_phys(self, paddr: int) -> int:
        """Reads a 32-bit little-endian word from physical RAM."""
        if not (self.ram_base <= paddr < self.ram_base + len(self.ram) - 3):
            raise PageFaultException(EXC_LOAD_PAGE_FAULT, paddr, "Physical RAM bus access fault")
        offset = paddr - self.ram_base
        return int.from_bytes(self.ram[offset:offset + 4], "little")

    def _write_word_phys(self, paddr: int, val: int):
        """Writes a 32-bit little-endian word to physical RAM."""
        if not (self.ram_base <= paddr < self.ram_base + len(self.ram) - 3):
            raise PageFaultException(EXC_STORE_PAGE_FAULT, paddr, "Physical RAM bus access fault")
        offset = paddr - self.ram_base
        self.ram[offset:offset + 4] = (val & 0xFFFFFFFF).to_bytes(4, "little")

    def translate(self, vaddr: int, access_type: int = ACCESS_LOAD, is_user: bool = False) -> int:
        """
        Translates a 32-bit virtual address to a physical address using Sv32 2-level walk.
        Throws PageFaultException on invalid mappings or permission violations.
        """
        if not self.enabled:
            return vaddr & 0xFFFFFFFF

        vaddr &= 0xFFFFFFFF
        vpn1 = (vaddr >> 22) & 0x3FF
        vpn0 = (vaddr >> 12) & 0x3FF
        offset = vaddr & 0xFFF

        # Level 1 Page Table Walk
        root_table_paddr = self.root_ppn << 12
        pte1_addr = root_table_paddr + (vpn1 * 4)
        pte1 = PageTableEntry(self._read_word_phys(pte1_addr))

        if not pte1.valid:
            cause = EXC_FETCH_PAGE_FAULT if access_type == ACCESS_FETCH else (
                EXC_STORE_PAGE_FAULT if access_type == ACCESS_STORE else EXC_LOAD_PAGE_FAULT
            )
            raise PageFaultException(cause, vaddr, "Level 1 PTE invalid")

        if not pte1.is_leaf:
            # Level 1 points to Level 0 Page Table
            level0_table_paddr = pte1.ppn << 12
            pte0_addr = level0_table_paddr + (vpn0 * 4)
            pte0 = PageTableEntry(self._read_word_phys(pte0_addr))

            if not pte0.valid or not pte0.is_leaf:
                cause = EXC_FETCH_PAGE_FAULT if access_type == ACCESS_FETCH else (
                    EXC_STORE_PAGE_FAULT if access_type == ACCESS_STORE else EXC_LOAD_PAGE_FAULT
                )
                raise PageFaultException(cause, vaddr, "Level 0 PTE invalid or not a leaf")

            # Check permissions
            self._check_permissions(pte0, vaddr, access_type, is_user)

            # Update Accessed & Dirty flags
            new_val = pte0.val | PTE_A
            if access_type == ACCESS_STORE:
                new_val |= PTE_D
            if new_val != pte0.val:
                self._write_word_phys(pte0_addr, new_val)

            # 4 KB Page physical address = (PPN << 12) | offset
            return (pte0.ppn << 12) | offset
        else:
            # Megapage (4 MB superpage) translation
            if pte1.ppn0 != 0:
                # Misaligned megapage
                raise PageFaultException(EXC_LOAD_PAGE_FAULT, vaddr, "Misaligned 4MB megapage")

            self._check_permissions(pte1, vaddr, access_type, is_user)

            new_val = pte1.val | PTE_A
            if access_type == ACCESS_STORE:
                new_val |= PTE_D
            if new_val != pte1.val:
                self._write_word_phys(pte1_addr, new_val)

            # Megapage offset = bits 21..0 (4 MB offset)
            return (pte1.ppn1 << 22) | (vaddr & 0x3FFFFF)

    def _check_permissions(self, pte: PageTableEntry, vaddr: int, access_type: int, is_user: bool):
        """Verifies privilege and R/W/X permission flags."""
        cause = EXC_FETCH_PAGE_FAULT if access_type == ACCESS_FETCH else (
            EXC_STORE_PAGE_FAULT if access_type == ACCESS_STORE else EXC_LOAD_PAGE_FAULT
        )

        if is_user and not pte.user:
            raise PageFaultException(cause, vaddr, "User privilege violation")
        if not is_user and pte.user and access_type == ACCESS_FETCH:
            raise PageFaultException(cause, vaddr, "Supervisor cannot execute user page")

        if access_type == ACCESS_FETCH and not pte.executable:
            raise PageFaultException(EXC_FETCH_PAGE_FAULT, vaddr, "Page is not executable")
        if access_type == ACCESS_LOAD and not pte.readable:
            raise PageFaultException(EXC_LOAD_PAGE_FAULT, vaddr, "Page is not readable")
        if access_type == ACCESS_STORE and not pte.writable:
            raise PageFaultException(EXC_STORE_PAGE_FAULT, vaddr, "Page is not writable")

if __name__ == "__main__":
    ram = bytearray(16 * 1024 * 1024) # 16 MB test RAM
    mmu = Sv32MMU(ram, ram_base=0x80000000)
    print("Sv32 MMU initialized.")
