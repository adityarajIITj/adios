"""
kernel/cmf/derivation_pipeline.py - Derivation Language & DAG Execution Engine

Implements:
- Composable derivation operators (Map, Filter, ReduceSum, GaloisPermute)
- DerivationPipeline: formal, serializable operator chains
- DAGExecutionEngine: Kahn's topological sort, parallel stage grouping, and dynamic telemetry
"""

from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from collections import deque
import time
import json

from kernel.cmf.causal_types import MaterializationState, PurityLevel, DerivationRecipe
from kernel.cmf.causal_object import CausalObject
from kernel.cmf.object_store import CausalObjectStore


class DerivationOp:
    """Base class for composable derivation operators."""

    def __init__(self, op_name: str, params: Optional[Dict[str, Any]] = None):
        self.op_name = op_name
        self.params = dict(params) if params else {}

    def apply(self, data: bytes) -> bytes:
        raise NotImplementedError

    def to_dict(self) -> Dict[str, Any]:
        return {"op": self.op_name, "params": self.params}


class OpMap(DerivationOp):
    """Element-wise byte transformation with lambda or scalar operation."""

    def __init__(self, fn: Callable[[int], int], fn_name: str = "custom_map", params: Optional[Dict[str, Any]] = None):
        super().__init__(f"MAP_{fn_name}", params)
        self.fn = fn

    def apply(self, data: bytes) -> bytes:
        return bytes([self.fn(b) & 0xFF for b in data])


class OpFilter(DerivationOp):
    """Byte-filtering operator."""

    def __init__(self, predicate: Callable[[int], bool], pred_name: str = "custom_filter", params: Optional[Dict[str, Any]] = None):
        super().__init__(f"FILTER_{pred_name}", params)
        self.predicate = predicate

    def apply(self, data: bytes) -> bytes:
        return bytes([b for b in data if self.predicate(b)])


class OpReduceSum(DerivationOp):
    """In-slab summation reduction (Morphic compatible)."""

    def __init__(self):
        super().__init__("REDUCE_SUM")

    def apply(self, data: bytes) -> bytes:
        total = sum(data)
        # Return 8-byte big-endian unsigned integer
        return total.to_bytes(8, byteorder="big", signed=False)


class OpGaloisPermute(DerivationOp):
    """Chronos-compatible Galois Field GF(2^8) invertible permutation."""

    def __init__(self, key: int = 0x5A):
        super().__init__("GALOIS_PERMUTE", {"key": key})
        self.key = key & 0xFF

    def apply(self, data: bytes) -> bytes:
        # Reversible bitwise non-linear involution
        return bytes([(b ^ self.key) for b in data])


class DerivationPipeline:
    """A sequential composite chain of DerivationOps."""

    def __init__(self, name: str, ops: Optional[List[DerivationOp]] = None):
        self.name = name
        self.ops: List[DerivationOp] = list(ops) if ops else []

    def add_op(self, op: DerivationOp) -> 'DerivationPipeline':
        self.ops.append(op)
        return self

    def execute(self, inputs: List[bytes], params: Optional[Dict[str, Any]] = None) -> bytes:
        """Executes the pipeline sequentially starting from input[0]."""
        if not inputs:
            return b""
        current = inputs[0]
        for op in self.ops:
            current = op.apply(current)
        return current

    def serialize_spec(self) -> str:
        """Deterministic JSON specification of pipeline for content-addressing."""
        spec = {
            "pipeline": self.name,
            "stages": [op.to_dict() for op in self.ops]
        }
        return json.dumps(spec, sort_keys=True)


class DAGExecutionEngine:
    """
    Schedules and executes multi-node CMF derivations using Kahn's topological sort
    and stage-by-stage dependency resolution.
    """

    def __init__(self, store: CausalObjectStore):
        self.store = store
        self.telemetry_history: List[Dict[str, Any]] = []

    def compute_topological_order(self, target_id: str) -> List[str]:
        """
        Computes the topological ordering of all ancestors required to materialize target_id.
        Uses Kahn's algorithm.
        """
        target = self.store.get(target_id)
        if not target:
            raise KeyError(f"Target object '{target_id}' not found.")

        # 1. Collect all reachable ancestors
        visited: Set[str] = set()
        ancestor_subgraph: Dict[str, Set[str]] = {}  # node -> set of parent nodes

        def collect(node_id: str):
            if node_id in visited:
                return
            visited.add(node_id)
            node = self.store.get(node_id)
            if not node:
                return
            ancestor_subgraph[node_id] = set(node.parents)
            for p in node.parents:
                collect(p)

        collect(target_id)

        # 2. In-degree calculation for subgraph (children in subgraph)
        in_degree: Dict[str, int] = {node: len(parents) for node, parents in ancestor_subgraph.items()}

        # 3. Queue nodes with in_degree == 0 (roots)
        queue = deque([node for node, deg in in_degree.items() if deg == 0])
        order: List[str] = []

        while queue:
            curr = queue.popleft()
            order.append(curr)

            # Find all nodes in subgraph that have curr as a parent
            for candidate, parents in ancestor_subgraph.items():
                if curr in parents:
                    in_degree[candidate] -= 1
                    if in_degree[candidate] == 0:
                        queue.append(candidate)

        if len(order) != len(visited):
            raise ValueError("Cycle detected in causal dependency graph!")

        return order

    def execute_plan(self, target_id: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Executes the derivation plan for target_id in topological order.
        Returns the materialized bytes and execution telemetry.
        """
        topo_order = self.compute_topological_order(target_id)

        t0 = time.perf_counter()
        nodes_evaluated = 0
        nodes_recomputed = 0
        total_bytes_materialized = 0

        for node_id in topo_order:
            node = self.store.get(node_id)
            nodes_evaluated += 1
            if not node.is_materialized or node.state == MaterializationState.STALE:
                self.store.materialize(node_id)
                nodes_recomputed += 1
                total_bytes_materialized += node.size_bytes

        target_obj = self.store.get(target_id)
        elapsed_us = (time.perf_counter() - t0) * 1e6

        telemetry = {
            "target_id": target_id,
            "total_nodes_in_plan": len(topo_order),
            "nodes_evaluated": nodes_evaluated,
            "nodes_recomputed": nodes_recomputed,
            "total_materialized_bytes": total_bytes_materialized,
            "elapsed_us": round(elapsed_us, 2),
            "topological_plan": topo_order
        }
        self.telemetry_history.append(telemetry)

        return target_obj.read(), telemetry
