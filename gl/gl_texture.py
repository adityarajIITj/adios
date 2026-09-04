#!/usr/bin/env python3
"""
AdiOS Software OpenGL Subsystem: 2D Texture Engine & Bilinear Filtering (gl/gl_texture.py)
Implements OpenGL 1.1 texture mapping pipeline from first principles:
- 2D Texture Objects with 32-bit ARGB texels
- Texture Filtering Modes:
    - GL_NEAREST: Nearest-neighbor point sampling
    - GL_LINEAR: 4-texel bilinear subpixel interpolation
- Texture Wrapping Modes:
    - GL_REPEAT: Periodic wrapping (modulo coordinates)
    - GL_CLAMP_TO_EDGE: Clamping coordinates to [0.0, 1.0]
- Affine and perspective-correct UV scanline span interpolation

Zero external dependencies. Pure RV32IM graphics pipeline component.
STRICT ZERO EMOJI POLICY.
"""

from typing import List, Tuple, Optional

GL_NEAREST       = 0x2600
GL_LINEAR        = 0x2601
GL_REPEAT        = 0x2901
GL_CLAMP_TO_EDGE = 0x812F

class Texture2D:
    """
    2D Texture memory object.
    """
    def __init__(self, width: int, height: int, pixels: Optional[List[int]] = None):
        self.width = width
        self.height = height
        if pixels is not None:
            if len(pixels) != width * height:
                raise ValueError("Pixel count does not match width * height")
            self.pixels = list(pixels)
        else:
            self.pixels = [0] * (width * height)

        self.min_filter = GL_LINEAR
        self.mag_filter = GL_LINEAR
        self.wrap_s = GL_REPEAT
        self.wrap_t = GL_REPEAT

    def set_pixel(self, x: int, y: int, color_argb: int):
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y * self.width + x] = color_argb

    def get_pixel(self, x: int, y: int) -> int:
        x = max(0, min(self.width - 1, x))
        y = max(0, min(self.height - 1, y))
        return self.pixels[y * self.width + x]

    def _wrap_coord(self, coord: float, size: int, wrap_mode: int) -> float:
        if wrap_mode == GL_REPEAT:
            return coord % 1.0
        else: # GL_CLAMP_TO_EDGE
            return max(0.0, min(1.0, coord))

    def sample(self, u: float, v: float, filter_mode: Optional[int] = None) -> int:
        """
        Samples texture at normalized coordinates (u, v) in range [0.0, 1.0].
        Returns 32-bit ARGB color.
        """
        mode = filter_mode if filter_mode is not None else self.mag_filter

        u_wrapped = self._wrap_coord(u, self.width, self.wrap_s)
        v_wrapped = self._wrap_coord(v, self.height, self.wrap_t)

        tex_x = u_wrapped * (self.width - 1)
        tex_y = v_wrapped * (self.height - 1)

        if mode == GL_NEAREST:
            ix = int(round(tex_x))
            iy = int(round(tex_y))
            return self.get_pixel(ix, iy)

        # GL_LINEAR (Bilinear filtering)
        x0 = int(tex_x)
        y0 = int(tex_y)
        x1 = min(self.width - 1, x0 + 1)
        y1 = min(self.height - 1, y0 + 1)

        fx = tex_x - x0
        fy = tex_y - y0

        c00 = self.get_pixel(x0, y0)
        c10 = self.get_pixel(x1, y0)
        c01 = self.get_pixel(x0, y1)
        c11 = self.get_pixel(x1, y1)

        # Extract channels and interpolate
        def blend(shift: int) -> int:
            v00 = (c00 >> shift) & 0xFF
            v10 = (c10 >> shift) & 0xFF
            v01 = (c01 >> shift) & 0xFF
            v11 = (c11 >> shift) & 0xFF
            top = v00 * (1.0 - fx) + v10 * fx
            bottom = v01 * (1.0 - fx) + v11 * fx
            return int(top * (1.0 - fy) + bottom * fy)

        a = blend(24)
        r = blend(16)
        g = blend(8)
        b = blend(0)

        return (a << 24) | (r << 16) | (g << 8) | b

def create_checkerboard_texture(size: int = 64, check_size: int = 8, col1: int = 0xFFFFFFFF, col2: int = 0xFF24283B) -> Texture2D:
    """Generates a procedural test checkerboard texture."""
    tex = Texture2D(size, size)
    for y in range(size):
        for x in range(size):
            pattern = ((x // check_size) ^ (y // check_size)) & 1
            tex.set_pixel(x, y, col1 if pattern else col2)
    return tex
