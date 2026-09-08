#!/usr/bin/env python3
"""
AdiOS Holo-Mode 3D Spatial Cyberspace Desktop (desktop/holo_desktop.py)
Transforms the traditional 2D flat desktop into an interactive 3D spatial cyberspace:
- Real-time perspective 3D window compositor.
- Panoramic amphitheater curved layout of live desktop windows.
- 6-DOF orbital camera navigation (pan, tilt, zoom, reset).
- Raycasted 3D mouse picking: click and interact with windows in 3D perspective space.
- Atmospheric cyberspace backdrop with 3D horizon grid and telemetry HUD.
- Zero external dependencies.

Strict Zero Emoji Policy Enforced.
"""

import math
import time
from typing import List, Dict, Tuple, Optional, Any

from graphics.spatial3d import Camera3D, SpatialQuad3D, SpatialRasterizer, Vector3
from graphics.engine2d import draw_rounded_rect, draw_drop_shadow


COLOR_HOLO_CYAN    = 0x0038BDF8
COLOR_HOLO_EMERALD = 0x0034D399
COLOR_HOLO_BG      = 0x000F172A
COLOR_HOLO_TEXT    = 0x00F8FAFC
COLOR_HOLO_MUTED   = 0x0094A3B8
COLOR_HOLO_BORDER  = 0x000284C7


