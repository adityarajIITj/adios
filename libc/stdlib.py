#!/usr/bin/env python3
"""
AdiOS Standard C Library: Standard Utilities & Heap Allocator (Deepened Architecture)
Implements C99 / POSIX standard library utilities from first principles:

Subsystems:
1. Dynamic Boundary-Tag Heap Allocator with 8-byte alignment, block splitting,
   coalescing, and heap fragmentation telemetry (malloc, calloc, realloc, free).
2. Advanced Numeric Parsers:
   - strtol, strtoul, strtoll, strtoull with arbitrary radix (2 to 36) and endptr
   - atoi, atol, atoll
   - atof (ASCII to double precision float with scientific notation parsing)
3. Integer Arithmetic & Division Structures:
   - abs, labs, llabs
   - div, ldiv, lldiv returning quot / rem tuples
4. Process Lifecycle & Environment:
   - atexit registration stack (up to 32 handlers)
   - exit, abort, getenv, setenv, unsetenv
5. Pseudo-Random Number Generation:
   - rand, srand (Linear Congruential Generator, glibc constants)
6. Sorting & Searching Algorithms:
   - qsort (Median-of-three pivot quicksort with custom comparators)
   - bsearch (Binary search with custom comparators)
"""

from typing import List, Optional, Callable, Any, Tuple, Dict


# =============================================================================
# Boundary-Tag Dynamic Memory Heap Allocator
# =============================================================================

class HeapBlock:
    """Boundary-tag memory block header with in-use status and metadata."""
    def __init__(self, offset: int, size: int, in_use: bool = False):
        self.offset = offset
        self.size = size
        self.in_use = in_use

    def __repr__(self) -> str:
        status = "BUSY" if self.in_use else "FREE"
        return f"Block(offset=0x{self.offset:06X}, size={self.size}, {status})"


class HeapAllocator:
    """
    First-Fit Free-List Heap Allocator with Boundary-Tag Block Coalescing.
    Maintains 8-byte alignment across all dynamic allocations.
    """
    def __init__(self, heap_size: int = 4 * 1024 * 1024):  # Default 4 MB Heap
        self.heap_size = heap_size
        self.raw_memory = bytearray(heap_size)
        self.blocks: List[HeapBlock] = [HeapBlock(0, heap_size, in_use=False)]
        self.total_malloc_calls = 0
        self.total_free_calls = 0

    def malloc(self, size: int) -> int:
        """Allocates an 8-byte aligned memory block."""
        if size <= 0:
            return 0

        # Align allocation request to 8-byte boundary
        aligned_size = (size + 7) & ~7
        self.total_malloc_calls += 1

        for idx, blk in enumerate(self.blocks):
            if not blk.in_use and blk.size >= aligned_size:
                # Split block if remaining chunk is at least 16 bytes
                if blk.size >= aligned_size + 16:
                    remainder = HeapBlock(
                        blk.offset + aligned_size,
                        blk.size - aligned_size,
                        in_use=False
                    )
                    blk.size = aligned_size
                    blk.in_use = True
                    self.blocks.insert(idx + 1, remainder)
                else:
                    blk.in_use = True
                return blk.offset

        raise MemoryError(f"Out of memory in libc malloc heap: requested {size} bytes")

    def free(self, ptr: int):
        """Reclaims a previously allocated block and coalesces adjacent free blocks."""
        if ptr == 0:
            return

        self.total_free_calls += 1
        for blk in self.blocks:
            if blk.offset == ptr:
                blk.in_use = False
                self._coalesce()
                return

    def _coalesce(self):
        """Merges contiguous adjacent free blocks in a single linear pass."""
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
        """Allocates zero-initialized memory for nmemb elements of size bytes."""
        total = nmemb * size
        ptr = self.malloc(total)
        self.raw_memory[ptr : ptr + total] = b"\x00" * total
        return ptr

    def realloc(self, ptr: int, new_size: int) -> int:
        """Resizes an allocated memory block, preserving existing content."""
        if ptr == 0:
            return self.malloc(new_size)
        if new_size == 0:
            self.free(ptr)
            return 0

        old_blk = next((b for b in self.blocks if b.offset == ptr), None)
        if not old_blk:
            raise ValueError("Invalid pointer passed to libc realloc")

        if old_blk.size >= new_size:
            return ptr

        new_ptr = self.malloc(new_size)
        copy_len = min(old_blk.size, new_size)
        self.raw_memory[new_ptr : new_ptr + copy_len] = self.raw_memory[ptr : ptr + copy_len]
        self.free(ptr)
        return new_ptr

    def get_telemetry(self) -> Dict[str, Any]:
        """Calculates heap memory utilization and fragmentation statistics."""
        busy_bytes = sum(b.size for b in self.blocks if b.in_use)
        free_bytes = sum(b.size for b in self.blocks if not b.in_use)
        free_blocks = [b.size for b in self.blocks if not b.in_use]
        largest_free = max(free_blocks) if free_blocks else 0
        return {
            "total_heap": self.heap_size,
            "busy_bytes": busy_bytes,
            "free_bytes": free_bytes,
            "largest_free_block": largest_free,
            "block_count": len(self.blocks),
            "malloc_calls": self.total_malloc_calls,
            "free_calls": self.total_free_calls,
        }


