#!/usr/bin/env python3
"""
AdiOS Sovereign File Explorer (desktop/file_explorer.py)
A modern visual file manager with dual-pane navigation:
- Left Sidebar: Quick access to system and user folders (Home, Scripts, Media, Desktop, Root).
- Main File Pane: File cards with extension-aware badges, sizes, modified dates.
- Integration: Opens scripts directly into Code Studio and media into Media Player.

Strict Zero Emoji Policy.
"""

import os
import time
from typing import List, Tuple, Dict, Optional, Any, Callable

from .window_manager import Window, CHAR_WIDTH, CHAR_HEIGHT
from .theme import ThemeManager

class FileEntry:
    def __init__(self, name: str, path: str, is_dir: bool, size: int, mtime: float):
        self.name = name
        self.path = path
        self.is_dir = is_dir
        self.size = size
        self.mtime = mtime

    @property
    def formatted_size(self) -> str:
        if self.is_dir:
            return "<DIR>"
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} KB"
        else:
            return f"{self.size / (1024 * 1024):.1f} MB"

    @property
    def file_type(self) -> str:
        if self.is_dir:
            return "Folder"
        ext = os.path.splitext(self.name)[1].lower()
        types = {
            ".py": "Python Script",
            ".ap": "AdiPython Script",
            ".s": "RISC-V Assembly",
            ".c": "C Source",
            ".h": "C Header",
            ".wav": "Wave Audio",
            ".mp4": "MPEG-4 Video",
            ".webm": "WebM Video",
            ".md": "Markdown Doc",
            ".txt": "Plain Text",
            ".json": "JSON Data",
            ".iso": "Disk Image",
            ".bin": "Binary Image"
        }
        return types.get(ext, "File")

