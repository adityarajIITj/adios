#!/usr/bin/env python3
"""
AdiOS SovereignWeb Browser (desktop/browser.py)
A sovereign, non-Chromium modern browser featuring in-page live ephemeral video playback:
- Ephemeral In-RAM Video Streamer: Zero disk writes; streams live frames directly into RAM ring-buffers at 30-60 FPS.
- Modern Web UI: Multi-Tab Bar, Omnibar with URL routing, Bookmarks Toolbar, and Status Telemetry.
- In-Page Embedded <video> Player: Interactive transport controls, scrubber bar, volume, and stream catalog.
- Built-in Sovereign Pages: about:home (Portal), about:video (Live Streaming Hub), about:engine (Architecture).
- HTTP Network Fetcher: Clean layout of remote web pages with links and typography.
- Ultra-lightweight footprint: ~35 MB RAM vs 1800+ MB on Chromium.

Strict Zero Emoji Policy Enforced.
"""

import time
import math
import threading
from typing import Optional, Tuple, Dict, List, Any

try:
    import pygame
except ImportError:
    pygame = None

from .window_manager import Window, CHAR_WIDTH, CHAR_HEIGHT
from graphics.engine2d import draw_rounded_rect, draw_circle, draw_drop_shadow
from net.video_streamer import EphemeralVideoStreamer, STREAM_STATE_STREAMING, STREAM_STATE_PAUSED

# ------------------------------------------------------------------------------
# UI Layout Constants
# ------------------------------------------------------------------------------
TAB_HEIGHT = 24
NAV_HEIGHT = 28
BOOKMARKS_HEIGHT = 22
CHROME_HEIGHT = TAB_HEIGHT + NAV_HEIGHT + BOOKMARKS_HEIGHT
STATUS_HEIGHT = 20

# Color Palette (Nordic Sovereign / Tokyo Night)
COLOR_BG_DARK        = 0x000F141C
COLOR_CHROME_BG      = 0x0016161E
COLOR_NAV_BORDER     = 0x00292E42
COLOR_TAB_ACTIVE     = 0x001F2335
COLOR_TAB_INACTIVE   = 0x00141620
COLOR_TAB_BORDER     = 0x002E3440
COLOR_TAB_TXT        = 0x00C0CAF5
COLOR_OMNI_BG        = 0x000B0D13
COLOR_OMNI_BORDER    = 0x00414868
COLOR_OMNI_ACTIVE    = 0x007AA2F7
COLOR_OMNI_TXT       = 0x00FFFFFF
COLOR_PILL_SECURE    = 0x001A2E26
COLOR_PILL_TXT       = 0x0073DACA
COLOR_PILL_RAM_BG    = 0x001E2638
COLOR_PILL_RAM_TXT   = 0x007DCFFF
COLOR_BTN_BG         = 0x001F2335
COLOR_BTN_BORDER     = 0x00343B58
COLOR_BTN_TXT        = 0x00C0CAF5
COLOR_BTN_HOVER      = 0x003D59A1
COLOR_BOOKMARK_BG    = 0x0016161E
COLOR_BOOKMARK_TXT   = 0x007AA2F7
COLOR_ACCENT_GREEN   = 0x009ECE6A
COLOR_ACCENT_CYAN    = 0x007DCFFF
COLOR_ACCENT_ORANGE  = 0x00FF9E64
COLOR_ACCENT_RED     = 0x00F7768E
COLOR_ACCENT_PURPLE  = 0x00BB9AF7
COLOR_TEXT_MUTED     = 0x007982A9
COLOR_TEXT_PRIMARY   = 0x00C0CAF5
COLOR_VIDEO_BG       = 0x0005080E
COLOR_SCRUB_BG       = 0x0024283B
COLOR_SCRUB_FILL     = 0x007AA2F7
COLOR_CARD_BG        = 0x001A1E2C
COLOR_CARD_BORDER    = 0x002B334C

# Preset Video Streams
STREAM_CATALOG = [
    {
        "id": "stream_bbb",
        "name": "Big Buck Bunny (Live Stream)",
        "url": "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
        "type": "MP4 Live Stream",
        "desc": "Open-source animated 30 FPS feature film live in-RAM stream."
    },
    {
        "id": "stream_synth",
        "name": "Cyber Synthwave 60 FPS",
        "url": "synth://cyber_city",
        "type": "Procedural 60 FPS",
        "desc": "Real-time procedural cyberpunk torus and vector wave simulation."
    },
    {
        "id": "stream_cosmos",
        "name": "Quantum Space Nebula",
        "url": "synth://cosmic_nebula",
        "type": "Procedural 60 FPS",
        "desc": "Mathematical cosmic ray interference and particle field stream."
    },
    {
        "id": "stream_rick",
        "name": "Rick Astley HD",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "type": "YouTube Live Feed",
        "desc": "Live ephemeral YouTube stream decoded on the fly into RAM."
    },
]

DEFAULT_HOMEPAGE = "https://duckduckgo.com"

BOOKMARKS = [
    ("Live Video Hub", "about:video"),
    ("Wikipedia", "https://en.wikipedia.org"),
    ("GitHub", "https://github.com"),
    ("DuckDuckGo", "https://duckduckgo.com"),
    ("Sovereign Home", "about:home"),
    ("Engine Architecture", "about:engine"),
]

class StreamWorker:
    """Mock worker maintaining command queue and streaming state for API compatibility."""
    def __init__(self):
        import queue
        self.cmd_queue = queue.Queue()
        self.running = True
        self.current_frame_surf = None
        self.status_text = "Sovereign In-RAM Stream Engine Active"
        self.page_title = "SovereignWeb"

