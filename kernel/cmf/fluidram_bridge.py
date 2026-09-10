"""
kernel/cmf/fluidram_bridge.py - Subsystem Integration: CMF + FluidRAM + TCM + Scheduler

Directly couples the Causal Materialization Framework with:
1. FluidRAMMesh: physical slab allocation, pool tracking, and causal surface tension dissipation
2. TCM (Temporal Causal Memory): predictive pre-warming of thread working sets before wakeup
3. MLFQScheduler: process dispatch and zero-stall hot wakeups
"""

from typing import Dict, List, Any, Optional, Set, Tuple
import time

from kernel.fluid_ram import (
    FluidRAMMesh, MorphicReversibleSlab, PhysicalMemorySlab,
    PAGE_PINNED, PAGE_TRANSIENT, PAGE_CACHE,
    POOL_USER_APPS, POOL_STREAM_RING, POOL_DYNAMIC_MESH,
    POOL_KERNEL_CORE, POOL_COMPOSITOR_FB, POOL_CHRONOS_DELTA
)
from kernel.cmf.causal_types import MaterializationState, DerivationRecipe
from kernel.cmf.causal_object import CausalObject
from kernel.cmf.object_store import CausalObjectStore
from kernel.cmf.cost_model import RematerializationCostEngine, CostModelParameters
from kernel.cmf.remat_scheduler import RematerializationScheduler
from proc.process import TaskControlBlock


class FluidRAMCMFBridge:
    """
    Unified architectural bridge integrating FluidRAM physical slabs with CMF causal semantics.
    """

    def __init__(
        self,
        mesh: Optional[FluidRAMMesh] = None,
        store: Optional[CausalObjectStore] = None,
        cost_engine: Optional[RematerializationCostEngine] = None
    ):
        self.mesh = mesh or FluidRAMMesh(total_ram_mb=64)
        self.store = store or CausalObjectStore()
        self.cost_engine = cost_engine or RematerializationCostEngine()
        self.scheduler = RematerializationScheduler(self.store, self.cost_engine)

        # Mapping between CausalObjectID and physical FluidRAM slab_id
        self.object_to_slab: Dict[str, int] = {}
        self.slab_to_object: Dict[int, str] = {}

    def allocate_causal_slab(
        self,
        object_id: str,
        pool_name: str = POOL_USER_APPS,
        initial_data: Optional[bytes] = None,
        recipe: Optional[DerivationRecipe] = None
    ) -> CausalObject:
        """
        Allocates a physical FluidRAM slab and binds it to a CausalObject in CMF.
        """
        # Register in CMF store
        if recipe:
            obj = self.store.register_derivation(recipe, owner_pool=pool_name)
            if initial_data is not None:
                obj._payload = bytearray(initial_data)
                obj.state = MaterializationState.MATERIALIZED
        else:
            payload = initial_data or b"\x00" * 4096
            obj = self.store.register_root(object_id, payload, owner_pool=pool_name)

        if initial_data is not None:
            slab = self.mesh.allocate_physical_slab(
                pool_name=pool_name,
                size_bytes=len(initial_data),
                classification=PAGE_TRANSIENT if not obj.is_root else PAGE_PINNED,
                data=initial_data
            )
            obj.link_slab(slab.slab_id)
            self.object_to_slab[object_id] = slab.slab_id
            self.slab_to_object[slab.slab_id] = object_id

        return obj

    def materialize_causal_slab(self, object_id: str) -> bytes:
        """
        Materializes a CausalObject and synchronizes its bytes into a physical FluidRAM slab.
        """
        data = self.store.materialize(object_id)
        obj = self.store.get(object_id)

        # Allocate or update slab in FluidRAM mesh
        existing_slab = self.mesh.get_slab_by_id(obj.slab_id) if obj.slab_id else None
        if existing_slab is None:
            slab = self.mesh.allocate_physical_slab(
                pool_name=obj.owner_pool,
                size_bytes=len(data),
                classification=PAGE_TRANSIENT if not obj.is_root else PAGE_PINNED,
                data=data
            )
            obj.link_slab(slab.slab_id)
            self.object_to_slab[object_id] = slab.slab_id
            self.slab_to_object[slab.slab_id] = object_id
        else:
            # Update existing slab data
            existing_slab.write(0, data)

        return data

    def dissipate_causal_surface_tension(self) -> Dict[str, Any]:
        """
        Intelligent hydrodynamic dissipation:
        Rather than blind LRU dropping, FluidRAM consults CMF cost models:
        - Priority 1: Evaporate objects with low re-materialization cost (< 100 us)
        - Priority 2: Evaporate objects with high idle ticks
        - Never evaporate root or non-derivable pinned objects unless explicitly forced
        """
        pressure_before = self.mesh.global_pressure
        freed_bytes = 0
        evaporated_objects = []

        # Sort candidate objects by re-materialization cost (cheapest first)
        candidates: List[Tuple[float, CausalObject]] = []
        for obj in self.store._objects.values():
            if obj.is_materialized and not obj.is_root:
                cost_us = self.cost_engine.calculate_rematerialization_cost_us(obj)
                candidates.append((cost_us, obj))

        candidates.sort(key=lambda x: x[0])  # Cheapest to re-materialize first

        for cost_us, obj in candidates:
            if self.mesh.global_pressure < 0.60:
                break  # Pressure relieved!

            # Free slab in FluidRAM mesh
            if obj.slab_id:
                slab = self.mesh.get_slab_by_id(obj.slab_id)
                if slab:
                    freed_bytes += slab.size_bytes
                self.mesh.free_physical_slab(obj.slab_id)

            # Evaporate in CMF (preserving recipe)
            obj.evaporate()
            evaporated_objects.append(obj.object_id)

        # Also trigger native mesh dissipation for any untracked transient slabs
        native_freed_mb = self.mesh.dissipate_surface_tension()
        freed_bytes += int(native_freed_mb * 1024 * 1024)

        return {
            "pressure_before": pressure_before,
            "pressure_after": self.mesh.global_pressure,
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024.0 * 1024.0), 2),
            "evaporated_causal_objects": evaporated_objects
        }

    def register_process_working_set_for_prewarm(self, process: TaskControlBlock, target_tick: int):
        """
        Connects a process's causal working set with CMF and TCM for zero-stall hot wakeups.
        """
        for obj_id in getattr(process, "causal_working_set", []):
            if isinstance(obj_id, str):
                self.scheduler.schedule_prewarm(obj_id, target_tick)

    def on_tick(self, current_tick: int) -> Dict[str, Any]:
        """Integrated tick handler updating both FluidRAM and CMF."""
        pressure = self.mesh.global_pressure
        cmf_report = self.scheduler.on_tick(current_tick, pressure)
        return {
            "tick": current_tick,
            "mesh_surface_tension": pressure,
            "cmf_scheduler": cmf_report
        }
