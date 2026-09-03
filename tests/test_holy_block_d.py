#!/usr/bin/env python3
"""
Test Suite: Block D Sovereign Interactive Environment & Cyber Shell
Verifies:
1. HardwareRandomLCG & Hardware Entropy Harvesting (CSR_MCYCLE & Timer)
2. Cosmic Entropy Oracle & Scientific/Philosophical Axiom Generation
3. Algorithmic 4-Part Counterpoint Baroque Synthesizer & MMIO Tone Playback
4. 3D Cyber Citadel & Quantum Core Perspective Wireframe Rasterization
5. Sovereign Cyber Shell Command Interpreter Dispatching
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from holy.oracle import HardwareRandomLCG, CosmicOracle, VOCABULARY
from holy.hymn import BaroqueSynthesizer
from holy.sanctuary3d import CyberCitadel3D
from holy.holy_shell import SovereignCyberShell
from vm.vm import VM

def test_holy_block_d_suite():
    print("[Test Block D] Initializing Sovereign Cyber Interactive Suite Verification...")

    # 1. Test Hardware Entropy & LCG
    print("  -> Testing Hardware Entropy Harvesting & LCG...")
    vm = VM()
    vm.mcycle = 12345678
    vm.timer_time = 87654321
    rng = HardwareRandomLCG(seed=42)
    rng.harvest_hardware_entropy(vm)
    u1 = rng.next_u32()
    u2 = rng.next_u32()
    assert u1 != u2, "LCG consecutive outputs must differ"
    val = rng.rand_range(10, 50)
    assert 10 <= val <= 50, f"Random range out of bounds: {val}"
    print("  -> [PASS] Hardware entropy harvesting and LCG verified.")

    # 2. Test Cosmic Oracle
    print("  -> Testing Cosmic Oracle & Scientific/Philosophical Axiom Generator...")
    oracle = CosmicOracle(vm)
    oracle_words = oracle.consult_oracle(12)
    words = oracle_words.split()
    assert len(words) == 12, f"Expected 12 words, got {len(words)}"
    for w in words:
        assert w in VOCABULARY, f"Word '{w}' not in vocabulary bank"
    
    axiom = oracle.generate_aphorism()
    assert len(axiom) > 20, "Philosophical axiom too short"
    
    doldoc = oracle.consult_doldoc("TEST CONSULTATION")
    assert "$CL$" in doldoc and "$FG," in doldoc, "Invalid DolDoc formatting"
    print("  -> [PASS] Cosmic Oracle verified.")

    # 3. Test Algorithmic Baroque Synthesizer
    print("  -> Testing Algorithmic 4-Part Counterpoint Baroque Synthesizer...")
    synth = BaroqueSynthesizer(seed=1337)
    piece = synth.compose_piece("Dorian", 8)
    assert len(piece["soprano"]) == 8, "Expected 8 soprano notes"
    assert len(piece["alto"]) == 8, "Expected 8 alto notes"
    assert len(piece["tenor"]) == 8, "Expected 8 tenor notes"
    assert len(piece["bass"]) == 8, "Expected 8 bass notes"
    assert len(piece["terms"]) == 8, "Expected 8 thematic terms"
    
    # Test MMIO speaker playback
    synth.play_to_speaker_mmio(vm, piece, 100)
    assert vm.audio_freq > 0, "Audio frequency register was not set"
    assert vm.audio_duration == 100, "Audio duration register was not set"
    print("  -> [PASS] Baroque counterpoint and MMIO playback verified.")

    # 4. Test 3D Cyber Citadel & Quantum Core
    print("  -> Testing 3D Cyber Citadel Wireframe Rasterization...")
    citadel = CyberCitadel3D(vm)
    assert len(citadel.lines) > 50, f"Insufficient geometry lines: {len(citadel.lines)}"
    lines_drawn = citadel.render_frame()
    assert lines_drawn > 20, f"Expected >20 lines drawn, got {lines_drawn}"
    
    # Verify non-blank framebuffer
    fb_bytes = bytes(vm.fb[:4096])
    assert any(b != 0 for b in fb_bytes), "Framebuffer was completely blank after 3D render"
    print(f"  -> [PASS] Cyber Citadel 3D wireframe rasterized ({lines_drawn} lines projected).")

    # 5. Test Sovereign Cyber Shell Command Interpreter
    print("  -> Testing Sovereign Cyber Shell Interpreter...")
    shell = SovereignCyberShell(vm)
    
    help_out = shell.execute_line("help")
    assert "SOVEREIGN CYBER SHELL COMMANDS" in help_out, "Help output invalid"
    
    oracle_out = shell.execute_line("oracle 8")
    assert "[Cosmic Oracle]" in oracle_out, "Oracle shell command failed"
    
    axiom_out = shell.execute_line("axiom")
    assert "[Philosophical Axiom]" in axiom_out, "Axiom shell command failed"
    
    synth_out = shell.execute_line("synth Lydian")
    assert "Mode: Lydian" in synth_out, "Synth shell command failed"
    
    citadel_out = shell.execute_line("citadel")
    assert "Rendered" in citadel_out, "Citadel shell command failed"
    
    palloc_out = shell.execute_line("palloc")
    assert "16,384 pages" in palloc_out, "Palloc shell command failed"
    
    tasks_out = shell.execute_line("tasks")
    assert "CyberShell" in tasks_out, "Tasks shell command failed"
    
    matrix_out = shell.execute_line("matrix")
    assert "CYBERSPACE" in matrix_out, "Matrix shell command failed"
    
    print("  -> [PASS] Sovereign Cyber Shell command execution verified.")

    print("\n[Test Block D] ALL BLOCK D SOVEREIGN CYBER SUITE TESTS PASSED (100%)!")
    return True

if __name__ == "__main__":
    test_holy_block_d_suite()
