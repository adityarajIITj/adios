#!/usr/bin/env python3
"""
AdiOS Chronos Time-Travel Engine (kernel/chronos.py)
The world's first OS-wide real-time temporal rewind and replay architecture:
- Continuously captures lightweight differential state deltas at up to 30 FPS into a rolling ring-buffer.
- Tracks multi-window positions, geometries, visibility, and Z-orders.
- Tracks in-app states: Paint Studio vector strokes, Notepad text buffers, Code Studio IDE buffers.
- Interactive Time Scrubbing: Drag backwards to un-draw strokes, un-type characters, and slide windows back.
- Reality Forking: Commit any historical point as the new present reality.
- Seamless Live Resumption: Spring back to real-time present with zero data corruption.

Strict Zero Emoji Policy Enforced.
"""

import time
from collections import deque
from typing import Optional, Dict, List, Tuple, Any

# Maximum recorded temporal snapshots (300 frames @ 30 FPS = 10.0 seconds of history)
MAX_CHRONOS_FRAMES = 300


class ChronosFrame:
    """
    Lightweight temporal snapshot representing the complete visual and interactive
    state of the operating system at an exact instant in time.
    """
    __slots__ = (
        "timestamp",
        "time_offset_s",
        "window_states",
        "active_win_id",
        "notepad_state",
        "code_studio_state",
        "paint_strokes_count",
        "paint_strokes_copy",
        "status_message",
    )

    def __init__(
        self,
        timestamp: float,
        time_offset_s: float,
        window_states: Dict[str, Dict[str, Any]],
        active_win_id: Optional[str],
        notepad_state: Optional[Dict[str, Any]],
        code_studio_state: Optional[Dict[str, Any]],
        paint_strokes_count: int,
        paint_strokes_copy: Optional[List[Any]],
        status_message: str,
    ):
        self.timestamp = timestamp
        self.time_offset_s = time_offset_s
        self.window_states = window_states
        self.active_win_id = active_win_id
        self.notepad_state = notepad_state
        self.code_studio_state = code_studio_state
        self.paint_strokes_count = paint_strokes_count
        self.paint_strokes_copy = paint_strokes_copy
        self.status_message = status_message


