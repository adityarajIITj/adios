#!/usr/bin/env python3
"""
AdiOS Sovereign YouTube Desktop Player Application (desktop/youtube_player.py)
A high-performance 30 FPS windowed media player for the AdiOS Workstation:
- Native Widescreen Video Viewport with VPU Hardware Controller Integration
- REAL YouTube Video Streaming via yt-dlp + ffmpeg Pipeline
- Live Internet & World YouTube Video Streaming with Download Progress
- Interactive URL Text Box: Typing, Backspace, Load, Enter keydown routing
- Real-time Network Status Indicator: [NET: ONLINE] / [NET: OFFLINE]
- Interactive Transport Bar: Play, Pause, Seek, Volume, and Quick-Select Catalog
- Telemetry HUD: Realtime FPS, Presentation Timestamp, and Buffer Gauge

STRICT ZERO EMOJI POLICY ENFORCED.
"""

import time
from typing import Optional, Tuple, Dict, Any
from vm.vpu import VPU, CMD_PLAY, CMD_PAUSE, CMD_STOP, CMD_SEEK, STATUS_PLAYING
from net.yt_relay import YouTubeStreamRelay, WORLD_VIDEOS, extract_youtube_id, STREAM_DOWNLOADING, STREAM_STREAMING, STREAM_ERROR, STREAM_DECODING, STREAM_IDLE


def get_system_clipboard_text() -> str:
    """
    Reads text from host operating system clipboard with zero external dependencies.
    Uses Windows Win32 API via standard ctypes with 64-bit pointer safety, with Tkinter fallback.
    """
    # 1. Direct Windows Win32 API via standard ctypes with 64-bit pointer types
    try:
        import ctypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_bool
        user32.GetClipboardData.argtypes = [ctypes.c_uint]
        user32.GetClipboardData.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = ctypes.c_bool
        user32.CloseClipboard.argtypes = []
        user32.CloseClipboard.restype = ctypes.c_bool

        if user32.OpenClipboard(None):
            try:
                # 13 = CF_UNICODETEXT
                h_data = user32.GetClipboardData(13)
                if h_data:
                    ptr = kernel32.GlobalLock(h_data)
                    if ptr:
                        try:
                            txt = ctypes.c_wchar_p(ptr).value
                            if txt:
                                return str(txt)
                        finally:
                            kernel32.GlobalUnlock(h_data)
            finally:
                user32.CloseClipboard()
    except Exception:
        pass

    # 2. Tkinter clipboard fallback
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        txt = root.clipboard_get()
        root.destroy()
        if txt:
            return str(txt)
    except Exception:
        pass

    return ""


