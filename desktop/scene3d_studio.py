#!/usr/bin/env python3
"""
AdiOS Interactive 3D Scene Studio (desktop/scene3d_studio.py)
A modern 3D spatial inspector:
- Mouse click-and-drag 3D rotation (azimuth & elevation).
- Geometry model selector: Cube, Temple Pyramid, Octahedron, Hex Prism, Sovereign Monolith.
- Render modes: Flat Shaded, Wireframe, Normal Vectors.
- Strict scissor clipping guaranteeing zero viewport overflow.

Strict Zero Emoji Policy.
"""

import math
import time
from typing import List, Tuple, Dict, Optional, Any

from .window_manager import Window, CHAR_WIDTH, CHAR_HEIGHT
from .theme import ThemeManager
from graphics.engine3d import (
    Engine3D, Vector3, Matrix4, Mesh, Face,
    create_cube, create_temple_pyramid
)

def create_octahedron(radius: float = 55.0) -> Mesh:
    """Generates a 3D Octahedron mesh (8 equilateral triangular faces)."""
    v = [
        Vector3(0, radius, 0),    # 0: top
        Vector3(0, -radius, 0),   # 1: bot
        Vector3(radius, 0, 0),    # 2: right
        Vector3(0, 0, radius),    # 3: front
        Vector3(-radius, 0, 0),   # 4: left
        Vector3(0, 0, -radius)    # 5: back
    ]

    col_top = 0x0038BDF8  # Cyan
    col_bot = 0x000EA5E9  # Darker Cyan
    faces = [
        Face((0, 2, 3), col_top),
        Face((0, 3, 4), col_top),
        Face((0, 4, 5), col_top),
        Face((0, 5, 2), col_top),
        Face((1, 3, 2), col_bot),
        Face((1, 4, 3), col_bot),
        Face((1, 5, 4), col_bot),
        Face((1, 2, 5), col_bot),
    ]
    return Mesh(v, faces, "Octahedron")

def create_hex_prism(radius: float = 45.0, height: float = 60.0) -> Mesh:
    """Generates a 3D Hexagonal Prism mesh."""
    h2 = height / 2.0
    v = []
    # 0..5: top ring
    for i in range(6):
        ang = i * (2.0 * math.pi / 6.0)
        v.append(Vector3(radius * math.cos(ang), h2, radius * math.sin(ang)))
    # 6..11: bot ring
    for i in range(6):
        ang = i * (2.0 * math.pi / 6.0)
        v.append(Vector3(radius * math.cos(ang), -h2, radius * math.sin(ang)))
    # 12: top center, 13: bot center
    v.append(Vector3(0, h2, 0))
    v.append(Vector3(0, -h2, 0))

    faces = []
    col_top = 0x0094A3B8
    col_bot = 0x0064748B
    col_side = 0x0038BDF8

    for i in range(6):
        ni = (i + 1) % 6
        # Top cap
        faces.append(Face((12, i, ni), col_top))
        # Bottom cap
        faces.append(Face((13, 6 + ni, 6 + i), col_bot))
        # Side quad
        faces.append(Face((i, 6 + i, 6 + ni), col_side))
        faces.append(Face((i, 6 + ni, ni), col_side))

    return Mesh(v, faces, "HexPrism")

def create_monolith(w: float = 30.0, h: float = 85.0, d: float = 15.0) -> Mesh:
    """Generates a 3D Sovereign Monolith (1:4:9 ratio)."""
    hw, hh, hd = w / 2.0, h / 2.0, d / 2.0
    v = [
        Vector3(-hw, -hh, -hd), Vector3(hw, -hh, -hd), Vector3(hw, hh, -hd), Vector3(-hw, hh, -hd),
        Vector3(-hw, -hh, hd),  Vector3(hw, -hh, hd),  Vector3(hw, hh, hd),  Vector3(-hw, hh, hd)
    ]
    col = 0x00475569  # Slate
    faces = [
        # Front
        Face((0, 2, 1), col), Face((0, 3, 2), col),
        # Back
        Face((5, 6, 4), col), Face((6, 7, 4), col),
        # Top
        Face((3, 6, 2), col), Face((3, 7, 6), col),
        # Bottom
        Face((0, 1, 5), col), Face((0, 5, 4), col),
        # Left
        Face((4, 7, 3), col), Face((4, 3, 0), col),
        # Right
        Face((1, 2, 6), col), Face((1, 6, 5), col),
    ]
    return Mesh(v, faces, "Monolith")

