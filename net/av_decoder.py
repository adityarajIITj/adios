#!/usr/bin/env python3
"""
AdiOS Real-Time Audio/Video Decoder (net/av_decoder.py)
Decodes real video frames and audio from local media files using ffmpeg subprocesses:
- Video: Pipes raw BGRX frames at 30 FPS from ffmpeg stdout for VPU consumption
- Audio: Extracts audio to a WAV file for winsound-based host playback
- Seeking: Re-spawns ffmpeg at a new timestamp offset
- Thread-safe frame buffer with producer/consumer architecture

Zero Python dependencies beyond subprocess and standard library.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

import os
import struct
import subprocess
import tempfile
import threading
import time
from typing import Optional, List, Tuple
from collections import deque


# Decoder states
DECODER_IDLE = "IDLE"
DECODER_STARTING = "STARTING"
DECODER_RUNNING = "RUNNING"
DECODER_STOPPED = "STOPPED"
DECODER_ERROR = "ERROR"


def _find_ffmpeg() -> Optional[str]:
    """Locates ffmpeg binary on the system."""
    import shutil
    candidates = [
        r"C:\Users\adity\AppData\Local\Programs\Python\Python314\Scripts\ffmpeg.exe",
        "ffmpeg",
        "ffmpeg.exe",
    ]
    for c in candidates:
        if os.path.isabs(c) and os.path.isfile(c):
            return c
        found = shutil.which(c)
        if found:
            return found

    # Try to find ffmpeg via yt-dlp's downloaded copy
    try:
        import yt_dlp
        ytdlp_dir = os.path.dirname(yt_dlp.__file__)
        # yt-dlp sometimes bundles ffmpeg alongside
        for name in ("ffmpeg.exe", "ffmpeg"):
            candidate = os.path.join(ytdlp_dir, name)
            if os.path.isfile(candidate):
                return candidate
    except ImportError:
        pass

    return None


def _find_ffprobe() -> Optional[str]:
    """Locates ffprobe binary on the system."""
    import shutil
    for name in ("ffprobe", "ffprobe.exe"):
        found = shutil.which(name)
        if found:
            return found
    return None


def probe_media_duration(media_path: str) -> float:
    """
    Uses ffprobe to determine the duration of a media file in seconds.
    Returns 0.0 if probing fails.
    """
    ffprobe = _find_ffprobe()
    if not ffprobe:
        # Fallback: try ffmpeg -i which prints duration to stderr
        ffmpeg = _find_ffmpeg()
        if not ffmpeg:
            return 0.0
        try:
            result = subprocess.run(
                [ffmpeg, "-i", media_path],
                capture_output=True, text=True, timeout=5.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            # Parse "Duration: HH:MM:SS.ss" from stderr
            for line in result.stderr.split("\n"):
                if "Duration:" in line:
                    dur_str = line.split("Duration:")[1].split(",")[0].strip()
                    parts = dur_str.split(":")
                    if len(parts) == 3:
                        h, m, s = float(parts[0]), float(parts[1]), float(parts[2])
                        return h * 3600 + m * 60 + s
        except Exception:
            pass
        return 0.0

    try:
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json",
             "-show_format", media_path],
            capture_output=True, text=True, timeout=5.0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        import json
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0.0))
    except Exception:
        return 0.0


def probe_media_fps(media_path: str) -> float:
    """
    Uses ffprobe to determine the native video stream framerate.
    Returns 30.0 if probing fails.
    """
    ffprobe = _find_ffprobe()
    if not ffprobe:
        return 30.0
    try:
        result = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json",
             "-show_streams", media_path],
            capture_output=True, text=True, timeout=5.0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        import json
        data = json.loads(result.stdout)
        for s in data.get("streams", []):
            if s.get("codec_type") == "video":
                r = s.get("r_frame_rate", "30/1")
                if "/" in r:
                    num, den = map(int, r.split("/"))
                    fps_val = num / den if den > 0 else 30.0
                else:
                    fps_val = float(r)
                if 10.0 <= fps_val <= 65.0:
                    return fps_val
    except Exception:
        pass
    return 30.0


class AVDecoder:
    """
    Real-time audio/video decoder using ffmpeg subprocesses.
    Decodes video frames to raw BGRX pixels and extracts audio to WAV.
    """

    def __init__(self, media_path: str, width: int = 640, height: int = 360, fps: Optional[int] = None, duration_s: float = 0.0):
        self.media_path = media_path
        self.width = width
        self.height = height
        if fps is None:
            probed = probe_media_fps(media_path)
            self.fps = int(round(probed)) if probed > 0 else 30
        else:
            self.fps = fps
        self.frame_size = width * height * 4  # BGRX = 4 bytes per pixel

        self.state = DECODER_IDLE
        self.ffmpeg_bin = _find_ffmpeg()

        # Video frame ring buffer (thread-safe)
        self._frame_lock = threading.Lock()
        self._frame_buffer: deque = deque(maxlen=max(120, int(self.fps * 3)))  # 3 seconds buffer
        self._frames_decoded: int = 0
        self._last_frame_bytes: Optional[bytes] = None
        self._last_target_pts_s: float = 0.0

        # Video decoder subprocess
        self._video_proc: Optional[subprocess.Popen] = None
        self._video_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Audio WAV file path
        self.audio_wav_path: Optional[str] = None
        self._audio_extracted = False

        # Seek state
        self._current_seek_s: float = 0.0

        # Duration
        self.duration_s: float = duration_s

    def is_available(self) -> bool:
        """Returns True if ffmpeg is available for decoding."""
        return self.ffmpeg_bin is not None

    def start(self, seek_s: float = 0.0):
        """
        Starts video frame decoding and audio extraction.
        seek_s: starting timestamp in seconds.
        """
        if not self.ffmpeg_bin:
            self.state = DECODER_ERROR
            return

        self.stop()
        self._stop_event.clear()
        self._current_seek_s = seek_s
        self._frames_decoded = 0
        self._last_frame_bytes = None
        self._last_target_pts_s = seek_s
        with self._frame_lock:
            self._frame_buffer.clear()
        self.state = DECODER_STARTING

        # Probe duration in background if not known
        if self.duration_s <= 0:
            def _probe():
                d = probe_media_duration(self.media_path)
                if d > 0:
                    self.duration_s = d
            threading.Thread(target=_probe, daemon=True, name="av_duration_probe").start()

        # Extract audio to WAV (checks cache first)
        if not self._audio_extracted:
            self._extract_audio_wav()

        # Start video frame reader thread
        self._video_thread = threading.Thread(
            target=self._video_decode_loop,
            args=(seek_s,),
            daemon=True,
            name="av_video_decoder"
        )
        self._video_thread.start()

    def stop(self):
        """Stops all decoder subprocesses."""
        self._stop_event.set()
        if self._video_proc:
            proc = self._video_proc
            self._video_proc = None
            try:
                if proc.stdout:
                    proc.stdout.close()
            except Exception:
                pass
            try:
                proc.kill()
                proc.wait(timeout=1.0)
            except Exception:
                pass

        if self._video_thread and self._video_thread.is_alive():
            self._video_thread.join(timeout=3.0)

        self.state = DECODER_STOPPED

    def seek(self, seek_s: float):
        """Seeks to a new position by restarting the decoder."""
        self._last_frame_bytes = None
        self._last_target_pts_s = seek_s
        self.start(seek_s=seek_s)

    def get_frame(self, target_pts_s: Optional[float] = None) -> Optional[bytes]:
        """
        Retrieves the decoded video frame matching target_pts_s (in seconds).
        If target_pts_s is None, pops the oldest frame FIFO.
        Returns raw BGRX bytes (width * height * 4) or None if empty.
        """
        with self._frame_lock:
            if target_pts_s is None:
                if self._frame_buffer:
                    item = self._frame_buffer.popleft()
                    self._last_frame_bytes = item[1] if isinstance(item, tuple) else item
                    return self._last_frame_bytes
                return self._last_frame_bytes

            # Check for backward seek or loop
            if target_pts_s < self._last_target_pts_s - 1.5:
                self._frame_buffer.clear()
            self._last_target_pts_s = target_pts_s

            frame_dt = 1.0 / float(max(1, self.fps))

            # Discard stale frames lagging behind target presentation time (catch-up)
            while len(self._frame_buffer) > 1:
                first = self._frame_buffer[0]
                pts = first[0] if isinstance(first, tuple) else 0.0
                if pts < target_pts_s - (frame_dt * 0.5):
                    second = self._frame_buffer[1]
                    s_pts = second[0] if isinstance(second, tuple) else 0.0
                    if s_pts <= target_pts_s + (frame_dt * 0.5):
                        item = self._frame_buffer.popleft()
                        self._last_frame_bytes = item[1] if isinstance(item, tuple) else item
                        continue
                break

            if self._frame_buffer:
                first = self._frame_buffer[0]
                pts = first[0] if isinstance(first, tuple) else 0.0
                raw = first[1] if isinstance(first, tuple) else first
                if pts <= target_pts_s + (frame_dt * 0.5):
                    self._frame_buffer.popleft()
                    self._last_frame_bytes = raw
                    return raw
                else:
                    # Future frame -- hold last frame to prevent playing ahead of audio
                    return self._last_frame_bytes or raw

            return self._last_frame_bytes

    def peek_frame(self) -> Optional[bytes]:
        """Returns the next frame without removing it from the buffer."""
        with self._frame_lock:
            if self._frame_buffer:
                first = self._frame_buffer[0]
                return first[1] if isinstance(first, tuple) else first
            return self._last_frame_bytes

    @property
    def buffer_count(self) -> int:
        """Number of frames currently buffered."""
        with self._frame_lock:
            return len(self._frame_buffer)

    @property
    def frames_decoded(self) -> int:
        return self._frames_decoded

    def _video_decode_loop(self, seek_s: float):
        """
        Background thread: spawns ffmpeg to decode video frames and reads
        raw BGRX pixels from its stdout pipe.
        """
        try:
            cmd = [
                self.ffmpeg_bin,
                "-loglevel", "error",
            ]

            # Seek input if needed
            if seek_s > 0.5:
                cmd.extend(["-ss", f"{seek_s:.2f}"])

            cmd.extend([
                "-i", self.media_path,
                "-vf", f"scale={self.width}:{self.height}",
                "-r", str(self.fps),
                "-f", "rawvideo",
                "-pix_fmt", "bgr0",
                "-an",  # No audio
                "pipe:1"
            ])

            self._video_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=self.frame_size * 4,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            self.state = DECODER_RUNNING

            loop_frames = 0
            while not self._stop_event.is_set():
                # Read exactly one frame
                raw = self._video_proc.stdout.read(self.frame_size)
                if not raw or len(raw) < self.frame_size:
                    break  # End of stream or error

                pts_s = seek_s + (loop_frames / float(max(1, self.fps)))
                with self._frame_lock:
                    self._frame_buffer.append((pts_s, raw))
                    self._frames_decoded += 1
                loop_frames += 1

                # Throttle if buffer is getting full (back-pressure)
                while not self._stop_event.is_set():
                    with self._frame_lock:
                        if len(self._frame_buffer) < 60:
                            break
                    time.sleep(0.005)

            # Video stream ended
            if not self._stop_event.is_set():
                self.state = DECODER_STOPPED

        except Exception as e:
            self.state = DECODER_ERROR
        finally:
            if self._video_proc:
                try:
                    self._video_proc.terminate()
                except Exception:
                    pass

    def _extract_audio_wav(self):
        """
        Extracts the audio track from the media file into a WAV file
        for playback through SoundServer (pygame.mixer). Checks cache first.
        """
        if not self.ffmpeg_bin:
            return

        # 1. Check if companion WAV file already exists alongside media
        cand_wav = os.path.splitext(self.media_path)[0] + ".wav"
        if os.path.isfile(cand_wav) and os.path.getsize(cand_wav) > 1000:
            self.audio_wav_path = cand_wav
            self._audio_extracted = True
            return

        # 2. Check user media cache directory
        try:
            from net.yt_downloader import get_media_cache_dir
            basename = os.path.splitext(os.path.basename(self.media_path))[0]
            cache_wav = os.path.join(get_media_cache_dir(), f"{basename}.wav")
            if os.path.isfile(cache_wav) and os.path.getsize(cache_wav) > 1000:
                self.audio_wav_path = cache_wav
                self._audio_extracted = True
                return
        except Exception:
            pass

        try:
            wav_path = cand_wav
            if not os.path.isabs(wav_path) or not os.path.exists(os.path.dirname(wav_path)):
                wav_path = os.path.join(tempfile.gettempdir(), "adios_audio_track.wav")

            cmd = [
                self.ffmpeg_bin,
                "-loglevel", "error",
                "-y",  # Overwrite
                "-i", self.media_path,
                "-vn",  # No video
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "2",  # Stereo for premier sound quality
                wav_path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=30.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            if os.path.isfile(wav_path) and os.path.getsize(wav_path) > 100:
                self.audio_wav_path = wav_path
                self._audio_extracted = True

        except Exception:
            pass

    def cleanup(self):
        """Stops decoder and cleans temporary audio files while preserving cached media."""
        self.stop()
        if self.audio_wav_path and os.path.exists(self.audio_wav_path):
            # Only remove temporary extract files, never delete persistent cached media
            if "adios_audio_track" in self.audio_wav_path or "temp" in self.audio_wav_path.lower():
                try:
                    os.remove(self.audio_wav_path)
                except Exception:
                    pass
        self.audio_wav_path = None
