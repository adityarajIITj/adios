#!/usr/bin/env python3
"""
Test Suite: Block W Cyberpunk Virtual Environment & Physics Spatial Engine
Verifies:
1. spatial/physics3d: 3D vector mathematics (dot, cross, norm, mag)
2. spatial/physics3d: Rigid body dynamics & gravity symplectic Euler integration
3. spatial/physics3d: Sphere-sphere impulse collision response & restitution bounce
4. spatial/physics3d: AABB intersection & Octree hierarchical spatial partitioning
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from spatial.physics3d import Vec3, RigidBody3D, resolve_sphere_collision, AABB, OctreeNode

def test_spatial_block_w_suite():
    print("[Test Spatial Block W] Initializing 3D Physics & Spatial Partitioning Verification...")

    # 1. Test 3D Vector Math
    print("  -> Testing 3D Vector Mathematics...")
    v1 = Vec3(1, 2, 3)
    v2 = Vec3(4, 5, 6)
    v_add = v1 + v2
    assert (v_add.x, v_add.y, v_add.z) == (5, 7, 9)

    dot_p = v1.dot(v2) # 1*4 + 2*5 + 3*6 = 32
    assert dot_p == 32.0

    cross_p = v1.cross(v2)
    # (2*6 - 3*5, 3*4 - 1*6, 1*5 - 2*4) = (-3, 6, -3)
    assert (cross_p.x, cross_p.y, cross_p.z) == (-3.0, 6.0, -3.0)

    v_norm = Vec3(0, 3, 4).normalized()
    assert abs(v_norm.length() - 1.0) < 0.0001
    assert abs(v_norm.y - 0.6) < 0.0001
    assert abs(v_norm.z - 0.8) < 0.0001
    print("  -> [PASS] 3D vector operations verified.")

    # 2. Test Rigid Body Symplectic Integration
    print("  -> Testing Rigid Body Symplectic Euler Integration...")
    body = RigidBody3D(Vec3(0, 100, 0), mass=2.0)
    # 1 second of gravity (g = [0, -9.81, 0])
    body.integrate(dt=1.0)
    assert abs(body.vel.y - (-9.81)) < 0.001
    assert abs(body.pos.y - (100.0 - 9.81)) < 0.001
    print("  -> [PASS] Symplectic integration verified.")

    # 3. Test Sphere-Sphere Collision & Restitution
    print("  -> Testing Sphere Collision Impulse Resolution...")
    b1 = RigidBody3D(Vec3(-0.5, 0, 0), mass=1.0, radius=1.0)
    b2 = RigidBody3D(Vec3(0.5, 0, 0), mass=1.0, radius=1.0)
    b1.vel = Vec3(10.0, 0, 0)  # Moving right
    b2.vel = Vec3(-10.0, 0, 0) # Moving left
    b1.restitution = 1.0       # Perfectly elastic
    b2.restitution = 1.0

    collided = resolve_sphere_collision(b1, b2)
    assert collided is True
    # In elastic collision of equal masses, velocities swap
    assert b1.vel.x < 0.0 # Bounced backwards to the left
    assert b2.vel.x > 0.0 # Bounced backwards to the right
    print("  -> [PASS] Elastic impulse collision response verified.")

    # 4. Test Octree Spatial Partitioning
    print("  -> Testing Octree 8-Way Hierarchical Spatial Partitioning...")
    world_bounds = AABB(Vec3(-100, -100, -100), Vec3(100, 100, 100))
    octree = OctreeNode(world_bounds, capacity=2)

    # Insert 5 bodies scattered across space
    b_a = RigidBody3D(Vec3(10, 10, 10))
    b_b = RigidBody3D(Vec3(12, 11, 10))
    b_c = RigidBody3D(Vec3(15, 14, 12))
    b_far = RigidBody3D(Vec3(-80, -80, -80))
    b_other = RigidBody3D(Vec3(50, -50, 20))

    for b in [b_a, b_b, b_c, b_far, b_other]:
        assert octree.insert(b) is True

    # Subdivision must have occurred because capacity=2 was exceeded
    assert octree.children is not None

    # Query local neighborhood around (10, 10, 10)
    query_box = AABB(Vec3(5, 5, 5), Vec3(20, 20, 20))
    found = octree.query_range(query_box)
    assert len(found) == 3
    assert b_a in found and b_b in found and b_c in found
    assert b_far not in found
    assert b_other not in found
    print("  -> [PASS] Octree insertion, subdivision, and range queries verified.")

    print("\n[Test Spatial Block W] ALL BLOCK W PHYSICS & SPATIAL TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_spatial_block_w_suite()
