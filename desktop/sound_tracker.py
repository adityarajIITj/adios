#!/usr/bin/env python3
"""
AdiOS SoundTracker - 8-Channel Polyphonic Synthesizer & Visual DAW (desktop/sound_tracker.py)
A full-featured retro-modern digital audio workstation:
- 8 polyphonic synthesizer tracks with independent waveform, ADSR, and volume control.
- Interactive tracker pattern matrix editor with scrolling playhead.
- Visual step sequencer / piano roll mode.
- Real-time oscilloscope waveform graph and 16-band spectrum visualizer.
- Native WAV audio file export to sovereign storage.
- Zero external dependencies.

Strict Zero Emoji Policy Enforced.
"""

import os
import math
import time
from typing import List, Dict, Tuple, Optional, Any

from audio.dsp_synth import PolyphonicDSPSynth, note_to_hz
from graphics.engine2d import draw_rounded_rect, draw_drop_shadow

COLOR_BG_DARK      = 0x000F172A
COLOR_BG_PANEL     = 0x001E293B
COLOR_BORDER_CYAN  = 0x000284C7
COLOR_TEXT_WHITE   = 0x00F8FAFC
COLOR_TEXT_MUTED   = 0x0094A3B8
COLOR_ACCENT_GREEN = 0x0034D399
COLOR_ACCENT_CYAN  = 0x0038BDF8
COLOR_ACCENT_AMBER = 0x00FBBF24
COLOR_ACCENT_PURPLE= 0x00A855F7
COLOR_ACCENT_RED   = 0x00F87171

# Key mapping to semitones: A=C, W=C#, S=D, E=D#, D=E, F=F, T=F#, G=G, Y=G#, H=A, U=A#, J=B, K=C+1
KEY_NOTE_MAP = {
    "a": "C", "w": "C#", "s": "D", "e": "D#", "d": "E",
    "f": "F", "t": "F#", "g": "G", "y": "G#", "h": "A",
    "u": "A#", "j": "B", "k": "C",
    "A": "C", "W": "C#", "S": "D", "E": "D#", "D": "E",
    "F": "F", "T": "F#", "G": "G", "Y": "G#", "H": "A",
    "U": "A#", "J": "B", "K": "C"
}

