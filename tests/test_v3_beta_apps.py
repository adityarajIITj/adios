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
from desktop.notepad import NotepadApp
from desktop.clipboard import SovereignClipboard
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
        self.assertIn("AdiOS Sovereign Code Studio", "\n".join(self.studio.lines))

    def test_interactive_keyboard_editing(self):
        self.studio.new_buffer()
        self.assertEqual(self.studio.lines, ["# Sovereign Python Script", ""])
        for ch in "val = 42":
            self.studio.handle_key(ch)
        self.assertEqual(self.studio.lines[1], "val = 42")
        self.studio.handle_key("\n")
        self.assertEqual(len(self.studio.lines), 3)
        self.studio.handle_key("\b")
        self.assertEqual(len(self.studio.lines), 2)

    def test_auto_indentation_on_colon(self):
        self.studio.new_buffer()
        for ch in "def foo():":
            self.studio.handle_key(ch)
        self.studio.handle_key("\n")
        self.assertEqual(self.studio.lines[2], "    ")
        self.assertEqual(self.studio.cursor_col, 4)

    def test_buffer_save_and_open(self):
        test_path = "workspace/test_script.py"
        self.studio.lines = ["print('AdiOS Test')", "x = 100"]
        self.studio.save_buffer(test_path)
        self.assertTrue(os.path.exists(test_path))

        new_studio = CodeStudio()
        new_studio.open_buffer(test_path)
        self.assertEqual(new_studio.lines, ["print('AdiOS Test')", "x = 100"])
        try:
            os.remove(test_path)
        except Exception:
            pass

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

    def test_font_scale_toggle(self):
        self.assertEqual(self.studio.font_scale, 1)
        self.studio.font_scale = 2
        self.assertEqual(self.studio.font_scale, 2)

    def test_package_catalog_inspection(self):
        self.assertTrue(len(self.studio.installed_packages) > 0)
        self.studio.packages_view_mode = "installed"
        self.studio.refresh_installed_packages()
        self.assertTrue(len(self.studio.installed_packages) > 0)
        # Test scroll paging
        self.studio.pkg_scroll_idx = 10
        self.assertEqual(self.studio.pkg_scroll_idx, 10)

    def test_code_studio_shortcuts_and_undo(self):
        # 1. Select All (Ctrl+A)
        self.studio.handle_key("CTRL_A")
        self.assertTrue(self.studio.select_all_active)

        # 2. Copy (Ctrl+C)
        self.studio.handle_key("CTRL_C")
        clip = SovereignClipboard.get_instance().get_text()
        self.assertIn("AdiOS Sovereign Code Studio", clip)

        # 3. Cut (Ctrl+X)
        self.studio.handle_key("CTRL_X")
        self.assertEqual(self.studio.lines, [""])
        self.assertFalse(self.studio.select_all_active)

        # 4. Undo (Ctrl+Z)
        self.studio.handle_key("CTRL_Z")
        self.assertIn("AdiOS Sovereign Code Studio", "\n".join(self.studio.lines))

        # 5. Redo (Ctrl+Y)
        self.studio.handle_key("CTRL_Y")
        self.assertEqual(self.studio.lines, [""])

        # 6. Paste (Ctrl+V)
        self.studio.handle_key("CTRL_V")
        self.assertIn("AdiOS Sovereign Code Studio", "\n".join(self.studio.lines))

        # 7. Word Delete Backward (Ctrl+Backspace)
        self.studio.new_buffer()
        for ch in "def compute_trajectory():":
            self.studio.handle_key(ch)
        self.studio.handle_key("CTRL_BACKSPACE")
        self.assertEqual(self.studio.lines[1], "def compute_trajectory")
        self.studio.handle_key("CTRL_BACKSPACE")
        self.assertEqual(self.studio.lines[1], "def ")

        # 8. Quick Run (Ctrl+Enter)
        self.studio.handle_key("CTRL_ENTER")
        self.assertEqual(self.studio.active_tab, TAB_OUTPUT)

        # 9. Save shortcut (Ctrl+S)
        self.studio.active_tab = TAB_EDITOR
        self.studio.handle_key("CTRL_S")
        self.assertTrue(os.path.exists(self.studio.filepath))

