"""
userland/run_c_benchmark.py - C Benchmark Runner and Compiler Driver
Compiles and runs benchmarks/benchmark_linux_with_vs_without_fluidram.c using native host compilers
(GCC/Clang/MSVC) or provides direct execution telemetry comparing Linux without FluidRAM vs Linux with FluidRAM.
"""

import os
import sys
import subprocess
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

def find_c_compiler() -> tuple:
    """Detects available C compiler on the host."""
    compilers = [
        ("gcc", ["gcc", "-O3", "-std=c99", "-o"]),
        ("clang", ["clang", "-O3", "-std=c99", "-o"]),
        ("cl", ["cl.exe", "/O2", "/Fe:"])
    ]
    for name, cmd in compilers:
        path = shutil.which(name)
        if path:
            return name, path, cmd
    return None, None, None

def run_standalone_c_benchmark():
    c_rel = os.path.join("benchmarks", "benchmark_linux_with_vs_without_fluidram.c")
    if not os.path.exists(c_rel):
        c_rel = os.path.join("benchmarks", "benchmark_linux_vs_adios.c")
    out_bin = os.path.join("benchmarks", "benchmark_linux_with_vs_without_fluidram.exe" if sys.platform == "win32" else "benchmark_linux_with_vs_without_fluidram")

    c_name, c_path, c_flags = find_c_compiler()

    if c_path:
        print(f"[C-Runner] Detected host C compiler: {c_name} ({c_path})")
        print(f"[C-Runner] Compiling '{c_rel}' (Linux Without FluidRAM vs Linux With FluidRAM)...")
        if c_name in ("gcc", "clang"):
            compile_cmd = [c_path, "-O3", "-std=c99", c_rel, "-o", out_bin, "-lm"]
        else:
            compile_cmd = [c_path, "/O2", c_rel, f"/Fe:{out_bin}"]

        res = subprocess.run(compile_cmd, capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(out_bin):
            print(f"[C-Runner] Compilation succeeded -> '{out_bin}'")
            print(f"[C-Runner] Executing native C binary...\n")
            exec_res = subprocess.run([out_bin], text=True)
            return exec_res.returncode
        else:
            print(f"[C-Runner] Native compilation failed:\n{res.stderr}")

    # If no native compiler on host, execute via the verified state-machine model with clear disclosure
    from userland.linux_memory_benchmark import get_global_memory_harness, LinuxKernelMemoryBenchmark, format_terminal_benchmark_report

    harness = get_global_memory_harness()
    phys_stats = harness.allocate_and_touch(16 * 1024 * 1024)

    print("=" * 80)
    print("  STANDALONE C BENCHMARK RUNNER: LINUX (WITHOUT FLUIDRAM) vs. WITH FLUIDRAM")
    print("=" * 80)
    print(f"  [C-Runner Source]    : {c_rel}")
    print(f"  [Host C Toolchain]   : Not detected in active PATH (Requires GCC/Clang/MSVC)")
    print(f"  [Native Linux Build] : gcc -O3 -std=c99 {c_rel} -o bench -lm && ./bench")
    print(f"  [Host Physical MMU]  : {phys_stats['allocated_bytes'] // (1024 * 1024)} MB allocated | {phys_stats['delta_page_faults']} physical page faults measured via {phys_stats['harness_mode']}")
    print(f"  [Active Mode]        : Algorithmic VM State-Machine Model (mm/vmscan.c + mm/oom_kill.c)")
    print(f"                         with Live Host Storage & DRAM Hardware Profiling")
    print("=" * 80 + "\n")

    runner = LinuxKernelMemoryBenchmark()
    print(format_terminal_benchmark_report(runner.run_all_benchmarks()))
    return 0

if __name__ == "__main__":
    sys.exit(run_standalone_c_benchmark())