DEMO_SONG_CYBER = [
    # Step: [Ch0, Ch1, Ch2, Ch3, Ch4, Ch5, Ch6, Ch7]
    ["C-2", "---", "F#4", "C-3", "C-4", "E-4", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"],
    ["---", "D-3", "F#4", "C-3", "E-4", "G-4", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"],
    ["C-2", "---", "F#4", "C-3", "G-4", "B-4", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"],
    ["---", "D-3", "F#4", "C-3", "E-4", "G-4", "---", "---"],
    ["---", "---", "F#4", "---", "D-4", "---", "---", "---"],
    ["G-1", "---", "F#4", "G-2", "C-4", "E-4", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"],
    ["---", "D-3", "F#4", "G-2", "D-4", "F-4", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"],
    ["C-2", "---", "F#4", "G-2", "E-4", "G-4", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"],
    ["---", "D-3", "F#4", "G-2", "G-4", "C-5", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"],
    ["F-1", "---", "F#4", "F-2", "A-3", "C-4", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"],
    ["---", "D-3", "F#4", "F-2", "C-4", "F-4", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"],
    ["F-1", "---", "F#4", "F-2", "D-4", "F-4", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"],
    ["---", "D-3", "F#4", "F-2", "C-4", "E-4", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"],
    ["G-1", "---", "F#4", "G-2", "B-3", "D-4", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"],
    ["---", "D-3", "F#4", "G-2", "D-4", "G-4", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"],
    ["G-1", "---", "F#4", "G-2", "G-4", "B-4", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"],
    ["---", "D-3", "F#4", "G-2", "D-5", "G-5", "---", "---"],
    ["---", "---", "F#4", "---", "---", "---", "---", "---"]
]


class SoundTrackerApp:
    """
    Sovereign SoundTracker 8-Channel Polyphonic Synth & Visual DAW.
    """

    def __init__(self, screen_w: int = 1280, screen_h: int = 720):
        self.screen_w = screen_w
        self.screen_h = screen_h

        # Core 8-Channel Polyphonic DSP Synthesizer
        self.synth = PolyphonicDSPSynth(num_channels=8)
        self._configure_default_channels()

        # Playback state
        self.is_playing = False
        self.bpm = 128
        self.octave = 4
        self.current_step = 0
        self.num_steps = 32
        self.last_step_time = time.time()
        self.view_mode = "tracker"  # "tracker" or "piano_roll"

        # Pattern matrix: 32 rows x 8 channels
        self.pattern: List[List[str]] = [list(row) for row in DEMO_SONG_CYBER]

        # Cursor and Selection
        self.cursor_row = 0
        self.cursor_col = 0
        self.scroll_row = 0

        # Status telemetry
        self.status_message = "SoundTracker Ready. Press Space to Play."

    def _configure_default_channels(self):
        """Sets up default instruments across all 8 tracks."""
        self.synth.set_channel_instrument(0, "kick")
        self.synth.set_channel_instrument(1, "snare")
        self.synth.set_channel_instrument(2, "hihat")
        self.synth.set_channel_instrument(3, "bass")
        self.synth.set_channel_instrument(4, "lead")
        self.synth.set_channel_instrument(5, "pad")
        self.synth.set_channel_instrument(6, "acid")
        self.synth.set_channel_instrument(7, "arcade")

    def toggle_playback(self):
        """Toggles sequence playback."""
        self.is_playing = not self.is_playing
        if self.is_playing:
            self.last_step_time = time.time()
            self.status_message = f"Playing at {self.bpm} BPM..."
        else:
            for ch in range(8):
                self.synth.note_off(ch)
            self.status_message = "Playback Stopped."

    def stop_playback(self):
        self.is_playing = False
        self.current_step = 0
        for ch in range(8):
            self.synth.note_off(ch)
        self.status_message = "Playback Reset."

    def step(self):
        """Advances sequence timing and steps synthesizer visualizers."""
        now = time.time()
        # 16th note interval = (60.0 / bpm) / 4.0
        step_interval = (60.0 / max(40, self.bpm)) * 0.25

        if self.is_playing:
            if now - self.last_step_time >= step_interval:
                self.last_step_time = now
                self._trigger_step(self.current_step)
                self.current_step = (self.current_step + 1) % self.num_steps

        # Synthesize audio samples into oscilloscope/spectrum buffers
        for _ in range(32):
            self.synth.render_mixed_sample()

        # Decay spectrum visualizer bars
        self.synth.update_spectrum()

    def _trigger_step(self, step_idx: int):
        """Fires note_on events for all 8 channels at this step."""
        row_notes = self.pattern[step_idx]
        for ch, note in enumerate(row_notes):
            if note and note not in ("---", "...", "OFF"):
                self.synth.note_on(ch, note, velocity=0.85)

    def export_wav(self) -> str:
        """Exports the active song to storage/audio/tracker_export.wav."""
        out_dir = os.path.join(os.path.expanduser("~"), "storage", "audio")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "soundtracker_export.wav")

        class StepPlayer:
            def __init__(self, app):
                self.app = app
                self.samples_per_step = int(44100 * ((60.0 / app.bpm) * 0.25))

            def step_sample(self, sample_idx):
                if sample_idx % self.samples_per_step == 0:
                    step = (sample_idx // self.samples_per_step) % self.app.num_steps
                    self.app._trigger_step(step)

        player = StepPlayer(self)
        duration_sec = (self.num_steps * (60.0 / self.bpm) * 0.25) * 2.0  # 2 full loops
        self.synth.export_wav(out_path, duration_sec=duration_sec, pattern_player=player)
        self.status_message = f"Exported WAV: storage/audio/soundtracker_export.wav"
        return out_path

    # --------------------------------------------------------------------------
    # Rendering
    # --------------------------------------------------------------------------

    def render(self, fb: bytearray, font: Any, win_x: int, win_y: int, win_w: int, win_h: int):
        """
        Renders the full SoundTracker DAW UI inside window client bounds.
        """
        cx, cy, cw, ch = win_x + 2, win_y + 20, win_w - 4, win_h - 22
        clip = (cx, cy, cx + cw, cy + ch)

        # 1. Main Background
        self._fill_rect(fb, cx, cy, cw, ch, COLOR_BG_DARK, clip)

        # 2. Top Toolbar (Controls, BPM, Octave, Mode, Export)
        self._render_toolbar(fb, font, cx, cy, cw, 34, clip)

        # 3. DSP Visualizer Header (Oscilloscope & 16-Band Spectrum)
        vis_h = 58
        self._render_visualizers(fb, font, cx, cy + 34, cw, vis_h, clip)

        # 4. Pattern Matrix Grid / Piano Roll
        grid_y = cy + 34 + vis_h
        grid_h = ch - (34 + vis_h + 20)
        if self.view_mode == "tracker":
            self._render_tracker_grid(fb, font, cx, grid_y, cw, grid_h, clip)
        else:
            self._render_piano_roll(fb, font, cx, grid_y, cw, grid_h, clip)

        # 5. Bottom Telemetry & Status Bar
        sb_y = cy + ch - 20
        self._render_status_bar(fb, font, cx, sb_y, cw, 20, clip)

    def _render_toolbar(self, fb: bytearray, font: Any, x: int, y: int, w: int, h: int, clip: Tuple):
        """Draws top control bar."""
        self._fill_rect(fb, x, y, w, h, COLOR_BG_PANEL, clip)
        self._draw_line(fb, x, y + h - 1, x + w, y + h - 1, COLOR_BORDER_CYAN, clip)

        # Play / Pause button
        play_bg = COLOR_ACCENT_GREEN if self.is_playing else 0x00334155
        play_txt = "STOP" if self.is_playing else "PLAY"
        self._draw_btn(fb, font, x + 8, y + 6, 52, 22, play_txt, play_bg, COLOR_TEXT_WHITE, clip)

        # BPM Controls
        self._draw_btn(fb, font, x + 66, y + 6, 22, 22, "-", 0x00334155, COLOR_TEXT_WHITE, clip)
        self._draw_str(fb, font, x + 94, y + 11, f"BPM:{self.bpm}", COLOR_ACCENT_CYAN, clip)
        self._draw_btn(fb, font, x + 154, y + 6, 22, 22, "+", 0x00334155, COLOR_TEXT_WHITE, clip)

        # Octave Controls
        self._draw_btn(fb, font, x + 184, y + 6, 22, 22, "-", 0x00334155, COLOR_TEXT_WHITE, clip)
        self._draw_str(fb, font, x + 212, y + 11, f"OCT:{self.octave}", COLOR_ACCENT_AMBER, clip)
        self._draw_btn(fb, font, x + 260, y + 6, 22, 22, "+", 0x00334155, COLOR_TEXT_WHITE, clip)

        # View Mode Toggle
        mode_lbl = "PIANO" if self.view_mode == "tracker" else "TRACK"
        self._draw_btn(fb, font, x + 290, y + 6, 56, 22, mode_lbl, 0x00334155, COLOR_ACCENT_CYAN, clip)

        # Export WAV Button
        self._draw_btn(fb, font, x + w - 100, y + 6, 92, 22, "EXPORT WAV", COLOR_BORDER_CYAN, COLOR_TEXT_WHITE, clip)

    def _render_visualizers(self, fb: bytearray, font: Any, x: int, y: int, w: int, h: int, clip: Tuple):
        """Draws live oscilloscope and 16-band spectrum analyzer."""
        self._fill_rect(fb, x, y, w, h, 0x000B1120, clip)
        self._draw_line(fb, x, y + h - 1, x + w, y + h - 1, COLOR_BORDER_CYAN, clip)

        half_w = w // 2

        # 1. Left: Real-time Oscilloscope
        self._draw_str(fb, font, x + 8, y + 4, "OSCILLOSCOPE (44.1 kHz)", COLOR_ACCENT_CYAN, clip)
        osc_y_mid = y + 32
        osc_buf = self.synth.oscilloscope_buffer
        step_x = max(1, (half_w - 20) // 128)

        prev_px = x + 10
        prev_py = osc_y_mid
        for i in range(128):
            sample = osc_buf[(i * 2) % len(osc_buf)]
            px = x + 10 + i * step_x
            py = int(osc_y_mid - sample * 22)
            py = max(y + 16, min(y + h - 6, py))
            self._draw_line(fb, prev_px, prev_py, px, py, COLOR_ACCENT_GREEN, clip)
            prev_px, prev_py = px, py

        # Center separator
        self._draw_line(fb, x + half_w, y + 4, x + half_w, y + h - 4, 0x001E293B, clip)

        # 2. Right: 16-Band Spectrum Analyzer
        spec_x = x + half_w + 10
        self._draw_str(fb, font, spec_x, y + 4, "16-BAND SPECTRUM ANALYZER", COLOR_ACCENT_PURPLE, clip)

        bar_w = max(4, (half_w - 30) // 16 - 2)
        for b in range(16):
            mag = self.synth.spectrum_bins[b]
            bar_h = int(mag * 36)
            bx = spec_x + b * (bar_w + 2)
            by = y + h - 6 - bar_h

            col = COLOR_ACCENT_GREEN if b < 6 else (COLOR_ACCENT_CYAN if b < 11 else COLOR_ACCENT_PURPLE)
            self._fill_rect(fb, bx, by, bar_w, max(2, bar_h), col, clip)

    def _render_tracker_grid(self, fb: bytearray, font: Any, x: int, y: int, w: int, h: int, clip: Tuple):
        """Draws 8-channel tracker matrix pattern editor."""
        row_h = 16
        visible_rows = (h - 22) // row_h
        ch_w = max(45, (w - 36) // 8)

        # Channel Column Headers
        self._fill_rect(fb, x, y, w, 20, COLOR_BG_PANEL, clip)
        self._draw_str(fb, font, x + 4, y + 5, "ROW", COLOR_TEXT_MUTED, clip)

        for ch in range(8):
            ch_x = x + 34 + ch * ch_w
            ch_name = f"CH{ch+1}"
            ch_col = COLOR_ACCENT_AMBER if self.synth.channels[ch].is_solo else (
                COLOR_ACCENT_RED if self.synth.channels[ch].is_muted else COLOR_ACCENT_CYAN
            )
            self._draw_str(fb, font, ch_x + 4, y + 5, ch_name, ch_col, clip)

        self._draw_line(fb, x, y + 20, x + w, y + 20, COLOR_BORDER_CYAN, clip)

        # Pattern Rows
        start_row = max(0, min(self.num_steps - visible_rows, self.cursor_row - visible_rows // 2))

        for v_idx in range(visible_rows):
            r = start_row + v_idx
            if r >= self.num_steps:
                break

            ry = y + 22 + v_idx * row_h
            is_active_step = (r == self.current_step and self.is_playing)
            is_cursor_row = (r == self.cursor_row)

            # Row background
            if is_active_step:
                self._fill_rect(fb, x, ry, w, row_h, 0x00034B68, clip)
            elif is_cursor_row:
                self._fill_rect(fb, x, ry, w, row_h, 0x001E293B, clip)
            elif r % 4 == 0:
                self._fill_rect(fb, x, ry, w, row_h, 0x00131D31, clip)

            # Row Index
            row_col = COLOR_ACCENT_AMBER if is_active_step else COLOR_TEXT_MUTED
            self._draw_str(fb, font, x + 6, ry + 3, f"{r:02d}", row_col, clip)

            # Channels
            for ch in range(8):
                ch_x = x + 34 + ch * ch_w
                note = self.pattern[r][ch]

                is_selected_cell = (r == self.cursor_row and ch == self.cursor_col)
                if is_selected_cell:
                    self._fill_rect(fb, ch_x, ry, ch_w - 2, row_h, 0x000284C7, clip)

                txt_col = COLOR_TEXT_WHITE if note != "---" else 0x00475569
                self._draw_str(fb, font, ch_x + 6, ry + 3, note, txt_col, clip)

    def _render_piano_roll(self, fb: bytearray, font: Any, x: int, y: int, w: int, h: int, clip: Tuple):
        """Draws visual piano roll view."""
        self._fill_rect(fb, x, y, w, h, COLOR_BG_DARK, clip)
        self._draw_str(fb, font, x + 10, y + 10, "PIANO ROLL STEP SEQUENCER (Channel 1 Active)", COLOR_ACCENT_CYAN, clip)

        notes_scale = ["B-4", "A#4", "A-4", "G#4", "G-4", "F#4", "F-4", "E-4", "D#4", "D-4", "C#4", "C-4"]
        step_w = max(14, (w - 60) // self.num_steps)
        row_h = 16

        for n_idx, n_name in enumerate(notes_scale):
            ny = y + 32 + n_idx * row_h
            is_black_key = "#" in n_name
            bg_col = 0x00131D31 if is_black_key else 0x001E293B
            self._fill_rect(fb, x + 40, ny, w - 50, row_h - 1, bg_col, clip)
            self._draw_str(fb, font, x + 6, ny + 3, n_name, COLOR_TEXT_MUTED, clip)

            for s in range(self.num_steps):
                sx = x + 40 + s * step_w
                if s == self.current_step and self.is_playing:
                    self._fill_rect(fb, sx, ny, step_w - 1, row_h - 1, 0x00034B68, clip)

                # Check if this note is present in active track (channel 0)
                if self.pattern[s][0] == n_name:
                    self._fill_rect(fb, sx, ny, step_w - 1, row_h - 1, COLOR_ACCENT_GREEN, clip)

    def _render_status_bar(self, fb: bytearray, font: Any, x: int, y: int, w: int, h: int, clip: Tuple):
        """Draws bottom status bar."""
        self._fill_rect(fb, x, y, w, h, COLOR_BG_PANEL, clip)
        msg = self.status_message[:32]
        self._draw_str(fb, font, x + 8, y + 5, msg, COLOR_TEXT_MUTED, clip)

        controls_hint = "[Space] Play | [A-K] Notes | [Del] Clear"
        self._draw_str(fb, font, x + w - 290, y + 5, controls_hint, COLOR_ACCENT_CYAN, clip)

    # --------------------------------------------------------------------------
    # Interactive Event Handlers
    # --------------------------------------------------------------------------

    def handle_click(self, rel_x: int, rel_y: int) -> bool:
        """Handles mouse clicks within window client bounds."""
        # Toolbar Clicks (y in 0..34)
        if 0 <= rel_y <= 34:
            # Play / Stop button (x: 8..60)
            if 8 <= rel_x <= 60:
                self.toggle_playback()
                return True
            # BPM - (x: 66..88)
            elif 66 <= rel_x <= 88:
                self.bpm = max(40, self.bpm - 4)
                self.status_message = f"Tempo: {self.bpm} BPM"
                return True
            # BPM + (x: 154..176)
            elif 154 <= rel_x <= 176:
                self.bpm = min(240, self.bpm + 4)
                self.status_message = f"Tempo: {self.bpm} BPM"
                return True
            # Octave - (x: 184..206)
            elif 184 <= rel_x <= 206:
                self.octave = max(1, self.octave - 1)
                self.status_message = f"Base Octave: {self.octave}"
                return True
            # Octave + (x: 260..282)
            elif 260 <= rel_x <= 282:
                self.octave = min(7, self.octave + 1)
                self.status_message = f"Base Octave: {self.octave}"
                return True
            # Mode Toggle (x: 290..346)
            elif 290 <= rel_x <= 346:
                self.view_mode = "piano_roll" if self.view_mode == "tracker" else "tracker"
                self.status_message = f"Switched view to {self.view_mode.upper()}."
                return True
            # Export WAV (rel_x >= width - 110)
            elif rel_x >= 500:
                self.export_wav()
                return True

        # Grid Clicks
        grid_y = 34 + 58
        if rel_y >= grid_y + 20:
            ch_w = max(45, (620 - 36) // 8)
            col = (rel_x - 34) // ch_w
            row_idx = (rel_y - (grid_y + 20)) // 16
            if 0 <= col < 8 and 0 <= row_idx < self.num_steps:
                self.cursor_col = col
                self.cursor_row = min(self.num_steps - 1, row_idx)
                return True

        return False

    def handle_key(self, key: str) -> bool:
        """Handles tracker keyboard navigation and musical typing."""
        if key == " ":
            self.toggle_playback()
            return True

        elif key in ("KEY_UP", "UP"):
            self.cursor_row = max(0, self.cursor_row - 1)
            return True

        elif key in ("KEY_DOWN", "DOWN"):
            self.cursor_row = min(self.num_steps - 1, self.cursor_row + 1)
            return True

        elif key in ("KEY_LEFT", "LEFT"):
            self.cursor_col = max(0, self.cursor_col - 1)
            return True

        elif key in ("KEY_RIGHT", "RIGHT"):
            self.cursor_col = min(7, self.cursor_col + 1)
            return True

        elif key in ("DELETE", "BACKSPACE", "\b"):
            self.pattern[self.cursor_row][self.cursor_col] = "---"
            self.cursor_row = min(self.num_steps - 1, self.cursor_row + 1)
            return True

        elif key in ("t", "T"):
            self.view_mode = "piano_roll" if self.view_mode == "tracker" else "tracker"
            return True

        # Musical keyboard input (A-K notes)
        elif key in KEY_NOTE_MAP:
            base_note = KEY_NOTE_MAP[key]
            octave = self.octave + (1 if key in ("k", "K") else 0)
            full_note = f"{base_note}-{octave}"
            self.pattern[self.cursor_row][self.cursor_col] = full_note
            # Audition the note immediately
            self.synth.note_on(self.cursor_col, full_note, velocity=0.85)
            self.status_message = f"Ch {self.cursor_col + 1} -> {full_note}"
            self.cursor_row = min(self.num_steps - 1, self.cursor_row + 1)
            return True

        return False

    # --------------------------------------------------------------------------
    # Drawing Primitives
    # --------------------------------------------------------------------------

    def _fill_rect(self, fb: bytearray, x: int, y: int, w: int, h: int, color: int, clip: Tuple):
        x1, y1 = max(clip[0], x), max(clip[1], y)
        x2, y2 = min(clip[2], x + w), min(clip[3], y + h)
        if x2 <= x1 or y2 <= y1:
            return
        b, g, r = color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF
        row_bytes = bytes([b, g, r, 0xFF]) * (x2 - x1)
        mv = memoryview(fb)
        sw = self.screen_w
        for row in range(y1, y2):
            off = (row * sw + x1) * 4
            mv[off : off + (x2 - x1) * 4] = row_bytes

    def _draw_line(self, fb: bytearray, x1: int, y1: int, x2: int, y2: int, color: int, clip: Tuple):
        b, g, r = color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF
        px = bytes([b, g, r, 0xFF])
        sw, sh = self.screen_w, self.screen_h
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        cx0, cy0, cx1, cy1 = clip
        while True:
            if cx0 <= x1 < cx1 and cy0 <= y1 < cy1 and 0 <= x1 < sw and 0 <= y1 < sh:
                off = (y1 * sw + x1) * 4
                fb[off : off + 4] = px
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy

    def _draw_btn(self, fb: bytearray, font: Any, x: int, y: int, w: int, h: int,
                  text: str, bg_color: int, txt_color: int, clip: Tuple):
        self._fill_rect(fb, x, y, w, h, bg_color, clip)
        self._draw_line(fb, x, y, x + w, y, COLOR_BORDER_CYAN, clip)
        self._draw_line(fb, x, y + h - 1, x + w, y + h - 1, COLOR_BORDER_CYAN, clip)
        self._draw_line(fb, x, y, x, y + h, COLOR_BORDER_CYAN, clip)
        self._draw_line(fb, x + w - 1, y, x + w - 1, y + h, COLOR_BORDER_CYAN, clip)

        tx = x + max(2, (w - len(text) * 8) // 2)
        ty = y + max(2, (h - 8) // 2)
        self._draw_str(fb, font, tx, ty, text, txt_color, clip)

    def _draw_str(self, fb: bytearray, font: Any, x: int, y: int, text: str, color: int, clip: Tuple):
        cx0, cy0, cx1, cy1 = clip
        sw = self.screen_w
        b, g, r = color & 0xFF, (color >> 8) & 0xFF, (color >> 16) & 0xFF
        c_bytes = bytes([b, g, r, 0xFF])

        curr_x = x
        for ch in text:
            if curr_x + 8 > cx1:
                break
            code = ord(ch)
            glyph = font.get(code) if isinstance(font, dict) else None
            if glyph:
                if cy0 <= y and y + 7 < cy1 and cx0 <= curr_x and curr_x + 7 < cx1:
                    for row in range(8):
                        byte_val = glyph[row]
                        if byte_val:
                            row_off = ((y + row) * sw + curr_x) * 4
                            for col in range(8):
                                if (byte_val >> (7 - col)) & 1:
                                    off = row_off + col * 4
                                    fb[off : off + 4] = c_bytes
            curr_x += 8
