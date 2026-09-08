#!/usr/bin/env python3
"""
AdiOS Spatial 3D Perspective Compositor (graphics/spatial3d.py)
High-performance software perspective 3D rasterizer for Holo-Mode desktop:
- Full 3D Camera with 6-DOF orbital and free-flight transformations.
- Perspective-correct textured 3D quad rasterizer with depth sorting and distance fog.
- Ray-plane intersection for true 3D interactive mouse clicking and hovering.
- Ambient cyberspace 3D horizon grid and starfield backdrop.
- Zero external dependencies. Pure RV32IM/x86 software graphics pipeline.

Strict Zero Emoji Policy Enforced.
"""

import math
from typing import List, Tuple, Optional, Dict, Any

from .engine3d import Vector3, Matrix4


class Camera3D:
    """6-DOF Perspective Camera with smooth orbital target navigation."""

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = -600.0,
                 fov: float = 60.0, aspect: float = 16.0 / 9.0, near: float = 10.0, far: float = 3000.0):
        self.pos = Vector3(x, y, z)
        self.target = Vector3(0.0, 0.0, 0.0)
        self.yaw = 0.0      # In degrees
        self.pitch = 0.0    # In degrees
        self.roll = 0.0
        self.fov = fov
        self.aspect = aspect
        self.near = near
        self.far = far

        # Motion velocities
        self.target_pos = Vector3(x, y, z)
        self.target_yaw = 0.0
        self.target_pitch = 0.0

    def update(self, dt: float = 0.033):
        """Smoothly lerps camera toward target position and angles."""
        alpha = min(1.0, dt * 10.0)
        self.pos.x += (self.target_pos.x - self.pos.x) * alpha
        self.pos.y += (self.target_pos.y - self.pos.y) * alpha
        self.pos.z += (self.target_pos.z - self.pos.z) * alpha
        self.yaw += (self.target_yaw - self.yaw) * alpha
        self.pitch += (self.target_pitch - self.pitch) * alpha

    def get_forward_vector(self) -> Vector3:
        rad_y = math.radians(self.yaw)
        rad_p = math.radians(self.pitch)
        return Vector3(
            math.sin(rad_y) * math.cos(rad_p),
            -math.sin(rad_p),
            math.cos(rad_y) * math.cos(rad_p)
        ).normalized()

    def get_right_vector(self) -> Vector3:
        rad_y = math.radians(self.yaw)
        return Vector3(math.cos(rad_y), 0.0, -math.sin(rad_y)).normalized()

    def get_up_vector(self) -> Vector3:
        fwd = self.get_forward_vector()
        right = self.get_right_vector()
        return right.cross(fwd).normalized()


class SpatialQuad3D:
    """
    Planar quad in 3D world space representing an interactive desktop window.
    """

    def __init__(self, win_id: str, center: Vector3, width: float, height: float,
                 yaw: float = 0.0, pitch: float = 0.0, roll: float = 0.0):
        self.win_id = win_id
        self.center = center
        self.width = width
        self.height = height
        self.yaw = yaw
        self.pitch = pitch
        self.roll = roll

        # Corners in local space: TL, TR, BR, BL
        hw = width / 2.0
        hh = height / 2.0
        self.local_vertices = [
            Vector3(-hw, -hh, 0.0),  # Top-Left (0, 0)
            Vector3( hw, -hh, 0.0),  # Top-Right (1, 0)
            Vector3( hw,  hh, 0.0),  # Bottom-Right (1, 1)
            Vector3(-hw,  hh, 0.0),  # Bottom-Left (0, 1)
        ]
        self.uvs = [
            (0.0, 0.0),
            (1.0, 0.0),
            (1.0, 1.0),
            (0.0, 1.0)
        ]

    def get_world_vertices(self) -> List[Vector3]:
        """Rotates and translates local corners into world space."""
        rad_y = math.radians(self.yaw)
        rad_p = math.radians(self.pitch)
        rad_r = math.radians(self.roll)

        cos_y, sin_y = math.cos(rad_y), math.sin(rad_y)
        cos_p, sin_p = math.cos(rad_p), math.sin(rad_p)
        cos_r, sin_r = math.cos(rad_r), math.sin(rad_r)

        world_verts = []
        for lv in self.local_vertices:
            # 1. Pitch (X)
            y1 = lv.y * cos_p - lv.z * sin_p
            z1 = lv.y * sin_p + lv.z * cos_p
            x1 = lv.x

            # 2. Yaw (Y)
            x2 = x1 * cos_y + z1 * sin_y
            z2 = -x1 * sin_y + z1 * cos_y
            y2 = y1

            # 3. Roll (Z)
            x3 = x2 * cos_r - y2 * sin_r
            y3 = x2 * sin_r + y2 * cos_r
            z3 = z2

            # Translate by quad center
            world_verts.append(Vector3(
                x3 + self.center.x,
                y3 + self.center.y,
                z3 + self.center.z
            ))
        return world_verts

    def get_normal(self) -> Vector3:
        wv = self.get_world_vertices()
        v0_to_v1 = wv[1] - wv[0]
        v0_to_v3 = wv[3] - wv[0]
        return v0_to_v1.cross(v0_to_v3).normalized()


