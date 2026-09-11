"""
kernel/cmf/causal_types.py - Core Types & Primitives for Causal Materialization Framework (CMF)

Formalizes the fundamental missing primitive in OS memory architecture:
    C = f(A, B, ...)
where derivation is a first-class kernel citizen, managed independently of the
producer process lifetime, with explicit re-materialization cost accounting,
purity classification, and state lifecycle.
"""

from enum import Enum, auto
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
import hashlib
import time


class MaterializationState(Enum):
    """Lifecycle states of a Causal Memory Object."""
    UNMATERIALIZED = "UNMATERIALIZED"  # Recipe registered, no physical RAM allocated
    MATERIALIZING  = "MATERIALIZING"   # Computation in progress
    MATERIALIZED   = "MATERIALIZED"    # Resident bytes in physical RAM/slab
    EVICTED        = "EVICTED"         # Evaporated under memory pressure; recipe preserved
    STALE          = "STALE"           # Upstream dependency mutated; requires re-derivation
    INVALIDATED    = "INVALIDATED"     # Explicitly deleted or marked permanently invalid


class PurityLevel(Enum):
    """Purity classification for derivation functions."""
    PURE_DETERMINISTIC = "PURE_DETERMINISTIC"  # Output is strict deterministic function of inputs; safe to recompute anywhere
    BOUNDED_IO         = "BOUNDED_IO"         # Deterministic within fixed I/O snapshot (e.g. read immutable block)
    NON_DETERMINISTIC  = "NON_DETERMINISTIC"  # Uses RNG, clock, or unmonitored syscall; CANNOT be safely recomputed without journal


class DerivationRecipe:
    """
    First-class specification of how a causal memory object is derived:
        Output = f(Inputs, Parameters)
    
    Persists independently of the producer process.
    """

    def __init__(
        self,
        output_id: str,
        input_ids: List[str],
        transform: Callable[..., bytes],
        transform_name: str,
        purity: PurityLevel = PurityLevel.PURE_DETERMINISTIC,
        estimated_compute_us: float = 100.0,
        output_size_bytes: int = 4096,
        producer_pid: Optional[int] = None,
        is_reversible: bool = False,
        reverse_transform: Optional[Callable[..., bytes]] = None,
        parameters: Optional[Dict[str, Any]] = None,
        validation_hash: Optional[str] = None
    ):
        self.output_id = output_id
        self.input_ids = list(input_ids)
        self.transform = transform
        self.transform_name = transform_name
        self.purity = purity
        self.estimated_compute_us = float(estimated_compute_us)
        self.output_size_bytes = int(output_size_bytes)
        self.producer_pid = producer_pid
        self.is_reversible = is_reversible
        self.reverse_transform = reverse_transform
        self.parameters = dict(parameters) if parameters else {}
        self.validation_hash = validation_hash
        self.creation_timestamp = time.time()
        self.execution_count = 0
        self.total_compute_time_us = 0.0

    def compute(self, input_payloads: List[bytes]) -> bytes:
        """
        Executes the transform on given input payloads and updates latency telemetry.
        
        Mathematical latency tracking applies an exponential moving average (EMA):
            EMA_t = 0.7 * EMA_{t-1} + 0.3 * elapsed_t
        
        If validation_hash is configured, output data integrity is audited via SHA-256.
        """
        t0 = time.perf_counter()
        result = self.transform(input_payloads, self.parameters)
        elapsed_us = (time.perf_counter() - t0) * 1e6

        self.execution_count += 1
        self.total_compute_time_us += elapsed_us
        # Exponential moving average of actual compute time
        self.estimated_compute_us = (0.7 * self.estimated_compute_us) + (0.3 * elapsed_us)

        # Hash validation if set
        if self.validation_hash:
            actual_hash = hashlib.sha256(result).hexdigest()
            if actual_hash != self.validation_hash:
                raise ValueError(
                    f"CMF Validation Failure for {self.output_id}: "
                    f"expected {self.validation_hash[:12]}..., got {actual_hash[:12]}..."
                )

        return result


