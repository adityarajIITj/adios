#!/usr/bin/env python3
"""
Automated Test Suite for AdiOS v3.0 Beta Applications & Minimalist Theme Engine
Tests:
- ThemeManager: Palette integrity, cycling, minimalist color constraints
- CodeStudio: Editor buffer, execution runner, online pip package manager
- FileExplorer: Directory scanning, places navigation, file type badges
- Scene3DStudio: 3D geometric models, rotation matrices, scissor clipping
- MasterDesktop Integration: Window management, taskbar theme toggling, icon launches

Strict Zero Emoji Policy.
"""

import unittest
import time
import os
from desktop.theme import ThemeManager, THEMES, PALETTE_NORDIC_SLATE, PALETTE_MONOCHROME, PALETTE_ARCTIC, PALETTE_EMERALD
from desktop.code_studio import CodeStudio, TEMPLATES, TAB_EDITOR, TAB_OUTPUT, TAB_PACKAGES
from desktop.file_explorer import FileExplorer, FileEntry
from desktop.scene3d_studio import Scene3DStudio, create_octahedron, create_hex_prism, create_monolith
from desktop.master_desktop import MasterDesktop

class TestV3ThemeEngine(unittest.TestCase):
    def test_palettes_exist(self):
        self.assertIn("nordic", THEMES)
        self.assertIn("mono", THEMES)
        self.assertIn("arctic", THEMES)
        self.assertIn("emerald", THEMES)

    def test_theme_manager_cycling(self):
        tm = ThemeManager.get_instance()
        tm.set_theme("nordic")
        self.assertEqual(tm.current_key, "nordic")
        self.assertEqual(tm.palette.name, "Nordic Slate")

        next_key = tm.next_theme()
        self.assertEqual(next_key, "mono")
        self.assertEqual(tm.palette.name, "Monochrome Silver")

        tm.next_theme() # arctic
        self.assertEqual(tm.current_key, "arctic")

        tm.next_theme() # emerald
        self.assertEqual(tm.current_key, "emerald")

        tm.next_theme() # back to nordic
        self.assertEqual(tm.current_key, "nordic")

    def test_palette_color_integrity(self):
        for key, pal in THEMES.items():
            self.assertIsInstance(pal.desktop_bg, int)
            self.assertIsInstance(pal.win_bg, int)
            self.assertIsInstance(pal.win_border, int)
            self.assertIsInstance(pal.text_primary, int)
            self.assertIsInstance(pal.accent_primary, int)

class TestV3CodeStudio(unittest.TestCase):
    def setUp(self):
        self.studio = CodeStudio()

    def test_initial_state(self):
        self.assertEqual(self.studio.active_tab, TAB_EDITOR)
        self.assertTrue(len(self.studio.lines) > 0)
        self.assertIn("project_point", "\n".join(self.studio.lines))

    def test_template_loading(self):
        self.studio.load_template("benchmark")
        self.assertIn("sieve", "\n".join(self.studio.lines))
        self.assertEqual(self.studio.active_tab, TAB_EDITOR)

        self.studio.load_template("webrequest")
        self.assertIn("urllib.request", "\n".join(self.studio.lines))

    def test_code_execution_runner(self):
        self.studio.lines = [
            "total = sum(range(10))",
            "print(f'Sum is: {total}')"
        ]
        self.studio.run_code()
        time.sleep(0.4)
        self.assertEqual(self.studio.active_tab, TAB_OUTPUT)
        output_text = "\n".join(self.studio.output_logs)
        self.assertIn("Sum is: 45", output_text)
        self.assertIn("Finished", output_text)

    def test_pip_package_runner_scaffold(self):
        self.studio.install_package("--help")
        self.assertEqual(self.studio.active_tab, TAB_PACKAGES)
        time.sleep(0.8)
        logs = "\n".join(self.studio.pkg_logs)
        self.assertIn("pip", logs.lower())

