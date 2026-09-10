"""
tests/test_cmf_phase4.py - Verification Suite for CMF Phase 4 (Derivation Language & DAG Execution Engine)

Tests:
1. Composable Derivation Operators (OpMap, OpFilter, OpReduceSum, OpGaloisPermute)
2. Reversible Galois involution property (bit-exact roundtrip)
3. DerivationPipeline chaining and canonical JSON serialization
4. DAGExecutionEngine Kahn's topological sort on diamond graph
5. Telemetry logging and selective cached node re-use
"""

import os
import sys
import unittest
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kernel.cmf import (
    MaterializationState,
    PurityLevel,
    DerivationRecipe,
    CausalObject,
    CausalObjectStore,
    DerivationOp,
    OpMap,
    OpFilter,
    OpReduceSum,
    OpGaloisPermute,
    DerivationPipeline,
    DAGExecutionEngine
)


class TestCMFPhase4(unittest.TestCase):
    """Verifies Phase 4: Derivation Pipeline Language & DAG Execution Engine."""

    def test_basic_operators(self):
        """Verifies primitive operators produce expected byte transformations."""
        raw = bytes([10, 20, 30, 40, 50])

        # OpMap
        mapped = OpMap(lambda b: b + 5).apply(raw)
        self.assertEqual(mapped, bytes([15, 25, 35, 45, 55]))

        # OpFilter
        filtered = OpFilter(lambda b: b > 25).apply(raw)
        self.assertEqual(filtered, bytes([30, 40, 50]))

        # OpReduceSum
        reduced = OpReduceSum().apply(raw)
        total = int.from_bytes(reduced, byteorder="big")
        self.assertEqual(total, sum(raw))

    def test_galois_reversible_involution(self):
        """Verifies that OpGaloisPermute is bit-exact reversible when reapplied."""
        original = b"CONFIDENTIAL_KERNEL_PAYLOAD_XYZ"
        permuted = OpGaloisPermute(key=0x3C).apply(original)
        self.assertNotEqual(permuted, original)

        # Reapply same key -> must restore original bit-exactly
        restored = OpGaloisPermute(key=0x3C).apply(permuted)
        self.assertEqual(restored, original)

    def test_pipeline_chaining_and_serialization(self):
        """Verifies multi-stage pipeline execution and canonical JSON spec."""
        pipeline = (
            DerivationPipeline("audio_dsp")
            .add_op(OpFilter(lambda b: b > 10, "nonzero"))
            .add_op(OpMap(lambda b: b * 2, "gain_2x"))
            .add_op(OpGaloisPermute(key=0x7F))
        )

        input_data = bytes([5, 12, 8, 20])
        # Step 1: Filter (>10) -> [12, 20]
        # Step 2: Map (*2) -> [24, 40]
        # Step 3: Permute (^0x7F) -> [24 ^ 127, 40 ^ 127] = [103, 87]
        output = pipeline.execute([input_data])
        expected = bytes([24 ^ 0x7F, 40 ^ 0x7F])
        self.assertEqual(output, expected)

        # Verify serialization produces valid deterministic JSON
        spec = pipeline.serialize_spec()
        parsed = json.loads(spec)
        self.assertEqual(parsed["pipeline"], "audio_dsp")
        self.assertEqual(len(parsed["stages"]), 3)
        self.assertEqual(parsed["stages"][0]["op"], "FILTER_nonzero")

    def test_dag_topological_sort_diamond(self):
        """Verifies Kahn's algorithm ordering on a diamond graph: Root -> (B, C) -> D."""
        store = CausalObjectStore()
        store.register_root("R", payload=b"ROOT_BYTE_DATA")

        # B = R + 1
        store.register_derivation(
            DerivationRecipe("B", ["R"], lambda inp, p: bytes([(b + 1) % 256 for b in inp[0]]), "add1")
        )
        # C = R + 2
        store.register_derivation(
            DerivationRecipe("C", ["R"], lambda inp, p: bytes([(b + 2) % 256 for b in inp[0]]), "add2")
        )
        # D = B + C
        def merge_bc(inp, p):
            return bytes([(x ^ y) for x, y in zip(inp[0], inp[1])])

        store.register_derivation(
            DerivationRecipe("D", ["B", "C"], merge_bc, "xor_merge")
        )

        engine = DAGExecutionEngine(store)
        order = engine.compute_topological_order("D")

        # R must be first, D must be last, B and C between R and D
        self.assertEqual(order[0], "R")
        self.assertEqual(order[-1], "D")
        self.assertIn("B", order[1:3])
        self.assertIn("C", order[1:3])

    def test_dag_execution_engine_telemetry_and_caching(self):
        """Verifies plan execution, telemetry recording, and caching of resident nodes."""
        store = CausalObjectStore()
        store.register_root("data_in", payload=bytes([1, 2, 3, 4, 5]))

        # Stage 1: double
        store.register_derivation(
            DerivationRecipe("stage1", ["data_in"], lambda inp, p: bytes([b * 2 for b in inp[0]]), "double", output_size_bytes=5)
        )
        # Stage 2: reduce
        store.register_derivation(
            DerivationRecipe("stage2", ["stage1"], lambda inp, p: OpReduceSum().apply(inp[0]), "reduce", output_size_bytes=8)
        )

        engine = DAGExecutionEngine(store)

        # 1. First execution: stage1 and stage2 are unmaterialized
        result, telemetry1 = engine.execute_plan("stage2")
        expected_sum = (2 + 4 + 6 + 8 + 10).to_bytes(8, byteorder="big")
        self.assertEqual(result, expected_sum)
        self.assertEqual(telemetry1["nodes_recomputed"], 2)  # stage1 and stage2
        self.assertGreater(telemetry1["elapsed_us"], 0.0)

        # 2. Second execution: all nodes already materialized -> 0 recomputed!
        result2, telemetry2 = engine.execute_plan("stage2")
        self.assertEqual(result2, expected_sum)
        self.assertEqual(telemetry2["nodes_recomputed"], 0)  # Reused resident memory!


if __name__ == "__main__":
    unittest.main()
