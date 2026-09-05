#!/usr/bin/env python3
"""
AdiOS Desktop Icon Subsystem (DesktopIconManager)
Sovereign Workstation v2.0 Stable.
Renders high-fidelity vector icons with hover glow, selection states,
and single-click / double-click launch dispatch.
STRICT ZERO EMOJI POLICY.
"""

import time
from typing import List, Optional, Tuple, Callable, Dict, Any
from graphics.engine2d import draw_procedural_icon, draw_rounded_rect

COLOR_ICON_HOVER = 0x002A2E42
COLOR_ICON_SEL   = 0x003D59A1
COLOR_LABEL_TXT  = 0x00C0CAF5
COLOR_LABEL_SEL  = 0x007AA2F7
CHAR_WIDTH  = 8
CHAR_HEIGHT = 8

class DesktopIcon:
    def __init__(self, icon_id: str, label: str, icon_type: str, action_target: str, x: int, y: int, size: int = 38):
        self.icon_id = icon_id
        self.label = label
        self.icon_type = icon_type
        self.action_target = action_target
        self.x = x
        self.y = y
        self.size = size
        self.width = 68
        self.height = 72
        self.selected = False
        self.hover = False

    @property
    def bounds(self) -> Tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.width and self.y <= py < self.y + self.height


class DesktopIconManager:
    """Manages desktop quick-launch icons rendered directly onto the desktop layer."""
    def __init__(self, screen_w: int = 1280, screen_h: int = 720):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.icons: List[DesktopIcon] = []
        self.last_click_time: float = 0.0
        self.last_clicked_icon: Optional[DesktopIcon] = None
        self.double_click_interval: float = 0.40  # 400ms

        self._setup_default_icons()

    def _setup_default_icons(self):
        default_items = [
            ("sysinfo",  "System",     "computer", "browser",  0x007AA2F7),
            ("youtube",  "YouTube",    "youtube",  "youtube",  0x00F7768E),
            ("games",    "3D Arcade",  "games",    "games",    0x00BB9AF7),
            ("explorer", "AdiFS Files","explorer", "explorer", 0x00E0AF68),
            ("shell",    "Cyber Shell","shell",    "shell",    0x009ECE6A),
            ("settings", "Audio/Set",  "settings", "sound_cfg",0x0073DACA),
        ]

        start_x = 24
        start_y = 38
        spacing_y = 82

        for idx, (iid, label, itype, target, accent) in enumerate(default_items):
            iy = start_y + idx * spacing_y
            icon = DesktopIcon(iid, label, itype, target, start_x, iy, size=38)
            icon.accent = accent
            self.icons.append(icon)

    def get_icon_at(self, mx: int, my: int) -> Optional[DesktopIcon]:
        for icon in self.icons:
            if icon.contains(mx, my):
                return icon
        return None

    def handle_mouse_move(self, mx: int, my: int):
        for icon in self.icons:
            icon.hover = icon.contains(mx, my)

    def handle_mouse_down(self, mx: int, my: int) -> Tuple[Optional[str], Optional[DesktopIcon]]:
        """
        Handles mouse click on icons.
        Returns ('launch', icon) on double-click, ('select', icon) on single click, or (None, None).
        """
        now = time.time()
        clicked = self.get_icon_at(mx, my)

        # Unselect all other icons
        for icon in self.icons:
            if icon != clicked:
                icon.selected = False

        if not clicked:
            return None, None

        clicked.selected = True

        # Check double click
        if self.last_clicked_icon == clicked and (now - self.last_click_time) <= self.double_click_interval:
            self.last_click_time = 0.0
            self.last_clicked_icon = None
            return "launch", clicked

        self.last_click_time = now
        self.last_clicked_icon = clicked
        return "select", clicked

    def render(self, fb: bytearray, font_dict: Dict, screen_w: int, screen_h: int):
        """Draws all desktop icons onto the framebuffer layer."""
        self.screen_w = screen_w
        self.screen_h = screen_h

        for icon in self.icons:
            ix, iy, iw, ih = icon.bounds

            # 1. Selection / Hover background highlight plate
            if icon.selected:
                draw_rounded_rect(fb, ix - 2, iy - 2, iw + 4, ih + 4, radius=8, fill_color=COLOR_ICON_SEL, border_color=COLOR_LABEL_SEL, screen_w=screen_w, screen_h=screen_h)
            elif icon.hover:
                draw_rounded_rect(fb, ix - 2, iy - 2, iw + 4, ih + 4, radius=8, fill_color=COLOR_ICON_HOVER, screen_w=screen_w, screen_h=screen_h)

            # 2. Draw Vector Icon centrally
            glyph_x = ix + (iw - icon.size) // 2
            glyph_y = iy + 4
            draw_procedural_icon(fb, glyph_x, glyph_y, icon.icon_type, size=icon.size, accent_color=getattr(icon, 'accent', 0x007AA2F7), screen_w=screen_w, screen_h=screen_h)

            # 3. Draw text label centered below icon
            label_len = len(icon.label) * CHAR_WIDTH
            label_x = ix + (iw - label_len) // 2
            label_y = glyph_y + icon.size + 6
            txt_color = COLOR_LABEL_SEL if icon.selected else COLOR_LABEL_TXT

            self._draw_string(fb, label_x, label_y, icon.label, txt_color, font_dict, screen_w, screen_h)

    def _draw_string(self, fb: bytearray, x: int, y: int, text: str, color: int, font_dict: Dict, screen_w: int, screen_h: int):
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        curr_x = x
        for ch in text:
            if curr_x + CHAR_WIDTH > screen_w:
                break
            glyph = font_dict.get(ord(ch), font_dict.get(ch, None)) if font_dict else None
            if glyph:
                for row in range(CHAR_HEIGHT):
                    py = y + row
                    if 0 <= py < screen_h:
                        bits = glyph[row]
                        for col in range(CHAR_WIDTH):
                            px = curr_x + col
                            if 0 <= px < screen_w:
                                if (bits >> (7 - col)) & 1:
                                    idx = (py * screen_w + px) * 4
                                    fb[idx : idx + 4] = c_bytes
            curr_x += CHAR_WIDTH
