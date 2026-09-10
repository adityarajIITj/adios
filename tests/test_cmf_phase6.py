"""
tests/test_cmf_phase6.py - Verification Suite for CMF Phase 6 (Subsystem Integration)

Tests:
1. FluidRAMCMFBridge slab allocation and bi-directional indexing
2. Materializing causal slabs into physical FluidRAM pools
3. Intelligent causal dissipation (evaporating cheap recomputable slabs first)
4. Protection of root / expensive slabs during surface tension surge
5. TCM pre-warming coordination with TaskControlBlock working set
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kernel.fluid_ram import (
    FluidRAMMesh,
    POOL_USER_APPS, POOL_STREAM_RING,
    PAGE_PINNED, PAGE_TRANSIENT
)
from kernel.cmf import (
    MaterializationState,
    DerivationRecipe,
    CausalObject,
    FluidRAMCMFBridge
)
from proc.process import TaskControlBlock, PriorityClass, ProcessState


class TestCMFPhase6(unittest.TestCase):
    """Verifies Phase 6: Subsystem Integration (CMF + FluidRAM + TCM + Scheduler)."""

    def test_causal_slab_allocation_and_binding(self):
        """Verifies allocate_causal_slab binds physical FluidRAM slab to CMF object."""
        mesh = FluidRAMMesh(total_ram_mb=32)
        bridge = FluidRAMCMFBridge(mesh=mesh)

        payload = b"ROOT_AUDIO_STREAM_001"
        root_obj = bridge.allocate_causal_slab(
            object_id="audio_root",
            pool_name=POOL_USER_APPS,
            initial_data=payload
        )

        self.assertTrue(root_obj.is_materialized)
        self.assertIsNotNone(root_obj.slab_id)
        slab = mesh.get_slab_by_id(root_obj.slab_id)
        self.assertIsNotNone(slab)
        self.assertEqual(slab.read(), payload)
        self.assertEqual(bridge.object_to_slab["audio_root"], root_obj.slab_id)

    def test_materialize_causal_slab_sync(self):
        """Verifies unmaterialized causal object allocates physical slab upon materialization."""
        mesh = FluidRAMMesh(total_ram_mb=32)
        bridge = FluidRAMCMFBridge(mesh=mesh)

        # Root object
        bridge.allocate_causal_slab("raw_data", initial_data=bytes([1, 2, 3, 4]))

        # Derived recipe
        recipe = DerivationRecipe(
            "doubled_data",
            ["raw_data"],
            lambda inp, p: bytes([b * 2 for b in inp[0]]),
            "double"
        )
        derived = bridge.allocate_causal_slab("doubled_data", recipe=recipe)

        self.assertEqual(derived.state, MaterializationState.UNMATERIALIZED)
        self.assertIsNone(derived.slab_id)

        # Materialize via bridge
        result = bridge.materialize_causal_slab("doubled_data")
        expected = bytes([2, 4, 6, 8])
        self.assertEqual(result, expected)
        self.assertEqual(derived.state, MaterializationState.MATERIALIZED)
        self.assertIsNotNone(derived.slab_id)
        slab = mesh.get_slab_by_id(derived.slab_id)
        self.assertIsNotNone(slab)
        self.assertEqual(slab.read(), expected)

    def test_causal_dissipation_prioritizes_cheap_derivations(self):
        """Verifies dissipation evaporates cheap derivations first while preserving roots."""
        mesh = FluidRAMMesh(total_ram_mb=8)  # 8 MB pool
        bridge = FluidRAMCMFBridge(mesh=mesh)

        # 1. Allocate root data (2 MB)
        bridge.allocate_causal_slab("root_db", initial_data=b"D" * (2 * 1024 * 1024))

        # 2. Allocate cheap derived object (compute = 10 us, 2 MB)
        recipe_cheap = DerivationRecipe(
            "derived_cheap", ["root_db"],
            lambda inp, p: inp[0], "cheap_pass",
            estimated_compute_us=10.0
        )
        bridge.allocate_causal_slab("derived_cheap", initial_data=b"C" * (2 * 1024 * 1024), recipe=recipe_cheap)

        # 3. Allocate expensive derived object (compute = 10,000 us, 2 MB)
        recipe_heavy = DerivationRecipe(
            "derived_heavy", ["root_db"],
            lambda inp, p: inp[0], "heavy_compute",
            estimated_compute_us=10000.0
        )
        bridge.allocate_causal_slab("derived_heavy", initial_data=b"H" * (2 * 1024 * 1024), recipe=recipe_heavy)

        # Total allocated: 6 MB of 8 MB (75% occupancy -> pressure >= 0.75)
        pressure_initial = mesh.global_pressure
        self.assertGreaterEqual(pressure_initial, 0.70)

        # Trigger causal surface-tension dissipation
        report = bridge.dissipate_causal_surface_tension()

        # Cheap derivation must have been evaporated
        self.assertIn("derived_cheap", report["evaporated_causal_objects"])
        self.assertEqual(bridge.store.get("derived_cheap").state, MaterializationState.EVICTED)

        # Root object must remain materialized!
        self.assertEqual(bridge.store.get("root_db").state, MaterializationState.MATERIALIZED)

        # Pressure must be relieved
        self.assertLess(report["pressure_after"], report["pressure_before"])

    def test_tcm_scheduler_prewarm_integration(self):
        """Verifies process working set pre-warming via TCM contract coordination."""
        mesh = FluidRAMMesh(total_ram_mb=32)
        bridge = FluidRAMCMFBridge(mesh=mesh)

        # Root dataset
        bridge.allocate_causal_slab("matrix_a", initial_data=bytes([5, 10, 15, 20]))

        # Derived working set for a worker thread
        recipe = DerivationRecipe(
            "worker_cache", ["matrix_a"],
            lambda inp, p: bytes([b + 1 for b in inp[0]]), "add_one"
        )
        bridge.allocate_causal_slab("worker_cache", recipe=recipe)

        # Process starts sleeping until tick 10
        proc = TaskControlBlock(name="compute_worker", priority=PriorityClass.HIGH)
        proc.causal_working_set = ["worker_cache"]
        proc.state = ProcessState.SLEEPING
        proc.sleep_until_tick = 10

        bridge.register_process_working_set_for_prewarm(proc, target_tick=10)

        # At tick 4: still unmaterialized
        bridge.on_tick(current_tick=4)
        self.assertEqual(bridge.store.get("worker_cache").state, MaterializationState.UNMATERIALIZED)

        # At tick 8 (within 2 ticks of wake horizon 10): CMF pre-warms the working set!
        tick_report = bridge.on_tick(current_tick=8)
        self.assertEqual(tick_report["cmf_scheduler"]["prewarmed_objects"], 1)
        self.assertEqual(bridge.store.get("worker_cache").state, MaterializationState.MATERIALIZED)
        self.assertEqual(bridge.store.get("worker_cache").read(), bytes([6, 11, 16, 21]))


if __name__ == "__main__":
    unittest.main()
