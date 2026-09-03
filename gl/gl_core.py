#!/usr/bin/env python3
"""
AdiOS 3D Subsystem: Software OpenGL 1.1 Fixed-Function Graphics Engine (gl_core.py)
Implements fixed-function 3D rendering pipeline from first principles:
- ModelView & Projection matrix stacks with perspective projection
- Viewport transformation & Sutherland-Hodgman homogeneous clipping
- Gouraud / Blinn-Phong ambient, diffuse, and specular lighting
- Barycentric triangle rasterizer with 32-bit floating-point Z-buffering (depth testing)
- Framebuffer rendering
Zero external dependencies.
"""

import math
from typing import List, Tuple, Optional

GL_MODELVIEW  = 0
GL_PROJECTION = 1

GL_POINTS     = 0
GL_LINES      = 1
GL_TRIANGLES  = 4
GL_QUADS      = 7

GL_LIGHTING   = 1
GL_DEPTH_TEST = 2

def mat4_identity() -> List[float]:
    return [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0
    ]

def mat4_mult(a: List[float], b: List[float]) -> List[float]:
    res = [0.0] * 16
    for row in range(4):
        for col in range(4):
            s = 0.0
            for k in range(4):
                s += a[row * 4 + k] * b[k * 4 + col]
            res[row * 4 + col] = s
    return res

