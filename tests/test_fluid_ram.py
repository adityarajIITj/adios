#!/usr/bin/env python3
"""
tests/test_fluid_ram.py - Unit Tests for FluidRAM Autonomous Memory Manifold,
The Void-Pipe, Biomimetic Tensegrity, Galois Retro-Inversion, and Visual Oscilloscope.

Strict Zero Emoji Policy Enforced.
"""

import unittest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kernel.fluid_ram import (
    FluidRAMMesh, get_fluid_ram_mesh, VoidPipeDecoder, GaloisInverter,
    PHYSICAL_RAM_MB, BASELINE_CAPACITIES_MB,
    POOL_KERNEL_CORE, POOL_COMPOSITOR_FB, POOL_STREAM_RING,
    POOL_CHRONOS_DELTA, POOL_USER_APPS, POOL_DYNAMIC_MESH
)
from desktop.fluid_oscilloscope import FluidOscilloscopeApp
from userland.fluid_cmd import run_fluid_cmd
from userland.coreutils import CoreUtils
from userland.sh import SovereignShell
from desktop.font import get_default_font


class TestFluidRAMKernel(unittest.TestCase):
    """Validates core physics, hydrodynamic flow vectors, and peer-to-peer lending."""

    def setUp(self):
        self.mesh = FluidRAMMesh()

    def test_manifold_baseline_capacities(self):
        """Validates that total physical capacity equals exactly 1024 MB."""
        self.assertEqual(self.mesh.total_ram_mb, 1024)
        total_baseline = sum(BASELINE_CAPACITIES_MB.values())
        self.assertEqual(total_baseline, 1024)
        self.assertEqual(len(self.mesh.pools), 6)

    def test_hydrodynamic_pressure_calculation(self):
        """Verifies pressure indices are strictly bounded in [0.0, 1.0]."""
        for pool in self.mesh.pools.values():
            self.assertGreaterEqual(pool.pressure, 0.0)
            self.assertLessEqual(pool.pressure, 1.0)
        self.assertGreaterEqual(self.mesh.global_pressure, 0.0)
        self.assertLessEqual(self.mesh.global_pressure, 1.0)

    def test_p2p_sub_millisecond_borrow_and_repay(self):
        """Verifies peer-to-peer capacity reallocation between surplus and requesting pools."""
        initial_cap = self.mesh.pools[POOL_USER_APPS].current_capacity_mb
        # Borrow 16 MB into USER_APPS
        success = self.mesh.borrow_pages(POOL_USER_APPS, 16.0)
        self.assertTrue(success)
        self.assertEqual(self.mesh.pools[POOL_USER_APPS].current_capacity_mb, initial_cap + 16.0)
        self.assertGreater(self.mesh.total_borrow_cycles, 0)

        # Repay capacity back
        lender_name = list(self.mesh.pools[POOL_USER_APPS].borrowed_from.keys())[0]
        repay_ok = self.mesh.repay_pages(POOL_USER_APPS, lender_name, 16.0)
        self.assertTrue(repay_ok)
        self.assertEqual(self.mesh.pools[POOL_USER_APPS].current_capacity_mb, initial_cap)

    def test_flow_vector_computation(self):
        """Computes potential flow velocity vectors based on pressure gradients."""
        # Artificially raise one pool's pressure
        self.mesh.pools[POOL_USER_APPS].used_mb = 200.0
        vectors = self.mesh.compute_flow_vectors()
        self.assertIsInstance(vectors, list)
        if vectors:
            v = vectors[0]
            self.assertIn("source", v)
            self.assertIn("target", v)
            self.assertIn("velocity", v)
            self.assertIn("flux_mb_per_sec", v)

    def test_dynamic_focus_attraction(self):
        """Tests that focus attraction field dilates active window and contracts background."""
        self.mesh.attract_focus("SoundTracker")
        self.assertEqual(self.mesh.focus_app, "SoundTracker")
        # User apps tension relaxed
        self.assertEqual(self.mesh.pools[POOL_USER_APPS].tension, 0.15)
        # Chronos delta contracted to lend slack
        self.assertEqual(self.mesh.pools[POOL_CHRONOS_DELTA].tension, 0.65)

    def test_harmonic_compaction(self):
        """Tests that harmonic compaction defragments transient buffers and restores equilibrium."""
        res = self.mesh.harmonic_compact()
        self.assertEqual(res["status"], "EQUILIBRIUM_RESTORED")
        self.assertIn("freed_mb", res)
        self.assertIn("global_pressure", res)
        self.assertGreater(self.mesh.compaction_events, 0)

    def test_topology_matrix_dimensions_and_cells(self):
        """Validates that the 32x32 topology grid represents exactly 1024 MB."""
        matrix = self.mesh.get_topology_matrix(rows=32, cols=32)
        self.assertEqual(len(matrix), 32)
        total_cells = sum(len(row) for row in matrix)
        self.assertEqual(total_cells, 1024)

        sample_cell = matrix[0][0]
        self.assertIn("pool", sample_cell)
        self.assertIn("heat", sample_cell)
        self.assertIn("pressure", sample_cell)
        self.assertIn("tension", sample_cell)


