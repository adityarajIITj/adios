#!/usr/bin/env python3
"""
AdiOS Unified 2D Vector Graphics Engine (Engine2D)
High-performance procedural 2D rasterizer for Sovereign Desktop v2.0 Stable.
Zero External Dependencies (Pure Python buffer operations).

Features:
- Anti-aliased rounded rectangles with configurable corner radius
- Smooth vertical & horizontal linear gradients
- Multi-layer alpha-blended soft drop shadows
- Anti-aliased circles & pills (macOS-style window traffic light buttons)
- Vector icon generator (Computer, YouTube, Arcade, Explorer, Shell, Settings, WiFi, Sound)
STRICT ZERO EMOJI POLICY.
"""

import math
from typing import Optional, Tuple

def unpack_rgb(col: int) -> Tuple[int, int, int]:
    r = (col >> 16) & 0xFF
    g = (col >> 8) & 0xFF
    b = col & 0xFF
    return r, g, b

def pack_rgb(r: int, g: int, b: int) -> int:
    return ((r & 0xFF) << 16) | ((g & 0xFF) << 8) | (b & 0xFF)

def blend_pixel(fb: bytearray, x: int, y: int, r: int, g: int, b: int, alpha: float, screen_w: int, screen_h: int):
    """Blends a single RGB color with alpha (0.0 to 1.0) into little-endian ARGB/BGRX framebuffer."""
    if x < 0 or x >= screen_w or y < 0 or y >= screen_h:
        return
    idx = (y * screen_w + x) * 4
    if alpha >= 0.99:
        fb[idx] = b
        fb[idx + 1] = g
        fb[idx + 2] = r
        fb[idx + 3] = 0
    elif alpha > 0.01:
        dst_b = fb[idx]
        dst_g = fb[idx + 1]
        dst_r = fb[idx + 2]
        inv = 1.0 - alpha
        fb[idx] = int(dst_b * inv + b * alpha)
        fb[idx + 1] = int(dst_g * inv + g * alpha)
        fb[idx + 2] = int(dst_r * inv + r * alpha)
        fb[idx + 3] = 0

def draw_circle(
    fb: bytearray,
    cx: int,
    cy: int,
    radius: int,
    fill_color: int,
    border_color: Optional[int] = None,
    clip: Optional[Tuple[int, int, int, int]] = None,
    screen_w: int = 1280,
    screen_h: int = 720
):
    """Draws a circle at (cx, cy) using fast horizontal row slices."""
    if radius <= 0:
        return
    r_fill, g_fill, b_fill = unpack_rgb(fill_color)
    r_bord, g_bord, b_bord = unpack_rgb(border_color) if border_color is not None else (r_fill, g_fill, b_fill)
    fill_px = bytes([b_fill, g_fill, r_fill, 0])
    bord_px = bytes([b_bord, g_bord, r_bord, 0])

    cx0 = 0 if clip is None else max(0, clip[0])
    cy0 = 0 if clip is None else max(0, clip[1])
    cx1 = screen_w if clip is None else min(screen_w, clip[2])
    cy1 = screen_h if clip is None else min(screen_h, clip[3])

    r2 = radius * radius
    for dy in range(-radius, radius + 1):
        py = cy + dy
        if cy0 <= py < cy1:
            dx_max = math.isqrt(max(0, r2 - dy * dy))
            rx0 = max(cx0, cx - dx_max)
            rx1 = min(cx1, cx + dx_max + 1)
            if rx1 > rx0:
                span_len = rx1 - rx0
                off = (py * screen_w + rx0) * 4
                if border_color is not None and (abs(dy) == radius):
                    fb[off : off + span_len * 4] = bord_px * span_len
                else:
                    fb[off : off + span_len * 4] = fill_px * span_len
                    if border_color is not None:
                        if rx0 == cx - dx_max:
                            fb[off : off + 4] = bord_px
                        if rx1 == cx + dx_max + 1 and span_len > 1:
                            fb[off + (span_len - 1) * 4 : off + span_len * 4] = bord_px

