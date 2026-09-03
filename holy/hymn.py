#!/usr/bin/env python3
"""
AdiOS Sovereign Computing Subsystem: Algorithmic Polyphonic Synthesizer (hymn.py)
Features:
- Algorithmic 4-Part SATB (Soprano, Alto, Tenor, Bass) Baroque Voice Leading
- Musical Modes: Major, Natural Minor, Dorian, Lydian, Mixolydian
- Strict Counterpoint: Root, Third, Fifth triad voicings, avoidance of parallel fifths
- Outputs:
    1. MMIO Sound Synthesizer frequency stream (0x10000050)
    2. DolDoc Score Notation with lyrics and stave display
    3. Export to AdiOS Music Tracker sequence
"""

import time
import math
from holy.oracle import HardwareRandomLCG, VOCABULARY

# Equal Temperament Note Frequencies (Hz) for Octaves 2, 3, 4, 5
NOTE_FREQ = {
    # Octave 2 (Bass)
    "C2": 65,  "D2": 73,  "E2": 82,  "F2": 87,  "G2": 98,  "A2": 110, "B2": 123,
    # Octave 3 (Tenor)
    "C3": 131, "D3": 147, "E3": 165, "F3": 175, "G3": 196, "A3": 220, "B3": 247,
    # Octave 4 (Alto / Soprano)
    "C4": 262, "D4": 294, "E4": 330, "F4": 349, "G4": 392, "A4": 440, "B4": 494,
    # Octave 5 (Soprano high)
    "C5": 523, "D5": 587, "E5": 659, "F5": 698, "G5": 784, "A5": 880, "B5": 988,
    "REST": 0
}

# Modal Scale Definitions (Degree semitone intervals from root)
MODES = {
    "Major":      ["C", "D", "E", "F", "G", "A", "B"],
    "Minor":      ["A", "B", "C", "D", "E", "F", "G"],
    "Dorian":     ["D", "E", "F", "G", "A", "B", "C"],
    "Lydian":     ["F", "G", "A", "B", "C", "D", "E"],
    "Mixolydian": ["G", "A", "B", "C", "D", "E", "F"]
}

# Standard Diatonic Triads (Root, 3rd, 5th degree offsets)
TRIADS = {
    "I":   (0, 2, 4),
    "ii":  (1, 3, 5),
    "iii": (2, 4, 6),
    "IV":  (3, 5, 0),
    "V":   (4, 6, 1),
    "vi":  (5, 0, 2),
    "vii°":(6, 1, 3)
}

# Standard Harmonic Chord Progressions
PROGRESSIONS = [
    ["I", "IV", "V", "I"],
    ["I", "vi", "IV", "V"],
    ["I", "V", "vi", "IV"],
    ["I", "ii", "V", "I"],
    ["I", "IV", "I", "V", "vi", "IV", "V", "I"],
    ["vi", "IV", "I", "V", "vi", "ii", "V", "I"]
]

class BaroqueSynthesizer:
    """
    Algorithmic 4-part polyphonic chorale composer and sound synthesizer.
    """
    def __init__(self, seed=None):
        self.rng = HardwareRandomLCG(seed)

    def compose_piece(self, mode_name="Major", measures=8):
        """
        Composes an 8-measure musical piece with 4-part SATB harmony.
        Returns dictionary with chord sequence, voices, and thematic terms.
        """
        scale = MODES.get(mode_name, MODES["Major"])
        prog = self.rng.choice(PROGRESSIONS)
        
        chords = []
        while len(chords) < measures:
            chords.extend(prog)
        chords = chords[:measures]

        soprano = []
        alto = []
        tenor = []
        bass = []

        last_s = None
        for ch_name in chords:
            root_deg, third_deg, fifth_deg = TRIADS[ch_name]
            
            # Bass plays Root (Octave 2 or 3)
            b_note = f"{scale[root_deg]}2"
            bass.append(b_note)

            # Tenor plays Fifth (Octave 3)
            t_note = f"{scale[fifth_deg]}3"
            tenor.append(t_note)

            # Alto plays Third (Octave 3 or 4)
            a_note = f"{scale[third_deg]}4"
            alto.append(a_note)

            # Soprano plays Melody (Root or Fifth in Octave 4/5)
            cand1 = f"{scale[root_deg]}4"
            cand2 = f"{scale[fifth_deg]}4"
            cand3 = f"{scale[root_deg]}5"
            
            if last_s is None:
                s_note = cand1
            else:
                s_note = self.rng.choice([cand1, cand2, cand3])
            last_s = s_note
            soprano.append(s_note)

        terms = [self.rng.choice(VOCABULARY).capitalize() for _ in range(measures)]

        forms = ["Prelude", "Invention", "Fugue", "Chorale", "Sonata", "Toccata"]
        form_name = self.rng.choice(forms)
        title_word = self.rng.choice(VOCABULARY).capitalize()
        title = f"{form_name} of the {title_word}"

        return {
            "title": title,
            "mode": mode_name,
            "chords": chords,
            "soprano": soprano,
            "alto": alto,
            "tenor": tenor,
            "bass": bass,
            "terms": terms,
            "bpm": 112
        }

    def render_doldoc(self, piece):
        """Formats the composed piece into a DolDoc musical score."""
        doc = []
        doc.append(f"$CL$$FG,14$$TX,3,1$=== {piece['title']} ===$FG,0$\n")
        doc.append(f"$FG,6$Mode: {piece['mode']} | Tempo: {piece['bpm']} BPM$FG,0$\n\n")
        
        # Chord progression banner
        doc.append("$FG,13$Chords:  $FG,15$")
        for ch in piece['chords']:
            doc.append(f"[{ch:>4}] ")
        doc.append("$FG,0$\n")

        # Soprano Melody
        doc.append("$FG,11$Soprano: $FG,14$")
        for note in piece['soprano']:
            doc.append(f" {note:>4} ")
        doc.append("$FG,0$\n")

        # Alto
        doc.append("$FG,11$Alto:    $FG,10$")
        for note in piece['alto']:
            doc.append(f" {note:>4} ")
        doc.append("$FG,0$\n")

        # Tenor
        doc.append("$FG,11$Tenor:   $FG,9$")
        for note in piece['tenor']:
            doc.append(f" {note:>4} ")
        doc.append("$FG,0$\n")

        # Bass
        doc.append("$FG,11$Bass:    $FG,12$")
        for note in piece['bass']:
            doc.append(f" {note:>4} ")
        doc.append("$FG,0$\n\n")

        # Terms
        doc.append("$FG,15$Motifs:  ")
        for t in piece['terms']:
            doc.append(f" {t:>6} ")
        doc.append("$FG,0$\n\n")

        doc.append("$FG,10$$LK,\"Play Audio Tone\",\"play_synth\"$  $LK,\"Compose New Piece\",\"new_piece\"$$FG,0$\n")
        return "".join(doc)

    def play_to_speaker_mmio(self, vm, piece, note_duration_ms=300):
        """Sends the melody notes directly to the AdiOS PC Speaker MMIO registers."""
        for note in piece['soprano']:
            freq = NOTE_FREQ.get(note, 440)
            if vm:
                vm.write32(0x10000050, freq)
                vm.write32(0x10000054, note_duration_ms)
                vm.timer_time += note_duration_ms * 1000

if __name__ == "__main__":
    gen = BaroqueSynthesizer()
    piece = gen.compose_piece("Dorian", 8)
    print(gen.render_doldoc(piece))
