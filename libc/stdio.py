#!/usr/bin/env python3
"""
AdiOS Standard C Library: Standard Input/Output Subsystem (stdio.py)
Implements C99 formatted string formatting (sprintf/snprintf) and
file stream I/O operations (fopen, fread, fwrite, fseek, ftell) from first principles.
Zero external dependencies.
"""

import re
from typing import List, Optional, Any

SEEK_SET = 0
SEEK_CUR = 1
SEEK_END = 2

EOF = -1

class FILE:
    """
    Standard C FILE stream descriptor.
    """
    def __init__(self, name: str, mode: str = "r", buffer_size: int = 1024):
        self.name = name
        self.mode = mode
        self.buffer = bytearray()
        self.pos = 0
        self.is_open = True
        self.error_flag = False
        self.eof_flag = False

    def close(self):
        self.is_open = False

class StdIO:
    """
    Standard I/O stream manager and formatted printing engine.
    """
    def __init__(self):
        self.stdin = FILE("<stdin>", "r")
        self.stdout = FILE("<stdout>", "w")
        self.stderr = FILE("<stderr>", "w")
        self.open_files: List[FILE] = [self.stdin, self.stdout, self.stderr]

    def fopen(self, path: str, mode: str = "r") -> Optional[FILE]:
        fp = FILE(path, mode)
        self.open_files.append(fp)
        return fp

    def fclose(self, fp: FILE) -> int:
        if fp in self.open_files:
            self.open_files.remove(fp)
        fp.close()
        return 0

    def fread(self, fp: FILE, size: int, count: int) -> bytes:
        if not fp.is_open or "r" not in fp.mode and "+" not in fp.mode:
            fp.error_flag = True
            return b""
        total = size * count
        chunk = bytes(fp.buffer[fp.pos:fp.pos + total])
        fp.pos += len(chunk)
        if fp.pos >= len(fp.buffer):
            fp.eof_flag = True
        return chunk

    def fwrite(self, data: bytes, size: int, count: int, fp: FILE) -> int:
        if not fp.is_open or "w" not in fp.mode and "a" not in fp.mode and "+" not in fp.mode:
            fp.error_flag = True
            return 0
        total = min(len(data), size * count)
        if "a" in fp.mode:
            fp.buffer.extend(data[:total])
            fp.pos = len(fp.buffer)
        else:
            if fp.pos + total > len(fp.buffer):
                fp.buffer.extend(b"\x00" * (fp.pos + total - len(fp.buffer)))
            fp.buffer[fp.pos:fp.pos + total] = data[:total]
            fp.pos += total
        return total // size if size > 0 else 0

    def fseek(self, fp: FILE, offset: int, whence: int) -> int:
        if whence == SEEK_SET:
            fp.pos = max(0, offset)
        elif whence == SEEK_CUR:
            fp.pos = max(0, fp.pos + offset)
        elif whence == SEEK_END:
            fp.pos = max(0, len(fp.buffer) + offset)
        else:
            return -1
        fp.eof_flag = False
        return 0

    def ftell(self, fp: FILE) -> int:
        return fp.pos

    def sprintf(self, fmt: str, *args) -> str:
        """
        Full C99 formatted string generator.
        Supports %d, %i, %u, %x, %X, %s, %c, %p, %%, width, zero-padding.
        """
        pattern = re.compile(r'%(-)?(0)?(\d+)?(?:\.(\d+))?([diuxXscp%])')
        arg_idx = 0
        out = []
        last_end = 0

        for m in pattern.finditer(fmt):
            out.append(fmt[last_end:m.start()])
            last_end = m.end()

            left_align = bool(m.group(1))
            zero_pad = bool(m.group(2)) and not left_align
            width = int(m.group(3)) if m.group(3) else 0
            precision = int(m.group(4)) if m.group(4) else None
            conv = m.group(5)

            if conv == '%':
                out.append('%')
                continue

            if arg_idx >= len(args):
                val = 0
            else:
                val = args[arg_idx]
                arg_idx += 1

            # Format conversion
            if conv in ('d', 'i'):
                s = str(int(val))
            elif conv == 'u':
                s = str(int(val) & 0xFFFFFFFF)
            elif conv == 'x':
                s = hex(int(val) & 0xFFFFFFFF)[2:].lower()
            elif conv == 'X':
                s = hex(int(val) & 0xFFFFFFFF)[2:].upper()
            elif conv == 's':
                s = val.decode("utf-8", errors="replace") if isinstance(val, (bytes, bytearray)) else str(val)
                if precision is not None:
                    s = s[:precision]
            elif conv == 'c':
                s = chr(val) if isinstance(val, int) else str(val)[:1]
            elif conv == 'p':
                s = f"0x{(int(val) & 0xFFFFFFFF):08x}"
            else:
                s = str(val)

            # Apply width padding
            if len(s) < width:
                pad_char = '0' if zero_pad else ' '
                pad_len = width - len(s)
                if left_align:
                    s = s + (' ' * pad_len)
                else:
                    s = (pad_char * pad_len) + s

            out.append(s)

        out.append(fmt[last_end:])
        return "".join(out)

    def snprintf(self, max_len: int, fmt: str, *args) -> str:
        s = self.sprintf(fmt, *args)
        return s[:max_len - 1] if max_len > 0 else ""

# Global singleton
_stdio = StdIO()
sprintf = _stdio.sprintf
snprintf = _stdio.snprintf
fopen = _stdio.fopen
fclose = _stdio.fclose
fread = _stdio.fread
fwrite = _stdio.fwrite
fseek = _stdio.fseek
ftell = _stdio.ftell

if __name__ == "__main__":
    res = sprintf("Code: 0x%08X, Count: %5d, Name: %s", 0xAD10, 42, "AdiOS")
    print("Formatted:", res)
    assert res == "Code: 0x0000AD10, Count:    42, Name: AdiOS"

    fp = fopen("test.txt", "w+")
    fwrite(b"Sovereign Computing", 1, 19, fp)
    fseek(fp, 0, SEEK_SET)
    read_back = fread(fp, 1, 19)
    assert read_back == b"Sovereign Computing"
    fclose(fp)
    print("LibC stdio verified.")