class YouTubePlayerApp:
    """
    Sovereign YouTube 30 FPS Windowed Player Application.
    Supports live network streaming, interactive URL input, and world video catalog.
    """
    def __init__(self, vpu: Optional[VPU] = None, initial_channel: Optional[int] = None):
        # Determine geometry from vpu or default to 640x360 @ 60 FPS HD
        target_w = vpu.width if vpu is not None else 640
        target_h = vpu.height if vpu is not None else 360
        target_fps = vpu.fps if vpu is not None else 60

        self.is_hd = (target_w >= 600)

        # Connect or initialize VPU and stream relay
        init_idx = initial_channel if initial_channel is not None else (3 if self.is_hd else 0)
        self.relay = YouTubeStreamRelay(init_idx)
        if vpu is not None:
            self.vpu = vpu
            self.vpu.relay = self.relay
        else:
            self.vpu = VPU(width=target_w, height=target_h, fps=target_fps)
            self.vpu.relay = self.relay

        if self.is_hd:
            self.width = 680
            self.height = 490
            self.title = "Sovereign YouTube Player (60 FPS HD)"
            self.video_x = 20
            self.video_y = 52
            self.video_w = 640
            self.video_h = 360
            self.scrub_x = 20
            self.scrub_y = 420
            self.scrub_w = 640
            self.scrub_h = 8
            self.btn_y = 438
            self.btn_h = 26

            # Top Header Rectangles
            self.rect_brand = (10, 10, 126, 24)
            self.rect_url   = (144, 10, 310, 24)
            self.rect_paste = (462, 10, 56, 24)
            self.rect_load  = (524, 10, 56, 24)
            self.rect_net   = (588, 10, 80, 24)

            # Transport Buttons Layout (Row at y = 438, h = 26)
            self.btn_play  = (16, 438, 56, 26)   # Play / Pause
            self.btn_ch1   = (78, 438, 86, 26)   # Rick Astley (channel 3)
            self.btn_ch2   = (170, 438, 92, 26)  # Bunny 60FPS (channel 5)
            self.btn_ch3   = (268, 438, 86, 26)  # Lofi Beats (channel 7)
            self.btn_cyber = (360, 438, 76, 26)  # Cyber 3D (channel 0)
            self.btn_vol   = (442, 438, 68, 26)  # Volume
            self.btn_sound = (516, 438, 68, 26)  # Sound toggle: [SND:ON] / [MUTED]
            self.btn_qual  = (590, 438, 78, 26)  # [60 FPS HD]
        else:
            self.width = 520
            self.height = 420
            self.title = "Sovereign YouTube Player (30 FPS)"
            self.video_x = 20
            self.video_y = 65
            self.video_w = 480
            self.video_h = 270
            self.scrub_x = 20
            self.scrub_y = 338
            self.scrub_w = 480
            self.scrub_h = 8
            self.btn_y = 356
            self.btn_h = 24

            # Top Header Rectangles
            self.rect_brand = (6, 10, 114, 22)
            self.rect_url   = (124, 10, 210, 22)
            self.rect_paste = (338, 10, 48, 22)
            self.rect_load  = (390, 10, 48, 22)
            self.rect_net   = (442, 10, 70, 22)

            # Transport Buttons Layout (Row at y = 356, h = 24)
            self.btn_play  = (16, 356, 56, 24)   # Play / Pause
            self.btn_ch1   = (78, 356, 76, 24)   # Channel 0: RISC-V 3D
            self.btn_ch2   = (160, 356, 76, 24)  # Channel 1: Synthwave
            self.btn_ch3   = (242, 356, 76, 24)  # Channel 2: Matrix
            self.btn_cyber = (242, 356, 76, 24)
            self.btn_vol   = (324, 356, 76, 24)  # Volume cycle
            self.btn_sound = (406, 356, 54, 24)  # Sound toggle: [SND:ON] / [MUTED]
            self.btn_qual  = (466, 356, 46, 24)  # Next catalog video

        # Player UI State
        self.url_text = self.relay.active_url
        self.url_focused = False
        self.is_playing = False
        self.volume = 80
        self.active_catalog_idx = init_idx
        self.status_message = "Ready"

        # Host Sound Output State: Default to Audible in HD mode, quiet in 480 legacy test mode
        self.sound_enabled = True if self.is_hd else False
        if hasattr(self.vpu, "sound_enabled"):
            self.vpu.sound_enabled = self.sound_enabled

        # Auto-start video playback on launch
        self.play()

    @property
    def active_channel(self) -> int:
        return self.active_catalog_idx

    @active_channel.setter
    def active_channel(self, val: int):
        self.active_catalog_idx = val

    def play(self):
        """Starts 30 FPS playback."""
        self.is_playing = True
        self.vpu.write32(0x30000000, CMD_PLAY)
        if self.sound_enabled:
            self.vpu.play_host_audio()

    def pause(self):
        """Pauses playback."""
        self.is_playing = False
        self.vpu.write32(0x30000000, CMD_PAUSE)
        self.vpu.stop_host_audio()

    def toggle_play(self):
        """Toggles play / pause state."""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def seek_percent(self, pct: float):
        """Seeks to percentage (0.0 - 1.0) of video duration."""
        pct = max(0.0, min(1.0, pct))
        target_ms = int(pct * max(1, self.vpu.duration_ms))
        self.vpu.write32(0x30000024, target_ms)
        self.vpu.write32(0x30000000, CMD_SEEK)

    def select_catalog_video(self, idx: int):
        """Switches to a world catalog video by index."""
        if 0 <= idx < len(WORLD_VIDEOS):
            self.vpu.stop_host_audio()
            self.active_catalog_idx = idx
            v = WORLD_VIDEOS[idx]
            self.url_text = v["url"]
            self.relay.set_channel(idx)
            self.vpu.duration_ms = self.relay.duration_ms
            self.vpu.write32(0x30000024, 0)
            self.vpu.write32(0x30000000, CMD_SEEK)
            self.play()
            self.status_message = f"Playing: {v['title'][:24]}"

    def load_active_url(self):
        """Loads and resolves the currently typed URL in the URL bar."""
        url = self.url_text.strip()
        if not url:
            return
        self.vpu.stop_host_audio()
        success = self.relay.load_url(url)
        if success:
            self.vpu.duration_ms = self.relay.duration_ms
            self.vpu.write32(0x30000024, 0)
            self.vpu.write32(0x30000000, CMD_SEEK)
            self.play()
            self.status_message = f"Loading: {self.relay.channel_info.get('title', 'Video')[:24]}"
        self.url_focused = False

    def close(self):
        """Cleanup resources on application close."""
        self.pause()
        self.vpu.stop_host_audio()
        if hasattr(self.relay, 'cleanup'):
            self.relay.cleanup()

    def cycle_volume(self):
        """Cycles audio volume levels (0%, 30%, 60%, 80%, 100%)."""
        levels = [0, 30, 60, 80, 100]
        curr_idx = levels.index(self.volume) if self.volume in levels else 3
        self.volume = levels[(curr_idx + 1) % len(levels)]
        self.vpu.write32(0x30000028, self.volume)

    def paste_clipboard_url(self) -> bool:
        """Pastes URL directly from system clipboard into the URL bar."""
        txt = get_system_clipboard_text().strip()
        if txt:
            clean = "".join(ch for ch in txt if 32 <= ord(ch) <= 126)
            if clean:
                self.url_text = clean
                self.url_focused = True
                self.status_message = "URL Pasted from clipboard."
                return True
        return False

    def toggle_sound(self):
        """Toggles audible speaker output through physical host audio device."""
        self.sound_enabled = not self.sound_enabled
        if hasattr(self.vpu, "set_sound_enabled"):
            self.vpu.set_sound_enabled(self.sound_enabled)
        try:
            from audio.sound_server import SoundServer
            server = SoundServer.get_instance()
            server.set_muted(not self.sound_enabled)
            if not self.sound_enabled:
                server.stop_all()
        except Exception:
            pass
        self.status_message = f"Speaker Audio: {'ON (Audible)' if self.sound_enabled else 'MUTED'}"

    def handle_key(self, k: str) -> bool:
        """Handles keyboard typing into the URL bar with paste, clear, and audio mute support."""
        if not self.url_focused:
            if k == " ":
                self.toggle_play()
                return True
            elif k in ("m", "M"):
                self.toggle_sound()
                return True
            return False

        # Ctrl+V / Paste string
        if k in ("\x16", "PASTE"):
            self.paste_clipboard_url()
            return True

        # Ctrl+A / Escape / Clear
        if k in ("\x01", "\x1b", "CLEAR"):
            self.url_text = ""
            return True

        # Pasted string from event dispatcher
        if len(k) > 1 and all(32 <= ord(c) <= 126 for c in k):
            if k.startswith("http://") or k.startswith("https://") or "youtube" in k:
                self.url_text = k
            else:
                self.url_text += k
            return True

        if k in ("\r", "\n"):
            self.load_active_url()
            return True
        elif k in ("\b", "\x7f"):
            if len(self.url_text) > 0:
                self.url_text = self.url_text[:-1]
            return True
        elif len(k) == 1 and 32 <= ord(k) <= 126:
            if len(self.url_text) < 180:
                self.url_text += k
            return True
        return False

    def handle_click(self, local_x: int, local_y: int) -> bool:
        """Processes mouse clicks inside application window."""
        # 1. URL Box Click (Focus/Unfocus)
        if self._in_rect(local_x, local_y, self.rect_url):
            self.url_focused = True
            return True
        else:
            self.url_focused = False

        # 1.5 Paste Button Click
        if self._in_rect(local_x, local_y, self.rect_paste):
            if self.paste_clipboard_url():
                self.load_active_url()
            return True

        # 2. Load Button Click
        if self._in_rect(local_x, local_y, self.rect_load):
            self.load_active_url()
            return True

        # 3. Check Scrub Bar click
        if (self.scrub_x <= local_x <= self.scrub_x + self.scrub_w and
            self.scrub_y - 4 <= local_y <= self.scrub_y + self.scrub_h + 4):
            pct = (local_x - self.scrub_x) / float(self.scrub_w)
            self.seek_percent(pct)
            return True

        # 4. Check Play / Pause
        if self._in_rect(local_x, local_y, self.btn_play):
            self.toggle_play()
            return True

        # 4.5 Check Sound Mute / Unmute
        if self._in_rect(local_x, local_y, self.btn_sound):
            self.toggle_sound()
            return True

        # 5. Check Channel Selectors
        if self._in_rect(local_x, local_y, self.btn_ch1):
            target_ch = 3 if self.is_hd else 0  # Rick Astley in HD, RISC-V in 480
            self.select_catalog_video(target_ch)
            return True
        if self._in_rect(local_x, local_y, self.btn_ch2):
            target_ch = 5 if self.is_hd else 1  # Big Buck Bunny in HD, Synthwave in 480
            self.select_catalog_video(target_ch)
            return True
        if self._in_rect(local_x, local_y, self.btn_ch3):
            target_ch = 7 if self.is_hd else 2  # Lofi Beats in HD, Matrix in 480
            self.select_catalog_video(target_ch)
            return True
        if hasattr(self, "btn_cyber") and self._in_rect(local_x, local_y, self.btn_cyber):
            self.select_catalog_video(0)  # RISC-V Cyber 3D
            return True

        # 6. Check Volume Toggle
        if self._in_rect(local_x, local_y, self.btn_vol):
            self.cycle_volume()
            return True

        # 7. Check Next Video in Catalog
        if self._in_rect(local_x, local_y, self.btn_qual):
            next_idx = (self.active_catalog_idx + 1) % len(WORLD_VIDEOS)
            self.select_catalog_video(next_idx)
            return True

        # 8. Check Video Canvas click to toggle play/pause
        if (self.video_x <= local_x <= self.video_x + self.video_w and
            self.video_y <= local_y <= self.video_y + self.video_h):
            self.toggle_play()
            return True

        return False

    def _in_rect(self, x: int, y: int, rect: Tuple[int, int, int, int]) -> bool:
        rx, ry, rw, rh = rect
        return rx <= x <= rx + rw and ry <= y <= ry + rh

    def step(self, now: Optional[float] = None) -> bool:
        """Paces video stream frame at target FPS and transitions to real audio when extracted."""
        if self.sound_enabled and self.is_playing and self.relay:
            real_wav = self.relay.get_audio_wav_path()
            if real_wav and getattr(self.vpu, "_audio_temp_path", None) != real_wav:
                self.vpu.play_host_audio()
        return self.vpu.step(now)

    def render(self, surface_buffer: bytearray, surf_w: int, surf_h: int):
        """
        Renders complete YouTube Player window interface:
        header, search bar, video canvas, scrub bar, and transport controls.
        """
        self.surf_w = surf_w
        self.surf_h = surf_h

        # 1. Fill window background (Dark sovereign aesthetic)
        self._fill_rect(surface_buffer, surf_w, 0, 0, surf_w, surf_h, (18, 18, 22, 255))

        # 2. Render Top Header
        # Brand pill [YT SOVEREIGN]
        self._fill_rect(surface_buffer, surf_w, self.rect_brand[0], self.rect_brand[1],
                         self.rect_brand[2], self.rect_brand[3], (220, 20, 20, 255))
        self._draw_text(surface_buffer, surf_w, self.rect_brand[0] + 4, self.rect_brand[1] + 7,
                         "[YT SOVEREIGN]", (255, 255, 255))

        # Interactive URL Input Box
        rx, ry, rw, rh = self.rect_url
        url_bg = (40, 44, 58, 255) if self.url_focused else (28, 30, 38, 255)
        border_col = (0, 220, 255, 255) if self.url_focused else (60, 65, 80, 255)
        self._fill_rect(surface_buffer, surf_w, rx, ry, rw, rh, url_bg)
        self._stroke_rect(surface_buffer, surf_w, rx, ry, rw, rh, border_col)
        
        disp_url = self.url_text[-30:] if len(self.url_text) > 30 else self.url_text
        if self.url_focused:
            disp_url += "_"
        self._draw_text(surface_buffer, surf_w, rx + 6, ry + 7, disp_url, (200, 220, 240))

        # Paste button
        self._draw_button(surface_buffer, surf_w, self.rect_paste, "PASTE", (45, 75, 140, 255))

        # Load button
        self._draw_button(surface_buffer, surf_w, self.rect_load, "LOAD", (45, 50, 70, 255))

        # Network Status Badge
        online = self.relay.is_online()
        net_text = "ONLINE" if online else "OFFLINE"
        net_col = (20, 140, 60, 255) if online else (160, 100, 20, 255)
        self._draw_button(surface_buffer, surf_w, self.rect_net, net_text, net_col)

        # Video Title & Metadata Line
        ch_info = self.relay.channel_info
        title = ch_info.get("title", "Sovereign Video")
        author = ch_info.get("author", "AdiOS")
        views = ch_info.get("views", "1.2M")
        meta_str = f"{title[:34]} | {author[:18]} | {views}"
        self._draw_text(surface_buffer, surf_w, 18, 36 if self.is_hd else 34, meta_str[:70], (200, 210, 230))

        # 3. Video Viewport Framebuffer DMA Blit
        self._stroke_rect(surface_buffer, surf_w, self.video_x - 1, self.video_y - 1,
                           self.video_w + 2, self.video_h + 2, (70, 75, 95, 255))

        # Perform DMA blit from VPU directly into window surface
        self.vpu.dma_blit_to_surface(surface_buffer, surf_w, surf_h, self.video_x, self.video_y)

        # Video HUD badges (top right of video)
        fps_badge = f"{self.video_w}x{self.video_h} @ {self.vpu.fps} FPS{' HD' if self.is_hd else ''}"
        badge_w = 158 if self.is_hd else 138
        self._fill_rect(surface_buffer, surf_w, self.video_x + self.video_w - badge_w - 6, self.video_y + 8, badge_w, 18, (10, 10, 15, 200))
        self._draw_text(surface_buffer, surf_w, self.video_x + self.video_w - badge_w - 2, self.video_y + 13, fps_badge, (0, 255, 220))

        # 4. Scrub Bar
        self._fill_rect(surface_buffer, surf_w, self.scrub_x, self.scrub_y, self.scrub_w, self.scrub_h, (40, 44, 55, 255))
        buf_pct = min(1.0, (self.vpu.current_pts + 40000) / float(max(1, self.vpu.duration_ms)))
        buf_w = int(self.scrub_w * buf_pct)
        self._fill_rect(surface_buffer, surf_w, self.scrub_x, self.scrub_y, buf_w, self.scrub_h, (70, 75, 90, 255))
        
        play_pct = min(1.0, self.vpu.current_pts / float(max(1, self.vpu.duration_ms)))
        play_w = int(self.scrub_w * play_pct)
        self._fill_rect(surface_buffer, surf_w, self.scrub_x, self.scrub_y, play_w, self.scrub_h, (230, 30, 30, 255))
        knob_x = min(self.scrub_x + self.scrub_w - 4, self.scrub_x + play_w)
        self._fill_rect(surface_buffer, surf_w, knob_x - 3, self.scrub_y - 2, 7, self.scrub_h + 4, (255, 255, 255, 255))

        # 5. Transport Controls Bar
        play_lbl = "PAUSE" if self.is_playing else "PLAY"
        btn_col = (200, 30, 30, 255) if self.is_playing else (40, 160, 80, 255)
        self._draw_button(surface_buffer, surf_w, self.btn_play, play_lbl, btn_col)

        # Host Speaker Sound Toggle Button
        snd_lbl = "SND:ON" if self.sound_enabled else "MUTED"
        snd_col = (20, 140, 60, 255) if self.sound_enabled else (180, 30, 30, 255)
        self._draw_button(surface_buffer, surf_w, self.btn_sound, snd_lbl, snd_col)

        # Channel & World Video Selectors
        if self.is_hd:
            c1_col = (220, 30, 30, 255) if self.active_catalog_idx == 3 else (45, 50, 65, 255)
            c2_col = (120, 200, 40, 255) if self.active_catalog_idx == 5 else (45, 50, 65, 255)
            c3_col = (200, 80, 160, 255) if self.active_catalog_idx == 7 else (45, 50, 65, 255)
            cy_col = (0, 140, 200, 255) if self.active_catalog_idx == 0 else (45, 50, 65, 255)
            self._draw_button(surface_buffer, surf_w, self.btn_ch1, "RICK", c1_col)
            self._draw_button(surface_buffer, surf_w, self.btn_ch2, "BUNNY 60F", c2_col)
            self._draw_button(surface_buffer, surf_w, self.btn_ch3, "LOFI", c3_col)
            if hasattr(self, "btn_cyber"):
                self._draw_button(surface_buffer, surf_w, self.btn_cyber, "CYBER 3D", cy_col)
            qual_lbl = "60 FPS"
        else:
            c1_col = (0, 120, 180, 255) if self.active_catalog_idx == 0 else (45, 50, 65, 255)
            c2_col = (180, 30, 120, 255) if self.active_catalog_idx == 1 else (45, 50, 65, 255)
            c3_col = (30, 140, 50, 255) if self.active_catalog_idx == 2 else (45, 50, 65, 255)
            self._draw_button(surface_buffer, surf_w, self.btn_ch1, "RISC-V", c1_col)
            self._draw_button(surface_buffer, surf_w, self.btn_ch2, "SYNTH", c2_col)
            self._draw_button(surface_buffer, surf_w, self.btn_ch3, "MATRIX", c3_col)
            cat_title = self.relay.channel_info.get("title", "MORE")
            qual_lbl = "MORE" if self.active_catalog_idx < 3 else cat_title[:5].upper()

        # Volume control
        vol_str = f"VOL:{self.volume}%"
        self._draw_button(surface_buffer, surf_w, self.btn_vol, vol_str, (45, 50, 65, 255))

        # World Video Quick Selector button
        self._draw_button(surface_buffer, surf_w, self.btn_qual, qual_lbl, (140, 40, 100, 255))

        # 6. Time & Telemetry Line
        pts_s = self.vpu.current_pts // 1000
        dur_s = self.vpu.duration_ms // 1000
        cur_time_str = f"{pts_s // 60:02d}:{pts_s % 60:02d}"
        dur_time_str = f"{dur_s // 60:02d}:{dur_s % 60:02d}"
        time_display = f"{cur_time_str} / {dur_time_str}"
        telem_y = self.btn_y + self.btn_h + 5
        self._draw_text(surface_buffer, surf_w, 20, telem_y, time_display, (170, 180, 200))

        # Stream status indicator
        stream_st = getattr(self.relay, 'stream_state', STREAM_IDLE)
        if stream_st == STREAM_DOWNLOADING:
            pct = self.relay.download_progress
            status_txt = f"Downloading: {pct:.0f}%"
            status_col = (0, 200, 255)
        elif stream_st == STREAM_DECODING:
            status_txt = "Decoding 60FPS..."
            status_col = (255, 200, 0)
        elif stream_st == STREAM_STREAMING:
            is_real = getattr(self.relay, 'is_real_video_active', False)
            status_txt = "REAL VIDEO 60FPS" if is_real else "STREAMING 60FPS"
            status_col = (0, 255, 120) if is_real else (200, 200, 200)
        elif stream_st == STREAM_ERROR:
            err = getattr(self.relay, '_stream_error_msg', 'Error')
            status_txt = f"ERR: {err[:18]}"
            status_col = (255, 60, 60)
        else:
            status_txt = f"Frames: {self.vpu.frames_played}"
            status_col = (110, 130, 160)

        telemetry_txt = f"{status_txt} | {net_text}"
        self._draw_text(surface_buffer, surf_w, 240 if self.is_hd else 220, telem_y, telemetry_txt[:38], status_col)

        # Update duration from relay if it changed (yt-dlp resolves real duration)
        if self.relay.duration_ms > 0 and self.relay.duration_ms != self.vpu.duration_ms:
            self.vpu.duration_ms = self.relay.duration_ms

    def _draw_button(self, buf: bytearray, pitch_w: int, rect: Tuple[int, int, int, int], text: str, color: Tuple[int, int, int, int]):
        rx, ry, rw, rh = rect
        self._fill_rect(buf, pitch_w, rx, ry, rw, rh, color)
        self._stroke_rect(buf, pitch_w, rx, ry, rw, rh, (min(255, color[0] + 40), min(255, color[1] + 40), min(255, color[2] + 40), 255))
        char_w = 8
        txt_w = len(text) * char_w
        tx = max(rx + 2, rx + (rw - txt_w) // 2)
        ty = ry + (rh - 8) // 2 + 1
        self._draw_text(buf, pitch_w, tx, ty, text, (255, 255, 255))

    def _fill_rect(self, buf: bytearray, pitch_w: int, x: int, y: int, w: int, h: int, color: Tuple[int, int, int, int]):
        r, g, b, a = color
        max_h = getattr(self, "surf_h", self.height)
        max_w = getattr(self, "surf_w", self.width)
        for dy in range(h):
            py = y + dy
            if 0 <= py < max_h:
                row_off = (py * pitch_w + x) * 4
                for dx in range(w):
                    px = x + dx
                    if 0 <= px < max_w:
                        off = row_off + dx * 4
                        if off + 3 < len(buf):
                            buf[off]   = b
                            buf[off+1] = g
                            buf[off+2] = r
                            buf[off+3] = a

    def _stroke_rect(self, buf: bytearray, pitch_w: int, x: int, y: int, w: int, h: int, color: Tuple[int, int, int, int]):
        r, g, b, a = color
        for px in range(x, x + w):
            self._set_pixel(buf, pitch_w, px, y, b, g, r, a)
            self._set_pixel(buf, pitch_w, px, y + h - 1, b, g, r, a)
        for py in range(y, y + h):
            self._set_pixel(buf, pitch_w, x, py, b, g, r, a)
            self._set_pixel(buf, pitch_w, x + w - 1, py, b, g, r, a)

    def _set_pixel(self, buf: bytearray, pitch_w: int, x: int, y: int, b: int, g: int, r: int, a: int):
        max_h = getattr(self, "surf_h", self.height)
        max_w = getattr(self, "surf_w", self.width)
        if 0 <= x < max_w and 0 <= y < max_h:
            off = (y * pitch_w + x) * 4
            if off + 3 < len(buf):
                buf[off]   = b
                buf[off+1] = g
                buf[off+2] = r
                buf[off+3] = a

    def _draw_text(self, buf: bytearray, pitch_w: int, x: int, y: int, text: str, color: Tuple[int, int, int]):
        """Renders ASCII string using standard 8x8 bitmap font."""
        if not hasattr(self, "font") or self.font is None:
            from desktop.font import get_default_font
            self.font = get_default_font()
        r, g, b = color
        curr_x = x
        max_h = getattr(self, "surf_h", self.height)
        max_w = getattr(self, "surf_w", self.width)
        for ch in text:
            if curr_x + 8 > max_w: break
            glyph = self.font.get(ch, self.font.get('?'))
            if glyph:
                for gy in range(8):
                    py = y + gy
                    if 0 <= py < max_h:
                        row_bits = glyph[gy]
                        row_off = (py * pitch_w + curr_x) * 4
                        for gx in range(8):
                            if (row_bits >> (7 - gx)) & 1:
                                off = row_off + gx * 4
                                if off + 3 < len(buf):
                                    buf[off]   = b
                                    buf[off+1] = g
                                    buf[off+2] = r
                                    buf[off+3] = 255
            curr_x += 8
