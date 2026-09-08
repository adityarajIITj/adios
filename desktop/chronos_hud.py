#!/usr/bin/env python3
"""
AdiOS Chronos Time-Travel HUD Overlay (desktop/chronos_hud.py)
Visual interface for the Chronos temporal rewind and replay engine:
- Renders an interactive floating temporal deck across the top of the desktop.
- Timeline scrubber with live time-offset telemetry (-04.28s to NOW).
- Temporal transport buttons: Rewind, Pause, Fast Forward, Fork Reality, Resume Live.
- Subtle temporal scanline overlay during time inspection.
- Mouse dragging and click-seeking across historical snapshots.

Strict Zero Emoji Policy Enforced.
"""

from typing import Tuple, Dict, Optional, Any
from kernel.chronos import ChronosEngine

# Chronos Temporal Theme Colors
COLOR_CHRONOS_BG       = 0xEE0B0E14
COLOR_CHRONOS_BORDER   = 0x00FFB000  # Glowing Amber Gold
COLOR_CHRONOS_AMBER    = 0x00D97706
COLOR_CHRONOS_GOLD     = 0x00FBBF24
COLOR_CHRONOS_PAST     = 0x00EF4444  # Crimson Past
COLOR_CHRONOS_NOW      = 0x0010B981  # Emerald Present
COLOR_CHRONOS_BTN_BG   = 0x00181C26
COLOR_CHRONOS_BTN_BRD  = 0x003A435E
COLOR_CHRONOS_TXT      = 0x00F3F4F6
COLOR_SCRUB_TRACK      = 0x001E2433
COLOR_SCRUB_TICK       = 0x00374151
COLOR_SCRUB_HANDLE     = 0x00FFD700


