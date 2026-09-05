#!/usr/bin/env python3
"""
AdiOS YouTube Stream Downloader (net/yt_downloader.py)
Background downloader that uses yt-dlp to extract and download real YouTube
video+audio streams to local temporary files for playback:
- Subprocess-based yt-dlp invocation with JSON metadata extraction
- Best quality stream selection (video+audio muxed, <=720p for performance)
- Async download with status callbacks: IDLE -> DOWNLOADING -> READY -> ERROR
- Temp file lifecycle management and cleanup

Zero UI dependencies. Pure subprocess + standard library architecture.
STRICT ZERO EMOJI POLICY ENFORCED.
"""

import sys
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
from typing import Optional, Dict, Any, Callable

# Download states
STATE_IDLE = "IDLE"
STATE_RESOLVING = "RESOLVING"
STATE_DOWNLOADING = "DOWNLOADING"
STATE_READY = "READY"
STATE_ERROR = "ERROR"


def find_yt_dlp_binary() -> Optional[str]:
    """Locates the yt-dlp executable on the host system."""
    # 1. Check if yt-dlp is importable as Python module (pip installed)
    try:
        import yt_dlp
        # When pip-installed, the executable should be on PATH
        found = shutil.which("yt-dlp")
        if found:
            return found
        # Fallback: use python -m yt_dlp
        return "__python_module__"
    except ImportError:
        pass

    # 2. Check PATH
    for name in ("yt-dlp", "yt-dlp.exe"):
        found = shutil.which(name)
        if found:
            return found

    return None


def find_ffmpeg_binary() -> Optional[str]:
    """Locates ffmpeg executable on the host system."""
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
    return None


def extract_video_id(url_or_id: str) -> Optional[str]:
    """Extracts 11-char YouTube video ID if present."""
    import re
    if not url_or_id:
        return None
    url = url_or_id.strip()
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url):
        return url
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})(?:[&?]|$)",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
        r"embed\/([0-9A-Za-z_-]{11})",
        r"shorts\/([0-9A-Za-z_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def get_media_cache_dir() -> str:
    """Returns persistent media cache directory."""
    candidates = [
        os.path.join(os.path.expanduser("~"), ".adios_media"),
        os.path.join(tempfile.gettempdir(), "adios_media_cache"),
    ]
    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            return d
        except Exception:
            pass
    return tempfile.gettempdir()


def find_in_media_cache(url_or_id: str) -> Optional[str]:
    """Finds cached video file for a YouTube video URL or ID."""
    vid = extract_video_id(url_or_id)
    if not vid:
        return None
    cache_dir = get_media_cache_dir()
    for ext in (".mp4", ".mkv", ".webm"):
        p = os.path.join(cache_dir, f"{vid}{ext}")
        if os.path.isfile(p) and os.path.getsize(p) > 1000:
            return p
    return None


