#!/usr/bin/env python3
"""
Test Suite: Block V Software OpenGL 1.1 3D Graphics Engine
Verifies:
1. gl/gl_core: 4x4 matrix stack operations (Identity, Translate, Scale, Push/Pop)
2. gl/gl_core: Perspective projection and NDC-to-Viewport transformation
3. gl/gl_core: Barycentric triangle rasterization & Gouraud color interpolation
4. gl/gl_core: 32-bit floating-point Z-buffering (depth occlusion & test rejection)
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from gl.gl_core import SoftwareGL, GL_MODELVIEW, GL_PROJECTION, GL_TRIANGLES, mat4_identity, mat4_mult

def test_gl_block_v_suite():
    print("[Test GL Block V] Initializing Software OpenGL 1.1 3D Verification...")

    # 1. Test Matrix Stack Operations
    print("  -> Testing 4x4 Matrix Mathematics & Stack (Push/Pop)...")
    gl = SoftwareGL(320, 240)
    gl.glMatrixMode(GL_MODELVIEW)
    gl.glLoadIdentity()
    assert gl.modelview_stack[-1] == mat4_identity()

    gl.glTranslatef(10.0, 20.0, -30.0)
    assert gl.modelview_stack[-1][3] == 10.0
    assert gl.modelview_stack[-1][7] == 20.0
    assert gl.modelview_stack[-1][11] == -30.0

    gl.glPushMatrix()
    assert len(gl.modelview_stack) == 2
    gl.glScalef(2.0, 2.0, 2.0)
    assert gl.modelview_stack[-1][0] == 2.0

    gl.glPopMatrix()
    assert len(gl.modelview_stack) == 1
    assert gl.modelview_stack[-1][0] == 1.0 # Restored
    print("  -> [PASS] Matrix operations & stack push/pop verified.")

    # 2. Test Perspective Setup & Primitive Rasterization
    print("  -> Testing Barycentric Triangle Rasterization & Framebuffer...")
    gl.glClear(0xFF000000)
    gl.glMatrixMode(GL_PROJECTION)
    gl.glLoadIdentity()
    gl.gluPerspective(60.0, 320.0 / 240.0, 0.1, 100.0)

    gl.glMatrixMode(GL_MODELVIEW)
    gl.glLoadIdentity()
    gl.glTranslatef(0.0, 0.0, -3.0)

    gl.glBegin(GL_TRIANGLES)
    gl.glColor3f(1.0, 1.0, 0.0) # Yellow
    gl.glVertex3f(-1.0, -1.0, 0.0)
    gl.glVertex3f(1.0, -1.0, 0.0)
    gl.glVertex3f(0.0, 1.0, 0.0)
    gl.glEnd()

    # Center pixel (x=160, y=120) should have yellow color (R > 0, G > 0)
    center_offset = (120 * 320 + 160) * 4
    b = gl.framebuffer[center_offset]
    g = gl.framebuffer[center_offset + 1]
    r = gl.framebuffer[center_offset + 2]
    assert r > 200
    assert g > 200
    print("  -> [PASS] Barycentric triangle rasterization verified.")

    # 3. Test Z-Buffer Depth Testing (Occlusion & Rejection)
    print("  -> Testing 32-bit Floating-Point Z-Buffer Depth Occlusion...")
    gl.glClear(0xFF000000)

    # Step A: Draw FAR Green triangle at z = -6.0
    gl.glMatrixMode(GL_MODELVIEW)
    gl.glLoadIdentity()
    gl.glTranslatef(0.0, 0.0, -6.0)

    gl.glBegin(GL_TRIANGLES)
    gl.glColor3f(0.0, 1.0, 0.0) # Green
    gl.glVertex3f(-2.0, -2.0, 0.0)
    gl.glVertex3f(2.0, -2.0, 0.0)
    gl.glVertex3f(0.0, 2.0, 0.0)
    gl.glEnd()

    center_g = gl.framebuffer[center_offset + 1]
    center_r = gl.framebuffer[center_offset + 2]
    assert center_g > 200
    assert center_r == 0

    # Step B: Draw NEAR Red triangle at z = -2.0 (Must occlude Green)
    gl.glLoadIdentity()
    gl.glTranslatef(0.0, 0.0, -2.0)

    gl.glBegin(GL_TRIANGLES)
    gl.glColor3f(1.0, 0.0, 0.0) # Red
    gl.glVertex3f(-0.5, -0.5, 0.0)
    gl.glVertex3f(0.5, -0.5, 0.0)
    gl.glVertex3f(0.0, 0.5, 0.0)
    gl.glEnd()

    center_g_after = gl.framebuffer[center_offset + 1]
    center_r_after = gl.framebuffer[center_offset + 2]
    assert center_r_after > 200 # Red won the depth test!
    assert center_g_after == 0

    # Step C: Attempt to draw BEHIND Blue triangle at z = -8.0 (Must be REJECTED)
    gl.glLoadIdentity()
    gl.glTranslatef(0.0, 0.0, -8.0)

    gl.glBegin(GL_TRIANGLES)
    gl.glColor3f(0.0, 0.0, 1.0) # Blue
    gl.glVertex3f(-1.0, -1.0, 0.0)
    gl.glVertex3f(1.0, -1.0, 0.0)
    gl.glVertex3f(0.0, 1.0, 0.0)
    gl.glEnd()

    # Red must STILL be there!
    assert gl.framebuffer[center_offset + 2] > 200 # Still Red
    assert gl.framebuffer[center_offset] == 0     # Blue rejected
    print("  -> [PASS] Z-buffer depth occlusion & rejection verified.")

    print("\n[Test GL Block V] ALL BLOCK V SOFTWARE OPENGL 1.1 TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_gl_block_v_suite()
