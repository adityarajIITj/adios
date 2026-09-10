"""
kernel/cmf/unified_kernel.py - Master Unified Kernel Subsystem Blueprint (CMF Phase 12)

Integrates:
1. RV32 Instruction / Memory Environment
2. MLFQScheduler (Multilevel Feedback Queue)
3. FluidRAMMesh (Hydrodynamic memory substrate across 6 pools)
4. CMF (Causal Materialization Framework): Store, Cost Model, DAG Engine
5. TCM (Temporal Causal Memory): Anticipatory working set pre-warming
6. CausalMMU: Hardware-level Sv32 address translation with PTE_CAUSAL
7. CMFSecurityGuard: ACLs, quotas, and depth bounds
"""

from typing import Dict, List, Any, Optional, Set, Tuple
import time

from kernel.fluid_ram import (
    FluidRAMMesh, MorphicReversibleSlab,
    PAGE_PINNED, PAGE_TRANSIENT, PAGE_CACHE,
    POOL_USER_APPS, POOL_STREAM_RING, POOL_DYNAMIC_MESH,
    POOL_KERNEL_CORE, POOL_COMPOSITOR_FB, POOL_CHRONOS_DELTA
)
from proc.scheduler import MLFQScheduler
from proc.process import TaskControlBlock, PriorityClass, ProcessState

from kernel.cmf.causal_types import MaterializationState, DerivationRecipe
from kernel.cmf.causal_object import CausalObject
from kernel.cmf.object_store import CausalObjectStore
from kernel.cmf.cost_model import RematerializationCostEngine, CostModelParameters
from kernel.cmf.remat_scheduler import RematerializationScheduler
from kernel.cmf.fluidram_bridge import FluidRAMCMFBridge
from kernel.cmf.hardware_mmu import CausalMMU, CausalPageTableEntry
from kernel.cmf.security_guard import CMFSecurityGuard, ProcessSecurityContext


class AdiOSUnifiedKernel:
    """
    Master unified operating system kernel substrate orchestrating
    computation, physical memory hydrodynamics, and causal derivations.
    """

    def __init__(self, physical_ram_mb: int = 64):
        self.physical_ram_mb = physical_ram_mb
        self.current_tick = 0
        self.boot_time = time.time()

        # 1. Physical Memory Substrate
        self.mesh = FluidRAMMesh(total_ram_mb=physical_ram_mb)

        # 2. Causal Materialization Framework Subsystems
        self.store = CausalObjectStore()
        self.cost_engine = RematerializationCostEngine()
        self.security = CMFSecurityGuard()
        self.bridge = FluidRAMCMFBridge(self.mesh, self.store, self.cost_engine)
        self.mmu = CausalMMU(self.store)

        # 3. Process Management & Scheduler
        self.scheduler = MLFQScheduler()
        self.scheduler.tcm_engine = self.mesh.tcm_engine

    def spawn_process(self, name: str, priority: PriorityClass = PriorityClass.NORMAL, uid: int = 1000) -> TaskControlBlock:
        """Spawns and registers a process in scheduler and security context."""
        proc = TaskControlBlock(name=name, priority=priority)
        self.scheduler.add_process(proc)
        self.security.get_or_create_context(proc.pid, uid=uid)
        return proc

    def allocate_process_causal_memory(
        self,
        proc: TaskControlBlock,
        vpn: int,
        object_id: str,
        initial_data: Optional[bytes] = None,
        recipe: Optional[DerivationRecipe] = None,
        pool_name: str = POOL_USER_APPS
    ) -> CausalPageTableEntry:
        """
        Allocates memory for a process, binding CMF causal object to hardware MMU page table.
        """
        ctx = self.security.get_or_create_context(proc.pid)

        # Security check if registering recipe
        if recipe:
            self.security.validate_recipe_registration(ctx, recipe, parent_depths=[0])

        # Allocate via bridge
        obj = self.bridge.allocate_causal_slab(
            object_id=object_id,
            pool_name=pool_name,
            initial_data=initial_data,
            recipe=recipe
        )

        # Map to hardware MMU
        pte = self.mmu.map_causal_page(vpn=vpn, causal_obj_id=object_id)
        if obj.is_materialized and initial_data is not None:
            # Sync initial physical frame
            self.mmu.physical_frames[self.mmu.next_ppn] = initial_data[:4096]
            pte.ppn = self.mmu.next_ppn
            self.mmu.next_ppn += 1
            pte.set_valid(True)

        # Add to process causal working set
        if not hasattr(proc, "causal_working_set"):
            proc.causal_working_set = []
        if object_id not in proc.causal_working_set:
            proc.causal_working_set.append(object_id)

        return pte

    def step_kernel_tick(self) -> Dict[str, Any]:
        """
        Advances the entire unified operating system by one clock tick.
        Coordinates MLFQ scheduler, TCM contracts, and CMF pre-warming/dissipation.
        """
        self.current_tick += 1

        # 1. Advance process scheduler
        self.scheduler.tick()

        # 2. Advance CMF and FluidRAM bridge
        bridge_report = self.bridge.on_tick(self.current_tick)

        return {
            "tick": self.current_tick,
            "running_process": self.scheduler.current_process.name if self.scheduler.current_process else "IDLE",
            "bridge": bridge_report,
            "mmu_stats": {
                "tlb_hits": self.mmu.tlb_hits,
                "tlb_misses": self.mmu.tlb_misses,
                "causal_faults_handled": self.mmu.causal_faults_handled
            }
        }

    def get_unified_system_telemetry(self) -> Dict[str, Any]:
        """Returns comprehensive publication-grade diagnostic state of all subsystems."""
        accounting = self.store.get_memory_accounting()
        return {
            "uptime_ticks": self.current_tick,
            "physical_ram_mb": self.physical_ram_mb,
            "mesh_used_mb": round(self.mesh.global_used_mb, 2),
            "mesh_pressure": round(self.mesh.global_pressure, 3),
            "active_processes": len(self.scheduler.all_processes),
            "cmf_total_objects": accounting["total_objects"],
            "cmf_materialized_objects": accounting["materialized_objects"],
            "cmf_evicted_objects": accounting["evicted_objects"],
            "cmf_virtual_expansion_ratio": accounting["memory_saving_ratio"],
            "mmu_causal_faults": self.mmu.causal_faults_handled
        }
