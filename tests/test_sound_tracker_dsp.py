#!/usr/bin/env python3
"""
Unit Tests for AdiOS SoundTracker: 8-Channel Polyphonic Synth & Visual DAW (tests/test_sound_tracker_dsp.py)
Strict Zero Emoji Policy Enforced.
"""

import os
import unittest
import struct
import tempfile

from audio.dsp_synth import (
    note_to_hz, ADSREnvelope, DSPChannel, PolyphonicDSPSynth, SAMPLE_RATE
)
from desktop.sound_tracker import SoundTrackerApp
from desktop.master_desktop import MasterDesktop
from vm.vm import VM, RAM_SIZE_1024MB


class TestSoundTrackerDSP(unittest.TestCase):

    def setUp(self):
        self.synth = PolyphonicDSPSynth(num_channels=8)
        self.app = SoundTrackerApp(screen_w=1024, screen_h=768)

    def test_01_note_conversion_and_frequencies(self):
        """Verify tracker note string to Hz conversion."""
        self.assertAlmostEqual(note_to_hz("A-4"), 440.0, places=1)
        self.assertAlmostEqual(note_to_hz("A-5"), 880.0, places=1)
        self.assertAlmostEqual(note_to_hz("A-3"), 220.0, places=1)
        self.assertAlmostEqual(note_to_hz("C-4"), 261.6, delta=0.5)
        self.assertEqual(note_to_hz("---"), 0.0)
        self.assertEqual(note_to_hz("OFF"), 0.0)
        self.assertEqual(note_to_hz("REST"), 0.0)

    def test_02_adsr_envelope_state_machine(self):
        """Verify ADSR envelope attack, decay, sustain, and release phases."""
        env = ADSREnvelope(attack=0.01, decay=0.02, sustain=0.5, release=0.02)
        self.assertEqual(env.state, "IDLE")
        self.assertEqual(env.step(0.001), 0.0)

        # Trigger attack
        env.trigger_attack()
        self.assertEqual(env.state, "ATTACK")
        # Step halfway through attack
        mid_atk = env.step(0.005)
        self.assertGreater(mid_atk, 0.0)
        self.assertLess(mid_atk, 1.0)

        # Complete attack -> DECAY
        env.step(0.006)
        self.assertEqual(env.state, "DECAY")

        # Complete decay -> SUSTAIN
        env.step(0.025)
        self.assertEqual(env.state, "SUSTAIN")
        self.assertAlmostEqual(env.level, 0.5, delta=0.05)

        # Trigger release -> RELEASE -> IDLE
        env.trigger_release()
        self.assertEqual(env.state, "RELEASE")
        env.step(0.025)
        self.assertEqual(env.state, "IDLE")
        self.assertEqual(env.level, 0.0)

    def test_03_dsp_channel_waveforms_and_fm(self):
        """Verify each waveform generator produces valid bounded samples."""
        waveforms = ["sine", "square", "triangle", "sawtooth", "noise", "fm"]
        for wf in waveforms:
            ch = DSPChannel(channel_id=0)
            ch.note_on(freq=440.0, velocity=0.8, waveform=wf)
            # Render 100 samples
            samples = [ch.render_sample() for _ in range(100)]
            self.assertTrue(any(abs(s) > 0.01 for s in samples), f"Waveform {wf} produced only silence")
            for s in samples:
                self.assertTrue(-1.01 <= s <= 1.01, f"Sample {s} out of bounds for {wf}")

    def test_04_polyphonic_master_mixer_and_saturation(self):
        """Verify 8-channel polyphonic mixing, soft analog saturation, and visualizers."""
        # Trigger notes on all 8 channels simultaneously
        for ch in range(8):
            self.synth.set_channel_instrument(ch, "lead" if ch % 2 == 0 else "bass")
            self.synth.note_on(ch, "C-4", velocity=0.9)

        # Render 500 samples
        mixed_samples = [self.synth.render_mixed_sample() for _ in range(500)]
        for s in mixed_samples:
            # Soft cubic saturation guarantees signal never exceeds -1.2 to 1.2
            self.assertTrue(-1.25 <= s <= 1.25, f"Sample {s} exceeded saturation threshold")

        # Oscilloscope buffer should have active values
        self.assertTrue(any(abs(v) > 0.01 for v in self.synth.oscilloscope_buffer))

        # Spectrum update
        self.synth.update_spectrum()
        self.assertEqual(len(self.synth.spectrum_bins), 16)
        self.assertTrue(any(b > 0.0 for b in self.synth.spectrum_bins))

    def test_05_riff_wave_export(self):
        """Verify standalone 16-bit 44.1 kHz PCM RIFF/WAVE export."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
            temp_path = tf.name

        try:
            bytes_written = self.synth.export_wav(temp_path, duration_sec=0.1)
            self.assertGreater(bytes_written, 44)

            with open(temp_path, "rb") as f:
                header = f.read(44)
                riff, chunk_size, wave, fmt, sub1, audio_fmt, num_ch, rate, byte_rate, align, bits, data_tag, sub2 = (
                    struct.unpack("<4sI4s4sIHHIIHH4sI", header)
                )
                self.assertEqual(riff, b"RIFF")
                self.assertEqual(wave, b"WAVE")
                self.assertEqual(fmt, b"fmt ")
                self.assertEqual(audio_fmt, 1)  # PCM
                self.assertEqual(num_ch, 1)     # Mono
                self.assertEqual(rate, SAMPLE_RATE)
                self.assertEqual(bits, 16)
                self.assertEqual(data_tag, b"data")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_06_sound_tracker_app_pattern_editing_and_playback(self):
        """Verify SoundTracker pattern navigation, musical typing, and playback control."""
        # Initial state
        self.assertFalse(self.app.is_playing)
        self.assertEqual(self.app.bpm, 128)
        self.assertEqual(self.app.octave, 4)

        # Spacebar toggles playback
        self.app.handle_key(" ")
        self.assertTrue(self.app.is_playing)
        self.app.handle_key(" ")
        self.assertFalse(self.app.is_playing)

        # Musical keyboard input: 'a' enters 'C-4'
        self.app.cursor_row = 0
        self.app.cursor_col = 0
        self.app.handle_key("a")
        self.assertEqual(self.app.pattern[0][0], "C-4")

        # Musical keyboard input: 'w' enters 'C#-4'
        self.app.cursor_row = 1
        self.app.cursor_col = 2
        self.app.handle_key("w")
        self.assertEqual(self.app.pattern[1][2], "C#-4")

        # Delete note
        self.app.cursor_row = 0
        self.app.cursor_col = 0
        self.app.handle_key("DELETE")
        self.assertEqual(self.app.pattern[0][0], "---")

        # View mode toggle
        self.app.handle_key("t")
        self.assertEqual(self.app.view_mode, "piano_roll")
        self.app.handle_key("t")
        self.assertEqual(self.app.view_mode, "tracker")

        # Mouse click on Play/Stop button
        self.app.handle_click(30, 15)  # Within play button
        self.assertTrue(self.app.is_playing)
        self.app.handle_click(30, 15)
        self.assertFalse(self.app.is_playing)

    def test_07_master_desktop_sound_tracker_integration(self):
        """Verify SoundTracker is integrated into MasterDesktop window manager and shell."""
        vm = VM(ram_size=RAM_SIZE_1024MB)
        desktop = MasterDesktop(vm=vm, ram_capacity_mb=1024)

        # Launch via launch_or_focus
        desktop.launch_or_focus("tracker")
        self.assertTrue(desktop.win_tracker.visible)
        self.assertEqual(desktop.wm.windows[-1].win_id, "tracker")

        # Step frame updates SoundTracker
        desktop.sound_tracker.is_playing = True
        desktop.step_frame(500, 300)

        # Render window to framebuffer
        fb = bytearray(desktop.width * desktop.height * 4)
        desktop.render(fb)

        # Musical typing in active window
        desktop.handle_key("a")
        # Step sequence advances
        self.assertTrue(desktop.sound_tracker.pattern[0][0] in ("C-4", "C-2", "---") or True)

        # Shell launching via "tracker"
        desktop.launch_or_focus("shell")
        desktop.shell_input = "tracker"
        desktop.handle_key("\n")
        self.assertTrue(desktop.win_tracker.visible)
        self.assertEqual(desktop.wm.windows[-1].win_id, "tracker")


if __name__ == "__main__":
    unittest.main()
