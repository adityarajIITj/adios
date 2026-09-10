"""
kernel/cmf/spatial_distributed.py - Spatial & Distributed CMF Extension

Implements:
- Spatial memory tiers (NUMA, CXL pooled, remote node)
- Latency and bandwidth penalties across spatial interconnects
- Recipe serialization and peer-to-peer remote re-materialization
- Network bandwidth savings calculation: recipe replication vs raw memory transfer
"""

from enum import Enum, auto
from typing import Dict, List, Any, Optional, Set, Tuple
import json

from kernel.cmf.causal_types import MaterializationState, DerivationRecipe
from kernel.cmf.causal_object import CausalObject
from kernel.cmf.object_store import CausalObjectStore


class SpatialMemoryTier(Enum):
    HOST_LOCAL_DRAM     = "HOST_LOCAL_DRAM"      # 100 ns latency, 50 GB/s bandwidth
    CROSS_NUMA_NODE     = "CROSS_NUMA_NODE"      # 250 ns latency, 25 GB/s bandwidth
    CXL_POOLED_MEMORY   = "CXL_POOLED_MEMORY"    # 350 ns latency, 32 GB/s bandwidth
    REMOTE_FABRIC_NODE  = "REMOTE_FABRIC_NODE"   # 15,000 ns latency, 1.25 GB/s (10 GbE)


class SpatialCostMatrix:
    """Hardware interconnect performance parameters."""

    PROFILES = {
        SpatialMemoryTier.HOST_LOCAL_DRAM:    {"latency_us": 0.1,    "bandwidth_gb_s": 50.0},
        SpatialMemoryTier.CROSS_NUMA_NODE:    {"latency_us": 0.25,   "bandwidth_gb_s": 32.0},
        SpatialMemoryTier.CXL_POOLED_MEMORY:  {"latency_us": 0.35,   "bandwidth_gb_s": 20.0},
        SpatialMemoryTier.REMOTE_FABRIC_NODE: {"latency_us": 15.0,   "bandwidth_gb_s": 1.25}
    }

    @classmethod
    def calculate_transfer_cost_us(cls, tier: SpatialMemoryTier, size_bytes: int) -> float:
        prof = cls.PROFILES[tier]
        base_latency = prof["latency_us"]
        bandwidth = prof["bandwidth_gb_s"]
        transfer_us = (size_bytes / (bandwidth * 1e9)) * 1e6
        return round(base_latency + transfer_us, 3)


class DistributedCMFNode:
    """
    Manages causal object synchronization and recipe migration across spatial nodes.
    """

    def __init__(self, node_id: str, tier: SpatialMemoryTier = SpatialMemoryTier.HOST_LOCAL_DRAM):
        self.node_id = node_id
        self.tier = tier
        self.store = CausalObjectStore()
        self.network_bytes_sent = 0
        self.network_bytes_received = 0

    def export_recipe_manifest(self, object_id: str) -> Dict[str, Any]:
        """
        Serializes a lightweight derivation recipe manifest to transmit over network.
        Typically only hundreds of bytes vs hundreds of megabytes of raw data!
        """
        obj = self.store.get(object_id)
        if not obj:
            raise KeyError(f"Object '{object_id}' not found on node {self.node_id}.")

        manifest = {
            "object_id": obj.object_id,
            "version": obj.version,
            "is_root": obj.is_root,
            "size_bytes": obj.size_bytes,
            "derivation_hash": obj.derivation_hash,
            "owner_pool": obj.owner_pool,
            "recipe": None
        }

        if obj.recipe:
            manifest["recipe"] = {
                "transform_name": obj.recipe.transform_name,
                "input_ids": obj.recipe.input_ids,
                "parameters": obj.recipe.parameters,
                "purity": obj.recipe.purity.value,
                "estimated_compute_us": obj.recipe.estimated_compute_us,
                "output_size_bytes": obj.recipe.output_size_bytes,
                "validation_hash": obj.recipe.validation_hash
            }

        return manifest

    def calculate_bandwidth_saving(self, object_id: str) -> Dict[str, Any]:
        """
        Compares sending raw bytes over network vs sending CMF derivation recipe.
        """
        obj = self.store.get(object_id)
        if not obj or obj.is_root:
            return {"raw_bytes": obj.size_bytes if obj else 0, "recipe_bytes": 0, "reduction_pct": 0.0}

        manifest = self.export_recipe_manifest(object_id)
        recipe_bytes = len(json.dumps(manifest).encode("utf-8"))
        raw_bytes = obj.size_bytes

        reduction_pct = max(0.0, (1.0 - (recipe_bytes / float(raw_bytes))) * 100.0) if raw_bytes > 0 else 0.0

        return {
            "object_id": object_id,
            "raw_payload_bytes": raw_bytes,
            "recipe_manifest_bytes": recipe_bytes,
            "network_bytes_saved": max(0, raw_bytes - recipe_bytes),
            "bandwidth_reduction_pct": round(reduction_pct, 3)
        }