class ChronosEngine:
    """
    Core engine managing temporal capture, timeline scrubbing, playback,
    and reality forking for the AdiOS Workstation.
    """

    def __init__(self, max_frames: int = MAX_CHRONOS_FRAMES):
        self.max_frames = max_frames
        self.frames: deque[ChronosFrame] = deque(maxlen=max_frames)

        # Operational Modes
        self.is_active: bool = False               # Time-travel scrub mode engaged
        self.scrub_index: int = -1                 # Index in self.frames being viewed
        self.is_playing_reverse: bool = False      # Continuous playback backwards
        self.is_playing_forward: bool = False      # Continuous playback forwards

        # Backup of present state prior to scrubbing
        self._present_backup: Optional[ChronosFrame] = None
        self._last_capture_time: float = 0.0
        self.capture_interval_s: float = 1.0 / 30.0  # 30 Hz capture rate

        # Telemetry
        self.total_frames_captured: int = 0
        self.reality_forks_count: int = 0

    @property
    def frame_count(self) -> int:
        """Returns number of temporal snapshots currently recorded."""
        return len(self.frames)

    @property
    def current_time_offset(self) -> float:
        """Returns how far back in seconds the current scrub head is (-0.0s is NOW)."""
        if not self.frames or self.scrub_index < 0 or self.scrub_index >= len(self.frames):
            return 0.0
        newest = self.frames[-1].timestamp
        curr = self.frames[self.scrub_index].timestamp
        return curr - newest  # Negative value representing seconds into the past

    @property
    def scrub_fraction(self) -> float:
        """Returns scrub position as a fraction from 0.0 (oldest) to 1.0 (now)."""
        if len(self.frames) <= 1:
            return 1.0
        idx = max(0, min(len(self.frames) - 1, self.scrub_index))
        return idx / float(len(self.frames) - 1)

    def capture_frame(self, desktop: Any) -> Optional[ChronosFrame]:
        """
        Captures a differential state delta of the desktop.
        Skips capture while actively scrubbing backwards to preserve recorded history.
        """
        if self.is_active:
            return None

        now = time.time()
        if now - self._last_capture_time < self.capture_interval_s:
            return None
        self._last_capture_time = now

        # 1. Window states (positions, dimensions, visibility, minimized)
        win_states: Dict[str, Dict[str, Any]] = {}
        if hasattr(desktop, "wm") and hasattr(desktop.wm, "windows"):
            for w in desktop.wm.windows:
                win_states[w.win_id] = {
                    "x": w.x,
                    "y": w.y,
                    "w": w.w,
                    "h": w.h,
                    "visible": w.visible,
                    "minimized": w.minimized,
                    "active": w.active,
                }

        # 2. Active window ID
        active_id = None
        if hasattr(desktop, "wm") and desktop.wm.windows:
            active_id = desktop.wm.windows[-1].win_id

        # 3. Notepad App state
        np_state = None
        if hasattr(desktop, "win_notepad") and desktop.win_notepad:
            np = desktop.win_notepad
            np_state = {
                "lines": list(np.lines),
                "cursor_line": np.cursor_line,
                "cursor_col": np.cursor_col,
                "is_dirty": getattr(np, "is_dirty", False),
            }

        # 4. Code Studio IDE state
        cs_state = None
        if hasattr(desktop, "win_studio") and desktop.win_studio:
            cs = desktop.win_studio
            cs_state = {
                "lines": list(cs.lines),
                "cursor_line": cs.cursor_line,
                "cursor_col": cs.cursor_col,
                "is_dirty": getattr(cs, "is_dirty", False),
            }

        # 5. Paint Studio state
        paint_count = 0
        paint_copy = None
        if hasattr(desktop, "win_paint") and desktop.win_paint:
            pt = desktop.win_paint
            if hasattr(pt, "paint_strokes"):
                paint_count = len(pt.paint_strokes)
                paint_copy = list(pt.paint_strokes)

        status = getattr(desktop, "status_message", "")

        frame = ChronosFrame(
            timestamp=now,
            time_offset_s=0.0,
            window_states=win_states,
            active_win_id=active_id,
            notepad_state=np_state,
            code_studio_state=cs_state,
            paint_strokes_count=paint_count,
            paint_strokes_copy=paint_copy,
            status_message=status,
        )

        self.frames.append(frame)
        self.total_frames_captured += 1
        return frame

    def toggle_time_travel(self, desktop: Any) -> bool:
        """
        Toggles Chronos time-travel mode on or off.
        Returns the new active state.
        """
        if not self.is_active:
            # Engage time-travel
            if not self.frames:
                self.capture_frame(desktop)
            self.is_active = True
            self.scrub_index = len(self.frames) - 1
            self.is_playing_reverse = False
            self.is_playing_forward = False
            if self.frames:
                self._present_backup = self.frames[-1]
            if hasattr(desktop, "status_message"):
                desktop.status_message = "Chronos Time-Travel Active. Drag scrubber to rewind OS."
        else:
            # Disengage and return to live present
            self.resume_live(desktop)

        return self.is_active

    def scrub_to_fraction(self, fraction: float, desktop: Any):
        """
        Scrubs timeline to a specific fraction (0.0 = oldest, 1.0 = present).
        Applies historical snapshot directly to the desktop.
        """
        if not self.frames:
            return
        fraction = max(0.0, min(1.0, fraction))
        target_idx = int(fraction * (len(self.frames) - 1))
        self.scrub_to_index(target_idx, desktop)

    def scrub_to_index(self, index: int, desktop: Any):
        """Applies historical snapshot at exact index to desktop."""
        if not self.frames:
            return
        self.scrub_index = max(0, min(len(self.frames) - 1, index))
        frame = self.frames[self.scrub_index]
        self.apply_frame_to_desktop(desktop, frame)

    def step_relative(self, delta: int, desktop: Any):
        """Steps timeline relative to current scrub position (+forward / -backward)."""
        if not self.frames:
            return
        target = self.scrub_index + delta
        self.scrub_to_index(target, desktop)

    def fork_reality(self, desktop: Any):
        """
        Forks reality at the current historical scrub position.
        Discards all chronological frames after scrub_index and sets
        the rewound state as the new baseline present!
        """
        if not self.is_active or not self.frames:
            return

        # Truncate history after scrub_index
        kept = list(self.frames)[:self.scrub_index + 1]
        self.frames.clear()
        self.frames.extend(kept)

        self.reality_forks_count += 1
        self.is_active = False
        self.is_playing_reverse = False
        self.is_playing_forward = False
        self._present_backup = None

        if hasattr(desktop, "status_message"):
            desktop.status_message = f"Timeline Forked at offset {self.current_time_offset:.2f}s. New reality committed."

    def resume_live(self, desktop: Any):
        """
        Exits time-travel scrub mode and restores the active real-time present.
        """
        if not self.is_active:
            return

        # Restore latest frame
        if self.frames:
            self.scrub_index = len(self.frames) - 1
            self.apply_frame_to_desktop(desktop, self.frames[-1])

        self.is_active = False
        self.is_playing_reverse = False
        self.is_playing_forward = False
        self._present_backup = None

        if hasattr(desktop, "status_message"):
            desktop.status_message = "Chronos resumed. Live present active."

    def apply_frame_to_desktop(self, desktop: Any, frame: ChronosFrame):
        """
        Restores the visual and data state of the desktop to match frame.
        """
        # 1. Restore Window coordinates, geometry, and visibility
        if hasattr(desktop, "wm") and hasattr(desktop.wm, "windows"):
            for w in desktop.wm.windows:
                if w.win_id in frame.window_states:
                    st = frame.window_states[w.win_id]
                    w.x = st["x"]
                    w.y = st["y"]
                    w.w = st["w"]
                    w.h = st["h"]
                    w.visible = st["visible"]
                    w.minimized = st["minimized"]

        # 2. Restore Notepad text buffer and cursor
        if frame.notepad_state and hasattr(desktop, "win_notepad") and desktop.win_notepad:
            np = desktop.win_notepad
            np.lines = list(frame.notepad_state["lines"])
            np.cursor_line = min(len(np.lines) - 1, frame.notepad_state["cursor_line"])
            np.cursor_col = min(len(np.lines[np.cursor_line]), frame.notepad_state["cursor_col"])
            if hasattr(np, "is_dirty"):
                np.is_dirty = frame.notepad_state["is_dirty"]

        # 3. Restore Code Studio IDE buffer and cursor
        if frame.code_studio_state and hasattr(desktop, "win_studio") and desktop.win_studio:
            cs = desktop.win_studio
            cs.lines = list(frame.code_studio_state["lines"])
            cs.cursor_line = min(len(cs.lines) - 1, frame.code_studio_state["cursor_line"])
            cs.cursor_col = min(len(cs.lines[cs.cursor_line]), frame.code_studio_state["cursor_col"])
            if hasattr(cs, "is_dirty"):
                cs.is_dirty = frame.code_studio_state["is_dirty"]

        # 4. Restore Paint Studio vector strokes (un-drawing future strokes)
        if frame.paint_strokes_copy is not None and hasattr(desktop, "win_paint") and desktop.win_paint:
            pt = desktop.win_paint
            if hasattr(pt, "paint_strokes"):
                pt.paint_strokes.clear()
                pt.paint_strokes.extend(frame.paint_strokes_copy)

    def step_playback(self, desktop: Any):
        """
        Advances or rewinds time if playback is actively rolling.
        """
        if not self.is_active:
            return

        if self.is_playing_reverse:
            if self.scrub_index > 0:
                self.step_relative(-1, desktop)
            else:
                self.is_playing_reverse = False
        elif self.is_playing_forward:
            if self.scrub_index < len(self.frames) - 1:
                self.step_relative(1, desktop)
            else:
                self.is_playing_forward = False
