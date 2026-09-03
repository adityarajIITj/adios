#!/usr/bin/env python3
"""
AdiOS Standard C Library: Standard Utilities & Heap Allocator (stdlib.py)
Implements C99 dynamic memory management (malloc, free, calloc, realloc)
using an in-house boundary-tag heap allocator with coalescing,
numeric parsers (strtol, atoi), qsort, bsearch, and rand/srand.
Zero external dependencies.
"""

from typing import List, Optional, Callable

class HeapBlock:
    """
    Boundary-tag memory block header.
    """
    def __init__(self, offset: int, size: int, in_use: bool = False):
        self.offset = offset
        self.size = size
        self.in_use = in_use

class HeapAllocator:
    """
    First-Fit Free-List Heap Allocator with Block Coalescing.
    """
    def __init__(self, heap_size: int = 4 * 1024 * 1024): # 4 MB Heap
        self.heap_size = heap_size
        self.raw_memory = bytearray(heap_size)
        self.blocks: List[HeapBlock] = [HeapBlock(0, heap_size, in_use=False)]

    def malloc(self, size: int) -> int:
        if size <= 0:
            return 0

        # Align allocation to 8 bytes
        aligned_size = (size + 7) & ~7

        for idx, blk in enumerate(self.blocks):
            if not blk.in_use and blk.size >= aligned_size:
                # Split block if remainder is large enough
                if blk.size >= aligned_size + 16:
                    remainder = HeapBlock(blk.offset + aligned_size, blk.size - aligned_size, in_use=False)
                    blk.size = aligned_size
                    blk.in_use = True
                    self.blocks.insert(idx + 1, remainder)
                else:
                    blk.in_use = True
                return blk.offset

        raise MemoryError("Out of memory in libc malloc heap")

    def free(self, ptr: int):
        if ptr == 0:
            return

        for idx, blk in enumerate(self.blocks):
            if blk.offset == ptr:
                blk.in_use = False
                self._coalesce()
                return

    def _coalesce(self):
        """Merges adjacent free memory blocks."""
        i = 0
        while i < len(self.blocks) - 1:
            curr = self.blocks[i]
            nxt = self.blocks[i + 1]
            if not curr.in_use and not nxt.in_use:
                curr.size += nxt.size
                del self.blocks[i + 1]
            else:
                i += 1

    def calloc(self, nmemb: int, size: int) -> int:
        total = nmemb * size
        ptr = self.malloc(total)
        self.raw_memory[ptr:ptr + total] = b"\x00" * total
        return ptr

    def realloc(self, ptr: int, new_size: int) -> int:
        if ptr == 0:
            return self.malloc(new_size)
        if new_size == 0:
            self.free(ptr)
            return 0

        old_blk = next((b for b in self.blocks if b.offset == ptr), None)
        if not old_blk:
            raise ValueError("Invalid pointer passed to realloc")

        if old_blk.size >= new_size:
            return ptr

        new_ptr = self.malloc(new_size)
        copy_len = min(old_blk.size, new_size)
        self.raw_memory[new_ptr:new_ptr + copy_len] = self.raw_memory[ptr:ptr + copy_len]
        self.free(ptr)
        return new_ptr

# Global allocator instance
_allocator = HeapAllocator()
malloc = _allocator.malloc
free = _allocator.free
calloc = _allocator.calloc
realloc = _allocator.realloc

# --- Numeric Conversion Functions ---

def atoi(s: str) -> int:
    return strtol(s, 10)

def atol(s: str) -> int:
    return strtol(s, 10)

def strtol(s: str, base: int = 10) -> int:
    """Converts a string to a 32-bit signed long int."""
    s = s.strip()
    if not s:
        return 0

    sign = 1
    if s[0] == '-':
        sign = -1
        s = s[1:]
    elif s[0] == '+':
        s = s[1:]

    if base == 16 or (base == 0 and s.startswith(('0x', '0X'))):
        if s.startswith(('0x', '0X')):
            s = s[2:]
        base = 16
    elif base == 0 and s.startswith('0') and len(s) > 1:
        base = 8
    elif base == 0:
        base = 10

    digits = []
    for c in s:
        val = -1
        if '0' <= c <= '9': val = ord(c) - ord('0')
        elif 'a' <= c <= 'z': val = ord(c) - ord('a') + 10
        elif 'A' <= c <= 'Z': val = ord(c) - ord('A') + 10
        if 0 <= val < base:
            digits.append(val)
        else:
            break

    if not digits:
        return 0

    total = 0
    for d in digits:
        total = total * base + d

    res = sign * total
    return (res + 0x80000000) % 0x100000000 - 0x80000000

def abs(j: int) -> int:
    return -j if j < 0 else j

# --- Pseudo-Random Number Generator ---

_rand_seed = 1

def srand(seed: int):
    global _rand_seed
    _rand_seed = seed & 0xFFFFFFFF

def rand() -> int:
    global _rand_seed
    _rand_seed = (_rand_seed * 1103515245 + 12345) & 0x7FFFFFFF
    return _rand_seed

# --- Sorting & Searching ---

def qsort(items: list, compar: Callable[[Any, Any], int] = None):
    """Sorts items in-place using quicksort."""
    if compar is None:
        compar = lambda a, b: (a > b) - (a < b)

    def _quick(low, high):
        if low < high:
            pivot = items[high]
            i = low - 1
            for j in range(low, high):
                if compar(items[j], pivot) <= 0:
                    i += 1
                    items[i], items[j] = items[j], items[i]
            items[i + 1], items[high] = items[high], items[i + 1]
            pi = i + 1
            _quick(low, pi - 1)
            _quick(pi + 1, high)

    if len(items) > 1:
        _quick(0, len(items) - 1)

def bsearch(key: Any, items: list, compar: Callable[[Any, Any], int] = None) -> Optional[int]:
    """Performs binary search on sorted items list."""
    if compar is None:
        compar = lambda a, b: (a > b) - (a < b)

    low = 0
    high = len(items) - 1
    while low <= high:
        mid = (low + high) // 2
        cmp_res = compar(key, items[mid])
        if cmp_res == 0:
            return mid
        elif cmp_res < 0:
            high = mid - 1
        else:
            low = mid + 1
    return None

if __name__ == "__main__":
    p1 = malloc(128)
    p2 = malloc(256)
    assert p1 == 0 and p2 == 128
    free(p1)
    p3 = malloc(64)
    assert p3 == 0 # Reused freed block
    free(p2)
    free(p3)

    assert atoi("  -42") == -42
    assert strtol("0x1F", 16) == 31

    arr = [9, 3, 7, 1, 5]
    qsort(arr)
    assert arr == [1, 3, 5, 7, 9]
    idx = bsearch(7, arr)
    assert idx == 3
    print("LibC stdlib (Heap, numeric, qsort, bsearch) verified.")
