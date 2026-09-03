#!/usr/bin/env python3
"""
AdiOS 3D Software Rasterizer & Mesh Engine
Inspired by Terry A. Davis's 3D graphics pipeline in TempleOS.
Features:
- Full Vector3 & Matrix4x4 mathematics
- Flat-shaded polygon rendering with directional diffuse lighting
- Backface culling (camera normal test)
- Painter's Algorithm depth sorting (Z-ordering)
- Integer scanline triangle rasterization directly into 640x480 Framebuffer
- Built-in 3D models: Cube, Temple Pyramid, Starfighter
"""

import math
import struct

WIDTH  = 640
HEIGHT = 480
HALFW  = WIDTH // 2
HALFH  = HEIGHT // 2
FOCAL  = 320.0

class Vector3:
    __slots__ = ("x", "y", "z")
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def __add__(self, o): return Vector3(self.x + o.x, self.y + o.y, self.z + o.z)
    def __sub__(self, o): return Vector3(self.x - o.x, self.y - o.y, self.z - o.z)
    def __mul__(self, s): return Vector3(self.x * s, self.y * s, self.z * s)
    def dot(self, o): return self.x * o.x + self.y * o.y + self.z * o.z

    def cross(self, o):
        return Vector3(
            self.y * o.z - self.z * o.y,
            self.z * o.x - self.x * o.z,
            self.x * o.y - self.y * o.x
        )

    def length(self):
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def normalized(self):
        l = self.length()
        if l < 1e-6: return Vector3(0, 0, 1)
        return Vector3(self.x / l, self.y / l, self.z / l)

class Face:
    def __init__(self, v_indices, base_color=0x007AA2F7):
        self.v_indices = v_indices # (idx0, idx1, idx2)
        self.base_color = base_color

class Mesh:
    def __init__(self, vertices, faces, name="Mesh"):
        self.vertices = vertices # list of Vector3
        self.faces = faces       # list of Face
        self.name = name

# ------------------------------------------------------------------------------
# Built-in 3D Meshes
# ------------------------------------------------------------------------------

def create_cube(size=80.0):
    s = size / 2.0
    v = [
        Vector3(-s, -s, -s), Vector3(s, -s, -s), Vector3(s, s, -s), Vector3(-s, s, -s),
        Vector3(-s, -s,  s), Vector3(s, -s,  s), Vector3(s, s,  s), Vector3(-s, s,  s)
    ]
    # 12 triangles (2 per cube face)
    f = [
        Face((0, 1, 2), 0x00F7768E), Face((0, 2, 3), 0x00F7768E), # Front (Red)
        Face((5, 4, 7), 0x007AA2F7), Face((5, 7, 6), 0x007AA2F7), # Back (Blue)
        Face((4, 0, 3), 0x009ECE6A), Face((4, 3, 7), 0x009ECE6A), # Left (Green)
        Face((1, 5, 6), 0x00E0AF68), Face((1, 6, 2), 0x00E0AF68), # Right (Yellow)
        Face((3, 2, 6), 0x00BB9AF7), Face((3, 6, 7), 0x00BB9AF7), # Top (Purple)
        Face((4, 5, 1), 0x007DCFFF), Face((4, 1, 0), 0x007DCFFF), # Bottom (Cyan)
    ]
    return Mesh(v, f, "Cube")

def create_temple_pyramid(base=100.0, height=90.0):
    b = base / 2.0
    h = height / 2.0
    v = [
        Vector3(-b, -h, -b), Vector3(b, -h, -b), Vector3(b, -h, b), Vector3(-b, -h, b),
        Vector3(0, h, 0) # Apex
    ]
    f = [
        Face((0, 1, 4), 0x00E0AF68), # Front
        Face((1, 2, 4), 0x00BB9AF7), # Right
        Face((2, 3, 4), 0x007AA2F7), # Back
        Face((3, 0, 4), 0x009ECE6A), # Left
        Face((0, 2, 1), 0x00F7768E), Face((0, 3, 2), 0x00F7768E)  # Base
    ]
    return Mesh(v, f, "Temple_Pyramid")

# ------------------------------------------------------------------------------
# 3D Pipeline & Scanline Rasterizer
# ------------------------------------------------------------------------------

