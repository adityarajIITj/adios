#!/usr/bin/env python3
"""
AdiOS Hardware MMIO Video Processing Unit (VPU) Peripheral (vm/vpu.py)
Provides hardware-accelerated 30 FPS video streaming and DMA blitting:
- Memory-Mapped I/O Register Interface (0x30000000 - 0x300000FF)
- Hardware Overlay Plane & Direct Framebuffer DMA Blitter
- 30 FPS Cycle-Accurate Frame Pacer (33.3ms interval)
- High-Capacity Video Frame Ring Buffer (supporting 256MB RAM scale)
- Audio-Video PTS Synchronization & Transport Control FSM

Zero external dependencies. Pure RV32IM hardware simulation architecture.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

import os
import time
import threading
from typing import Optional, Tuple, List, Dict

# MMIO Register Offsets (Base: 0x30000000)
VPU_BASE            = 0x30000000
VPU_CMD             = 0x30000000  # W: 0=IDLE, 1=PLAY, 2=PAUSE, 3=STOP, 4=SEEK
VPU_STATUS          = 0x30000004  # R: 0=STOPPED, 1=PLAYING, 2=PAUSED, 3=BUFFERING, 4=ERROR
VPU_TARGET_FB       = 0x30000008  # R/W: Physical address of target surface
VPU_WIDTH           = 0x3000000C  # R/W: Video width (default 480)
VPU_HEIGHT          = 0x30000010  # R/W: Video height (default 270 or 360)
VPU_FPS             = 0x30000014  # R/W: Target FPS (default 30)
VPU_FRAMES_PLAYED   = 0x30000018  # R: Total delivered frames counter
VPU_CURRENT_PTS     = 0x3000001C  # R: Current presentation timestamp (ms)
VPU_DURATION_MS     = 0x30000020  # R/W: Stream total duration (ms)
VPU_SEEK_TARGET     = 0x30000024  # R/W: Target PTS for seek operation (ms)
VPU_VOLUME          = 0x30000028  # R/W: Audio volume (0 - 100)
VPU_BUFFER_CAPACITY = 0x3000002C  # R: Max frames in ring buffer (e.g. 120)
VPU_BUFFER_OCCUPANCY= 0x30000030  # R: Current unconsumed frames count
VPU_STREAM_TYPE     = 0x30000034  # R/W: 0=SYNTH_CYBER, 1=HTTP_STREAM, 2=RAW_DMA

# VPU Commands
CMD_IDLE  = 0
CMD_PLAY  = 1
CMD_PAUSE = 2
CMD_STOP  = 3
CMD_SEEK  = 4

# VPU Status States
STATUS_STOPPED   = 0
STATUS_PLAYING   = 1
STATUS_PAUSED    = 2
STATUS_BUFFERING = 3
STATUS_ERROR     = 4


class VideoFrame:
    """Represents an uncompressed 32-bit ARGB video frame."""
    __slots__ = ('width', 'height', 'pts_ms', 'data')

    def __init__(self, width: int, height: int, pts_ms: int, data: bytes):
        self.width = width
        self.height = height
        self.pts_ms = pts_ms
        self.data = data


class VPU:
    """
    Hardware Video Processing Unit (VPU) Controller.
    Decodes and DMA-blits video streams at deterministic 30 FPS.
    """
    def __init__(self, vm=None, width: int = 640, height: int = 360, fps: int = 60):
        self.vm = vm
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_interval = 1.0 / float(fps)  # ~0.0166s (16.6ms for 60 FPS)
        
        # State Registers
        self.cmd = CMD_IDLE
        self.status = STATUS_STOPPED
        self.target_fb = 0x20000000  # Default to primary FB
        self.frames_played = 0
        self.current_pts = 0
        self.duration_ms = 180000    # Default 3 minutes (180,000 ms)
        self.seek_target = 0
        self.volume = 80
        self.stream_type = 0         # 0=Synthetic Cyber stream
        self.buffer_capacity = 120   # 4 seconds pre-buffer at 30 FPS
        
        # Internal Frame Buffer Ring
        self._frame_queue: List[VideoFrame] = []
        self._current_frame: Optional[VideoFrame] = None
        self._lock = threading.Lock()
        
        # Frame Pacing Timing
        self._last_frame_time = 0.0
        self._playback_start_pts = 0
        # Host Audio Speaker Output State
        self.sound_enabled = True
        self._host_audio_playing = False
        
        # Connected Host Relay
        self.relay = None

    def play_host_audio(self, pcm_bytes: Optional[bytes] = None, seek_ms: Optional[int] = None):
        """Starts asynchronous looping audio playback on host speakers.
        Priority: Real audio WAV/media from relay > Provided PCM bytes > Synthetic PCM."""
        if not self.sound_enabled:
            return

        if seek_ms is None:
            seek_ms = self.current_pts
        seek_pos_s = max(0.0, float(seek_ms) / 1000.0)

        try:
            from audio.sound_server import SoundServer
            server = SoundServer.get_instance()
            if server.is_muted or server.master_volume <= 0.01:
                return
        except Exception:
            server = None

        # === PRIORITY 1: Real audio WAV or media from relay (actual YouTube audio) ===
        if self.relay and hasattr(self.relay, 'get_audio_wav_path'):
            media_path = self.relay.get_audio_wav_path()
            if media_path and os.path.isfile(media_path):
                self._audio_temp_path = media_path
                if server:
                    server.stream_audio_file(media_path, loop=True, start_pos_s=seek_pos_s)
                    self._host_audio_playing = True
                    return
                else:
                    self._play_wav_direct(media_path, start_pos_s=seek_pos_s)
                    return

        # === PRIORITY 2: Provided or generated PCM bytes (fallback) ===
        if pcm_bytes is None and self.relay:
            pcm_bytes = self.relay.generate_audio_pcm(duration_sec=4.0)
        if not pcm_bytes:
            return

        if server:
            server.play_pcm_sound(pcm_bytes, loop=True)
            self._host_audio_playing = True
            return

        try:
            import tempfile
            wav = self._pcm_to_wav(pcm_bytes, sample_rate=44100, volume_pct=self.volume)
            tmp = tempfile.NamedTemporaryFile(prefix="adios_audio_", suffix=".wav", delete=False)
            tmp.write(wav)
            tmp.close()

            # Clean up previously playing audio temp file
            old_path = getattr(self, "_audio_temp_path", None)
            if old_path and old_path != tmp.name:
                try:
                    if os.path.exists(old_path):
                        os.remove(old_path)
                except Exception:
                    pass

            self._audio_temp_path = tmp.name
            import winsound
            winsound.PlaySound(self._audio_temp_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
            self._host_audio_playing = True
        except Exception:
            pass

    def _play_wav_direct(self, wav_path: str, start_pos_s: float = 0.0):
        """Plays a WAV or media file directly through SoundServer or winsound."""
        try:
            from audio.sound_server import SoundServer
            server = SoundServer.get_instance()
            if server and not server.is_muted and server.master_volume > 0.01:
                server.stream_audio_file(wav_path, loop=True, start_pos_s=start_pos_s)
                self._host_audio_playing = True
                return
        except Exception:
            pass

        try:
            import winsound

            old_path = getattr(self, "_audio_temp_path", None)
            if old_path:
                try:
                    winsound.PlaySound(None, winsound.SND_PURGE)
                    if old_path != wav_path and os.path.exists(old_path):
                        os.remove(old_path)
                except Exception:
                    pass

            self._audio_temp_path = wav_path
            winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
            self._host_audio_playing = True
        except Exception:
            pass

    def stop_host_audio(self):
        """Silences host speaker audio playback and cleans temporary audio files."""
        try:
            from audio.sound_server import SoundServer
            SoundServer.get_instance().stop_all()
        except Exception:
            pass

        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

        old_path = getattr(self, "_audio_temp_path", None)
        if old_path:
            if "adios_audio_" in old_path or "temp" in old_path.lower():
                try:
                    if os.path.exists(old_path):
                        os.remove(old_path)
                except Exception:
                    pass

        self._audio_temp_path = None
        self._host_audio_playing = False

    def set_sound_enabled(self, enabled: bool):
        """Toggles audio speaker output on or off."""
        self.sound_enabled = bool(enabled)
        if not self.sound_enabled:
            self.stop_host_audio()
        elif self.status == STATUS_PLAYING:
            self.play_host_audio(seek_ms=self.current_pts)

    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 44100, volume_pct: int = 100) -> bytes:
        """Formats 16-bit mono PCM into standard RIFF WAVE bytes with volume attenuation."""
        import struct
        vol_factor = max(0.0, min(1.0, volume_pct / 100.0))
        scaled_pcm = bytearray(len(pcm_data))
        for i in range(0, len(pcm_data), 2):
            sample = struct.unpack_from("<h", pcm_data, i)[0]
            scaled = int(sample * vol_factor)
            struct.pack_into("<h", scaled_pcm, i, max(-32768, min(32767, scaled)))
        data_bytes = bytes(scaled_pcm)
        data_size = len(data_bytes)
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + data_size,
            b"WAVE",
            b"fmt ",
            16,
            1,
            1,
            sample_rate,
            sample_rate * 2,
            2,
            16,
            b"data",
            data_size
        )
        return header + data_bytes

    def read32(self, addr: int) -> int:
        """MMIO register read handler."""
        if addr == VPU_CMD:             return self.cmd
        if addr == VPU_STATUS:          return self.status
        if addr == VPU_TARGET_FB:       return self.target_fb
        if addr == VPU_WIDTH:           return self.width
        if addr == VPU_HEIGHT:          return self.height
        if addr == VPU_FPS:             return self.fps
        if addr == VPU_FRAMES_PLAYED:   return self.frames_played
        if addr == VPU_CURRENT_PTS:     return self.current_pts
        if addr == VPU_DURATION_MS:     return self.duration_ms
        if addr == VPU_SEEK_TARGET:     return self.seek_target
        if addr == VPU_VOLUME:          return self.volume
        if addr == VPU_BUFFER_CAPACITY: return self.buffer_capacity
        if addr == VPU_BUFFER_OCCUPANCY:
            with self._lock:
                return len(self._frame_queue)
        if addr == VPU_STREAM_TYPE:     return self.stream_type
        return 0

    def write32(self, addr: int, val: int):
        """MMIO register write handler."""
        val &= 0xFFFFFFFF
        if addr == VPU_CMD:
            self._execute_cmd(val)
        elif addr == VPU_STATUS:
            self.status = val & 0x07
        elif addr == VPU_TARGET_FB:
            self.target_fb = val
        elif addr == VPU_WIDTH:
            self.width = max(16, min(1024, val))
        elif addr == VPU_HEIGHT:
            self.height = max(16, min(768, val))
        elif addr == VPU_FPS:
            self.fps = max(1, min(60, val))
            self.frame_interval = 1.0 / float(self.fps)
        elif addr == VPU_DURATION_MS:
            self.duration_ms = val
        elif addr == VPU_SEEK_TARGET:
            self.seek_target = val
        elif addr == VPU_VOLUME:
            self.volume = max(0, min(100, val))
            try:
                from audio.sound_server import SoundServer
                SoundServer.get_instance().set_volume_pct(self.volume)
            except Exception:
                pass
            if self.volume <= 1:
                self.stop_host_audio()
            elif self._host_audio_playing and self.sound_enabled:
                self.play_host_audio(seek_ms=self.current_pts)
        elif addr == VPU_STREAM_TYPE:
            self.stream_type = val

    def _execute_cmd(self, cmd: int):
        """Processes VPU hardware command state transitions."""
        self.cmd = cmd
        now = time.perf_counter()
        
        if cmd == CMD_PLAY:
            if self.status != STATUS_PLAYING:
                self.status = STATUS_PLAYING
                self._playback_start_clock = now
                self._playback_start_pts = self.current_pts
                self._last_frame_time = now
                self.play_host_audio(seek_ms=self.current_pts)
        elif cmd == CMD_PAUSE:
            if self.status == STATUS_PLAYING:
                self.status = STATUS_PAUSED
                self.stop_host_audio()
        elif cmd == CMD_STOP:
            self.status = STATUS_STOPPED
            self.current_pts = 0
            self._playback_start_pts = 0
            self.stop_host_audio()
            with self._lock:
                self._frame_queue.clear()
                self._current_frame = None
        elif cmd == CMD_SEEK:
            self.current_pts = min(self.duration_ms, self.seek_target)
            self._playback_start_clock = now
            self._playback_start_pts = self.current_pts
            with self._lock:
                self._frame_queue.clear()
            if self.relay:
                self.relay.seek(self.current_pts)
            if self.status == STATUS_PLAYING:
                self.play_host_audio(seek_ms=self.current_pts)

    def push_frame(self, frame: VideoFrame) -> bool:
        """Pushes an incoming decoded video frame into the VPU ring buffer."""
        with self._lock:
            if len(self._frame_queue) >= self.buffer_capacity:
                # Buffer full: drop oldest frame to maintain realtime pacing
                self._frame_queue.pop(0)
            self._frame_queue.append(frame)
            return True

    def get_current_frame(self) -> Optional[VideoFrame]:
        """Returns the active video frame for display."""
        with self._lock:
            return self._current_frame

    def step(self, now: Optional[float] = None) -> bool:
        """
        Advances video playback by one frame interval (~33.3ms for 30 FPS, ~16.6ms for 60 FPS).
        Returns True if a new frame was blitted/advanced.
        """
        if self.status != STATUS_PLAYING:
            return False

        if now is None:
            now = time.perf_counter()

        elapsed = now - self._last_frame_time
        if elapsed < self.frame_interval:
            return False  # Maintain exact frame pacing (e.g. 16.6ms for 60 FPS)

        # Advance presentation timestamp (sync with hardware audio clock if streaming)
        self._last_frame_time = now
        synced_audio = False
        if self._host_audio_playing:
            try:
                import pygame
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    mpos = pygame.mixer.music.get_pos()
                    if mpos >= 0:
                        self.current_pts = min(self.duration_ms, self._playback_start_pts + mpos)
                        synced_audio = True
            except Exception:
                pass

        if not synced_audio:
            calculated_pts = int(self._playback_start_pts + (now - self._playback_start_clock) * 1000)
            self.current_pts = min(self.duration_ms, calculated_pts)

        # Loop playback when reaching end of stream
        if self.current_pts >= self.duration_ms:
            self.current_pts = 0
            self._playback_start_clock = now
            self._playback_start_pts = 0
            with self._lock:
                self._frame_queue.clear()
            if self.relay:
                self.relay.seek(0)
            if self._host_audio_playing and self.sound_enabled:
                self.play_host_audio(seek_ms=0)

        # Retrieve next frame from ring buffer or request from relay
        advanced = False
        with self._lock:
            if self._frame_queue:
                self._current_frame = self._frame_queue.pop(0)
                self.frames_played += 1
                advanced = True
            elif self.relay:
                frame = self.relay.generate_frame(self.current_pts, self.width, self.height)
                if frame:
                    self._current_frame = frame
                    self.frames_played += 1
                    advanced = True

        # Check if real audio has become available and start it
        if advanced and self.relay and hasattr(self.relay, 'is_real_video_active'):
            if self.relay.is_real_video_active and not self._host_audio_playing and self.sound_enabled:
                self.play_host_audio(seek_ms=self.current_pts)

        return advanced

    def dma_blit_to_surface(self, surface_buffer: bytearray, surf_w: int, surf_h: int,
                            dst_x: int, dst_y: int, clip_rect: Optional[Tuple[int, int, int, int]] = None):
        """
        High-performance DMA blit: transfers the active video frame directly
        into target surface memory with coordinate clipping.
        """
        frame = self.get_current_frame()
        if frame is None or not frame.data:
            return

        fw = frame.width
        fh = frame.height
        src_data = frame.data

        # Determine clip boundary
        cx0 = 0 if clip_rect is None else clip_rect[0]
        cy0 = 0 if clip_rect is None else clip_rect[1]
        cx1 = surf_w if clip_rect is None else clip_rect[0] + clip_rect[2]
        cy1 = surf_h if clip_rect is None else clip_rect[1] + clip_rect[3]

        # Intersect with surface bounds
        x_start = max(dst_x, cx0, 0)
        y_start = max(dst_y, cy0, 0)
        x_end   = min(dst_x + fw, cx1, surf_w)
        y_end   = min(dst_y + fh, cy1, surf_h)

        if x_start >= x_end or y_start >= y_end:
            return  # Completely culled

        copy_w = x_end - x_start
        copy_bytes = copy_w * 4

        src_offset_x = x_start - dst_x
        src_pitch = fw * 4
        dst_pitch = surf_w * 4

        for y in range(y_start, y_end):
            src_y = y - dst_y
            s_off = src_y * src_pitch + (src_offset_x * 4)
            d_off = y * dst_pitch + (x_start * 4)
            surface_buffer[d_off : d_off + copy_bytes] = src_data[s_off : s_off + copy_bytes]

VideoProcessingUnit = VPU

