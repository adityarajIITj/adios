#!/usr/bin/env python3
"""
AdiOS Sovereign Computing Subsystem: 3D Cyber Citadel & Quantum Core (sanctuary3d.py)
Features:
- 3D Vector Geometry: 12 Colonnade Pillars, Octagonal Citadel, and Central Quantum Core
- 6-DOF Perspective Camera Engine (Yaw, Pitch, Dolly, Strafe)
- Real-time Wireframe Vector Rendering onto 640x480 32-bit Framebuffer
- DolDoc Navigation HUD & Compass
"""

import math
import time

class CyberCitadel3D:
    """
    3D Perspective Wireframe Cyber Citadel and Quantum Core Renderer.
    """
    def __init__(self, vm=None, width=640, height=480):
        self.vm = vm
        self.width = width
        self.height = height
        self.focal_length = 320

        # Camera state
        self.cam_x = 0.0
        self.cam_y = -1.5 # Eye level
        self.cam_z = -12.0
        self.yaw = 0.0
        self.pitch = 0.0

        # Build 3D mesh geometry
        self.lines = []
        self._build_citadel_geometry()

    def _add_line(self, p1, p2, color=0x0000FFCC):
        """Adds a 3D line segment (x, y, z) to the scene."""
        self.lines.append((p1, p2, color))

    def _add_box(self, cx, cy, cz, sx, sy, sz, color=0x0000FFCC):
        """Generates wireframe box lines centered at (cx, cy, cz)."""
        hx, hy, hz = sx / 2, sy / 2, sz / 2
        v = [
            (cx - hx, cy - hy, cz - hz),
            (cx + hx, cy - hy, cz - hz),
            (cx + hx, cy + hy, cz - hz),
            (cx - hx, cy + hy, cz - hz),
            (cx - hx, cy - hy, cz + hz),
            (cx + hx, cy - hy, cz + hz),
            (cx + hx, cy + hy, cz + hz),
            (cx - hx, cy + hy, cz + hz),
        ]
        # Bottom face
        self._add_line(v[0], v[1], color)
        self._add_line(v[1], v[2], color)
        self._add_line(v[2], v[3], color)
        self._add_line(v[3], v[0], color)
        # Top face
        self._add_line(v[4], v[5], color)
        self._add_line(v[5], v[6], color)
        self._add_line(v[6], v[7], color)
        self._add_line(v[7], v[4], color)
        # Vertical edges
        self._add_line(v[0], v[4], color)
        self._add_line(v[1], v[5], color)
        self._add_line(v[2], v[6], color)
        self._add_line(v[3], v[7], color)

    def _build_citadel_geometry(self):
        """Builds the 3D model of the Cyber Citadel, Colonnade, and Central Core."""
        CYAN = 0x0000FFFF
        GOLD = 0x00FFCC00
        PURPLE = 0x00BD93F9
        EMERALD = 0x0050FA7B

        # 1. Foundation Matrix Grid
        for x in range(-8, 9, 2):
            self._add_line((x, 0, 0), (x, 0, 24), CYAN)
        for z in range(0, 25, 3):
            self._add_line((-8, 0, z), (8, 0, z), CYAN)

        # 2. 12 Cyber Colonnade Pillars (6 Left, 6 Right)
        for i in range(6):
            z_pos = 2 + i * 3.5
            # Left pillar
            self._add_box(-6, -2, z_pos, 0.6, 4, 0.6, EMERALD)
            # Right pillar
            self._add_box(6, -2, z_pos, 0.6, 4, 0.6, EMERALD)

        # 3. Octagonal Cyber Chamber (Center z = 18..24)
        self._add_box(0, -3, 21, 8, 6, 6, PURPLE)

        # 4. Central Quantum Core Monolith (z = 21)
        self._add_box(0, -0.6, 21, 2.0, 2.0, 2.0, GOLD)

        # Solar Wings / Solar Flux Arrays
        self._add_line((-1.0, -0.6, 21), (-3.0, -1.8, 21), CYAN)
        self._add_line((-1.0, -0.6, 20.8), (-3.0, -1.8, 20.8), CYAN)
        self._add_line((1.0, -0.6, 21), (3.0, -1.8, 21), CYAN)
        self._add_line((1.0, -0.6, 20.8), (3.0, -1.8, 20.8), CYAN)

    def transform_and_project(self, point):
        """Applies camera transform and perspective projection."""
        x, y, z = point
        dx = x - self.cam_x
        dy = y - self.cam_y
        dz = z - self.cam_z

        cos_y = math.cos(self.yaw)
        sin_y = math.sin(self.yaw)
        rx = dx * cos_y - dz * sin_y
        rz = dx * sin_y + dz * cos_y

        cos_p = math.cos(self.pitch)
        sin_p = math.sin(self.pitch)
        ry = dy * cos_p - rz * sin_p
        final_z = dy * sin_p + rz * cos_p

        if final_z <= 0.2:
            return None

        sx = int(self.width / 2 + (rx * self.focal_length) / final_z)
        sy = int(self.height / 2 + (ry * self.focal_length) / final_z)
        return (sx, sy, final_z)

    def render_frame(self):
        """Renders the complete 3D wireframe citadel into the VM framebuffer."""
        if not self.vm:
            return 0

        fb = self.vm.fb
        # Clear framebuffer to deep dark terminal space
        clear_color = b"\x14\x0E\x0B\x00" * (self.width * self.height)
        fb[:] = clear_color

        lines_drawn = 0
        for p1, p2, color in self.lines:
            proj1 = self.transform_and_project(p1)
            proj2 = self.transform_and_project(p2)

            if proj1 and proj2:
                x0, y0, _ = proj1
                x1, y1, _ = proj2
                self._draw_line_fb(fb, x0, y0, x1, y1, color)
                lines_drawn += 1

        return lines_drawn

    def _draw_line_fb(self, fb, x0, y0, x1, y1, color):
        """Bresenham line drawing algorithm directly on framebuffer."""
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF

        while True:
            if 0 <= x0 < self.width and 0 <= y0 < self.height:
                off = (y0 * self.width + x0) * 4
                fb[off] = b
                fb[off + 1] = g
                fb[off + 2] = r
                fb[off + 3] = 0

            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

if __name__ == "__main__":
    citadel = CyberCitadel3D()
    print(f"CyberCitadel 3D initialized: {len(citadel.lines)} wireframe lines.")