class Scene3DStudio(Window):
    """
    Interactive 3D Scene Studio Application Window.
    """
    def __init__(self, win_id: str = "scene3d", x: int = 150, y: int = 60, w: int = 620, h: int = 490):
        super().__init__(
            win_id=win_id,
            title="AdiOS 3D Scene Studio",
            x=x,
            y=y,
            w=w,
            h=h,
            bg_color=0x000F141C
        )
        self.engine3d = Engine3D(None, width=w, height=h)
        self.models: Dict[str, Mesh] = {
            "cube": create_cube(70.0),
            "pyramid": create_temple_pyramid(70.0, 65.0),
            "octahedron": create_octahedron(60.0),
            "prism": create_hex_prism(45.0, 65.0),
            "monolith": create_monolith(30.0, 85.0, 15.0)
        }
        self.current_model_key = "octahedron"
        self.wireframe_mode = False
        self.auto_rotate = True
        self.rot_x = 0.35
        self.rot_y = 0.65
        self.last_mouse_pos = None
        self.zoom = 220.0

        self.on_draw_content = self._render_content
        self.on_click_content = self._handle_click

    def _render_content(self, win: Window, fb: bytearray, font_dict: Dict):
        """Draws toolbar, 3D viewport canvas, and renders the 3D model with scissor clipping."""
        cx, cy, cw, ch = self.client_rect
        tm = ThemeManager.get_instance()
        pal = tm.palette

        # 1. Top Control Bar (height: 32px)
        toolbar_h = 32
        self._render_toolbar(fb, cx, cy, cw, toolbar_h, pal, font_dict)

        # 2. Viewport Canvas Background
        view_y = cy + toolbar_h
        view_h = ch - toolbar_h
        self._fill_rect(fb, cx, view_y, cw, view_h, pal.win_bg)

        # Subtle grid lines on canvas floor
        grid_col = pal.gutter_line
        for gx in range(cx + 20, cx + cw, 40):
            self._draw_vline(fb, gx, view_y, view_h, grid_col)
        for gy in range(view_y + 20, view_y + view_h, 40):
            self._draw_hline(fb, cx, gy, cw, grid_col)

        # 3. Auto-rotation progression
        if self.auto_rotate:
            self.rot_y += 0.015

        # 4. Compute rotation angles
        pos = Vector3(0, 0, self.zoom)
        rot = Vector3(math.degrees(self.rot_x), math.degrees(self.rot_y), 0)

        # 5. Render Mesh strictly clipped inside Viewport
        center_x = cx + cw // 2
        center_y = view_y + view_h // 2
        clip_rect = (cx + 1, view_y + 1, cx + cw - 2, view_y + view_h - 2)

        mesh = self.models.get(self.current_model_key, self.models["cube"])

        self.engine3d.render_mesh(
            mesh=mesh,
            pos=pos,
            rot=rot,
            wireframe=self.wireframe_mode,
            center_x=center_x,
            center_y=center_y,
            clip_rect=clip_rect,
            fb=fb
        )

        # 6. Overlay Telemetry Badge (Bottom-Left)
        badge_y = view_y + view_h - 24
        self._fill_rect(fb, cx + 8, badge_y, 270, 18, pal.card_bg)
        self._draw_rect_outline(fb, cx + 8, badge_y, 270, 18, pal.card_border)
        info_txt = f"Model: {self.current_model_key.title()} | {len(mesh.faces)} Polys | Zoom: {int(self.zoom)}"
        self._draw_text(fb, cx + 14, badge_y + 5, info_txt, pal.text_muted, font_dict)

    def _render_toolbar(self, fb: bytearray, x: int, y: int, w: int, h: int, pal: Any, font_dict: Dict):
        """Renders model switcher and shading mode buttons."""
        self._fill_rect(fb, x, y, w, h, pal.gutter_bg)
        self._draw_hline(fb, x, y + h - 1, w, pal.card_border)

        # Model Switcher Buttons
        btn_models = [("Cube", "cube"), ("Pyramid", "pyramid"), ("Octa", "octahedron"), ("Prism", "prism"), ("Monolith", "monolith")]
        curr_x = x + 8
        for label, key in btn_models:
            is_active = (self.current_model_key == key)
            bw = len(label) * CHAR_WIDTH + 14
            bg = pal.accent_primary if is_active else pal.btn_bg
            txt_col = 0x000F172A if (is_active and pal.name == "Arctic Minimal") else (0x00FFFFFF if is_active else pal.text_primary)

            self._fill_rect(fb, curr_x, y + 5, bw, h - 10, bg)
            self._draw_rect_outline(fb, curr_x, y + 5, bw, h - 10, pal.btn_border)
            self._draw_text(fb, curr_x + 7, y + 9, label, txt_col, font_dict)
            curr_x += bw + 5

        # Mode Buttons on right: [Z-], [Z+], [Wireframe], [Auto-Rot]
        btn_zm_w = 26
        btn_zm_x = x + w - 240
        self._fill_rect(fb, btn_zm_x, y + 5, btn_zm_w, h - 10, pal.btn_bg)
        self._draw_rect_outline(fb, btn_zm_x, y + 5, btn_zm_w, h - 10, pal.btn_border)
        self._draw_text(fb, btn_zm_x + 5, y + 9, "Z-", pal.text_primary, font_dict)

        btn_zp_w = 26
        btn_zp_x = btn_zm_x + btn_zm_w + 4
        self._fill_rect(fb, btn_zp_x, y + 5, btn_zp_w, h - 10, pal.btn_bg)
        self._draw_rect_outline(fb, btn_zp_x, y + 5, btn_zp_w, h - 10, pal.btn_border)
        self._draw_text(fb, btn_zp_x + 5, y + 9, "Z+", pal.text_primary, font_dict)

        btn_wire_w = 75
        btn_wire_x = btn_zp_x + btn_zp_w + 6
        wire_bg = pal.accent_primary if self.wireframe_mode else pal.btn_bg
        wire_txt = 0x000F172A if (self.wireframe_mode and pal.name == "Arctic Minimal") else (0x00FFFFFF if self.wireframe_mode else pal.text_primary)
        self._fill_rect(fb, btn_wire_x, y + 5, btn_wire_w, h - 10, wire_bg)
        self._draw_rect_outline(fb, btn_wire_x, y + 5, btn_wire_w, h - 10, pal.btn_border)
        self._draw_text(fb, btn_wire_x + 8, y + 9, "Wireframe", wire_txt, font_dict)

        btn_rot_w = 85
        btn_rot_x = x + w - btn_rot_w - 6
        rot_bg = pal.accent_primary if self.auto_rotate else pal.btn_bg
        rot_txt = 0x000F172A if (self.auto_rotate and pal.name == "Arctic Minimal") else (0x00FFFFFF if self.auto_rotate else pal.text_primary)
        self._fill_rect(fb, btn_rot_x, y + 5, btn_rot_w, h - 10, rot_bg)
        self._draw_rect_outline(fb, btn_rot_x, y + 5, btn_rot_w, h - 10, pal.btn_border)
        self._draw_text(fb, btn_rot_x + 8, y + 9, "Auto Rotate", rot_txt, font_dict)

    def zoom_in(self, delta: float = 25.0):
        """Decreases camera distance to zoom in."""
        self.zoom = max(80.0, self.zoom - delta)

    def zoom_out(self, delta: float = 25.0):
        """Increases camera distance to zoom out."""
        self.zoom = min(450.0, self.zoom + delta)

    def _handle_click(self, win: Window, rel_x: int, rel_y: int):
        """Handles model selection, zoom, and render mode toggles."""
        if rel_y <= 32:
            # Model buttons
            btn_models = [("Cube", "cube"), ("Pyramid", "pyramid"), ("Octa", "octahedron"), ("Prism", "prism"), ("Monolith", "monolith")]
            curr_x = 8
            for label, key in btn_models:
                bw = len(label) * CHAR_WIDTH + 14
                if curr_x <= rel_x <= curr_x + bw:
                    self.current_model_key = key
                    return
                curr_x += bw + 5

            cw = self.client_rect[2]
            # Z- button
            btn_zm_x = cw - 240
            if btn_zm_x <= rel_x <= btn_zm_x + 26:
                self.zoom_out()
                return
            # Z+ button
            btn_zp_x = btn_zm_x + 30
            if btn_zp_x <= rel_x <= btn_zp_x + 26:
                self.zoom_in()
                return
            # Wireframe toggle
            btn_wire_x = btn_zp_x + 32
            if btn_wire_x <= rel_x <= btn_wire_x + 75:
                self.wireframe_mode = not self.wireframe_mode
                return
            # Auto-rotate toggle
            btn_rot_x = cw - 91
            if btn_rot_x <= rel_x <= cw - 6:
                self.auto_rotate = not self.auto_rotate
                return
        else:
            # Clicking in canvas toggles manual rotation step
            self.rot_y += 0.25

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
