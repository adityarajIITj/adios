"""
kernel/cmf/cost_model.py - CMF Re-Materialization Engine & Cost Model

Implements the formal economic and physical cost framework:
- Remat cost: Cost = T_exec + (Sum Input Bytes / Bus Bandwidth)
- Retention penalty: Penalty = Size * Surface_Tension_Pressure * Age_Penalty
- Eviction decision engine: should_evaporate(obj, pressure)
- Materialization budget allocator: prevents CPU starvation during re-derivations
"""

import time
from typing import Dict, List, Any, Optional
from kernel.cmf.causal_object import CausalObject


class CostModelParameters:
    """Hardware and operating system cost constants."""

    def __init__(
        self,
        host_mem_bus_gb_s: float = 6.0,
        baseline_swap_stall_us: float = 15000.0,  # 15 ms standard NVMe/SSD swap page fault stall
        cpu_time_quantum_us: float = 1000.0,      # 1 ms scheduler quantum
        max_remat_budget_ratio: float = 0.25      # Max 25% of quantum spent on re-materialization
    ):
        self.host_mem_bus_gb_s = host_mem_bus_gb_s
        self.baseline_swap_stall_us = baseline_swap_stall_us
        self.cpu_time_quantum_us = cpu_time_quantum_us
        self.max_remat_budget_ratio = max_remat_budget_ratio

    @property
    def max_budget_per_quantum_us(self) -> float:
        return self.cpu_time_quantum_us * self.max_remat_budget_ratio


class MaterializationBudget:
    """Tracks and caps CPU budget spent on re-materializing objects per scheduling cycle."""

    def __init__(self, budget_limit_us: float = 250.0):
        self.budget_limit_us = budget_limit_us
        self.consumed_us = 0.0

    def has_budget(self, estimated_cost_us: float) -> bool:
        return (self.consumed_us + estimated_cost_us) <= self.budget_limit_us

    def consume(self, cost_us: float):
        self.consumed_us += cost_us

    def reset(self):
        self.consumed_us = 0.0


class RematerializationCostEngine:
    """
    Evaluates re-materialization economics to balance DRAM occupancy
    against CPU recomputation overhead.
    """

    def __init__(self, params: Optional[CostModelParameters] = None):
        self.params = params or CostModelParameters()

    def calculate_rematerialization_cost_us(self, obj: CausalObject, input_sizes: Optional[List[int]] = None) -> float:
        """
        Calculates T_remat(obj) in microseconds:
            Cost = T_compute_ema + (Input Bytes / Mem Bus Bandwidth)
        """
        if obj.is_root:
            return float('inf')  # Root objects cannot be computed

        compute_us = obj.recipe.estimated_compute_us if obj.recipe else 10.0

        # Memory bus read transfer time for input payloads
        if input_sizes is None and obj.recipe:
            input_sizes = [obj.recipe.output_size_bytes for _ in obj.recipe.input_ids]
        total_input_bytes = sum(input_sizes) if input_sizes else 0

        bus_transfer_us = (total_input_bytes / (self.params.host_mem_bus_gb_s * 1e9)) * 1e6
        return round(compute_us + bus_transfer_us, 2)

    def calculate_retention_penalty(self, obj: CausalObject, surface_tension_pressure: float, current_tick: int) -> float:
        """
        Calculates penalty for keeping object resident in DRAM:
            Penalty = Size_KB * Pressure * (1.0 + Idle_Ticks / 100)
        """
        if not obj.is_materialized:
            return 0.0

        size_kb = obj.size_bytes / 1024.0
        idle_ticks = max(0, current_tick - obj.last_accessed_tick)
        age_multiplier = 1.0 + (idle_ticks / 100.0)

        # Scale non-linearly with pressure
        pressure_factor = max(0.1, surface_tension_pressure ** 1.5)
        return round(size_kb * pressure_factor * age_multiplier, 3)

    def should_evaporate(
        self,
        obj: CausalObject,
        surface_tension_pressure: float,
        current_tick: int,
        pressure_evict_threshold: float = 0.70
    ) -> bool:
        """
        Decision rule: Should this object be evaporated to relieve memory pressure?
        Returns True if:
        1. Object is not a root object.
        2. Pressure is above threshold.
        3. Re-materialization cost is significantly cheaper than standard disk swap stalls.
        """
        if obj.is_root:
            return False

        if not obj.is_materialized:
            return False

        if surface_tension_pressure < pressure_evict_threshold:
            return False

        remat_cost_us = self.calculate_rematerialization_cost_us(obj)

        # Evaporate if recomputing takes less than 50% of classical swap stall time
        if remat_cost_us < (self.params.baseline_swap_stall_us * 0.5):
            return True

        # Even for heavier compute, if pressure is near critical (>= 0.95), evaporate non-hot data
        if surface_tension_pressure >= 0.95:
            idle_ticks = max(0, current_tick - obj.last_accessed_tick)
            if idle_ticks > 10:
                return True

        return False
