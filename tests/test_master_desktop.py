#!/usr/bin/env python3
"""
AdiOS Test Suite: Unified Sovereign Master Desktop & 8 Subsystem Applications
Verifies complete bare-metal compositor, Start Menu, and 8 integrated apps.
STRICT ZERO EMOJI POLICY.
"""

import unittest
from desktop.master_desktop import MasterDesktop, WIDTH, HEIGHT, COLOR_DESKTOP_BG, COLOR_START_PILL
from vm.vm import VM

class TestMasterDesktop(unittest.TestCase):
    def setUp(self):
        self.vm = VM()
        self.desktop = MasterDesktop(self.vm)
        self.fb = bytearray(WIDTH * HEIGHT * 4)

    def test_01_initialization(self):
        """Verify MasterDesktop initializes all 9 windows and default state."""
        self.assertEqual(len(self.desktop.wm.windows), 9)
        win_ids = [w.win_id for w in self.desktop.wm.windows]
        expected = ["browser", "sql", "lisp", "gl", "explorer", "netmon", "shell", "paint", "games"]
        for exp in expected:
            self.assertIn(exp, win_ids)

        self.assertFalse(self.desktop.start_menu_open)
        self.assertIsNotNone(self.desktop.font)
        self.assertEqual(len(self.desktop.font), 95)

    def test_02_desktop_rendering(self):
        """Verify framebuffer rendering of desktop wallpaper, taskbar, and windows."""
        self.desktop.render(self.fb)

        # Check background pixel at (1, 300)
        bg_off = (300 * WIDTH + 1) * 4
        expected_bg = bytes([COLOR_DESKTOP_BG & 0xFF, (COLOR_DESKTOP_BG >> 8) & 0xFF, (COLOR_DESKTOP_BG >> 16) & 0xFF, 0])
        self.assertEqual(self.fb[bg_off : bg_off + 4], expected_bg)

        # Check Start Pill on Taskbar at (6, 4)
        pill_off = (4 * WIDTH + 6) * 4
        expected_pill = bytes([COLOR_START_PILL & 0xFF, (COLOR_START_PILL >> 8) & 0xFF, (COLOR_START_PILL >> 16) & 0xFF, 0])
        self.assertEqual(self.fb[pill_off : pill_off + 4], expected_pill)

    def test_03_start_menu_toggle_and_launch(self):
        """Verify Start Menu opens on click, renders items, and launches an app."""
        # Click Start Pill at (30, 10)
        res = self.desktop.handle_mouse_down(30, 10)
        self.assertEqual(res, ("start_toggle", None))
        self.assertTrue(self.desktop.start_menu_open)

        # Render menu
        self.desktop.render(self.fb)

        # Click item 7 (POSIX Sovereign Shell) at (50, 160)
        # my = 24 + 28 + 6 * 18 = 160
        res = self.desktop.handle_mouse_down(50, 160)
        self.assertEqual(res, ("menu_select", "shell"))
        self.assertFalse(self.desktop.start_menu_open)
        self.assertTrue(self.desktop.win_shell.visible)
        self.assertTrue(self.desktop.win_shell.active)

    def test_04_browser_app(self):
        """Verify Sovereign Web Browser DOM tree and navigation."""
        self.assertIsNotNone(self.desktop.browser_dom)
        self.assertIsNotNone(self.desktop.browser_layout)
        initial_url = self.desktop.browser_url

        # Click GO button
        cx, cy, cw, _ = self.desktop.win_browser.client_rect
        self.desktop.win_browser.on_click_content(self.desktop.win_browser, cw - 20, 10)
        self.assertNotEqual(self.desktop.browser_url, initial_url)

    def test_05_sql_terminal(self):
        """Verify SovereignSQL Terminal query execution."""
        initial_rows = len(self.desktop.sql_results.get("rows", []))
        self.assertGreater(initial_rows, 0)

        # Click RUN button
        _, _, cw, _ = self.desktop.win_sql.client_rect
        self.desktop.win_sql.on_click_content(self.desktop.win_sql, cw - 20, 10)
        self.assertIsNotNone(self.desktop.sql_results)

    def test_06_lisp_vm(self):
        """Verify Lisp Bytecode REPL evaluates S-Expressions."""
        self.assertEqual(self.desktop.lisp_last_val, 52)

        # Evaluate (+ 2 3)
        ch = self.desktop.win_lisp.h - 22
        self.desktop.win_lisp.on_click_content(self.desktop.win_lisp, 30, ch - 34)
        self.assertEqual(self.desktop.lisp_last_val, 5)

    def test_07_opengl_3d_viewport(self):
        """Verify OpenGL 3D viewport rotation and model switching."""
        self.assertEqual(self.desktop.mesh_name, "CUBE")
        ch = self.desktop.win_gl.h - 22

        # Click MODEL button at (30, ch - 14)
        self.desktop.win_gl.on_click_content(self.desktop.win_gl, 30, ch - 14)
        self.assertEqual(self.desktop.mesh_name, "PYRAMID")

        # Click TOGGLE button at (100, ch - 14)
        self.desktop.win_gl.on_click_content(self.desktop.win_gl, 100, ch - 14)
        self.assertTrue(self.desktop.wireframe_3d)

        # Step frame rotates
        orig_rot = self.desktop.rot_3d.y
        self.desktop.step_frame(0, 0)
        self.assertNotEqual(self.desktop.rot_3d.y, orig_rot)

    def test_08_file_explorer(self):
        """Verify Sovereign File Explorer drive switching."""
        self.assertEqual(self.desktop.explorer_drive, "Ext2")
        self.desktop.win_explorer.on_click_content(self.desktop.win_explorer, 100, 10)
        self.assertEqual(self.desktop.explorer_drive, "FAT32")

    def test_09_network_and_crypto(self):
        """Verify Network & Crypto Monitor TLS 1.3 handshake."""
        orig_hash = self.desktop.sha256_val
        ch = self.desktop.win_netmon.h - 22
        self.desktop.win_netmon.on_click_content(self.desktop.win_netmon, 50, ch - 14)
        self.assertIn("TLS 1.3 Handshake Verified", self.desktop.status_message)
        self.assertNotEqual(self.desktop.sha256_val, orig_hash)

    def test_10_posix_shell(self):
        """Verify POSIX Shell command execution."""
        ch = self.desktop.win_shell.h - 22
        self.desktop.win_shell.on_click_content(self.desktop.win_shell, 90, ch - 30) # uname -a
        self.assertTrue(any("AdiOS 1.0.0-sovereign" in line for line in self.desktop.shell_history))

    def test_11_paint_and_calc(self):
        """Verify Paint canvas stroke and Calculator arithmetic (7 + 5 = 12)."""
        # Paint stroke at (50, 40)
        self.desktop.win_paint.on_click_content(self.desktop.win_paint, 50, 40)
        self.assertEqual(len(self.desktop.paint_strokes), 1)

        # Calculator: 7 + 5 = 12
        # '7' is at (6, 34) relative to cal_y=92 -> rel_y = 126, rel_x = 20
        self.desktop.win_paint.on_click_content(self.desktop.win_paint, 20, 130)
        self.assertEqual(self.desktop.calc_display, "7")

        # '+' is at (3 * 47 = 141 + 6 = 147, 34 + 3 * 17 = 85 + 92 = 177)
        self.desktop._handle_calc_key("+")
        self.desktop._handle_calc_key("5")
        self.desktop._handle_calc_key("=")
        self.assertEqual(self.desktop.calc_display, "12")

    def test_12_games_arcade(self):
        """Verify Sovereign 3D Games Arcade window, game switching, and controls."""
        # 1. Launch via top taskbar pill at (100, 10)
        res = self.desktop.handle_mouse_down(100, 10)
        self.assertEqual(res, ("menu_select", "games"))
        self.assertTrue(self.desktop.win_games.visible)
        self.assertTrue(self.desktop.win_games.active)

        # 2. Render in Castle 3D mode
        self.assertEqual(self.desktop.game_mode, "castle")
        self.desktop.render(self.fb)

        # 3. Test Castle controls (W to move, D to turn)
        orig_x, orig_y = self.desktop.castle_pos_x, self.desktop.castle_pos_y
        self.desktop.handle_key("w")
        self.assertNotEqual((self.desktop.castle_pos_x, self.desktop.castle_pos_y), (orig_x, orig_y))
        orig_dir_x = self.desktop.castle_dir_x
        self.desktop.handle_key("d")
        self.assertNotEqual(self.desktop.castle_dir_x, orig_dir_x)

        # 4. Switch to StarFlight 3D mode via key '2'
        self.desktop.handle_key("2")
        self.assertEqual(self.desktop.game_mode, "flight")
        self.desktop.render(self.fb)

        # 5. Test StarFlight controls (W to pitch, A to bank)
        orig_bank = self.desktop.flight_bank
        self.desktop.handle_key("a")
        self.assertLess(self.desktop.flight_bank, orig_bank)

        # 6. Test frame step
        orig_score = self.desktop.flight_score
        self.desktop.step_frame(0, 0)
        self.assertGreaterEqual(self.desktop.flight_score, orig_score)

        # 7. Test switch back to Castle via toolbar click
        self.desktop.win_games.on_click_content(self.desktop.win_games, 50, 10)
        self.assertEqual(self.desktop.game_mode, "castle")

if __name__ == "__main__":
    unittest.main()
