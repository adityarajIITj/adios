#!/usr/bin/env python3
"""
AdiOS Standard C Library: Memory & String Subsystem (string.py)
Implements ANSI/ISO C99 standard memory and string manipulation functions
from first principles. Zero external dependencies.
"""

def strlen(s: bytes) -> int:
    """Returns number of bytes before the first null terminator."""
    idx = 0
    while idx < len(s) and s[idx] != 0:
        idx += 1
    return idx

def strcmp(s1: bytes, s2: bytes) -> int:
    """Compares two null-terminated strings lexicographically."""
    i = 0
    while True:
        b1 = s1[i] if i < len(s1) else 0
        b2 = s2[i] if i < len(s2) else 0
        if b1 != b2:
            return b1 - b2
        if b1 == 0:
            return 0
        i += 1

def strncmp(s1: bytes, s2: bytes, n: int) -> int:
    """Compares up to n bytes of two strings."""
    for i in range(n):
        b1 = s1[i] if i < len(s1) else 0
        b2 = s2[i] if i < len(s2) else 0
        if b1 != b2:
            return b1 - b2
        if b1 == 0:
            return 0
    return 0

def strcpy(dst: bytearray, src: bytes) -> bytearray:
    """Copies null-terminated string src into dst."""
    i = 0
    while i < len(src) and src[i] != 0:
        if i < len(dst):
            dst[i] = src[i]
        else:
            dst.append(src[i])
        i += 1
    if i < len(dst):
        dst[i] = 0
    else:
        dst.append(0)
    return dst

def strncpy(dst: bytearray, src: bytes, n: int) -> bytearray:
    """Copies up to n bytes of src into dst. Padds with null if src < n."""
    src_len = strlen(src)
    for i in range(n):
        val = src[i] if i < src_len else 0
        if i < len(dst):
            dst[i] = val
        else:
            dst.append(val)
    return dst

def strcat(dst: bytearray, src: bytes) -> bytearray:
    """Concatenates null-terminated src to the end of dst."""
    dst_len = strlen(dst)
    i = 0
    while i < len(src) and src[i] != 0:
        idx = dst_len + i
        if idx < len(dst):
            dst[idx] = src[i]
        else:
            dst.append(src[i])
        i += 1
    idx = dst_len + i
    if idx < len(dst):
        dst[idx] = 0
    else:
        dst.append(0)
    return dst

def strchr(s: bytes, c: int) -> int:
    """Returns index of first occurrence of character c in s, or -1 if not found."""
    target = c & 0xFF
    for i in range(len(s)):
        if s[i] == target:
            return i
        if s[i] == 0:
            break
    if target == 0:
        return strlen(s)
    return -1

def strrchr(s: bytes, c: int) -> int:
    """Returns index of last occurrence of character c in s, or -1 if not found."""
    target = c & 0xFF
    last = -1
    for i in range(len(s)):
        if s[i] == target:
            last = i
        if s[i] == 0:
            break
    return last

def strstr(haystack: bytes, needle: bytes) -> int:
    """Finds the first occurrence of substring needle in haystack."""
    n_len = strlen(needle)
    if n_len == 0:
        return 0
    h_len = strlen(haystack)
    if n_len > h_len:
        return -1

    for i in range(h_len - n_len + 1):
        if haystack[i:i + n_len] == needle[:n_len]:
            return i
    return -1

# --- Memory Functions ---

def memcpy(dst: bytearray, src: bytes, n: int) -> bytearray:
    """Copies n bytes from memory area src to dst."""
    for i in range(n):
        if i < len(dst):
            dst[i] = src[i]
        else:
            dst.append(src[i])
    return dst

def memmove(dst: bytearray, src: bytes, n: int) -> bytearray:
    """Copies n bytes between potentially overlapping memory areas."""
    temp = bytes(src[:n])
    for i in range(n):
        if i < len(dst):
            dst[i] = temp[i]
        else:
            dst.append(temp[i])
    return dst

def memset(dst: bytearray, c: int, n: int) -> bytearray:
    """Fills the first n bytes of dst with constant byte c."""
    val = c & 0xFF
    for i in range(n):
        if i < len(dst):
            dst[i] = val
        else:
            dst.append(val)
    return dst

def memcmp(s1: bytes, s2: bytes, n: int) -> int:
    """Compares the first n bytes of two memory areas."""
    for i in range(n):
        b1 = s1[i] if i < len(s1) else 0
        b2 = s2[i] if i < len(s2) else 0
        if b1 != b2:
            return b1 - b2
    return 0

def memchr(s: bytes, c: int, n: int) -> int:
    """Scans the first n bytes of memory area s for byte c."""
    target = c & 0xFF
    for i in range(n):
        if i < len(s) and s[i] == target:
            return i
    return -1

if __name__ == "__main__":
    msg = b"Hello AdiOS\x00"
    assert strlen(msg) == 11
    assert strcmp(b"abc\x00", b"abc\x00") == 0
    assert strcmp(b"abc\x00", b"abd\x00") < 0
    assert strstr(b"Sovereign Computing\x00", b"Computing\x00") == 10

    buf = bytearray(16)
    memset(buf, 0x42, 8)
    assert buf[:8] == b"\x42" * 8
    print("LibC string & memory functions verified.")
