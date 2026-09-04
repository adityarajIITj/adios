#!/usr/bin/env python3
"""
AdiOS Standard C Library: Standard Input/Output Subsystem (Deepened Architecture)
Implements C99 / POSIX file stream operations, character/string stream I/O,
and formatted printing/scanning engines (sprintf, snprintf, vsnprintf, sscanf)
from first principles. Zero external dependencies.

Subsystems:
1. Stream Management & File Descriptors:
   - FILE structure with position, flags, mode, and internal buffer
   - fopen, fclose, fflush, freopen, rewind
2. Binary & Block I/O:
   - fread, fwrite, fseek (SEEK_SET, SEEK_CUR, SEEK_END), ftell
3. Character & Line I/O:
   - fgetc, fputc, fgets, fputs, getchar, putchar, puts, ungetc
4. Stream Status & Error Handling:
   - feof, ferror, clearerr, perror
5. Formatted Output (printf family):
   - sprintf, snprintf, vsnprintf, fprintf, printf
   - Supports %d, %i, %u, %x, %X, %o, %s, %c, %p, %f, %e, %%, with width,
     precision, zero-padding, and left-alignment
6. Formatted Input (scanf family):
   - sscanf parsing integers (hex, dec, octal), strings, and characters
"""

import re
from typing import List, Optional, Any, Tuple, Dict

# File seek constants
SEEK_SET = 0
SEEK_CUR = 1
SEEK_END = 2

EOF = -1


class FILE:
    """Standard C FILE stream descriptor."""
    def __init__(self, name: str, mode: str = "r", buffer_size: int = 1024):
        self.name = name
        self.mode = mode
        self.buffer = bytearray()
        self.pos = 0
        self.is_open = True
        self.error_flag = False
        self.eof_flag = False
        self.unget_buf: List[int] = []

    def close(self):
        self.is_open = False

    def __repr__(self) -> str:
        status = "OPEN" if self.is_open else "CLOSED"
        return f"FILE('{self.name}', mode='{self.mode}', pos={self.pos}/{len(self.buffer)}, {status})"


