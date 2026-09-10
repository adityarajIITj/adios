"""
tests/test_linux_kernel_benchmarks.py - Automated Test Suite for Linux Kernel Memory Benchmarks
Verifies:
1. Canonical Linux kernel C source files are imported and valid
2. Linux vmscan.c dual-list LRU page reclaim behavior
3. Linux oom_kill.c badness calculation and process termination
4. Comparative benchmark execution pitting Linux against AdiOS Flagship Memory Architecture
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from vendor.linux_kernel.linux_mm_model import (
    LinuxZone, LinuxProcessStub, LinuxVMScanEngine, LinuxOOMKiller,
    LRU_INACTIVE_ANON, LRU_ACTIVE_ANON, WMARK_LOW, WMARK_MIN
)
from userland.linux_memory_benchmark import LinuxKernelMemoryBenchmark


class TestLinuxKernelBenchmarks(unittest.TestCase):
    """Verifies Linux kernel memory management models and comparative benchmarks."""

    def test_linux_source_files_present(self):
        """Verifies that Linux kernel C source files exist and have substantial size."""
        base_dir = os.path.join(os.path.dirname(__file__), "..", "vendor", "linux_kernel")
        expected_files = ["mmzone.h", "vmscan.c", "oom_kill.c", "oom.h"]
        for fname in expected_files:
            fpath = os.path.join(base_dir, fname)
            self.assertTrue(os.path.exists(fpath), f"Missing Linux source file: {fname}")
            size = os.path.getsize(fpath)
            self.assertGreater(size, 1000, f"Linux source file {fname} is too small ({size} bytes)")

    def test_linux_vmscan_lru_behavior(self):
        """Verifies active/inactive list demotion and eviction based on mm/vmscan.c."""
        zone = LinuxZone(total_ram_mb=32)
        vmscan = LinuxVMScanEngine(zone)
        proc = LinuxProcessStub(pid=1, name="init", rss_pages=0)
        vmscan.register_process(proc)

        # Allocate 10 pages -> initially enter LRU_INACTIVE_ANON
        for _ in range(10):
            zone.allocate_page(proc)

        self.assertEqual(len(zone.lru_lists[LRU_INACTIVE_ANON]), 10)
        self.assertEqual(len(zone.lru_lists[LRU_ACTIVE_ANON]), 0)

        # Mark 5 pages as accessed -> should promote to LRU_ACTIVE_ANON on scan
        for p in list(proc.pages)[:5]:
            p.mark_accessed()
            p.mark_accessed()

        # Shrink inactive list
        vmscan.shrink_inactive_list(nr_to_scan=10)
        self.assertEqual(len(zone.lru_lists[LRU_ACTIVE_ANON]), 5)
        self.assertEqual(len(zone.lru_lists[LRU_INACTIVE_ANON]), 0)
        self.assertEqual(zone.pages_reclaimed, 5)

    def test_linux_oom_killer(self):
        """Verifies Linux oom_badness scoring and process selection based on mm/oom_kill.c."""
        zone = LinuxZone(total_ram_mb=16)
        oom = LinuxOOMKiller(zone)

        p1 = LinuxProcessStub(pid=10, name="small_proc", rss_pages=50)
        p2 = LinuxProcessStub(pid=20, name="memory_hog", rss_pages=500)
        victim = oom.select_bad_process([p1, p2])

        self.assertIsNotNone(victim)
        self.assertEqual(victim.pid, 20)

        freed = oom.oom_kill_process(victim)
        self.assertEqual(freed, 500)
        self.assertTrue(p2.is_killed)
        self.assertIn(20, oom.killed_processes)

    def test_linux_vs_adios_benchmarks(self):
        """Executes full 4-workload benchmark and asserts AdiOS sovereign advantages."""
        runner = LinuxKernelMemoryBenchmark()
        report = runner.run_all_benchmarks()
        benchmarks = report["benchmarks"]
        self.assertEqual(len(benchmarks), 4)

        # Benchmark 1: Sleeping Wakeup Stalls
        b1 = benchmarks[0]
        self.assertGreater(b1["linux"]["wakeup_page_faults"], 0)
        self.assertEqual(b1["adios"]["wakeup_page_faults"], 0)
        self.assertEqual(b1["adios"]["cpu_stall_latency_ms"], 0.0)

        # Benchmark 2: Bus Traffic
        b2 = benchmarks[1]
        self.assertGreater(b2["linux"]["bus_traffic_mb"], 60.0)
        self.assertLess(b2["adios"]["bus_traffic_mb"], 0.01)
        self.assertGreater(b2["adios"]["bus_reduction_pct"], 99.0)

        # Benchmark 3: Transaction Rollback
        b3 = benchmarks[2]
        self.assertGreater(b3["linux"]["snapshot_memory_mb"], 50.0)
        self.assertEqual(b3["adios"]["snapshot_memory_mb"], 0.0)
        self.assertTrue(b3["adios"]["bit_exact_recovery"])

        # Benchmark 4: Overcommit Surge
        b4 = benchmarks[3]
        self.assertGreater(b4["linux"]["processes_killed"], 0)
        self.assertEqual(b4["adios"]["processes_killed"], 0)


if __name__ == "__main__":
    unittest.main()