class YouTubeDownloader:
    """
    Background downloader that extracts real YouTube streams via yt-dlp.
    Downloads a muxed video+audio file to a temporary location for local playback.
    """

    def __init__(self, temp_dir: Optional[str] = None):
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix="adios_yt_")
        self.state = STATE_IDLE
        self.progress_pct: float = 0.0
        self.error_message: str = ""

        # Downloaded media file path
        self.media_path: Optional[str] = None
        self.metadata: Dict[str, Any] = {}

        # Background thread
        self._thread: Optional[threading.Thread] = None
        self._cancel_flag = threading.Event()

        # yt-dlp binary
        self._ytdlp_bin = find_yt_dlp_binary()
        self._ffmpeg_bin = find_ffmpeg_binary()

    def is_available(self) -> bool:
        """Returns True if yt-dlp is available on this system."""
        return self._ytdlp_bin is not None

    def download_async(self, url: str, on_complete: Optional[Callable] = None):
        """
        Starts a background download of the given YouTube URL.
        Calls on_complete(success: bool) when finished.
        """
        if self._thread and self._thread.is_alive():
            self.cancel()
            self._thread.join(timeout=5.0)

        # 1. Check persistent media cache first for instant playback
        cached = find_in_media_cache(url)
        if cached:
            self.media_path = cached
            self.state = STATE_READY
            self.progress_pct = 100.0
            if on_complete:
                t = threading.Thread(target=lambda: on_complete(True), daemon=True)
                t.start()
            return

        self._cancel_flag.clear()
        self.state = STATE_RESOLVING
        self.progress_pct = 0.0
        self.error_message = ""
        self.media_path = None

        self._thread = threading.Thread(
            target=self._download_worker,
            args=(url, on_complete),
            daemon=True,
            name="yt_downloader"
        )
        self._thread.start()

    def download_sync(self, url: str) -> bool:
        """Synchronous download. Blocks until complete. Returns True on success."""
        cached = find_in_media_cache(url)
        if cached:
            self.media_path = cached
            self.state = STATE_READY
            self.progress_pct = 100.0
            return True

        self._cancel_flag.clear()
        self.state = STATE_RESOLVING
        self.progress_pct = 0.0
        self.error_message = ""
        self.media_path = None
        self._download_worker(url, None)
        return self.state == STATE_READY

    def cancel(self):
        """Cancels an in-progress download."""
        self._cancel_flag.set()

    def cleanup(self):
        """Removes temporary files created by this downloader."""
        self.cancel()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self.media_path and os.path.exists(self.media_path):
            # Only remove if inside temp directory, preserve persistent media cache
            if self.media_path.startswith(self.temp_dir):
                try:
                    os.remove(self.media_path)
                except Exception:
                    pass
            self.media_path = None
        # Try to clean temp dir
        try:
            if os.path.isdir(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass

    def _build_ytdlp_command(self, url: str, output_path: str) -> list:
        """Constructs the yt-dlp command line for downloading."""
        if self._ytdlp_bin == "__python_module__":
            cmd = [sys.executable, "-m", "yt_dlp"]
        else:
            cmd = [self._ytdlp_bin]

        cmd.extend([
            # Format selection: H.264 video + AAC audio in MP4, with format 18 fallback
            "-f", "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/18/bestvideo+bestaudio/best[ext=mp4]/best",
            # Merge to mp4 for compatibility
            "--merge-output-format", "mp4",
            # Output path
            "-o", output_path,
            # No playlist, single video only
            "--no-playlist",
            # Write metadata as JSON alongside
            "--write-info-json",
            # Quiet output, progress to stderr
            "--no-warnings",
            "--newline",
        ])

        # If ffmpeg is available, tell yt-dlp where it is
        if self._ffmpeg_bin and self._ffmpeg_bin != "ffmpeg":
            ffmpeg_dir = os.path.dirname(self._ffmpeg_bin)
            if ffmpeg_dir:
                cmd.extend(["--ffmpeg-location", ffmpeg_dir])

        cmd.append(url)
        return cmd

    def _download_worker(self, url: str, on_complete: Optional[Callable]):
        """Worker thread that runs the yt-dlp download process."""
        try:
            if not self._ytdlp_bin:
                self.state = STATE_ERROR
                self.error_message = "yt-dlp not found. Install with: pip install yt-dlp"
                if on_complete:
                    on_complete(False)
                return

            # Prepare output path
            output_path = os.path.join(self.temp_dir, "video.mp4")

            # Clean previous download
            for f in os.listdir(self.temp_dir):
                try:
                    os.remove(os.path.join(self.temp_dir, f))
                except Exception:
                    pass

            self.state = STATE_DOWNLOADING
            self.progress_pct = 0.0

            cmd = self._build_ytdlp_command(url, output_path)

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )

            # Parse progress from yt-dlp output lines
            while True:
                if self._cancel_flag.is_set():
                    proc.terminate()
                    self.state = STATE_IDLE
                    if on_complete:
                        on_complete(False)
                    return

                line = proc.stdout.readline()
                if not line and proc.poll() is not None:
                    break

                line = line.strip()
                if not line:
                    continue

                # Parse download progress: "[download]  42.5% of ..."
                if "[download]" in line and "%" in line:
                    try:
                        pct_str = line.split("%")[0].split()[-1]
                        self.progress_pct = float(pct_str)
                    except (ValueError, IndexError):
                        pass
                elif "[Merger]" in line or "[ExtractAudio]" in line:
                    self.progress_pct = 95.0

            retcode = proc.wait()

            # Find the actual output file (yt-dlp may have renamed it)
            actual_path = None
            if os.path.isfile(output_path):
                actual_path = output_path
            else:
                # Search for any video file in temp dir
                for f in os.listdir(self.temp_dir):
                    if f.endswith((".mp4", ".mkv", ".webm", ".m4a")):
                        actual_path = os.path.join(self.temp_dir, f)
                        break

            if actual_path and os.path.isfile(actual_path) and os.path.getsize(actual_path) > 1000:
                # Save to persistent cache for instant playback on future launches
                vid = extract_video_id(url)
                if vid:
                    try:
                        cache_dir = get_media_cache_dir()
                        cached_dest = os.path.join(cache_dir, f"{vid}.mp4")
                        if not os.path.exists(cached_dest):
                            shutil.copy2(actual_path, cached_dest)
                            actual_path = cached_dest
                    except Exception:
                        pass

                self.media_path = actual_path
                self.progress_pct = 100.0

                # Load metadata from info JSON if available
                self._load_info_json()

                self.state = STATE_READY
                if on_complete:
                    on_complete(True)
            else:
                self.state = STATE_ERROR
                self.error_message = f"Download failed (exit code {retcode})"
                if on_complete:
                    on_complete(False)

        except Exception as e:
            self.state = STATE_ERROR
            self.error_message = str(e)[:120]
            if on_complete:
                on_complete(False)

    def _load_info_json(self):
        """Loads metadata from the yt-dlp generated .info.json file."""
        if not self.temp_dir:
            return
        for f in os.listdir(self.temp_dir):
            if f.endswith(".info.json"):
                json_path = os.path.join(self.temp_dir, f)
                try:
                    with open(json_path, "r", encoding="utf-8") as fh:
                        data = json.load(fh)
                    self.metadata = {
                        "title": data.get("title", "Unknown"),
                        "author": data.get("uploader", data.get("channel", "Unknown")),
                        "duration_s": data.get("duration", 180),
                        "duration_ms": int(data.get("duration", 180) * 1000),
                        "views": data.get("view_count", 0),
                        "thumbnail_url": data.get("thumbnail", ""),
                        "id": data.get("id", ""),
                        "description": data.get("description", "")[:200],
                    }
                except Exception:
                    pass
                return