class Engine3D:
    def __init__(self, vm=None):
        self.vm = vm
        self.light_dir = Vector3(0.577, 0.577, -0.577).normalized()

    def project_vertex(self, v):
        if v.z <= 5.0: return None
        sx = int(HALFW + (v.x * FOCAL) / v.z)
        sy = int(HALFH - (v.y * FOCAL) / v.z)
        return (sx, sy, v.z)

    def shade_color(self, base_color, normal):
        # Diffuse directional light
        dot = normal.dot(self.light_dir)
        factor = max(0.25, min(1.0, 0.35 + 0.65 * max(0.0, dot)))

        r = int(((base_color >> 16) & 0xFF) * factor)
        g = int(((base_color >> 8) & 0xFF) * factor)
        b = int((base_color & 0xFF) * factor)
        return (r << 16) | (g << 8) | b

    def render_mesh(self, mesh, pos, rot, wireframe=False):
        """Renders 3D mesh with Euler rotation, backface culling, depth sort, and flat shading."""
        if not self.vm: return

        fb = self.vm.fb
        # Precompute rotation trigonometry
        rx, ry, rz = math.radians(rot.x), math.radians(rot.y), math.radians(rot.z)
        cx, sx = math.cos(rx), math.sin(rx)
        cy, sy = math.cos(ry), math.sin(ry)
        cz, sz = math.cos(rz), math.sin(rz)

        # 1. Transform vertices to camera space
        cam_vertices = []
        for v in mesh.vertices:
            # Rotate Z
            x1 = v.x * cz - v.y * sz
            y1 = v.x * sz + v.y * cz
            z1 = v.z
            # Rotate X
            y2 = y1 * cx - z1 * sx
            z2 = y1 * sx + z1 * cx
            x2 = x1
            # Rotate Y
            x3 = x2 * cy + z2 * sy
            z3 = -x2 * sy + z2 * cy
            y3 = y2

            # Translate by pos
            cv = Vector3(x3 + pos.x, y3 + pos.y, z3 + pos.z)
            cam_vertices.append(cv)

        # 2. Process faces (Backface culling & Z-sorting)
        drawable_faces = []
        for face in mesh.faces:
            v0 = cam_vertices[face.v_indices[0]]
            v1 = cam_vertices[face.v_indices[1]]
            v2 = cam_vertices[face.v_indices[2]]

            # Reject if behind camera
            if v0.z <= 5.0 or v1.z <= 5.0 or v2.z <= 5.0:
                continue

            # Calculate normal in camera space
            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = edge1.cross(edge2).normalized()

            # Backface culling: Dot product of normal with view ray (from camera to v0)
            view_vec = v0.normalized()
            if normal.dot(view_vec) >= 0.0:
                continue # Faces away from camera

            # Project vertices to 2D screen coordinates
            p0 = self.project_vertex(v0)
            p1 = self.project_vertex(v1)
            p2 = self.project_vertex(v2)

            avg_z = (v0.z + v1.z + v2.z) / 3.0
            lit_color = self.shade_color(face.base_color, normal)
            drawable_faces.append((avg_z, p0, p1, p2, lit_color))

        # 3. Sort faces by descending depth (Painter's Algorithm)
        drawable_faces.sort(key=lambda item: item[0], reverse=True)

        # 4. Rasterize faces
        for _, p0, p1, p2, color in drawable_faces:
            if wireframe:
                self.draw_line(p0[0], p0[1], p1[0], p1[1], color)
                self.draw_line(p1[0], p1[1], p2[0], p2[1], color)
                self.draw_line(p2[0], p2[1], p0[0], p0[1], color)
            else:
                self.fill_triangle(p0[0], p0[1], p1[0], p1[1], p2[0], p2[1], color)

    def draw_line(self, x0, y0, x1, y1, color):
        fb = self.vm.fb
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy

        while True:
            if 0 <= x0 < WIDTH and 0 <= y0 < HEIGHT:
                off = (y0 * WIDTH + x0) * 4
                fb[off:off+4] = c_bytes
            if x0 == x1 and y0 == y1: break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def fill_triangle(self, x0, y0, x1, y1, x2, y2, color):
        """Scanline triangle filler."""
        fb = self.vm.fb
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])

        # Sort vertices by y: y0 <= y1 <= y2
        if y0 > y1: x0, x1 = x1, x0; y0, y1 = y1, y0
        if y0 > y2: x0, x2 = x2, x0; y0, y2 = y2, y0
        if y1 > y2: x1, x2 = x2, x1; y1, y2 = y2, y1

        if y0 == y2: return # Degenerate flat triangle

        total_height = y2 - y0

        for i in range(total_height):
            second_half = i > (y1 - y0) or (y1 == y0)
            segment_height = (y2 - y1) if second_half else (y1 - y0)
            if segment_height == 0: continue

            alpha = i / float(total_height)
            beta  = (i - (y1 - y0 if second_half else 0)) / float(segment_height)

            ax = int(x0 + (x2 - x0) * alpha)
            bx = int((x1 + (x2 - x1) * beta) if second_half else (x0 + (x1 - x0) * beta))

            if ax > bx: ax, bx = bx, ax

            curr_y = y0 + i
            if 0 <= curr_y < HEIGHT:
                # Clamp scanline span to screen
                start_x = max(0, ax)
                end_x   = min(WIDTH - 1, bx)
                if start_x <= end_x:
                    off_start = (curr_y * WIDTH + start_x) * 4
                    span_len = end_x - start_x + 1
                    fb[off_start : off_start + span_len * 4] = c_bytes * span_len
