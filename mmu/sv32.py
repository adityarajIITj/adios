#!/usr/bin/env python3
"""
AdiOS Virtual Memory Subsystem: RISC-V Sv32 Paging Engine (sv32.py)
Implements standard RISC-V Sv32 2-Level Page Table Translation & Hardware Page Faults:
- Standard Sv32 Page Table Entry (PTE) flag bits (V, R, W, X, U, G, A, D)
- 4 KB Standard Page Translation (VPN[1] -> VPN[0] -> PPN)
- 4 MB Megapage (Superpage) Translation (VPN[1] -> PPN)
- Integrated 64-Entry Fast-Path TLB with ASID tagging, LRU eviction, and sfence.vma
- In-memory Page Table Manager (map_page, unmap_page, map_megapage, protect_page)
- Demand Paging & Disk Swap Entry encoding in non-valid PTEs
- Hardware Access Violation & Page Fault Exception Generation (Fetch, Load, Store)

Zero external dependencies. Pure RV32IM bare-metal MMU subsystem.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

from typing import Dict, List, Optional, Tuple

# PTE Flag Bitmasks according to RISC-V Privileged Architecture Specification
PTE_V = 1 << 0  # Valid
PTE_R = 1 << 1  # Readable
PTE_W = 1 << 2  # Writable
PTE_X = 1 << 3  # Executable
PTE_U = 1 << 4  # User mode accessible
PTE_G = 1 << 5  # Global mapping
PTE_A = 1 << 6  # Accessed
PTE_D = 1 << 7  # Dirty

# AdiOS Swap Indicator flag in RSW (Reserved for Software) bits 9..8
PTE_SWAP = 1 << 8

# Access Types for Permission Checking
ACCESS_FETCH = 0  # Instruction fetch
ACCESS_LOAD  = 1  # Memory read
ACCESS_STORE = 2  # Memory write

# RISC-V Exception Codes (mcause / scause)
EXC_FETCH_PAGE_FAULT = 12
EXC_LOAD_PAGE_FAULT  = 13
EXC_STORE_PAGE_FAULT = 15

PAGE_SIZE      = 4096            # 4 KB
MEGAPAGE_SIZE  = 4096 * 1024     # 4 MB
ENTRIES_PER_PT = 1024            # 1024 32-bit entries per 4KB page table

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
    def global_map(self) -> bool:
        return bool(self.val & PTE_G)

    @property
    def accessed(self) -> bool:
        return bool(self.val & PTE_A)

    @property
    def dirty(self) -> bool:
        return bool(self.val & PTE_D)

    @property
    def is_swap(self) -> bool:
        return (not self.valid) and bool(self.val & PTE_SWAP)

    @property
    def swap_slot(self) -> int:
        return (self.val >> 10) & 0x3FFFFF

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
    def make(cls, ppn: int, flags: int) -> 'PageTableEntry':
        return cls(((ppn & 0x3FFFFF) << 10) | (flags & 0x3FF))

    @classmethod
    def make_swap(cls, swap_slot: int) -> 'PageTableEntry':
        return cls(((swap_slot & 0x3FFFFF) << 10) | PTE_SWAP)

class MMUTLBEntry:
    """Integrated TLB entry for accelerated translation."""
    def __init__(self, vpn: int, paddr_base: int, flags: int, asid: int = 0, is_megapage: bool = False):
        self.vpn = vpn
        self.paddr_base = paddr_base
        self.flags = flags
        self.asid = asid
        self.is_megapage = is_megapage
        self.last_access = 0

class Sv32MMU:
    """
    RISC-V Sv32 Memory Management Unit.
    Performs 2-level hardware page table walks on physical RAM,
    accelerated by a 64-entry internal TLB with LRU replacement.
    """
    def __init__(self, ram: bytearray, ram_base: int = 0x80000000, tlb_capacity: int = 64):
        self.ram = ram
        self.ram_base = ram_base
        self.enabled = False
        self.root_ppn = 0   # Base PPN of Level 1 Page Table
        self.asid = 0       # Active Address Space Identifier
        self.tlb_capacity = tlb_capacity
        self.tlb: Dict[Tuple[int, int], MMUTLBEntry] = {}  # (vpn, asid) -> MMUTLBEntry
        self.access_counter = 0

        # Telemetry
        self.tlb_hits = 0
        self.tlb_misses = 0
        self.page_walks = 0

    def set_satp(self, satp_val: int):
        """
        Updates the Supervisor Address Translation and Protection (satp) register.
        Mode: bit 31 (0 = Bare / No translation, 1 = Sv32).
        ASID: bits 30..22.
        PPN:  bits 21..0.
        """
        mode = (satp_val >> 31) & 1
        new_enabled = (mode == 1)
        new_asid = (satp_val >> 22) & 0x1FF
        new_root_ppn = satp_val & 0x3FFFFF

        if new_root_ppn != self.root_ppn or new_asid != self.asid:
            # Flushes non-global TLB entries on context switch
            self.sfence_vma(asid=self.asid)

        self.enabled = new_enabled
        self.asid = new_asid
        self.root_ppn = new_root_ppn

    def sfence_vma(self, vaddr: Optional[int] = None, asid: Optional[int] = None):
        """
        RISC-V sfence.vma instruction simulation.
        Selectively invalidates TLB entries by virtual address and/or ASID.
        """
        if vaddr is None and asid is None:
            self.tlb.clear()
            return

        target_vpn = (vaddr >> 12) if vaddr is not None else None
        to_delete = []

        for (vpn, entry_asid), entry in self.tlb.items():
            # Global entries are preserved unless explicitly invalidated
            if entry.flags & PTE_G and asid is not None:
                continue

            match_vaddr = (target_vpn is None) or (vpn == target_vpn)
            match_asid = (asid is None) or (entry_asid == asid)

            if match_vaddr and match_asid:
                to_delete.append((vpn, entry_asid))

        for key in to_delete:
            del self.tlb[key]

    def _read_word_phys(self, paddr: int) -> int:
        """Reads a 32-bit little-endian word from physical RAM."""
        if not (self.ram_base <= paddr <= self.ram_base + len(self.ram) - 4):
            raise PageFaultException(EXC_LOAD_PAGE_FAULT, paddr, "Physical RAM bus access fault")
        offset = paddr - self.ram_base
        return int.from_bytes(self.ram[offset:offset + 4], "little")

    def _write_word_phys(self, paddr: int, val: int):
        """Writes a 32-bit little-endian word to physical RAM."""
        if not (self.ram_base <= paddr <= self.ram_base + len(self.ram) - 4):
            raise PageFaultException(EXC_STORE_PAGE_FAULT, paddr, "Physical RAM bus access fault")
        offset = paddr - self.ram_base
        self.ram[offset:offset + 4] = (val & 0xFFFFFFFF).to_bytes(4, "little")

    def _insert_tlb(self, vpn: int, paddr_base: int, flags: int, is_megapage: bool = False):
        if len(self.tlb) >= self.tlb_capacity:
            # Evict LRU entry
            lru_key = min(self.tlb.keys(), key=lambda k: self.tlb[k].last_access)
            del self.tlb[lru_key]

        entry = MMUTLBEntry(vpn, paddr_base, flags, self.asid, is_megapage)
        entry.last_access = self.access_counter
        self.tlb[(vpn, self.asid)] = entry

    def translate(self, vaddr: int, access_type: int = ACCESS_LOAD, is_user: bool = False) -> int:
        """
        Translates a 32-bit virtual address to a physical address using Sv32 2-level walk,
        with TLB acceleration.
        Throws PageFaultException on invalid mappings or permission violations.
        """
        if not self.enabled:
            return vaddr & 0xFFFFFFFF

        self.access_counter += 1
        vaddr &= 0xFFFFFFFF
        vpn = vaddr >> 12
        vpn1 = (vaddr >> 22) & 0x3FF
        vpn0 = (vaddr >> 12) & 0x3FF
        offset = vaddr & 0xFFF

        # 1. TLB Fast-Path Lookup
        tlb_key = (vpn, self.asid)
        if tlb_key in self.tlb:
            entry = self.tlb[tlb_key]
            # Check permissions from cached flags
            pte_dummy = PageTableEntry(entry.flags)
            self._check_permissions(pte_dummy, vaddr, access_type, is_user)
            self.tlb_hits += 1
            entry.last_access = self.access_counter
            if entry.is_megapage:
                return entry.paddr_base | (vaddr & 0x3FFFFF)
            return entry.paddr_base | offset

        # 2. Hardware 2-Level Page Table Walk
        self.tlb_misses += 1
        self.page_walks += 1

        root_table_paddr = self.root_ppn << 12
        pte1_addr = root_table_paddr + (vpn1 * 4)
        pte1 = PageTableEntry(self._read_word_phys(pte1_addr))

        if not pte1.valid:
            if pte1.is_swap:
                raise PageFaultException(
                    EXC_LOAD_PAGE_FAULT if access_type != ACCESS_STORE else EXC_STORE_PAGE_FAULT,
                    vaddr,
                    f"Page swapped to disk slot {pte1.swap_slot}"
                )
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
                if pte0.is_swap:
                    raise PageFaultException(
                        EXC_LOAD_PAGE_FAULT if access_type != ACCESS_STORE else EXC_STORE_PAGE_FAULT,
                        vaddr,
                        f"Page swapped to disk slot {pte0.swap_slot}"
                    )
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

            # Insert into TLB
            paddr_base = pte0.ppn << 12
            self._insert_tlb(vpn, paddr_base, pte0.val, is_megapage=False)

            # 4 KB Page physical address = (PPN << 12) | offset
            return paddr_base | offset
        else:
            # Megapage (4 MB superpage) translation
            if pte1.ppn0 != 0:
                raise PageFaultException(EXC_LOAD_PAGE_FAULT, vaddr, "Misaligned 4MB megapage")

            self._check_permissions(pte1, vaddr, access_type, is_user)

            new_val = pte1.val | PTE_A
            if access_type == ACCESS_STORE:
                new_val |= PTE_D
            if new_val != pte1.val:
                self._write_word_phys(pte1_addr, new_val)

            paddr_base = pte1.ppn1 << 22
            self._insert_tlb(vpn, paddr_base, pte1.val, is_megapage=True)

            # Megapage offset = bits 21..0 (4 MB offset)
            return paddr_base | (vaddr & 0x3FFFFF)

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

class Sv32PageTableManager:
    """
    Constructs, maps, and manipulates in-memory Sv32 page tables.
    """
    def __init__(self, mmu: Sv32MMU):
        self.mmu = mmu

    def map_page(self, root_ppn: int, vaddr: int, paddr: int, flags: int):
        """Maps a 4KB virtual address to a physical address."""
        vpn1 = (vaddr >> 22) & 0x3FF
        vpn0 = (vaddr >> 12) & 0x3FF

        root_paddr = root_ppn << 12
        pte1_addr = root_paddr + (vpn1 * 4)
        pte1 = PageTableEntry(self.mmu._read_word_phys(pte1_addr))

        if not pte1.valid:
            # Allocate Level 0 table in RAM
            # In simulation, place Level 0 table at a dedicated page
            l0_paddr = (root_ppn + 1 + vpn1) << 12
            pte1 = PageTableEntry.make(l0_paddr >> 12, PTE_V)
            self.mmu._write_word_phys(pte1_addr, pte1.val)

        l0_paddr = pte1.ppn << 12
        pte0_addr = l0_paddr + (vpn0 * 4)
        new_pte0 = PageTableEntry.make(paddr >> 12, flags | PTE_V)
        self.mmu._write_word_phys(pte0_addr, new_pte0.val)
        self.mmu.sfence_vma(vaddr=vaddr)

    def map_megapage(self, root_ppn: int, vaddr: int, paddr: int, flags: int):
        """Maps a 4MB superpage."""
        vpn1 = (vaddr >> 22) & 0x3FF
        root_paddr = root_ppn << 12
        pte1_addr = root_paddr + (vpn1 * 4)
        new_pte1 = PageTableEntry.make(paddr >> 12, flags | PTE_V)
        self.mmu._write_word_phys(pte1_addr, new_pte1.val)
        self.mmu.sfence_vma(vaddr=vaddr)

    def unmap_page(self, root_ppn: int, vaddr: int):
        """Unmaps a 4KB page and flushes TLB."""
        vpn1 = (vaddr >> 22) & 0x3FF
        vpn0 = (vaddr >> 12) & 0x3FF

        root_paddr = root_ppn << 12
        pte1_addr = root_paddr + (vpn1 * 4)
        pte1 = PageTableEntry(self.mmu._read_word_phys(pte1_addr))

        if pte1.valid and not pte1.is_leaf:
            l0_paddr = pte1.ppn << 12
            pte0_addr = l0_paddr + (vpn0 * 4)
            self.mmu._write_word_phys(pte0_addr, 0)
            self.mmu.sfence_vma(vaddr=vaddr)

if __name__ == "__main__":
    ram = bytearray(16 * 1024 * 1024) # 16 MB test RAM
    mmu = Sv32MMU(ram, ram_base=0x80000000)
    pt_mgr = Sv32PageTableManager(mmu)

    # Set up root page table at PPN 0x80000 (0x80000000)
    root_ppn = 0x80000
    mmu.set_satp((1 << 31) | root_ppn) # Enable Sv32

    # Map 4KB page
    pt_mgr.map_page(root_ppn, 0x1000, 0x80100000, PTE_R | PTE_W | PTE_U)
    pa = mmu.translate(0x1020, access_type=ACCESS_LOAD, is_user=True)
    assert pa == 0x80100020
    assert mmu.tlb_misses == 1

    # Second access hits TLB
    pa2 = mmu.translate(0x1040, access_type=ACCESS_LOAD, is_user=True)
    assert pa2 == 0x80100040
    assert mmu.tlb_hits == 1

    # Invalidate TLB with sfence.vma
    mmu.sfence_vma(vaddr=0x1000)
    assert (0x1, mmu.asid) not in mmu.tlb

    print("Sv32 MMU, Page Table Manager, and Integrated TLB verified.")