class TestV3Notepad(unittest.TestCase):
    def setUp(self):
        self.notepad = NotepadApp()

    def test_initial_notepad_state(self):
        self.assertTrue(len(self.notepad.lines) > 0)
        self.assertTrue(self.notepad.word_count > 0)
        self.assertTrue(self.notepad.char_count > 0)
        self.assertTrue(self.notepad.show_line_numbers)

    def test_notepad_typing_and_editing(self):
        self.notepad.new_file()
        self.assertEqual(self.notepad.lines, [""])
        for ch in "AdiOS Sovereign Note":
            self.notepad.handle_key(ch)
        self.assertEqual(self.notepad.lines[0], "AdiOS Sovereign Note")
        self.assertEqual(self.notepad.word_count, 3)

        self.notepad.handle_key("\n")
        self.assertEqual(len(self.notepad.lines), 2)
        for ch in "Second line":
            self.notepad.handle_key(ch)
        self.assertEqual(self.notepad.lines[1], "Second line")

        # Backspace test
        self.notepad.handle_key("\b")
        self.assertEqual(self.notepad.lines[1], "Second lin")

    def test_notepad_save_and_open(self):
        test_file = "test_note.txt"
        self.notepad.lines = ["Title: Sovereign Note", "Body: Testing save."]
        self.notepad.save_file(test_file)
        self.assertTrue(os.path.exists(test_file))

        np2 = NotepadApp()
        np2.open_file(test_file)
        self.assertEqual(np2.lines, ["Title: Sovereign Note", "Body: Testing save."])
        try:
            os.remove(test_file)
        except Exception:
            pass

    def test_notepad_shortcuts_and_undo(self):
        # 1. Select All (Ctrl+A)
        self.notepad.handle_key("CTRL_A")
        self.assertTrue(self.notepad.select_all_active)

        # 2. Copy (Ctrl+C)
        self.notepad.handle_key("CTRL_C")
        clip = SovereignClipboard.get_instance().get_text()
        self.assertIn("Welcome to AdiOS", clip)

        # 3. Cut (Ctrl+X)
        self.notepad.handle_key("CTRL_X")
        self.assertEqual(self.notepad.lines, [""])
        self.assertFalse(self.notepad.select_all_active)

        # 4. Undo (Ctrl+Z)
        self.notepad.handle_key("CTRL_Z")
        self.assertIn("Welcome to AdiOS", "\n".join(self.notepad.lines))

        # 5. Redo (Ctrl+Y)
        self.notepad.handle_key("CTRL_Y")
        self.assertEqual(self.notepad.lines, [""])

        # 6. Paste (Ctrl+V)
        self.notepad.handle_key("CTRL_V")
        self.assertIn("Welcome to AdiOS", "\n".join(self.notepad.lines))

        # 7. Word Delete Backward (Ctrl+Backspace)
        self.notepad.new_file()
        for ch in "alpha beta gamma":
            self.notepad.handle_key(ch)
        self.notepad.handle_key("CTRL_BACKSPACE")
        self.assertEqual(self.notepad.lines[0], "alpha beta ")
        self.notepad.handle_key("CTRL_BACKSPACE")
        self.assertEqual(self.notepad.lines[0], "alpha ")

        # 8. Selection replacement typing
        self.notepad.handle_key("CTRL_A")
        self.assertTrue(self.notepad.select_all_active)
        self.notepad.handle_key("X")
        self.assertEqual(self.notepad.lines, ["X"])
        self.assertFalse(self.notepad.select_all_active)

        # 9. Save shortcut (Ctrl+S)
        self.notepad.handle_key("CTRL_S")
        self.assertTrue(os.path.exists(self.notepad.filename))

    def test_notepad_rendering(self):
        fb = bytearray(1280 * 720 * 4)
        self.notepad.on_draw_content(self.notepad, fb, {})
        cx, cy, cw, ch = self.notepad.client_rect
        sample_off = ((cy + 40) * 1280 + (cx + 50)) * 4
        self.assertTrue(any(fb[sample_off:sample_off+4]))

