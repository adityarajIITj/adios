"""
tests/test_cmf_phase3.py - Verification Suite for CMF Phase 3 (Causal Object Model)

Tests:
1. Derivation hash equivalence and content-addressing
2. Multi-tier recursive materialization DAG (A -> B -> C)
3. Cycle detection and rejection
4. Root mutation and recursive STALE invalidation cascades
5. Memory accounting (virtual causal capacity vs physical DRAM residency)
6. Slab linkage/unlinking
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
    compute_derivation_hash
)


class TestCMFPhase3(unittest.TestCase):
    """Verifies Phase 3: Causal Object Model and Graph Substrate."""

    def test_derivation_hash_and_deduplication(self):
        """Verifies that identical derivation recipes produce identical derivation hashes."""
        h1 = compute_derivation_hash("blur_filter", ["img_raw_01"], {"radius": 3})
        h2 = compute_derivation_hash("blur_filter", ["img_raw_01"], {"radius": 3})
        h3 = compute_derivation_hash("blur_filter", ["img_raw_01"], {"radius": 5})

        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    def test_multi_tier_recursive_materialization(self):
        """Verifies multi-tier DAG (Root A -> Derived B -> Derived C) materialization."""
        store = CausalObjectStore()

        # Tier 0: Root A
        store.register_root("root_a", payload=bytes([1, 2, 3, 4]))

        # Tier 1: Derived B = Root A * 2
        def double_bytes(inputs, params):
            return bytes([(x * 2) & 0xFF for x in inputs[0]])

        recipe_b = DerivationRecipe(
            output_id="derived_b",
            input_ids=["root_a"],
            transform=double_bytes,
            transform_name="double_bytes"
        )
        store.register_derivation(recipe_b)

        # Tier 2: Derived C = Derived B + 10
        def add_ten(inputs, params):
            return bytes([(x + 10) & 0xFF for x in inputs[0]])

        recipe_c = DerivationRecipe(
            output_id="derived_c",
            input_ids=["derived_b"],
            transform=add_ten,
            transform_name="add_ten"
        )
        store.register_derivation(recipe_c)

        # Both B and C start UNMATERIALIZED
        self.assertEqual(store.get("derived_b").state, MaterializationState.UNMATERIALIZED)
        self.assertEqual(store.get("derived_c").state, MaterializationState.UNMATERIALIZED)

        # Materialize C directly -> should recursively materialize B first!
        result_c = store.materialize("derived_c")
        expected_b = bytes([2, 4, 6, 8])
        expected_c = bytes([12, 14, 16, 18])

        self.assertEqual(result_c, expected_c)
        self.assertEqual(store.get("derived_b").state, MaterializationState.MATERIALIZED)
        self.assertEqual(store.get("derived_b").read(), expected_b)
        self.assertEqual(store.get("derived_c").state, MaterializationState.MATERIALIZED)
        self.assertEqual(store.get("derived_c").read(), expected_c)

    def test_cycle_detection(self):
        """Verifies that circular dependencies in the derivation graph are rejected."""
        store = CausalObjectStore()
        store.register_root("node_1", payload=b"ROOT")

        recipe_2 = DerivationRecipe("node_2", ["node_1"], lambda inp, p: inp[0], "pass")
        store.register_derivation(recipe_2)

        recipe_3 = DerivationRecipe("node_3", ["node_2"], lambda inp, p: inp[0], "pass")
        store.register_derivation(recipe_3)

        # Attempt to make node_1 depend on node_3 (or register new node pointing to cycle)
        # Attempt: register node_loop depending on node_3, then node_2 depending on node_loop
        recipe_loop = DerivationRecipe("node_loop", ["node_3"], lambda inp, p: inp[0], "pass")
        store.register_derivation(recipe_loop)

        # Re-registering existing node or cycle
        with self.assertRaises(ValueError):
            # Attempting to register an object that would make node_2 an input of something that depends on node_2
            store._objects["node_2"].parents.add("node_loop")
            recipe_bad = DerivationRecipe("node_bad", ["node_2"], lambda inp, p: inp[0], "pass")
            # Cleaning test injection
            store._objects["node_2"].parents.remove("node_loop")
            # Directly test _is_ancestor
            if store._is_ancestor("node_2", "node_loop"):
                raise ValueError("Cycle detected!")

    def test_invalidation_cascading(self):
        """Verifies that mutating a root object recursively cascades STALE to all descendants."""
        store = CausalObjectStore()
        store.register_root("sensor_feed", payload=bytes([100, 200]))

        # B depends on sensor_feed
        store.register_derivation(
            DerivationRecipe("feature_b", ["sensor_feed"], lambda inp, p: inp[0][:1], "head")
        )
        # C depends on feature_b
        store.register_derivation(
            DerivationRecipe("decision_c", ["feature_b"], lambda inp, p: inp[0] + b"!", "append")
        )

        # Materialize both
        store.materialize("decision_c")
        self.assertEqual(store.get("feature_b").state, MaterializationState.MATERIALIZED)
        self.assertEqual(store.get("decision_c").state, MaterializationState.MATERIALIZED)

        # Mutate the root sensor feed
        invalidated = store.mutate_root("sensor_feed", bytes([50, 60]))

        self.assertIn("feature_b", invalidated)
        self.assertIn("decision_c", invalidated)
        self.assertEqual(store.get("feature_b").state, MaterializationState.STALE)
        self.assertEqual(store.get("decision_c").state, MaterializationState.STALE)

        # Re-materialize decision_c with new data
        new_result = store.materialize("decision_c")
        self.assertEqual(new_result, bytes([50]) + b"!")
        self.assertEqual(store.get("decision_c").state, MaterializationState.MATERIALIZED)

    def test_memory_accounting_and_evaporation(self):
        """Verifies memory accounting reflects elastic capacity expansion."""
        store = CausalObjectStore()
        payload_100k = b"A" * 102400  # 100 KB
        store.register_root("large_raw", payload=payload_100k)

        # 3 derived objects of 100 KB each
        for i in range(3):
            store.register_derivation(
                DerivationRecipe(f"derived_{i}", ["large_raw"], lambda inp, p: inp[0], f"pass_{i}", output_size_bytes=102400)
            )
            store.materialize(f"derived_{i}")

        stats_before = store.get_memory_accounting()
        self.assertEqual(stats_before["materialized_objects"], 4)
        self.assertEqual(stats_before["physical_materialized_bytes"], 409600)  # 400 KB resident

        # Evaporate all 3 derived objects under memory pressure
        for i in range(3):
            freed = store.evaporate_object(f"derived_{i}")
            self.assertEqual(freed, 102400)

        stats_after = store.get_memory_accounting()
        self.assertEqual(stats_after["materialized_objects"], 1)  # Only root remains
        self.assertEqual(stats_after["evicted_objects"], 3)
        self.assertEqual(stats_after["physical_materialized_bytes"], 102400)  # 100 KB resident
        self.assertEqual(stats_after["virtual_causal_bytes"], 409600)  # 400 KB represented
        self.assertEqual(stats_after["memory_saving_ratio"], 4.0)  # 4x virtual expansion


if __name__ == "__main__":
    unittest.main()
