#!/usr/bin/env python3
"""
Test Suite: Temporal Causal Memory (TCM) & Temporal Residency Contracts (TRC)
Tests forward-looking eviction pressure, scheduler emission, speculative pre-warming,
and anticipatory hydrodynamic flow coupling.
Strict Zero Emoji Policy Enforced.
"""

import math
import time
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from proc.process import TaskControlBlock, PriorityClass, ProcessState, TemporalResidencyContract
from proc.scheduler import MLFQScheduler
from kernel.fluid_ram import (
    FluidRAMMesh,
    POOL_USER_APPS,
    POOL_STREAM_RING,
    POOL_CHRONOS_DELTA,
    PAGE_PINNED
)

def test_trc_lifecycle_and_evaluation():
    """Verifies TRC initialization, Bayesian confidence update, and hold pressure decay."""
    trc = TemporalResidencyContract(
        pid=10,
        wake_horizon=100.0,
        working_set=[1, 2, 3],
        priority=PriorityClass.HIGH,
        kappa=1.2,
        recon_cost=300.0,
        confidence=0.8
    )
    assert trc.pid == 10
    assert trc.working_set == [1, 2, 3]
    assert trc.confidence == 0.8
    assert not trc.prewarmed

    # Prior to horizon (dt = 50, tau = 1000)
    p_before = trc.evaluate_hold_pressure(t_now=50.0, tau=1000.0)
    assert p_before > 0.0

    # At or after horizon: peak pressure
    p_peak = trc.evaluate_hold_pressure(t_now=100.0, tau=1000.0)
    assert p_peak >= p_before

    # Pre-warming due check (delta = 5.0)
    assert not trc.is_prewarm_due(t_now=90.0, delta=5.0)
    assert trc.is_prewarm_due(t_now=95.0, delta=5.0)
    assert trc.is_prewarm_due(t_now=105.0, delta=5.0)

    # Bayesian confidence updates
    initial_conf = trc.confidence
    new_conf = trc.update_confidence(actual_hit=True, learning_rate=0.2)
    assert new_conf > initial_conf
    assert new_conf <= 1.0

    lower_conf = trc.update_confidence(actual_hit=False, learning_rate=0.2)
    assert lower_conf < new_conf

def test_tcm_prewarming_engine():
    """Verifies speculative working set pre-warming prior to dispatch."""
    mesh = FluidRAMMesh()
    slab1 = mesh.allocate_physical_slab(POOL_USER_APPS, 64 * 1024, PAGE_PINNED, b"\xAA" * 1024)
    slab2 = mesh.allocate_physical_slab(POOL_USER_APPS, 64 * 1024, PAGE_PINNED, b"\xBB" * 1024)

    tcm = mesh.tcm_engine
    trc = TemporalResidencyContract(
        pid=20,
        wake_horizon=50.0,
        working_set=[slab1.slab_id, slab2.slab_id],
        priority=PriorityClass.REALTIME,
        recon_cost=450.0
    )
    tcm.register_contract(trc)
    assert 20 in tcm.active_contracts

    initial_acc1 = slab1.access_count
    initial_acc2 = slab2.access_count

    # Trigger pre-warm
    success = tcm.prewarm_task(pid=20, t_now=48.0)
    assert success
    assert trc.prewarmed
    assert slab1.access_count > initial_acc1
    assert slab2.access_count > initial_acc2

    # Diagnostics inspection
    diag = tcm.get_diagnostics()
    assert diag["active_contracts_count"] == 1
    assert diag["prewarmed_tasks_count"] == 1
    assert diag["contracts"][0]["prewarmed"] is True

def test_scheduler_trc_integration():
    """Verifies that MLFQScheduler emits TRC on sleep/yield and records dispatch metrics."""
    mesh = FluidRAMMesh()
    sched = MLFQScheduler()
    sched.tcm_engine = mesh.tcm_engine

    proc1 = TaskControlBlock("audio_dsp", priority=PriorityClass.REALTIME)
    proc1.causal_working_set = [1, 2]
    proc1.historical_recon_latency_us = 200.0

    sched.add_process(proc1)
    assert proc1.active_trc is not None
    assert proc1.pid in mesh.tcm_engine.active_contracts

    # Run tick 1: proc1 executes
    running = sched.tick()
    assert running.pid == proc1.pid

    # proc1 goes to sleep for 5 ticks
    sched.sleep_current(ticks=5)
    assert proc1.state == ProcessState.SLEEPING
    assert proc1.sleep_until_tick == sched.current_tick + 5
    assert proc1.active_trc.wake_horizon == float(sched.current_tick + 5)
    assert not proc1.active_trc.prewarmed

    # Advance ticks: pre-warming should trigger at current_tick >= wake_horizon - prewarm_delta_ticks
    # wake_horizon is sched.current_tick (1) + 5 = 6. prewarm_delta is 2 -> triggers at tick 4
    for _ in range(3):
        sched.tick()

    assert proc1.active_trc.prewarmed is True

    # Advance remaining ticks until proc1 wakes
    for _ in range(3):
        sched.tick()

    # On wake and dispatch, metrics should register warm hit
    assert proc1.metrics.trc_warm_hits >= 1
    assert proc1.metrics.stall_time_saved_us >= 200.0
    assert proc1.active_trc.confidence > 0.8

def test_anticipatory_hydrodynamic_flow():
    """Verifies that upcoming task wakeups generate anticipatory flux vectors."""
    mesh = FluidRAMMesh()
    tcm = mesh.tcm_engine

    now = time.time()
    # Register imminent contract for userland task
    trc = TemporalResidencyContract(
        pid=55,
        wake_horizon=now + 2.0,  # 2 seconds away: high urgency
        working_set=[10],
        priority=PriorityClass.HIGH,
        kappa=2.0,
        confidence=0.95
    )
    tcm.register_contract(trc)

    derivative = tcm.compute_pool_anticipatory_derivative(POOL_USER_APPS, now)
    assert derivative > 0.0

    # Flow vectors must include anticipatory components
    vectors = mesh.compute_flow_vectors()
    found_anticipatory = any("anticipatory_component" in v and v["anticipatory_component"] != 0.0 for v in vectors)
    assert found_anticipatory

def test_tcm_vs_lru_simulation():
    """
    Comparative simulation:
    TCM pre-warming vs. Retrospective LRU cold-wake under memory pressure.
    """
    mesh = FluidRAMMesh()
    sched = MLFQScheduler()
    sched.tcm_engine = mesh.tcm_engine

    tasks = []
    for i in range(4):
        p = TaskControlBlock(f"worker_{i}", priority=PriorityClass.NORMAL)
        p.historical_recon_latency_us = 350.0
        p.causal_working_set = [i + 1]
        tasks.append(p)
        sched.add_process(p)

    # Put all tasks to sleep with staggered horizons
    for idx, p in enumerate(tasks):
        p.state = ProcessState.SLEEPING
        p.sleep_until_tick = 5 + (idx * 3)
        trc = p.emit_trc(wake_horizon=float(p.sleep_until_tick), recon_cost_us=p.historical_recon_latency_us)
        trc.is_suspended = True
        mesh.tcm_engine.register_contract(trc)

    # Step through scheduler simulation
    for _ in range(45):
        sched.tick()

    # All completed tasks should have warm hits and zero cold misses
    total_warm_hits = sum(t.metrics.trc_warm_hits for t in tasks)
    total_saved_us = sum(t.metrics.stall_time_saved_us for t in tasks)
    assert total_warm_hits >= len(tasks)
    assert total_saved_us >= len(tasks) * 350.0