class ChronosHUD:
    """
    Floating temporal control overlay rendered above all desktop windows
    when Chronos Time-Travel mode is engaged.
    """

    def __init__(self, screen_w: int = 1280, screen_h: int = 720):
        self.screen_w = screen_w
        self.screen_h = screen_h

        # Deck Geometry (centered at top)
        self.hud_w = min(880, screen_w - 60)
        self.hud_h = 68
        self.hud_x = (screen_w - self.hud_w) // 2
        self.hud_y = 36

        # Scrubber bar relative bounds inside HUD
        self.scrub_rel_x = 16
        self.scrub_rel_y = 26
        self.scrub_w = self.hud_w - 32
        self.scrub_h = 10

        # Drag state
        self.is_dragging_scrubber: bool = False

    def render(self, fb: bytearray, chronos: ChronosEngine, desktop: Any, font_dict: Dict):
        """
        Renders the temporal scanline ambiance and the floating Chronos HUD.
        """
        if not chronos.is_active:
            return

        screen_w = desktop.width if hasattr(desktop, "width") else self.screen_w
        screen_h = desktop.height if hasattr(desktop, "height") else self.screen_h
        clip = (0, 0, screen_w, screen_h)

        # 1. Subtle Temporal Scanline Overlay across entire desktop
        self._render_temporal_scanlines(fb, screen_w, screen_h)

        # 2. Floating Deck Frame
        hx, hy, hw, hh = self.hud_x, self.hud_y, self.hud_w, self.hud_h
        hud_clip = (hx, hy, hx + hw, hy + hh)

        # Draw HUD body and glowing amber border
        self._fill_rect(fb, screen_w, hx, hy, hw, hh, COLOR_CHRONOS_BG, clip)
        self._draw_rect(fb, screen_w, hx, hy, hw, hh, COLOR_CHRONOS_BORDER, clip)
        self._draw_rect(fb, screen_w, hx + 1, hy + 1, hw - 2, hh - 2, COLOR_CHRONOS_AMBER, clip)

        # 3. Header Text & Timecode
        offset_s = chronos.current_time_offset
        is_at_now = (abs(offset_s) < 0.05 or chronos.scrub_index >= chronos.frame_count - 1)

        # Left Title
        self._draw_text(fb, screen_w, hx + 16, hy + 8, "ADIOS CHRONOS: TIME-TRAVEL REWIND", COLOR_CHRONOS_GOLD, clip)

        # Center Timecode
        if is_at_now:
            time_txt = "[NOW (LIVE PRESENT)]"
            time_col = COLOR_CHRONOS_NOW
        else:
            time_txt = f"[{offset_s:.2f}s REWOUND PAST]"
            time_col = COLOR_CHRONOS_PAST
        tx = hx + (hw - len(time_txt) * 8) // 2
        self._draw_text(fb, screen_w, tx, hy + 8, time_txt, time_col, clip)

        # Right Telemetry
        frames_txt = f"{chronos.scrub_index + 1}/{chronos.frame_count} Snapshots"
        rx = hx + hw - len(frames_txt) * 8 - 16
        self._draw_text(fb, screen_w, rx, hy + 8, frames_txt, 0x009CA3AF, clip)

        # 4. Interactive Timeline Scrubber Track
        sx = hx + self.scrub_rel_x
        sy = hy + self.scrub_rel_y
        sw = self.scrub_w
        sh = self.scrub_h

        # Scrubber Groove
        self._fill_rect(fb, screen_w, sx, sy, sw, sh, COLOR_SCRUB_TRACK, clip)
        self._draw_rect(fb, screen_w, sx, sy, sw, sh, COLOR_CHRONOS_BTN_BRD, clip)

        # Keyframe tick marks
        if chronos.frame_count > 1:
            step_px = max(1, sw // max(1, min(50, chronos.frame_count)))
            for tx_pos in range(sx, sx + sw, step_px):
                self._draw_line(fb, screen_w, tx_pos, sy, tx_pos, sy + sh - 1, COLOR_SCRUB_TICK, clip)

        # Fill to scrub handle
        fill_w = int(sw * chronos.scrub_fraction)
        if fill_w > 0:
            self._fill_rect(fb, screen_w, sx, sy, fill_w, sh, COLOR_CHRONOS_AMBER, clip)

        # Scrub Handle
        hx_pos = sx + fill_w
        self._fill_rect(fb, screen_w, max(sx, hx_pos - 4), sy - 2, 8, sh + 4, COLOR_SCRUB_HANDLE, clip)
        self._draw_rect(fb, screen_w, max(sx, hx_pos - 4), sy - 2, 8, sh + 4, 0x00FFFFFF, clip)

        # 5. Transport Controls Toolbar
        by = sy + sh + 6
        bx = sx
        bh = 18

        # [<< REW]
        rew_bg = COLOR_CHRONOS_GOLD if chronos.is_playing_reverse else COLOR_CHRONOS_BTN_BG
        rew_fg = 0x000000 if chronos.is_playing_reverse else COLOR_CHRONOS_TXT
        self._draw_button(fb, screen_w, bx, by, 62, bh, "<< REW", rew_bg, rew_fg, clip)
        bx += 68

        # [|| PAUSE]
        self._draw_button(fb, screen_w, bx, by, 50, bh, "PAUSE", COLOR_CHRONOS_BTN_BG, COLOR_CHRONOS_TXT, clip)
        bx += 56

        # [FWD >>]
        fwd_bg = COLOR_CHRONOS_GOLD if chronos.is_playing_forward else COLOR_CHRONOS_BTN_BG
        fwd_fg = 0x000000 if chronos.is_playing_forward else COLOR_CHRONOS_TXT
        self._draw_button(fb, screen_w, bx, by, 62, bh, "FWD >>", fwd_bg, fwd_fg, clip)
        bx += 74

        # [FORK REALITY] (Commit historical point as new present)
        self._draw_button(fb, screen_w, bx, by, 114, bh, "FORK REALITY", 0x002B180A, COLOR_CHRONOS_GOLD, clip)
        bx += 122

        # [RESUME LIVE (Esc)]
        self._draw_button(fb, screen_w, bx, by, 140, bh, "RESUME LIVE (Esc)", 0x000F291E, COLOR_CHRONOS_NOW, clip)

        # Right Side Help Hint
        help_txt = "Drag Scrubber or use Left/Right arrows"
        h_rx = hx + hw - len(help_txt) * 8 - 16
        self._draw_text(fb, screen_w, h_rx, by + 4, help_txt, 0x006B7280, clip)

    def handle_mouse_down(self, mx: int, my: int, chronos: ChronosEngine, desktop: Any) -> bool:
        """
        Dispatches mouse clicks on the Chronos HUD.
        Returns True if the event was consumed by the HUD.
        """
        if not chronos.is_active:
            return False

        hx, hy, hw, hh = self.hud_x, self.hud_y, self.hud_w, self.hud_h
        if not (hx <= mx <= hx + hw and hy <= my <= hy + hh):
            return False

        # 1. Clicked Timeline Scrubber
        sx = hx + self.scrub_rel_x
        sy = hy + self.scrub_rel_y
        sw = self.scrub_w
        sh = self.scrub_h

        if sx <= mx <= sx + sw and sy - 4 <= my <= sy + sh + 4:
            self.is_dragging_scrubber = True
            fraction = (mx - sx) / float(max(1, sw))
            chronos.scrub_to_fraction(fraction, desktop)
            chronos.is_playing_reverse = False
            chronos.is_playing_forward = False
            return True

        # 2. Clicked Buttons
        by = sy + sh + 6
        bx = sx
        bh = 18

        # [<< REW]
        if bx <= mx <= bx + 62 and by <= my <= by + bh:
            chronos.is_playing_reverse = not chronos.is_playing_reverse
            chronos.is_playing_forward = False
            return True
        bx += 68

        # [PAUSE]
        if bx <= mx <= bx + 50 and by <= my <= by + bh:
            chronos.is_playing_reverse = False
            chronos.is_playing_forward = False
            return True
        bx += 56

        # [FWD >>]
        if bx <= mx <= bx + 62 and by <= my <= by + bh:
            chronos.is_playing_forward = not chronos.is_playing_forward
            chronos.is_playing_reverse = False
            return True
        bx += 74

        # [FORK REALITY]
        if bx <= mx <= bx + 114 and by <= my <= by + bh:
            chronos.fork_reality(desktop)
            return True
        bx += 122

        # [RESUME LIVE]
        if bx <= mx <= bx + 140 and by <= my <= by + bh:
            chronos.resume_live(desktop)
            return True

        return True

    def handle_mouse_drag(self, mx: int, my: int, chronos: ChronosEngine, desktop: Any) -> bool:
        """Handles smooth timeline dragging."""
        if not chronos.is_active or not self.is_dragging_scrubber:
            return False

        sx = self.hud_x + self.scrub_rel_x
        sw = self.scrub_w
        fraction = max(0.0, min(1.0, (mx - sx) / float(max(1, sw))))
        chronos.scrub_to_fraction(fraction, desktop)
        chronos.is_playing_reverse = False
        chronos.is_playing_forward = False
        return True

    def handle_mouse_up(self, mx: int, my: int):
        self.is_dragging_scrubber = False

    def _render_temporal_scanlines(self, fb: bytearray, screen_w: int, screen_h: int):
        """Draws faint temporal scanning ambiance across the screen."""
        mv = memoryview(fb)
        line_bytes = bytes([0x00, 0x14, 0x1E, 0x00]) * screen_w
        for y in range(0, screen_h, 4):
            off = y * screen_w * 4
            # Additive or blend
            mv[off : off + screen_w * 4] = line_bytes

    def _fill_rect(self, fb: bytearray, screen_w: int, x: int, y: int, w: int, h: int, color: int, clip: Tuple):
        x1 = max(clip[0], x)
        y1 = max(clip[1], y)
        x2 = min(clip[2], x + w)
        y2 = min(clip[3], y + h)
        if x2 <= x1 or y2 <= y1:
            return
        b = color & 0xFF
        g = (color >> 8) & 0xFF
        r = (color >> 16) & 0xFF
        a = (color >> 24) & 0xFF or 0xFF
        row_bytes = bytearray([b, g, r, a] * (x2 - x1))
        mv = memoryview(fb)
        for row in range(y1, y2):
            off = (row * screen_w + x1) * 4
            mv[off : off + (x2 - x1) * 4] = row_bytes

    def _draw_rect(self, fb: bytearray, screen_w: int, x: int, y: int, w: int, h: int, color: int, clip: Tuple):
        self._draw_line(fb, screen_w, x, y, x + w - 1, y, color, clip)
        self._draw_line(fb, screen_w, x, y + h - 1, x + w - 1, y + h - 1, color, clip)
        self._draw_line(fb, screen_w, x, y, x, y + h - 1, color, clip)
        self._draw_line(fb, screen_w, x + w - 1, y, x + w - 1, y + h - 1, color, clip)

    def _draw_line(self, fb: bytearray, screen_w: int, x1: int, y1: int, x2: int, y2: int, color: int, clip: Tuple):
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        curr_x, curr_y = x1, y1
        b = color & 0xFF
        g = (color >> 8) & 0xFF
        r = (color >> 16) & 0xFF
        while True:
            if clip[0] <= curr_x < clip[2] and clip[1] <= curr_y < clip[3]:
                off = (curr_y * screen_w + curr_x) * 4
                fb[off] = b
                fb[off + 1] = g
                fb[off + 2] = r
                fb[off + 3] = 0xFF
            if curr_x == x2 and curr_y == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                curr_x += sx
            if e2 < dx:
                err += dx
                curr_y += sy

    def _draw_button(self, fb: bytearray, screen_w: int, x: int, y: int, w: int, h: int, text: str, bg: int, fg: int, clip: Tuple):
        self._fill_rect(fb, screen_w, x, y, w, h, bg, clip)
        self._draw_rect(fb, screen_w, x, y, w, h, COLOR_CHRONOS_BTN_BRD, clip)
        tx = x + max(2, (w - len(text) * 8) // 2)
        ty = y + max(2, (h - 10) // 2)
        self._draw_text(fb, screen_w, tx, ty, text, fg, clip)

    def _draw_text(self, fb: bytearray, screen_w: int, x: int, y: int, text: str, color: int, clip: Tuple):
        from .font import get_default_font
        font = get_default_font()
        b = color & 0xFF
        g = (color >> 8) & 0xFF
        r = (color >> 16) & 0xFF
        cx = x
        for ch in text:
            glyph = font.get(ch, font.get(ord(ch), None))
            if glyph:
                for row_idx, row_byte in enumerate(glyph):
                    py = y + row_idx
                    if clip[1] <= py < clip[3]:
                        for col_idx in range(8):
                            if (row_byte >> (7 - col_idx)) & 1:
                                px = cx + col_idx
                                if clip[0] <= px < clip[2]:
                                    off = (py * screen_w + px) * 4
                                    fb[off] = b
                                    fb[off + 1] = g
                                    fb[off + 2] = r
                                    fb[off + 3] = 0xFF
            cx += 8
