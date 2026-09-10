"""
tests/test_cmf_phase12.py - Verification Suite for CMF Phase 12 (Unified System Blueprint)

Tests:
1. End-to-end boot of AdiOSUnifiedKernel
2. Process spawning, MLFQ integration, and security context initialization
3. Allocating causal memory mapped to hardware MMU page tables
4. Advancing kernel ticks and tracking integrated scheduler / CMF steps
5. Transparent hardware fault resolution via CausalMMU
6. Holistic cross-subsystem telemetry verification
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kernel.cmf import (
    MaterializationState,
    DerivationRecipe,
    AdiOSUnifiedKernel
)
from proc.process import PriorityClass, ProcessState


class TestCMFPhase12(unittest.TestCase):
    """Verifies Phase 12: Unified System Blueprint."""

    def test_unified_kernel_boot_and_spawn(self):
        """Verifies unified kernel boot and process registration."""
        kernel = AdiOSUnifiedKernel(physical_ram_mb=64)

        self.assertEqual(kernel.physical_ram_mb, 64)
        self.assertEqual(kernel.current_tick, 0)

        # Spawn processes
        p1 = kernel.spawn_process("app_worker_1", priority=PriorityClass.HIGH)
        p2 = kernel.spawn_process("background_dsp", priority=PriorityClass.IDLE)

        self.assertEqual(len(kernel.scheduler.all_processes), 2)
        self.assertIn(p1.pid, kernel.security.contexts)
        self.assertIn(p2.pid, kernel.security.contexts)

    def test_end_to_end_causal_memory_allocation_and_mmu_translation(self):
        """Verifies allocating causal memory mapped into hardware MMU and transparent fault handling."""
        kernel = AdiOSUnifiedKernel(physical_ram_mb=64)
        p = kernel.spawn_process("data_processor")

        # 1. Allocate root input data (4KB)
        kernel.allocate_process_causal_memory(
            proc=p,
            vpn=100,
            object_id="raw_stream_1",
            initial_data=bytes([1, 2, 3, 4] * 1024)
        )

        # 2. Allocate derived computation (starts unmaterialized)
        recipe = DerivationRecipe(
            "doubled_stream",
            ["raw_stream_1"],
            lambda inp, p: bytes([(b * 2) & 0xFF for b in inp[0]]),
            "double",
            output_size_bytes=4096
        )
        kernel.allocate_process_causal_memory(
            proc=p,
            vpn=200,
            object_id="doubled_stream",
            recipe=recipe
        )

        # Verify VPN 200 is initially non-valid in MMU
        pte_200 = kernel.mmu.page_table[200]
        self.assertFalse(pte_200.is_valid)
        self.assertTrue(pte_200.is_causal)

        # 3. Process reads VPN 200 -> triggers FAULT_CAUSAL_MISS -> Resolved!
        frame, status = kernel.mmu.translate_and_read(vpn=200)
        self.assertEqual(status, "FAULT_CAUSAL_RESOLVED")
        self.assertEqual(frame[:4], bytes([2, 4, 6, 8]))
        self.assertTrue(pte_200.is_valid)

        # 4. Subsequent read hits TLB directly
        frame2, status2 = kernel.mmu.translate_and_read(vpn=200)
        self.assertEqual(status2, "TLB_HIT")
        self.assertEqual(frame2, frame)

    def test_kernel_tick_advancement_and_telemetry(self):
        """Verifies step_kernel_tick advances time and produces holistic telemetry."""
        kernel = AdiOSUnifiedKernel(physical_ram_mb=64)
        proc = kernel.spawn_process("interactive_app", priority=PriorityClass.HIGH)

        # Advance 5 ticks
        for _ in range(5):
            tick_report = kernel.step_kernel_tick()
            self.assertGreater(tick_report["tick"], 0)

        self.assertEqual(kernel.current_tick, 5)

        # Telemetry
        telemetry = kernel.get_unified_system_telemetry()
        self.assertEqual(telemetry["uptime_ticks"], 5)
        self.assertEqual(telemetry["physical_ram_mb"], 64)
        self.assertGreater(telemetry["mesh_pressure"], 0.0)
        self.assertEqual(telemetry["active_processes"], 1)


if __name__ == "__main__":
    unittest.main()
