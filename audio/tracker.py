#!/usr/bin/env python3
"""
AdiOS PC Speaker Music Tracker & Hymn Player
Inspired by Terry A. Davis's GodSong and PC Speaker sound synthesizer in TempleOS.
Features:
- Note to frequency conversion (12-TET equal temperament)
- Score parser with note names (C4, D#4, Eb4, G5) and durations (W, H, Q, E, S)
- Direct MMIO PC speaker synthesis at 0x10000050
- Built-in hymns: 'Hymn of AdiOS', 'Ode to Light', 'Victory Fanfare'
"""

import math
import time

# Base note semitone offsets relative to A4 (440 Hz = MIDI 69)
NOTE_OFFSETS = {
    "C": -9, "C#": -8, "DB": -8,
    "D": -7, "D#": -6, "EB": -6,
    "E": -5,
    "F": -4, "F#": -3, "GB": -3,
    "G": -2, "G#": -1, "AB": -1,
    "A":  0, "A#":  1, "BB":  1,
    "B":  2
}

# Standard Durations in milliseconds (at 120 BPM)
DURATION_MS = {
    "W": 1000, # Whole note
    "H":  500, # Half note
    "Q":  250, # Quarter note
    "E":  125, # Eighth note
    "S":   62  # Sixteenth note
}

def note_to_freq(note_str):
    """Converts a note string like 'A4', 'C#5', 'REST' to frequency in Hz."""
    s = note_str.strip().upper()
    if s in ("REST", "R", "-"):
        return 0

    octave = int(s[-1])
    note_name = s[:-1]
    semitone = NOTE_OFFSETS.get(note_name, 0) + (octave - 4) * 12
    # f = 440 * 2^(semitone / 12)
    freq = int(440.0 * math.pow(2.0, semitone / 12.0))
    return freq

# ------------------------------------------------------------------------------
# Built-in Soundtracks & Hymns
# ------------------------------------------------------------------------------

HYMN_OF_ADIOS = [
    ("E4", "Q"), ("G4", "Q"), ("A4", "Q"), ("B4", "Q"),
    ("C5", "H"), ("B4", "Q"), ("A4", "Q"),
    ("G4", "H"), ("E4", "H"),
    ("D4", "Q"), ("E4", "Q"), ("G4", "Q"), ("A4", "Q"),
    ("G4", "W")
]

VICTORY_FANFARE = [
    ("C4", "E"), ("E4", "E"), ("G4", "E"), ("C5", "Q"),
    ("G4", "E"), ("C5", "H")
]

TERRYS_REVERIE = [
    ("C4", "Q"), ("E4", "Q"), ("G4", "Q"), ("B4", "Q"),
    ("C5", "H"), ("G4", "H"),
    ("A4", "Q"), ("F4", "Q"), ("D4", "Q"), ("G4", "Q"),
    ("C4", "W")
]

class AudioTracker:
    def __init__(self, vm=None):
        self.vm = vm

    def play_tone(self, freq, duration_ms):
        """Sends audio tone to the PC Speaker MMIO controller (0x10000050)."""
        if not self.vm: return
        self.vm.write32(0x10000050, freq)
        self.vm.write32(0x10000054, duration_ms)

    def play_note(self, note_str, dur_str="Q"):
        freq = note_to_freq(note_str)
        dur = DURATION_MS.get(dur_str.upper(), 250)
        self.play_tone(freq, dur)

    def play_track(self, track, sleep_between=True):
        """Plays a sequence of (note, duration) pairs."""
        for note, dur in track:
            freq = note_to_freq(note)
            duration_ms = DURATION_MS.get(dur.upper(), 250)
            self.play_tone(freq, duration_ms)
            if sleep_between:
                time.sleep(duration_ms / 1000.0)

    def parse_and_play(self, score_str):
        """Parses score string like 'C4:Q D4:Q E4:H' and plays it."""
        tokens = score_str.strip().split()
        track = []
        for t in tokens:
            if ":" in t:
                n, d = t.split(":", 1)
                track.append((n, d))
            else:
                track.append((t, "Q"))
        self.play_track(track)
        return len(track)
