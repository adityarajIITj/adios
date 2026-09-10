"""
kernel/cmf/object_store.py - Kernel Causal Object Store & Graph Registry

Manages:
- Registration of root and derived CausalObjects
- Bi-directional dependency tracking (parents and children)
- Content-addressable and derivation-hash lookups
- Cycle detection across derivation DAGs
- Recursive invalidation cascading (marking descendants STALE upon root mutation)
- System memory tracking (materialized RAM vs virtual causal footprint)
"""

import hashlib
from typing import Dict, List, Any, Optional, Set
from kernel.cmf.causal_types import MaterializationState, DerivationRecipe
from kernel.cmf.causal_object import CausalObject


class CausalObjectStore:
    """
    Central kernel registry managing the global Causal Object DAG.
    """

    def __init__(self):
        self._objects: Dict[str, CausalObject] = {}
        self._hash_index: Dict[str, str] = {}  # derivation_hash -> object_id

    def register_root(self, object_id: str, payload: bytes, owner_pool: str = "POOL_USER_APPS") -> CausalObject:
        """Registers a ground-truth root object with immediate physical materialization."""
        if object_id in self._objects:
            raise KeyError(f"Causal object '{object_id}' is already registered.")

        obj = CausalObject(
            object_id=object_id,
            recipe=None,
            initial_payload=payload,
            owner_pool=owner_pool
        )
        self._objects[object_id] = obj
        self._hash_index[obj.derivation_hash] = object_id
        return obj

    def register_derivation(self, recipe: DerivationRecipe, owner_pool: str = "POOL_USER_APPS") -> CausalObject:
        """Registers a derived causal object and updates DAG dependency linkages."""
        if recipe.output_id in self._objects:
            raise KeyError(f"Causal object '{recipe.output_id}' is already registered.")

        # Ensure all parents exist
        for parent_id in recipe.input_ids:
            if parent_id not in self._objects:
                raise KeyError(f"Parent object '{parent_id}' does not exist in CausalObjectStore.")

        # Cycle detection: check if recipe.output_id is already an ancestor of any input
        for parent_id in recipe.input_ids:
            if self._is_ancestor(recipe.output_id, parent_id):
                raise ValueError(
                    f"Causal cycle detected! '{recipe.output_id}' is an ancestor of parent '{parent_id}'."
                )

        obj = CausalObject(
            object_id=recipe.output_id,
            recipe=recipe,
            initial_payload=None,
            size_bytes=recipe.output_size_bytes,
            owner_pool=owner_pool
        )

        self._objects[recipe.output_id] = obj
        self._hash_index[obj.derivation_hash] = recipe.output_id

        # Update reverse dependency references (children)
        for parent_id in recipe.input_ids:
            self._objects[parent_id].children.add(recipe.output_id)

        return obj

    def _is_ancestor(self, candidate_ancestor: str, current_node: str) -> bool:
        """Helper to recursively detect cycles."""
        if candidate_ancestor == current_node:
            return True
        node = self._objects.get(current_node)
        if not node:
            return False
        for p in node.parents:
            if self._is_ancestor(candidate_ancestor, p):
                return True
        return False

    def get(self, object_id: str) -> Optional[CausalObject]:
        """Retrieves a causal object by ID."""
        return self._objects.get(object_id)

    def lookup_by_derivation_hash(self, derivation_hash: str) -> Optional[CausalObject]:
        """Content-addressable lookup of existing identical derivation."""
        obj_id = self._hash_index.get(derivation_hash)
        if obj_id:
            return self._objects.get(obj_id)
        return None

    def materialize(self, object_id: str) -> bytes:
        """
        Recursively materializes an object and any unmaterialized parents.
        """
        obj = self.get(object_id)
        if not obj:
            raise KeyError(f"Object '{object_id}' not found.")

        if obj.is_materialized:
            return obj.read()

        if obj.is_root:
            raise RuntimeError(f"Root object '{object_id}' is unmaterialized without payload.")

        # Materialize all parents first
        parent_payloads: List[bytes] = []
        for parent_id in obj.recipe.input_ids:
            parent_payload = self.materialize(parent_id)
            parent_payloads.append(parent_payload)

        # Compute output
        computed = obj.recipe.compute(parent_payloads)
        obj._payload = bytearray(computed)
        obj.size_bytes = len(computed)
        obj.content_hash = hashlib.sha256(computed).hexdigest()
        obj.state = MaterializationState.MATERIALIZED
        obj.materialization_count += 1
        return bytes(obj._payload)

    def mutate_root(self, root_id: str, new_payload: bytes) -> Set[str]:
        """
        Updates a root object's data and propagates STALE invalidation
        to all downstream descendants in the causal DAG.
        Returns the set of invalidated descendant IDs.
        """
        root = self.get(root_id)
        if not root:
            raise KeyError(f"Root object '{root_id}' not found.")
        if not root.is_root:
            raise ValueError(f"Object '{root_id}' is not a root object.")

        root.update_root_payload(new_payload)

        invalidated_ids: Set[str] = set()
        self._cascade_stale(root_id, invalidated_ids)
        return invalidated_ids

    def _cascade_stale(self, node_id: str, invalidated_set: Set[str]):
        """Recursively marks all children STALE."""
        node = self.get(node_id)
        if not node:
            return
        for child_id in node.children:
            child = self.get(child_id)
            if child and child.state != MaterializationState.STALE:
                child.mark_stale()
                invalidated_set.add(child_id)
                self._cascade_stale(child_id, invalidated_set)

    def evaporate_object(self, object_id: str) -> int:
        """Evaporates an object, freeing physical memory."""
        obj = self.get(object_id)
        if not obj:
            raise KeyError(f"Object '{object_id}' not found.")
        return obj.evaporate()

    def get_memory_accounting(self) -> Dict[str, Any]:
        """Returns statistics on physical RAM materialized vs virtual causal footprint."""
        materialized_bytes = sum(len(obj._payload) for obj in self._objects.values() if obj.is_materialized)
        virtual_causal_bytes = sum(obj.size_bytes for obj in self._objects.values())
        return {
            "total_objects": len(self._objects),
            "materialized_objects": sum(1 for obj in self._objects.values() if obj.is_materialized),
            "evicted_objects": sum(1 for obj in self._objects.values() if obj.state == MaterializationState.EVICTED),
            "stale_objects": sum(1 for obj in self._objects.values() if obj.state == MaterializationState.STALE),
            "physical_materialized_bytes": materialized_bytes,
            "virtual_causal_bytes": virtual_causal_bytes,
            "memory_saving_ratio": round(virtual_causal_bytes / max(1, materialized_bytes), 2)
        }