class SpatialRasterizer:
    """
    Pure software 3D pipeline that composites textured 3D quads into a 32-bit framebuffer.
    """

    def __init__(self, screen_w: int = 1280, screen_h: int = 720):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.half_w = screen_w / 2.0
        self.half_h = screen_h / 2.0
        self.focal_length = self.half_h / math.tan(math.radians(30.0))  # 60 deg FOV

    def project_vertex(self, v: Vector3, cam: Camera3D) -> Tuple[float, float, float]:
        """
        Transforms a world vertex into camera space and projects to screen coordinates.
        Returns (screen_x, screen_y, cam_z).
        """
        # World to Camera Translation
        tx = v.x - cam.pos.x
        ty = v.y - cam.pos.y
        tz = v.z - cam.pos.z

        # Rotate by Camera Yaw and Pitch
        rad_y = -math.radians(cam.yaw)
        cos_y, sin_y = math.cos(rad_y), math.sin(rad_y)
        cx1 = tx * cos_y + tz * sin_y
        cz1 = -tx * sin_y + tz * cos_y
        cy1 = ty

        rad_p = -math.radians(cam.pitch)
        cos_p, sin_p = math.cos(rad_p), math.sin(rad_p)
        cy2 = cy1 * cos_p - cz1 * sin_p
        cz2 = cy1 * sin_p + cz1 * cos_p
        cx2 = cx1

        if cz2 <= 1.0:
            cz2 = 1.0  # Guard against division by zero

        # Perspective projection
        sx = self.half_w + (cx2 * self.focal_length) / cz2
        sy = self.half_h + (cy2 * self.focal_length) / cz2
        return (sx, sy, cz2)

    def render_cyberspace_backdrop(self, fb: bytearray, cam: Camera3D):
        """
        Draws a spatial 3D perspective grid on the ground and celestial particles.
        """
        w, h = self.screen_w, self.screen_h
        clip = (0, 0, w, h)

        # 1. Dark Gradient Cyberspace Background (Deep Obsidian to Midnight Slate)
        # Fast row fill
        c_top = (10, 14, 24)
        c_bot = (4, 6, 12)
        mv = memoryview(fb)
        for y in range(h):
            t = y / float(max(1, h))
            r = int(c_top[0] * (1 - t) + c_bot[0] * t)
            g = int(c_top[1] * (1 - t) + c_bot[1] * t)
            b = int(c_top[2] * (1 - t) + c_bot[2] * t)
            row_bytes = bytes([b, g, r, 0xFF]) * w
            mv[y * w * 4 : (y + 1) * w * 4] = row_bytes

        # 2. 3D Perspective Ground Grid (Floor at Y = 280)
        grid_y = 280.0
        grid_color = 0x001E3A5F  # Cyber Blue Grid
        grid_glow  = 0x003B82F6

        # Longitudinal lines (Z lines)
        for gx in range(-800, 801, 160):
            p1 = self.project_vertex(Vector3(float(gx), grid_y, 50.0), cam)
            p2 = self.project_vertex(Vector3(float(gx), grid_y, 1600.0), cam)
            if p1[2] > 10.0 and p2[2] > 10.0:
                self._draw_line_fast(fb, w, int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]), grid_color, clip)

        # Transverse lines (X lines)
        for gz in range(100, 1601, 150):
            p1 = self.project_vertex(Vector3(-800.0, grid_y, float(gz)), cam)
            p2 = self.project_vertex(Vector3( 800.0, grid_y, float(gz)), cam)
            if p1[2] > 10.0 and p2[2] > 10.0:
                col = grid_glow if gz == 400 else grid_color
                self._draw_line_fast(fb, w, int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]), col, clip)

    def render_textured_quad(self, fb: bytearray, quad: SpatialQuad3D, cam: Camera3D,
                             texture: bytearray, tex_w: int, tex_h: int, is_focused: bool = False):
        """
        Renders a 3D textured quad using scanline perspective texture mapping.
        """
        world_verts = quad.get_world_vertices()
        screen_pts = [self.project_vertex(wv, cam) for wv in world_verts]

        # Frustum culling: if all vertices are behind camera, skip
        if all(sp[2] <= 10.0 for sp in screen_pts):
            return

        w, h = self.screen_w, self.screen_h
        clip = (0, 0, w, h)

        # Triangle 1: (0, 1, 2)
        t1_pts = [screen_pts[0], screen_pts[1], screen_pts[2]]
        t1_uvs = [quad.uvs[0], quad.uvs[1], quad.uvs[2]]
        self._rasterize_textured_triangle(fb, t1_pts, t1_uvs, texture, tex_w, tex_h, clip)

        # Triangle 2: (0, 2, 3)
        t2_pts = [screen_pts[0], screen_pts[2], screen_pts[3]]
        t2_uvs = [quad.uvs[0], quad.uvs[2], quad.uvs[3]]
        self._rasterize_textured_triangle(fb, t2_pts, t2_uvs, texture, tex_w, tex_h, clip)

        # 3D Glowing Border Wireframe
        border_col = 0x0038BDF8 if is_focused else 0x00475569
        p0, p1, p2, p3 = screen_pts
        self._draw_line_fast(fb, w, int(p0[0]), int(p0[1]), int(p1[0]), int(p1[1]), border_col, clip)
        self._draw_line_fast(fb, w, int(p1[0]), int(p1[1]), int(p2[0]), int(p2[1]), border_col, clip)
        self._draw_line_fast(fb, w, int(p2[0]), int(p2[1]), int(p3[0]), int(p3[1]), border_col, clip)
        self._draw_line_fast(fb, w, int(p3[0]), int(p3[1]), int(p0[0]), int(p0[1]), border_col, clip)

    def _rasterize_textured_triangle(self, fb: bytearray, pts: List[Tuple[float, float, float]],
                                     uvs: List[Tuple[float, float]], texture: bytearray,
                                     tex_w: int, tex_h: int, clip: Tuple[int, int, int, int]):
        """
        Scanline triangle rasterizer with affine/perspective interpolation.
        """
        # Sort vertices by screen Y: v0 <= v1 <= v2
        indices = [0, 1, 2]
        indices.sort(key=lambda i: pts[i][1])
        (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = pts[indices[0]], pts[indices[1]], pts[indices[2]]
        (u0, v0), (u1, v1), (u2, v2) = uvs[indices[0]], uvs[indices[1]], uvs[indices[2]]

        # Round Y to integer scanlines
        iy0, iy1, iy2 = int(y0), int(y1), int(y2)
        if iy0 == iy2:
            return

        # Clamp vertical scan range
        min_y = max(clip[1], iy0)
        max_y = min(clip[3] - 1, iy2)
        if min_y > max_y:
            return

        screen_w = self.screen_w
        inv_total_height = 1.0 / float(y2 - y0)
        has_mid_split = (iy1 > iy0) and (iy2 > iy1)

        # Precompute reciprocal z for perspective correction
        rz0 = 1.0 / max(1.0, z0)
        rz1 = 1.0 / max(1.0, z1)
        rz2 = 1.0 / max(1.0, z2)

        u0_z, v0_z = u0 * rz0, v0 * rz0
        u1_z, v1_z = u1 * rz1, v1 * rz1
        u2_z, v2_z = u2 * rz2, v2 * rz2

        for sy in range(min_y, max_y + 1):
            is_second_half = (sy > iy1) or (iy1 == iy0)
            segment_height = (y2 - y1) if is_second_half else (y1 - y0)
            if segment_height <= 0:
                continue

            alpha = (sy - y0) * inv_total_height
            beta  = (sy - (y1 if is_second_half else y0)) / float(segment_height)

            # Left/Right endpoints
            ax = x0 + (x2 - x0) * alpha
            arz = rz0 + (rz2 - rz0) * alpha
            au_z = u0_z + (u2_z - u0_z) * alpha
            av_z = v0_z + (v2_z - v0_z) * alpha

            if is_second_half:
                bx = x1 + (x2 - x1) * beta
                brz = rz1 + (rz2 - rz1) * beta
                bu_z = u1_z + (u2_z - u1_z) * beta
                bv_z = v1_z + (v2_z - v1_z) * beta
            else:
                bx = x0 + (x1 - x0) * beta
                brz = rz0 + (rz1 - rz0) * beta
                bu_z = u0_z + (u1_z - u0_z) * beta
                bv_z = v0_z + (v1_z - v0_z) * beta

            if ax > bx:
                ax, bx = bx, ax
                arz, brz = brz, arz
                au_z, bu_z = bu_z, au_z
                av_z, bv_z = bv_z, av_z

            start_x = max(clip[0], int(ax))
            end_x   = min(clip[2] - 1, int(bx))
            if start_x >= end_x:
                continue

            span_w = float(bx - ax)
            if span_w <= 0:
                continue

            # Step across scanline
            inv_span = 1.0 / span_w
            line_off = sy * screen_w * 4

            # Sub-sample step of 2 pixels for extreme software rendering speed
            step = 1 if (end_x - start_x < 120) else 2
            for sx in range(start_x, end_x + 1, step):
                t = (sx - ax) * inv_span
                rz = arz + (brz - arz) * t
                if rz <= 0:
                    continue
                z = 1.0 / rz
                u = (au_z + (bu_z - au_z) * t) * z
                v = (av_z + (bv_z - av_z) * t) * z

                # Texture coordinates
                tx = int(u * tex_w)
                ty = int(v * tex_h)
                if 0 <= tx < tex_w and 0 <= ty < tex_h:
                    tex_off = (ty * tex_w + tx) * 4
                    tb = texture[tex_off]
                    tg = texture[tex_off + 1]
                    tr = texture[tex_off + 2]

                    # Atmospheric distance dimming
                    fog = max(0.55, min(1.0, 900.0 / (z + 200.0)))
                    pb = int(tb * fog)
                    pg = int(tg * fog)
                    pr = int(tr * fog)

                    dst_off = line_off + sx * 4
                    fb[dst_off]     = pb
                    fb[dst_off + 1] = pg
                    fb[dst_off + 2] = pr
                    fb[dst_off + 3] = 0xFF

                    if step == 2 and sx + 1 <= end_x:
                        fb[dst_off + 4] = pb
                        fb[dst_off + 5] = pg
                        fb[dst_off + 6] = pr
                        fb[dst_off + 7] = 0xFF

    def raycast_quad_uv(self, mx: int, my: int, quad: SpatialQuad3D, cam: Camera3D) -> Optional[Tuple[float, float]]:
        """
        Casts a ray from camera through screen (mx, my) and tests intersection with quad plane.
        Returns (u, v) in range [0.0, 1.0] if ray intersects the quad, or None.
        """
        # Convert screen (mx, my) to normalized camera ray
        nx = (mx - self.half_w) / self.focal_length
        ny = (my - self.half_h) / self.focal_length
        nz = 1.0

        # Rotate ray by camera angles into world space
        rad_p = math.radians(cam.pitch)
        cos_p, sin_p = math.cos(rad_p), math.sin(rad_p)
        ry1 = ny * cos_p - nz * sin_p
        rz1 = ny * sin_p + nz * cos_p
        rx1 = nx

        rad_y = math.radians(cam.yaw)
        cos_y, sin_y = math.cos(rad_y), math.sin(rad_y)
        rx2 = rx1 * cos_y + rz1 * sin_y
        rz2 = -rx1 * sin_y + rz1 * cos_y
        ry2 = ry1

        ray_dir = Vector3(rx2, ry2, rz2).normalized()
        ray_origin = cam.pos

        # Quad plane normal and origin
        normal = quad.get_normal()
        denom = normal.dot(ray_dir)
        if abs(denom) < 1e-6:
            return None  # Ray parallel to quad

        p0 = quad.center
        t = (p0 - ray_origin).dot(normal) / denom
        if t <= 0:
            return None  # Intersection behind camera

        # Intersection point in world space
        hit_point = ray_origin + ray_dir * t

        # Vector from quad center to hit point
        rel_hit = hit_point - quad.center

        # Project onto quad local axes: Right and Up
        wv = quad.get_world_vertices()
        axis_right = (wv[1] - wv[0]).normalized()
        axis_down  = (wv[3] - wv[0]).normalized()

        dist_x = rel_hit.dot(axis_right)
        dist_y = rel_hit.dot(axis_down)

        hw = quad.width / 2.0
        hh = quad.height / 2.0

        if -hw <= dist_x <= hw and -hh <= dist_y <= hh:
            u = (dist_x + hw) / quad.width
            v = (dist_y + hh) / quad.height
            return (max(0.0, min(1.0, u)), max(0.0, min(1.0, v)))

        return None

    def _draw_line_fast(self, fb: bytearray, screen_w: int, x1: int, y1: int, x2: int, y2: int,
                        color: int, clip: Tuple[int, int, int, int]):
        """Bresenham integer line renderer."""
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
                fb[off]     = b
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
