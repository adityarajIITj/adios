#!/usr/bin/env python3
"""
AdiOS Standard C Library: Memory & String Subsystem (Deepened Architecture)
Implements ANSI/ISO C99 and POSIX.1-2008 memory and string manipulation functions
from first principles. Zero external dependencies.

Subsystems:
1. Standard string measurement and inspection (strlen, strnlen)
2. Lexicographical comparisons (strcmp, strncmp, strcasecmp, strncasecmp)
3. Copying and concatenation (strcpy, strncpy, strcat, strncat, strlcpy, strlcat)
4. Character and substring search (strchr, strrchr, strstr, strpbrk, strspn, strcspn)
5. Tokenization engines (strtok, strtok_r re-entrant tokenizer)
6. Raw memory primitives (memcpy, memmove, memset, memcmp, memchr, memrchr)
7. Fast 32-bit aligned memory block operations (memset32, memcpy32)
"""

from typing import Optional, Tuple, List


# Internal static state for non-reentrant strtok
_strtok_last: Optional[bytearray] = None
_strtok_pos: int = 0


# =============================================================================
# String Measurement & Inspection
# =============================================================================

def strlen(s: bytes) -> int:
    """Returns the number of bytes before the first null terminator."""
    idx = 0
    limit = len(s)
    while idx < limit and s[idx] != 0:
        idx += 1
    return idx


def strnlen(s: bytes, maxlen: int) -> int:
    """Returns either strlen(s) or maxlen, whichever is smaller."""
    idx = 0
    limit = min(len(s), maxlen)
    while idx < limit and s[idx] != 0:
        idx += 1
    return idx


# =============================================================================
# String Comparisons
# =============================================================================

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


def strcasecmp(s1: bytes, s2: bytes) -> int:
    """Case-insensitive comparison of two null-terminated strings."""
    i = 0
    while True:
        b1 = s1[i] if i < len(s1) else 0
        b2 = s2[i] if i < len(s2) else 0
        # Convert ASCII uppercase (65-90) to lowercase (97-122)
        c1 = b1 + 32 if 65 <= b1 <= 90 else b1
        c2 = b2 + 32 if 65 <= b2 <= 90 else b2
        if c1 != c2:
            return c1 - c2
        if c1 == 0:
            return 0
        i += 1


def strncasecmp(s1: bytes, s2: bytes, n: int) -> int:
    """Case-insensitive comparison of up to n bytes of two strings."""
    for i in range(n):
        b1 = s1[i] if i < len(s1) else 0
        b2 = s2[i] if i < len(s2) else 0
        c1 = b1 + 32 if 65 <= b1 <= 90 else b1
        c2 = b2 + 32 if 65 <= b2 <= 90 else b2
        if c1 != c2:
            return c1 - c2
        if c1 == 0:
            return 0
    return 0


# =============================================================================
# String Copying & Concatenation
# =============================================================================

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
    """Copies up to n bytes of src into dst, padding with nulls if src < n."""
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


def strncat(dst: bytearray, src: bytes, n: int) -> bytearray:
    """Appends at most n bytes from src to dst, plus a terminating null."""
    dst_len = strlen(dst)
    i = 0
    while i < n and i < len(src) and src[i] != 0:
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


def strlcpy(dst: bytearray, src: bytes, size: int) -> int:
    """
    BSD/POSIX safe string copy.
    Guarantees null termination if size > 0.
    Returns total length of string src that it tried to create.
    """
    src_len = strlen(src)
    if size > 0:
        copy_len = min(src_len, size - 1)
        for i in range(copy_len):
            if i < len(dst):
                dst[i] = src[i]
            else:
                dst.append(src[i])
        term_idx = copy_len
        if term_idx < len(dst):
            dst[term_idx] = 0
        else:
            dst.append(0)
    return src_len


def strlcat(dst: bytearray, src: bytes, size: int) -> int:
    """
    BSD/POSIX safe string concatenation.
    Guarantees null termination if dst_len < size.
    Returns initial dst_len + src_len.
    """
    dst_len = strlen(dst)
    src_len = strlen(src)
    if dst_len >= size:
        return size + src_len

    avail = size - dst_len - 1
    copy_len = min(src_len, avail)
    for i in range(copy_len):
        idx = dst_len + i
        if idx < len(dst):
            dst[idx] = src[i]
        else:
            dst.append(src[i])
    term_idx = dst_len + copy_len
    if term_idx < len(dst):
        dst[term_idx] = 0
    else:
        dst.append(0)

    return dst_len + src_len


# =============================================================================
# Searching & Scanning
# =============================================================================

def strchr(s: bytes, c: int) -> int:
    """Returns index of first occurrence of byte c in s, or -1 if not found."""
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
    """Returns index of last occurrence of byte c in s, or -1 if not found."""
    target = c & 0xFF
    last = -1
    for i in range(len(s)):
        if s[i] == target:
            last = i
        if s[i] == 0:
            break
    if target == 0:
        return strlen(s)
    return last


