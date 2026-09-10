"""
kernel/cmf/remat_scheduler.py - CMF Re-Materialization Scheduler & Policy Engine

Implements:
- Scheduling policies: LAZY, EAGER_PREWARM, SPECULATIVE
- Coordination with TCM pre-warming horizons
- CPU budget enforcement per scheduling cycle
"""

from enum import Enum, auto
from typing import Dict, List, Any, Optional, Set, Tuple
import time

from kernel.cmf.causal_types import MaterializationState
from kernel.cmf.causal_object import CausalObject
from kernel.cmf.object_store import CausalObjectStore
from kernel.cmf.cost_model import RematerializationCostEngine, MaterializationBudget, CostModelParameters


class MaterializationPolicy(Enum):
    LAZY          = "LAZY"           # Only materialize when read is explicitly requested (on-demand page fault)
    EAGER_PREWARM = "EAGER_PREWARM"  # Pre-materialize before thread wakes up (TCM contract coordination)
    SPECULATIVE   = "SPECULATIVE"    # Pre-materialize during CPU idle if memory pressure is low


class RematerializationScheduler:
    """
    Schedules re-materializations across system ticks respecting CPU budget and memory pressure.
    """

    def __init__(
        self,
        store: CausalObjectStore,
        cost_engine: Optional[RematerializationCostEngine] = None,
        default_policy: MaterializationPolicy = MaterializationPolicy.LAZY
    ):
        self.store = store
        self.cost_engine = cost_engine or RematerializationCostEngine()
        self.policy = default_policy
        self.budget = MaterializationBudget(self.cost_engine.params.max_budget_per_quantum_us)

        # Work queue of pending pre-warming contracts: (object_id, target_tick)
        self.prewarm_queue: List[Tuple[str, int]] = []

    def schedule_prewarm(self, object_id: str, target_tick: int):
        """Enqueues an object to be eagerly pre-warmed prior to target_tick."""
        self.prewarm_queue.append((object_id, target_tick))

    def on_tick(self, current_tick: int, system_pressure: float) -> Dict[str, Any]:
        """
        Executes scheduler step at clock tick.
        Refills budget and executes scheduled pre-warming operations if budget allows.
        """
        self.budget.reset()
        materialized_count = 0
        deferred_count = 0
        evaporated_count = 0

        # 1. Check for autonomous evaporation under high pressure
        if system_pressure >= 0.70:
            for obj in list(self.store._objects.values()):
                if self.cost_engine.should_evaporate(obj, system_pressure, current_tick):
                    freed = obj.evaporate()
                    if freed > 0:
                        evaporated_count += 1

        # 2. Process prewarm queue
        remaining_queue: List[Tuple[str, int]] = []
        for obj_id, target_tick in self.prewarm_queue:
            obj = self.store.get(obj_id)
            if not obj or obj.is_materialized:
                continue

            # If target tick is approaching (within 2 ticks)
            if target_tick - current_tick <= 2:
                cost_us = self.cost_engine.calculate_rematerialization_cost_us(obj)
                if self.budget.has_budget(cost_us):
                    t0 = time.perf_counter()
                    self.store.materialize(obj_id)
                    actual_us = (time.perf_counter() - t0) * 1e6
                    self.budget.consume(actual_us)
                    materialized_count += 1
                else:
                    # Defer because CPU budget exhausted this tick
                    deferred_count += 1
                    remaining_queue.append((obj_id, target_tick))
            else:
                remaining_queue.append((obj_id, target_tick))

        self.prewarm_queue = remaining_queue

        return {
            "tick": current_tick,
            "system_pressure": system_pressure,
            "budget_consumed_us": round(self.budget.consumed_us, 2),
            "budget_limit_us": self.budget.budget_limit_us,
            "prewarmed_objects": materialized_count,
            "deferred_objects": deferred_count,
            "evaporated_objects": evaporated_count
        }