class HoloDesktop:
    """
    Manager for Holo-Mode 3D Spatial Cyberspace Workstation.
    """

    def __init__(self, width: int = 1280, height: int = 720):
        self.width = width
        self.height = height
        self.is_active = False

        # Transition interpolation (0.0 = flat 2D, 1.0 = full 3D)
        self.transition_t = 0.0
        self.transition_speed = 3.5  # Reaches full 3D in ~0.28 seconds

        # 3D Spatial Camera setup
        self.camera = Camera3D(
            x=0.0, y=-20.0, z=-480.0,
            fov=60.0, aspect=float(width) / float(max(1, height))
        )
        self.default_pos = Vector3(0.0, -20.0, -480.0)
        self.default_yaw = 0.0
        self.default_pitch = 0.0

        # Software 3D Rasterizer
        self.rasterizer = SpatialRasterizer(screen_w=width, screen_h=height)

        # Interactive states
        self.hovered_win_id: Optional[str] = None
        self.hovered_uv: Optional[Tuple[float, float]] = None
        self.focused_win_id: Optional[str] = None
        self.is_dragging_camera = False
        self.last_drag_mouse = (0, 0)

        # Window offscreen rendering caches
        self._window_surfaces: Dict[str, Tuple[bytearray, int, int]] = {}
        self._screen_fb = bytearray(width * height * 4)

    def toggle(self, desktop: Any) -> bool:
        """Toggles Holo-Mode 3D Cyberspace on/off."""
        self.is_active = not self.is_active
        if self.is_active:
            self.reset_camera()
            desktop.status_message = "[Holo-Mode] 3D Spatial Cyberspace Engaged (F10 or Esc to Exit)."
            desktop.sound_server.play_ui_sound("launch")
        else:
            desktop.status_message = "[Holo-Mode] Returned to 2D Flat Workstation."
            desktop.sound_server.play_ui_sound("click")
        return self.is_active

    def reset_camera(self):
        """Resets camera view to standard cyberspace vantage point."""
        self.camera.target_pos.x = self.default_pos.x
        self.camera.target_pos.y = self.default_pos.y
        self.camera.target_pos.z = self.default_pos.z
        self.camera.target_yaw = self.default_yaw
        self.camera.target_pitch = self.default_pitch

    def orbit(self, delta_yaw: float, delta_pitch: float):
        """Orbits the spatial camera."""
        self.camera.target_yaw += delta_yaw
        self.camera.target_pitch = max(-45.0, min(45.0, self.camera.target_pitch + delta_pitch))

    def dolly(self, delta_z: float):
        """Dollies the camera forward or backward."""
        self.camera.target_pos.z = max(-900.0, min(-180.0, self.camera.target_pos.z + delta_z))

    def pan(self, delta_x: float, delta_y: float):
        """Pans the camera horizontally or vertically."""
        self.camera.target_pos.x = max(-600.0, min(600.0, self.camera.target_pos.x + delta_x))
        self.camera.target_pos.y = max(-300.0, min(300.0, self.camera.target_pos.y + delta_y))

    def step(self, dt: float = 0.033):
        """Animates transitions and updates camera physics."""
        # Transition progress interpolation
        if self.is_active:
            if self.transition_t < 1.0:
                self.transition_t = min(1.0, self.transition_t + self.transition_speed * dt)
        else:
            if self.transition_t > 0.0:
                self.transition_t = max(0.0, self.transition_t - self.transition_speed * dt)

        # Update smooth camera lerping
        self.camera.update(dt)

    def _build_spatial_quads(self, desktop: Any) -> List[Tuple[SpatialQuad3D, Any]]:
        """
        Generates 3D spatial quads for all visible windows in an amphitheater arrangement.
        """
        visible_windows = [w for w in desktop.wm.windows if w.visible and not w.minimized]
        quad_pairs = []

        count = len(visible_windows)
        if count == 0:
            return quad_pairs

        # Semi-circular curved layout parameters
        radius = 520.0
        total_arc = min(110.0, max(40.0, count * 24.0))  # Degrees
        step_arc = total_arc / float(max(1, count - 1)) if count > 1 else 0.0
        start_angle = -total_arc / 2.0

        for idx, win in enumerate(visible_windows):
            angle_deg = start_angle + idx * step_arc if count > 1 else 0.0
            angle_rad = math.radians(angle_deg)

            # Amphitheater arc positioning: X = R*sin(theta), Z = R*cos(theta) - (R - 200)
            qx = radius * math.sin(angle_rad)
            qz = radius * math.cos(angle_rad) - (radius - 220.0)
            qy = -20.0 + (idx % 2) * 15.0  # Subtle staggered height

            # Window quad faces inward toward the camera
            q_yaw = -angle_deg * 0.85
            q_pitch = 0.0

            # Scale window dimensions to 3D world units
            qw = win.w * 0.58
            qh = win.h * 0.58

            quad = SpatialQuad3D(
                win_id=win.win_id,
                center=Vector3(qx, qy, qz),
                width=qw,
                height=qh,
                yaw=q_yaw,
                pitch=q_pitch
            )
            quad_pairs.append((quad, win))

        return quad_pairs

    def _render_window_to_texture(self, win: Any, desktop: Any) -> Tuple[bytearray, int, int]:
        """
        Extracts a window's rendered pixels from the 2D workspace into a texture buffer.
        """
        tw, th = max(1, win.w), max(1, win.h)
        buf_size = tw * th * 4

        # Reuse or create texture buffer
        if win.win_id not in self._window_surfaces or len(self._window_surfaces[win.win_id][0]) != buf_size:
            self._window_surfaces[win.win_id] = (bytearray(buf_size), tw, th)

        tex_buf, _, _ = self._window_surfaces[win.win_id]

        # Extract window pixel sub-rect from rendered 2D screen surface
        sw = self.width
        sh = self.height
        sfb = self._screen_fb
        mv_dst = memoryview(tex_buf)
        mv_src = memoryview(sfb)

        for ry in range(th):
            sy = win.y + ry
            if 0 <= sy < sh:
                sx = max(0, min(sw - 1, win.x))
                row_w = max(0, min(tw, sw - sx))
                src_off = (sy * sw + sx) * 4
                dst_off = ry * tw * 4
                mv_dst[dst_off : dst_off + row_w * 4] = mv_src[src_off : src_off + row_w * 4]

        return (tex_buf, tw, th)

    def render(self, fb: bytearray, desktop: Any):
        """
        Renders the full 3D spatial cyberspace scene into the primary desktop framebuffer.
        """
        if self.transition_t <= 0.0:
            return

        # 0. Render 2D workspace to offscreen surface so live windows are refreshed
        desktop.render_2d_workspace(self._screen_fb)

        # 1. Render 3D Cyberspace Gradient Backdrop and Horizon Grid
        self.rasterizer.render_cyberspace_backdrop(fb, self.camera)

        # 2. Build 3D spatial quads for all open windows
        quad_pairs = self._build_spatial_quads(desktop)

        # 3. Depth-sort quads from back to front (Painter's Algorithm)
        def get_distance_to_cam(pair):
            quad, _ = pair
            diff = quad.center - self.camera.pos
            return diff.length()

        quad_pairs.sort(key=get_distance_to_cam, reverse=True)

        # 4. Rasterize each window quad onto the 3D framebuffer
        for quad, win in quad_pairs:
            texture, tw, th = self._render_window_to_texture(win, desktop)
            is_hovered = (quad.win_id == self.hovered_win_id)
            self.rasterizer.render_textured_quad(
                fb, quad, self.camera, texture, tw, th, is_focused=is_hovered
            )

        # 5. Render Top Spatial HUD Overlay
        self._render_holo_hud(fb, desktop)

    def _render_holo_hud(self, fb: bytearray, desktop: Any):
        """
        Draws the floating spatial cyberspace telemetry and navigation bar.
        """
        w, h = self.width, self.height
        hud_w = min(1040, w - 80)
        hud_h = 32
        hud_x = (w - hud_w) // 2
        hud_y = 30

        # Draw HUD Dark Slate Background with Alpha = 0xFF
        bg_col = COLOR_HOLO_BG
        b, g, r = bg_col & 0xFF, (bg_col >> 8) & 0xFF, (bg_col >> 16) & 0xFF
        bg_row = bytes([b, g, r, 0xFF]) * hud_w

        border_col = COLOR_HOLO_CYAN
        bb, bg_, br = border_col & 0xFF, (border_col >> 8) & 0xFF, (border_col >> 16) & 0xFF
        bord_row = bytes([bb, bg_, br, 0xFF]) * hud_w

        mv = memoryview(fb)
        for row in range(hud_y, hud_y + hud_h):
            off = (row * w + hud_x) * 4
            if row == hud_y or row == hud_y + hud_h - 1:
                mv[off : off + hud_w * 4] = bord_row
            else:
                mv[off : off + hud_w * 4] = bg_row
                mv[off : off + 4] = bytes([bb, bg_, br, 0xFF])
                mv[off + (hud_w - 1) * 4 : off + hud_w * 4] = bytes([bb, bg_, br, 0xFF])

        # Brand / Mode Tag
        desktop._draw_string(fb, hud_x + 14, hud_y + 11, "ADIOS HOLO-MODE : 3D SPATIAL CYBERSPACE", COLOR_HOLO_CYAN)

        # Telemetry
        cam_info = f"CAM: ({int(self.camera.pos.x)},{int(self.camera.pos.y)},{int(self.camera.pos.z)}) | YAW: {int(self.camera.yaw)} deg"
        desktop._draw_string(fb, hud_x + 365, hud_y + 11, cam_info, COLOR_HOLO_EMERALD)

        # Navigation Controls
        nav_hints = "[F10/Esc] Exit | [R] Reset | [Drag] Orbit | [W/S] Zoom"
        desktop._draw_string(fb, hud_x + hud_w - 380, hud_y + 11, nav_hints, COLOR_HOLO_MUTED)

        # Target Window indicator if hovered
        if self.hovered_win_id:
            hover_pill = f"Target: [{self.hovered_win_id.upper()}] (Click to Focus)"
            desktop._draw_string(fb, hud_x + 14, hud_y + 20, hover_pill, COLOR_HOLO_EMERALD)

    def handle_mouse_move(self, mx: int, my: int, desktop: Any):
        """
        Raycasts through spatial quads to identify hovered window and coordinates.
        """
        if not self.is_active:
            return

        # If user is actively dragging the camera with right-click or alt
        if self.is_dragging_camera:
            dx = mx - self.last_drag_mouse[0]
            dy = my - self.last_drag_mouse[1]
            self.orbit(dx * 0.35, -dy * 0.35)
            self.last_drag_mouse = (mx, my)
            return

        # Test ray-plane intersection against each quad
        quad_pairs = self._build_spatial_quads(desktop)
        self.hovered_win_id = None
        self.hovered_uv = None

        for quad, win in quad_pairs:
            uv = self.rasterizer.raycast_quad_uv(mx, my, quad, self.camera)
            if uv is not None:
                self.hovered_win_id = quad.win_id
                self.hovered_uv = uv
                break

    def handle_mouse_down(self, mx: int, my: int, button: int, desktop: Any) -> Optional[Tuple[str, Any]]:
        """
        Handles mouse clicks in 3D spatial cyberspace.
        Right-click (button 3): Begins orbital camera drag.
        Left-click (button 1): Focuses window or interacts with it.
        """
        if not self.is_active:
            return None

        # Right click or Middle click: camera orbit drag
        if button in (2, 3):
            self.is_dragging_camera = True
            self.last_drag_mouse = (mx, my)
            return ("holo_drag_start", None)

        # Left click: test if clicking a 3D window
        if button == 1:
            quad_pairs = self._build_spatial_quads(desktop)
            for quad, win in quad_pairs:
                uv = self.rasterizer.raycast_quad_uv(mx, my, quad, self.camera)
                if uv is not None:
                    u, v = uv
                    # Unproject into local window coordinates
                    wx = int(u * win.w)
                    wy = int(v * win.h)

                    # Focus window in window manager
                    desktop.wm.focus_window(win)
                    desktop.sound_server.play_ui_sound("click")
                    desktop.status_message = f"Focused 3D Window '{win.title}' in Cyberspace."

                    # Forward click event into window's internal handler
                    if hasattr(win, "handle_mouse_down"):
                        win.handle_mouse_down(wx, wy)

                    return ("holo_window_click", (win.win_id, wx, wy))

        return None

    def handle_mouse_up(self, mx: int, my: int, button: int):
        """Releases camera dragging."""
        if button in (2, 3):
            self.is_dragging_camera = False

    def handle_key(self, key: str, desktop: Any) -> bool:
        """
        Handles keyboard navigation in Holo-Mode.
        """
        if not self.is_active:
            return False

        if key in ("F10", "ESCAPE", "ESC"):
            self.toggle(desktop)
            return True
        elif key in ("r", "R"):
            self.reset_camera()
            desktop.sound_server.play_ui_sound("click")
            return True
        elif key in ("w", "W"):
            self.dolly(40.0)
            return True
        elif key in ("s", "S"):
            self.dolly(-40.0)
            return True
        elif key in ("a", "A", "KEY_LEFT"):
            self.orbit(-4.0, 0.0)
            return True
        elif key in ("d", "D", "KEY_RIGHT"):
            self.orbit(4.0, 0.0)
            return True
        elif key in ("KEY_UP",):
            self.orbit(0.0, 3.0)
            return True
        elif key in ("KEY_DOWN",):
            self.orbit(0.0, -3.0)
            return True

        return False