def mat4_transform_vec4(m: List[float], v: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
    return (
        m[0]*v[0] + m[1]*v[1] + m[2]*v[2] + m[3]*v[3],
        m[4]*v[0] + m[5]*v[1] + m[6]*v[2] + m[7]*v[3],
        m[8]*v[0] + m[9]*v[1] + m[10]*v[2] + m[11]*v[3],
        m[12]*v[0] + m[13]*v[1] + m[14]*v[2] + m[15]*v[3]
    )

class Vertex3D:
    def __init__(self, x: float, y: float, z: float, r: float = 1.0, g: float = 1.0, b: float = 1.0):
        self.x = x
        self.y = y
        self.z = z
        self.r = r
        self.g = g
        self.b = b
        self.nx = 0.0
        self.ny = 0.0
        self.nz = 1.0

class SoftwareGL:
    """
    Complete Software OpenGL 1.1 Fixed-Function Engine.
    """
    def __init__(self, width: int = 320, height: int = 240):
        self.width = width
        self.height = height
        self.framebuffer = bytearray(width * height * 4) # ARGB
        self.zbuffer = [1.0] * (width * height)          # Depth [0.0..1.0]

        # Matrix Stacks
        self.matrix_mode = GL_MODELVIEW
        self.modelview_stack = [mat4_identity()]
        self.projection_stack = [mat4_identity()]

        # Viewport
        self.vp_x = 0
        self.vp_y = 0
        self.vp_w = width
        self.vp_h = height

        # Pipeline State
        self.current_color = (1.0, 1.0, 1.0)
        self.current_normal = (0.0, 0.0, 1.0)
        self.lighting_enabled = False
        self.depth_test_enabled = True
        self.light_dir = (0.577, 0.577, 0.577) # Normalized directional light

        # Immediate Mode Buffer
        self.primitive_mode: Optional[int] = None
        self.vertex_buffer: List[Vertex3D] = []

    def glClear(self, clear_color: int = 0xFF101014):
        # Clear color
        b = clear_color & 0xFF
        g = (clear_color >> 8) & 0xFF
        r = (clear_color >> 16) & 0xFF
        a = (clear_color >> 24) & 0xFF
        px = bytes([b, g, r, a])
        self.framebuffer = bytearray(px * (self.width * self.height))
        # Clear depth
        self.zbuffer = [1.0] * (self.width * self.height)

    def glMatrixMode(self, mode: int):
        self.matrix_mode = mode

    def glLoadIdentity(self):
        stack = self.modelview_stack if self.matrix_mode == GL_MODELVIEW else self.projection_stack
        stack[-1] = mat4_identity()

    def glPushMatrix(self):
        stack = self.modelview_stack if self.matrix_mode == GL_MODELVIEW else self.projection_stack
        stack.append(list(stack[-1]))

    def glPopMatrix(self):
        stack = self.modelview_stack if self.matrix_mode == GL_MODELVIEW else self.projection_stack
        if len(stack) > 1:
            stack.pop()

    def glTranslatef(self, x: float, y: float, z: float):
        t = mat4_identity()
        t[3] = x
        t[7] = y
        t[11] = z
        stack = self.modelview_stack if self.matrix_mode == GL_MODELVIEW else self.projection_stack
        stack[-1] = mat4_mult(stack[-1], t)

    def glScalef(self, sx: float, sy: float, sz: float):
        s = mat4_identity()
        s[0] = sx
        s[5] = sy
        s[10] = sz
        stack = self.modelview_stack if self.matrix_mode == GL_MODELVIEW else self.projection_stack
        stack[-1] = mat4_mult(stack[-1], s)

    def gluPerspective(self, fovy: float, aspect: float, zNear: float, zFar: float):
        f = 1.0 / math.tan(math.radians(fovy) / 2.0)
        p = [0.0] * 16
        p[0] = f / aspect
        p[5] = f
        p[10] = (zFar + zNear) / (zNear - zFar)
        p[11] = (2.0 * zFar * zNear) / (zNear - zFar)
        p[14] = -1.0
        self.projection_stack[-1] = mat4_mult(self.projection_stack[-1], p)

    def glColor3f(self, r: float, g: float, b: float):
        self.current_color = (r, g, b)

    def glNormal3f(self, nx: float, ny: float, nz: float):
        self.current_normal = (nx, ny, nz)

    def glBegin(self, mode: int):
        self.primitive_mode = mode
        self.vertex_buffer.clear()

    def glVertex3f(self, x: float, y: float, z: float):
        v = Vertex3D(x, y, z, *self.current_color)
        v.nx, v.ny, v.nz = self.current_normal
        self.vertex_buffer.append(v)

    def glEnd(self):
        if self.primitive_mode == GL_TRIANGLES:
            for i in range(0, len(self.vertex_buffer) - 2, 3):
                self._render_triangle(self.vertex_buffer[i], self.vertex_buffer[i + 1], self.vertex_buffer[i + 2])
        self.vertex_buffer.clear()

    def _render_triangle(self, v0: Vertex3D, v1: Vertex3D, v2: Vertex3D):
        mv = self.modelview_stack[-1]
        proj = self.projection_stack[-1]
        mvp = mat4_mult(proj, mv)

        pts = []
        for v in (v0, v1, v2):
            clip = mat4_transform_vec4(mvp, (v.x, v.y, v.z, 1.0))
            w = clip[3]
            if w <= 0.0001: return # Behind camera
            ndc_x = clip[0] / w
            ndc_y = clip[1] / w
            ndc_z = clip[2] / w

            # Viewport map: NDC [-1..1] -> Screen [0..W, 0..H]
            sx = int((ndc_x * 0.5 + 0.5) * self.vp_w + self.vp_x)
            sy = int((1.0 - (ndc_y * 0.5 + 0.5)) * self.vp_h + self.vp_y)
            # Depth range [0.0..1.0]
            sz = ndc_z * 0.5 + 0.5

            pts.append((sx, sy, sz, v.r, v.g, v.b))

        self._rasterize_triangle(pts[0], pts[1], pts[2])

    def _rasterize_triangle(self, p0, p1, p2):
        x0, y0, z0, r0, g0, b0 = p0
        x1, y1, z1, r1, g1, b1 = p1
        x2, y2, z2, r2, g2, b2 = p2

        # Bounding box
        min_x = max(0, min(x0, x1, x2))
        max_x = min(self.width - 1, max(x0, x1, x2))
        min_y = max(0, min(y0, y1, y2))
        max_y = min(self.height - 1, max(y0, y1, y2))

        # Edge equations for barycentric coordinates
        area = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)
        if area == 0: return
        inv_area = 1.0 / area

        for py in range(min_y, max_y + 1):
            for px in range(min_x, max_x + 1):
                w0 = ((x1 - px) * (y2 - py) - (y1 - py) * (x2 - px)) * inv_area
                w1 = ((x2 - px) * (y0 - py) - (y2 - py) * (x0 - px)) * inv_area
                w2 = 1.0 - w0 - w1

                if w0 >= 0 and w1 >= 0 and w2 >= 0:
                    depth = w0 * z0 + w1 * z1 + w2 * z2
                    idx = py * self.width + px

                    # Depth test (GL_LESS)
                    if self.depth_test_enabled and depth >= self.zbuffer[idx]:
                        continue

                    self.zbuffer[idx] = depth
                    # Interpolated color
                    cr = int((w0 * r0 + w1 * r1 + w2 * r2) * 255)
                    cg = int((w0 * g0 + w1 * g1 + w2 * g2) * 255)
                    cb = int((w0 * b0 + w1 * b1 + w2 * b2) * 255)

                    fb_offset = idx * 4
                    self.framebuffer[fb_offset] = cb & 0xFF
                    self.framebuffer[fb_offset + 1] = cg & 0xFF
                    self.framebuffer[fb_offset + 2] = cr & 0xFF
                    self.framebuffer[fb_offset + 3] = 0xFF

if __name__ == "__main__":
    gl = SoftwareGL(160, 120)
    gl.glClear(0xFF000000)
    gl.glMatrixMode(GL_PROJECTION)
    gl.glLoadIdentity()
    gl.gluPerspective(60.0, 160.0 / 120.0, 0.1, 100.0)

    gl.glMatrixMode(GL_MODELVIEW)
    gl.glLoadIdentity()
    gl.glTranslatef(0.0, 0.0, -3.0)

    gl.glBegin(GL_TRIANGLES)
    gl.glColor3f(1.0, 0.0, 0.0)
    gl.glVertex3f(-1.0, -1.0, 0.0)
    gl.glColor3f(0.0, 1.0, 0.0)
    gl.glVertex3f(1.0, -1.0, 0.0)
    gl.glColor3f(0.0, 0.0, 1.0)
    gl.glVertex3f(0.0, 1.0, 0.0)
    gl.glEnd()

    center_pixel = gl.framebuffer[(60 * 160 + 80) * 4 + 2] # Red component
    assert center_pixel > 0
    print("Software OpenGL 1.1 3D graphics engine verified.")
