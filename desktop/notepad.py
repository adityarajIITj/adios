#!/usr/bin/env python3
"""
AdiOS Sovereign Notepad Application (desktop/notepad.py)
A clean, minimalist, high-productivity text editor and document draft studio.
Features:
- Multi-line text buffer with cursor navigation (Arrow keys, Home, End, Backspace, Enter, Tab)
- Document management: [New], [Open], [Save], [Clear]
- Toggleable line numbers gutter
- Live telemetry: Line, Column, Word Count, Character Count
- Minimalist modern styling integrated with AdiOS ThemeManager
- Zero bloat, pure linear framebuffer rendering

Strict Zero Emoji Policy.
"""

import os
from typing import List, Optional, Tuple, Dict, Any

from .window_manager import Window, CHAR_WIDTH, CHAR_HEIGHT
from .theme import ThemeManager

class NotepadApp(Window):
    """
    Sovereign Notepad Application Window.
    """
    def __init__(
        self,
        win_id: str = "notepad",
        x: int = 220,
        y: int = 90,
        w: int = 600,
        h: int = 460,
        initial_file: str = "notes.txt"
    ):
        super().__init__(
            win_id=win_id,
            title=f"AdiOS Notepad - [{initial_file}]",
            x=x,
            y=y,
            w=w,
            h=h,
            bg_color=0x00121820
        )
        self.filename: str = initial_file
        self.lines: List[str] = [
            "Welcome to AdiOS Notepad.",
            "Type directly into this buffer to take notes or draft code.",
            ""
        ]
        self.cursor_line: int = 2
        self.cursor_col: int = 0
        self.scroll_line: int = 0
        self.show_line_numbers: bool = True
        self.dirty: bool = False
        self.status_msg: str = "Ready."

        self.on_draw_content = self._render_content
        self.on_click_content = self._handle_click

    @property
    def word_count(self) -> int:
        """Returns total words in the text buffer."""
        total = 0
        for l in self.lines:
            total += len(l.split())
        return total

    @property
    def char_count(self) -> int:
        """Returns total character count including newlines."""
        return sum(len(l) for l in self.lines) + max(0, len(self.lines) - 1)

    # --------------------------------------------------------------------------
    # Document Operations
    # --------------------------------------------------------------------------

    def new_file(self):
        """Resets the document buffer to an empty file."""
        self.lines = [""]
        self.cursor_line = 0
        self.cursor_col = 0
        self.scroll_line = 0
        self.dirty = False
        self.status_msg = "New empty document created."
        self.title = f"AdiOS Notepad - [{self.filename}]"

    def open_file(self, path: Optional[str] = None):
        """Loads text from disk into document buffer."""
        target = path or self.filename
        try:
            if os.path.exists(target):
                with open(target, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self.lines = content.splitlines() if content else [""]
                self.filename = target
                self.cursor_line = 0
                self.cursor_col = 0
                self.scroll_line = 0
                self.dirty = False
                self.status_msg = f"Opened '{os.path.basename(target)}' ({len(self.lines)} lines)."
                self.title = f"AdiOS Notepad - [{os.path.basename(target)}]"
            else:
                self.status_msg = f"File '{target}' does not exist."
        except Exception as e:
            self.status_msg = f"Open error: {e}"

    def save_file(self, path: Optional[str] = None):
        """Saves current document buffer to disk."""
        target = path or self.filename
        try:
            content = "\n".join(self.lines)
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            self.filename = target
            self.dirty = False
            self.status_msg = f"Saved '{os.path.basename(target)}' ({len(self.lines)} lines, {self.char_count} chars)."
            self.title = f"AdiOS Notepad - [{os.path.basename(target)}]"
        except Exception as e:
            self.status_msg = f"Save error: {e}"

    def clear_all(self):
        """Clears buffer completely."""
        self.lines = [""]
        self.cursor_line = 0
        self.cursor_col = 0
        self.scroll_line = 0
        self.dirty = True
        self.status_msg = "Buffer cleared."

    # --------------------------------------------------------------------------
    # Keyboard Navigation and Input
    # --------------------------------------------------------------------------

    def handle_key(self, key_char: str):
        """Processes keystrokes for text editing and navigation."""
        if not self.lines:
            self.lines = [""]

        # 1. Newline (Enter)
        if key_char in ("\r", "\n"):
            line = self.lines[self.cursor_line]
            left = line[:self.cursor_col]
            right = line[self.cursor_col:]
            self.lines[self.cursor_line] = left
            self.lines.insert(self.cursor_line + 1, right)
            self.cursor_line += 1
            self.cursor_col = 0
            self.dirty = True
            self.status_msg = "Editing"
            self._ensure_cursor_visible()
            return

        # 2. Backspace
        if key_char in ("\b", "\x08"):
            line = self.lines[self.cursor_line]
            if self.cursor_col > 0:
                # Check for 4-space unindent
                if line[:self.cursor_col].endswith("    "):
                    self.lines[self.cursor_line] = line[:self.cursor_col - 4] + line[self.cursor_col:]
                    self.cursor_col -= 4
                else:
                    self.lines[self.cursor_line] = line[:self.cursor_col - 1] + line[self.cursor_col:]
                    self.cursor_col -= 1
                self.dirty = True
            elif self.cursor_line > 0:
                # Merge with previous line
                prev_line = self.lines[self.cursor_line - 1]
                prev_len = len(prev_line)
                self.lines[self.cursor_line - 1] = prev_line + line
                del self.lines[self.cursor_line]
                self.cursor_line -= 1
                self.cursor_col = prev_len
                self.dirty = True
            self._ensure_cursor_visible()
            return

        # 3. Tab (4 spaces)
        if key_char == "\t":
            line = self.lines[self.cursor_line]
            self.lines[self.cursor_line] = line[:self.cursor_col] + "    " + line[self.cursor_col:]
            self.cursor_col += 4
            self.dirty = True
            self._ensure_cursor_visible()
            return

        # 4. Arrow Navigation
        if key_char in ("KEY_UP", "\x1b[A"):
            if self.cursor_line > 0:
                self.cursor_line -= 1
                self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))
            self._ensure_cursor_visible()
            return

        if key_char in ("KEY_DOWN", "\x1b[B"):
            if self.cursor_line < len(self.lines) - 1:
                self.cursor_line += 1
                self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))
            self._ensure_cursor_visible()
            return

        if key_char in ("KEY_LEFT", "\x1b[D"):
            if self.cursor_col > 0:
                self.cursor_col -= 1
            elif self.cursor_line > 0:
                self.cursor_line -= 1
                self.cursor_col = len(self.lines[self.cursor_line])
            self._ensure_cursor_visible()
            return

        if key_char in ("KEY_RIGHT", "\x1b[C"):
            if self.cursor_col < len(self.lines[self.cursor_line]):
                self.cursor_col += 1
            elif self.cursor_line < len(self.lines) - 1:
                self.cursor_line += 1
                self.cursor_col = 0
            self._ensure_cursor_visible()
            return

        # 5. Printable Character Insertion
        if len(key_char) == 1 and ord(key_char) >= 32:
            line = self.lines[self.cursor_line]
            self.lines[self.cursor_line] = line[:self.cursor_col] + key_char + line[self.cursor_col:]
            self.cursor_col += 1
            self.dirty = True
            self._ensure_cursor_visible()

    def _ensure_cursor_visible(self):
        """Scrolls editor if cursor moves outside current visible view."""
        _, _, _, ch = self.client_rect
        visible_lines = max(1, (ch - 52) // 16)
        if self.cursor_line < self.scroll_line:
            self.scroll_line = self.cursor_line
        elif self.cursor_line >= self.scroll_line + visible_lines:
            self.scroll_line = self.cursor_line - visible_lines + 1

    # --------------------------------------------------------------------------
    # Rendering
    # --------------------------------------------------------------------------

    def _render_content(self, win: Window, fb: bytearray, font_dict: Dict):
        """Renders notepad toolbar, paper canvas, line numbers, text, and status bar."""
        cx, cy, cw, ch = self.client_rect
        tm = ThemeManager.get_instance()
        pal = tm.palette

        # 1. Top Toolbar (height: 28px)
        tb_h = 28
        self._render_toolbar(fb, cx, cy, cw, tb_h, pal, font_dict)

        # 2. Text Canvas Dimensions
        status_h = 20
        canvas_y = cy + tb_h
        canvas_h = ch - tb_h - status_h

        gutter_w = 36 if self.show_line_numbers else 8
        text_x = cx + gutter_w + 8
        text_w = cw - gutter_w - 12

        # Draw gutter background
        if self.show_line_numbers:
            self._fill_rect(fb, cx, canvas_y, gutter_w, canvas_h, pal.gutter_bg)
            self._draw_vline(fb, cx + gutter_w, canvas_y, canvas_h, pal.card_border)

        # Draw text canvas background
        self._fill_rect(fb, cx + gutter_w + (1 if self.show_line_numbers else 0), canvas_y, text_w + 10, canvas_h, pal.win_bg)

        # 3. Render Lines & Cursor
        line_h = 16
        visible_count = canvas_h // line_h

        for idx in range(visible_count):
            line_idx = self.scroll_line + idx
            if line_idx >= len(self.lines):
                break

            line_y = canvas_y + idx * line_h + 3

            # Render Gutter Line Number
            if self.show_line_numbers:
                num_col = pal.text_highlight if line_idx == self.cursor_line else pal.text_muted
                self._draw_text(fb, cx + 6, line_y, f"{line_idx + 1:2d}", num_col, font_dict)

            # Active Line subtle tint
            if line_idx == self.cursor_line:
                self._fill_rect(fb, text_x - 4, line_y - 2, text_w, line_h, pal.btn_bg)

            # Render Line Text
            raw_line = self.lines[line_idx]
            self._draw_text(fb, text_x, line_y, raw_line[:text_w // CHAR_WIDTH], pal.text_primary, font_dict)

            # Render Cursor Bar
            if line_idx == self.cursor_line:
                cur_x = text_x + self.cursor_col * CHAR_WIDTH
                if text_x <= cur_x <= cx + cw - 4:
                    self._fill_rect(fb, cur_x, line_y, 2, 13, pal.accent_primary)

        # 4. Bottom Status Bar
        sb_y = cy + ch - status_h
        self._fill_rect(fb, cx, sb_y, cw, status_h, pal.gutter_bg)
        self._draw_hline(fb, cx, sb_y, cw, pal.card_border)

        dirty_tag = " *" if self.dirty else ""
        stat_txt = (
            f"Ln {self.cursor_line + 1}, Col {self.cursor_col + 1} | "
            f"{self.word_count} words | {self.char_count} chars | "
            f"'{self.filename}'{dirty_tag} | {self.status_msg}"
        )
        self._draw_text(fb, cx + 10, sb_y + 5, stat_txt[:cw // CHAR_WIDTH - 2], pal.text_muted, font_dict)

    def _render_toolbar(self, fb: bytearray, x: int, y: int, w: int, h: int, pal: Any, font_dict: Dict):
        """Renders toolbar action buttons."""
        self._fill_rect(fb, x, y, w, h, pal.gutter_bg)
        self._draw_hline(fb, x, y + h - 1, w, pal.card_border)

        buttons = [
            ("New", 48),
            ("Open", 52),
            ("Save", 52),
            ("Clear", 56),
            ("Nums", 54)
        ]
        curr_x = x + 8
        for label, bw in buttons:
            self._fill_rect(fb, curr_x, y + 4, bw, h - 8, pal.btn_bg)
            self._draw_rect_outline(fb, curr_x, y + 4, bw, h - 8, pal.btn_border)
            self._draw_text(fb, curr_x + 8, y + 8, label, pal.text_primary, font_dict)
            curr_x += bw + 6

    def _handle_click(self, win: Window, rel_x: int, rel_y: int):
        """Handles toolbar button clicks and canvas cursor placement."""
        # Check toolbar buttons
        if rel_y <= 28:
            if 8 <= rel_x <= 56:
                self.new_file()
            elif 62 <= rel_x <= 114:
                self.open_file()
            elif 120 <= rel_x <= 172:
                self.save_file()
            elif 178 <= rel_x <= 234:
                self.clear_all()
            elif 240 <= rel_x <= 294:
                self.show_line_numbers = not self.show_line_numbers
                self.status_msg = f"Line numbers: {'ON' if self.show_line_numbers else 'OFF'}"
            return

        # Check canvas click to place cursor
        gutter_w = 36 if self.show_line_numbers else 8
        line_h = 16
        clicked_idx = self.scroll_line + (rel_y - 28) // line_h
        if 0 <= clicked_idx < len(self.lines):
            self.cursor_line = clicked_idx
            text_x = gutter_w + 8
            if rel_x >= text_x:
                col = (rel_x - text_x) // CHAR_WIDTH
                self.cursor_col = min(col, len(self.lines[self.cursor_line]))
            else:
                self.cursor_col = 0

    # --------------------------------------------------------------------------
    # Framebuffer Drawing Primitives
    # --------------------------------------------------------------------------

    def _fill_rect(self, fb: bytearray, x: int, y: int, w: int, h: int, color: int):
        if w <= 0 or h <= 0: return
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        px = bytes([b, g, r, 0])
        row = px * w
        for cy in range(max(0, y), min(720, y + h)):
            off = (cy * 1280 + max(0, x)) * 4
            fb[off : off + w * 4] = row

    def _draw_rect_outline(self, fb: bytearray, x: int, y: int, w: int, h: int, color: int):
        self._draw_hline(fb, x, y, w, color)
        self._draw_hline(fb, x, y + h - 1, w, color)
        self._draw_vline(fb, x, y, h, color)
        self._draw_vline(fb, x + w - 1, y, h, color)

    def _draw_hline(self, fb: bytearray, x: int, y: int, w: int, color: int):
        if y < 0 or y >= 720 or w <= 0: return
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        px = bytes([b, g, r, 0])
        off = (y * 1280 + max(0, x)) * 4
        fb[off : off + w * 4] = px * w

    def _draw_vline(self, fb: bytearray, x: int, y: int, h: int, color: int):
        if x < 0 or x >= 1280 or h <= 0: return
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        px = bytes([b, g, r, 0])
        for cy in range(max(0, y), min(720, y + h)):
            off = (cy * 1280 + x) * 4
            fb[off : off + 4] = px

    def _draw_text(self, fb: bytearray, x: int, y: int, text: str, color: int, font_dict: Dict):
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        from .window_manager import WIDTH, HEIGHT
        curr_x = x
        for ch in text:
            if curr_x + CHAR_WIDTH > WIDTH:
                break
            glyph = font_dict.get(ord(ch), font_dict.get(ch, None)) if font_dict else None
            if glyph:
                for row in range(CHAR_HEIGHT):
                    py = y + row
                    if 0 <= py < HEIGHT:
                        bits = glyph[row] if row < len(glyph) else 0
                        for col in range(CHAR_WIDTH):
                            px = curr_x + col
                            if 0 <= px < WIDTH and (bits & (1 << (7 - col))):
                                fb[(py * WIDTH + px) * 4 : (py * WIDTH + px + 1) * 4] = c_bytes
            curr_x += CHAR_WIDTH
