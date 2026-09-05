#!/usr/bin/env python3
"""
AdiOS Premier Multi-Backend Sound Server (audio/sound_server.py)
Sovereign Workstation v2.0 Stable.
Provides multi-tier audio architecture:
1. Premier Backend: pygame.mixer (SDL2 hardware mixer with simultaneous multi-channel audio)
2. Hardware Backend: Windows MCI (winmm.dll) for direct OS hardware control
3. Fallback Backend: Standard winsound audio pipe
4. Instant system-wide mute and master volume attenuation

STRICT ZERO EMOJI POLICY ENFORCED.
"""

import math
import struct
import threading
import time
import os
import ctypes
from typing import Optional, List, Dict, Any


class SoundServer:
    _instance: Optional["SoundServer"] = None

    @classmethod
    def get_instance(cls) -> "SoundServer":
        if cls._instance is None:
            cls._instance = SoundServer()
        return cls._instance

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.master_volume: float = 0.80  # 80% default
        self.is_muted: bool = False
        self.vu_level: float = 0.0
        self.lock = threading.RLock()
        self.active_stream_path: Optional[str] = None
        self._mci_alias = "adios_stream"
        self._mci_active = False

        # Windows winmm.dll for MCI hardware control
        try:
            self._winmm = ctypes.windll.winmm
        except Exception:
            self._winmm = None

        # Premier Backend: pygame.mixer
        self._has_pygame = False
        self._ui_channel = None
        self._synth_channel = None
        self._ui_sounds: Dict[str, Any] = {}

        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=sample_rate, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(8)
            self._ui_channel = pygame.mixer.Channel(0)
            self._synth_channel = pygame.mixer.Channel(1)
            self._has_pygame = True
            self._init_ui_sounds()
        except Exception:
            self._has_pygame = False

    def _init_ui_sounds(self):
        """Pre-synthesizes clean, low-latency UI sound effects into memory."""
        if not self._has_pygame:
            return
        try:
            import pygame
            two_pi = 2.0 * math.pi

            def synthesize_effect(freqs: List[float], duration: float = 0.08) -> Any:
                samples = int(self.sample_rate * duration)
                pcm = bytearray(samples * 4)  # 16-bit stereo = 4 bytes per sample
                f_step = duration / max(1, len(freqs))
                for i in range(samples):
                    t = i / float(self.sample_rate)
                    f_idx = min(len(freqs) - 1, int(t / f_step))
                    f = freqs[f_idx]
                    step_t = t - (f_idx * f_step)
                    env = math.exp(-step_t * 24.0)
                    v = int(math.sin(two_pi * f * t) * env * 18000)
                    struct.pack_into("<hh", pcm, i * 4, v, v)
                return pygame.mixer.Sound(buffer=bytes(pcm))

            self._ui_sounds = {
                "click": synthesize_effect([1200.0], 0.03),
                "notify": synthesize_effect([880.0, 1320.0], 0.12),
                "snap": synthesize_effect([640.0], 0.04),
                "launch": synthesize_effect([523.25, 659.25, 783.99], 0.16),
            }
        except Exception:
            self._ui_sounds = {}

    def _mci_send(self, command: str) -> int:
        """Sends a command string to Windows Media Control Interface (MCI)."""
        if not self._winmm:
            return -1
        try:
            buf = ctypes.create_unicode_buffer(256)
            return self._winmm.mciSendStringW(command, buf, 255, None)
        except Exception:
            return -1

    def get_volume_pct(self) -> int:
        return int(self.master_volume * 100)

    def set_volume_pct(self, pct: int):
        with self.lock:
            self.master_volume = max(0.0, min(1.0, pct / 100.0))
            eff = self.get_effective_volume()

            if self._has_pygame:
                try:
                    import pygame
                    pygame.mixer.music.set_volume(eff)
                    if self._ui_channel:
                        self._ui_channel.set_volume(eff)
                    if self._synth_channel:
                        self._synth_channel.set_volume(eff)
                except Exception:
                    pass

            if self._mci_active:
                vol_1000 = int(eff * 1000)
                self._mci_send(f"setaudio {self._mci_alias} volume to {vol_1000}")

            if self.master_volume <= 0.01:
                self.stop_all()

    def toggle_mute(self) -> bool:
        with self.lock:
            self.is_muted = not self.is_muted
            if self.is_muted:
                self.stop_all()
            else:
                self.set_volume_pct(int(self.master_volume * 100))
            return self.is_muted

    def set_muted(self, muted: bool):
        with self.lock:
            self.is_muted = bool(muted)
            if self.is_muted:
                self.stop_all()
            else:
                self.set_volume_pct(int(self.master_volume * 100))

    def get_effective_volume(self) -> float:
        if self.is_muted:
            return 0.0
        return self.master_volume

    def get_vu_meter(self) -> float:
        """Returns normalized 0.0-1.0 current audio output level."""
        if self.is_muted or not self.active_stream_path:
            return 0.0
        self.vu_level = max(0.0, self.vu_level * 0.90)
        return self.vu_level

    def play_ui_sound(self, sound_type: str = "click"):
        """Plays non-blocking UI sound effect via pygame or winsound fallback."""
        eff_vol = self.get_effective_volume()
        if eff_vol <= 0.01:
            return

        # 1. Premier pygame.mixer playback (zero latency, simultaneous channels)
        if self._has_pygame and self._ui_channel and sound_type in self._ui_sounds:
            try:
                self._ui_channel.set_volume(eff_vol)
                self._ui_channel.play(self._ui_sounds[sound_type])
                self.vu_level = 0.4 * eff_vol
                return
            except Exception:
                pass

        # 2. Fallback winsound beep in background thread
        def worker():
            try:
                import winsound
                if sound_type == "click":
                    self.vu_level = 0.3 * eff_vol
                    winsound.Beep(1200, 15)
                elif sound_type == "notify":
                    self.vu_level = 0.6 * eff_vol
                    winsound.Beep(880, 35)
                    winsound.Beep(1320, 50)
                elif sound_type == "snap":
                    self.vu_level = 0.4 * eff_vol
                    winsound.Beep(640, 20)
                elif sound_type == "launch":
                    self.vu_level = 0.7 * eff_vol
                    winsound.Beep(523, 25)
                    winsound.Beep(659, 25)
                    winsound.Beep(784, 40)
            except Exception:
                pass

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def stream_audio_file(self, file_path: str, loop: bool = True):
        """Streams an audio file (WAV, MP3, M4A, OGG) with volume control & instant stop."""
        if not os.path.exists(file_path):
            return
        if self.is_muted or self.master_volume <= 0.01:
            return

        # Stop previous playback first
        self.stop_all()

        with self.lock:
            self.active_stream_path = file_path
            eff_vol = self.get_effective_volume()

            # 1. Premier pygame.mixer.music streaming (supports WAV, MP3, OGG, FLAC)
            if self._has_pygame:
                try:
                    import pygame
                    pygame.mixer.music.load(file_path)
                    pygame.mixer.music.set_volume(eff_vol)
                    pygame.mixer.music.play(-1 if loop else 0)
                    self.vu_level = 0.75 * eff_vol
                    return
                except Exception:
                    pass

            # 2. Windows MCI hardware playback (supports WAV, MP3, M4A)
            if self._winmm:
                norm_path = os.path.abspath(file_path)
                res = self._mci_send(f'open "{norm_path}" alias {self._mci_alias}')
                if res == 0:
                    vol_1000 = int(eff_vol * 1000)
                    self._mci_send(f"setaudio {self._mci_alias} volume to {vol_1000}")
                    play_cmd = f"play {self._mci_alias} repeat" if loop else f"play {self._mci_alias}"
                    self._mci_send(play_cmd)
                    self._mci_active = True
                    self.vu_level = 0.75 * eff_vol
                    return

            # 3. Fallback to winsound (for WAV files)
            if file_path.lower().endswith(".wav"):
                try:
                    import winsound
                    self.vu_level = 0.75 * eff_vol
                    flags = winsound.SND_FILENAME | winsound.SND_ASYNC
                    if loop:
                        flags |= winsound.SND_LOOP
                    winsound.PlaySound(file_path, flags)
                except Exception:
                    pass

    def play_pcm_sound(self, pcm_data: bytes, loop: bool = True):
        """Plays raw 16-bit 44.1 kHz PCM audio data via pygame or temporary WAV."""
        if not pcm_data:
            return
        if self.is_muted or self.master_volume <= 0.01:
            return

        self.stop_all()

        with self.lock:
            eff_vol = self.get_effective_volume()

            # 1. Premier pygame raw PCM Sound playback
            if self._has_pygame and self._synth_channel:
                try:
                    import pygame
                    snd = pygame.mixer.Sound(buffer=pcm_data)
                    self._synth_channel.set_volume(eff_vol)
                    self._synth_channel.play(snd, loops=-1 if loop else 0)
                    self.active_stream_path = "procedural_synth"
                    self.vu_level = 0.75 * eff_vol
                    return
                except Exception:
                    pass

            # 2. Fallback via temporary WAV file
            try:
                import tempfile
                wav = self._pcm_to_wav(pcm_data, sample_rate=self.sample_rate, volume_pct=int(eff_vol * 100))
                tmp = tempfile.NamedTemporaryFile(prefix="adios_synth_", suffix=".wav", delete=False)
                tmp.write(wav)
                tmp.close()
                self._fallback_wav_path = tmp.name
                self.stream_audio_file(self._fallback_wav_path, loop=loop)
            except Exception:
                pass

    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int = 44100, volume_pct: int = 100) -> bytes:
        """Formats 16-bit mono PCM into standard RIFF WAVE bytes with volume attenuation."""
        vol_factor = max(0.0, min(1.0, volume_pct / 100.0))
        scaled_pcm = bytearray(len(pcm_data))
        for i in range(0, len(pcm_data), 2):
            sample = struct.unpack_from("<h", pcm_data, i)[0]
            scaled = int(sample * vol_factor)
            struct.pack_into("<h", scaled_pcm, i, max(-32768, min(32767, scaled)))
        data_bytes = bytes(scaled_pcm)
        data_size = len(data_bytes)
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + data_size,
            b"WAVE",
            b"fmt ",
            16,
            1,
            1,
            sample_rate,
            sample_rate * 2,
            2,
            16,
            b"data",
            data_size
        )
        return header + data_bytes

    def stop_all(self):
        """Guaranteed instant silence across all audio backends."""
        # 1. Stop pygame.mixer
        if self._has_pygame:
            try:
                import pygame
                pygame.mixer.music.stop()
                if self._synth_channel:
                    self._synth_channel.stop()
            except Exception:
                pass

        # 2. Stop and close MCI alias
        if self._winmm:
            try:
                self._mci_send(f"stop {self._mci_alias}")
                self._mci_send(f"close {self._mci_alias}")
            except Exception:
                pass
        self._mci_active = False

        # 3. Stop winsound
        try:
            import winsound
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass

        # Clean temporary fallback file
        fb_path = getattr(self, "_fallback_wav_path", None)
        if fb_path and os.path.exists(fb_path):
            try:
                os.remove(fb_path)
            except Exception:
                pass
            self._fallback_wav_path = None

        self.active_stream_path = None
        self.vu_level = 0.0

    def stop_audio(self):
        """Alias for stop_all."""
        self.stop_all()
