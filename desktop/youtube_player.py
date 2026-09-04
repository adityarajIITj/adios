#!/usr/bin/env python3
"""
AdiOS Sovereign YouTube Desktop Player Application (desktop/youtube_player.py)
A high-performance 30 FPS windowed media player for the AdiOS Workstation:
- Native 480x270 16:9 widescreen video viewport
- Direct Integration with Hardware MMIO Video Processing Unit (VPU)
- Interactive Transport Bar: Play, Pause, Seek, Volume, Channel Selectors
- Telemetry HUD: Realtime FPS, Presentation Timestamp, and Buffer Gauge

Zero external dependencies. Pure RV32IM workstation window architecture.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

import time
from typing import Optional, Tuple
from vm.vpu import VPU, CMD_PLAY, CMD_PAUSE, CMD_STOP, CMD_SEEK, STATUS_PLAYING
from net.yt_relay import YouTubeStreamRelay, CHANNELS


class YouTubePlayerApp:
    """
    Sovereign YouTube 30 FPS Windowed Player Application.
    """
    def __init__(self, vpu: Optional[VPU] = None):
        self.width = 520
        self.height = 420
        self.title = "Sovereign YouTube Player (30 FPS)"
        
        # Connect or initialize VPU and stream relay
        self.relay = YouTubeStreamRelay(0)
        if vpu is not None:
            self.vpu = vpu
            self.vpu.width = 480
            self.vpu.height = 270
            self.vpu.fps = 30
            self.vpu.relay = self.relay
        else:
            self.vpu = VPU(width=480, height=270, fps=30)
            self.vpu.relay = self.relay

        # Player UI State
        self.url_text = "https://youtube.com/watch?v=riscv_core"
        self.is_playing = False
        self.volume = 80
        self.active_channel = 0
        
        # Geometry layout
        self.video_x = 20
        self.video_y = 65
        self.video_w = 480
        self.video_h = 270
        
        # Progress Scrub Bar Layout
        self.scrub_x = 20
        self.scrub_y = 345
        self.scrub_w = 480
        self.scrub_h = 10
        
        # Transport Buttons Layout
        self.btn_play = (20, 365, 56, 22)
        self.btn_ch1  = (85, 365, 80, 22)
        self.btn_ch2  = (170, 365, 86, 22)
        self.btn_ch3  = (261, 365, 75, 22)
        self.btn_vol  = (345, 365, 78, 22)
        self.btn_qual = (430, 365, 70, 22)
        
        # Auto-start playback on launch
        self.play()

    def play(self):
        """Starts 30 FPS playback."""
        self.is_playing = True
        self.vpu.write32(0x30000000, CMD_PLAY)

    def pause(self):
        """Pauses playback."""
        self.is_playing = False
        self.vpu.write32(0x30000000, CMD_PAUSE)

    def toggle_play(self):
        """Toggles play / pause state."""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def seek_percent(self, pct: float):
        """Seeks to percentage (0.0 - 1.0) of video duration."""
        pct = max(0.0, min(1.0, pct))
        target_ms = int(pct * self.vpu.duration_ms)
        self.vpu.write32(0x30000024, target_ms)
        self.vpu.write32(0x30000000, CMD_SEEK)

    def switch_channel(self, idx: int):
        """Switches active channel and restarts playback."""
        self.active_channel = idx % len(CHANNELS)
        self.relay.set_channel(self.active_channel)
        self.vpu.duration_ms = self.relay.duration_ms
        self.url_text = f"https://youtube.com/watch?v={self.relay.channel_info['id']}"
        self.vpu.write32(0x30000024, 0)
        self.vpu.write32(0x30000000, CMD_SEEK)
        self.play()

    def cycle_volume(self):
        """Cycles audio volume levels (0%, 30%, 60%, 80%, 100%)."""
        levels = [0, 30, 60, 80, 100]
        curr_idx = levels.index(self.volume) if self.volume in levels else 3
        self.volume = levels[(curr_idx + 1) % len(levels)]
        self.vpu.write32(0x30000028, self.volume)

    def handle_click(self, local_x: int, local_y: int) -> bool:
        """Processes mouse clicks inside application window."""
        # Check Scrub Bar click
        if (self.scrub_x <= local_x <= self.scrub_x + self.scrub_w and
            self.scrub_y - 4 <= local_y <= self.scrub_y + self.scrub_h + 4):
            pct = (local_x - self.scrub_x) / float(self.scrub_w)
            self.seek_percent(pct)
            return True

        # Check Play / Pause
        if self._in_rect(local_x, local_y, self.btn_play):
            self.toggle_play()
            return True

        # Check Channel Selectors
        if self._in_rect(local_x, local_y, self.btn_ch1):
            self.switch_channel(0)
            return True
        if self._in_rect(local_x, local_y, self.btn_ch2):
            self.switch_channel(1)
            return True
        if self._in_rect(local_x, local_y, self.btn_ch3):
            self.switch_channel(2)
            return True

        # Check Volume Toggle
        if self._in_rect(local_x, local_y, self.btn_vol):
            self.cycle_volume()
            return True

        # Check Video Canvas click to toggle play/pause
        if (self.video_x <= local_x <= self.video_x + self.video_w and
            self.video_y <= local_y <= self.video_y + self.video_h):
            self.toggle_play()
            return True

        return False

    def _in_rect(self, x: int, y: int, rect: Tuple[int, int, int, int]) -> bool:
        rx, ry, rw, rh = rect
        return rx <= x <= rx + rw and ry <= y <= ry + rh

    def step(self, now: Optional[float] = None) -> bool:
        """Paces video stream frame at 30 FPS."""
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

        # 2. Render Top Header (YouTube Red brand banner & URL bar)
        self._fill_rect(surface_buffer, surf_w, 12, 10, 110, 22, (220, 20, 20, 255))
        self._draw_text(surface_buffer, surf_w, 16, 17, "[YT SOVEREIGN]", (255, 255, 255))

        # URL Input Box
        self._fill_rect(surface_buffer, surf_w, 130, 10, 310, 22, (30, 32, 40, 255))
        self._stroke_rect(surface_buffer, surf_w, 130, 10, 310, 22, (60, 65, 80, 255))
        self._draw_text(surface_buffer, surf_w, 138, 17, self.url_text[:36], (180, 200, 220))

        # Load / Refresh button
        self._fill_rect(surface_buffer, surf_w, 448, 10, 52, 22, (40, 44, 56, 255))
        self._stroke_rect(surface_buffer, surf_w, 448, 10, 52, 22, (80, 88, 110, 255))
        self._draw_text(surface_buffer, surf_w, 456, 17, "LIVE", (0, 255, 180))

        # Channel & Status Meta Line
        ch_title = self.relay.channel_info["title"]
        views = self.relay.channel_info["views"]
        meta_str = f"{ch_title} - {views} views"
        self._draw_text(surface_buffer, surf_w, 20, 42, meta_str[:54], (200, 210, 230))

        # 3. Video Viewport Framebuffer DMA Blit
        # Outline frame
        self._stroke_rect(surface_buffer, surf_w, self.video_x - 1, self.video_y - 1,
                           self.video_w + 2, self.video_h + 2, (70, 75, 95, 255))

        # Perform DMA blit from VPU directly into window surface
        self.vpu.dma_blit_to_surface(surface_buffer, surf_w, surf_h, self.video_x, self.video_y)

        # Draw Video Overlays: Resolution, FPS, and Timecode
        pts_s = self.vpu.current_pts // 1000
        dur_s = self.vpu.duration_ms // 1000
        cur_time_str = f"{pts_s // 60:02d}:{pts_s % 60:02d}"
        dur_time_str = f"{dur_s // 60:02d}:{dur_s % 60:02d}"
        
        # Video HUD badges (top right of video)
        fps_badge = "480x270 @ 30 FPS"
        self._fill_rect(surface_buffer, surf_w, self.video_x + self.video_w - 145, self.video_y + 8, 138, 18, (10, 10, 15, 200))
        self._draw_text(surface_buffer, surf_w, self.video_x + self.video_w - 140, self.video_y + 13, fps_badge, (0, 255, 220))

        # 4. Scrub Bar
        # Background track
        self._fill_rect(surface_buffer, surf_w, self.scrub_x, self.scrub_y, self.scrub_w, self.scrub_h, (40, 44, 55, 255))
        # Buffered progress (simulated 80% ahead)
        buf_pct = min(1.0, (self.vpu.current_pts + 40000) / float(self.vpu.duration_ms))
        buf_w = int(self.scrub_w * buf_pct)
        self._fill_rect(surface_buffer, surf_w, self.scrub_x, self.scrub_y, buf_w, self.scrub_h, (70, 75, 90, 255))
        # Played progress (YouTube red)
        play_pct = min(1.0, self.vpu.current_pts / float(self.vpu.duration_ms)) if self.vpu.duration_ms > 0 else 0.0
        play_w = int(self.scrub_w * play_pct)
        self._fill_rect(surface_buffer, surf_w, self.scrub_x, self.scrub_y, play_w, self.scrub_h, (230, 30, 30, 255))
        # Scrubber Knob
        knob_x = min(self.scrub_x + self.scrub_w - 4, self.scrub_x + play_w)
        self._fill_rect(surface_buffer, surf_w, knob_x - 3, self.scrub_y - 2, 7, self.scrub_h + 4, (255, 255, 255, 255))

        # 5. Transport Controls Bar
        # Play/Pause button
        play_lbl = "PAUSE" if self.is_playing else "PLAY"
        btn_col = (200, 30, 30, 255) if self.is_playing else (40, 160, 80, 255)
        self._draw_button(surface_buffer, surf_w, self.btn_play, play_lbl, btn_col)

        # Channel Selectors
        c1_col = (0, 120, 180, 255) if self.active_channel == 0 else (45, 50, 65, 255)
        c2_col = (180, 30, 120, 255) if self.active_channel == 1 else (45, 50, 65, 255)
        c3_col = (30, 140, 50, 255) if self.active_channel == 2 else (45, 50, 65, 255)
        self._draw_button(surface_buffer, surf_w, self.btn_ch1, "RISC-V 3D", c1_col)
        self._draw_button(surface_buffer, surf_w, self.btn_ch2, "SYNTHWAVE", c2_col)
        self._draw_button(surface_buffer, surf_w, self.btn_ch3, "MATRIX", c3_col)

        # Volume control
        vol_str = f"VOL:{self.volume}%"
        self._draw_button(surface_buffer, surf_w, self.btn_vol, vol_str, (45, 50, 65, 255))

        # Time & Quality Telemetry
        time_display = f"{cur_time_str} / {dur_time_str}"
        self._draw_text(surface_buffer, surf_w, 20, 396, time_display, (170, 180, 200))
        
        telemetry_txt = f"Frames: {self.vpu.frames_played} | 256MB RAM Scale"
        self._draw_text(surface_buffer, surf_w, 280, 396, telemetry_txt, (110, 130, 160))

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