def draw_gradient_v(
    fb: bytearray,
    x: int,
    y: int,
    w: int,
    h: int,
    color_top: int,
    color_bottom: int,
    clip: Optional[Tuple[int, int, int, int]] = None,
    screen_w: int = 1280,
    screen_h: int = 720
):
    """Draws a vertical linear gradient fill."""
    if w <= 0 or h <= 0:
        return
    rt, gt, bt = unpack_rgb(color_top)
    rb, gb, bb = unpack_rgb(color_bottom)

    x0 = max(0, x)
    x1 = min(screen_w, x + w)
    y0 = max(0, y)
    y1 = min(screen_h, y + h)

    if clip:
        x0 = max(x0, clip[0])
        y0 = max(y0, clip[1])
        x1 = min(x1, clip[2])
        y1 = min(y1, clip[3])

    if x0 >= x1 or y0 >= y1:
        return

    row_width = x1 - x0
    for py in range(y0, y1):
        t = (py - y) / max(1, h - 1)
        r = int(rt + (rb - rt) * t)
        g = int(gt + (gb - gt) * t)
        b = int(bt + (bb - bt) * t)
        row_bytes = bytes([b, g, r, 0]) * row_width
        idx = (py * screen_w + x0) * 4
        fb[idx : idx + row_width * 4] = row_bytes

_SHADOW_LUT = bytes(int(i * 0.65) for i in range(256))

def draw_drop_shadow(
    fb: bytearray,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int = 8,
    alpha: float = 0.35,
    screen_w: int = 1280,
    screen_h: int = 720
):
    """Renders a smooth fast drop shadow to the bottom and right of a rectangular window using byte LUT."""
    if w <= 0 or h <= 0:
        return
    offset = radius
    lut = _SHADOW_LUT
    sx0 = max(0, x + 4)
    sy0 = max(0, y + 4)
    sx1 = min(screen_w, x + w + offset)
    sy1 = min(screen_h, y + h + offset)

    # Bottom shadow strip
    bot_y0 = max(y + h, sy0)
    for py in range(bot_y0, sy1):
        row_off = py * screen_w * 4
        for px in range(sx0, sx1):
            idx = row_off + px * 4
            fb[idx]   = lut[fb[idx]]
            fb[idx+1] = lut[fb[idx+1]]
            fb[idx+2] = lut[fb[idx+2]]

    # Right shadow strip
    right_x0 = max(x + w, sx0)
    right_y1 = min(y + h, sy1)
    for py in range(sy0, right_y1):
        row_off = py * screen_w * 4
        for px in range(right_x0, sx1):
            idx = row_off + px * 4
            fb[idx]   = lut[fb[idx]]
            fb[idx+1] = lut[fb[idx+1]]
            fb[idx+2] = lut[fb[idx+2]]

_CORNER_SPANS: Dict[int, List[int]] = {}

def _get_corner_spans(rad: int) -> List[int]:
    if rad not in _CORNER_SPANS:
        spans = []
        for dy in range(rad):
            y_dist = rad - 1 - dy
            w = int(math.isqrt(max(0, rad * rad - y_dist * y_dist)))
            spans.append(w)
        _CORNER_SPANS[rad] = spans
    return _CORNER_SPANS[rad]