class CausalMemoryObject:
    """
    A memory object whose presence in RAM is elastic and managed causally.
    If evicted under memory pressure, it can be re-materialized on-demand
    via its DerivationRecipe.
    """

    def __init__(
        self,
        object_id: str,
        recipe: Optional[DerivationRecipe] = None,
        initial_bytes: Optional[bytes] = None,
        size_bytes: int = 4096,
        owner_pool: str = "POOL_USER_APPS"
    ):
        self.object_id = object_id
        self.recipe = recipe
        self.size_bytes = size_bytes
        self.owner_pool = owner_pool

        # Root inputs have no recipe (they are ground-truth data)
        self.is_root = (recipe is None)

        if initial_bytes is not None:
            self._bytes: Optional[bytearray] = bytearray(initial_bytes)
            self.state = MaterializationState.MATERIALIZED
            self.size_bytes = len(initial_bytes)
        else:
            self._bytes = None
            self.state = MaterializationState.UNMATERIALIZED

        self.access_count = 0
        self.last_accessed_tick = 0
        self.materialization_count = 1 if self._bytes is not None else 0
        self.eviction_count = 0

    @property
    def is_materialized(self) -> bool:
        return self.state == MaterializationState.MATERIALIZED and self._bytes is not None

    def read(self) -> bytes:
        """Reads the resident bytes, asserting residency."""
        if not self.is_materialized:
            raise MemoryError(
                f"Object {self.object_id} is in state {self.state.value}. "
                "Must be materialized prior to reading."
            )
        self.access_count += 1
        return bytes(self._bytes)

    def evaporate(self) -> int:
        """
        Evaporates the physical bytes from RAM, transitioning to EVICTED.
        Root objects cannot be evaporated unless explicitly managed by backing store.
        Returns bytes freed.
        """
        if self.is_root:
            raise PermissionError(f"Cannot evaporate root causal object {self.object_id} without external backing store.")

        if not self.is_materialized:
            return 0

        freed_bytes = len(self._bytes)
        self._bytes = None
        self.state = MaterializationState.EVICTED
        self.eviction_count += 1
        return freed_bytes

    def materialize(self, input_objects: Optional[List['CausalMemoryObject']] = None) -> bytes:
        """
        Materializes the object using its DerivationRecipe.
        If already materialized, returns resident bytes.
        """
        if self.is_materialized:
            self.access_count += 1
            return bytes(self._bytes)

        if self.is_root:
            raise RuntimeError(f"Cannot re-materialize root object {self.object_id} without provided raw payload.")

        if not self.recipe:
            raise RuntimeError(f"Object {self.object_id} has no derivation recipe.")

        # Gather inputs
        input_payloads: List[bytes] = []
        if input_objects:
            for inp in input_objects:
                if not inp.is_materialized:
                    inp.materialize()
                input_payloads.append(inp.read())

        self.state = MaterializationState.MATERIALIZING
        computed_bytes = self.recipe.compute(input_payloads)
        self._bytes = bytearray(computed_bytes)
        self.size_bytes = len(self._bytes)
        self.state = MaterializationState.MATERIALIZED
        self.materialization_count += 1
        self.access_count += 1
        return bytes(self._bytes)

    def calculate_rematerialization_cost_us(self, host_mem_bus_gb_s: float = 6.0) -> float:
        """
        Calculates the estimated latency cost (in microseconds) to recreate this object:
            Cost = T_compute(f) + T_read(inputs)
        """
        if self.is_root:
            return float('inf')  # Cannot be recreated purely from computation

        recipe_cost = self.recipe.estimated_compute_us if self.recipe else 0.0

        # Memory bus read overhead for inputs: (sum of input sizes) / bus_speed
        input_size_total = sum(self.recipe.output_size_bytes for _ in self.recipe.input_ids) if self.recipe else 0
        bus_transfer_us = (input_size_total / (host_mem_bus_gb_s * 1e9)) * 1e6

        return round(recipe_cost + bus_transfer_us, 2)
