#!/usr/bin/env python3
"""
AdiOS Sovereign Notepad Application (desktop/notepad.py)
A clean, minimalist, high-productivity text editor and document draft studio.
Features:
- Multi-line text buffer with cursor navigation (Arrow keys, Home, End, Backspace, Enter, Tab)
- Standard productivity shortcuts: Ctrl+A, Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+Z, Ctrl+Y, Ctrl+S, Ctrl+Backspace, Ctrl+Enter
- Ultra-smooth word-level deletion and multi-level undo/redo
- Sovereign clipboard engine integration
- Dedicated storage directory: storage/notepad/ (notes.txt)
- Document management: [New], [Open], [Save], [Clear]
- Toggleable line numbers gutter
- Live telemetry: Line, Column, Word Count, Character Count
- Minimalist modern styling integrated with AdiOS ThemeManager

Strict Zero Emoji Policy.
"""

import os
from typing import List, Optional, Tuple, Dict, Any

from .window_manager import Window, CHAR_WIDTH, CHAR_HEIGHT
from .theme import ThemeManager
from .clipboard import SovereignClipboard

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
        initial_file: str = "storage/notepad/notes.txt"
    ):
        super().__init__(
            win_id=win_id,
            title=f"AdiOS Notepad - [{os.path.basename(initial_file)}]",
            x=x,
            y=y,
            w=w,
            h=h,
            bg_color=0x00121820
        )
        self.filename: str = initial_file
        os.makedirs(os.path.dirname(self.filename) or ".", exist_ok=True)

        self.lines: List[str] = [
            "Welcome to AdiOS Sovereign Notepad.",
            "Type directly into this buffer to take notes or draft ideas.",
            "Shortcuts: Ctrl+A (all), Ctrl+C (copy), Ctrl+V (paste), Ctrl+Z (undo), Ctrl+S (save)."
        ]
        self.cursor_line: int = 2
        self.cursor_col: int = 0
        self.scroll_line: int = 0
        self.show_line_numbers: bool = True
        self.dirty: bool = False
        self.status_msg: str = "Ready."

        # Undo / Redo & Selection State
        self.undo_stack: List[Tuple[List[str], int, int]] = []
        self.redo_stack: List[Tuple[List[str], int, int]] = []
        self.select_all_active: bool = False

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
    # Undo / Redo Mechanics
    # --------------------------------------------------------------------------

    def _push_undo(self):
        """Snapshots current buffer and cursor position into undo stack."""
        self.undo_stack.append(([line for line in self.lines], self.cursor_line, self.cursor_col))
        if len(self.undo_stack) > 64:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def undo(self):
        """Reverts text buffer to previous snapshot."""
        if self.undo_stack:
            self.redo_stack.append(([line for line in self.lines], self.cursor_line, self.cursor_col))
            lines, cline, ccol = self.undo_stack.pop()
            self.lines = [line for line in lines]
            self.cursor_line = max(0, min(cline, len(self.lines) - 1))
            self.cursor_col = max(0, min(ccol, len(self.lines[self.cursor_line])))
            self.select_all_active = False
            self.dirty = True
            self.status_msg = f"Undo ({len(self.undo_stack)} actions remaining)"
            self._ensure_cursor_visible()

    def redo(self):
        """Restores previously undone text buffer snapshot."""
        if self.redo_stack:
            self.undo_stack.append(([line for line in self.lines], self.cursor_line, self.cursor_col))
            lines, cline, ccol = self.redo_stack.pop()
            self.lines = [line for line in lines]
            self.cursor_line = max(0, min(cline, len(self.lines) - 1))
            self.cursor_col = max(0, min(ccol, len(self.lines[self.cursor_line])))
            self.select_all_active = False
            self.dirty = True
            self.status_msg = f"Redo ({len(self.redo_stack)} actions remaining)"
            self._ensure_cursor_visible()

    # --------------------------------------------------------------------------
    # Clipboard & Selection Actions
    # --------------------------------------------------------------------------

    def select_all(self):
        """Highlights entire document buffer for batch operations."""
        self.select_all_active = True
        self.status_msg = f"Selected all text ({self.char_count} chars)."

    def copy_selection(self):
        """Copies selection or current line to system clipboard."""
        if self.select_all_active:
            text = "\n".join(self.lines)
        else:
            text = self.lines[self.cursor_line] if self.lines else ""
        SovereignClipboard.get_instance().set_text(text)
        self.status_msg = f"Copied {len(text)} chars to clipboard."

    def cut_selection(self):
        """Cuts selection or current line to system clipboard."""
        self._push_undo()
        if self.select_all_active:
            text = "\n".join(self.lines)
            SovereignClipboard.get_instance().set_text(text)
            self.lines = [""]
            self.cursor_line = 0
            self.cursor_col = 0
            self.select_all_active = False
        else:
            text = self.lines[self.cursor_line] if self.lines else ""
            SovereignClipboard.get_instance().set_text(text)
            if len(self.lines) > 1:
                del self.lines[self.cursor_line]
                if self.cursor_line >= len(self.lines):
                    self.cursor_line = len(self.lines) - 1
                self.cursor_col = min(self.cursor_col, len(self.lines[self.cursor_line]))
            else:
                self.lines = [""]
                self.cursor_col = 0
        self.dirty = True
        self.status_msg = f"Cut {len(text)} chars to clipboard."
        self._ensure_cursor_visible()

    def paste_clipboard(self):
        """Pastes text from clipboard into document buffer."""
        clip_text = SovereignClipboard.get_instance().get_text()
        if not clip_text:
            self.status_msg = "Clipboard is empty."
            return

        self._push_undo()
        paste_lines = clip_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

        if self.select_all_active:
            self.lines = paste_lines or [""]
            self.cursor_line = len(self.lines) - 1
            self.cursor_col = len(self.lines[-1])
            self.select_all_active = False
        else:
            line = self.lines[self.cursor_line]
            left = line[:self.cursor_col]
            right = line[self.cursor_col:]

            if len(paste_lines) == 1:
                self.lines[self.cursor_line] = left + paste_lines[0] + right
                self.cursor_col += len(paste_lines[0])
            else:
                self.lines[self.cursor_line] = left + paste_lines[0]
                for idx in range(1, len(paste_lines) - 1):
                    self.lines.insert(self.cursor_line + idx, paste_lines[idx])
                self.lines.insert(self.cursor_line + len(paste_lines) - 1, paste_lines[-1] + right)
                self.cursor_line += len(paste_lines) - 1
                self.cursor_col = len(paste_lines[-1])

        self.dirty = True
        self.status_msg = f"Pasted {len(clip_text)} chars ({len(paste_lines)} lines)."
        self._ensure_cursor_visible()

    def _delete_word_backward(self):
        """Performs smooth word-level backward deletion across whitespace and tokens."""
        if not self.lines:
            self.lines = [""]
            return

        line = self.lines[self.cursor_line]
        if self.cursor_col == 0:
            if self.cursor_line > 0:
                self._push_undo()
                prev_line = self.lines[self.cursor_line - 1]
                prev_len = len(prev_line)
                self.lines[self.cursor_line - 1] = prev_line + line
                del self.lines[self.cursor_line]
                self.cursor_line -= 1
                self.cursor_col = prev_len
                self.dirty = True
                self._ensure_cursor_visible()
            return

        self._push_undo()
        left = line[:self.cursor_col]
        right = line[self.cursor_col:]

        # 1. Skip trailing spaces to the left of cursor
        i = len(left)
        while i > 0 and left[i - 1] in (' ', '\t'):
            i -= 1

        if i == 0:
            # Entire left was whitespace
            self.lines[self.cursor_line] = right
            self.cursor_col = 0
            self.dirty = True
            self._ensure_cursor_visible()
            return

        # 2. Match token category (word char including underscore vs punctuation)
        def is_word_char(c: str) -> bool:
            return c.isalnum() or c == '_'

        is_word = is_word_char(left[i - 1])
        while i > 0 and left[i - 1] not in (' ', '\t') and (is_word_char(left[i - 1]) == is_word):
            i -= 1

        self.lines[self.cursor_line] = left[:i] + right
        self.cursor_col = i
        self.dirty = True
        self._ensure_cursor_visible()

    # --------------------------------------------------------------------------
    # Document Operations
    # --------------------------------------------------------------------------

    def new_file(self):
        """Resets the document buffer to an empty file."""
        self._push_undo()
        self.lines = [""]
        self.cursor_line = 0
        self.cursor_col = 0
        self.scroll_line = 0
        self.dirty = False
        self.select_all_active = False
        self.status_msg = "New empty document created."
        self.title = f"AdiOS Notepad - [{os.path.basename(self.filename)}]"

    def open_file(self, path: Optional[str] = None):
        """Loads text from disk into document buffer."""
        target = path or self.filename
        try:
            if os.path.exists(target):
                with open(target, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self._push_undo()
                self.lines = content.splitlines() if content else [""]
                self.filename = target
                self.cursor_line = 0
                self.cursor_col = 0
                self.scroll_line = 0
                self.dirty = False
                self.select_all_active = False
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
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
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
        self._push_undo()
        self.lines = [""]
        self.cursor_line = 0
        self.cursor_col = 0
        self.scroll_line = 0
        self.dirty = True
        self.select_all_active = False
        self.status_msg = "Buffer cleared."

    # --------------------------------------------------------------------------
    # Keyboard Navigation and Input
    # --------------------------------------------------------------------------

    def handle_key(self, key_char: str):
        """Processes keystrokes for text editing, shortcuts, and navigation."""
        if not self.lines:
            self.lines = [""]

        # Productivity Shortcuts
        if key_char in ("CTRL_A", "\x01"):
            self.select_all()
            return

        if key_char in ("CTRL_C", "\x03"):
            self.copy_selection()
            return

        if key_char in ("CTRL_X", "\x18"):
            self.cut_selection()
            return

        if key_char in ("CTRL_V", "\x16"):
            self.paste_clipboard()
            return

        if key_char in ("CTRL_Z", "\x1a"):
            self.undo()
            return

        if key_char in ("CTRL_Y", "\x19"):
            self.redo()
            return

        if key_char in ("CTRL_S", "\x13"):
            self.save_file()
            return

        if key_char in ("CTRL_BACKSPACE", "\x7f"):
            self._delete_word_backward()
            return

        if key_char == "CTRL_ENTER":
            self.handle_key("\n")
            return

        # If select all is active, non-shortcut keys operate on entire selection
        if self.select_all_active:
            if key_char in ("\b", "\x08"):
                self._push_undo()
                self.lines = [""]
                self.cursor_line = 0
                self.cursor_col = 0
                self.select_all_active = False
                self.dirty = True
                self._ensure_cursor_visible()
                return
            elif key_char in ("\r", "\n"):
                self._push_undo()
                self.lines = ["", ""]
                self.cursor_line = 1
                self.cursor_col = 0
                self.select_all_active = False
                self.dirty = True
                self._ensure_cursor_visible()
                return
            elif key_char in ("KEY_UP", "KEY_DOWN", "KEY_LEFT", "KEY_RIGHT", "\x1b[A", "\x1b[B", "\x1b[C", "\x1b[D"):
                self.select_all_active = False
            elif len(key_char) == 1 and ord(key_char) >= 32:
                self._push_undo()
                self.lines = [key_char]
                self.cursor_line = 0
                self.cursor_col = 1
                self.select_all_active = False
                self.dirty = True
                self._ensure_cursor_visible()
                return

        # 1. Newline (Enter)
        if key_char in ("\r", "\n"):
            self._push_undo()
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
                self._push_undo()
                # Check for 4-space unindent
                if line[:self.cursor_col].endswith("    ") and self.cursor_col >= 4:
                    self.lines[self.cursor_line] = line[:self.cursor_col - 4] + line[self.cursor_col:]
                    self.cursor_col -= 4
                else:
                    self.lines[self.cursor_line] = line[:self.cursor_col - 1] + line[self.cursor_col:]
                    self.cursor_col -= 1
                self.dirty = True
            elif self.cursor_line > 0:
                self._push_undo()
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
            self._push_undo()
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
            if key_char == " " or self.cursor_col == 0 or self.cursor_col % 8 == 0:
                self._push_undo()
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

            # Line highlight: full selection or active cursor line
            if self.select_all_active:
                sel_bg = 0x001E3A5F if pal.name != "Arctic Minimal" else 0x00C7D2FE
                self._fill_rect(fb, text_x - 4, line_y - 2, text_w, line_h, sel_bg)
            elif line_idx == self.cursor_line:
                self._fill_rect(fb, text_x - 4, line_y - 2, text_w, line_h, pal.btn_bg)

            # Render Line Text
            raw_line = self.lines[line_idx]
            text_color = pal.text_highlight if self.select_all_active else pal.text_primary
            self._draw_text(fb, text_x, line_y, raw_line[:text_w // CHAR_WIDTH], text_color, font_dict)

            # Render Cursor Bar (if not in select-all mode)
            if not self.select_all_active and line_idx == self.cursor_line:
                cur_x = text_x + self.cursor_col * CHAR_WIDTH
                if text_x <= cur_x <= cx + cw - 4:
                    self._fill_rect(fb, cur_x, line_y, 2, 13, pal.accent_primary)

        # 4. Bottom Status Bar
        sb_y = cy + ch - status_h
        self._fill_rect(fb, cx, sb_y, cw, status_h, pal.gutter_bg)
        self._draw_hline(fb, cx, sb_y, cw, pal.card_border)

        dirty_tag = " *" if self.dirty else ""
        sel_tag = " [ALL SELECTED]" if self.select_all_active else ""
        stat_txt = (
            f"Ln {self.cursor_line + 1}, Col {self.cursor_col + 1} | "
            f"{self.word_count} words | {self.char_count} chars | "
            f"'{self.filename}'{dirty_tag}{sel_tag} | {self.status_msg}"
        )
        self._draw_text(fb, cx + 10, sb_y + 5, stat_txt[:cw // CHAR_WIDTH - 2], pal.text_muted, font_dict)

    def _render_toolbar(self, fb: bytearray, x: int, y: int, w: int, h: int, pal: Any, font_dict: Dict):
        """Renders toolbar action buttons."""
        self._fill_rect(fb, x, y, w, h, pal.gutter_bg)
        self._draw_hline(fb, x, y + h - 1, w, pal.card_border)

        buttons = [
            ("New", 46),
            ("Open", 48),
            ("Save", 48),
            ("Undo", 48),
            ("Copy", 48),
            ("Paste", 52),
            ("Clear", 52),
            ("Nums", 50)
        ]
        curr_x = x + 8
        for label, bw in buttons:
            self._fill_rect(fb, curr_x, y + 4, bw, h - 8, pal.btn_bg)
            self._draw_rect_outline(fb, curr_x, y + 4, bw, h - 8, pal.btn_border)
            self._draw_text(fb, curr_x + 6, y + 8, label, pal.text_primary, font_dict)
            curr_x += bw + 5

    def _handle_click(self, win: Window, rel_x: int, rel_y: int):
        """Handles toolbar button clicks and canvas cursor placement."""
        # Check toolbar buttons
        if rel_y <= 28:
            curr_x = 8
            if curr_x <= rel_x <= curr_x + 46:
                self.new_file()
            elif curr_x + 51 <= rel_x <= curr_x + 99:
                self.open_file()
            elif curr_x + 104 <= rel_x <= curr_x + 152:
                self.save_file()
            elif curr_x + 157 <= rel_x <= curr_x + 205:
                self.undo()
            elif curr_x + 210 <= rel_x <= curr_x + 258:
                self.copy_selection()
            elif curr_x + 263 <= rel_x <= curr_x + 315:
                self.paste_clipboard()
            elif curr_x + 320 <= rel_x <= curr_x + 372:
                self.clear_all()
            elif curr_x + 377 <= rel_x <= curr_x + 427:
                self.show_line_numbers = not self.show_line_numbers
                self.status_msg = f"Line numbers: {'ON' if self.show_line_numbers else 'OFF'}"
            return

        # Check canvas click to place cursor
        self.select_all_active = False
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
