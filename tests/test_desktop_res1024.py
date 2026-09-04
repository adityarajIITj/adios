#!/usr/bin/env python3
"""
AdiOS Test Suite: High-Resolution Workstation (1024x768 XGA) & Window Manager Controls
Verifies 1024x768 desktop compositing, window snapping, minimize/maximize, and interactive apps.
STRICT ZERO EMOJI POLICY.
"""

import unittest
from desktop.master_desktop import MasterDesktop, DEFAULT_WIDTH, DEFAULT_HEIGHT, COLOR_DESKTOP_BG, COLOR_START_PILL
from desktop.window_manager import WindowManager, Window, SNAP_MAXIMIZE, SNAP_LEFT_HALF, SNAP_RIGHT_HALF
from vm.vm import VM

class TestDesktopRes1024(unittest.TestCase):
    def setUp(self):
        self.vm = VM()
        self.desktop = MasterDesktop(self.vm, width=1024, height=768)
        self.fb = bytearray(1024 * 768 * 4)

    def test_01_workstation_resolution_init(self):
        """Verify 1024x768 workstation dimensions, window count, and font glyphs."""
        self.assertEqual(self.desktop.width, 1024)
        self.assertEqual(self.desktop.height, 768)
        self.assertEqual(len(self.desktop.wm.windows), 9)
        self.assertFalse(self.desktop.start_menu_open)
        self.assertEqual(len(self.desktop.font), 95)

    def test_02_workstation_framebuffer_render(self):
        """Verify 1024x768 desktop wallpaper and taskbar rendering."""
        self.desktop.render(self.fb)

        # Check background pixel at (10, 500)
        bg_off = (500 * 1024 + 10) * 4
        expected_bg = bytes([COLOR_DESKTOP_BG & 0xFF, (COLOR_DESKTOP_BG >> 8) & 0xFF, (COLOR_DESKTOP_BG >> 16) & 0xFF, 0])
        self.assertEqual(self.fb[bg_off : bg_off + 4], expected_bg)

        # Check Start Pill on Taskbar at (10, 4)
        pill_off = (4 * 1024 + 10) * 4
        expected_pill = bytes([COLOR_START_PILL & 0xFF, (COLOR_START_PILL >> 8) & 0xFF, (COLOR_START_PILL >> 16) & 0xFF, 0])
        self.assertEqual(self.fb[pill_off : pill_off + 4], expected_pill)

    def test_03_titlebar_controls_maximize_and_restore(self):
        """Verify [^] button maximizes window to 1024x744 and restores floating rect."""
        win = self.desktop.win_browser
        orig_w, orig_h = win.w, win.h
        self.assertFalse(win.maximized)

        # Click maximize button
        # btn_x = win.x + win.w - 36, btn_y = win.y + 3
        max_btn_x = win.x + win.w - 30
        max_btn_y = win.y + 8
        res = self.desktop.handle_mouse_down(max_btn_x, max_btn_y)
        self.assertEqual(res[0], "maximize")
        self.assertTrue(win.maximized)
        self.assertEqual(win.w, 1024)
        self.assertEqual(win.h, 744)

        # Click restore button
        max_btn_x = win.x + win.w - 30
        max_btn_y = win.y + 8
        res = self.desktop.handle_mouse_down(max_btn_x, max_btn_y)
        self.assertEqual(res[0], "maximize")
        self.assertFalse(win.maximized)
        self.assertEqual(win.w, orig_w)
        self.assertEqual(win.h, orig_h)

    def test_04_titlebar_controls_minimize_and_restore(self):
        """Verify [_] button minimizes window and taskbar pill restores it."""
        win = self.desktop.win_browser
        self.assertTrue(win.visible)
        self.assertFalse(win.minimized)

        # Click minimize button at win.x + win.w - 54
        min_btn_x = win.x + win.w - 48
        min_btn_y = win.y + 8
        res = self.desktop.handle_mouse_down(min_btn_x, min_btn_y)
        self.assertEqual(res[0], "minimize")
        self.assertTrue(win.minimized)
        self.assertFalse(win.visible)

        # Restore via Start Menu or launch_or_focus
        self.desktop.launch_or_focus("browser")
        self.assertFalse(win.minimized)
        self.assertTrue(win.visible)
        self.assertTrue(win.active)

    def test_05_window_snapping(self):
        """Verify window snapping to top (maximize) and left/right half tiles."""
        wm = WindowManager(width=1024, height=768)
        win = Window("test", "Test Window", 100, 100, 400, 300)
        wm.add_window(win)

        # Snap to left half (0, 24, 512, 744)
        win.snap_tile(SNAP_LEFT_HALF, 1024, 768)
        self.assertEqual(win.x, 0)
        self.assertEqual(win.y, 24)
        self.assertEqual(win.w, 512)
        self.assertEqual(win.h, 744)

        # Snap to right half (512, 24, 512, 744)
        win.snap_tile(SNAP_RIGHT_HALF, 1024, 768)
        self.assertEqual(win.x, 512)
        self.assertEqual(win.y, 24)
        self.assertEqual(win.w, 512)
        self.assertEqual(win.h, 744)

    def test_06_interactive_browser_links(self):
        """Verify Browser URL navigation and hyperlink clicking in 1024x768."""
        self.assertEqual(self.desktop.browser_url, "about:adios")
        # Click System Specs link button at rel_x = 50, rel_y = 125
        cx, cy, _, _ = self.desktop.win_browser.client_rect
        self.desktop.handle_mouse_down(cx + 50, cy + 125)
        self.assertEqual(self.desktop.browser_url, "about:system")

        # Click Home button at rel_x = 50, rel_y = 155
        self.desktop.handle_mouse_down(cx + 50, cy + 155)
        self.assertEqual(self.desktop.browser_url, "about:adios")

    def test_07_interactive_sql_explain_plan(self):
        """Verify SQL EXPLAIN PLAN toggle in SovereignSQL terminal."""
        self.assertFalse(self.desktop.sql_show_plan)
        cx, cy, _, _ = self.desktop.win_sql.client_rect
        # Click EXPLAIN PLAN button at rel_x = 130, rel_y = 10
        self.desktop.handle_mouse_down(cx + 130, cy + 10)
        self.assertTrue(self.desktop.sql_show_plan)
        self.assertIn("query_planner", self.desktop.sql_status)

    def test_08_interactive_calculator_sqrt_pow(self):
        """Verify scientific calculator operations: SQRT and POW."""
        # Enter "16", press SQRT -> 4
        self.desktop.calc_display = "16"
        self.desktop._handle_calc_key("SQRT")
        self.assertEqual(self.desktop.calc_display, "4")

        # 2 POW 4 = 16
        self.desktop.calc_display = "2"
        self.desktop._handle_calc_key("POW")
        self.desktop.calc_display = "4"
        self.desktop._handle_calc_key("=")
        self.assertEqual(self.desktop.calc_display, "16")

if __name__ == "__main__":
    unittest.main()
