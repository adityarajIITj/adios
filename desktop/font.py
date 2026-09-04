#!/usr/bin/env python3
"""
AdiOS Desktop Font Loader: Parses 8x8 bitmap font from kernel/font8x8.s
Provides full 95 ASCII printable characters (32 - 126) for window manager and text renderers.
Zero external dependencies.
"""

import os

_DEFAULT_FONT = None

def get_default_font():
    global _DEFAULT_FONT
    if _DEFAULT_FONT is not None:
        return _DEFAULT_FONT

    font = {}
    path = os.path.join(os.path.dirname(__file__), "..", "kernel", "font8x8.s")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        curr_char = None
        for line in lines:
            line = line.strip()
            if line.startswith("# ") and len(line) >= 4 and line[2:].split()[0].isdigit():
                ascii_code = int(line[2:].split()[0])
                curr_char = chr(ascii_code)
            elif line.startswith(".byte") and curr_char is not None:
                bytes_vals = [int(x.strip(), 16) for x in line[5:].split(",")]
                font[curr_char] = bytes(bytes_vals)
                curr_char = None

    _DEFAULT_FONT = font
    return font

if __name__ == "__main__":
    f = get_default_font()
    assert len(f) == 95
    print("Font loaded:", len(f), "characters.")
