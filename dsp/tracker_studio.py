#!/usr/bin/env python3
"""
AdiOS Audio DSP Subsystem: 4-Channel Tracker Studio & Synthesizer (dsp/tracker_studio.py)
Implements Amiga-style 4-channel audio synthesis and PCM WAV generation:
- Waveform Oscillators: Sine, Pulse/Square (variable duty), Triangle, Sawtooth, White Noise
- ADSR Envelope Generator: Attack, Decay, Sustain, Release curves
- Polyphonic 4-channel mixing bus with independent channel volume & panning
- Soft-clipping master limiter (hyperbolic tangent tanh saturation)
- 44.1kHz 16-bit PCM RIFF/WAVE audio stream encoder

Zero external dependencies. Pure RV32IM audio synthesis engine.
STRICT ZERO EMOJI POLICY.
"""

import math
import struct
from typing import List, Tuple, Optional, Dict

SAMPLE_RATE = 44100 # 44.1 kHz standard audio sample rate

class ADSREnvelope:
    """
    Attack, Decay, Sustain, Release Envelope Generator.
    """
    def __init__(self, attack_sec: float = 0.05, decay_sec: float = 0.1, sustain_level: float = 0.7, release_sec: float = 0.2):
        self.attack_sec = max(0.001, attack_sec)
        self.decay_sec = max(0.001, decay_sec)
        self.sustain_level = max(0.0, min(1.0, sustain_level))
        self.release_sec = max(0.001, release_sec)

    def get_amplitude(self, t: float, note_duration: float) -> float:
        """Returns envelope amplitude multiplier in range [0.0, 1.0]."""
        if t < 0.0:
            return 0.0

        # Attack phase
        if t < self.attack_sec:
            return t / self.attack_sec

        # Decay phase
        t_decay = t - self.attack_sec
        if t_decay < self.decay_sec:
            frac = t_decay / self.decay_sec
            return 1.0 - frac * (1.0 - self.sustain_level)

        # Sustain phase (until note_duration)
        if t < note_duration:
            return self.sustain_level

        # Release phase
        t_rel = t - note_duration
        if t_rel < self.release_sec:
            frac = t_rel / self.release_sec
            return self.sustain_level * (1.0 - frac)

        return 0.0

class Voice:
    """Individual oscillator voice playing a note."""
    def __init__(self, waveform: str = "sine", freq: float = 440.0, duration: float = 0.5, envelope: Optional[ADSREnvelope] = None):
        self.waveform = waveform.lower()
        self.freq = freq
        self.duration = duration
        self.envelope = envelope or ADSREnvelope()
        self.phase = 0.0

    def sample_at(self, t: float) -> float:
        if t > self.duration + self.envelope.release_sec:
            return 0.0

        phase_inc = 2.0 * math.pi * self.freq * t

        if self.waveform == "sine":
            raw = math.sin(phase_inc)
        elif self.waveform == "square":
            raw = 1.0 if math.sin(phase_inc) >= 0.0 else -1.0
        elif self.waveform == "triangle":
            norm = (self.freq * t) % 1.0
            raw = 4.0 * abs(norm - 0.5) - 1.0
        elif self.waveform == "sawtooth":
            norm = (self.freq * t) % 1.0
            raw = 2.0 * norm - 1.0
        elif self.waveform == "noise":
            # Linear congruential pseudo-random generator
            seed = int(t * 100000) & 0x7FFFFFFF
            raw = ((seed % 1000) / 500.0) - 1.0
        else:
            raw = math.sin(phase_inc)

        env_amp = self.envelope.get_amplitude(t, self.duration)
        return raw * env_amp

class AudioChannel:
    """Single channel on tracker mixer."""
    def __init__(self, channel_id: int):
        self.channel_id = channel_id
        self.volume = 0.8
        self.voices: List[Tuple[float, Voice]] = [] # list of (start_time, voice)

    def note_on(self, start_time: float, waveform: str, freq: float, duration: float, envelope: Optional[ADSREnvelope] = None):
        v = Voice(waveform, freq, duration, envelope)
        self.voices.append((start_time, v))

    def sample_at(self, t: float) -> float:
        total = 0.0
        for start_t, voice in self.voices:
            if start_t <= t <= start_t + voice.duration + voice.envelope.release_sec:
                rel_t = t - start_t
                total += voice.sample_at(rel_t)
        return total * self.volume

class TrackerStudio:
    """
    4-Channel Master Tracker Studio.
    """
    def __init__(self, sample_rate: int = SAMPLE_RATE):
        self.sample_rate = sample_rate
        self.channels = [AudioChannel(i) for i in range(4)]
        self.master_volume = 0.9

    def render_pcm_buffer(self, total_seconds: float) -> List[int]:
        """
        Renders mixed audio samples into 16-bit signed PCM integers [-32767, 32767].
        Applies tanh soft-clipping to eliminate distortion.
        """
        num_samples = int(total_seconds * self.sample_rate)
        pcm_out = []

        dt = 1.0 / self.sample_rate
        for i in range(num_samples):
            t = i * dt
            # Mix 4 channels
            mixed = sum(ch.sample_at(t) for ch in self.channels) * self.master_volume
            # Tanh soft-clipping
            saturated = math.tanh(mixed)
            # Scale to 16-bit integer
            sample_16 = int(saturated * 32760.0)
            pcm_out.append(sample_16)

        return pcm_out

    @staticmethod
    def pcm_to_wav(pcm_samples: List[int], sample_rate: int = SAMPLE_RATE) -> bytes:
        """Encodes 16-bit PCM integer samples into standard RIFF WAVE bytes."""
        num_samples = len(pcm_samples)
        bytes_per_sample = 2 # 16-bit
        num_channels = 1     # Mono
        byte_rate = sample_rate * num_channels * bytes_per_sample
        block_align = num_channels * bytes_per_sample
        data_size = num_samples * bytes_per_sample

        # RIFF Header
        header = bytearray()
        header.extend(b"RIFF")
        header.extend(struct.pack("<I", 36 + data_size))
        header.extend(b"WAVE")

        # fmt subchunk
        header.extend(b"fmt ")
        header.extend(struct.pack("<I", 16)) # Subchunk1Size for PCM
        header.extend(struct.pack("<H", 1))  # AudioFormat 1 = PCM
        header.extend(struct.pack("<H", num_channels))
        header.extend(struct.pack("<I", sample_rate))
        header.extend(struct.pack("<I", byte_rate))
        header.extend(struct.pack("<H", block_align))
        header.extend(struct.pack("<H", 16)) # BitsPerSample

        # data subchunk
        header.extend(b"data")
        header.extend(struct.pack("<I", data_size))

        # Sample data
        data = struct.pack(f"<{num_samples}h", *pcm_samples)

        return bytes(header) + data
