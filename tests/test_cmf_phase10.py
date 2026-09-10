"""
tests/test_cmf_phase10.py - Verification Suite for CMF Phase 10 (Comparative Architectural Analysis)

Tests:
1. Comparative modeling across 4 major systems paradigms:
   - Linux Monolithic VM
   - Spark / Ray Userland RDDs
   - Mach External Pager
   - AdiOS CMF + FluidRAM
2. Quantifying CMF speedups vs disk swap latency (>1,000x faster)
3. Zero process murders in CMF vs positive SIGKILL count in Linux
4. Virtual capacity expansion ratio verification
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from kernel.cmf import (
    ArchitectureParadigm,
    ComparativeArchitectureEngine
)


class TestCMFPhase10(unittest.TestCase):
    """Verifies Phase 10: Comparative Architectural Analysis."""

    def test_overcommit_burst_evaluation_all_paradigms(self):
        """Verifies simulation across all 4 architectures under 200% memory overcommit."""
        engine = ComparativeArchitectureEngine(host_disk_speed_mb_s=35.0, host_mem_bus_gb_s=6.0)

        results = engine.evaluate_overcommit_burst(
            physical_ram_mb=64,
            demanded_ram_mb=128,
            task_count=20
        )

        self.assertIn(ArchitectureParadigm.LINUX_VM_SWAP, results)
        self.assertIn(ArchitectureParadigm.SPARK_RAY_RDD, results)
        self.assertIn(ArchitectureParadigm.MACH_EXTERNAL_PAGER, results)
        self.assertIn(ArchitectureParadigm.ADIOS_CMF_FLUIDRAM, results)

        linux = results[ArchitectureParadigm.LINUX_VM_SWAP]
        cmf = results[ArchitectureParadigm.ADIOS_CMF_FLUIDRAM]
        spark = results[ArchitectureParadigm.SPARK_RAY_RDD]
        mach = results[ArchitectureParadigm.MACH_EXTERNAL_PAGER]

        # 1. Linux kills tasks under 200% overcommit; CMF kills ZERO!
        self.assertGreater(linux["tasks_killed"], 0)
        self.assertEqual(cmf["tasks_killed"], 0)
        self.assertEqual(cmf["data_loss"], "NO (100% state preserved in causal graph)")

        # 2. CMF fault resolution latency is orders of magnitude faster than Linux, Mach, Spark
        self.assertLess(cmf["fault_latency_ms"], 0.1)  # < 0.1 ms (45 us)
        self.assertGreater(linux["fault_latency_ms"], 1000.0)  # > 1,000 ms
        self.assertGreater(mach["fault_latency_ms"], 10.0)
        self.assertGreater(spark["fault_latency_ms"], 100.0)

        # 3. Efficiency ratio
        self.assertGreater(cmf["memory_efficiency_ratio"], linux["memory_efficiency_ratio"])

    def test_comparative_summary_speedup_calculation(self):
        """Verifies summary calculations and speedup metrics."""
        engine = ComparativeArchitectureEngine()
        results = engine.evaluate_overcommit_burst(physical_ram_mb=64, demanded_ram_mb=128, task_count=20)
        summary = engine.calculate_comparative_summary(results)

        self.assertIn("x Faster", summary["latency_speedup_vs_linux_swap"])
        self.assertEqual(summary["cmf_tasks_killed"], 0)
        self.assertGreater(summary["linux_tasks_killed"], 0)


if __name__ == "__main__":
    unittest.main()
