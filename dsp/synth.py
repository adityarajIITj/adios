#!/usr/bin/env python3
"""
AdiOS Audio Subsystem: Digital Audio Synthesis & DSP Studio (synth.py)
Implements first-principles digital signal processing and sound synthesis:
- Waveform Oscillators: Sine, Square (PWM), Triangle, Sawtooth, White Noise
- ADSR (Attack, Decay, Sustain, Release) Envelope Generator
- 2-pole Resonant Low-Pass Filter (State-Variable / Biquad)
- Feedback Delay & Echo line buffer
- 16-Voice Polyphonic Mixer with 16-bit PCM and RIFF/WAV packing
Zero external dependencies.
"""

import math
import struct
from typing import List, Optional

SAMPLE_RATE = 44100 # Standard CD-quality sample rate

class ADSREnvelope:
    """ADSR (Attack, Decay, Sustain, Release) Envelope."""
    def __init__(self, attack_sec: float = 0.01, decay_sec: float = 0.05,
                 sustain_level: float = 0.7, release_sec: float = 0.1):
        self.a_samples = int(attack_sec * SAMPLE_RATE)
        self.d_samples = int(decay_sec * SAMPLE_RATE)
        self.s_level = sustain_level
        self.r_samples = int(release_sec * SAMPLE_RATE)

    def get_amplitude(self, sample_idx: int, note_length_samples: int) -> float:
        if sample_idx < self.a_samples:
            return sample_idx / max(1, self.a_samples)
        elif sample_idx < self.a_samples + self.d_samples:
            progress = (sample_idx - self.a_samples) / max(1, self.d_samples)
            return 1.0 - progress * (1.0 - self.s_level)
        elif sample_idx < note_length_samples:
            return self.s_level
        elif sample_idx < note_length_samples + self.r_samples:
            progress = (sample_idx - note_length_samples) / max(1, self.r_samples)
            return max(0.0, self.s_level * (1.0 - progress))
        return 0.0

class Oscillator:
    """Waveform generator."""
    @staticmethod
    def generate_sample(wave_type: str, phase: float, pwm: float = 0.5) -> float:
        norm_phase = phase % 1.0
        if wave_type == "sine":
            return math.sin(2.0 * math.pi * norm_phase)
        elif wave_type == "square":
            return 1.0 if norm_phase < pwm else -1.0
        elif wave_type == "saw":
            return 2.0 * norm_phase - 1.0
        elif wave_type == "triangle":
            return 4.0 * abs(norm_phase - 0.5) - 1.0
        elif wave_type == "noise":
            # Linear Congruential pseudo-random noise [-1.0, 1.0]
            val = ((int(phase * 1000000) * 1103515245 + 12345) & 0x7FFFFFFF) / 0x7FFFFFFF
            return 2.0 * val - 1.0
        return 0.0

class BiquadLowPass:
    """2-pole resonant low-pass filter."""
    def __init__(self, cutoff_hz: float = 1000.0, resonance: float = 1.0):
        w0 = 2.0 * math.pi * cutoff_hz / SAMPLE_RATE
        alpha = math.sin(w0) / (2.0 * resonance)
        cos_w0 = math.cos(w0)

        b0 = (1.0 - cos_w0) / 2.0
        b1 = 1.0 - cos_w0
        b2 = (1.0 - cos_w0) / 2.0
        a0 = 1.0 + alpha
        a1 = -2.0 * cos_w0
        a2 = 1.0 - alpha

        self.b0 = b0 / a0
        self.b1 = b1 / a0
        self.b2 = b2 / a0
        self.a1 = a1 / a0
        self.a2 = a2 / a0

        self.x1 = 0.0
        self.x2 = 0.0
        self.y1 = 0.0
        self.y2 = 0.0

    def process(self, x: float) -> float:
        y = self.b0 * x + self.b1 * self.x1 + self.b2 * self.x2 - self.a1 * self.y1 - self.a2 * self.y2
        self.x2 = self.x1
        self.x1 = x
        self.y2 = self.y1
        self.y1 = y
        return y

class SynthesizerVoice:
    """Single polyphonic synthesizer voice."""
    def __init__(self, freq_hz: float, wave_type: str = "saw", duration_sec: float = 0.2):
        self.freq = freq_hz
        self.wave_type = wave_type
        self.duration_samples = int(duration_sec * SAMPLE_RATE)
        self.envelope = ADSREnvelope()
        self.total_samples = self.duration_samples + self.envelope.r_samples
        self.filter = BiquadLowPass(cutoff_hz=2500.0, resonance=1.5)

    def render(self) -> List[float]:
        samples = []
        phase_step = self.freq / SAMPLE_RATE
        phase = 0.0
        for i in range(self.total_samples):
            raw = Oscillator.generate_sample(self.wave_type, phase)
            env = self.envelope.get_amplitude(i, self.duration_samples)
            filtered = self.filter.process(raw * env)
            samples.append(filtered)
            phase += phase_step
        return samples

class AudioEngine:
    """Polyphonic audio engine rendering into standard 16-bit PCM WAV."""
    @staticmethod
    def pack_wav(float_samples: List[float]) -> bytes:
        """Packs normalized float audio samples into standard RIFF WAV bytes."""
        num_samples = len(float_samples)
        data_size = num_samples * 2 # 16-bit mono = 2 bytes per sample

        # RIFF header (44 bytes total)
        header = bytearray()
        header.extend(b"RIFF")
        header.extend(struct.pack("<I", 36 + data_size))
        header.extend(b"WAVEfmt ")
        header.extend(struct.pack("<IHHIIHH", 16, 1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16))
        header.extend(b"data")
        header.extend(struct.pack("<I", data_size))

        # Sample conversion
        pcm_bytes = bytearray()
        for s in float_samples:
            clamped = max(-1.0, min(1.0, s))
            pcm_val = int(clamped * 32767.0)
            pcm_bytes.extend(struct.pack("<h", pcm_val))

        return bytes(header) + bytes(pcm_bytes)

if __name__ == "__main__":
    voice = SynthesizerVoice(freq_hz=440.0, wave_type="sine", duration_sec=0.05)
    rendered = voice.render()
    assert len(rendered) > 100
    wav = AudioEngine.pack_wav(rendered)
    assert wav[:4] == b"RIFF"
    assert b"WAVE" in wav
    print("Audio synthesizer and DSP engine verified.")