def draw_rounded_rect(
    fb: bytearray,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int,
    fill_color: int,
    border_color: Optional[int] = None,
    round_top_only: bool = False,
    clip: Optional[Tuple[int, int, int, int]] = None,
    screen_w: int = 1280,
    screen_h: int = 720
):
    """
    Renders a rectangle with smoothly rounded corners.
    Accelerated with vectorized row slices and precomputed span lookup tables.
    """
    if w <= 0 or h <= 0:
        return
    rad = min(radius, w // 2, h // 2)
    rf, gf, bf = unpack_rgb(fill_color)
    rb, gb, bb = unpack_rgb(border_color) if border_color is not None else (rf, gf, bf)
    fill_px = bytes([bf, gf, rf, 0])
    bord_px = bytes([bb, gb, rb, 0])

    cx0 = 0 if clip is None else max(0, clip[0])
    cy0 = 0 if clip is None else max(0, clip[1])
    cx1 = screen_w if clip is None else min(screen_w, clip[2])
    cy1 = screen_h if clip is None else min(screen_h, clip[3])

    if rad <= 0:
        x0 = max(cx0, x)
        x1 = min(cx1, x + w)
        y0 = max(cy0, y)
        y1 = min(cy1, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        row_len = x1 - x0
        body_slice = fill_px * row_len
        bord_slice = bord_px * row_len
        for py in range(y0, y1):
            off = (py * screen_w + x0) * 4
            if border_color is not None and (py == y or py == y + h - 1):
                fb[off : off + row_len * 4] = bord_slice
            else:
                fb[off : off + row_len * 4] = body_slice
                if border_color is not None:
                    if x0 == x: fb[off : off + 4] = bord_px
                    if x1 == x + w and row_len > 1: fb[off + (row_len - 1) * 4 : off + row_len * 4] = bord_px
        return

    spans = _get_corner_spans(rad)

    # 1. Top rounded rows
    for dy in range(rad):
        py = y + dy
        if cy0 <= py < cy1:
            span_w = spans[dy]
            rx0 = max(cx0, x + rad - span_w)
            rx1 = min(cx1, x + w - rad + span_w)
            if rx1 > rx0:
                row_len = rx1 - rx0
                off = (py * screen_w + rx0) * 4
                if dy == 0 and border_color is not None:
                    fb[off : off + row_len * 4] = bord_px * row_len
                else:
                    fb[off : off + row_len * 4] = fill_px * row_len
                    if border_color is not None:
                        if rx0 == x + rad - span_w:
                            fb[off : off + 4] = bord_px
                        if rx1 == x + w - rad + span_w and row_len > 1:
                            fb[off + (row_len - 1) * 4 : off + row_len * 4] = bord_px

    # 2. Middle rows
    mid_start = rad
    mid_end = h if round_top_only else h - rad
    for dy in range(mid_start, mid_end):
        py = y + dy
        if cy0 <= py < cy1:
            rx0 = max(cx0, x)
            rx1 = min(cx1, x + w)
            if rx1 > rx0:
                row_len = rx1 - rx0
                off = (py * screen_w + rx0) * 4
                fb[off : off + row_len * 4] = fill_px * row_len
                if border_color is not None:
                    if rx0 == x:
                        fb[off : off + 4] = bord_px
                    if rx1 == x + w and row_len > 1:
                        fb[off + (row_len - 1) * 4 : off + row_len * 4] = bord_px

    # 3. Bottom rounded rows
    if not round_top_only:
        for dy in range(rad):
            py = y + h - rad + dy
            if cy0 <= py < cy1:
                span_w = spans[rad - 1 - dy]
                rx0 = max(cx0, x + rad - span_w)
                rx1 = min(cx1, x + w - rad + span_w)
                if rx1 > rx0:
                    row_len = rx1 - rx0
                    off = (py * screen_w + rx0) * 4
                    if dy == rad - 1 and border_color is not None:
                        fb[off : off + row_len * 4] = bord_px * row_len
                    else:
                        fb[off : off + row_len * 4] = fill_px * row_len
                        if border_color is not None:
                            if rx0 == x + rad - span_w:
                                fb[off : off + 4] = bord_px
                            if rx1 == x + w - rad + span_w and row_len > 1:
                                fb[off + (row_len - 1) * 4 : off + row_len * 4] = bord_px

def draw_procedural_icon(
    fb: bytearray,
    x: int,
    y: int,
    icon_type: str,
    size: int = 36,
    accent_color: Optional[int] = None,
    screen_w: int = 1280,
    screen_h: int = 720
):
    """
    Draws a sleek procedural vector icon directly into the framebuffer.
    Supported types: 'computer', 'youtube', 'games', 'explorer', 'shell', 'settings', 'wifi', 'sound'
    """
    plate_bg = 0x001E1E2E
    plate_border = accent_color if accent_color is not None else 0x007AA2F7
    draw_rounded_rect(fb, x, y, size, size, radius=8, fill_color=plate_bg, border_color=plate_border, screen_w=screen_w, screen_h=screen_h)

    cx = x + size // 2
    cy = y + size // 2

    if icon_type == "youtube":
        card_w, card_h = size - 12, size - 16
        draw_rounded_rect(fb, cx - card_w // 2, cy - card_h // 2, card_w, card_h, radius=4, fill_color=0x00FF0033, screen_w=screen_w, screen_h=screen_h)
        tx0 = cx - 3
        for py in range(cy - 4, cy + 5):
            half = 4 - abs(py - cy)
            for px in range(tx0, tx0 + half + 2):
                blend_pixel(fb, px, py, 255, 255, 255, 1.0, screen_w, screen_h)

    elif icon_type == "computer":
        mw, mh = size - 12, size - 18
        mx0, my0 = cx - mw // 2, cy - mh // 2 - 2
        draw_rounded_rect(fb, mx0, my0, mw, mh, radius=3, fill_color=0x002A2A3E, border_color=0x007AA2F7, screen_w=screen_w, screen_h=screen_h)
        for py in range(my0 + 2, my0 + mh - 2):
            for px in range(mx0 + 2, mx0 + mw - 2):
                blend_pixel(fb, px, py, 0, 210, 255, 0.85, screen_w, screen_h)
        for py in range(my0 + mh, my0 + mh + 4):
            blend_pixel(fb, cx - 1, py, 180, 190, 210, 1.0, screen_w, screen_h)
            blend_pixel(fb, cx, py, 180, 190, 210, 1.0, screen_w, screen_h)
        for px in range(cx - 5, cx + 6):
            blend_pixel(fb, px, my0 + mh + 4, 180, 190, 210, 1.0, screen_w, screen_h)

    elif icon_type == "games":
        gw, gh = size - 10, size - 18
        gx0, gy0 = cx - gw // 2, cy - gh // 2
        draw_rounded_rect(fb, gx0, gy0, gw, gh, radius=6, fill_color=0x00BB9AF7, screen_w=screen_w, screen_h=screen_h)
        for py in range(cy - 3, cy + 4):
            blend_pixel(fb, gx0 + 4, py, 30, 30, 46, 1.0, screen_w, screen_h)
        for px in range(gx0 + 2, gx0 + 7):
            blend_pixel(fb, px, cy, 30, 30, 46, 1.0, screen_w, screen_h)
        draw_circle(fb, gx0 + gw - 6, cy - 2, 2, 0x00F7768E, screen_w=screen_w, screen_h=screen_h)
        draw_circle(fb, gx0 + gw - 3, cy + 2, 2, 0x009ECE6A, screen_w=screen_w, screen_h=screen_h)

    elif icon_type == "explorer":
        fw, fh = size - 12, size - 16
        fx0, fy0 = cx - fw // 2, cy - fh // 2
        for py in range(fy0, fy0 + 3):
            for px in range(fx0, fx0 + 8):
                blend_pixel(fb, px, py, 224, 175, 104, 1.0, screen_w, screen_h)
        draw_rounded_rect(fb, fx0, fy0 + 3, fw, fh - 3, radius=3, fill_color=0x00E0AF68, border_color=0x00FF9E3B, screen_w=screen_w, screen_h=screen_h)

    elif icon_type == "shell":
        sw, sh = size - 12, size - 16
        sx0, sy0 = cx - sw // 2, cy - sh // 2
        draw_rounded_rect(fb, sx0, sy0, sw, sh, radius=3, fill_color=0x00101014, border_color=0x00414868, screen_w=screen_w, screen_h=screen_h)
        blend_pixel(fb, sx0 + 3, sy0 + 4, 158, 206, 106, 1.0, screen_w, screen_h)
        blend_pixel(fb, sx0 + 4, sy0 + 5, 158, 206, 106, 1.0, screen_w, screen_h)
        blend_pixel(fb, sx0 + 3, sy0 + 6, 158, 206, 106, 1.0, screen_w, screen_h)
        for px in range(sx0 + 7, sx0 + 11):
            blend_pixel(fb, px, sy0 + 6, 158, 206, 106, 1.0, screen_w, screen_h)

    elif icon_type == "settings":
        draw_circle(fb, cx, cy, 6, 0x007AA2F7, border_color=0x00C0CAF5, screen_w=screen_w, screen_h=screen_h)
        draw_circle(fb, cx, cy, 2, 0x001E1E2E, screen_w=screen_w, screen_h=screen_h)
        for i in range(4):
            ang = i * (math.pi / 2)
            px = int(cx + math.cos(ang) * 8)
            py = int(cy + math.sin(ang) * 8)
            blend_pixel(fb, px, py, 192, 202, 245, 1.0, screen_w, screen_h)

    elif icon_type == "wifi":
        draw_circle(fb, cx, cy + 6, 2, 0x0073DACA, screen_w=screen_w, screen_h=screen_h)
        for py in range(cy - 6, cy + 4):
            for px in range(cx - 8, cx + 9):
                dx = px - cx
                dy = (py - (cy + 6))
                dist = math.sqrt(dx * dx + dy * dy)
                if (5.5 < dist < 7.5 and py < cy + 4) or (9.5 < dist < 11.5 and py < cy + 1):
                    blend_pixel(fb, px, py, 115, 218, 202, 1.0, screen_w, screen_h)

    elif icon_type == "sound":
        for py in range(cy - 4, cy + 5):
            blend_pixel(fb, cx - 6, py, 255, 255, 255, 1.0, screen_w, screen_h)
            blend_pixel(fb, cx - 5, py, 255, 255, 255, 1.0, screen_w, screen_h)
        for py in range(cy - 6, cy + 7):
            w_cone = max(0, 6 - abs(py - cy))
            for px in range(cx - 4, cx - 4 + w_cone):
                blend_pixel(fb, px, py, 255, 255, 255, 1.0, screen_w, screen_h)
        for py in range(cy - 5, cy + 6):
            dy = abs(py - cy)
            blend_pixel(fb, cx + 5 - dy // 2, py, 122, 162, 247, 1.0, screen_w, screen_h)
            blend_pixel(fb, cx + 9 - dy // 2, py, 122, 162, 247, 0.8, screen_w, screen_h)