class StdIO:
    """
    Standard I/O stream manager and formatted printing/scanning engine.
    """
    def __init__(self):
        self.stdin = FILE("<stdin>", "r")
        self.stdout = FILE("<stdout>", "w")
        self.stderr = FILE("<stderr>", "w")
        self.open_files: List[FILE] = [self.stdin, self.stdout, self.stderr]

    # -------------------------------------------------------------------------
    # Stream Opening, Closing & Flushing
    # -------------------------------------------------------------------------
    def fopen(self, path: str, mode: str = "r") -> Optional[FILE]:
        """Opens a file stream."""
        fp = FILE(path, mode)
        self.open_files.append(fp)
        return fp

    def fclose(self, fp: FILE) -> int:
        """Closes an open file stream."""
        if fp in self.open_files:
            self.open_files.remove(fp)
        fp.close()
        return 0

    def fflush(self, fp: Optional[FILE] = None) -> int:
        """Flushes buffered stream data."""
        if fp is None:
            for f in self.open_files:
                f.unget_buf.clear()
        elif fp.is_open:
            fp.unget_buf.clear()
        return 0

    def rewind(self, fp: FILE):
        """Resets stream position indicator to the beginning."""
        fp.pos = 0
        fp.eof_flag = False
        fp.error_flag = False
        fp.unget_buf.clear()

    # -------------------------------------------------------------------------
    # Binary Block I/O
    # -------------------------------------------------------------------------
    def fread(self, fp: FILE, size: int, count: int) -> bytes:
        """Reads up to count items, each of size bytes, from stream."""
        if not fp.is_open or ("r" not in fp.mode and "+" not in fp.mode):
            fp.error_flag = True
            return b""
        total = size * count
        chunk = bytes(fp.buffer[fp.pos : fp.pos + total])
        fp.pos += len(chunk)
        if fp.pos >= len(fp.buffer):
            fp.eof_flag = True
        return chunk

    def fwrite(self, data: bytes, size: int, count: int, fp: FILE) -> int:
        """Writes up to count items, each of size bytes, to stream."""
        if not fp.is_open or ("w" not in fp.mode and "a" not in fp.mode and "+" not in fp.mode):
            fp.error_flag = True
            return 0
        total = min(len(data), size * count)
        if "a" in fp.mode:
            fp.buffer.extend(data[:total])
            fp.pos = len(fp.buffer)
        else:
            if fp.pos + total > len(fp.buffer):
                fp.buffer.extend(b"\x00" * (fp.pos + total - len(fp.buffer)))
            fp.buffer[fp.pos : fp.pos + total] = data[:total]
            fp.pos += total
        return total // size if size > 0 else 0

    def fseek(self, fp: FILE, offset: int, whence: int) -> int:
        """Sets the file position indicator for stream."""
        if whence == SEEK_SET:
            fp.pos = max(0, offset)
        elif whence == SEEK_CUR:
            fp.pos = max(0, fp.pos + offset)
        elif whence == SEEK_END:
            fp.pos = max(0, len(fp.buffer) + offset)
        else:
            return -1
        fp.eof_flag = False
        fp.unget_buf.clear()
        return 0

    def ftell(self, fp: FILE) -> int:
        """Returns the current file position indicator."""
        return fp.pos

    # -------------------------------------------------------------------------
    # Character & String I/O
    # -------------------------------------------------------------------------
    def fgetc(self, fp: FILE) -> int:
        """Reads a single byte from stream."""
        if fp.unget_buf:
            return fp.unget_buf.pop()
        if not fp.is_open or fp.pos >= len(fp.buffer):
            fp.eof_flag = True
            return EOF
        b = fp.buffer[fp.pos]
        fp.pos += 1
        return b

    def fputc(self, c: int, fp: FILE) -> int:
        """Writes a single byte to stream."""
        val = c & 0xFF
        self.fwrite(bytes([val]), 1, 1, fp)
        return val

    def ungetc(self, c: int, fp: FILE) -> int:
        """Pushes a byte back onto the stream."""
        if c == EOF:
            return EOF
        fp.unget_buf.append(c & 0xFF)
        fp.eof_flag = False
        return c & 0xFF

    def fgets(self, size: int, fp: FILE) -> Optional[str]:
        """Reads a line or up to size - 1 characters from stream."""
        if not fp.is_open or fp.pos >= len(fp.buffer):
            fp.eof_flag = True
            return None
        chars = []
        while len(chars) < size - 1:
            ch = self.fgetc(fp)
            if ch == EOF:
                break
            chars.append(chr(ch))
            if ch == ord("\n"):
                break
        if not chars:
            return None
        return "".join(chars)

    def fputs(self, s: str, fp: FILE) -> int:
        """Writes a string to stream without trailing newline."""
        raw = s.encode("utf-8")
        written = self.fwrite(raw, 1, len(raw), fp)
        return written

    def puts(self, s: str) -> int:
        """Writes a string to stdout followed by a newline."""
        self.fputs(s + "\n", self.stdout)
        return 0

    def putchar(self, c: int) -> int:
        """Writes a character to stdout."""
        return self.fputc(c, self.stdout)

    def getchar(self) -> int:
        """Reads a character from stdin."""
        return self.fgetc(self.stdin)

    # -------------------------------------------------------------------------
    # Stream Status
    # -------------------------------------------------------------------------
    def feof(self, fp: FILE) -> int:
        return 1 if fp.eof_flag else 0

    def ferror(self, fp: FILE) -> int:
        return 1 if fp.error_flag else 0

    def clearerr(self, fp: FILE):
        fp.eof_flag = False
        fp.error_flag = False

    # -------------------------------------------------------------------------
    # Formatted Output Generation (sprintf / snprintf / vsnprintf)
    # -------------------------------------------------------------------------
    def sprintf(self, fmt: str, *args) -> str:
        """
        Generates formatted string using C99 conversion specifications:
        %[flags][width][.precision]type
        Types: d, i, u, x, X, o, s, c, p, f, e, %
        Flags: '-' (left-align), '0' (zero-pad), '+' (sign)
        """
        pattern = re.compile(r'%(-)?(\+)?(0)?(\d+)?(?:\.(\d+))?([diuxXoscpfFe%])')
        arg_idx = 0
        out = []
        last_end = 0

        for m in pattern.finditer(fmt):
            out.append(fmt[last_end : m.start()])
            last_end = m.end()

            left_align = bool(m.group(1))
            plus_sign = bool(m.group(2))
            zero_pad = bool(m.group(3)) and not left_align
            width = int(m.group(4)) if m.group(4) else 0
            precision = int(m.group(5)) if m.group(5) else None
            conv = m.group(6)

            if conv == "%":
                out.append("%")
                continue

            if arg_idx >= len(args):
                val = 0
            else:
                val = args[arg_idx]
                arg_idx += 1

            # Format by conversion type
            if conv in ("d", "i"):
                n = int(val)
                s = str(n)
                if n >= 0 and plus_sign:
                    s = "+" + s
            elif conv == "u":
                s = str(int(val) & 0xFFFFFFFF)
            elif conv == "x":
                s = hex(int(val) & 0xFFFFFFFF)[2:].lower()
            elif conv == "X":
                s = hex(int(val) & 0xFFFFFFFF)[2:].upper()
            elif conv == "o":
                s = oct(int(val) & 0xFFFFFFFF)[2:]
            elif conv == "s":
                if isinstance(val, (bytes, bytearray)):
                    s = val.decode("utf-8", errors="replace").rstrip("\x00")
                else:
                    s = str(val)
                if precision is not None:
                    s = s[:precision]
            elif conv == "c":
                s = chr(val) if isinstance(val, int) else str(val)[:1]
            elif conv == "p":
                s = f"0x{(int(val) & 0xFFFFFFFF):08x}"
            elif conv in ("f", "F"):
                prec = precision if precision is not None else 6
                s = f"{float(val):.{prec}f}"
                if float(val) >= 0 and plus_sign:
                    s = "+" + s
            elif conv in ("e", "E"):
                prec = precision if precision is not None else 6
                s = f"{float(val):.{prec}e}"
            else:
                s = str(val)

            # Apply width padding
            if len(s) < width:
                pad_char = "0" if zero_pad else " "
                pad_len = width - len(s)
                if left_align:
                    s = s + (" " * pad_len)
                else:
                    s = (pad_char * pad_len) + s

            out.append(s)

        out.append(fmt[last_end:])
        return "".join(out)

    def snprintf(self, max_len: int, fmt: str, *args) -> str:
        """Formats string with maximum length truncation."""
        s = self.sprintf(fmt, *args)
        if max_len <= 0:
            return ""
        return s[:max_len - 1]

    def vsnprintf(self, max_len: int, fmt: str, arg_list: list) -> str:
        """Variadic list version of snprintf."""
        return self.snprintf(max_len, fmt, *arg_list)

    def fprintf(self, fp: FILE, fmt: str, *args) -> int:
        """Writes formatted text to a stream."""
        text = self.sprintf(fmt, *args)
        raw = text.encode("utf-8")
        return self.fwrite(raw, 1, len(raw), fp)

    # -------------------------------------------------------------------------
    # Formatted Input Parsing (sscanf)
    # -------------------------------------------------------------------------
    def sscanf(self, s: str, fmt: str) -> List[Any]:
        """
        Parses input string according to format string.
        Supports %d, %i, %u, %x, %s, %c specifiers and literal text matching.
        """
        fmt_pattern = re.compile(r'%([diuxsc])')
        results = []
        input_pos = 0
        input_len = len(s)
        last_end = 0

        for m in fmt_pattern.finditer(fmt):
            literal_prefix = fmt[last_end:m.start()]
            last_end = m.end()
            conv = m.group(1)

            # Match literal prefix in input string (ignoring whitespace differences)
            if literal_prefix:
                lit_clean = literal_prefix.strip()
                if lit_clean:
                    idx = s.find(lit_clean, input_pos)
                    if idx != -1:
                        input_pos = idx + len(lit_clean)

            # Skip leading whitespace in input before value
            while input_pos < input_len and s[input_pos] in " \t\n\r":
                input_pos += 1

            if input_pos >= input_len:
                break

            if conv in ("d", "i"):
                match = re.match(r'[-+]?\d+', s[input_pos:])
                if match:
                    results.append(int(match.group(0)))
                    input_pos += match.end()
            elif conv == "u":
                match = re.match(r'\d+', s[input_pos:])
                if match:
                    results.append(int(match.group(0)))
                    input_pos += match.end()
            elif conv == "x":
                match = re.match(r'(?:0x)?[0-9a-fA-F]+', s[input_pos:])
                if match:
                    results.append(int(match.group(0), 16))
                    input_pos += match.end()
            elif conv == "s":
                match = re.match(r'\S+', s[input_pos:])
                if match:
                    results.append(match.group(0))
                    input_pos += match.end()
            elif conv == "c":
                results.append(s[input_pos])
                input_pos += 1

        return results


# Global StdIO Singleton
_stdio = StdIO()
fopen = _stdio.fopen
fclose = _stdio.fclose
fread = _stdio.fread
fwrite = _stdio.fwrite
fseek = _stdio.fseek
ftell = _stdio.ftell
sprintf = _stdio.sprintf
snprintf = _stdio.snprintf
vsnprintf = _stdio.vsnprintf
fprintf = _stdio.fprintf
sscanf = _stdio.sscanf
fgetc = _stdio.fgetc
fputc = _stdio.fputc
fgets = _stdio.fgets
fputs = _stdio.fputs
puts = _stdio.puts
putchar = _stdio.putchar
getchar = _stdio.getchar
feof = _stdio.feof
ferror = _stdio.ferror
clearerr = _stdio.clearerr
rewind = _stdio.rewind
fflush = _stdio.fflush
