#!/usr/bin/env python3
"""
Unit tests for AdiOS WebKit Browser (tests/test_browser_app.py).
Verifies:
- Browser window initialization and geometry.
- Omnibar URL and search query parsing and submission.
- Bookmark toolbar routing.
- Asynchronous worker command queuing.
- Framebuffer rendering and linear blitting.
- Keyboard input handling and focus toggling.
- Clean application shutdown.

Strict Zero Emoji Policy.
"""

import unittest
import time
from desktop.browser import WebKitBrowserApp, DEFAULT_HOMEPAGE, BOOKMARKS

class TestWebKitBrowserApp(unittest.TestCase):
    def setUp(self):
        self.browser = WebKitBrowserApp(
            win_id="test_browser",
            x=50,
            y=50,
            w=640,
            h=480,
            initial_url=DEFAULT_HOMEPAGE,
            lazy_start=False
        )

    def tearDown(self):
        if self.browser:
            self.browser.close()

    def test_browser_initial_state(self):
        self.assertEqual(self.browser.win_id, "test_browser")
        self.assertEqual(self.browser.current_url, DEFAULT_HOMEPAGE)
        self.assertEqual(self.browser.omnibar_text, DEFAULT_HOMEPAGE)
        self.assertFalse(self.browser.omnibar_focused)
        self.assertGreater(len(self.browser.history), 0)
        self.assertIsNotNone(self.browser.worker)

    def test_omnibar_search_routing(self):
        # 1. Plain query -> DuckDuckGo Search
        self.browser.omnibar_text = "operating systems architecture"
        self.browser._submit_omnibar()
        self.assertTrue(self.browser.current_url.startswith("https://duckduckgo.com/?q="))
        self.assertIn("operating%20systems", self.browser.current_url)

        # 2. Domain without protocol -> https:// prefix
        self.browser.omnibar_text = "wikipedia.org"
        self.browser._submit_omnibar()
        self.assertEqual(self.browser.current_url, "https://wikipedia.org")

        # 3. Explicit https URL -> unchanged
        self.browser.omnibar_text = "https://github.com/adityarajIITj/adios"
        self.browser._submit_omnibar()
        self.assertEqual(self.browser.current_url, "https://github.com/adityarajIITj/adios")

    def test_bookmark_navigation(self):
        initial_history_len = len(self.browser.history)
        self.browser.navigate(BOOKMARKS[1][1])  # Wikipedia
        self.assertEqual(self.browser.current_url, "https://en.wikipedia.org")
        self.assertGreater(len(self.browser.history), initial_history_len)

    def test_navigation_controls(self):
        self.browser.navigate("https://news.ycombinator.com")
        self.browser.go_back()
        self.browser.go_forward()
        self.browser.reload()
        # Verify worker received commands without error
        self.assertFalse(self.browser.worker.cmd_queue.empty())

    def test_keyboard_omnibar_editing(self):
        self.browser.omnibar_focused = True
        self.browser.omnibar_text = "test"
        self.browser.handle_key("1")
        self.assertEqual(self.browser.omnibar_text, "test1")
        self.browser.handle_key("\b")
        self.assertEqual(self.browser.omnibar_text, "test")
        self.browser.handle_key("ESCAPE")
        self.assertFalse(self.browser.omnibar_focused)

    def test_viewport_rendering_to_framebuffer(self):
        fb = bytearray(1024 * 768 * 4)
        font_dict = {}
        # Test rendering content does not crash and populates framebuffer
        self.browser._render_content(self.browser, fb, font_dict)
        # Check that pixels were rendered within the window bounds
        nonzero = sum(1 for b in fb if b != 0)
        self.assertGreater(nonzero, 0)

    def test_fullscreen_toggle(self):
        self.assertFalse(self.browser.is_fullscreen)
        # Toggle via F11
        self.browser.handle_key("F11")
        self.assertTrue(self.browser.is_fullscreen)
        self.assertEqual(self.browser.x, 0)
        self.assertEqual(self.browser.y, 0)
        self.assertEqual(self.browser.w, 1280)
        self.assertEqual(self.browser.h, 720)

        # Toggle back via ESCAPE
        self.browser.handle_key("ESCAPE")
        self.assertFalse(self.browser.is_fullscreen)

    def test_resize_dispatch(self):
        initial_q_size = self.browser.worker.cmd_queue.qsize()
        # Trigger resize
        self.browser._handle_resize(self.browser, 1280, 720)
        self.assertGreater(self.browser.worker.cmd_queue.qsize(), initial_q_size)

    def test_graceful_shutdown(self):
        worker = self.browser.worker
        self.browser.close()
        self.assertFalse(worker.running)
        self.assertIsNone(self.browser.worker)

if __name__ == "__main__":
    unittest.main()