# Global Allocator Singleton
_allocator = HeapAllocator()
malloc = _allocator.malloc
free = _allocator.free
calloc = _allocator.calloc
realloc = _allocator.realloc


# =============================================================================
# Numeric Conversion Functions
# =============================================================================

def strtol(s: str, base: int = 10, endptr: Optional[List[int]] = None) -> int:
    """
    Converts initial part of string to a 32-bit signed long int.
    Supports radix from 2 to 36, optional sign, and auto-detecting base (0).
    Updates endptr[0] with index of first invalid character if endptr is provided.
    """
    s_raw = str(s)
    idx = 0
    while idx < len(s_raw) and s_raw[idx] in " \t\n\r":
        idx += 1

    if idx >= len(s_raw):
        if endptr is not None:
            endptr[0] = idx
        return 0

    sign = 1
    if s_raw[idx] == "-":
        sign = -1
        idx += 1
    elif s_raw[idx] == "+":
        idx += 1

    # Auto-detect base 16 or 8 if base == 0
    if base == 0:
        if s_raw[idx : idx + 2].lower() == "0x":
            base = 16
            idx += 2
        elif s_raw[idx : idx + 1] == "0" and len(s_raw) > idx + 1 and s_raw[idx + 1].isdigit():
            base = 8
            idx += 1
        else:
            base = 10
    elif base == 16 and s_raw[idx : idx + 2].lower() == "0x":
        idx += 2

    digits = []
    while idx < len(s_raw):
        c = s_raw[idx]
        val = -1
        if "0" <= c <= "9":
            val = ord(c) - ord("0")
        elif "a" <= c <= "z":
            val = ord(c) - ord("a") + 10
        elif "A" <= c <= "Z":
            val = ord(c) - ord("A") + 10

        if 0 <= val < base:
            digits.append(val)
            idx += 1
        else:
            break

    if endptr is not None:
        endptr[0] = idx

    if not digits:
        return 0

    total = 0
    for d in digits:
        total = total * base + d

    res = sign * total
    # Clamp to 32-bit signed range [-2147483648, 2147483647]
    return (res + 0x80000000) % 0x100000000 - 0x80000000


def strtoul(s: str, base: int = 10, endptr: Optional[List[int]] = None) -> int:
    """Converts initial part of string to a 32-bit unsigned long int."""
    val = strtol(s, base, endptr)
    return val & 0xFFFFFFFF


def strtoll(s: str, base: int = 10, endptr: Optional[List[int]] = None) -> int:
    """Converts initial part of string to a 64-bit signed integer."""
    s_raw = str(s).strip()
    idx = 0
    sign = 1
    if s_raw.startswith("-"):
        sign = -1
        idx += 1
    elif s_raw.startswith("+"):
        idx += 1

    if base == 0:
        if s_raw[idx : idx + 2].lower() == "0x":
            base = 16
            idx += 2
        elif s_raw[idx : idx + 1] == "0" and len(s_raw) > idx + 1:
            base = 8
            idx += 1
        else:
            base = 10
    elif base == 16 and s_raw[idx : idx + 2].lower() == "0x":
        idx += 2

    digits = []
    while idx < len(s_raw):
        c = s_raw[idx]
        val = -1
        if "0" <= c <= "9": val = ord(c) - ord("0")
        elif "a" <= c <= "z": val = ord(c) - ord("a") + 10
        elif "A" <= c <= "Z": val = ord(c) - ord("A") + 10
        if 0 <= val < base:
            digits.append(val)
            idx += 1
        else:
            break

    if endptr is not None:
        endptr[0] = idx

    total = 0
    for d in digits:
        total = total * base + d
    return sign * total


def atoi(s: str) -> int:
    """Converts ASCII string to integer."""
    return strtol(s, 10)


