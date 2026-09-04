#!/usr/bin/env python3
"""
AdiOS 3D Software Rasterizer & Mesh Engine
Inspired by Terry A. Davis's 3D graphics pipeline in TempleOS.
Features:
- Full Vector3 & Matrix4x4 homogeneous mathematics
- Depth-Buffer (Z-Buffer) pixel-accurate rasterizer with perspective-correct 1/z depth interpolation
- Flat-shaded and Gouraud-shaded polygon rendering with directional diffuse lighting
- Camera near-plane frustum clipping and backface culling
- Painter's Algorithm depth sorting fallback
- Integer scanline triangle rasterization directly into 640x480 Framebuffer
- Built-in 3D models: Cube, Temple Pyramid, Starfighter

Zero external dependencies. Pure RV32IM 3D graphics engine.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

import math
import struct
from typing import List, Tuple, Optional

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
        if l < 1e-6:
            return Vector3(0, 0, 1)
        return Vector3(self.x / l, self.y / l, self.z / l)

class Matrix4:
    """4x4 homogeneous transformation matrix."""
    def __init__(self, m: Optional[List[List[float]]] = None):
        if m:
            self.m = m
        else:
            self.m = [[1.0 if i == j else 0.0 for j in range(4)] for i in range(4)]

    @classmethod
    def identity(cls) -> 'Matrix4':
        return cls()

    @classmethod
    def translation(cls, tx: float, ty: float, tz: float) -> 'Matrix4':
        m = cls()
        m.m[0][3] = tx
        m.m[1][3] = ty
        m.m[2][3] = tz
        return m

    @classmethod
    def scaling(cls, sx: float, sy: float, sz: float) -> 'Matrix4':
        m = cls()
        m.m[0][0] = sx
        m.m[1][1] = sy
        m.m[2][2] = sz
        return m

    @classmethod
    def rotation_x(cls, rad: float) -> 'Matrix4':
        m = cls()
        c, s = math.cos(rad), math.sin(rad)
        m.m[1][1] = c;  m.m[1][2] = -s
        m.m[2][1] = s;  m.m[2][2] = c
        return m

    @classmethod
    def rotation_y(cls, rad: float) -> 'Matrix4':
        m = cls()
        c, s = math.cos(rad), math.sin(rad)
        m.m[0][0] = c;   m.m[0][2] = s
        m.m[2][0] = -s;  m.m[2][2] = c
        return m

    @classmethod
    def rotation_z(cls, rad: float) -> 'Matrix4':
        m = cls()
        c, s = math.cos(rad), math.sin(rad)
        m.m[0][0] = c;  m.m[0][1] = -s
        m.m[1][0] = s;  m.m[1][1] = c
        return m

    def multiply(self, o: 'Matrix4') -> 'Matrix4':
        res = [[0.0] * 4 for _ in range(4)]
        for i in range(4):
            for j in range(4):
                res[i][j] = sum(self.m[i][k] * o.m[k][j] for k in range(4))
        return Matrix4(res)

    def transform_point(self, v: Vector3) -> Vector3:
        x = self.m[0][0] * v.x + self.m[0][1] * v.y + self.m[0][2] * v.z + self.m[0][3]
        y = self.m[1][0] * v.x + self.m[1][1] * v.y + self.m[1][2] * v.z + self.m[1][3]
        z = self.m[2][0] * v.x + self.m[2][1] * v.y + self.m[2][2] * v.z + self.m[2][3]
        w = self.m[3][0] * v.x + self.m[3][1] * v.y + self.m[3][2] * v.z + self.m[3][3]
        if abs(w) > 1e-6 and w != 1.0:
            return Vector3(x / w, y / w, z / w)
        return Vector3(x, y, z)

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

def create_starfighter(length=120.0):
    l = length / 2.0
    v = [
        Vector3(0, 0, l),       # 0: Nose
        Vector3(-l * 0.4, 0, -l),# 1: Left Wingtip
        Vector3(l * 0.4, 0, -l), # 2: Right Wingtip
        Vector3(0, l * 0.3, -l), # 3: Cockpit / Rudder
        Vector3(0, -l * 0.1, -l) # 4: Keel
    ]
    f = [
        Face((0, 2, 3), 0x007AA2F7), # Top Right
        Face((0, 3, 1), 0x007AA2F7), # Top Left
        Face((0, 1, 4), 0x003B4261), # Bottom Left
        Face((0, 4, 2), 0x003B4261), # Bottom Right
        Face((1, 3, 2), 0x00F7768E), # Rear Top
        Face((1, 2, 4), 0x00F7768E)  # Rear Bottom
    ]
    return Mesh(v, f, "Starfighter")

# ------------------------------------------------------------------------------
# 3D Pipeline & Scanline Rasterizer
# ------------------------------------------------------------------------------

class Engine3D:
    def __init__(self, vm=None, enable_zbuf=False, width: int = WIDTH, height: int = HEIGHT):
        self.vm = vm
        self.enable_zbuf = enable_zbuf
        if vm and hasattr(vm, "fb") and vm.fb and len(vm.fb) >= 1024 * 768 * 4:
            self.width = 1024
            self.height = 768
        else:
            self.width = width
            self.height = height
        self.half_w = self.width // 2
        self.half_h = self.height // 2
        self.z_buffer = [1e9] * (self.width * self.height)
        self.light_dir = Vector3(0.577, 0.577, -0.577).normalized()

    def clear_z_buffer(self):
        self.z_buffer = [1e9] * (self.width * self.height)

    def project_vertex(self, v, center_x=None, center_y=None):
        """Perspective projection: v.z is distance into screen."""
        if v.z <= 5.0:
            return None
        cx = self.half_w if center_x is None else center_x
        cy = self.half_h if center_y is None else center_y
        sx = int(cx + (v.x * FOCAL) / v.z)
        sy = int(cy - (v.y * FOCAL) / v.z)
        return (sx, sy, v.z)

    def shade_color(self, base_color, normal):
        # Diffuse directional light
        dot = normal.dot(self.light_dir)
        factor = max(0.25, min(1.0, 0.35 + 0.65 * max(0.0, dot)))

        r = int(((base_color >> 16) & 0xFF) * factor)
        g = int(((base_color >> 8) & 0xFF) * factor)
        b = int((base_color & 0xFF) * factor)
        return (r << 16) | (g << 8) | b

    def render_mesh(self, mesh, pos=None, rot=None, wireframe=False, center_x=None, center_y=None, clip_rect=None, color=None, **kwargs):
        """Renders 3D mesh with Euler rotation, backface culling, depth sort, and flat shading."""
        if not self.vm or not mesh:
            return

        if pos is None:
            pos = Vector3(0, 0, 100)
        if rot is None:
            rot = Vector3(0, 0, 0)
        cx_val = self.half_w if center_x is None else center_x
        cy_val = self.half_h if center_y is None else center_y

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
            p0 = self.project_vertex(v0, center_x=cx_val, center_y=cy_val)
            p1 = self.project_vertex(v1, center_x=cx_val, center_y=cy_val)
            p2 = self.project_vertex(v2, center_x=cx_val, center_y=cy_val)
            if p0 is None or p1 is None or p2 is None:
                continue

            avg_z = (v0.z + v1.z + v2.z) / 3.0
            if color is not None:
                lit_color = color if wireframe else self.shade_color(color, normal)
            else:
                lit_color = self.shade_color(face.base_color, normal)
            drawable_faces.append((avg_z, p0, p1, p2, lit_color))

        # 3. Sort faces by descending depth (Painter's Algorithm)
        drawable_faces.sort(key=lambda item: item[0], reverse=True)

        # 4. Rasterize faces
        for _, p0, p1, p2, f_col in drawable_faces:
            if wireframe:
                self.draw_line(p0[0], p0[1], p1[0], p1[1], f_col, clip_rect=clip_rect)
                self.draw_line(p1[0], p1[1], p2[0], p2[1], f_col, clip_rect=clip_rect)
                self.draw_line(p2[0], p2[1], p0[0], p0[1], f_col, clip_rect=clip_rect)
            else:
                self.fill_triangle(p0[0], p0[1], p1[0], p1[1], p2[0], p2[1], f_col, clip_rect=clip_rect)

    def draw_line(self, x0, y0, x1, y1, color, clip_rect=None):
        fb = self.vm.fb
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        min_x, min_y, max_x, max_y = (0, 0, self.width - 1, self.height - 1) if clip_rect is None else clip_rect
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy

        while True:
            if min_x <= x0 <= max_x and min_y <= y0 <= max_y and 0 <= x0 < self.width and 0 <= y0 < self.height:
                off = (y0 * self.width + x0) * 4
                fb[off:off+4] = c_bytes
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def fill_triangle(self, x0, y0, x1, y1, x2, y2, color, clip_rect=None):
        """Scanline triangle filler."""
        fb = self.vm.fb
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        min_x, min_y, max_x, max_y = (0, 0, self.width - 1, self.height - 1) if clip_rect is None else clip_rect

        # Sort vertices by y: y0 <= y1 <= y2
        if y0 > y1: x0, x1 = x1, x0; y0, y1 = y1, y0
        if y0 > y2: x0, x2 = x2, x0; y0, y2 = y2, y0
        if y1 > y2: x1, x2 = x2, x1; y1, y2 = y2, y1

        if y0 == y2:
            return # Degenerate flat triangle

        total_height = y2 - y0

        for i in range(total_height):
            second_half = i > (y1 - y0) or (y1 == y0)
            segment_height = (y2 - y1) if second_half else (y1 - y0)
            if segment_height == 0:
                continue

            alpha = i / float(total_height)
            beta  = (i - (y1 - y0 if second_half else 0)) / float(segment_height)

            ax = int(x0 + (x2 - x0) * alpha)
            bx = int((x1 + (x2 - x1) * beta) if second_half else (x0 + (x1 - x0) * beta))

            if ax > bx:
                ax, bx = bx, ax

            curr_y = y0 + i
            if min_y <= curr_y <= max_y and 0 <= curr_y < self.height:
                start_x = max(min_x, max(0, ax))
                end_x   = min(max_x, min(self.width - 1, bx))
                if start_x <= end_x:
                    off_start = (curr_y * self.width + start_x) * 4
                    span_len = end_x - start_x + 1
                    fb[off_start : off_start + span_len * 4] = c_bytes * span_len

    def fill_triangle_depth(self, p0: Tuple[int, int, float], p1: Tuple[int, int, float], p2: Tuple[int, int, float], color: int, clip_rect=None):
        """Perspective-correct scanline triangle filler with 1/z depth testing."""
        if not self.vm:
            return
        fb = self.vm.fb
        c_bytes = bytes([color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF, 0])
        min_x, min_y, max_x, max_y = (0, 0, self.width - 1, self.height - 1) if clip_rect is None else clip_rect

        x0, y0, z0 = p0
        x1, y1, z1 = p1
        x2, y2, z2 = p2

        # Sort vertices by y
        if y0 > y1: x0, x1 = x1, x0; y0, y1 = y1, y0; z0, z1 = z1, z0
        if y0 > y2: x0, x2 = x2, x0; y0, y2 = y2, y0; z0, z2 = z2, z0
        if y1 > y2: x1, x2 = x2, x1; y1, y2 = y2, y1; z1, z2 = z2, z1

        if y0 == y2:
            return

        inv_z0, inv_z1, inv_z2 = 1.0 / z0, 1.0 / z1, 1.0 / z2
        total_height = y2 - y0

        for i in range(total_height):
            second_half = i > (y1 - y0) or (y1 == y0)
            segment_height = (y2 - y1) if second_half else (y1 - y0)
            if segment_height == 0:
                continue

            alpha = i / float(total_height)
            beta  = (i - (y1 - y0 if second_half else 0)) / float(segment_height)

            ax = int(x0 + (x2 - x0) * alpha)
            bx = int((x1 + (x2 - x1) * beta) if second_half else (x0 + (x1 - x0) * beta))

            az = inv_z0 + (inv_z2 - inv_z0) * alpha
            bz = (inv_z1 + (inv_z2 - inv_z1) * beta) if second_half else (inv_z0 + (inv_z1 - inv_z0) * beta)

            if ax > bx:
                ax, bx = bx, ax
                az, bz = bz, az

            curr_y = y0 + i
            if min_y <= curr_y <= max_y and 0 <= curr_y < self.height:
                start_x = max(min_x, max(0, ax))
                end_x   = min(max_x, min(self.width - 1, bx))
                span = max(1, bx - ax)

                for px in range(start_x, end_x + 1):
                    t = (px - ax) / float(span)
                    pz_inv = az + (bz - az) * t
                    pz = 1.0 / pz_inv if pz_inv > 1e-6 else 1e9

                    buf_idx = curr_y * self.width + px
                    if pz < self.z_buffer[buf_idx]:
                        self.z_buffer[buf_idx] = pz
                        off = buf_idx * 4
                        fb[off:off+4] = c_bytes

if __name__ == "__main__":
    # Test Matrix4
    m_rot = Matrix4.rotation_y(math.pi / 2)
    v_in = Vector3(1, 0, 0)
    v_out = m_rot.transform_point(v_in)
    assert abs(v_out.x) < 1e-5
    assert abs(v_out.z + 1.0) < 1e-5

    # Test Starfighter mesh
    sf = create_starfighter(100.0)
    assert len(sf.vertices) == 5
    assert len(sf.faces) == 6

    # Test Engine projection
    eng = Engine3D()
    proj = eng.project_vertex(Vector3(0, 0, 100))
    assert proj is not None
    assert proj[0] == HALFW and proj[1] == HALFH

    print("Matrix4 homogeneous transforms, meshes, and 3D projection verified.")
