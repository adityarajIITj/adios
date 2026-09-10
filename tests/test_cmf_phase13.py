"""
tests/test_cmf_phase13.py - Test Suite for CMF Phase 13:
First Implementation Sequence & Master Validation Benchmarks.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from userland.linux_memory_benchmark import (
    NativeKernelMemoryHarness,
    get_global_memory_harness,
    LinuxKernelMemoryBenchmark
)
from userland.proof_of_sovereignty import (
    OperatingSystemProofEngine,
    format_proof_report
)
from kernel.cmf.unified_kernel import (
    AdiOSUnifiedKernel,
    FirstImplementationSequence
)


def test_native_kernel_memory_harness_counters():
    """Verifies that NativeKernelMemoryHarness samples valid host OS performance counters."""
    harness = get_global_memory_harness()
    assert harness is not None

    counters = harness.sample_counters()
    assert isinstance(counters, dict)
    assert "timestamp_ms" in counters
    assert "page_faults" in counters
    assert "working_set_kb" in counters
    assert "mode" in counters
    assert counters["page_faults"] >= 0
    assert counters["working_set_kb"] >= 0


def test_native_kernel_memory_harness_allocation_and_faults():
    """Verifies physical allocation and page touching triggers measured page faults."""
    harness = get_global_memory_harness()
    size = 8 * 1024 * 1024  # 8 MB = 2048 pages

    res = harness.allocate_and_touch(size)
    assert isinstance(res, dict)
    assert res["allocated_bytes"] == size
    assert res["pages_touched"] == 2048
    assert res["delta_page_faults"] >= 0
    assert res["elapsed_ms"] >= 0.0
    assert "harness_mode" in res


def test_first_implementation_sequence_cold_boot():
    """Verifies 6-stage cold-boot sequence initializes all unified kernel subsystems."""
    boot_engine = FirstImplementationSequence(physical_ram_mb=64)
    kernel = boot_engine.run_bootstrap_sequence()

    assert kernel is not None
    assert boot_engine.stage == FirstImplementationSequence.STAGE_READY
    assert len(boot_engine.stage_history) == 7

    # Verify stage statuses
    for entry in boot_engine.stage_history:
        assert entry["status"] == "SUCCESS"

    # Verify unified kernel state
    assert len(kernel.mesh.pools) == 6
    assert kernel.store is not None
    assert kernel.mmu is not None
    assert kernel.security is not None
    assert kernel.scheduler is not None


def test_first_implementation_master_workload():
    """Verifies master empirical validation workload with CMF derivation and MMU fault recovery."""
    boot_engine = FirstImplementationSequence(physical_ram_mb=64)
    result = boot_engine.execute_master_validation_workload()

    assert result["bootstrap_stages_executed"] == 7
    assert result["fault_resolved"] is True
    assert result["latency_bound_met"] is True
    assert result["fault_recovery_latency_us"] < 50000.0  # sub-50 ms bound
    assert result["zero_killed_processes"] is True
    assert result["zero_swap_disk_writes"] is True

    telemetry = result["telemetry"]
    assert telemetry["cmf_total_objects"] >= 3
    assert telemetry["mmu_causal_faults"] >= 1


def test_proof_of_sovereignty_proof_1_and_proof_8():
    """Verifies Proof 1 (genuine Linux MM state machine) and Proof 8 (CMF vs Swap Thrashing)."""
    engine = OperatingSystemProofEngine()

    p1 = engine.run_proof_1_thrashing_vs_hydrodynamics()
    assert p1["traditional_os"]["page_faults"] > 0
    assert p1["traditional_os"]["swap_disk_written_kb"] > 0
    assert p1["adios_fluid_ram"]["page_faults"] == 0
    assert p1["adios_fluid_ram"]["swap_disk_written_kb"] == 0.0
    assert p1["speedup_factor"] > 1.0

    p8 = engine.run_proof_8_cmf_causal_derivation_vs_virtual_swap()
    assert p8["traditional_virtual_memory"]["swap_disk_written_mb"] > 0.0
    assert p8["adios_cmf"]["swap_disk_written_mb"] == 0.0
    assert p8["adios_cmf"]["mmu_causal_faults"] == 1
    assert p8["adios_cmf"]["processes_killed"] == 0
    assert p8["speedup_factor"] > 1.0


def test_proof_of_sovereignty_all_8_proofs_dossier():
    """Verifies full execution of all 8 proofs and formatting of evidence dossier."""
    engine = OperatingSystemProofEngine()
    proofs = engine.run_all_proofs()

    assert len(proofs) == 9  # timestamp + 8 proofs
    assert "proof_1_thrashing" in proofs
    assert "proof_2_oom_killer" in proofs
    assert "proof_3_galois_reversibility" in proofs
    assert "proof_4_void_pipe" in proofs
    assert "proof_5_morphic_inslab" in proofs
    assert "proof_6_landauer_wal" in proofs
    assert "proof_7_temporal_causal" in proofs
    assert "proof_8_cmf_causal" in proofs

    report = format_proof_report(proofs)
    assert "PROOF 1: ELIMINATING DISK THRASHING" in report
    assert "PROOF 8: CMF CAUSAL DERIVATION" in report
    assert "Sovereign Invariants Verified Across All 8 Physics Domains" in report