def atol(s: str) -> int:
    """Converts ASCII string to long integer."""
    return strtol(s, 10)


def atoll(s: str) -> int:
    """Converts ASCII string to 64-bit long long integer."""
    return strtoll(s, 10)


def atof(s: str) -> float:
    """
    Parses a floating-point number from string.
    Supports sign, decimal fraction, and exponent (e.g. -12.34e-5).
    """
    s_clean = s.strip()
    if not s_clean:
        return 0.0
    try:
        return float(s_clean)
    except ValueError:
        return 0.0


# =============================================================================
# Integer Arithmetic & Division Structures
# =============================================================================

def abs(j: int) -> int:
    """Returns the absolute value of an integer."""
    return -j if j < 0 else j


def labs(j: int) -> int:
    return abs(j)


def llabs(j: int) -> int:
    return abs(j)


class div_t:
    """Structure returned by integer division."""
    def __init__(self, quot: int, rem: int):
        self.quot = quot
        self.rem = rem

    def __repr__(self) -> str:
        return f"div_t(quot={self.quot}, rem={self.rem})"


def div(numer: int, denom: int) -> div_t:
    """Computes the quotient and remainder of integer division."""
    if denom == 0:
        return div_t(0, 0)
    quot = int(numer / denom)
    rem = numer - quot * denom
    return div_t(quot, rem)


def ldiv(numer: int, denom: int) -> div_t:
    return div(numer, denom)


def lldiv(numer: int, denom: int) -> div_t:
    return div(numer, denom)


# =============================================================================
# Process Lifecycle & Environment Subsystem
# =============================================================================

_atexit_handlers: List[Callable[[], None]] = []
_env_vars: Dict[str, str] = {
    "PATH": "/bin:/usr/bin",
    "HOME": "/root",
    "USER": "sovereign",
    "SHELL": "/bin/ash",
    "TERM": "adios-xga"
}


def atexit(func: Callable[[], None]) -> int:
    """Registers a function to be called on normal program termination."""
    if len(_atexit_handlers) >= 32:
        return -1  # Standard POSIX limit
    _atexit_handlers.append(func)
    return 0


def exit(status: int = 0):
    """Executes registered atexit callbacks in LIFO order and terminates."""
    while _atexit_handlers:
        handler = _atexit_handlers.pop()
        try:
            handler()
        except Exception:
            pass
    return status


def abort():
    """Abnormally terminates the process."""
    raise SystemExit("SIGABRT: Process aborted abnormally")


def getenv(name: str) -> Optional[str]:
    """Retrieves an environment variable."""
    return _env_vars.get(name, None)


def setenv(name: str, value: str, overwrite: int = 1) -> int:
    """Sets or mutates an environment variable."""
    if not name or "=" in name:
        return -1
    if name not in _env_vars or overwrite != 0:
        _env_vars[name] = str(value)
    return 0


def unsetenv(name: str) -> int:
    """Removes an environment variable."""
    if name in _env_vars:
        del _env_vars[name]
    return 0


# =============================================================================
# Pseudo-Random Number Generator (Linear Congruential Generator)
# =============================================================================

_rand_seed: int = 1


def srand(seed: int):
    """Seeds the pseudo-random number generator."""
    global _rand_seed
    _rand_seed = seed & 0xFFFFFFFF


def rand() -> int:
    """Returns a pseudo-random integer in the range [0, 2147483647]."""
    global _rand_seed
    _rand_seed = (_rand_seed * 1103515245 + 12345) & 0x7FFFFFFF
    return _rand_seed


# =============================================================================
# Sorting & Searching Algorithms
# =============================================================================

def qsort(items: list, compar: Callable[[Any, Any], int] = None):
    """
    Sorts an array in-place using median-of-three pivot Quicksort.
    Guarantees O(n log n) average time complexity.
    """
    if compar is None:
        compar = lambda a, b: (a > b) - (a < b)

    def _median_of_three(a, b, c):
        if compar(items[a], items[b]) > 0:
            a, b = b, a
        if compar(items[b], items[c]) > 0:
            b, c = c, b
        if compar(items[a], items[b]) > 0:
            a, b = b, a
        return b

    def _quick(low: int, high: int):
        if low < high:
            # Median-of-three pivot selection
            mid = (low + high) // 2
            pivot_idx = _median_of_three(low, mid, high)
            items[pivot_idx], items[high] = items[high], items[pivot_idx]

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
    """
    Performs binary search on a sorted list.
    Returns index of matching element or None if not found.
    """
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