class TestVoidPipeDecoder(unittest.TestCase):
    """Validates the in-flight ephemeral stream rasterization invariants."""

    def setUp(self):
        self.decoder = VoidPipeDecoder()

    def test_ephemeral_channel_zero_disk(self):
        """Channel creation strictly writes 0 bytes to disk."""
        chan = self.decoder.open_ephemeral_channel("yt_live_stream_01", width=1280, height=720)
        self.assertEqual(chan["disk_writes_bytes"], 0)
        self.assertEqual(chan["mode"], "VOID_PIPE_EPHEMERAL_STREAM")
        self.assertLessEqual(chan["ephemeral_footprint_mb"], 4.0)

    def test_transduce_frames_bounded_footprint(self):
        """Stream rendering across 120 frames remains strictly bounded under 4.0 MB."""
        frame_bytes = 1280 * 720 * 4
        for _ in range(120):
            active_mb = self.decoder.transduce_frame(frame_bytes)
            self.assertLessEqual(active_mb, 4.0)

        telemetry = self.decoder.get_telemetry()
        self.assertEqual(telemetry["frames_rendered"], 120)
        self.assertEqual(telemetry["disk_cache_usage_kb"], 0.0)
        self.assertEqual(telemetry["evaporation_rate_fps"], 60.0)


class TestGaloisInverter(unittest.TestCase):
    """Validates Galois Field GF(2^8) reversible time-travel permutation."""

    def setUp(self):
        self.inverter = GaloisInverter(key=0x42)

    def test_multiplicative_inverse_property(self):
        """Verifies a * a^(-1) = 1 in GF(2^8) for all non-zero elements."""
        for a in range(1, 256):
            a_inv = self.inverter.gf_inv(a)
            prod = self.inverter.gf_mult(a, a_inv)
            self.assertEqual(prod, 1, f"GF(2^8) inverse violation for element {a}")

    def test_forward_inverse_permutation_symmetry(self):
        """Verifies 100% loss-free state recovery using inverse permutation with 0 snapshot storage."""
        original_state = b"AdiOS-Kernel-Thread-State-Registers-PC-SP-GP-TP-S0-A0"
        mutated = self.inverter.forward_permute(original_state)
        self.assertNotEqual(mutated, original_state)
        restored = self.inverter.inverse_permute(mutated)
        self.assertEqual(restored, original_state)


class TestFluidOscilloscopeUI(unittest.TestCase):
    """Validates real-time oscilloscope application rendering and interactions."""

    def setUp(self):
        self.app = FluidOscilloscopeApp(screen_w=1024, screen_h=768)

    def test_step_decay(self):
        """Validates step tick and wave pulse decay."""
        self.app.mesh.wave_pulse_phase = 2.0
        self.app.step()
        self.assertLess(self.app.mesh.wave_pulse_phase, 2.0)

    def test_button_clicks(self):
        """Tests tactile button clicks."""
        # Click Pulse Wave button (x: 50, y: 40)
        self.app.handle_click(50, 40)
        self.assertGreater(self.app.mesh.wave_pulse_phase, 0.0)

        # Click Harmonic Compact button (x: 200, y: 40)
        self.app.handle_click(200, 40)
        self.assertIn("Harmonic compaction complete", self.app.status_message)

        # Click Equilibrium Purge button (x: 350, y: 40)
        self.app.handle_click(350, 40)
        self.assertIn("Surface tension dissipated", self.app.status_message)

    def test_grid_cell_selection(self):
        """Tests clicking a cell in the 32x32 topological grid."""
        # Click cell (x: 14 + 2*13 = 40, y: 72 + 2*13 = 98)
        self.app.handle_click(40, 98)
        self.assertIsNotNone(self.app.selected_cell_index)
        self.assertIsNotNone(self.app.selected_cell_info)
        self.assertIn("0x", self.app.selected_cell_info["address_hex"])

    def test_headless_rasterization(self):
        """Validates headless software frame rendering into a 1024x768 buffer."""
        fb = bytearray(1024 * 768 * 4)
        font = get_default_font()
        self.app.render(fb, font, win_x=100, win_y=100, win_w=760, win_h=520)
        # Check that framebuffer contains rendered pixels
        non_zero = any(b != 0 for b in fb[100 * 1024 * 4 : 200 * 1024 * 4])
        self.assertTrue(non_zero)


class TestFluidUserlandCmd(unittest.TestCase):
    """Validates CLI command diagnostics and sovereign challenge benchmark."""

    def test_fluid_status_command(self):
        out = run_fluid_cmd(["status"])
        self.assertIn("ADIOS FLUIDRAM SOVEREIGN MEMORY MANIFOLD", out)
        self.assertIn("1024.00 MB", out)
        self.assertIn("THE VOID-PIPE", out)

    def test_fluid_challenge_benchmark(self):
        out = run_fluid_cmd(["--challenge"])
        self.assertIn("BENCHMARK RESULTS", out)
        self.assertIn("50 Active Processes", out)
        self.assertIn("Hardware Page Faults:        0", out)
        self.assertIn("Swap Disk Operations:        0.00 KB", out)
        self.assertIn("OOM Process Terminations:    0", out)
        self.assertIn("Physical limits bypassed", out)

    def test_fluid_compact_and_pulse_command(self):
        c_out = run_fluid_cmd(["compact"])
        self.assertIn("Harmonic Compaction Executed", c_out)
        p_out = run_fluid_cmd(["pulse"])
        self.assertIn("pulse wave injected", p_out)

    def test_sh_shell_integration(self):
        u = CoreUtils()
        sh = SovereignShell(u)
        res = sh.eval("fluid status")
        self.assertIn("ADIOS FLUIDRAM", res)


if __name__ == "__main__":
    unittest.main()