class TestV3FileExplorer(unittest.TestCase):
    def setUp(self):
        self.explorer = FileExplorer()

    def test_directory_scanning(self):
        self.assertTrue(len(self.explorer.entries) > 0)
        has_dirs = any(e.is_dir for e in self.explorer.entries)
        self.assertTrue(has_dirs)

    def test_search_filtering(self):
        self.explorer.set_search_filter("py")
        self.assertTrue(len(self.explorer.entries) > 0)
        for e in self.explorer.entries:
            self.assertIn("py", e.name.lower())
        # Clear filter
        self.explorer.set_search_filter("")
        self.assertEqual(self.explorer.search_query, "")

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

    def test_places_storage_bookmarks(self):
        places_dict = dict(self.explorer.places)
        self.assertIn("Notes", places_dict)
        self.assertIn("Code", places_dict)
        self.assertTrue(os.path.isdir(places_dict["Notes"]))
        self.assertTrue(os.path.isdir(places_dict["Code"]))

        # Navigate to Notes folder
        self.explorer.navigate_to(places_dict["Notes"])
        self.assertEqual(self.explorer.current_dir, places_dict["Notes"])

        # Navigate to Code folder
        self.explorer.navigate_to(places_dict["Code"])
        self.assertEqual(self.explorer.current_dir, places_dict["Code"])

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

    def test_camera_zoom_controls(self):
        initial_zoom = self.studio.zoom
        self.studio.zoom_in()
        self.assertLess(self.studio.zoom, initial_zoom)
        self.studio.zoom_out()
        self.assertEqual(self.studio.zoom, initial_zoom)

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
        self.assertIsNotNone(self.desktop.win_notepad)

    def test_app_launch_or_focus(self):
        self.desktop.launch_or_focus("studio")
        self.assertTrue(self.desktop.win_studio.visible)
        self.assertFalse(self.desktop.win_studio.minimized)

        self.desktop.launch_or_focus("files")
        self.assertTrue(self.desktop.win_file_explorer.visible)

        self.desktop.launch_or_focus("scene3d")
        self.assertTrue(self.desktop.win_scene3d.visible)

        self.desktop.launch_or_focus("notepad")
        self.assertTrue(self.desktop.win_notepad.visible)
        self.assertFalse(self.desktop.win_notepad.minimized)

    def test_notepad_key_routing(self):
        self.desktop.launch_or_focus("notepad")
        self.desktop.win_notepad.new_file()
        self.desktop.handle_key("A")
        self.desktop.handle_key("d")
        self.desktop.handle_key("i")
        self.assertEqual(self.desktop.win_notepad.lines[0], "Adi")

    def test_taskbar_window_minimize_and_restore(self):
        # Find active window and its taskbar pill coordinate
        active_win = self.desktop.wm.windows[-1]
        active_win.visible = True
        active_win.minimized = False
        self.desktop.wm.focus_window(active_win)

        visible_windows = [w for w in self.desktop.wm.windows if w.visible]
        active_idx = visible_windows.index(active_win)
        active_pill_x = 338 + active_idx * 72 + 10

        # Click pill of active window -> minimizes it
        res = self.desktop.handle_mouse_down(active_pill_x, 10)
        self.assertEqual(res[0], "minimize_window")
        self.assertTrue(active_win.minimized)

        # Click pill of minimized window -> restores it
        res2 = self.desktop.handle_mouse_down(active_pill_x, 10)
        self.assertEqual(res2[0], "restore_window")
        self.assertFalse(active_win.minimized)

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

class TestV3StorageSegregation(unittest.TestCase):
    def test_segregated_default_locations(self):
        np = NotepadApp()
        cs = CodeStudio()

        # Check default paths contain respective storage directories
        self.assertTrue("storage" in np.filename and "notepad" in np.filename)
        self.assertTrue("storage" in cs.filepath and "code" in cs.filepath)

        # Ensure directories exist
        self.assertTrue(os.path.isdir("storage/notepad"))
        self.assertTrue(os.path.isdir("storage/code"))

        # Save sample documents into each
        np.lines = ["Note item 1", "Note item 2"]
        np.save_file()
        self.assertTrue(os.path.exists(np.filename))

        cs.lines = ["# Code item", "print('ok')"]
        cs.save_buffer()
        self.assertTrue(os.path.exists(cs.filepath))

        # Check that file paths are distinct and folders separate
        self.assertNotEqual(os.path.dirname(np.filename), os.path.dirname(cs.filepath))

if __name__ == "__main__":
    unittest.main()
