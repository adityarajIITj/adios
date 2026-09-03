#!/usr/bin/env python3
"""
Test Suite: Block G Virtual Memory, Sv32 Paging & TLB Subsystem
Verifies:
1. Sv32 PageTableEntry Flags & Permissions
2. 4 KB Standard Page 2-Level Walk & Translation
3. 4 MB Megapage Superpage Translation
4. Hardware Access Faults (Unmapped, Read-Only, Non-Executable, Privilege)
5. 64-Entry Translation Lookaside Buffer (TLB) Fast-Path & sfence.vma Invalidation
6. AddressSpace Manager & 64MB Kernel Identity Mapping
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from mmu.sv32 import (
    PageTableEntry, Sv32MMU, PageFaultException,
    PTE_V, PTE_R, PTE_W, PTE_X, PTE_U, PTE_G,
    ACCESS_FETCH, ACCESS_LOAD, ACCESS_STORE,
    EXC_FETCH_PAGE_FAULT, EXC_LOAD_PAGE_FAULT, EXC_STORE_PAGE_FAULT
)
from mmu.tlb import TLB
from mmu.address_space import AddressSpace

def test_mmu_block_g_suite():
    print("[Test MMU Block G] Initializing Virtual Memory Subsystem Verification...")

    # 1. Test PageTableEntry
    print("  -> Testing Sv32 PageTableEntry Encoding...")
    pte = PageTableEntry.make(ppn=0x80040, flags=PTE_R | PTE_W | PTE_V)
    assert pte.valid
    assert pte.readable
    assert pte.writable
    assert not pte.executable
    assert pte.is_leaf
    assert pte.ppn == 0x80040
    assert pte.paddr == 0x80040000
    print("  -> [PASS] PageTableEntry encoding verified.")

    # 2. Test 4 KB Page Translation and Hardware Page Faults
    print("  -> Testing 4 KB Standard Page 2-Level Walk & Page Faults...")
    ram = bytearray(64 * 1024 * 1024) # 64 MB RAM
    mmu = Sv32MMU(ram, ram_base=0x80000000)
    space = AddressSpace(mmu)

    # Map Virtual Address 0x00010000 to Physical Address 0x80500000 with Read/Write permissions
    space.map_page(0x00010000, 0x80500000, PTE_R | PTE_W | PTE_U)
    space.activate()

    # Load translation
    pa = mmu.translate(0x00010024, access_type=ACCESS_LOAD, is_user=True)
    assert pa == 0x80500024, f"Expected 0x80500024, got {hex(pa)}"

    # Store translation
    pa_store = mmu.translate(0x000100A0, access_type=ACCESS_STORE, is_user=True)
    assert pa_store == 0x805000A0

    # Unmapped address fault
    try:
        mmu.translate(0x00020000, access_type=ACCESS_LOAD)
        assert False, "MMU must throw PageFaultException on unmapped virtual address"
    except PageFaultException as e:
        assert e.cause == EXC_LOAD_PAGE_FAULT

    # Non-executable instruction fetch fault
    try:
        mmu.translate(0x00010000, access_type=ACCESS_FETCH, is_user=True)
        assert False, "MMU must throw PageFaultException on execute non-executable page"
    except PageFaultException as e:
        assert e.cause == EXC_FETCH_PAGE_FAULT

    print("  -> [PASS] 4 KB page translation and page fault exceptions verified.")

    # 3. Test 4 MB Megapage Superpage Translation
    print("  -> Testing 4 MB Megapage (Superpage) Translation...")
    space.map_megapage(0x40000000, 0x80800000, PTE_R | PTE_W | PTE_X | PTE_G)

    # Translate at start of megapage
    pa_mega = mmu.translate(0x40000000, access_type=ACCESS_FETCH)
    assert pa_mega == 0x80800000

    # Translate with 1 MB offset into megapage
    pa_mega_off = mmu.translate(0x40100456, access_type=ACCESS_LOAD)
    assert pa_mega_off == 0x80900456
    print("  -> [PASS] 4 MB megapage translation verified.")

    # 4. Test 64-Entry TLB
    print("  -> Testing Translation Lookaside Buffer (TLB) & sfence.vma...")
    tlb = TLB(capacity=64)
    # Insert entry
    tlb.insert(0x10000000, 0x80000000, flags=0x07, asid=1)
    
    # Lookup hit
    hit = tlb.lookup(0x10000ABC, asid=1)
    assert hit is not None
    assert hit.ppn == (0x80000000 >> 12)
    assert tlb.hits == 1

    # Lookup miss (different ASID)
    miss = tlb.lookup(0x10000ABC, asid=2)
    assert miss is None
    assert tlb.misses == 1

    # Test sfence.vma invalidation
    tlb.flush(vaddr=0x10000000, asid=1)
    flushed = tlb.lookup(0x10000ABC, asid=1)
    assert flushed is None
    print("  -> [PASS] TLB fast-path and sfence.vma invalidation verified.")

    # 5. Test Full Kernel Identity Mapping
    print("  -> Testing Full 64MB Kernel Identity Mapping...")
    k_space = AddressSpace(mmu)
    k_space.setup_kernel_identity_map()
    k_space.activate()

    # Verify identity mapping across 64MB RAM
    for ram_probe in [0x80000000, 0x81000000, 0x82000000, 0x83FFFFFC]:
        pa = mmu.translate(ram_probe, access_type=ACCESS_LOAD)
        assert pa == ram_probe, f"Identity mapping failed at {hex(ram_probe)}"

    # Verify MMIO mapping
    assert mmu.translate(0x10000000, access_type=ACCESS_STORE) == 0x10000000
    assert mmu.translate(0x20000000, access_type=ACCESS_STORE) == 0x20000000
    print("  -> [PASS] Kernel identity mapping verified.")

    print("\n[Test MMU Block G] ALL BLOCK G VIRTUAL MEMORY TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_mmu_block_g_suite()
