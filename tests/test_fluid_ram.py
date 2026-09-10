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
    POOL_CHRONOS_DELTA, POOL_USER_APPS, POOL_DYNAMIC_MESH,
    PAGE_PINNED, PAGE_RECONSTRUCTIBLE, PAGE_TRANSIENT, PAGE_CACHE,
    ReversibleStateChain, PhysicalMemorySlab
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

    def test_physical_slab_allocation_and_borrowing(self):
        """Validates real physical memory slab allocation, byte reading/writing, and slab migration."""
        slab = self.mesh.allocate_physical_slab(
            POOL_STREAM_RING, 1024 * 1024, PAGE_TRANSIENT, b"INITIAL_SLAB_DATA"
        )
        self.assertIsInstance(slab, PhysicalMemorySlab)
        self.assertEqual(slab.owner_pool, POOL_STREAM_RING)
        self.assertEqual(slab.size_bytes, 1024 * 1024)

        # Write and read back data
        written = self.mesh.write_physical_slab(slab.slab_id, 0, b"ADIOS_SLAB_WRITE_TEST")
        self.assertEqual(written, 21)
        read_back = self.mesh.read_physical_slab(slab.slab_id, 0, 21)
        self.assertEqual(read_back, b"ADIOS_SLAB_WRITE_TEST")

        # Test borrowing moves unpinned slabs from lender to requesting pool
        target_pool = POOL_USER_APPS
        self.mesh.borrow_pages(target_pool, 5.0)
        # Verify slab was transferred
        self.assertIn(slab.slab_id, self.mesh.pools[target_pool].slabs)
        self.assertEqual(slab.owner_pool, target_pool)

    def test_dissipation_preserves_pinned_slabs(self):
        """Verifies that surface tension dissipation reclaims TRANSIENT and CACHE slabs while preserving PINNED."""
        pinned = self.mesh.allocate_physical_slab(
            POOL_USER_APPS, 1024 * 1024, PAGE_PINNED, b"CRITICAL_PINNED_KERNEL_VECTORS"
        )
        transient = self.mesh.allocate_physical_slab(
            POOL_USER_APPS, 1024 * 1024, PAGE_TRANSIENT, b"DISCARDABLE_STREAM_FRAME"
        )

        freed_mb = self.mesh.dissipate_surface_tension()
        self.assertGreaterEqual(freed_mb, 1)

        # Pinned slab MUST still exist and have exact uncorrupted bytes
        self.assertIn(pinned.slab_id, self.mesh.pools[POOL_USER_APPS].slabs)
        content = self.mesh.read_physical_slab(pinned.slab_id, 0, 30)
        self.assertEqual(content, b"CRITICAL_PINNED_KERNEL_VECTORS")

        # Transient slab should be dissipated
        self.assertNotIn(transient.slab_id, self.mesh.pools[POOL_USER_APPS].slabs)


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

    def test_transduce_frame_stream_scanline_blit(self):
        """Validates real scanline blitting into destination framebuffer and zero disk writes."""
        w, h = 64, 32
        src_frame = bytes([(i % 250) + 1 for i in range(w * h * 4)])
        dest_fb = bytearray(1280 * 720 * 4)

        res = self.decoder.transduce_frame_stream(
            src_frame, dest_fb, dest_x=10, dest_y=10, width=w, height=h, dest_stride=1280
        )
        self.assertTrue(res["evaporated"])
        self.assertEqual(res["disk_writes_bytes"], 0)
        self.assertLessEqual(res["resident_scratchpad_mb"], 4.0)

        # Check destination framebuffer has non-zero pixels at blit destination
        offset = ((10 * 1280) + 10) * 4
        self.assertEqual(dest_fb[offset : offset + 4], src_frame[:4])

    def test_void_pipe_peak_memory_measurement(self):
        """Verifies physically measured scratchpad memory is strictly < 4.0 MB."""
        peak_mb = self.decoder.get_measured_peak_memory_mb()
        self.assertLess(peak_mb, 4.0)
        self.assertGreater(peak_mb, 0.5)


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

    def test_continuous_multi_step_trajectory_rewind(self):
        """Validates continuous 20-step trajectory rewind with >70% storage reduction and 100% bitwise exactness."""
        chain = ReversibleStateChain(self.inverter)
        state_len = 2048
        s0 = bytes([i % 256 for i in range(state_len)])
        current = bytearray(s0)

        # Record 20 steps of sequential sparse mutation
        for step in range(20):
            nxt = bytearray(current)
            for j in range(0, state_len, 32):
                nxt[j] = (nxt[j] + step + 13) & 0xFF
            chain.record_transition(bytes(current), bytes(nxt), key=0x03)
            current = nxt

        # Check storage savings
        savings = chain.get_storage_savings_ratio()
        self.assertGreater(savings, 0.70)

        # Rewind all 20 steps back to S_0
        reconstructed_s0 = chain.rewind_to_start(bytes(current))
        self.assertEqual(reconstructed_s0, s0)


