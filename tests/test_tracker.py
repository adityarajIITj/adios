#!/usr/bin/env python3
"""
Test Suite: PC Speaker Music Tracker & Audio Synthesizer
Verifies:
1. 12-TET Note to frequency calculation (A4 = 440 Hz, C4 = 261 Hz)
2. Score string parser
3. MMIO audio dispatch (0x10000050)
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from vm.vm import VM
from audio import AudioTracker, note_to_freq

def test_tracker_suite():
    print("[Test Audio Tracker] Testing PC Speaker Music Tracker...")

    # 1. Test Note to Frequency
    print("  -> Testing note frequency calculations...")
    assert note_to_freq("A4") == 440, f"A4 expected 440, got {note_to_freq('A4')}"
    assert note_to_freq("A3") == 220, f"A3 expected 220, got {note_to_freq('A3')}"
    assert note_to_freq("A5") == 880, f"A5 expected 880, got {note_to_freq('A5')}"
    assert note_to_freq("C4") in (261, 262), f"C4 expected ~261, got {note_to_freq('C4')}"
    assert note_to_freq("REST") == 0, "REST note must be 0 Hz"
    print("  -> [PASS] Note frequencies verified.")

    # 2. Test MMIO Audio Dispatch
    print("  -> Testing MMIO dispatch to audio registers (0x10000050)...")
    vm = VM()
    tracker = AudioTracker(vm)

    # Play tone 440 Hz for 250ms
    tracker.play_tone(440, 250)
    assert vm.read32(0x10000050) == 440, "AUDIO_FREQ register not updated"
    assert vm.read32(0x10000054) == 250, "AUDIO_DURATION register not updated"

    # Play note C4
    tracker.play_note("C4", "H")
    assert vm.read32(0x10000050) == note_to_freq("C4")
    assert vm.read32(0x10000054) == 500
    print("  -> [PASS] MMIO Audio synthesizer dispatch verified.")

    # 3. Test Score Parsing
    print("  -> Testing score string parsing...")
    count = tracker.parse_and_play("E4:Q G4:Q A4:H")
    assert count == 3, f"Expected 3 notes parsed, got {count}"
    print("  -> [PASS] Score string parser verified.")

    print("\n[Test Audio Tracker] ALL AUDIO SYNTHESIZER TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_tracker_suite()
