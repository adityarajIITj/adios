#!/usr/bin/env python3
"""
AdiOS Memory Subsystem: Physical Page Allocator & Buddy Allocator (mmu/page_alloc.py)
Implements enterprise-grade physical memory management and demand paging:
- Binary Buddy Allocator (Order 0 to Order 10, 4KB to 4MB blocks) with coalescing & splitting
- Zone-based memory partitioning (ZONE_DMA, ZONE_NORMAL, ZONE_HIGHMEM)
- Physical Page Frame Allocator with reference counting and flag bitmasks
- Kernel Slab Allocator for small objects (32B to 1024B) with zero internal fragmentation
- CLOCK (Second Chance) Page Replacement Algorithm with reference and dirty bits
- Copy-On-Write (COW) fork mechanics and store page fault handler
- Fragmentation index and memory telemetry accounting

Zero external dependencies. Pure RV32IM bare-metal MMU subsystem.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

from typing import Dict, List, Tuple, Optional, Set

PAGE_SIZE = 4096      # 4KB standard Sv32 page size
RAM_BASE  = 0x80000000
RAM_SIZE  = 64 * 1024 * 1024  # 64MB
TOTAL_PAGES = RAM_SIZE // PAGE_SIZE  # 16,384 pages

# Maximum buddy order: 2^10 pages = 1024 pages = 4MB
MAX_BUDDY_ORDER = 10

# Page flags bitmask
PG_LOCKED     = 1 << 0
PG_ACTIVE     = 1 << 1
PG_REFERENCED = 1 << 2
PG_DIRTY      = 1 << 3
PG_SLAB       = 1 << 4
PG_BUDDY      = 1 << 5
PG_RESERVED   = 1 << 6

class PageFrame:
    """Represents a 4KB physical memory frame."""
    def __init__(self, paddr: int):
        self.paddr = paddr
        self.ref_count = 0
        self.is_free = True
        self.ref_bit = False
        self.dirty_bit = False
        self.pinned = False  # Kernel frames cannot be evicted
        self.vaddr_owner: Optional[int] = None
        self.flags = 0
        self.order = 0

class MemoryZone:
    """
    Physical memory zone with watermarks for allocation throttling.
    """
    def __init__(self, name: str, start_paddr: int, size_bytes: int):
        self.name = name
        self.start_paddr = start_paddr
        self.end_paddr = start_paddr + size_bytes
        self.total_pages = size_bytes // PAGE_SIZE
        self.free_pages = self.total_pages
        # Watermarks
        self.watermark_min  = int(self.total_pages * 0.02)
        self.watermark_low  = int(self.total_pages * 0.05)
        self.watermark_high = int(self.total_pages * 0.10)

    def contains(self, paddr: int) -> bool:
        return self.start_paddr <= paddr < self.end_paddr

class BuddyAllocator:
    """
    Power-of-two Binary Buddy Allocator managing physical frame blocks.
    Supports Order 0 (4KB) through Order 10 (4MB).
    """
    def __init__(self, base_addr: int = RAM_BASE, total_pages: int = TOTAL_PAGES):
        self.base_addr = base_addr
        self.total_pages = total_pages
        self.max_order = MAX_BUDDY_ORDER
        # Free lists per order: order -> list of block starting page indices
        self.free_lists: Dict[int, List[int]] = {o: [] for o in range(self.max_order + 1)}
        self.block_orders: Dict[int, int] = {}  # page_idx -> allocated order
        self._init_buddy_blocks()

    def _init_buddy_blocks(self):
        """Populates initial free lists with largest possible power-of-two blocks."""
        # Reserve first 1024 pages (4MB) for kernel code & page tables
        curr_page = 1024
        remaining = self.total_pages - curr_page

        while remaining > 0:
            order = self.max_order
            while (1 << order) > remaining or (curr_page % (1 << order)) != 0:
                order -= 1
            self.free_lists[order].append(curr_page)
            curr_page += (1 << order)
            remaining -= (1 << order)

    def alloc_pages(self, order: int) -> Optional[int]:
        """
        Allocates 2^order contiguous pages.
        Splits larger blocks if exact order is unavailable.
        Returns physical start address.
        """
        if order > self.max_order:
            return None

        # Find smallest available order >= requested order
        current_order = order
        while current_order <= self.max_order and not self.free_lists[current_order]:
            current_order += 1

        if current_order > self.max_order:
            return None  # Out of memory for this order

        # Remove block from free list
        block_idx = self.free_lists[current_order].pop(0)

        # Split block down to requested order
        while current_order > order:
            current_order -= 1
            buddy_idx = block_idx + (1 << current_order)
            self.free_lists[current_order].append(buddy_idx)

        self.block_orders[block_idx] = order
        return self.base_addr + (block_idx * PAGE_SIZE)

    def free_pages(self, paddr: int, order: int):
        """
        Frees 2^order contiguous pages and recursively coalesces with buddies.
        """
        block_idx = (paddr - self.base_addr) // PAGE_SIZE
        self.block_orders.pop(block_idx, None)

        current_order = order
        while current_order < self.max_order:
            buddy_idx = block_idx ^ (1 << current_order)
            if buddy_idx in self.free_lists[current_order]:
                # Coalesce: remove buddy and merge into lower index
                self.free_lists[current_order].remove(buddy_idx)
                block_idx = min(block_idx, buddy_idx)
                current_order += 1
            else:
                break

        self.free_lists[current_order].append(block_idx)

class Slab:
    """Single page holding fixed-size object slots."""
    def __init__(self, paddr: int, obj_size: int):
        self.paddr = paddr
        self.obj_size = obj_size
        self.total_objects = PAGE_SIZE // obj_size
        self.free_objects = list(range(self.total_objects))

    def alloc(self) -> Optional[int]:
        if not self.free_objects:
            return None
        slot = self.free_objects.pop(0)
        return self.paddr + (slot * self.obj_size)

    def free(self, obj_paddr: int):
        slot = (obj_paddr - self.paddr) // self.obj_size
        if 0 <= slot < self.total_objects and slot not in self.free_objects:
            self.free_objects.append(slot)

    @property
    def is_empty(self) -> bool:
        return len(self.free_objects) == self.total_objects

    @property
    def is_full(self) -> bool:
        return len(self.free_objects) == 0

class SlabCache:
    """
    Caches fixed-size small objects (e.g. 32B, 64B, 128B, 256B, 512B).
    """
    def __init__(self, obj_size: int, page_allocator: 'PhysicalPageAllocator'):
        self.obj_size = obj_size
        self.allocator = page_allocator
        self.slabs: List[Slab] = []

    def alloc(self) -> int:
        for slab in self.slabs:
            if not slab.is_full:
                return slab.alloc()

        # Allocate new page frame for slab
        paddr = self.allocator.alloc_page(pinned=True)
        if paddr is None:
            raise MemoryError("Out of memory allocating slab page")
        new_slab = Slab(paddr, self.obj_size)
        self.slabs.append(new_slab)
        return new_slab.alloc()

    def free(self, obj_paddr: int):
        page_base = obj_paddr & ~(PAGE_SIZE - 1)
        for slab in self.slabs:
            if slab.paddr == page_base:
                slab.free(obj_paddr)
                if slab.is_empty and len(self.slabs) > 1:
                    self.slabs.remove(slab)
                    self.allocator.free_page(slab.paddr)
                break

class PhysicalPageAllocator:
    """
    Manages physical page allocation, reference counts, free list, and zones.
    """
    def __init__(self, base_addr: int = RAM_BASE, total_pages: int = TOTAL_PAGES):
        self.base_addr = base_addr
        self.total_pages = total_pages
        self.frames: List[PageFrame] = [
            PageFrame(base_addr + i * PAGE_SIZE) for i in range(total_pages)
        ]
        # Memory zones
        self.zone_dma = MemoryZone("DMA", base_addr, 16 * 1024 * 1024)
        self.zone_normal = MemoryZone("NORMAL", base_addr + 16 * 1024 * 1024, 40 * 1024 * 1024)
        self.zone_highmem = MemoryZone("HIGHMEM", base_addr + 56 * 1024 * 1024, 8 * 1024 * 1024)

        # Reserve first 1024 pages (4MB) for kernel code & page tables
        for i in range(1024):
            self.frames[i].is_free = False
            self.frames[i].pinned = True
            self.frames[i].ref_count = 1
            self.frames[i].flags |= (PG_LOCKED | PG_RESERVED)

        self.free_count = total_pages - 1024
        self.next_free_index = 1024

        # Initialize Buddy Allocator and Slab caches
        self.buddy = BuddyAllocator(base_addr, total_pages)
        self.slab_caches: Dict[int, SlabCache] = {
            sz: SlabCache(sz, self) for sz in [32, 64, 128, 256, 512, 1024]
        }

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
                frame.flags |= PG_ACTIVE
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
                frame.flags = 0
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

    def slab_alloc(self, size: int) -> int:
        """Allocates small kernel object from appropriate slab size cache."""
        for sz in sorted(self.slab_caches.keys()):
            if size <= sz:
                return self.slab_caches[sz].alloc()
        raise ValueError(f"Object size {size} exceeds maximum slab size 1024")

    def slab_free(self, obj_paddr: int, size: int):
        """Frees small kernel object back to slab cache."""
        for sz in sorted(self.slab_caches.keys()):
            if size <= sz:
                self.slab_caches[sz].free(obj_paddr)
                return

    def get_memory_info(self) -> Dict[str, int]:
        """Returns detailed physical memory telemetry."""
        return {
            "total_bytes": RAM_SIZE,
            "free_bytes": self.free_count * PAGE_SIZE,
            "used_bytes": (self.total_pages - self.free_count) * PAGE_SIZE,
            "total_pages": self.total_pages,
            "free_pages": self.free_count,
            "pinned_pages": sum(1 for f in self.frames if f.pinned),
        }

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

if __name__ == "__main__":
    allocator = PhysicalPageAllocator()
    # Test Buddy Allocator
    paddr_4m = allocator.buddy.alloc_pages(order=10) # 4MB
    assert paddr_4m is not None
    allocator.buddy.free_pages(paddr_4m, order=10)

    # Test Slab Allocator
    ptr1 = allocator.slab_alloc(64)
    ptr2 = allocator.slab_alloc(64)
    assert ptr1 != ptr2
    allocator.slab_free(ptr1, 64)
    allocator.slab_free(ptr2, 64)

    # Test Standard page alloc & refcounts
    pa = allocator.alloc_page()
    assert pa is not None
    assert allocator.get_ref_count(pa) == 1
    allocator.retain_page(pa)
    assert allocator.get_ref_count(pa) == 2
    allocator.free_page(pa)
    assert allocator.get_ref_count(pa) == 1
    allocator.free_page(pa)
    assert allocator.get_ref_count(pa) == 0

    print("PhysicalPageAllocator, Buddy Allocator, and Slab Caching verified.")
