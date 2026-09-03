#!/usr/bin/env python3
"""
AdiOS Virtual Memory Subsystem: Process Address Space Manager (address_space.py)
Manages two-level Sv32 page table structures, memory allocations, and kernel identity mappings.
"""

from mmu.sv32 import (
    PageTableEntry, Sv32MMU, PTE_V, PTE_R, PTE_W, PTE_X, PTE_U, PTE_G, PTE_A, PTE_D,
    PAGE_SIZE, MEGAPAGE_SIZE
)
from mmu.tlb import TLB

class AddressSpace:
    """
    Virtual Address Space representation for the Kernel and isolated user tasks.
    """
    def __init__(self, mmu: Sv32MMU, tlb: TLB = None, asid: int = 0):
        self.mmu = mmu
        self.tlb = tlb or TLB()
        self.asid = asid
        self.allocated_pages = []

        # Allocate root Level 1 Page Table (4096 bytes = 1024 4-byte entries)
        self.root_paddr = self._alloc_zeroed_page()
        self.root_ppn = self.root_paddr >> 12

    def _alloc_zeroed_page(self) -> int:
        """
        Allocates a zeroed 4KB physical page from the top of physical RAM.
        """
        # Place page tables starting from offset 48 MB to 56 MB in physical RAM
        base_alloc_paddr = self.mmu.ram_base + (48 * 1024 * 1024)
        paddr = base_alloc_paddr + (len(self.allocated_pages) * PAGE_SIZE)

        ram_off = paddr - self.mmu.ram_base
        if ram_off + PAGE_SIZE > len(self.mmu.ram):
            raise MemoryError("Out of physical memory for page table frames")

        # Zero out the 4KB page
        self.mmu.ram[ram_off:ram_off + PAGE_SIZE] = b"\x00" * PAGE_SIZE
        self.allocated_pages.append(paddr)
        return paddr

    def get_satp(self) -> int:
        """Returns the 32-bit satp register value for this address space."""
        # Mode = 1 (Sv32, bit 31), ASID (bits 30..22), PPN (bits 21..0)
        return (1 << 31) | ((self.asid & 0x1FF) << 22) | (self.root_ppn & 0x3FFFFF)

    def activate(self):
        """Loads this address space into the hardware MMU."""
        satp_val = self.get_satp()
        self.mmu.set_satp(satp_val)
        if self.tlb:
            self.tlb.flush(asid=self.asid)

    def map_page(self, vaddr: int, paddr: int, flags: int):
        """
        Maps a 4 KB virtual page to a physical page in this address space.
        Flags: Bitwise OR of PTE_V, PTE_R, PTE_W, PTE_X, PTE_U, PTE_G.
        """
        vpn1 = (vaddr >> 22) & 0x3FF
        vpn0 = (vaddr >> 12) & 0x3FF
        ppn = paddr >> 12

        # 1. Level 1 Page Table Entry
        pte1_addr = self.root_paddr + (vpn1 * 4)
        pte1_val = self.mmu._read_word_phys(pte1_addr)
        pte1 = PageTableEntry(pte1_val)

        if not pte1.valid:
            # Allocate Level 0 Page Table
            level0_paddr = self._alloc_zeroed_page()
            level0_ppn = level0_paddr >> 12
            # Pointer to next level: V=1, R=W=X=0
            new_pte1 = PageTableEntry.make(level0_ppn, PTE_V)
            self.mmu._write_word_phys(pte1_addr, new_pte1.val)
            pte1 = new_pte1

        # 2. Level 0 Page Table Entry (Leaf)
        level0_paddr = pte1.ppn << 12
        pte0_addr = level0_paddr + (vpn0 * 4)
        pte0 = PageTableEntry.make(ppn, flags | PTE_V | PTE_A)
        self.mmu._write_word_phys(pte0_addr, pte0.val)

        if self.tlb:
            self.tlb.flush(vaddr=vaddr, asid=self.asid)

    def map_megapage(self, vaddr: int, paddr: int, flags: int):
        """
        Maps a 4 MB superpage directly at Level 1.
        Requires 4 MB alignment on both vaddr and paddr.
        """
        if (vaddr & 0x3FFFFF) != 0 or (paddr & 0x3FFFFF) != 0:
            raise ValueError("Megapage must be 4 MB aligned")

        vpn1 = (vaddr >> 22) & 0x3FF
        ppn = paddr >> 12

        pte1_addr = self.root_paddr + (vpn1 * 4)
        pte1 = PageTableEntry.make(ppn, flags | PTE_V | PTE_A)
        self.mmu._write_word_phys(pte1_addr, pte1.val)

        if self.tlb:
            self.tlb.flush(vaddr=vaddr, asid=self.asid)

    def setup_kernel_identity_map(self):
        """
        Constructs the standard AdiOS Kernel identity mapping:
        - 0x10000000 - 0x10002000: Peripherals MMIO (UART, Timer, Disk) [R/W]
        - 0x20000000 - 0x20200000: Linear Framebuffer & Display Ctrl [R/W]
        - 0x80000000 - 0x84000000: Physical RAM (64 MB via 16 4MB Megapages) [R/W/X]
        """
        rw_flags = PTE_R | PTE_W | PTE_G
        rwx_flags = PTE_R | PTE_W | PTE_X | PTE_G

        # 1. Map 64 MB RAM using 16 x 4MB Megapages
        for i in range(16):
            base_addr = 0x80000000 + (i * MEGAPAGE_SIZE)
            self.map_megapage(base_addr, base_addr, rwx_flags)

        # 2. Map Peripherals MMIO (4KB pages at 0x10000000 and 0x10001000)
        self.map_page(0x10000000, 0x10000000, rw_flags) # UART, Timer, Audio
        self.map_page(0x10001000, 0x10001000, rw_flags) # Disk Controller

        # 3. Map Framebuffer (4MB Megapage covering 0x20000000 - 0x20400000)
        self.map_megapage(0x20000000, 0x20000000, rw_flags)

if __name__ == "__main__":
    ram = bytearray(64 * 1024 * 1024)
    mmu = Sv32MMU(ram, 0x80000000)
    space = AddressSpace(mmu)
    space.setup_kernel_identity_map()
    space.activate()

    # Test translation of RAM
    p = mmu.translate(0x80001000, access_type=0)
    assert p == 0x80001000
    print("Kernel identity mapping translation verified.")
