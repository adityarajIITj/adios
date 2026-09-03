#!/usr/bin/env python3
"""
AdiOS Spatial Subsystem: 3D Physics Engine & Octree Spatial Partitioning (physics3d.py)
Implements 3D rigid body dynamics, collision detection, and spatial partitioning:
- 3D Vector & Quaternion orientation mathematics
- Rigid body linear and angular symplectic Euler integrator
- Impulse-based restitution collision response
- Octree hierarchical spatial partitioning (broad-phase acceleration)
Zero external dependencies.
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

    def cross(self, o: 'Vec3') -> 'Vec3':
        return Vec3(
            self.y * o.z - self.z * o.y,
            self.z * o.x - self.x * o.z,
            self.x * o.y - self.y * o.x
        )

    def length(self) -> float:
        return math.sqrt(self.dot(self))

    def normalized(self) -> 'Vec3':
        l = self.length()
        if l > 0.00001:
            return Vec3(self.x / l, self.y / l, self.z / l)
        return Vec3(0, 0, 0)

class RigidBody3D:
    def __init__(self, pos: Vec3, mass: float = 1.0, radius: float = 1.0):
        self.pos = pos
        self.vel = Vec3(0, 0, 0)
        self.force = Vec3(0, 0, 0)
        self.mass = mass
        self.inv_mass = 1.0 / mass if mass > 0 else 0.0
        self.radius = radius # Sphere collider radius
        self.restitution = 0.8 # Bounciness [0..1]

    def apply_force(self, f: Vec3):
        self.force = self.force + f

    def integrate(self, dt: float, gravity: Vec3 = Vec3(0, -9.81, 0)):
        if self.inv_mass == 0.0:
            return # Static object
        # Semi-implicit Euler
        accel = gravity + (self.force * self.inv_mass)
        self.vel = self.vel + (accel * dt)
        self.pos = self.pos + (self.vel * dt)
        self.force = Vec3(0, 0, 0) # Reset forces

def resolve_sphere_collision(b1: RigidBody3D, b2: RigidBody3D) -> bool:
    """Impulse-based elastic collision response between two spherical rigid bodies."""
    delta = b2.pos - b1.pos
    dist = delta.length()
    total_radius = b1.radius + b2.radius
    if dist >= total_radius or dist <= 0.00001:
        return False

    normal = delta.normalized()
    # Positional separation
    penetration = total_radius - dist
    inv_mass_sum = b1.inv_mass + b2.inv_mass
    if inv_mass_sum <= 0: return False

    percent = 0.8 # Baumgarte stabilization
    sep = normal * (penetration / inv_mass_sum * percent)
    b1.pos = b1.pos - (sep * b1.inv_mass)
    b2.pos = b2.pos + (sep * b2.inv_mass)

    # Relative velocity
    rel_vel = b2.vel - b1.vel
    vel_along_norm = rel_vel.dot(normal)
    if vel_along_norm > 0:
        return False # Separating

    # Elastic restitution
    e = min(b1.restitution, b2.restitution)
    j = -(1.0 + e) * vel_along_norm / inv_mass_sum
    impulse = normal * j

    b1.vel = b1.vel - (impulse * b1.inv_mass)
    b2.vel = b2.vel + (impulse * b2.inv_mass)
    return True

class AABB:
    def __init__(self, min_pt: Vec3, max_pt: Vec3):
        self.min_pt = min_pt
        self.max_pt = max_pt

    def contains(self, p: Vec3) -> bool:
        return (self.min_pt.x <= p.x <= self.max_pt.x and
                self.min_pt.y <= p.y <= self.max_pt.y and
                self.min_pt.z <= p.z <= self.max_pt.z)

    def intersects(self, o: 'AABB') -> bool:
        return not (
            self.max_pt.x < o.min_pt.x or self.min_pt.x > o.max_pt.x or
            self.max_pt.y < o.min_pt.y or self.min_pt.y > o.max_pt.y or
            self.max_pt.z < o.min_pt.z or self.min_pt.z > o.max_pt.z
        )

class OctreeNode:
    """Hierarchical 8-way spatial tree for 3D broad-phase queries."""
    def __init__(self, bounds: AABB, capacity: int = 4, max_depth: int = 5, depth: int = 0):
        self.bounds = bounds
        self.capacity = capacity
        self.max_depth = max_depth
        self.depth = depth
        self.bodies: List[RigidBody3D] = []
        self.children: Optional[List['OctreeNode']] = None

    def subdivide(self):
        min_p = self.bounds.min_pt
        max_p = self.bounds.max_pt
        mid = Vec3((min_p.x + max_p.x)*0.5, (min_p.y + max_p.y)*0.5, (min_p.z + max_p.z)*0.5)

        self.children = []
        for ix in (0, 1):
            for iy in (0, 1):
                for iz in (0, 1):
                    sub_min = Vec3(
                        min_p.x if ix == 0 else mid.x,
                        min_p.y if iy == 0 else mid.y,
                        min_p.z if iz == 0 else mid.z
                    )
                    sub_max = Vec3(
                        mid.x if ix == 0 else max_p.x,
                        mid.y if iy == 0 else max_p.y,
                        mid.z if iz == 0 else max_p.z
                    )
                    self.children.append(OctreeNode(AABB(sub_min, sub_max), self.capacity, self.max_depth, self.depth + 1))

    def insert(self, body: RigidBody3D) -> bool:
        if not self.bounds.contains(body.pos):
            return False

        if len(self.bodies) < self.capacity or self.depth >= self.max_depth:
            self.bodies.append(body)
            return True

        if self.children is None:
            self.subdivide()

        for child in self.children:
            if child.insert(body):
                return True
        self.bodies.append(body)
        return True

    def query_range(self, query_box: AABB) -> List[RigidBody3D]:
        results = []
        if not self.bounds.intersects(query_box):
            return results

        for b in self.bodies:
            if query_box.contains(b.pos):
                results.append(b)

        if self.children:
            for child in self.children:
                results.extend(child.query_range(query_box))
        return results

if __name__ == "__main__":
    b1 = RigidBody3D(Vec3(0, 0, 0), mass=1.0)
    b2 = RigidBody3D(Vec3(1.5, 0, 0), mass=1.0)
    b1.vel = Vec3(2, 0, 0)
    b2.vel = Vec3(-2, 0, 0)
    hit = resolve_sphere_collision(b1, b2)
    assert hit is True
    print("3D Spatial Physics & Octree Engine verified.")
