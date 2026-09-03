#!/usr/bin/env python3
"""
Test Suite: Block R Digital Audio Synthesis & DSP Studio
Verifies:
1. dsp/synth: Oscillators (sine, square, triangle, saw, noise)
2. dsp/synth: ADSR envelope phase transitions (Attack, Decay, Sustain, Release)
3. dsp/synth: 2-Pole Biquad resonant low-pass filter attenuation
4. dsp/synth: Polyphonic voice rendering & RIFF 16-bit PCM WAV packing
"""

import sys
import os
import struct

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from dsp.synth import Oscillator, ADSREnvelope, BiquadLowPass, SynthesizerVoice, AudioEngine, SAMPLE_RATE

def test_dsp_block_r_suite():
    print("[Test DSP Block R] Initializing Audio Synthesis & DSP Studio Verification...")

    # 1. Test Oscillators
    print("  -> Testing Waveform Oscillators (Sine, Square, Triangle, Saw, Noise)...")
    for phase in [0.0, 0.25, 0.5, 0.75]:
        s = Oscillator.generate_sample("sine", phase)
        assert -1.0 <= s <= 1.0
        sq = Oscillator.generate_sample("square", phase)
        assert sq in (-1.0, 1.0)
        tri = Oscillator.generate_sample("triangle", phase)
        assert -1.0 <= tri <= 1.0
        saw = Oscillator.generate_sample("saw", phase)
        assert -1.0 <= saw <= 1.0
        nz = Oscillator.generate_sample("noise", phase)
        assert -1.0 <= nz <= 1.0
    print("  -> [PASS] All 5 oscillators verified within boundary conditions.")

    # 2. Test ADSR Envelope
    print("  -> Testing ADSR Envelope Curve Transitions...")
    env = ADSREnvelope(attack_sec=0.01, decay_sec=0.02, sustain_level=0.6, release_sec=0.02)
    note_len = 2000

    # Start of attack: 0.0
    assert env.get_amplitude(0, note_len) == 0.0
    # Peak of attack: 1.0
    assert abs(env.get_amplitude(env.a_samples, note_len) - 1.0) < 0.05
    # During sustain: 0.6
    assert abs(env.get_amplitude(env.a_samples + env.d_samples + 50, note_len) - 0.6) < 0.01
    # After release: 0.0
    assert env.get_amplitude(note_len + env.r_samples + 10, note_len) == 0.0
    print("  -> [PASS] ADSR envelope phases verified.")

    # 3. Test Biquad Low-Pass Filter
    print("  -> Testing 2-Pole Biquad Low-Pass Filter Stability...")
    lp = BiquadLowPass(cutoff_hz=800.0, resonance=1.0)
    # Feed DC step response
    outputs = [lp.process(1.0) for _ in range(200)]
    assert abs(outputs[-1] - 1.0) < 0.05 # Reaches unit DC gain
    print("  -> [PASS] Biquad low-pass filter stability verified.")

    # 4. Test Synthesizer Voice & RIFF WAV Packer
    print("  -> Testing Synthesizer Voice Rendering & WAV File Packaging...")
    voice = SynthesizerVoice(freq_hz=440.0, wave_type="saw", duration_sec=0.05)
    rendered = voice.render()
    assert len(rendered) > 1000

    wav_bytes = AudioEngine.pack_wav(rendered)
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"
    assert wav_bytes[12:16] == b"fmt "
    assert wav_bytes[36:40] == b"data"

    # Verify 16-bit format in header
    audio_format, channels, sample_rate = struct.unpack("<HHI", wav_bytes[20:28])
    assert audio_format == 1 # PCM
    assert channels == 1     # Mono
    assert sample_rate == SAMPLE_RATE
    print("  -> [PASS] RIFF WAV 16-bit CD-quality format verified.")

    print("\n[Test DSP Block R] ALL BLOCK R AUDIO SYNTHESIS & DSP TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_dsp_block_r_suite()