def strstr(haystack: bytes, needle: bytes) -> int:
    """
    Finds the first occurrence of substring needle in haystack.
    Returns starting index in haystack, or -1 if not found.
    """
    n_len = strlen(needle)
    if n_len == 0:
        return 0
    h_len = strlen(haystack)
    if n_len > h_len:
        return -1

    # Boyer-Moore-Horspool Bad Character Skip Table
    skip = [n_len] * 256
    for i in range(n_len - 1):
        skip[needle[i]] = n_len - 1 - i

    idx = 0
    while idx <= h_len - n_len:
        match = True
        for j in range(n_len - 1, -1, -1):
            if haystack[idx + j] != needle[j]:
                match = False
                break
        if match:
            return idx
        last_char = haystack[idx + n_len - 1]
        idx += skip[last_char]

    return -1


def strspn(s: bytes, accept: bytes) -> int:
    """
    Calculates the length of the initial segment of s which consists
    entirely of bytes in accept.
    """
    accept_set = set(accept[:strlen(accept)])
    count = 0
    for b in s:
        if b == 0 or b not in accept_set:
            break
        count += 1
    return count


def strcspn(s: bytes, reject: bytes) -> int:
    """
    Calculates the length of the initial segment of s which consists
    entirely of bytes NOT in reject.
    """
    reject_set = set(reject[:strlen(reject)])
    count = 0
    for b in s:
        if b == 0 or b in reject_set:
            break
        count += 1
    return count


def strpbrk(s: bytes, accept: bytes) -> int:
    """
    Locates the first occurrence in the string s of any of the bytes
    in the string accept. Returns index or -1.
    """
    accept_set = set(accept[:strlen(accept)])
    for i, b in enumerate(s):
        if b == 0:
            break
        if b in accept_set:
            return i
    return -1


# =============================================================================
# String Tokenization
# =============================================================================

def strtok_r(s: Optional[bytearray], delim: bytes, saveptr: List[Any]) -> Optional[bytearray]:
    """
    Re-entrant, thread-safe string tokenizer.
    saveptr is a list [buffer, current_offset] maintaining state across calls.
    """
    delim_set = set(delim[:strlen(delim)])
    if s is not None:
        saveptr.clear()
        saveptr.append(s)
        saveptr.append(0)
    elif not saveptr or len(saveptr) < 2:
        return None

    current_buf = saveptr[0]
    pos = saveptr[1]
    total_len = len(current_buf)

    # 1. Skip leading delimiters
    while pos < total_len and current_buf[pos] in delim_set:
        pos += 1

    if pos >= total_len or current_buf[pos] == 0:
        saveptr[1] = pos
        return None

    # 2. Find end of token
    token_start = pos
    while pos < total_len and current_buf[pos] != 0 and current_buf[pos] not in delim_set:
        pos += 1

    token = bytearray(current_buf[token_start:pos])
    token.append(0)  # Null terminate

    if pos < total_len and current_buf[pos] in delim_set:
        pos += 1

    saveptr[1] = pos
    return token


def strtok(s: Optional[bytearray], delim: bytes) -> Optional[bytearray]:
    """Non-reentrant tokenizer maintaining internal static state."""
    global _strtok_last, _strtok_pos
    delim_set = set(delim[:strlen(delim)])

    if s is not None:
        _strtok_last = s
        _strtok_pos = 0

    if _strtok_last is None:
        return None

    total_len = len(_strtok_last)
    while _strtok_pos < total_len and _strtok_last[_strtok_pos] in delim_set:
        _strtok_pos += 1

    if _strtok_pos >= total_len or _strtok_last[_strtok_pos] == 0:
        return None

    start = _strtok_pos
    while _strtok_pos < total_len and _strtok_last[_strtok_pos] != 0 and _strtok_last[_strtok_pos] not in delim_set:
        _strtok_pos += 1

    token = bytearray(_strtok_last[start:_strtok_pos])
    token.append(0)

    if _strtok_pos < total_len and _strtok_last[_strtok_pos] in delim_set:
        _strtok_pos += 1

    return token


# =============================================================================
# Raw Memory Functions
# =============================================================================

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
    limit = min(len(s), n)
    for i in range(limit):
        if s[i] == target:
            return i
    return -1


def memrchr(s: bytes, c: int, n: int) -> int:
    """Scans backwards in the first n bytes of memory area s for byte c."""
    target = c & 0xFF
    limit = min(len(s), n)
    for i in range(limit - 1, -1, -1):
        if s[i] == target:
            return i
    return -1


def memset32(dst: bytearray, word: int, word_count: int) -> bytearray:
    """Fast 32-bit aligned memory block filling."""
    w_bytes = bytes([
        word & 0xFF,
        (word >> 8) & 0xFF,
        (word >> 16) & 0xFF,
        (word >> 24) & 0xFF
    ])
    chunk = w_bytes * word_count
    dst[:len(chunk)] = chunk
    return dst
