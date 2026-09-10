"""
tests/test_cmf_phase8.py - Verification Suite for CMF Phase 8 (Spatial & Distributed CMF)

Tests:
1. Spatial interconnect latency and bandwidth calculations
2. Distributed recipe manifest export and schema verification
3. Bandwidth reduction quantification (recipe manifest vs raw buffer broadcast)
4. Peer-to-peer recipe replication and remote materialization on secondary node
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
    SpatialMemoryTier,
    SpatialCostMatrix,
    DistributedCMFNode
)


class TestCMFPhase8(unittest.TestCase):
    """Verifies Phase 8: Spatial & Distributed CMF Extension."""

    def test_spatial_cost_matrix_tiers(self):
        """Verifies spatial latency penalties across memory tiers."""
        payload_1mb = 1024 * 1024

        cost_local = SpatialCostMatrix.calculate_transfer_cost_us(SpatialMemoryTier.HOST_LOCAL_DRAM, payload_1mb)
        cost_numa = SpatialCostMatrix.calculate_transfer_cost_us(SpatialMemoryTier.CROSS_NUMA_NODE, payload_1mb)
        cost_cxl = SpatialCostMatrix.calculate_transfer_cost_us(SpatialMemoryTier.CXL_POOLED_MEMORY, payload_1mb)
        cost_fabric = SpatialCostMatrix.calculate_transfer_cost_us(SpatialMemoryTier.REMOTE_FABRIC_NODE, payload_1mb)

        self.assertLess(cost_local, cost_numa)
        self.assertLess(cost_numa, cost_cxl)
        self.assertLess(cost_cxl, cost_fabric)
        # Remote fabric should be orders of magnitude slower than local DRAM
        self.assertGreater(cost_fabric, cost_local * 10.0)

    def test_bandwidth_saving_calculation(self):
        """Verifies >99.9% bandwidth reduction sending recipe manifests instead of 10 MB payloads."""
        node = DistributedCMFNode("node_alpha")
        node.store.register_root("raw_camera", payload=b"RAW_INPUT")

        # Derived 10 MB frame buffer
        recipe = DerivationRecipe(
            "frame_hd",
            ["raw_camera"],
            lambda inp, p: b"FRAME" * (2 * 1024 * 1024),
            "render_hd",
            output_size_bytes=10 * 1024 * 1024
        )
        node.store.register_derivation(recipe)

        savings = node.calculate_bandwidth_saving("frame_hd")

        self.assertEqual(savings["raw_payload_bytes"], 10 * 1024 * 1024)
        self.assertLess(savings["recipe_manifest_bytes"], 500)  # ~300 bytes!
        self.assertGreater(savings["bandwidth_reduction_pct"], 99.9)

    def test_peer_recipe_replication_and_remote_materialization(self):
        """Verifies recipe transferred from Node A can be materialized on Node B."""
        node_a = DistributedCMFNode("node_a")
        node_b = DistributedCMFNode("node_b")

        # Node A creates recipe
        def invert_bytes(inputs, params):
            return bytes([b ^ 0xFF for b in inputs[0]])

        recipe_a = DerivationRecipe(
            "inverted_payload",
            ["shared_root"],
            invert_bytes,
            "invert_all"
        )
        node_a.store.register_root("shared_root", payload=bytes([0, 1, 2, 255]))
        node_a.store.register_derivation(recipe_a)

        # Export manifest from Node A
        manifest = node_a.export_recipe_manifest("inverted_payload")
        self.assertIn("recipe", manifest)
        self.assertEqual(manifest["recipe"]["transform_name"], "invert_all")

        # Node B receives manifest and shared root
        node_b.store.register_root("shared_root", payload=bytes([0, 1, 2, 255]))
        recipe_b = DerivationRecipe(
            output_id=manifest["object_id"],
            input_ids=manifest["recipe"]["input_ids"],
            transform=invert_bytes,  # looked up from registered transform catalogue
            transform_name=manifest["recipe"]["transform_name"]
        )
        node_b.store.register_derivation(recipe_b)

        # Materialize on Node B
        result_b = node_b.store.materialize("inverted_payload")
        expected = bytes([255, 254, 253, 0])
        self.assertEqual(result_b, expected)


if __name__ == "__main__":
    unittest.main()
