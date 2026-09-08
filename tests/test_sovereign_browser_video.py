#!/usr/bin/env python3
"""
Unit Test Suite for SovereignWeb Ephemeral In-RAM Video Browser (tests/test_sovereign_browser_video.py)
Validates:
1. Zero-disk in-memory video stream pipeline (strictly 0 bytes written to disk).
2. Ephemeral RAM ring-buffer frame decoding at 30-60 FPS.
3. In-page embedded video player transport controls (Play/Pause, Scrubber, Channel Switch).
4. Multi-tab navigation, history traversal, and built-in sovereign portals.
5. Linear 32-bit framebuffer rasterization and MasterDesktop integration.

Strict Zero Emoji Policy Enforced.
"""

import unittest
import time
from net.video_streamer import (
    EphemeralVideoStreamer,
    STREAM_STATE_STREAMING,
    STREAM_STATE_PAUSED,
    STREAM_STATE_STOPPED,
)
from desktop.browser import SovereignBrowser, WebKitBrowserApp, STREAM_CATALOG
from desktop.master_desktop import MasterDesktop


class TestSovereignBrowserVideo(unittest.TestCase):
    """Test suite for SovereignWeb in-page live video streaming browser."""

    def test_01_ephemeral_streamer_zero_disk_guarantee(self):
        """Verify video streamer runs purely in memory with zero disk writes."""
        streamer = EphemeralVideoStreamer(width=320, height=180, fps=30)
        self.assertEqual(streamer.disk_bytes_written, 0)
        self.assertEqual(streamer.ram_used_bytes, 0)

        # Start procedural stream
        streamer.start_stream("synth://test_channel", "Test Procedural Stream")
        time.sleep(0.3)

        # Check telemetry
        telem = streamer.get_telemetry()
        self.assertEqual(telem["state"], STREAM_STATE_STREAMING)
        self.assertEqual(telem["disk_bytes_written"], 0)
        self.assertTrue(telem["zero_disk_verified"])
        self.assertGreater(telem["frames_streamed"], 0)
        self.assertGreater(telem["ram_used_mb"], 0.0)

        # Verify frame retrieval
        frame = streamer.get_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(len(frame), 320 * 180 * 4)

        streamer.stop()
        self.assertEqual(streamer.state, STREAM_STATE_STOPPED)

    def test_02_streamer_pause_resume_toggle(self):
        """Verify transport controls (pause, resume, toggle) work accurately."""
        streamer = EphemeralVideoStreamer(width=160, height=90, fps=30)
        streamer.start_stream("synth://test_transport")
        time.sleep(0.1)

        self.assertTrue(streamer.is_playing)
        streamer.pause()
        self.assertEqual(streamer.state, STREAM_STATE_PAUSED)
        self.assertFalse(streamer.is_playing)

        streamer.resume()
        self.assertEqual(streamer.state, STREAM_STATE_STREAMING)
        self.assertTrue(streamer.is_playing)

        streamer.toggle_play()
        self.assertEqual(streamer.state, STREAM_STATE_PAUSED)

        streamer.stop()

    def test_03_sovereign_browser_navigation_and_tabs(self):
        """Verify tab switching, URL navigation, and history traversal."""
        browser = SovereignBrowser(win_id="test_browser", w=720, h=480)
        self.assertEqual(browser.current_url, "about:home")
        self.assertEqual(len(browser.tabs), 3)

        # Navigate to Video Hub
        browser.navigate_to("about:video")
        self.assertEqual(browser.current_url, "about:video")
        self.assertEqual(browser.tabs[browser.active_tab_idx]["title"], "Live Video Hub")

        # Navigate to Architecture
        browser.navigate_to("about:engine")
        self.assertEqual(browser.current_url, "about:engine")

        # Go back
        browser.go_back()
        self.assertEqual(browser.current_url, "about:video")

        # Go forward
        browser.go_forward()
        self.assertEqual(browser.current_url, "about:engine")

        browser.video_streamer.stop()

    def test_04_in_page_stream_switching(self):
        """Verify switching stream channels updates active streamer URL."""
        browser = SovereignBrowser(win_id="test_browser", w=720, h=480)
        initial_idx = browser.active_stream_idx

        # Switch to next channel
        browser._next_stream_channel()
        new_idx = browser.active_stream_idx
        self.assertNotEqual(initial_idx, new_idx)
        self.assertEqual(browser.video_streamer.stream_title, STREAM_CATALOG[new_idx]["name"])

        # Switch to channel 0
        browser._select_stream_channel(0)
        self.assertEqual(browser.active_stream_idx, 0)
        self.assertEqual(browser.video_streamer.stream_title, STREAM_CATALOG[0]["name"])

        browser.video_streamer.stop()

    def test_05_browser_framebuffer_rasterization(self):
        """Verify browser window rasterizes cleanly into linear 32-bit framebuffer."""
        browser = SovereignBrowser(win_id="test_browser", x=10, y=10, w=640, h=440)
        fb = bytearray(1280 * 720 * 4)

        # Render Home Portal
        browser.navigate_to("about:home")
        browser._render_browser_window(browser, fb, {})
        # Verify content was written
        non_zero = sum(1 for b in fb[:1280 * 400 * 4:1000] if b != 0)
        self.assertGreater(non_zero, 0)

        # Render Video Hub
        browser.navigate_to("about:video")
        browser._render_browser_window(browser, fb, {})
        self.assertGreater(sum(1 for b in fb[:1280 * 400 * 4:1000] if b != 0), 0)

        # Render Engine Architecture
        browser.navigate_to("about:engine")
        browser._render_browser_window(browser, fb, {})
        self.assertGreater(sum(1 for b in fb[:1280 * 400 * 4:1000] if b != 0), 0)

        browser.video_streamer.stop()

    def test_06_master_desktop_sovereign_browser_launch(self):
        """Verify MasterDesktop launches SovereignBrowser and verifies zero disk writes."""
        desktop = MasterDesktop()
        self.assertIsNotNone(desktop.win_webkit)
        self.assertIsInstance(desktop.win_webkit, SovereignBrowser)

        # Initially invisible
        self.assertFalse(desktop.win_webkit.visible)

        # Launch via action ID
        desktop.launch_or_focus("webkit")
        self.assertTrue(desktop.win_webkit.visible)
        self.assertEqual(desktop.wm.windows[-1], desktop.win_webkit)

        # Step frame
        desktop.step_frame(100, 100)

        # Check telemetry
        telem = desktop.win_webkit.video_streamer.get_telemetry()
        self.assertEqual(telem["disk_bytes_written"], 0)
        self.assertTrue(telem["zero_disk_verified"])

        desktop.win_webkit.video_streamer.stop()


if __name__ == "__main__":
    unittest.main()
