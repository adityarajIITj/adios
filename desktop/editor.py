#!/usr/bin/env python3
"""
AdiOS In-OS Code Editor (AdiIDE)
Inspired by Terry A. Davis's built-in document/code editor (Ed) in TempleOS.
Features:
- Syntax highlighting for AdiPython (keywords, built-ins, numbers, strings, comments)
- Interactive [RUN] button compiling code live via AdiPython
- Interactive [SAVE] button writing contiguously to the virtual disk via AdiFS
- Line numbering and status bar
"""

import re
from fs.adifs import AdiFS

# Syntax Highlighting Palette
COLOR_KEYWORD = 0x00BB9AF7 # Purple
COLOR_BUILTIN = 0x007AA2F7 # Blue
COLOR_NUMBER  = 0x00E0AF68 # Gold / Yellow
COLOR_STRING  = 0x009ECE6A # Green
COLOR_COMMENT = 0x007DCFFF # Cyan
COLOR_DEFAULT = 0x00C0CAF5 # Soft White
COLOR_LINENUM = 0x00565F89 # Muted Blue
COLOR_BTN_RUN = 0x009ECE6A # Green
COLOR_BTN_SAVE= 0x007AA2F7 # Blue

KEYWORDS = {"def", "return", "if", "elif", "else", "while", "for", "in", "range"}
BUILTINS = {"print", "peek", "poke", "pixel", "rect", "line", "clear", "tone", "sleep", "malloc", "isqrt"}

CHAR_WIDTH  = 8
CHAR_HEIGHT = 8