class TestV3FileExplorer(unittest.TestCase):
    def setUp(self):
        self.explorer = FileExplorer()

    def test_directory_scanning(self):
        self.assertTrue(len(self.explorer.entries) > 0)
        has_dirs = any(e.is_dir for e in self.explorer.entries)
        self.assertTrue(has_dirs)

    def test_navigation(self):
        orig_dir = self.explorer.current_dir
        self.explorer.navigate_to("scripts")
        self.assertTrue(self.explorer.current_dir.endswith("scripts"))
        self.explorer.navigate_up()
        self.assertEqual(self.explorer.current_dir, orig_dir)

    def test_file_entry_properties(self):
        entry_dir = FileEntry("test_dir", "/tmp/test_dir", True, 4096, time.time())
        self.assertEqual(entry_dir.formatted_size, "<DIR>")
        self.assertEqual(entry_dir.file_type, "Folder")

        entry_file = FileEntry("script.py", "/tmp/script.py", False, 2048, time.time())
        self.assertEqual(entry_file.formatted_size, "2.0 KB")
        self.assertEqual(entry_file.file_type, "Python Script")

    def test_open_file_callback(self):
        opened_paths = []
        explorer = FileExplorer(on_open_file=lambda p: opened_paths.append(p))
        # Find first non-directory file
        file_idx = next(i for i, e in enumerate(explorer.entries) if not e.is_dir)
        # Scroll so file is top visible item
        explorer.scroll_idx = file_idx
        explorer.selected_idx = file_idx
        # Click first visible row (rel_y = 60, rel_x = 200)
        explorer._handle_click(explorer, 200, 60)
        self.assertTrue(len(opened_paths) > 0)
        self.assertEqual(opened_paths[0], explorer.entries[file_idx].path)

class TestV3Scene3DStudio(unittest.TestCase):
    def setUp(self):
        self.studio = Scene3DStudio()

    def test_mesh_generation(self):
        octa = create_octahedron()
        self.assertEqual(len(octa.vertices), 6)
        self.assertEqual(len(octa.faces), 8)

        prism = create_hex_prism()
        self.assertEqual(len(prism.vertices), 14)
        self.assertEqual(len(prism.faces), 24)

        monolith = create_monolith()
        self.assertEqual(len(monolith.vertices), 8)
        self.assertEqual(len(monolith.faces), 12)

    def test_viewport_rendering_with_clipping(self):
        fb = bytearray(1280 * 720 * 4)
        self.studio.current_model_key = "octahedron"
        self.studio.on_draw_content(self.studio, fb, {})
        # Verify rendered non-zero pixel data in window region
        cx, cy, cw, ch = self.studio.client_rect
        sample_off = ((cy + ch // 2) * 1280 + (cx + cw // 2)) * 4
        self.assertTrue(any(fb[sample_off:sample_off+4]))

class TestV3MasterDesktopIntegration(unittest.TestCase):
    def setUp(self):
        self.desktop = MasterDesktop()

    def test_v3_apps_registered(self):
        self.assertIsNotNone(self.desktop.win_studio)
        self.assertIsNotNone(self.desktop.win_file_explorer)
        self.assertIsNotNone(self.desktop.win_scene3d)

    def test_app_launch_or_focus(self):
        self.desktop.launch_or_focus("studio")
        self.assertTrue(self.desktop.win_studio.visible)
        self.assertFalse(self.desktop.win_studio.minimized)

        self.desktop.launch_or_focus("files")
        self.assertTrue(self.desktop.win_file_explorer.visible)

        self.desktop.launch_or_focus("scene3d")
        self.assertTrue(self.desktop.win_scene3d.visible)

    def test_taskbar_theme_toggle_click(self):
        init_theme = ThemeManager.get_instance().current_key
        # Taskbar theme button @ (width - 300, 10)
        res = self.desktop.handle_mouse_down(self.desktop.width - 250, 10)
        self.assertIsNotNone(res)
        self.assertEqual(res[0], "theme_change")
        new_theme = ThemeManager.get_instance().current_key
        self.assertNotEqual(init_theme, new_theme)

    def test_desktop_rendering_cycle(self):
        fb = bytearray(1280 * 720 * 4)
        self.desktop.render(fb)
        self.assertEqual(len(fb), 1280 * 720 * 4)

if __name__ == "__main__":
    unittest.main()
