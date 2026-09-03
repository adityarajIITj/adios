#!/usr/bin/env python3
"""
Test Suite: Block J Zero-Dependency Standard C Library (libc)
Verifies:
1. libc/string: ANSI/ISO C string and memory manipulation routines
2. libc/stdio: Formatted I/O (sprintf/snprintf) and buffered file streams
3. libc/stdlib: Free-list heap allocator, numeric parsers, qsort, bsearch, rand
4. libc/math: Taylor-series trigonometry, Newton-Raphson sqrt, exp, log, pow
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import libc.string as c_str
import libc.stdio as c_io
import libc.stdlib as c_lib
import libc.math as c_m

def test_libc_block_j_suite():
    print("[Test LibC Block J] Initializing Standard C Library Verification...")

    # 1. Test String & Memory Functions
    print("  -> Testing libc/string...")
    s = b"Sovereign Operating System\x00"
    assert c_str.strlen(s) == 26
    assert c_str.strcmp(b"alpha\x00", b"alpha\x00") == 0
    assert c_str.strcmp(b"alpha\x00", b"beta\x00") < 0
    assert c_str.strncmp(b"abcdef\x00", b"abcXYZ\x00", 3) == 0

    buf = bytearray(32)
    c_str.strcpy(buf, b"AdiOS\x00")
    assert buf[:6] == b"AdiOS\x00"
    c_str.strcat(buf, b"_Core\x00")
    assert buf[:11] == b"AdiOS_Core\x00"

    assert c_str.strchr(s, ord('O')) == 10
    assert c_str.strrchr(s, ord('e')) == 24
    assert c_str.strstr(s, b"System\x00") == 20
    assert c_str.strstr(s, b"NotFound\x00") == -1

    # Memory functions
    mem = bytearray(16)
    c_str.memset(mem, 0xAA, 8)
    assert mem[:8] == b"\xAA" * 8
    assert mem[8:] == b"\x00" * 8

    dst = bytearray(16)
    c_str.memcpy(dst, mem, 8)
    assert dst[:8] == b"\xAA" * 8
    assert c_str.memcmp(mem, dst, 8) == 0
    print("  -> [PASS] libc/string functions verified.")

    # 2. Test Stdio Formatted I/O & Streams
    print("  -> Testing libc/stdio...")
    formatted = c_io.sprintf("Node: %s, PID: %d, Addr: 0x%08X, Hex: %x", "AdiOS", 42, 0x80001000, 255)
    assert formatted == "Node: AdiOS, PID: 42, Addr: 0x80001000, Hex: ff"

    sn_res = c_io.snprintf(10, "1234567890ABCDEF")
    assert len(sn_res) == 9

    # Test file streams
    fp = c_io.fopen("virtual_file.bin", "w+")
    payload = b"ADIFS_STANDARD_C_LIBRARY_BUFFERED_STREAM"
    written_units = c_io.fwrite(payload, 1, len(payload), fp)
    assert written_units == len(payload)

    c_io.fseek(fp, 6, c_io.SEEK_SET)
    assert c_io.ftell(fp) == 6

    chunk = c_io.fread(fp, 1, 8)
    assert chunk == b"STANDARD"
    c_io.fclose(fp)
    print("  -> [PASS] libc/stdio functions verified.")

    # 3. Test Stdlib Heap Allocator & Utilities
    print("  -> Testing libc/stdlib...")
    p1 = c_lib.malloc(64)
    p2 = c_lib.malloc(128)
    p3 = c_lib.malloc(256)
    assert p1 < p2 < p3

    # Free middle and coalesce
    c_lib.free(p2)
    # Reallocate should reuse p2 block
    p2_reuse = c_lib.malloc(100)
    assert p2_reuse == p2

    c_lib.free(p1)
    c_lib.free(p2_reuse)
    c_lib.free(p3)

    # Conversions
    assert c_lib.atoi("12345") == 12345
    assert c_lib.atoi("-987") == -987
    assert c_lib.strtol("0xDeadBeef", 16) == -559038737  # 32-bit signed

    # Quicksort & Binary Search
    numbers = [64, 25, 12, 22, 11, 90, 42]
    c_lib.qsort(numbers)
    assert numbers == [11, 12, 22, 25, 42, 64, 90]
    idx_42 = c_lib.bsearch(42, numbers)
    assert idx_42 == 4
    assert c_lib.bsearch(999, numbers) is None

    # Rand
    c_lib.srand(1337)
    r1 = c_lib.rand()
    r2 = c_lib.rand()
    assert r1 != r2
    print("  -> [PASS] libc/stdlib functions verified.")

    # 4. Test Math Subsystem
    print("  -> Testing libc/math...")
    assert c_m.fabs(-42.5) == 42.5
    assert c_m.floor(3.7) == 3
    assert c_m.ceil(3.2) == 4

    assert c_m.fabs(c_m.sqrt(25.0) - 5.0) < 1e-6
    assert c_m.fabs(c_m.sin(0.0)) < 1e-6
    assert c_m.fabs(c_m.sin(c_m.PI / 2.0) - 1.0) < 1e-6
    assert c_m.fabs(c_m.cos(0.0) - 1.0) < 1e-6
    assert c_m.fabs(c_m.cos(c_m.PI) - (-1.0)) < 1e-6
    assert c_m.fabs(c_m.pow(2.0, 8.0) - 256.0) < 1e-4
    assert c_m.fabs(c_m.exp(0.0) - 1.0) < 1e-6
    assert c_m.fabs(c_m.log(c_m.E) - 1.0) < 1e-4
    print("  -> [PASS] libc/math functions verified.")

    print("\n[Test LibC Block J] ALL BLOCK J STANDARD C LIBRARY TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_libc_block_j_suite()
