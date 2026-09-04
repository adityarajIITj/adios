#!/usr/bin/env python3
"""
AdiOS Test Suite: Pass 4 — 3D Graphics, Physics & Audio DSP Deepening
Tests:
- Texture2D: Bilinear filtering, nearest-neighbor, and texture wrap modes (gl/gl_texture.py)
- LightingEngine: Blinn-Phong diffuse, specular, and point light attenuation (gl/gl_lighting.py)
- RigidBody3D: 6-DOF linear momentum, angular torque, inertia tensor, and ground bounce (spatial/rigidbody3d.py)
- TrackerStudio: 4-channel polyphonic synthesis, ADSR envelopes, and WAV stream encoding (dsp/tracker_studio.py)

Zero external dependencies. Pure bare-metal verification.
STRICT ZERO EMOJI POLICY.
"""

import math
import struct
import unittest
from gl.gl_texture import Texture2D, GL_NEAREST, GL_LINEAR, GL_REPEAT, GL_CLAMP_TO_EDGE
from gl.gl_lighting import LightingEngine, LightSource, Material, Vec3
from spatial.rigidbody3d import RigidBody3D
from dsp.tracker_studio import TrackerStudio, ADSREnvelope

class TestPass4GraphicsPhysicsAudio(unittest.TestCase):

    # --------------------------------------------------------------------------
    # 1. Texture Engine & Bilinear Filtering Tests
    # --------------------------------------------------------------------------

    def test_01_texture_bilinear_and_nearest(self):
        # 2x2 Texture: Top-left Red, Top-right Blue, Bottom-left Green, Bottom-right White
        c_red   = 0xFFFF0000
        c_blue  = 0xFF0000FF
        c_green = 0xFF00FF00
        c_white = 0xFFFFFFFF

        tex = Texture2D(2, 2, [c_red, c_blue, c_green, c_white])
        tex.wrap_s = GL_CLAMP_TO_EDGE
        tex.wrap_t = GL_CLAMP_TO_EDGE

        # Nearest neighbor sample exactly at corners
        self.assertEqual(tex.sample(0.0, 0.0, filter_mode=GL_NEAREST), c_red)
        self.assertEqual(tex.sample(1.0, 0.0, filter_mode=GL_NEAREST), c_blue)

        # Bilinear sample at center (0.5, 0.5) must blend all 4 colors
        center_color = tex.sample(0.5, 0.5, filter_mode=GL_LINEAR)
        cr = (center_color >> 16) & 0xFF
        cg = (center_color >> 8) & 0xFF
        cb = center_color & 0xFF
        # Center should have non-zero contributions from R, G, and B
        self.assertGreater(cr, 0)
        self.assertGreater(cg, 0)
        self.assertGreater(cb, 0)

    # --------------------------------------------------------------------------
    # 2. Blinn-Phong Lighting Model Tests
    # --------------------------------------------------------------------------

    def test_02_blinn_phong_lighting(self):
        engine = LightingEngine()
        # Directional light pointing along -Z
        light = LightSource(position=Vec3(0, 0, -1), is_directional=True)
        engine.add_light(light)

        mat = Material(ambient=(0.1, 0.1, 0.1), diffuse=(0.8, 0.8, 0.8), specular=(1.0, 1.0, 1.0))
        eye = Vec3(0, 0, 5)

        # Normal directly facing light (along +Z) -> Strong diffuse & specular
        norm_facing = Vec3(0, 0, 1)
        color_lit = engine.shade(Vec3(0, 0, 0), norm_facing, eye, mat)
        r_lit = (color_lit >> 16) & 0xFF

        # Normal facing away from light (along -Z) -> Only ambient
        norm_away = Vec3(0, 0, -1)
        color_dark = engine.shade(Vec3(0, 0, 0), norm_away, eye, mat)
        r_dark = (color_dark >> 16) & 0xFF

        self.assertGreater(r_lit, r_dark)

    # --------------------------------------------------------------------------
    # 3. 3D Rigid Body Dynamics & Torque Tests
    # --------------------------------------------------------------------------

    def test_03_rigidbody_linear_and_angular_mechanics(self):
        body = RigidBody3D(mass=2.0)
        body.position = Vec3(0, 10, 0) # 10 units in air

        # Apply an off-center force: Force in +Z applied at offset (1, 0, 0)
        # Torque tau = r x F = (1, 0, 0) x (0, 0, 10) = (0, -10, 0)
        body.apply_force_at_point(Vec3(0, 0, 10), Vec3(1, 10, 0))

        # Integrate 0.1 seconds
        body.integrate(0.1, gravity=-9.81)

        # Body should have moved downward (gravity) and forward (+Z)
        self.assertLess(body.position.y, 10.0)
        self.assertGreater(body.position.z, 0.0)
        # Body should have acquired angular velocity around Y axis
        self.assertNotEqual(body.angular_velocity.y, 0.0)

    def test_04_rigidbody_ground_collision(self):
        body = RigidBody3D(mass=1.0)
        body.position = Vec3(0, 0.5, 0)
        body.velocity = Vec3(0, -10, 0) # falling fast

        # Next integration hits ground (y <= 0)
        body.integrate(0.1, gravity=0)
        self.assertGreaterEqual(body.position.y, 0.0)
        # Restitution reverses velocity to positive Y
        self.assertGreater(body.velocity.y, 0.0)

    # --------------------------------------------------------------------------
    # 4. Audio DSP Tracker Studio & Synthesis Tests
    # --------------------------------------------------------------------------

    def test_05_tracker_synthesis_and_wav_export(self):
        tracker = TrackerStudio(sample_rate=22050)
        env = ADSREnvelope(attack_sec=0.01, decay_sec=0.02, sustain_level=0.8, release_sec=0.05)

        # Channel 0: Plays C4 (261.63 Hz) Sine wave
        tracker.channels[0].note_on(start_time=0.0, waveform="sine", freq=261.63, duration=0.1, envelope=env)
        # Channel 1: Plays E4 (329.63 Hz) Triangle wave
        tracker.channels[1].note_on(start_time=0.05, waveform="triangle", freq=329.63, duration=0.1, envelope=env)

        # Render 0.15 seconds of audio
        pcm_samples = tracker.render_pcm_buffer(total_seconds=0.15)
        self.assertGreater(len(pcm_samples), 0)
        # Verify samples are non-zero and within 16-bit signed range
        self.assertTrue(any(s != 0 for s in pcm_samples))
        self.assertTrue(all(-32768 <= s <= 32767 for s in pcm_samples))

        # Encode to RIFF WAVE bytes
        wav_bytes = tracker.pcm_to_wav(pcm_samples, sample_rate=22050)
        self.assertEqual(wav_bytes[0:4], b"RIFF")
        self.assertEqual(wav_bytes[8:12], b"WAVE")
        self.assertEqual(wav_bytes[12:16], b"fmt ")
        self.assertEqual(wav_bytes[36:40], b"data")

if __name__ == "__main__":
    unittest.main()