class FileExplorer(Window):
    """
    Sovereign File Explorer Window.
    """
    def __init__(
        self,
        win_id: str = "explorer",
        x: int = 120,
        y: int = 80,
        w: int = 740,
        h: int = 480,
        on_open_file: Optional[Callable[[str], None]] = None
    ):
        super().__init__(
            win_id=win_id,
            title="AdiOS File Explorer",
            x=x,
            y=y,
            w=w,
            h=h,
            bg_color=0x00131822
        )
        self.on_open_file = on_open_file
        self.current_dir = os.path.abspath(".")
        self.places = [
            ("Root", os.path.abspath(".")),
            ("Scripts", os.path.abspath("scripts")),
            ("Desktop", os.path.abspath("desktop")),
            ("Graphics", os.path.abspath("graphics")),
            ("Tests", os.path.abspath("tests"))
        ]
        self.entries: List[FileEntry] = []
        self.selected_idx: int = -1
        self.scroll_idx: int = 0
        self.status_msg: str = "Ready."

        self.refresh_directory()
        self.on_draw_content = self._render_content
        self.on_click_content = self._handle_click

    def refresh_directory(self):
        """Scans current_dir and populates FileEntry list."""
        self.entries.clear()
        try:
            items = os.listdir(self.current_dir)
            dirs = []
            files = []
            for it in items:
                p = os.path.join(self.current_dir, it)
                try:
                    st = os.stat(p)
                    is_d = os.path.isdir(p)
                    entry = FileEntry(it, p, is_d, st.st_size, st.st_mtime)
                    if is_d:
                        dirs.append(entry)
                    else:
                        files.append(entry)
                except Exception:
                    pass

            dirs.sort(key=lambda e: e.name.lower())
            files.sort(key=lambda e: e.name.lower())
            self.entries = dirs + files
            self.status_msg = f"{len(dirs)} folders, {len(files)} files in '{os.path.basename(self.current_dir) or self.current_dir}'"
        except Exception as e:
            self.status_msg = f"Error reading directory: {e}"

    def navigate_to(self, path: str):
        """Navigates to specified directory."""
        if os.path.isdir(path):
            self.current_dir = os.path.abspath(path)
            self.selected_idx = -1
            self.scroll_idx = 0
            self.refresh_directory()

    def navigate_up(self):
        """Navigates to parent directory."""
        parent = os.path.dirname(self.current_dir)
        if parent and parent != self.current_dir:
            self.navigate_to(parent)

    def _render_content(self, win: Window, fb: bytearray, font_dict: Dict):
        """Composites dual-pane file explorer view."""
        cx, cy, cw, ch = self.client_rect
        tm = ThemeManager.get_instance()
        pal = tm.palette

        # 1. Breadcrumb Location Bar
        bar_h = 30
        self._render_address_bar(fb, cx, cy, cw, bar_h, pal, font_dict)

        # 2. Left Sidebar (width: 150px)
        sidebar_w = 150
        body_y = cy + bar_h
        body_h = ch - bar_h - 22
        self._render_sidebar(fb, cx, body_y, sidebar_w, body_h, pal, font_dict)

        # 3. Main File List Pane
        file_pane_x = cx + sidebar_w + 1
        file_pane_w = cw - sidebar_w - 1
        self._render_file_pane(fb, file_pane_x, body_y, file_pane_w, body_h, pal, font_dict)

        # 4. Status Bar (bottom 22px)
        status_y = cy + ch - 22
        self._render_status_bar(fb, cx, status_y, cw, 22, pal, font_dict)

    def _render_address_bar(self, fb: bytearray, x: int, y: int, w: int, h: int, pal: Any, font_dict: Dict):
        """Renders top location and navigation bar."""
        self._fill_rect(fb, x, y, w, h, pal.gutter_bg)
        self._draw_hline(fb, x, y + h - 1, w, pal.card_border)

        # [Up] Navigation Button
        self._fill_rect(fb, x + 8, y + 5, 45, h - 10, pal.btn_bg)
        self._draw_rect_outline(fb, x + 8, y + 5, 45, h - 10, pal.btn_border)
        self._draw_text(fb, x + 18, y + 9, "[..]", pal.text_primary, font_dict)

        # Path display card
        path_box_x = x + 60
        path_box_w = w - 70
        self._fill_rect(fb, path_box_x, y + 5, path_box_w, h - 10, pal.win_bg)
        self._draw_rect_outline(fb, path_box_x, y + 5, path_box_w, h - 10, pal.card_border)
        
        display_path = self.current_dir
        if len(display_path) * CHAR_WIDTH > path_box_w - 20:
            display_path = "..." + display_path[-(path_box_w // CHAR_WIDTH - 6):]
        self._draw_text(fb, path_box_x + 8, y + 9, display_path, pal.text_highlight, font_dict)

    def _render_sidebar(self, fb: bytearray, x: int, y: int, w: int, h: int, pal: Any, font_dict: Dict):
        """Renders places sidebar with quick-access locations."""
        self._fill_rect(fb, x, y, w, h, pal.gutter_bg)
        self._draw_vline(fb, x + w, y, h, pal.card_border)

        # Places Header
        self._draw_text(fb, x + 12, y + 10, "PLACES", pal.text_muted, font_dict)

        curr_y = y + 30
        for name, path in self.places:
            is_active = (self.current_dir == path)
            if is_active:
                self._fill_rect(fb, x + 6, curr_y - 2, w - 12, 22, pal.card_bg)
                self._draw_rect_outline(fb, x + 6, curr_y - 2, w - 12, 22, pal.card_border)
                self._draw_vline(fb, x + 6, curr_y - 2, 22, pal.accent_primary)
                txt_col = pal.accent_primary
            else:
                txt_col = pal.text_primary

            self._draw_text(fb, x + 16, curr_y + 3, name, txt_col, font_dict)
            curr_y += 28

    def _render_file_pane(self, fb: bytearray, x: int, y: int, w: int, h: int, pal: Any, font_dict: Dict):
        """Renders file rows table with type badges, names, and sizes."""
        self._fill_rect(fb, x, y, w, h, pal.win_bg)

        # Table Header
        hdr_h = 24
        self._fill_rect(fb, x, y, w, hdr_h, pal.card_bg)
        self._draw_hline(fb, x, y + hdr_h - 1, w, pal.card_border)

        self._draw_text(fb, x + 12, y + 7, "Name", pal.text_muted, font_dict)
        self._draw_text(fb, x + w - 190, y + 7, "Type", pal.text_muted, font_dict)
        self._draw_text(fb, x + w - 80, y + 7, "Size", pal.text_muted, font_dict)

        # Render rows
        row_h = 24
        visible_rows = (h - hdr_h) // row_h
        row_y = y + hdr_h

        for idx in range(visible_rows):
            entry_idx = self.scroll_idx + idx
            if entry_idx >= len(self.entries):
                break

            entry = self.entries[entry_idx]
            is_sel = (entry_idx == self.selected_idx)

            if is_sel:
                self._fill_rect(fb, x + 2, row_y, w - 4, row_h - 1, pal.btn_bg)
                self._draw_rect_outline(fb, x + 2, row_y, w - 4, row_h - 1, pal.accent_primary)

            # Icon Badge
            badge_char = "[D]" if entry.is_dir else "[F]"
            badge_col = pal.accent_primary if entry.is_dir else pal.text_muted
            self._draw_text(fb, x + 8, row_y + 6, badge_char, badge_col, font_dict)

            # Name
            name_txt = entry.name[:(w - 230) // CHAR_WIDTH]
            name_col = pal.text_primary if not entry.is_dir else pal.text_highlight
            self._draw_text(fb, x + 38, row_y + 6, name_txt, name_col, font_dict)

            # Type
            type_txt = entry.file_type[:12]
            self._draw_text(fb, x + w - 190, row_y + 6, type_txt, pal.text_muted, font_dict)

            # Size
            size_txt = entry.formatted_size
            self._draw_text(fb, x + w - 80, row_y + 6, size_txt, pal.text_muted, font_dict)

            row_y += row_h

    def _render_status_bar(self, fb: bytearray, x: int, y: int, w: int, h: int, pal: Any, font_dict: Dict):
        """Renders bottom status information."""
        self._fill_rect(fb, x, y, w, h, pal.gutter_bg)
        self._draw_hline(fb, x, y, w, pal.card_border)
        self._draw_text(fb, x + 12, y + 6, self.status_msg, pal.text_muted, font_dict)

    def _handle_click(self, win: Window, rel_x: int, rel_y: int):
        """Handles clicks on navigation buttons, sidebar places, and file entries."""
        # [..] Up button
        if rel_y <= 30 and 8 <= rel_x <= 53:
            self.navigate_up()
            return

        # Sidebar places click
        if 30 <= rel_y < win.h - 22 and rel_x <= 150:
            curr_y = 60
            for name, path in self.places:
                if curr_y - 2 <= rel_y <= curr_y + 20:
                    self.navigate_to(path)
                    return
                curr_y += 28
            return

        # File rows click
        hdr_h = 54
        if hdr_h <= rel_y < win.h - 22 and rel_x > 150:
            row_idx = (rel_y - hdr_h) // 24
            clicked_idx = self.scroll_idx + row_idx
            if clicked_idx < len(self.entries):
                if self.selected_idx == clicked_idx:
                    # Double-click behavior: open entry
                    entry = self.entries[clicked_idx]
                    if entry.is_dir:
                        self.navigate_to(entry.path)
                    else:
                        if self.on_open_file:
                            self.on_open_file(entry.path)
                        self.status_msg = f"Opened file: {entry.name}"
                else:
                    self.selected_idx = clicked_idx
                    sel_entry = self.entries[clicked_idx]
                    self.status_msg = f"Selected: {sel_entry.name} ({sel_entry.formatted_size})"

    # --------------------------------------------------------------------------
    # Framebuffer Drawing Primitives
    # --------------------------------------------------------------------------

    def _fill_rect(self, fb: bytearray, x: int, y: int, w: int, h: int, color: int):
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        from .window_manager import WIDTH, HEIGHT
        for dy in range(h):
            py = y + dy
            if 0 <= py < HEIGHT:
                for dx in range(w):
                    px = x + dx
                    if 0 <= px < WIDTH:
                        fb[(py * WIDTH + px) * 4 : (py * WIDTH + px + 1) * 4] = c_bytes

    def _draw_hline(self, fb: bytearray, x: int, y: int, w: int, color: int):
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        from .window_manager import WIDTH, HEIGHT
        if 0 <= y < HEIGHT:
            for dx in range(w):
                px = x + dx
                if 0 <= px < WIDTH:
                    fb[(y * WIDTH + px) * 4 : (y * WIDTH + px + 1) * 4] = c_bytes

    def _draw_vline(self, fb: bytearray, x: int, y: int, h: int, color: int):
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        from .window_manager import WIDTH, HEIGHT
        if 0 <= x < WIDTH:
            for dy in range(h):
                py = y + dy
                if 0 <= py < HEIGHT:
                    fb[(py * WIDTH + x) * 4 : (py * WIDTH + x + 1) * 4] = c_bytes

    def _draw_rect_outline(self, fb: bytearray, x: int, y: int, w: int, h: int, color: int):
        self._draw_hline(fb, x, y, w, color)
        self._draw_hline(fb, x, y + h - 1, w, color)
        self._draw_vline(fb, x, y, h, color)
        self._draw_vline(fb, x + w - 1, y, h, color)

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