class CodeEditor:
    def __init__(self, filename="script.ap", initial_code=None, vm=None):
        self.filename = filename
        self.vm = vm
        self.adifs = AdiFS("disk.img")
        self.status = f"Editing '{filename}'"

        if initial_code:
            self.lines = initial_code.splitlines()
        else:
            self.lines = [
                "# AdiOS In-OS Code Editor",
                "def main():",
                "    total = 0",
                "    for i in range(10):",
                "        total += i * 5",
                "    print('Computed total:', total)",
                "    return total",
                "",
                "main()"
            ]

    def highlight_line(self, line):
        """Tokenizes a line of source code and returns list of (token_str, color)."""
        tokens = []
        # Check comment
        if "#" in line:
            code_part, comment_part = line.split("#", 1)
            tokens.extend(self._tokenize_code(code_part))
            tokens.append(("#" + comment_part, COLOR_COMMENT))
        else:
            tokens.extend(self._tokenize_code(line))
        return tokens

    def _tokenize_code(self, code_str):
        tokens = []
        # Regex matching words, numbers, strings, and other chars
        pattern = r'(\b\w+\b|\"[^\"]*\"|\'[^\']*\'|[^\w\s]|\s+)'
        parts = re.findall(pattern, code_str)

        for p in parts:
            if p in KEYWORDS:
                tokens.append((p, COLOR_KEYWORD))
            elif p in BUILTINS:
                tokens.append((p, COLOR_BUILTIN))
            elif p.isdigit() or (p.startswith("0x") or p.startswith("0b")):
                tokens.append((p, COLOR_NUMBER))
            elif (p.startswith('"') and p.endswith('"')) or (p.startswith("'") and p.endswith("'")):
                tokens.append((p, COLOR_STRING))
            else:
                tokens.append((p, COLOR_DEFAULT))
        return tokens

    def run_code(self):
        """Compiles and executes editor code live in AdiPython."""
        if not self.vm:
            self.status = "[RUN] VM not attached"
            return None

        from adipython import AdiPython
        ap = AdiPython(self.vm, adifs=self.adifs)
        code = "\n".join(self.lines)
        try:
            res = ap.execute(code)
            self.status = f"[RUN SUCCESS] Result: {res}"
            return res
        except Exception as e:
            self.status = f"[RUN ERROR] {str(e)[:30]}"
            return None

    def save_to_disk(self):
        """Saves editor buffer to the virtual hard disk via AdiFS."""
        code = "\n".join(self.lines)
        try:
            import os
            if not os.path.exists(self.adifs.disk_path):
                self.adifs.format_disk()
            else:
                try:
                    self.adifs.get_superblock()
                except Exception:
                    self.adifs.format_disk()

            entry = self.adifs.create_file(self.filename, code)
            self.status = f"[SAVED] '{self.filename}' @ Sector {entry.start_sector}"
            return True
        except Exception as e:
            self.status = f"[SAVE ERROR] {str(e)[:30]}"
            return False

    def render(self, fb, font_dict, origin_x, origin_y, w, h, screen_w=640):
        """Renders editor buffer, line numbers, syntax highlighting, and action buttons."""
        # 1. Editor Toolbar: [RUN] and [SAVE] buttons at top
        btn_y = origin_y + 4
        # [RUN] Button at origin_x + 6
        self._draw_button(fb, font_dict, origin_x + 6, btn_y, "[RUN]", COLOR_BTN_RUN, screen_w)
        # [SAVE] Button at origin_x + 60
        self._draw_button(fb, font_dict, origin_x + 60, btn_y, "[SAVE]", COLOR_BTN_SAVE, screen_w)

        # Status text at right of toolbar
        self._draw_str(fb, font_dict, origin_x + 120, btn_y + 2, self.status[:32], 0x00A9B1D6, screen_w)

        # Separator Line below toolbar
        sep_y = origin_y + 22
        sep_color = bytes([0x41, 0x48, 0x68, 0])
        for x in range(origin_x, origin_x + w):
            fb[(sep_y * screen_w + x) * 4 : (sep_y * screen_w + x) * 4 + 4] = sep_color

        # 2. Render Code Lines with Line Numbers
        text_y_start = origin_y + 28
        max_display_lines = (h - 32) // 12

        for i, line in enumerate(self.lines[:max_display_lines]):
            curr_y = text_y_start + i * 12
            # Line Number (e.g. " 1 ")
            ln_str = f"{i + 1:2d} "
            self._draw_str(fb, font_dict, origin_x + 6, curr_y, ln_str, COLOR_LINENUM, screen_w)

            # Code Tokens
            tokens = self.highlight_line(line)
            curr_x = origin_x + 36
            for tok_str, tok_col in tokens:
                self._draw_str(fb, font_dict, curr_x, curr_y, tok_str, tok_col, screen_w)
                curr_x += len(tok_str) * CHAR_WIDTH

    def handle_click(self, rel_x, rel_y):
        """Handles clicks on toolbar buttons."""
        if 4 <= rel_y <= 20:
            if 6 <= rel_x <= 50:
                self.run_code()
                return "run"
            elif 60 <= rel_x <= 110:
                self.save_to_disk()
                return "save"
        return None

    def _draw_button(self, fb, font_dict, x, y, label, bg_color, screen_w):
        bg_bytes = bytes([bg_color & 0xFF, (bg_color >> 8) & 0xFF, (bg_color >> 16) & 0xFF, 0])
        bw = len(label) * CHAR_WIDTH + 8
        bh = 16
        for py in range(y, y + bh):
            fb[(py * screen_w + x) * 4 : (py * screen_w + x + bw) * 4] = bg_bytes * bw
        self._draw_str(fb, font_dict, x + 4, y + 4, label, 0x00FFFFFF, screen_w)

    def _draw_str(self, fb, font_dict, x, y, text, color, screen_w):
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        for idx, ch in enumerate(text):
            bitmap = font_dict.get(ch, font_dict.get(" ", b"\x00"*8))
            px = x + idx * CHAR_WIDTH
            if px + CHAR_WIDTH > screen_w: break

            for row in range(CHAR_HEIGHT):
                py = y + row
                if py >= 480: break
                byte_val = bitmap[row]
                for col in range(CHAR_WIDTH):
                    if (byte_val >> (7 - col)) & 1:
                        off = (py * screen_w + (px + col)) * 4
                        fb[off : off + 4] = c_bytes
