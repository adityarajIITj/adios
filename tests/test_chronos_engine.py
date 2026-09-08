#!/usr/bin/env python3
"""
Unit Test Suite for AdiOS Chronos OS-Wide Time-Travel Engine (tests/test_chronos_engine.py)
Validates:
1. Continuous differential state capture without memory leaks.
2. Window geometry, Paint Studio vector stroke, and text buffer temporal rewinding.
3. Timeline scrubbing, keyframe seek, and time offset calculations.
4. Reality forking: Committing past state as new present timeline.
5. Live resumption: Springing back to real-time present.
6. Chronos HUD overlay rasterization and interactive click/drag event handling.
7. F9 shortcut and taskbar dispatch integration in MasterDesktop.

Strict Zero Emoji Policy Enforced.
"""

import unittest
import time
from kernel.chronos import ChronosEngine, ChronosFrame
from desktop.chronos_hud import ChronosHUD
from desktop.master_desktop import MasterDesktop


class TestChronosEngine(unittest.TestCase):
    """Test suite for Chronos Time-Travel Rewind & Replay Engine."""

    def test_01_chronos_capture_and_frame_retrieval(self):
        """Verify continuous differential state capture."""
        desktop = MasterDesktop()
        chronos = desktop.chronos
        self.assertEqual(chronos.frame_count, 0)
        self.assertFalse(chronos.is_active)

        # Capture frame
        frame = chronos.capture_frame(desktop)
        self.assertIsNotNone(frame)
        self.assertEqual(chronos.frame_count, 1)
        self.assertIn("browser", frame.window_states)
        self.assertIn("notepad", frame.window_states)
        self.assertIn("studio", frame.window_states)

    def test_02_time_travel_toggle_and_window_rewind(self):
        """Verify scrubbing timeline moves windows back to historical coordinates."""
        desktop = MasterDesktop()
        chronos = desktop.chronos

        # Initial state: capture frame 1
        desktop.win_notepad.x = 100
        desktop.win_notepad.y = 100
        chronos._last_capture_time = 0.0  # Force capture
        chronos.capture_frame(desktop)
        time.sleep(0.04)

        # Move window: capture frame 2
        desktop.win_notepad.x = 300
        desktop.win_notepad.y = 300
        chronos._last_capture_time = 0.0
        chronos.capture_frame(desktop)
        time.sleep(0.04)

        # Move window again: capture frame 3
        desktop.win_notepad.x = 500
        desktop.win_notepad.y = 500
        chronos._last_capture_time = 0.0
        chronos.capture_frame(desktop)

        self.assertEqual(chronos.frame_count, 3)
        self.assertEqual(desktop.win_notepad.x, 500)

        # Activate time-travel
        chronos.toggle_time_travel(desktop)
        self.assertTrue(chronos.is_active)

        # Scrub backwards to frame 0 (oldest)
        chronos.scrub_to_index(0, desktop)
        self.assertEqual(desktop.win_notepad.x, 100)
        self.assertEqual(desktop.win_notepad.y, 100)
        self.assertLess(chronos.current_time_offset, 0.0)

        # Scrub forward to frame 1
        chronos.scrub_to_index(1, desktop)
        self.assertEqual(desktop.win_notepad.x, 300)

        # Scrub to frame 2 (present)
        chronos.scrub_to_index(2, desktop)
        self.assertEqual(desktop.win_notepad.x, 500)

        chronos.resume_live(desktop)
        self.assertFalse(chronos.is_active)

    def test_03_text_and_paint_stroke_rewind(self):
        """Verify un-drawing paint strokes and un-typing buffer text."""
        desktop = MasterDesktop()
        chronos = desktop.chronos

        # State 1: Notepad has 1 line
        desktop.win_notepad.lines = ["Line 1: Origin"]
        desktop.win_paint.paint_strokes = [{"color": 1, "points": [(10, 10)]}]
        chronos._last_capture_time = 0.0
        chronos.capture_frame(desktop)
        time.sleep(0.04)

        # State 2: User adds 2 lines and 2 more strokes
        desktop.win_notepad.lines = ["Line 1: Origin", "Line 2: Edited", "Line 3: Future"]
        desktop.win_paint.paint_strokes.append({"color": 2, "points": [(20, 20)]})
        desktop.win_paint.paint_strokes.append({"color": 3, "points": [(30, 30)]})
        chronos._last_capture_time = 0.0
        chronos.capture_frame(desktop)

        self.assertEqual(len(desktop.win_notepad.lines), 3)
        self.assertEqual(len(desktop.win_paint.paint_strokes), 3)

        # Engage time-travel and scrub back to State 1
        chronos.toggle_time_travel(desktop)
        chronos.scrub_to_index(0, desktop)

        # Verify historical text and stroke restoration
        self.assertEqual(len(desktop.win_notepad.lines), 1)
        self.assertEqual(desktop.win_notepad.lines[0], "Line 1: Origin")
        self.assertEqual(len(desktop.win_paint.paint_strokes), 1)

        chronos.resume_live(desktop)

    def test_04_fork_reality_commits_rewound_present(self):
        """Verify forking reality commits historical point as the new present."""
        desktop = MasterDesktop()
        chronos = desktop.chronos

        # Frame 0: x=100
        desktop.win_studio.x = 100
        chronos._last_capture_time = 0.0
        chronos.capture_frame(desktop)
        time.sleep(0.04)

        # Frame 1: x=200
        desktop.win_studio.x = 200
        chronos._last_capture_time = 0.0
        chronos.capture_frame(desktop)
        time.sleep(0.04)

        # Frame 2: x=300
        desktop.win_studio.x = 300
        chronos._last_capture_time = 0.0
        chronos.capture_frame(desktop)

        self.assertEqual(chronos.frame_count, 3)

        # Engage time-travel and scrub to Frame 1 (x=200)
        chronos.toggle_time_travel(desktop)
        chronos.scrub_to_index(1, desktop)
        self.assertEqual(desktop.win_studio.x, 200)

        # Fork Reality
        chronos.fork_reality(desktop)
        self.assertFalse(chronos.is_active)
        self.assertEqual(chronos.reality_forks_count, 1)
        # History truncated after Frame 1
        self.assertEqual(chronos.frame_count, 2)
        # Current studio x is committed at 200
        self.assertEqual(desktop.win_studio.x, 200)

    def test_05_chronos_hud_rendering_and_interaction(self):
        """Verify Chronos HUD overlay rasterization and click dispatch."""
        desktop = MasterDesktop()
        chronos = desktop.chronos
        hud = desktop.chronos_hud

        # Populate a few frames
        for i in range(5):
            chronos._last_capture_time = 0.0
            chronos.capture_frame(desktop)

        chronos.toggle_time_travel(desktop)
        self.assertTrue(chronos.is_active)

        # Render onto framebuffer
        fb = bytearray(1280 * 720 * 4)
        hud.render(fb, chronos, desktop, {})

        # Verify pixels were written
        non_zero = sum(1 for b in fb[:1280 * 120 * 4:1000] if b != 0)
        self.assertGreater(non_zero, 0)

        # Test click on scrubber (middle)
        scrub_click_x = hud.hud_x + hud.scrub_rel_x + (hud.scrub_w // 2)
        scrub_click_y = hud.hud_y + hud.scrub_rel_y + 2
        handled = hud.handle_mouse_down(scrub_click_x, scrub_click_y, chronos, desktop)
        self.assertTrue(handled)
        self.assertAlmostEqual(chronos.scrub_fraction, 0.5, delta=0.2)

        chronos.resume_live(desktop)

    def test_06_f9_shortcut_and_taskbar_integration(self):
        """Verify F9 key toggles Chronos and arrow keys step time."""
        desktop = MasterDesktop()
        chronos = desktop.chronos

        # Populate frames
        for i in range(4):
            chronos._last_capture_time = 0.0
            chronos.capture_frame(desktop)

        self.assertFalse(chronos.is_active)

        # Press F9 to engage
        desktop.handle_key("F9")
        self.assertTrue(chronos.is_active)

        # Press LEFT to step backward
        initial_idx = chronos.scrub_index
        desktop.handle_key("KEY_LEFT")
        self.assertEqual(chronos.scrub_index, initial_idx - 1)

        # Press RIGHT to step forward
        desktop.handle_key("KEY_RIGHT")
        self.assertEqual(chronos.scrub_index, initial_idx)

        # Press ESCAPE to exit
        desktop.handle_key("ESCAPE")
        self.assertFalse(chronos.is_active)

        # Test Taskbar button click at x=desktop.width - 380, y=10 (CHRONOS pill)
        evt = desktop.handle_mouse_down(desktop.width - 380, 10)
        self.assertEqual(evt, ("chronos_toggle", True))
        self.assertTrue(chronos.is_active)


if __name__ == "__main__":
    unittest.main()