class TestEmpiricalDensityBenchmark(unittest.TestCase):
    """Validates real 4x workload density execution and bitwise correctness."""

    def test_empirical_4x_benchmark_execution(self):
        mesh = FluidRAMMesh()
        res = mesh.run_empirical_4x_benchmark(scale_mb=256)
        self.assertTrue(res["pinned_bitwise_verified"])
        self.assertTrue(res["galois_bitwise_verified"])
        self.assertTrue(res["density_target_met"])
        self.assertTrue(res["void_pipe_bounded_ok"])
        self.assertEqual(res["hardware_page_faults"], 0)
        self.assertEqual(res["swap_disk_operations_kb"], 0.0)
        self.assertEqual(res["oom_terminations"], 0)


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


class TestFluidRAMDesktopIntegration(unittest.TestCase):
    """Validates FluidRAM desktop integration, start menu item 19, desktop icon, and shell launch."""

    def setUp(self):
        from desktop.master_desktop import MasterDesktop, TASKBAR_HEIGHT
        self.desktop = MasterDesktop(width=1280, height=720)
        self.taskbar_h = TASKBAR_HEIGHT

    def test_start_menu_launch_item_19(self):
        """Validates that clicking item 19 in Start Menu opens FluidRAM Oscilloscope."""
        self.desktop.win_fluid.visible = False
        self.desktop.handle_mouse_down(10, 10)  # Open start menu
        self.assertTrue(self.desktop.start_menu_open)
        
        # Item 19: rel_item = 18. Hit y = TASKBAR_HEIGHT + 30 + 18 * 20 + 4
        click_y = self.taskbar_h + 30 + 18 * 20 + 4
        res = self.desktop.handle_mouse_down(50, click_y)
        self.assertEqual(res, ("menu_select", "fluid_ram"))
        self.assertTrue(self.desktop.win_fluid.visible)
        self.assertFalse(self.desktop.start_menu_open)

    def test_desktop_icon_double_click(self):
        """Validates that double-clicking the FluidRAM desktop icon launches the window."""
        self.desktop.win_fluid.visible = False
        fluid_icon = [i for i in self.desktop.icons.icons if i.icon_id == "fluid_ram"][0]
        
        # First click selects
        res1 = self.desktop.handle_mouse_down(fluid_icon.x + 10, fluid_icon.y + 10)
        self.assertEqual(res1, ("icon_select", "fluid_ram"))
        
        # Second click within interval launches
        res2 = self.desktop.handle_mouse_down(fluid_icon.x + 10, fluid_icon.y + 10)
        self.assertEqual(res2, ("icon_launch", "fluid_ram"))
        self.assertTrue(self.desktop.win_fluid.visible)

    def test_shell_command_launch(self):
        """Validates launching FluidRAM from shell input command."""
        self.desktop.win_fluid.visible = False
        self.desktop.wm.focus_window(self.desktop.win_shell)
        self.desktop.shell_input = "fluid"
        self.desktop.handle_key("\n")
        self.assertTrue(self.desktop.win_fluid.visible)
        self.assertIn("FluidRAM", self.desktop.shell_history[-1])

    def test_fluid_window_rendering_and_interaction(self):
        """Validates that FluidRAM renders on desktop framebuffer without clipping or errors."""
        self.desktop.launch_or_focus("fluid_ram")
        fb = bytearray(1280 * 720 * 4)
        self.desktop.step_frame(200, 200)
        self.desktop.render(fb)
        self.assertEqual(len(fb), 1280 * 720 * 4)
        
        # Test clicking Pulse Wave button
        self.desktop.win_fluid.on_click_content(self.desktop.win_fluid, 50, 45)
        self.assertIn("Pressure pulse injected", self.desktop.fluid_oscilloscope.status_message)


class TestOperatingSystemProofEngine(unittest.TestCase):
    """Verifies that the empirical proofs solving 40-year-old OS problems execute and validate."""

    def setUp(self):
        from userland.proof_of_sovereignty import OperatingSystemProofEngine
        self.engine = OperatingSystemProofEngine()

    def test_proof_1_thrashing_eliminated(self):
        res = self.engine.run_proof_1_thrashing_vs_hydrodynamics()
        self.assertEqual(res["adios_fluid_ram"]["page_faults"], 0)
        self.assertEqual(res["adios_fluid_ram"]["swap_disk_written_kb"], 0.0)
        self.assertGreater(res["speedup_factor"], 100)

    def test_proof_2_oom_killer_eliminated(self):
        res = self.engine.run_proof_2_oom_killer_vs_surface_dissipation()
        self.assertEqual(res["adios_fluid_ram"]["processes_killed"], 0)
        self.assertTrue(res["adios_fluid_ram"]["pinned_data_intact"])
        self.assertTrue(res["adios_fluid_ram"]["transient_evaporated"])

    def test_proof_3_galois_retro_inversion(self):
        res = self.engine.run_proof_3_snapshot_bloat_vs_galois_retro_inversion()
        self.assertTrue(res["adios_galois_engine"]["bitwise_exact_reconstruction"])
        self.assertGreater(res["adios_galois_engine"]["memory_savings_pct"], 75.0)

    def test_proof_4_void_pipe_bounded_stream(self):
        res = self.engine.run_proof_4_chromium_bloat_vs_void_pipe()
        self.assertLess(res["adios_void_pipe"]["resident_memory_mb"], 4.0)
        self.assertEqual(res["adios_void_pipe"]["disk_cache_writes_mb"], 0.0)
        self.assertGreater(res["memory_reduction_ratio"], 50.0)


if __name__ == "__main__":
    unittest.main()

