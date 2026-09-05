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


class AVDecoder:
    """
    Real-time audio/video decoder using ffmpeg subprocesses.
    Decodes video frames to raw BGRX pixels and extracts audio to WAV.
    """

    def __init__(self, media_path: str, width: int = 480, height: int = 270, fps: int = 30):
        self.media_path = media_path
        self.width = width
        self.height = height
        self.fps = fps
        self.frame_size = width * height * 4  # BGRX = 4 bytes per pixel

        self.state = DECODER_IDLE
        self.ffmpeg_bin = _find_ffmpeg()

        # Video frame ring buffer (thread-safe)
        self._frame_lock = threading.Lock()
        self._frame_buffer: deque = deque(maxlen=90)  # 3 seconds at 30fps
        self._frames_decoded: int = 0

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
        self.duration_s: float = 0.0

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
        self.state = DECODER_STARTING

        # Probe duration if not known
        if self.duration_s <= 0:
            self.duration_s = probe_media_duration(self.media_path)

        # Extract audio to WAV (one-time operation)
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
            try:
                self._video_proc.terminate()
                self._video_proc.wait(timeout=2.0)
            except Exception:
                try:
                    self._video_proc.kill()
                except Exception:
                    pass
            self._video_proc = None

        if self._video_thread and self._video_thread.is_alive():
            self._video_thread.join(timeout=3.0)

        self.state = DECODER_STOPPED

    def seek(self, seek_s: float):
        """Seeks to a new position by restarting the decoder."""
        self.start(seek_s=seek_s)

    def get_frame(self) -> Optional[bytes]:
        """
        Pops the next decoded video frame from the buffer.
        Returns raw BGRX bytes (width * height * 4) or None if empty.
        """
        with self._frame_lock:
            if self._frame_buffer:
                return self._frame_buffer.popleft()
            return None

    def peek_frame(self) -> Optional[bytes]:
        """Returns the next frame without removing it from the buffer."""
        with self._frame_lock:
            if self._frame_buffer:
                return self._frame_buffer[0]
            return None

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

            while not self._stop_event.is_set():
                # Read exactly one frame
                raw = self._video_proc.stdout.read(self.frame_size)
                if not raw or len(raw) < self.frame_size:
                    break  # End of stream or error

                with self._frame_lock:
                    self._frame_buffer.append(raw)
                    self._frames_decoded += 1

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
        for playback through winsound.
        """
        if not self.ffmpeg_bin:
            return

        try:
            wav_path = os.path.join(
                os.path.dirname(self.media_path),
                "audio_track.wav"
            )

            cmd = [
                self.ffmpeg_bin,
                "-loglevel", "error",
                "-y",  # Overwrite
                "-i", self.media_path,
                "-vn",  # No video
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "1",  # Mono for winsound compatibility
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
        """Stops decoder and removes temporary audio files."""
        self.stop()
        if self.audio_wav_path and os.path.exists(self.audio_wav_path):
            try:
                os.remove(self.audio_wav_path)
            except Exception:
                pass
            self.audio_wav_path = None