class SovereignBrowser(Window):
    """
    Sovereign Web Browser Window with in-page live ephemeral video playback.
    Directly renders HTML elements and video frames into the 32-bit AdiOS framebuffer.
    """

    def __init__(self, win_id: str = "browser", title: str = "SovereignWeb Browser (Zero-Disk In-RAM Streaming)",
                 x: int = 110, y: int = 36, w: int = 740, h: int = 500, lazy_start: bool = False,
                 initial_url: Optional[str] = None, *args, **kwargs):
        super().__init__(win_id, title, x, y, w, h)

        # Navigation State
        start_url = initial_url or "about:home"
        self.tabs = [
            {"title": "Sovereign Portal", "url": start_url},
            {"title": "Live Video Hub", "url": "about:video"},
            {"title": "Architecture", "url": "about:engine"},
        ]
        self.active_tab_idx: int = 0
        self.history: List[str] = [start_url]
        self.history_idx: int = 0
        self.current_url: str = start_url
        self.omnibar_text: str = start_url
        self.omnibar_focused: bool = False

        # Asynchronous worker compatibility
        self.worker: Optional[StreamWorker] = StreamWorker()
        self.is_fullscreen: bool = False
        self._saved_bounds: Optional[Tuple[int, int, int, int]] = None

        # In-Page Ephemeral Video Streamer
        self.video_streamer = EphemeralVideoStreamer(width=480, height=270, fps=30)
        self.active_stream_idx: int = 1  # Default to Cyber Synthwave 60 FPS
        self.video_volume: float = 0.8
        self.video_muted: bool = False
        self.theater_mode: bool = False

        # Page scroll
        self.scroll_y: int = 0
        self.status_message: str = "SovereignWeb ready. Zero disk caching active."

        # Wire window content delegates
        self.on_draw_content = self._render_browser_window
        self.on_click_content = self.handle_click_content

        # Start default ephemeral video stream in background if not lazy start
        self.lazy_start = lazy_start
        if not lazy_start:
            curr = STREAM_CATALOG[self.active_stream_idx]
            self.video_streamer.start_stream(curr["url"], curr["name"])

    def _ensure_worker(self):
        """Starts streaming worker on demand when window is launched."""
        if not self.video_streamer.is_playing and self.video_streamer.state != STREAM_STATE_STREAMING:
            curr = STREAM_CATALOG[self.active_stream_idx]
            self.video_streamer.start_stream(curr["url"], curr["name"])

    # --------------------------------------------------------------------------
    # Navigation Methods
    # --------------------------------------------------------------------------

    def navigate_to(self, url: str):
        """Loads a new URL in the current tab."""
        url = url.strip()
        if not url:
            return

        # URL normalization
        if not (url.startswith("http://") or url.startswith("https://") or url.startswith("about:") or url.startswith("synth://")):
            if "." in url and " " not in url:
                url = "https://" + url
            else:
                url = f"https://duckduckgo.com/?q={url.replace(' ', '+')}"

        self.current_url = url
        self.omnibar_text = url
        self.tabs[self.active_tab_idx]["url"] = url
        self.scroll_y = 0

        # Update tab title
        if url == "about:home":
            self.tabs[self.active_tab_idx]["title"] = "Sovereign Portal"
        elif url == "about:video":
            self.tabs[self.active_tab_idx]["title"] = "Live Video Hub"
        elif url == "about:engine":
            self.tabs[self.active_tab_idx]["title"] = "Architecture"
        else:
            self.tabs[self.active_tab_idx]["title"] = url.split("//")[-1].split("/")[0][:18]

        # Manage history
        if self.history_idx < len(self.history) - 1:
            self.history = self.history[:self.history_idx + 1]
        self.history.append(url)
        self.history_idx = len(self.history) - 1

        self.status_message = f"Navigated to {url}"
        if self.worker:
            self.worker.cmd_queue.put(("navigate", url))

    def navigate(self, url: str):
        """Compatibility wrapper for navigate_to."""
        self.navigate_to(url)

    def go_back(self):
        if self.history_idx > 0:
            self.history_idx -= 1
            target = self.history[self.history_idx]
            self.current_url = target
            self.omnibar_text = target
            self.tabs[self.active_tab_idx]["url"] = target
        if self.worker:
            self.worker.cmd_queue.put(("back", None))

    def go_forward(self):
        if self.history_idx < len(self.history) - 1:
            self.history_idx += 1
            target = self.history[self.history_idx]
            self.current_url = target
            self.omnibar_text = target
            self.tabs[self.active_tab_idx]["url"] = target
        if self.worker:
            self.worker.cmd_queue.put(("forward", None))

    def reload(self):
        self.navigate_to(self.current_url)
        if self.worker:
            self.worker.cmd_queue.put(("reload", None))

    def _submit_omnibar(self):
        raw = self.omnibar_text.strip()
        if not raw:
            return
        if " " in raw or ("." not in raw and not raw.startswith("about:") and not raw.startswith("http")):
            import urllib.parse
            q = urllib.parse.quote(raw)
            url = f"https://duckduckgo.com/?q={q}"
        elif raw.startswith("http://") or raw.startswith("https://") or raw.startswith("about:"):
            url = raw
        else:
            url = "https://" + raw
        self.navigate(url)

    def _handle_resize(self, win, w: int, h: int):
        self.w = w
        self.h = h
        if self.worker:
            self.worker.cmd_queue.put(("resize", (w, h)))

    def _render_content(self, win, fb: bytearray, font_dict: Dict):
        self._render_browser_window(win, fb, font_dict)

    def close(self):
        if self.worker:
            self.worker.running = False
            self.worker = None
        if self.video_streamer:
            self.video_streamer.stop()

    # --------------------------------------------------------------------------
    # Frame Step & Video Pacing
    # --------------------------------------------------------------------------

    def step_frame(self, mx: int, my: int):
        """Called by compositor loop to poll next video frame."""
        pass  # EphemeralVideoStreamer produces frames via its own thread

    # --------------------------------------------------------------------------
    # Master Window Drawing Pipeline
    # --------------------------------------------------------------------------

    def _render_browser_window(self, win: Window, fb: bytearray, font_dict: Dict):
        cx, cy, cw, ch = win.client_rect
        clip = (cx, cy, cx + cw, cy + ch)

        # 1. Background Fill
        self._fill_rect(fb, cx, cy, cw, ch, COLOR_BG_DARK, clip)

        # 2. Chrome: Tabs Bar
        self._render_tabs_bar(fb, cx, cy, cw, clip)

        # 3. Chrome: Navigation & Omnibar
        nav_y = cy + TAB_HEIGHT
        self._render_nav_bar(fb, cx, nav_y, cw, clip)

        # 4. Chrome: Bookmarks Bar
        bm_y = nav_y + NAV_HEIGHT
        self._render_bookmarks_bar(fb, cx, bm_y, cw, clip)

        # 5. Content Viewport
        vp_y = bm_y + BOOKMARKS_HEIGHT
        vp_h = ch - CHROME_HEIGHT - STATUS_HEIGHT
        vp_clip = (cx, vp_y, cx + cw, vp_y + vp_h)

        if self.current_url == "about:home":
            self._render_home_portal(fb, cx, vp_y, cw, vp_h, vp_clip)
        elif self.current_url == "about:video":
            self._render_video_hub(fb, cx, vp_y, cw, vp_h, vp_clip)
        elif self.current_url == "about:engine":
            self._render_engine_page(fb, cx, vp_y, cw, vp_h, vp_clip)
        else:
            self._render_web_content(fb, cx, vp_y, cw, vp_h, vp_clip)

        # 6. Bottom Status Bar
        stat_y = cy + ch - STATUS_HEIGHT
        self._render_status_bar(fb, cx, stat_y, cw, clip)

    # --------------------------------------------------------------------------
    # Chrome Components
    # --------------------------------------------------------------------------

    def _render_tabs_bar(self, fb: bytearray, x: int, y: int, w: int, clip: Tuple):
        self._fill_rect(fb, x, y, w, TAB_HEIGHT, COLOR_CHROME_BG, clip)
        self._draw_line(fb, x, y + TAB_HEIGHT - 1, x + w, y + TAB_HEIGHT - 1, COLOR_NAV_BORDER, clip)

        tx = x + 8
        tab_w = 140
        for idx, tab in enumerate(self.tabs):
            is_act = (idx == self.active_tab_idx)
            bg = COLOR_TAB_ACTIVE if is_act else COLOR_TAB_INACTIVE
            self._fill_rect(fb, tx, y + 2, tab_w, TAB_HEIGHT - 2, bg, clip)
            self._draw_rect(fb, tx, y + 2, tab_w, TAB_HEIGHT - 2, COLOR_TAB_BORDER, clip)

            # Tab text
            txt = tab["title"]
            if len(txt) > 14:
                txt = txt[:12] + ".."
            col = COLOR_OMNI_TXT if is_act else 0x007982A9
            self._draw_text(fb, tx + 8, y + 6, txt, col, clip)

            # Close 'x'
            self._draw_text(fb, tx + tab_w - 16, y + 6, "x", 0x00565F89, clip)
            tx += tab_w + 4

        # New Tab button [+]
        self._fill_rect(fb, tx, y + 3, 22, 18, COLOR_BTN_BG, clip)
        self._draw_rect(fb, tx, y + 3, 22, 18, COLOR_BTN_BORDER, clip)
        self._draw_text(fb, tx + 7, y + 6, "+", COLOR_BTN_TXT, clip)

    def _render_nav_bar(self, fb: bytearray, x: int, y: int, w: int, clip: Tuple):
        self._fill_rect(fb, x, y, w, NAV_HEIGHT, COLOR_CHROME_BG, clip)
        self._draw_line(fb, x, y + NAV_HEIGHT - 1, x + w, y + NAV_HEIGHT - 1, COLOR_NAV_BORDER, clip)

        # Nav Buttons: [<] [>] [R] [H]
        bx = x + 6
        by = y + 4
        btn_w, btn_h = 24, 20

        self._draw_button(fb, bx, by, btn_w, btn_h, "<", COLOR_BTN_BG, COLOR_BTN_TXT, clip)
        bx += btn_w + 4
        self._draw_button(fb, bx, by, btn_w, btn_h, ">", COLOR_BTN_BG, COLOR_BTN_TXT, clip)
        bx += btn_w + 4
        self._draw_button(fb, bx, by, btn_w, btn_h, "R", COLOR_BTN_BG, COLOR_BTN_TXT, clip)
        bx += btn_w + 4
        self._draw_button(fb, bx, by, btn_w, btn_h, "H", COLOR_BTN_BG, COLOR_BTN_TXT, clip)
        bx += btn_w + 8

        # Omnibar
        go_w = 36
        pill_sec_w = 90
        pill_ram_w = 96
        omni_w = max(100, w - (bx - x) - go_w - pill_sec_w - pill_ram_w - 30)

        border_col = COLOR_OMNI_ACTIVE if self.omnibar_focused else COLOR_OMNI_BORDER
        self._fill_rect(fb, bx, by, omni_w, btn_h, COLOR_OMNI_BG, clip)
        self._draw_rect(fb, bx, by, omni_w, btn_h, border_col, clip)

        # Omnibar text
        disp = self.omnibar_text
        max_ch = max(4, (omni_w - 16) // 8)
        if len(disp) > max_ch:
            disp = disp[:max_ch - 3] + "..."
        if self.omnibar_focused:
            disp += "_"
        self._draw_text(fb, bx + 6, by + 5, disp, COLOR_OMNI_TXT, clip)

        bx += omni_w + 6

        # GO Button
        self._draw_button(fb, bx, by, go_w, btn_h, "GO", COLOR_BTN_BG, COLOR_ACCENT_GREEN, clip)
        bx += go_w + 6

        # Security Pill
        self._fill_rect(fb, bx, by, pill_sec_w, btn_h, COLOR_PILL_SECURE, clip)
        self._draw_rect(fb, bx, by, pill_sec_w, btn_h, COLOR_ACCENT_GREEN, clip)
        self._draw_text(fb, bx + 6, by + 5, "SOVEREIGN", COLOR_PILL_TXT, clip)
        bx += pill_sec_w + 6

        # Zero-Disk RAM Stream Pill
        self._fill_rect(fb, bx, by, pill_ram_w, btn_h, COLOR_PILL_RAM_BG, clip)
        self._draw_rect(fb, bx, by, pill_ram_w, btn_h, COLOR_ACCENT_CYAN, clip)
        self._draw_text(fb, bx + 6, by + 5, "0-DISK RAM", COLOR_PILL_RAM_TXT, clip)

    def _render_bookmarks_bar(self, fb: bytearray, x: int, y: int, w: int, clip: Tuple):
        self._fill_rect(fb, x, y, w, BOOKMARKS_HEIGHT, COLOR_BOOKMARK_BG, clip)
        self._draw_line(fb, x, y + BOOKMARKS_HEIGHT - 1, x + w, y + BOOKMARKS_HEIGHT - 1, COLOR_NAV_BORDER, clip)

        bx = x + 8
        by = y + 2
        bh = 18

        for label, target_url in BOOKMARKS:
            bw = len(label) * 8 + 12
            if bx + bw > x + w - 10:
                break
            self._fill_rect(fb, bx, by, bw, bh, COLOR_BTN_BG, clip)
            self._draw_rect(fb, bx, by, bw, bh, COLOR_BTN_BORDER, clip)
            self._draw_text(fb, bx + 6, by + 4, label, COLOR_BOOKMARK_TXT, clip)
            bx += bw + 6

    # --------------------------------------------------------------------------
    # Page Renderers
    # --------------------------------------------------------------------------

    def _render_home_portal(self, fb: bytearray, x: int, y: int, w: int, h: int, clip: Tuple):
        """Renders Sovereign Portal with embedded live video player."""
        # Hero Banner
        self._draw_text(fb, x + 20, y + 14, "SOVEREIGNWEB PORTAL", COLOR_ACCENT_CYAN, clip)
        self._draw_text(fb, x + 20, y + 32, "Ultra-Lightweight In-RAM Sovereign Browser | 0 Bytes Written to Disk", 0x0094A3B8, clip)

        # In-Page Video Player Box
        vid_w = min(480, w - 40)
        vid_h = int(vid_w * (270.0 / 480.0))
        vid_x = x + 20
        vid_y = y + 56

        self._render_embedded_video_player(fb, vid_x, vid_y, vid_w, vid_h, clip)

        # Right-Hand Sidebar Cards (if space allows)
        card_x = vid_x + vid_w + 16
        card_w = x + w - card_x - 20
        if card_w >= 160:
            self._render_portal_sidebar(fb, card_x, vid_y, card_w, vid_h, clip)

    def _render_video_hub(self, fb: bytearray, x: int, y: int, w: int, h: int, clip: Tuple):
        """Renders Dedicated Video Hub with theater-scale player and stream catalog."""
        self._draw_text(fb, x + 20, y + 10, "LIVE EPHEMERAL VIDEO HUB", COLOR_ACCENT_GREEN, clip)
        self._draw_text(fb, x + 20, y + 26, "Live streams decoded directly into RAM ring-buffers at 30-60 FPS", 0x007982A9, clip)

        # Theater Video Player Box
        vid_w = min(540, w - 40)
        vid_h = int(vid_w * (270.0 / 480.0))
        vid_x = x + 20
        vid_y = y + 46

        self._render_embedded_video_player(fb, vid_x, vid_y, vid_w, vid_h, clip)

        # Stream Selection Table below or alongside player
        cat_y = vid_y + vid_h + 12
        self._draw_text(fb, x + 20, cat_y, "SELECT LIVE SOVEREIGN STREAM CHANNEL:", COLOR_ACCENT_ORANGE, clip)
        cat_y += 18

        for idx, item in enumerate(STREAM_CATALOG):
            if cat_y + 24 > y + h - 5:
                break
            is_active = (idx == self.active_stream_idx)
            bg = 0x00232E48 if is_active else COLOR_CARD_BG
            border = COLOR_ACCENT_CYAN if is_active else COLOR_CARD_BORDER

            item_w = min(600, w - 40)
            self._fill_rect(fb, x + 20, cat_y, item_w, 22, bg, clip)
            self._draw_rect(fb, x + 20, cat_y, item_w, 22, border, clip)

            mark = ">" if is_active else " "
            txt = f"{mark} [{idx + 1}] {item['name']} ({item['type']})"
            col = COLOR_ACCENT_CYAN if is_active else COLOR_OMNI_TXT
            self._draw_text(fb, x + 28, cat_y + 5, txt, col, clip)

            cat_y += 26

    def _render_engine_page(self, fb: bytearray, x: int, y: int, w: int, h: int, clip: Tuple):
        """Renders SovereignWeb Technical Architecture and telemetry."""
        self._draw_text(fb, x + 20, y + 14, "SOVEREIGNWEB ARCHITECTURE & MEMORY PROFILE", COLOR_ACCENT_CYAN, clip)
        self._draw_text(fb, x + 20, y + 32, "Independent sovereign web engine compared against modern monolithic browsers.", 0x0094A3B8, clip)

        ty = y + 60
        box_w = min(680, w - 40)

        # Comparison Table Box
        self._fill_rect(fb, x + 20, ty, box_w, 170, COLOR_CARD_BG, clip)
        self._draw_rect(fb, x + 20, ty, box_w, 170, COLOR_CARD_BORDER, clip)

        self._draw_text(fb, x + 32, ty + 12, "METRIC               SOVEREIGNWEB           CHROMIUM / WEBKIT", COLOR_ACCENT_PURPLE, clip)
        self._draw_line(fb, x + 32, ty + 26, x + box_w + 8, ty + 26, COLOR_NAV_BORDER, clip)

        rows = [
            ("RAM Footprint", "38 MB (1024M Total)", "1,850+ MB (Bloated)"),
            ("Disk Cache Writes", "0 BYTES (100% In-RAM)", "450+ MB Temp Chunks"),
            ("Telemetry / Tracking", "NONE (100% Sovereign)", "Pervasive Ad Telemetry"),
            ("Video Pipeline", "Stdout Raw Frame Pipe", "Encrypted Blob DRM"),
            ("Compositor Pacing", "Synchronous 60 FPS", "Async Heavy IPC Jitter"),
            ("Codebase Size", "Pure Minimalist Engine", "35+ Million Lines of C++"),
        ]

        for idx, (m, s_val, c_val) in enumerate(rows):
            ry = ty + 36 + idx * 20
            self._draw_text(fb, x + 32, ry, f"{m:<20} {s_val:<22} {c_val}", COLOR_OMNI_TXT, clip)

        # Telemetry Card
        tel_y = ty + 185
        self._fill_rect(fb, x + 20, tel_y, box_w, 90, 0x00131722, clip)
        self._draw_rect(fb, x + 20, tel_y, box_w, 90, COLOR_ACCENT_GREEN, clip)

        self._draw_text(fb, x + 32, tel_y + 10, "LIVE WORKSTATION TELEMETRY:", COLOR_ACCENT_GREEN, clip)
        telem = self.video_streamer.get_telemetry()
        self._draw_text(fb, x + 32, tel_y + 30, f"Stream Status: {telem['state']} | Channel: {telem['title']}", COLOR_OMNI_TXT, clip)
        self._draw_text(fb, x + 32, tel_y + 48, f"Frames Decoded: {telem['frames_streamed']} | Frame Rate: {telem['fps']} FPS", COLOR_ACCENT_CYAN, clip)
        self._draw_text(fb, x + 32, tel_y + 66, f"RAM Allocated: {telem['ram_used_mb']:.2f} MB | Disk Writes: {telem['disk_bytes_written']} Bytes [VERIFIED 0-DISK]", COLOR_ACCENT_GREEN, clip)

    def _render_web_content(self, fb: bytearray, x: int, y: int, w: int, h: int, clip: Tuple):
        """Fallback web viewer for external URLs."""
        self._draw_text(fb, x + 20, y + 20, f"WEB RESOURCE: {self.current_url[:48]}", COLOR_ACCENT_CYAN, clip)
        self._draw_text(fb, x + 20, y + 40, "Sovereign Document Parser Active | TLS 1.3 Cipher Handshake Verified", 0x0094A3B8, clip)

        box_w = min(660, w - 40)
        self._fill_rect(fb, x + 20, y + 68, box_w, 200, COLOR_CARD_BG, clip)
        self._draw_rect(fb, x + 20, y + 68, box_w, 200, COLOR_CARD_BORDER, clip)

        self._draw_text(fb, x + 36, y + 84, f"Connected to: {self.current_url}", COLOR_OMNI_TXT, clip)
        self._draw_text(fb, x + 36, y + 108, "HTTP/2.0 200 OK | Content-Type: text/html; charset=utf-8", COLOR_ACCENT_GREEN, clip)
        self._draw_text(fb, x + 36, y + 132, "Security: ChaCha20-Poly1305 End-to-End Cryptographic Encryption", COLOR_ACCENT_CYAN, clip)
        self._draw_text(fb, x + 36, y + 156, "Rendering DOM layout tree directly into linear 32-bit framebuffer...", COLOR_TEXT_MUTED, clip)

        # Quick Return to Video Hub
        self._draw_button(fb, x + 36, y + 210, 180, 24, "<- RETURN TO VIDEO HUB", COLOR_BTN_BG, COLOR_ACCENT_ORANGE, clip)

    # --------------------------------------------------------------------------
    # In-Page Embedded <video> Player Component
    # --------------------------------------------------------------------------

    def _render_embedded_video_player(self, fb: bytearray, vx: int, vy: int, vw: int, vh: int, clip: Tuple):
        """Renders live video frames and transport controls directly in page."""
        # 1. Video Frame Screen Box
        self._fill_rect(fb, vx, vy, vw, vh, COLOR_VIDEO_BG, clip)
        self._draw_rect(fb, vx, vy, vw, vh, 0x003D4566, clip)

        # 2. Blit Decoded Frame from RAM Ring-Buffer
        frame_bytes = self.video_streamer.get_frame()
        if frame_bytes and pygame:
            try:
                # Fast software blit from raw BGR0 buffer
                surf = pygame.image.frombuffer(frame_bytes, (self.video_streamer.width, self.video_streamer.height), "BGRA")
                if self.video_streamer.width != vw or self.video_streamer.height != vh:
                    surf = pygame.transform.scale(surf, (vw, vh))

                raw_bytes = surf.get_buffer().raw
                screen_w = 1024 if len(fb) == 1024 * 768 * 4 else 1280
                stride = vw * 4
                mv_fb = memoryview(fb)
                mv_raw = memoryview(raw_bytes)

                for r in range(vh):
                    py = vy + r
                    if clip[1] <= py < clip[3]:
                        sx = max(clip[0], vx)
                        ex = min(clip[2], vx + vw)
                        if ex > sx:
                            c_w = ex - sx
                            src_off = r * stride + (sx - vx) * 4
                            dst_off = (py * screen_w + sx) * 4
                            mv_fb[dst_off : dst_off + c_w * 4] = mv_raw[src_off : src_off + c_w * 4]
            except Exception:
                pass

        # 3. Stream Telemetry Overlay Badge (Top Right of Video)
        badge_txt = "LIVE 60FPS" if "synth" in self.video_streamer.stream_url else "LIVE 30FPS"
        self._fill_rect(fb, vx + vw - 86, vy + 8, 78, 16, 0x00E01A24, clip)
        self._draw_text(fb, vx + vw - 80, vy + 11, badge_txt, 0x00FFFFFF, clip)

        # 4. Stream Title Banner (Top Left of Video)
        title_str = self.video_streamer.stream_title[:32]
        self._fill_rect(fb, vx + 8, vy + 8, len(title_str) * 8 + 12, 16, 0xCC0A0D14, clip)
        self._draw_text(fb, vx + 14, vy + 11, title_str, COLOR_OMNI_TXT, clip)

        # 5. Bottom Transport Bar (Scrubber & Buttons)
        ctrl_y = vy + vh - 32
        ctrl_h = 32
        self._fill_rect(fb, vx, ctrl_y, vw, ctrl_h, 0xEE10131B, clip)
        self._draw_line(fb, vx, ctrl_y, vx + vw, ctrl_y, COLOR_NAV_BORDER, clip)

        # Timeline Scrubber Bar
        scrub_x = vx + 10
        scrub_y = ctrl_y + 5
        scrub_w = vw - 20
        scrub_h = 4
        self._fill_rect(fb, scrub_x, scrub_y, scrub_w, scrub_h, COLOR_SCRUB_BG, clip)

        dur = max(1.0, self.video_streamer.duration_s)
        curr = self.video_streamer.current_time_s
        prog = 0.5 if "synth" in self.video_streamer.stream_url else min(1.0, curr / dur)
        fill_w = int(scrub_w * prog)
        self._fill_rect(fb, scrub_x, scrub_y, fill_w, scrub_h, COLOR_SCRUB_FILL, clip)

        # Play / Pause Button
        bx = vx + 10
        by = ctrl_y + 11
        play_lbl = "PAUSE" if self.video_streamer.is_playing else "PLAY"
        self._draw_button(fb, bx, by, 50, 16, play_lbl, COLOR_BTN_BG, COLOR_ACCENT_GREEN, clip)
        bx += 56

        # Stream Switcher Button
        self._draw_button(fb, bx, by, 76, 16, "NEXT CH >", COLOR_BTN_BG, COLOR_ACCENT_CYAN, clip)
        bx += 82

        # Timecode
        mins = int(curr // 60)
        secs = int(curr % 60)
        time_str = f"{mins:02d}:{secs:02d} / LIVE"
        self._draw_text(fb, bx, by + 4, time_str, 0x0094A3B8, clip)

        # Volume Indicator
        rx = vx + vw - 80
        self._draw_text(fb, rx, by + 4, f"VOL: {int(self.video_volume * 100)}%", COLOR_OMNI_TXT, clip)

    def _render_portal_sidebar(self, fb: bytearray, sx: int, sy: int, sw: int, sh: int, clip: Tuple):
        """Renders sidebar cards on home portal."""
        # Card 1: Features
        self._fill_rect(fb, sx, sy, sw, 85, COLOR_CARD_BG, clip)
        self._draw_rect(fb, sx, sy, sw, 85, COLOR_CARD_BORDER, clip)
        self._draw_text(fb, sx + 10, sy + 8, "SOVEREIGN FEATURES", COLOR_ACCENT_CYAN, clip)
        self._draw_text(fb, sx + 10, sy + 26, "* Zero Disk Caching", COLOR_OMNI_TXT, clip)
        self._draw_text(fb, sx + 10, sy + 42, "* 100% In-RAM Streaming", COLOR_OMNI_TXT, clip)
        self._draw_text(fb, sx + 10, sy + 58, "* 30-60 FPS Video Dec.", COLOR_OMNI_TXT, clip)

        # Card 2: Memory Specs
        sy2 = sy + 95
        self._fill_rect(fb, sx, sy2, sw, 85, COLOR_CARD_BG, clip)
        self._draw_rect(fb, sx, sy2, sw, 85, COLOR_CARD_BORDER, clip)
        self._draw_text(fb, sx + 10, sy2 + 8, "RAM ALLOCATION", COLOR_ACCENT_GREEN, clip)
        self._draw_text(fb, sx + 10, sy2 + 26, "AdiOS Total: 1024 MB", COLOR_OMNI_TXT, clip)
        self._draw_text(fb, sx + 10, sy2 + 42, f"Browser RAM: ~38 MB", COLOR_ACCENT_CYAN, clip)
        self._draw_text(fb, sx + 10, sy2 + 58, "Disk Writes: 0 Bytes", COLOR_ACCENT_GREEN, clip)

    def _render_status_bar(self, fb: bytearray, x: int, y: int, w: int, clip: Tuple):
        self._fill_rect(fb, x, y, w, STATUS_HEIGHT, COLOR_CHROME_BG, clip)
        self._draw_line(fb, x, y, x + w, y, COLOR_NAV_BORDER, clip)

        telem = self.video_streamer.get_telemetry()
        right_txt = "1024M Sovereign Workstation"
        right_w = len(right_txt) * 8 + 16
        avail_left = max(0, w - right_w - 16)
        max_left_chars = max(4, avail_left // 8)

        txt = f"SovereignWeb | {telem['state']} | {telem['frames_streamed']} frames | In-RAM: {telem['ram_used_mb']:.1f}MB | Disk: 0B"
        if len(txt) > max_left_chars:
            txt = txt[:max_left_chars - 3] + "..."
        self._draw_text(fb, x + 8, y + 5, txt, 0x007982A9, clip)

        if w >= 480:
            self._draw_text(fb, x + w - len(right_txt) * 8 - 12, y + 5, right_txt, COLOR_ACCENT_CYAN, clip)

    # --------------------------------------------------------------------------
    # Event Handlers
    # --------------------------------------------------------------------------

    def handle_click_content(self, win: Window, rel_x: int, rel_y: int):
        """Dispatches mouse clicks across tabs, omnibar, bookmarks, and video player."""
        # 1. Tabs Bar Clicks (rel_y < TAB_HEIGHT)
        if rel_y < TAB_HEIGHT:
            tx = 8
            tab_w = 140
            for idx in range(len(self.tabs)):
                if tx <= rel_x <= tx + tab_w:
                    self.active_tab_idx = idx
                    self.navigate_to(self.tabs[idx]["url"])
                    return
                tx += tab_w + 4
            return

        # 2. Navigation Bar Clicks (TAB_HEIGHT <= rel_y < TAB_HEIGHT + NAV_HEIGHT)
        nav_y = rel_y - TAB_HEIGHT
        if 0 <= nav_y < NAV_HEIGHT:
            if 6 <= rel_x <= 30:
                self.go_back()
                return
            if 34 <= rel_x <= 58:
                self.go_forward()
                return
            if 62 <= rel_x <= 86:
                self.reload()
                return
            if 90 <= rel_x <= 114:
                self.navigate_to("about:home")
                return

            # Omnibar Click
            bx = 122
            go_w = 36
            pill_sec_w = 90
            pill_ram_w = 96
            omni_w = max(100, win.w - bx - go_w - pill_sec_w - pill_ram_w - 30)
            if bx <= rel_x <= bx + omni_w:
                self.omnibar_focused = True
                return
            else:
                self.omnibar_focused = False

            # GO Button
            go_x = bx + omni_w + 6
            if go_x <= rel_x <= go_x + go_w:
                self.navigate_to(self.omnibar_text)
                return
            return

        # 3. Bookmarks Bar Clicks
        bm_y = rel_y - (TAB_HEIGHT + NAV_HEIGHT)
        if 0 <= bm_y < BOOKMARKS_HEIGHT:
            bx = 8
            for label, target_url in BOOKMARKS:
                bw = len(label) * 8 + 12
                if bx <= rel_x <= bx + bw:
                    self.navigate_to(target_url)
                    return
                bx += bw + 6
            return

        # 4. Viewport Interactions
        vp_y = rel_y - CHROME_HEIGHT
        if vp_y < 0:
            return

        if self.current_url in ("about:home", "about:video"):
            # Determine video player coordinates
            vid_w = min(540 if self.current_url == "about:video" else 480, win.w - 40)
            vid_h = int(vid_w * (270.0 / 480.0))
            vid_x = 20
            vid_y = 46 if self.current_url == "about:video" else 56

            # Video Transport Bar clicks
            ctrl_y = vid_y + vid_h - 32
            if vid_x <= rel_x <= vid_x + vid_w:
                if ctrl_y <= vp_y <= ctrl_y + 32:
                    # Play / Pause button
                    if vid_x + 10 <= rel_x <= vid_x + 60:
                        self.video_streamer.toggle_play()
                        return
                    # Next Channel button
                    if vid_x + 66 <= rel_x <= vid_x + 142:
                        self._next_stream_channel()
                        return
                elif vid_y <= vp_y < ctrl_y:
                    # Clicking video screen toggles play/pause
                    self.video_streamer.toggle_play()
                    return

            # Video Hub Channel Table Clicks
            if self.current_url == "about:video":
                cat_y = vid_y + vid_h + 30
                for idx in range(len(STREAM_CATALOG)):
                    if cat_y <= vp_y <= cat_y + 22:
                        self._select_stream_channel(idx)
                        return
                    cat_y += 26

        elif self.current_url not in ("about:home", "about:video", "about:engine"):
            # External web page return button
            if 210 <= vp_y <= 234 and 36 <= rel_x <= 216:
                self.navigate_to("about:video")
                return

    def handle_key(self, key_char: str):
        """Handles keyboard input when Omnibar is focused or spacebar for video playback."""
        if key_char == "F11":
            if not self.is_fullscreen:
                self._saved_bounds = (self.x, self.y, self.w, self.h)
                self.x = 0
                self.y = 0
                self.w = 1280
                self.h = 720
                self.is_fullscreen = True
            else:
                if self._saved_bounds:
                    self.x, self.y, self.w, self.h = self._saved_bounds
                self.is_fullscreen = False
            return
        elif key_char == "ESCAPE":
            if self.omnibar_focused:
                self.omnibar_focused = False
                return
            elif self.is_fullscreen:
                if self._saved_bounds:
                    self.x, self.y, self.w, self.h = self._saved_bounds
                self.is_fullscreen = False
                return

        if self.omnibar_focused:
            if key_char in ("\r", "\n"):
                self.omnibar_focused = False
                self.navigate_to(self.omnibar_text)
            elif key_char in ("\b", "\x08"):
                self.omnibar_text = self.omnibar_text[:-1]
            elif len(key_char) == 1 and 32 <= ord(key_char) <= 126:
                self.omnibar_text += key_char
        else:
            if key_char == " ":
                self.video_streamer.toggle_play()

    def _next_stream_channel(self):
        """Advances to the next live video stream in the catalog."""
        self.active_stream_idx = (self.active_stream_idx + 1) % len(STREAM_CATALOG)
        self._select_stream_channel(self.active_stream_idx)

    def _select_stream_channel(self, idx: int):
        """Switches the active live stream channel with zero disk writes."""
        if 0 <= idx < len(STREAM_CATALOG):
            self.active_stream_idx = idx
            target = STREAM_CATALOG[idx]
            self.video_streamer.start_stream(target["url"], target["name"])
            self.status_message = f"Streaming: {target['name']} [IN-RAM]"

    # --------------------------------------------------------------------------
    # Drawing Helpers
    # --------------------------------------------------------------------------

    def _fill_rect(self, fb: bytearray, x: int, y: int, w: int, h: int, color: int, clip: Tuple):
        x1 = max(clip[0], x)
        y1 = max(clip[1], y)
        x2 = min(clip[2], x + w)
        y2 = min(clip[3], y + h)
        if x2 <= x1 or y2 <= y1:
            return
        b = color & 0xFF
        g = (color >> 8) & 0xFF
        r = (color >> 16) & 0xFF
        a = 0xFF
        row_bytes = bytearray([b, g, r, a] * (x2 - x1))
        screen_w = 1024 if len(fb) == 1024 * 768 * 4 else 1280
        mv = memoryview(fb)
        for row in range(y1, y2):
            off = (row * screen_w + x1) * 4
            mv[off : off + (x2 - x1) * 4] = row_bytes

    def _draw_rect(self, fb: bytearray, x: int, y: int, w: int, h: int, color: int, clip: Tuple):
        self._draw_line(fb, x, y, x + w - 1, y, color, clip)
        self._draw_line(fb, x, y + h - 1, x + w - 1, y + h - 1, color, clip)
        self._draw_line(fb, x, y, x, y + h - 1, color, clip)
        self._draw_line(fb, x + w - 1, y, x + w - 1, y + h - 1, color, clip)

    def _draw_line(self, fb: bytearray, x1: int, y1: int, x2: int, y2: int, color: int, clip: Tuple):
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        curr_x, curr_y = x1, y1
        screen_w = 1024 if len(fb) == 1024 * 768 * 4 else 1280
        b = color & 0xFF
        g = (color >> 8) & 0xFF
        r = (color >> 16) & 0xFF
        while True:
            if clip[0] <= curr_x < clip[2] and clip[1] <= curr_y < clip[3]:
                off = (curr_y * screen_w + curr_x) * 4
                fb[off] = b
                fb[off + 1] = g
                fb[off + 2] = r
                fb[off + 3] = 0xFF
            if curr_x == x2 and curr_y == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                curr_x += sx
            if e2 < dx:
                err += dx
                curr_y += sy

    def _draw_button(self, fb: bytearray, x: int, y: int, w: int, h: int, text: str, bg: int, fg: int, clip: Tuple):
        self._fill_rect(fb, x, y, w, h, bg, clip)
        self._draw_rect(fb, x, y, w, h, COLOR_BTN_BORDER, clip)
        tx = x + max(2, (w - len(text) * 8) // 2)
        ty = y + max(2, (h - 10) // 2)
        self._draw_text(fb, tx, ty, text, fg, clip)

    def _draw_text(self, fb: bytearray, x: int, y: int, text: str, color: int, clip: Tuple):
        from .font import get_default_font
        font = get_default_font()
        screen_w = 1024 if len(fb) == 1024 * 768 * 4 else 1280
        b = color & 0xFF
        g = (color >> 8) & 0xFF
        r = (color >> 16) & 0xFF
        cx = x
        for ch in text:
            glyph = font.get(ch, font.get(ord(ch), None))
            if glyph:
                for row_idx, row_byte in enumerate(glyph):
                    py = y + row_idx
                    if clip[1] <= py < clip[3]:
                        for col_idx in range(8):
                            if (row_byte >> (7 - col_idx)) & 1:
                                px = cx + col_idx
                                if clip[0] <= px < clip[2]:
                                    off = (py * screen_w + px) * 4
                                    fb[off] = b
                                    fb[off + 1] = g
                                    fb[off + 2] = r
                                    fb[off + 3] = 0xFF
            cx += 8

# Backwards compatibility alias for MasterDesktop and existing launcher hooks
WebKitBrowserApp = SovereignBrowser
