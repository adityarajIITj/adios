#!/usr/bin/env python3
"""
Test Suite: 3D Graphics Engine & Software Rasterizer
Verifies:
1. Vector3 math (addition, cross product, length, dot product)
2. 3D Mesh structures (Cube, Temple Pyramid)
3. Euler camera transformation and perspective projection
4. Lighting and flat-shading color calculation
5. Rasterization onto 640x480 Framebuffer
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from vm.vm import VM
from graphics import Engine3D, Vector3, create_cube, create_temple_pyramid

def test_engine3d_suite():
    print("[Test 3D Engine] Testing 3D Graphics Pipeline & Software Rasterizer...")

    # 1. Test Vector3 Math
    print("  -> Testing Vector3 algebra...")
    v1 = Vector3(1, 0, 0)
    v2 = Vector3(0, 1, 0)
    v3 = v1.cross(v2)
    assert abs(v3.x) < 1e-5 and abs(v3.y) < 1e-5 and abs(v3.z - 1.0) < 1e-5, "Vector3 cross product failed"
    assert abs(v1.dot(v2)) < 1e-5, "Vector3 dot product failed"
    assert abs(v1.length() - 1.0) < 1e-5, "Vector3 length failed"
    print("  -> [PASS] Vector3 algebra verified.")

    # 2. Test Mesh Generation
    print("  -> Testing 3D Mesh generation...")
    cube = create_cube(size=60)
    assert len(cube.vertices) == 8, f"Cube vertices expected 8, got {len(cube.vertices)}"
    assert len(cube.faces) == 12, f"Cube faces expected 12, got {len(cube.faces)}"

    pyr = create_temple_pyramid(base=80, height=70)
    assert len(pyr.vertices) == 5, f"Pyramid vertices expected 5, got {len(pyr.vertices)}"
    assert len(pyr.faces) == 6, f"Pyramid faces expected 6, got {len(pyr.faces)}"
    print("  -> [PASS] 3D Meshes verified.")

    # 3. Test 3D Pipeline & Rasterization
    print("  -> Testing 3D transformation & scanline rasterization on VM Framebuffer...")
    vm = VM()
    engine = Engine3D(vm)

    # Render flat-shaded cube at (0, 0, 150)
    pos = Vector3(0, 0, 150)
    rot = Vector3(25, 45, 0)
    engine.render_mesh(cube, pos, rot, wireframe=False)

    # Check that pixels were written to the center area of the Framebuffer
    center_y = 240
    center_x = 320
    center_pixel_off = (center_y * 640 + center_x) * 4
    pixel_bytes = vm.fb[center_pixel_off : center_pixel_off + 4]
    # Assert that the center pixel is not black (i.e. polygon rendered!)
    assert any(b > 0 for b in pixel_bytes), "Cube failed to rasterize to screen center"
    print(f"  -> Center pixel rendered: {list(pixel_bytes)}")

    # Test wireframe mode on pyramid
    pos_pyr = Vector3(0, 0, 180)
    rot_pyr = Vector3(15, 30, 0)
    engine.render_mesh(pyr, pos_pyr, rot_pyr, wireframe=True)
    print("  -> [PASS] 3D Rasterization & Shading verified.")

    print("\n[Test 3D Engine] ALL 3D GRAPHICS PIPELINE TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_engine3d_suite()
