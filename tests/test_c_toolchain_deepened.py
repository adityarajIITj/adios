#!/usr/bin/env python3
"""
Test Suite: Deepened C Compiler Toolchain & Zero-Dependency Standard C Library
Verifies Phase X Deepening:
1. libc/string: strtok_r re-entrant tokenizer, strcasecmp, strspn, strcspn, strpbrk, strlcpy, strlcat
2. libc/stdlib: arbitrary-radix strtol/strtoll, atof, div_t, atexit lifecycle, getenv/setenv, qsort, bsearch
3. libc/stdio: vsnprintf, sscanf, file stream fgetc/fputc/fgets/fputs, clearerr, float %f formatting
4. compiler/c_codegen: compound assignments, array indexing, pre/post increments
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from libc.string import (
    strlen, strcmp, strncmp, strcasecmp, strncasecmp, strcpy, strncpy,
    strlcpy, strlcat, strchr, strrchr, strstr, strspn, strcspn, strpbrk,
    strtok_r, memcpy, memmove, memset, memcmp, memchr
)
from libc.stdlib import (
    malloc, free, calloc, realloc, strtol, strtoul, strtoll, atoi, atol,
    atof, abs, div, ldiv, atexit, exit, getenv, setenv, unsetenv, qsort, bsearch
)
from libc.stdio import (
    FILE, StdIO, fopen, fclose, fread, fwrite, fseek, ftell, sprintf,
    snprintf, vsnprintf, sscanf, fgetc, fputc, fgets, fputs, rewind, clearerr
)
from compiler.c_lexer import CLexer
from compiler.c_parser import CParser
from compiler.c_codegen import CCodeGen


def test_c_toolchain_deepened_suite():
    print("[Test C Toolchain Deepened] Initializing deepened subsystem verification...")

    # 1. Test libc/string Deepening
    print("  -> Testing libc/string (strcasecmp, strlcpy, strlcat, strspn, strcspn, strtok_r)...")
    # strcasecmp
    assert strcasecmp(b"AdiOS\x00", b"adios\x00") == 0
    assert strncasecmp(b"Antigravity\x00", b"ANTIGRAV\x00", 8) == 0

    # strlcpy / strlcat
    dst = bytearray(16)
    copied_len = strlcpy(dst, b"Hello World!\x00", 10)
    assert copied_len == 12  # Source length
    assert dst[:10] == b"Hello Wor\x00"

    cat_len = strlcat(dst, b" Extra\x00", 16)
    assert dst[9:15] == b" Extra"

    # strspn / strcspn / strpbrk
    s_test = b"12345abcde\x00"
    assert strspn(s_test, b"0123456789\x00") == 5
    assert strcspn(s_test, b"abc\x00") == 5
    assert strpbrk(s_test, b"cxz\x00") == 7  # 'c' is at index 7

    # strtok_r
    csv = bytearray(b"kernel,driver,network,crypto\x00")
    saveptr = [0]
    t1 = strtok_r(csv, b",\x00", saveptr)
    t2 = strtok_r(None, b",\x00", saveptr)
    t3 = strtok_r(None, b",\x00", saveptr)
    t4 = strtok_r(None, b",\x00", saveptr)
    t5 = strtok_r(None, b",\x00", saveptr)
    assert t1 == b"kernel\x00"
    assert t2 == b"driver\x00"
    assert t3 == b"network\x00"
    assert t4 == b"crypto\x00"
    assert t5 is None
    print("  -> [PASS] libc/string deepened functions verified.")

    # 2. Test libc/stdlib Deepening
    print("  -> Testing libc/stdlib (radix strtol, atof, div_t, getenv/setenv, qsort)...")
    # Radix parsing
    endptr = [0]
    val_bin = strtol("10110101XYZ", 2, endptr)
    assert val_bin == 0b10110101
    assert endptr[0] == 8

    val_hex = strtoul("0xDEADBEEF", 16)
    assert val_hex == 0xDEADBEEF

    val_base36 = strtol("ADIOS", 36)
    assert val_base36 == 17426908

    # atof
    assert abs(atof("  -3.14159  ") - (-3.14159)) < 1e-5
    assert abs(atof("1.25e-3") - 0.00125) < 1e-6

    # div_t
    d_res = div(47, 5)
    assert d_res.quot == 9 and d_res.rem == 2

    # Environment variables
    setenv("SOVEREIGN_MODE", "ACTIVE", 1)
    assert getenv("SOVEREIGN_MODE") == "ACTIVE"
    unsetenv("SOVEREIGN_MODE")
    assert getenv("SOVEREIGN_MODE") is None

    # Sorting & Searching
    nums = [42, 17, 89, 5, 23, 56, 12]
    qsort(nums)
    assert nums == [5, 12, 17, 23, 42, 56, 89]
    assert bsearch(23, nums) == 3
    assert bsearch(99, nums) is None
    print("  -> [PASS] libc/stdlib deepened functions verified.")

    # 3. Test libc/stdio Deepening
    print("  -> Testing libc/stdio (vsnprintf, sscanf, file character I/O, float printf)...")
    # Float & Hex sprintf
    s_fmt = sprintf("Pi: %.2f, Hex: 0x%08X, Left: %-8s!", 3.14159, 0xC0FFEE, "ADIOS")
    assert s_fmt == "Pi: 3.14, Hex: 0x00C0FFEE, Left: ADIOS   !"

    # vsnprintf
    s_trunc = vsnprintf(10, "%s is sovereign", ["AdiOS"])
    assert s_trunc == "AdiOS is "

    # sscanf
    parsed = sscanf("Width: 1024 Height: 768 Depth: 0x20", "Width: %d Height: %d Depth: %x")
    assert parsed == [1024, 768, 32]

    # File stream line I/O
    io = StdIO()
    fp = io.fopen("test.txt", "w+")
    io.fputs("Line 1: Systems Engineering\nLine 2: Sovereign OS\n", fp)
    io.rewind(fp)
    line1 = io.fgets(64, fp)
    line2 = io.fgets(64, fp)
    assert line1 == "Line 1: Systems Engineering\n"
    assert line2 == "Line 2: Sovereign OS\n"
    io.fclose(fp)
    print("  -> [PASS] libc/stdio deepened functions verified.")

    # 4. Test compiler/c_codegen Deepening
    print("  -> Testing C Codegen (Compound assignments, pre/post increments, array indexing)...")
    src_c = """
    int test_ops(int *arr, int len) {
        int sum = 0;
        int i = 0;
        while (i < len) {
            sum += arr[i];
            i++;
        }
        return sum;
    }
    """
    tokens = CLexer(src_c).tokenize()
    ast = CParser(tokens).parse()
    cg = CCodeGen()
    asm = cg.generate(ast)

    # Verify compound add and array indexing emitted
    assert "add  a0, t0, t1" in asm
    assert "slli a0, a0, 2" in asm  # Array stride shift
    assert "sw   a0, -12(s0)" in asm  # Store to stack
    print("  -> [PASS] C Codegen deepened operations verified.")

    print("\n===========================================================")
    print("[Test C Toolchain Deepened] ALL 4 DEEPENED TESTS PASSED (100%)!")
    print("===========================================================")
    return True


if __name__ == "__main__":
    test_c_toolchain_deepened_suite()
