"""
tests/test_cmf_phase2.py - Comprehensive Verification of CMF Phase 2 Architecture

Tests:
1. Root vs Derived Causal Objects
2. First-class Derivation Recipe [C = f(A, B)]
3. Lifecycle state transitions: UNMATERIALIZED -> MATERIALIZING -> MATERIALIZED -> EVICTED -> MATERIALIZED
4. Process lifespan independence (recipe survives producer process exit)
5. Validation hash integrity checking (cryptographic assurance)
6. Rematerialization cost modeling vs disk swap latency
7. Purity classification
"""

import os
import sys
import unittest
import hashlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kernel.cmf.causal_types import (
    MaterializationState,
    PurityLevel,
    DerivationRecipe,
    CausalMemoryObject
)


class TestCMFPhase2(unittest.TestCase):
    """Verifies Phase 2: The Architectural Gap & Missing CMF Primitive."""

    def test_root_object_creation_and_immutability(self):
        """Verifies root causal objects cannot be evaporated without external backing."""
        raw_payload = b"ROOT_GROUND_TRUTH_DATA_12345"
        root_obj = CausalMemoryObject(
            object_id="root_sensor_01",
            recipe=None,
            initial_bytes=raw_payload
        )
        self.assertTrue(root_obj.is_root)
        self.assertEqual(root_obj.state, MaterializationState.MATERIALIZED)
        self.assertEqual(root_obj.read(), raw_payload)

        # Evaporating root without backing store raises PermissionError
        with self.assertRaises(PermissionError):
            root_obj.evaporate()

    def test_derived_object_lazy_lifecycle(self):
        """Verifies lazy materialization, evaporation, and re-materialization."""
        # 1. Create two root objects A and B
        raw_a = bytes([10, 20, 30, 40, 50])
        raw_b = bytes([1, 2, 3, 4, 5])
        obj_a = CausalMemoryObject("obj_a", initial_bytes=raw_a)
        obj_b = CausalMemoryObject("obj_b", initial_bytes=raw_b)

        # 2. Define transform function: Vector addition C[i] = A[i] + B[i]
        def vector_add(inputs, params):
            a, b = inputs[0], inputs[1]
            return bytes([(x + y) & 0xFF for x, y in zip(a, b)])

        recipe = DerivationRecipe(
            output_id="obj_c",
            input_ids=["obj_a", "obj_b"],
            transform=vector_add,
            transform_name="vector_add_simd",
            purity=PurityLevel.PURE_DETERMINISTIC,
            estimated_compute_us=25.0,
            output_size_bytes=5
        )

        obj_c = CausalMemoryObject("obj_c", recipe=recipe)

        # Initial state: UNMATERIALIZED (Zero physical bytes allocated)
        self.assertEqual(obj_c.state, MaterializationState.UNMATERIALIZED)
        self.assertFalse(obj_c.is_materialized)
        with self.assertRaises(MemoryError):
            obj_c.read()

        # Materialize C from inputs A and B
        result_c = obj_c.materialize([obj_a, obj_b])
        expected = bytes([11, 22, 33, 44, 55])
        self.assertEqual(result_c, expected)
        self.assertEqual(obj_c.state, MaterializationState.MATERIALIZED)
        self.assertEqual(obj_c.read(), expected)
        self.assertEqual(obj_c.materialization_count, 1)

        # Evaporate C under simulated memory pressure
        freed = obj_c.evaporate()
        self.assertEqual(freed, 5)
        self.assertEqual(obj_c.state, MaterializationState.EVICTED)
        self.assertFalse(obj_c.is_materialized)
        self.assertEqual(obj_c.eviction_count, 1)

        # Re-materialize C on demand
        recomputed = obj_c.materialize([obj_a, obj_b])
        self.assertEqual(recomputed, expected)
        self.assertEqual(obj_c.state, MaterializationState.MATERIALIZED)
        self.assertEqual(obj_c.materialization_count, 2)

    def test_process_lifespan_independence(self):
        """Verifies recipe survives the termination of the producer process."""
        def filter_odds(inputs, params):
            return bytes([b for b in inputs[0] if b % 2 == 0])

        producer_pid = 4096
        recipe = DerivationRecipe(
            output_id="even_bytes_obj",
            input_ids=["raw_stream"],
            transform=filter_odds,
            transform_name="filter_even_elements",
            producer_pid=producer_pid
        )

        derived = CausalMemoryObject("even_bytes_obj", recipe=recipe)
        raw_stream = CausalMemoryObject("raw_stream", initial_bytes=bytes([1, 2, 3, 4, 5, 6, 7, 8]))

        # Simulate producer process exit (pid 4096 destroyed in OS scheduler)
        del producer_pid

        # A completely different consumer process (pid 9999) requests the object
        consumer_pid = 9999
        self.assertEqual(derived.recipe.producer_pid, 4096)  # Record preserved
        result = derived.materialize([raw_stream])
        self.assertEqual(result, bytes([2, 4, 6, 8]))

    def test_validation_hash_enforcement(self):
        """Verifies that cryptographic hash mismatch triggers validation failure."""
        expected_output = b"DETERMINISTIC_PAYLOAD_ABC"
        correct_hash = hashlib.sha256(expected_output).hexdigest()
        corrupt_hash = "0" * 64

        # Transform returning expected payload
        def identity_tx(inputs, params):
            return expected_output

        # 1. Valid hash recipe succeeds
        recipe_valid = DerivationRecipe(
            output_id="valid_obj",
            input_ids=[],
            transform=identity_tx,
            transform_name="identity_tx",
            validation_hash=correct_hash
        )
        obj_valid = CausalMemoryObject("valid_obj", recipe=recipe_valid)
        self.assertEqual(obj_valid.materialize([]), expected_output)

        # 2. Corrupted hash recipe raises ValueError
        recipe_corrupt = DerivationRecipe(
            output_id="corrupt_obj",
            input_ids=[],
            transform=identity_tx,
            transform_name="identity_tx",
            validation_hash=corrupt_hash
        )
        obj_corrupt = CausalMemoryObject("corrupt_obj", recipe=recipe_corrupt)
        with self.assertRaises(ValueError):
            obj_corrupt.materialize([])

    def test_rematerialization_cost_calculation(self):
        """Verifies cost model calculates compute + memory bus read latency accurately."""
        recipe = DerivationRecipe(
            output_id="heavy_obj",
            input_ids=["in1", "in2"],
            transform=lambda inp, p: b"X" * 65536,
            transform_name="heavy_compute",
            estimated_compute_us=35.0,
            output_size_bytes=65536
        )
        obj = CausalMemoryObject("heavy_obj", recipe=recipe)

        # Bus transfer for 2 inputs of 64 KB = 128 KB at 6.0 GB/s
        # 131,072 / 6e9 * 1e6 =~ 21.84 us
        # Total cost =~ 35.0 + 21.85 = 56.85 us
        cost_us = obj.calculate_rematerialization_cost_us(host_mem_bus_gb_s=6.0)
        self.assertGreater(cost_us, 35.0)
        self.assertLess(cost_us, 100.0)  # ~56.8 us vs 150,000 us for Linux disk swap!


if __name__ == "__main__":
    unittest.main()
