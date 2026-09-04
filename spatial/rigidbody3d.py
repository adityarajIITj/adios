#!/usr/bin/env python3
"""
AdiOS Spatial Subsystem: 3D Rigid Body Dynamics Simulator (spatial/rigidbody3d.py)
Implements 6-DOF (Degrees of Freedom) Newtonian rigid body mechanics:
- Linear state: position, velocity, acceleration, mass, inverse mass
- Angular state: orientation, angular velocity, torque, inertia tensor matrix
- Torque generation: tau = r x F from off-center force applications
- Inertia tensor calculation for standard shapes (Box, Sphere, Cylinder)
- Semi-implicit symplectic Euler numerical integrator
- Ground plane collision restitution and kinetic friction

Zero external dependencies. Pure RV32IM physics engine component.
STRICT ZERO EMOJI POLICY.
"""

import math
from typing import Tuple, List, Optional
from gl.gl_lighting import Vec3

class Mat3:
    """3x3 Matrix for Moment of Inertia calculations."""
    def __init__(self, m: Optional[List[List[float]]] = None):
        if m:
            self.m = m
        else:
            self.m = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]

    @staticmethod
    def diag(ixx: float, iyy: float, izz: float) -> 'Mat3':
        return Mat3([[ixx, 0.0, 0.0], [0.0, iyy, 0.0], [0.0, 0.0, izz]])

    def inverse_diag(self) -> 'Mat3':
        return Mat3([
            [1.0 / self.m[0][0] if self.m[0][0] != 0 else 0.0, 0.0, 0.0],
            [0.0, 1.0 / self.m[1][1] if self.m[1][1] != 0 else 0.0, 0.0],
            [0.0, 0.0, 1.0 / self.m[2][2] if self.m[2][2] != 0 else 0.0]
        ])

    def mul_vec(self, v: Vec3) -> Vec3:
        return Vec3(
            self.m[0][0]*v.x + self.m[0][1]*v.y + self.m[0][2]*v.z,
            self.m[1][0]*v.x + self.m[1][1]*v.y + self.m[1][2]*v.z,
            self.m[2][0]*v.x + self.m[2][1]*v.y + self.m[2][2]*v.z
        )

def cross(a: Vec3, b: Vec3) -> Vec3:
    return Vec3(
        a.y * b.z - a.z * b.y,
        a.z * b.x - a.x * b.z,
        a.x * b.y - a.y * b.x
    )

class RigidBody3D:
    """
    6-DOF Rigid Body with linear and angular momentum.
    """
    def __init__(self, mass: float = 1.0, is_static: bool = False):
        self.mass = mass
        self.is_static = is_static
        self.inv_mass = 0.0 if is_static or mass <= 0 else 1.0 / mass

        # Linear state
        self.position = Vec3(0, 0, 0)
        self.velocity = Vec3(0, 0, 0)
        self.force_acc = Vec3(0, 0, 0)

        # Angular state
        self.rotation = Vec3(0, 0, 0) # Euler angles in degrees
        self.angular_velocity = Vec3(0, 0, 0) # rad/s
        self.torque_acc = Vec3(0, 0, 0)

        # Default box inertia: width=1, height=1, depth=1
        ixx = (1.0 / 12.0) * mass * (1.0 + 1.0)
        self.inertia_tensor = Mat3.diag(ixx, ixx, ixx)
        self.inv_inertia_tensor = self.inertia_tensor.inverse_diag()

        # Damping
        self.linear_damping = 0.98
        self.angular_damping = 0.95
        self.restitution = 0.6 # Bounce bounciness

    def apply_force(self, force: Vec3):
        if not self.is_static:
            self.force_acc = self.force_acc + force

    def apply_force_at_point(self, force: Vec3, world_point: Vec3):
        """Applies force at a world offset point, generating torque."""
        if self.is_static:
            return
        self.apply_force(force)
        r = world_point - self.position
        torque = cross(r, force)
        self.torque_acc = self.torque_acc + torque

    def apply_torque(self, torque: Vec3):
        if not self.is_static:
            self.torque_acc = self.torque_acc + torque

    def integrate(self, dt: float, gravity: float = -9.81):
        if self.is_static:
            return

        # Linear acceleration = F / m + g
        grav_force = Vec3(0, gravity * self.mass, 0)
        tot_force = self.force_acc + grav_force
        lin_acc = tot_force * self.inv_mass

        # Semi-implicit Euler
        self.velocity = (self.velocity + lin_acc * dt) * self.linear_damping
        self.position = self.position + self.velocity * dt

        # Angular acceleration = I^-1 * tau
        ang_acc = self.inv_inertia_tensor.mul_vec(self.torque_acc)
        self.angular_velocity = (self.angular_velocity + ang_acc * dt) * self.angular_damping
        # Update rotation (degrees)
        deg_step = self.angular_velocity * (dt * (180.0 / math.pi))
        self.rotation = self.rotation + deg_step

        # Ground plane collision at y = 0
        if self.position.y < 0.0:
            self.position.y = 0.0
            if self.velocity.y < 0.0:
                self.velocity.y = -self.velocity.y * self.restitution
                # Ground friction on horizontal velocity
                self.velocity.x *= 0.85
                self.velocity.z *= 0.85

        # Reset accumulators
        self.force_acc = Vec3(0, 0, 0)
        self.torque_acc = Vec3(0, 0, 0)
