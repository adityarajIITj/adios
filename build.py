#!/usr/bin/env python3
"""
AdiOS Unified Build & Boot Script (v0.2.0-alpha)
Usage:
  python build.py          # Assembles GUI kernel and boots interactive desktop
  python build.py --cli    # Assembles CLI kernel and runs in terminal mode
  python build.py --test   # Runs full regression test suite (CLI + GUI)
  python build.py --build  # Assembles kernel binaries only
"""

import sys
import os
import subprocess

def assemble(kernel_src="kernel/gui_kernel.s", output_bin="adios.bin"):
    print(f"[AdiOS Build] Assembling '{kernel_src}' with custom RV32I toolchain...")
    cmd = [sys.executable, "toolchain/assembler.py", kernel_src, output_bin]
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print("[AdiOS Build] Assembly failed!")
        sys.exit(1)
    print(f"[AdiOS Build] Build complete: '{output_bin}' ready.")

def boot(use_gui=True):
    print(f"[AdiOS] Launching Simulation Layer ({'GUI Desktop' if use_gui else 'CLI Console'})...")
    args = [sys.executable, "vm/vm.py", "adios.bin"]
    if not use_gui:
        args.append("--cli")
    subprocess.run(args)

def test():
    print("\n[AdiOS] Running Automated Regression Test Suite...")
    print("--- 1. Testing Bare-Metal Shell Subsystem ---")
    assemble("kernel/asm_kernel.s", "adios.bin")
    res1 = subprocess.run([sys.executable, "tests/test_shell.py"])

    print("\n--- 2. Testing Graphical Desktop & Mouse Subsystem ---")
    assemble("kernel/gui_kernel.s", "adios.bin")
    res2 = subprocess.run([sys.executable, "tests/test_gui.py"])

    if res1.returncode == 0 and res2.returncode == 0:
        print("\n[AdiOS] ALL TESTS PASSED SUCCESSFULLY! Both CLI and GUI are fully operational.")
    else:
        print("\n[AdiOS] Test failure detected.")
        sys.exit(1)

if __name__ == "__main__":
    if "--build" in sys.argv:
        assemble("kernel/gui_kernel.s", "adios.bin")
    elif "--test" in sys.argv:
        test()
    elif "--cli" in sys.argv:
        assemble("kernel/asm_kernel.s", "adios.bin")
        boot(use_gui=False)
    else:
        assemble("kernel/gui_kernel.s", "adios.bin")
        boot(use_gui=True)
