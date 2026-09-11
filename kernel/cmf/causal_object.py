"""
kernel/cmf/causal_object.py - Comprehensive Causal Object Model

Implements the formal semantics of a Causal Memory Object:
- Immutable content-addressable identity: H(f, H(A), H(B), theta)
- Versioning and epoch tracking
- Parent/child dependency graphs
- Slabs linkage to FluidRAM
- Ephemeral lifecycle and automatic invalidation cascades
"""

import hashlib
import time
from typing import Dict, List, Any, Optional, Set, Callable
from kernel.cmf.causal_types import MaterializationState, PurityLevel, DerivationRecipe


def compute_derivation_hash(transform_name: str, input_hashes: List[str], parameters: Dict[str, Any]) -> str:
    """
    Computes deterministic SHA-256 derivation hash:
        H(transform_name || sorted(input_hashes) || parameters)
    """
    hasher = hashlib.sha256()
    hasher.update(transform_name.encode("utf-8"))
    for h in sorted(input_hashes):
        hasher.update(h.encode("utf-8"))
    # Deterministic parameter serialization
    param_str = str(sorted(parameters.items()))
    hasher.update(param_str.encode("utf-8"))
    return hasher.hexdigest()


class CausalObject:
    """
    First-class Causal Memory Object in the AdiOS kernel.
    """

    def __init__(
        self,
        object_id: str,
        recipe: Optional[DerivationRecipe] = None,
        initial_payload: Optional[bytes] = None,
        size_bytes: int = 4096,
        owner_pool: str = "POOL_USER_APPS",
        version: int = 1
    ):
        self.object_id = object_id
        self.recipe = recipe
        self.size_bytes = len(initial_payload) if initial_payload is not None else size_bytes
        self.owner_pool = owner_pool
        self.version = version

        # Causal DAG references
        self.parents: Set[str] = set(recipe.input_ids) if recipe else set()
        self.children: Set[str] = set()

        # Physical residency
        self._payload: Optional[bytearray] = bytearray(initial_payload) if initial_payload is not None else None
        self.slab_id: Optional[int] = None
        self.state = MaterializationState.MATERIALIZED if initial_payload is not None else MaterializationState.UNMATERIALIZED

        # Content/Derivation Hash
        if initial_payload is not None:
            self.content_hash = hashlib.sha256(initial_payload).hexdigest()
            self.derivation_hash = self.content_hash
        elif recipe:
            self.content_hash = None
            self.derivation_hash = compute_derivation_hash(
                recipe.transform_name,
                recipe.input_ids,
                recipe.parameters
            )
        else:
            self.content_hash = None
            self.derivation_hash = hashlib.sha256(object_id.encode("utf-8")).hexdigest()

        # Telemetry
        self.access_count = 0
        self.last_accessed_tick = 0
        self.materialization_count = 1 if self._payload is not None else 0
        self.eviction_count = 0

    @property
    def is_root(self) -> bool:
        return self.recipe is None

    @property
    def is_materialized(self) -> bool:
        return self.state == MaterializationState.MATERIALIZED and self._payload is not None

    def read(self) -> bytes:
        """Reads the resident memory, asserting residency and state."""
        if not self.is_materialized:
            raise MemoryError(
                f"Cannot read non-materialized CausalObject '{self.object_id}' (State: {self.state.value})"
            )
        self.access_count += 1
        return bytes(self._payload)

    def link_slab(self, slab_id: int):
        """Links this causal object to an active FluidRAM physical slab."""
        self.slab_id = slab_id

    def unlink_slab(self):
        """Unlinks the object from its physical slab."""
        self.slab_id = None

    def evaporate(self) -> int:
        """
        Evaporates physical memory bytes while preserving the DerivationRecipe.
        
        Transitions object state from MATERIALIZED to EVICTED and unlinks any
        backing FluidRAM physical slab, returning the total bytes reclaimed.
        Subsequent read attempts trigger on-demand re-materialization.
        """
        if self.is_root:
            raise PermissionError(f"Root causal object '{self.object_id}' cannot be evaporated without backing store.")

        if not self.is_materialized:
            return 0

        freed = len(self._payload)
        self._payload = None
        self.unlink_slab()
        self.state = MaterializationState.EVICTED
        self.eviction_count += 1
        return freed

    def mark_stale(self):
        """Marks object stale when an upstream dependency is mutated."""
        self.state = MaterializationState.STALE
        self._payload = None
        self.unlink_slab()

    def update_root_payload(self, new_payload: bytes):
        """Updates the payload of a root object, incrementing version."""
        if not self.is_root:
            raise PermissionError(f"Cannot directly write payload to derived object '{self.object_id}'.")
        self._payload = bytearray(new_payload)
        self.size_bytes = len(new_payload)
        self.content_hash = hashlib.sha256(new_payload).hexdigest()
        self.derivation_hash = self.content_hash
        self.version += 1
        self.state = MaterializationState.MATERIALIZED
