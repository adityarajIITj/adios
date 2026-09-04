#!/usr/bin/env python3
"""
AdiOS Memory Subsystem: Physical Page Allocator & CLOCK Eviction Engine (mmu/page_alloc.py)
Implements industrial-grade physical memory management and demand paging:
- Physical Page Frame Allocator with reference counting
- Bitmap-based free frame tracking across 64MB RAM (16,384 4KB pages)
- CLOCK (Second Chance) Page Replacement Algorithm with reference and dirty bits
- Copy-On-Write (COW) fork mechanics and store page fault handler
- Eviction writeback queue for swapped pages

Zero external dependencies. Pure RV32IM bare-metal MMU subsystem.
STRICT ZERO EMOJI POLICY.
"""

from typing import Dict, List, Tuple, Optional, Set

PAGE_SIZE = 4096 # 4KB standard Sv32 page size
RAM_BASE  = 0x80000000
RAM_SIZE  = 64 * 1024 * 1024 # 64MB
TOTAL_PAGES = RAM_SIZE // PAGE_SIZE # 16,384 pages

class PageFrame:
    """Represents a 4KB physical memory frame."""
    def __init__(self, paddr: int):
        self.paddr = paddr
        self.ref_count = 0
        self.is_free = True
        self.ref_bit = False
        self.dirty_bit = False
        self.pinned = False # Kernel frames cannot be evicted
        self.vaddr_owner: Optional[int] = None

class PhysicalPageAllocator:
    """
    Manages physical page allocation, reference counts, and free list.
    """
    def __init__(self, base_addr: int = RAM_BASE, total_pages: int = TOTAL_PAGES):
        self.base_addr = base_addr
        self.total_pages = total_pages
        self.frames: List[PageFrame] = [
            PageFrame(base_addr + i * PAGE_SIZE) for i in range(total_pages)
        ]
        # Reserve first 1024 pages (4MB) for kernel code & page tables
        for i in range(1024):
            self.frames[i].is_free = False
            self.frames[i].pinned = True
            self.frames[i].ref_count = 1

        self.free_count = total_pages - 1024
        self.next_free_index = 1024

    def alloc_page(self, pinned: bool = False) -> Optional[int]:
        """Allocates a free physical frame and returns its physical address."""
        if self.free_count == 0:
            return None

        # Search for free frame
        start = self.next_free_index
        for i in range(self.total_pages):
            idx = (start + i) % self.total_pages
            frame = self.frames[idx]
            if frame.is_free:
                frame.is_free = False
                frame.ref_count = 1
                frame.ref_bit = True
                frame.dirty_bit = False
                frame.pinned = pinned
                self.free_count -= 1
                self.next_free_index = (idx + 1) % self.total_pages
                return frame.paddr

        return None

    def free_page(self, paddr: int):
        """Decrements ref_count and frees frame when reference hits zero."""
        idx = (paddr - self.base_addr) // PAGE_SIZE
        if 0 <= idx < self.total_pages:
            frame = self.frames[idx]
            if frame.ref_count > 0:
                frame.ref_count -= 1
            if frame.ref_count == 0 and not frame.pinned:
                frame.is_free = True
                frame.ref_bit = False
                frame.dirty_bit = False
                frame.vaddr_owner = None
                self.free_count += 1

    def retain_page(self, paddr: int):
        """Increments ref_count for Copy-On-Write sharing."""
        idx = (paddr - self.base_addr) // PAGE_SIZE
        if 0 <= idx < self.total_pages:
            self.frames[idx].ref_count += 1

    def get_ref_count(self, paddr: int) -> int:
        idx = (paddr - self.base_addr) // PAGE_SIZE
        if 0 <= idx < self.total_pages:
            return self.frames[idx].ref_count
        return 0

class ClockEvictionEngine:
    """
    Second-chance CLOCK page replacement algorithm.
    """
    def __init__(self, allocator: PhysicalPageAllocator):
        self.allocator = allocator
        self.hand = 0
        self.active_pages: List[int] = [] # list of paddrs in eviction circle

    def register_page(self, paddr: int, vaddr: int):
        idx = (paddr - self.allocator.base_addr) // PAGE_SIZE
        if 0 <= idx < self.allocator.total_pages:
            frame = self.allocator.frames[idx]
            frame.vaddr_owner = vaddr
            frame.ref_bit = True
            if paddr not in self.active_pages:
                self.active_pages.append(paddr)

    def access_page(self, paddr: int):
        """Called on memory read/execute: sets reference bit."""
        idx = (paddr - self.allocator.base_addr) // PAGE_SIZE
        if 0 <= idx < self.allocator.total_pages:
            self.allocator.frames[idx].ref_bit = True

    def modify_page(self, paddr: int):
        """Called on memory write: sets reference and dirty bits."""
        idx = (paddr - self.allocator.base_addr) // PAGE_SIZE
        if 0 <= idx < self.allocator.total_pages:
            self.allocator.frames[idx].ref_bit = True
            self.allocator.frames[idx].dirty_bit = True

    def select_victim(self) -> Optional[Tuple[int, int, bool]]:
        """
        Steps clock hand forward.
        Returns (victim_paddr, victim_vaddr, was_dirty) or None.
        """
        if not self.active_pages:
            return None

        attempts = len(self.active_pages) * 2
        while attempts > 0:
            self.hand = self.hand % len(self.active_pages)
            paddr = self.active_pages[self.hand]
            idx = (paddr - self.allocator.base_addr) // PAGE_SIZE
            frame = self.allocator.frames[idx]

            if frame.pinned:
                self.hand += 1
                attempts -= 1
                continue

            if frame.ref_bit:
                # Second chance: clear reference bit and advance
                frame.ref_bit = False
                self.hand += 1
            else:
                # Found victim with ref_bit == 0
                victim_paddr = paddr
                victim_vaddr = frame.vaddr_owner or 0
                was_dirty = frame.dirty_bit

                # Remove from active list
                self.active_pages.pop(self.hand)
                self.allocator.free_page(victim_paddr)
                return (victim_paddr, victim_vaddr, was_dirty)

            attempts -= 1

        return None

class CopyOnWriteManager:
    """
    Handles Copy-On-Write (COW) page sharing and fault resolution.
    """
    def __init__(self, allocator: PhysicalPageAllocator, memory_store: bytearray):
        self.allocator = allocator
        self.memory_store = memory_store # RAM bytearray

    def fork_share_page(self, paddr: int):
        """Shares page frame between parent and child by retaining reference."""
        self.allocator.retain_page(paddr)

    def handle_cow_store_fault(self, old_paddr: int) -> int:
        """
        Resolves store page fault on read-only COW page:
        - If ref_count > 1: duplicates 4KB page to a new physical frame, decrements old ref_count.
        - If ref_count == 1: page is no longer shared, returns old_paddr with write permission.
        """
        ref_count = self.allocator.get_ref_count(old_paddr)

        if ref_count <= 1:
            # Sole owner: no copy needed, grant write
            return old_paddr

        # Multiple references: allocate new frame and duplicate content
        new_paddr = self.allocator.alloc_page()
        if new_paddr is None:
            raise MemoryError("Out of physical memory during COW resolution")

        # Copy 4KB data from old frame to new frame
        old_off = old_paddr - self.allocator.base_addr
        new_off = new_paddr - self.allocator.base_addr
        self.memory_store[new_off : new_off + PAGE_SIZE] = self.memory_store[old_off : old_off + PAGE_SIZE]

        # Release one reference on the shared parent frame
        self.allocator.free_page(old_paddr)
        return new_paddr
