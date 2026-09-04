#!/usr/bin/env python3
"""
AdiOS Software OpenGL Subsystem: Blinn-Phong Lighting Model (gl/gl_lighting.py)
Implements OpenGL 1.1 fixed-function lighting pipeline:
- Ambient, Diffuse (Lambertian), and Specular (Blinn-Phong) components
- Multiple Light Sources: Directional and Positional Point Lights
- Distance attenuation: 1.0 / (constant + linear*d + quadratic*d^2)
- Material Properties: Ka (ambient), Kd (diffuse), Ks (specular), and Shininess exponent
- Vector3 lighting math: dot, reflect, halfway vector, normalization

Zero external dependencies. Pure RV32IM graphics pipeline component.
STRICT ZERO EMOJI POLICY.
"""

import math
from typing import List, Tuple, Optional

class Vec3:
    __slots__ = ("x", "y", "z")
    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def __add__(self, o: 'Vec3') -> 'Vec3':
        return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, o: 'Vec3') -> 'Vec3':
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, s: float) -> 'Vec3':
        return Vec3(self.x * s, self.y * s, self.z * s)

    def dot(self, o: 'Vec3') -> float:
        return self.x * o.x + self.y * o.y + self.z * o.z

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def normalized(self) -> 'Vec3':
        l = self.length()
        if l == 0:
            return Vec3(0, 0, 0)
        return Vec3(self.x / l, self.y / l, self.z / l)

class Material:
    def __init__(
        self,
        ambient: Tuple[float, float, float] = (0.2, 0.2, 0.2),
        diffuse: Tuple[float, float, float] = (0.8, 0.8, 0.8),
        specular: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        shininess: float = 32.0
    ):
        self.ambient = ambient
        self.diffuse = diffuse
        self.specular = specular
        self.shininess = shininess

class LightSource:
    def __init__(
        self,
        position: Vec3,
        is_directional: bool = True,
        ambient: Tuple[float, float, float] = (0.1, 0.1, 0.1),
        diffuse: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        specular: Tuple[float, float, float] = (1.0, 1.0, 1.0),
        att_const: float = 1.0,
        att_lin: float = 0.045,
        att_quad: float = 0.0075
    ):
        self.position = position # Direction if directional
        self.is_directional = is_directional
        self.ambient = ambient
        self.diffuse = diffuse
        self.specular = specular
        self.att_const = att_const
        self.att_lin = att_lin
        self.att_quad = att_quad

class LightingEngine:
    """
    Computes Blinn-Phong lighting across active lights and materials.
    """
    def __init__(self):
        self.lights: List[LightSource] = []
        self.global_ambient = (0.1, 0.1, 0.1)

    def add_light(self, light: LightSource):
        self.lights.append(light)

    def shade(self, point: Vec3, normal: Vec3, eye_pos: Vec3, material: Material) -> int:
        """
        Shades a fragment point. Returns packed 32-bit ARGB color.
        """
        N = normal.normalized()
        V = (eye_pos - point).normalized()

        tot_r = self.global_ambient[0] * material.ambient[0]
        tot_g = self.global_ambient[1] * material.ambient[1]
        tot_b = self.global_ambient[2] * material.ambient[2]

        for light in self.lights:
            if light.is_directional:
                L = (light.position * -1.0).normalized()
                attenuation = 1.0
            else:
                light_dir = light.position - point
                dist = light_dir.length()
                L = light_dir.normalized()
                attenuation = 1.0 / (light.att_const + light.att_lin * dist + light.att_quad * (dist * dist))

            # Ambient
            tot_r += light.ambient[0] * material.ambient[0] * attenuation
            tot_g += light.ambient[1] * material.ambient[1] * attenuation
            tot_b += light.ambient[2] * material.ambient[2] * attenuation

            # Diffuse (Lambert)
            n_dot_l = max(0.0, N.dot(L))
            if n_dot_l > 0.0:
                tot_r += light.diffuse[0] * material.diffuse[0] * n_dot_l * attenuation
                tot_g += light.diffuse[1] * material.diffuse[1] * n_dot_l * attenuation
                tot_b += light.diffuse[2] * material.diffuse[2] * n_dot_l * attenuation

                # Specular (Blinn-Phong halfway vector)
                H = (L + V).normalized()
                n_dot_h = max(0.0, N.dot(H))
                spec_factor = math.pow(n_dot_h, material.shininess)

                tot_r += light.specular[0] * material.specular[0] * spec_factor * attenuation
                tot_g += light.specular[1] * material.specular[1] * spec_factor * attenuation
                tot_b += light.specular[2] * material.specular[2] * spec_factor * attenuation

        # Clamp RGB to [0, 255]
        ir = min(255, max(0, int(tot_r * 255.0)))
        ig = min(255, max(0, int(tot_g * 255.0)))
        ib = min(255, max(0, int(tot_b * 255.0)))

        return (0xFF << 24) | (ir << 16) | (ig << 8) | ib
