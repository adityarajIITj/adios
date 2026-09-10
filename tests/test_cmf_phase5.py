"""
tests/test_cmf_phase5.py - Verification Suite for CMF Phase 5 (Re-Materialization Engine & Cost Model)

Tests:
1. Cost model equations (T_remat vs T_swap_stall)
2. Retention penalty scaling with surface tension pressure and idle age
3. Eviction decision engine (low vs high vs critical pressure)
4. MaterializationBudget quota enforcement and reset
5. RematerializationScheduler on_tick execution and TCM pre-warming coordination
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kernel.cmf import (
    MaterializationState,
    PurityLevel,
    DerivationRecipe,
    CausalObject,
    CausalObjectStore,
    CostModelParameters,
    MaterializationBudget,
    RematerializationCostEngine,
    MaterializationPolicy,
    RematerializationScheduler
)


class TestCMFPhase5(unittest.TestCase):
    """Verifies Phase 5: Re-Materialization Engine & Cost Model."""

    def test_cost_calculation(self):
        """Verifies rematerialization cost equation against theoretical baseline."""
        engine = RematerializationCostEngine(CostModelParameters(host_mem_bus_gb_s=5.0))

        # Root object -> infinity
        root = CausalObject("root_raw", initial_payload=b"12345")
        self.assertEqual(engine.calculate_rematerialization_cost_us(root), float('inf'))

        # Derived object: compute = 50 us, input = 25 KB
        # Bus transfer = 25,600 / (5e9) * 1e6 = 5.12 us
        # Total =~ 55.12 us
        recipe = DerivationRecipe(
            "derived_obj",
            ["root_raw"],
            lambda inp, p: inp[0],
            "pass",
            estimated_compute_us=50.0,
            output_size_bytes=25600
        )
        derived = CausalObject("derived_obj", recipe=recipe, size_bytes=25600)
        cost = engine.calculate_rematerialization_cost_us(derived, input_sizes=[25600])

        self.assertAlmostEqual(cost, 55.12, delta=1.0)
        # Verify it's orders of magnitude cheaper than standard 15,000 us swap stall
        self.assertLess(cost, 15000.0 * 0.01)

    def test_retention_penalty_scaling(self):
        """Verifies retention penalty increases non-linearly with pressure and age."""
        engine = RematerializationCostEngine()
        obj = CausalObject("active_slab", initial_payload=b"A" * 10240)  # 10 KB
        obj.last_accessed_tick = 100

        # At tick 100 (idle = 0):
        # Low pressure (0.2):
        penalty_low = engine.calculate_retention_penalty(obj, surface_tension_pressure=0.2, current_tick=100)
        # High pressure (0.9):
        penalty_high = engine.calculate_retention_penalty(obj, surface_tension_pressure=0.9, current_tick=100)
        # High pressure + Old age (tick 200, idle = 100 -> age factor = 2.0):
        penalty_old = engine.calculate_retention_penalty(obj, surface_tension_pressure=0.9, current_tick=200)

        self.assertGreater(penalty_high, penalty_low * 5.0)
        self.assertGreater(penalty_old, penalty_high * 1.5)

    def test_eviction_decision_rules(self):
        """Verifies should_evaporate behavior under varying pressure regimes."""
        engine = RematerializationCostEngine()

        root = CausalObject("root", initial_payload=b"ROOT")
        recipe = DerivationRecipe("derived", ["root"], lambda inp, p: inp[0], "pass", estimated_compute_us=20.0)
        derived = CausalObject("derived", recipe=recipe, initial_payload=b"DERIVED")

        # 1. Under low pressure (0.40) -> Never evaporate
        self.assertFalse(engine.should_evaporate(derived, surface_tension_pressure=0.40, current_tick=10))

        # 2. Under high pressure (0.80) -> Derived object evaporates (cheap compute)
        self.assertTrue(engine.should_evaporate(derived, surface_tension_pressure=0.80, current_tick=10))

        # 3. Root object never evaporates under any pressure
        self.assertFalse(engine.should_evaporate(root, surface_tension_pressure=0.99, current_tick=10))

    def test_materialization_budget(self):
        """Verifies CPU budget enforcement and reset."""
        budget = MaterializationBudget(budget_limit_us=100.0)

        self.assertTrue(budget.has_budget(40.0))
        budget.consume(40.0)
        self.assertEqual(budget.consumed_us, 40.0)

        self.assertTrue(budget.has_budget(50.0))
        budget.consume(50.0)
        self.assertEqual(budget.consumed_us, 90.0)

        # 90 + 20 = 110 > 100 -> Rejected!
        self.assertFalse(budget.has_budget(20.0))

        # Reset for new tick
        budget.reset()
        self.assertEqual(budget.consumed_us, 0.0)
        self.assertTrue(budget.has_budget(20.0))

    def test_scheduler_prewarm_and_evaporate(self):
        """Verifies RematerializationScheduler coordinates evaporation and pre-warming."""
        store = CausalObjectStore()
        store.register_root("sensor_stream", payload=b"SENSOR_DATA")

        # Register derived task working set
        recipe = DerivationRecipe(
            "task_ws",
            ["sensor_stream"],
            lambda inp, p: inp[0] + b"_PROCESSED",
            "process",
            estimated_compute_us=30.0
        )
        store.register_derivation(recipe)

        scheduler = RematerializationScheduler(store)

        # 1. Schedule eager prewarm for tick 10
        scheduler.schedule_prewarm("task_ws", target_tick=10)

        # At tick 5 (far from tick 10) -> not yet pre-warmed
        status_t5 = scheduler.on_tick(current_tick=5, system_pressure=0.2)
        self.assertEqual(status_t5["prewarmed_objects"], 0)
        self.assertEqual(store.get("task_ws").state, MaterializationState.UNMATERIALIZED)

        # At tick 8 (target 10 - 8 = 2 <= 2) -> pre-warm executes!
        status_t8 = scheduler.on_tick(current_tick=8, system_pressure=0.2)
        self.assertEqual(status_t8["prewarmed_objects"], 1)
        self.assertEqual(store.get("task_ws").state, MaterializationState.MATERIALIZED)
        self.assertEqual(store.get("task_ws").read(), b"SENSOR_DATA_PROCESSED")

        # At tick 12: Memory pressure surges to 0.85 -> scheduler evaporates task_ws!
        status_t12 = scheduler.on_tick(current_tick=12, system_pressure=0.85)
        self.assertEqual(status_t12["evaporated_objects"], 1)
        self.assertEqual(store.get("task_ws").state, MaterializationState.EVICTED)


if __name__ == "__main__":
    unittest.main()
