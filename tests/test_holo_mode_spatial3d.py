#!/usr/bin/env python3
"""
Unit Tests for AdiOS Holo-Mode 3D Spatial Cyberspace Engine (tests/test_holo_mode_spatial3d.py)
Tests:
- Camera3D 6-DOF mathematics, vector normalization, and lerp updates.
- SpatialQuad3D geometric transformations, world vertices, and normals.
- SpatialRasterizer perspective projection, scanline rasterization, and raycast UV picking.
- HoloDesktop lifecycle, amphitheater layout, camera orbit/dolly/pan, and HUD rendering.
- MasterDesktop F10 hotkey, taskbar button, and shell command integration.

Strict Zero Emoji Policy Enforced.
"""

import unittest
import math

from graphics.spatial3d import Camera3D, SpatialQuad3D, SpatialRasterizer, Vector3
from desktop.holo_desktop import HoloDesktop
from desktop.master_desktop import MasterDesktop
from vm.vm import VM, RAM_SIZE_1024MB


class TestHoloModeSpatial3D(unittest.TestCase):

    def setUp(self):
        self.vm = VM(ram_size=RAM_SIZE_1024MB)
        self.desktop = MasterDesktop(vm=self.vm, ram_capacity_mb=1024)

    def test_01_camera3d_mathematics(self):
        cam = Camera3D(x=0.0, y=10.0, z=-500.0, fov=60.0)
        self.assertEqual(cam.pos.x, 0.0)
        self.assertEqual(cam.pos.y, 10.0)
        self.assertEqual(cam.pos.z, -500.0)

        fwd = cam.get_forward_vector()
        self.assertAlmostEqual(fwd.length(), 1.0, places=5)
        self.assertAlmostEqual(fwd.z, 1.0, places=5)

        cam.target_pos = Vector3(100.0, 50.0, -300.0)
        cam.target_yaw = 45.0
        cam.update(dt=0.1)
        self.assertGreater(cam.pos.x, 0.0)
        self.assertGreater(cam.yaw, 0.0)

    def test_02_spatial_quad_geometry(self):
        quad = SpatialQuad3D(
            win_id="test_win",
            center=Vector3(0.0, 0.0, 300.0),
            width=200.0,
            height=150.0,
            yaw=0.0
        )
        world_verts = quad.get_world_vertices()
        self.assertEqual(len(world_verts), 4)

        # Top-Left should be at X = -100, Y = -75, Z = 300
        tl = world_verts[0]
        self.assertAlmostEqual(tl.x, -100.0, places=2)
        self.assertAlmostEqual(tl.y, -75.0, places=2)
        self.assertAlmostEqual(tl.z, 300.0, places=2)

        # Bottom-Right should be at X = 100, Y = 75, Z = 300
        br = world_verts[2]
        self.assertAlmostEqual(br.x, 100.0, places=2)
        self.assertAlmostEqual(br.y, 75.0, places=2)
        self.assertAlmostEqual(br.z, 300.0, places=2)

        normal = quad.get_normal()
        self.assertAlmostEqual(normal.length(), 1.0, places=4)

    def test_03_spatial_rasterizer_projection_and_raycast(self):
        rasterizer = SpatialRasterizer(screen_w=1280, screen_h=720)
        cam = Camera3D(x=0.0, y=0.0, z=-400.0, fov=60.0)

        # Project a point directly in front of camera
        v = Vector3(0.0, 0.0, 0.0)
        sx, sy, cz = rasterizer.project_vertex(v, cam)
        self.assertAlmostEqual(sx, 640.0, places=1)
        self.assertAlmostEqual(sy, 360.0, places=1)
        self.assertAlmostEqual(cz, 400.0, places=1)

        # Raycast directly at screen center should hit quad center (u=0.5, v=0.5)
        quad = SpatialQuad3D(
            win_id="center_win",
            center=Vector3(0.0, 0.0, 0.0),
            width=300.0,
            height=200.0,
            yaw=0.0
        )
        uv = rasterizer.raycast_quad_uv(640, 360, quad, cam)
        self.assertIsNotNone(uv)
        self.assertAlmostEqual(uv[0], 0.5, places=2)
        self.assertAlmostEqual(uv[1], 0.5, places=2)

        # Raycast far away outside quad bounds should return None
        uv_miss = rasterizer.raycast_quad_uv(50, 50, quad, cam)
        self.assertIsNone(uv_miss)

    def test_04_holo_desktop_toggle_and_navigation(self):
        holo = HoloDesktop(width=1280, height=720)
        self.assertFalse(holo.is_active)

        # Toggle on
        is_act = holo.toggle(self.desktop)
        self.assertTrue(is_act)
        self.assertTrue(holo.is_active)

        # Step transition
        holo.step(dt=0.1)
        self.assertGreater(holo.transition_t, 0.0)

        # Camera navigation
        init_yaw = holo.camera.target_yaw
        holo.orbit(15.0, -10.0)
        self.assertEqual(holo.camera.target_yaw, init_yaw + 15.0)

        init_z = holo.camera.target_pos.z
        holo.dolly(50.0)
        self.assertEqual(holo.camera.target_pos.z, init_z + 50.0)

        # Reset camera
        holo.reset_camera()
        self.assertEqual(holo.camera.target_yaw, holo.default_yaw)
        self.assertEqual(holo.camera.target_pos.z, holo.default_pos.z)

    def test_05_holo_desktop_rendering_and_interaction(self):
        holo = HoloDesktop(width=1280, height=720)
        holo.toggle(self.desktop)
        holo.transition_t = 1.0  # Fully transitioned

        fb = bytearray(1280 * 720 * 4)
        holo.render(fb, self.desktop)

        # Verify framebuffer was populated (cyberspace grid + HUD pixels drawn)
        self.assertGreater(sum(fb[:1000]), 0)

        # Test mouse movement and hovering
        holo.handle_mouse_move(640, 360, self.desktop)

        # Test mouse up
        holo.handle_mouse_up(640, 360, button=1)

        # Test keyboard commands
        handled = holo.handle_key("w", self.desktop)
        self.assertTrue(handled)
        handled = holo.handle_key("r", self.desktop)
        self.assertTrue(handled)
        handled = holo.handle_key("ESCAPE", self.desktop)
        self.assertTrue(handled)
        self.assertFalse(holo.is_active)

    def test_06_master_desktop_f10_and_taskbar_integration(self):
        # Initial state: Holo-Mode is inactive
        self.assertFalse(self.desktop.holo_desktop.is_active)

        # Press F10 to toggle Holo-Mode
        self.desktop.handle_key("F10")
        self.assertTrue(self.desktop.holo_desktop.is_active)

        # Step frame updates Holo transition
        self.desktop.step_frame(640, 360)
        self.assertGreater(self.desktop.holo_desktop.transition_t, 0.0)

        # Press F10 again to exit
        self.desktop.handle_key("F10")
        self.assertFalse(self.desktop.holo_desktop.is_active)

        # Click HOLO F10 button on taskbar (width - 515 <= mx <= width - 435, my = 10)
        holo_btn_x = self.desktop.width - 480
        res = self.desktop.handle_mouse_down(holo_btn_x, 10)
        self.assertEqual(res, ("holo_toggle", True))
        self.assertTrue(self.desktop.holo_desktop.is_active)

        # Click HOLO F10 button again to toggle off
        res = self.desktop.handle_mouse_down(holo_btn_x, 10)
        self.assertEqual(res, ("holo_toggle", False))
        self.assertFalse(self.desktop.holo_desktop.is_active)

        # Launch via shell command: "holo"
        self.desktop.launch_or_focus("shell")
        self.desktop.shell_input = "holo"
        self.desktop.handle_key("\n")
        self.assertTrue(self.desktop.holo_desktop.is_active)


if __name__ == "__main__":
    unittest.main()
