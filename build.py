#!/usr/bin/env python3
"""
AdiOS Unified Build & Boot Script
Usage:
  python build.py          # Assembles kernel and boots the interactive OS
  python build.py --build  # Assembles kernel only
  python build.py --test   # Runs automated test suite
"""

import sys
import os
import subprocess

def assemble():
    print("[AdiOS Build] Assembling bare-metal kernel with custom RV32I toolchain...")
    cmd = [sys.executable, "toolchain/assembler.py", "kernel/asm_kernel.s", "adios.bin"]
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print("[AdiOS Build] Assembly failed!")
        sys.exit(1)
    print("[AdiOS Build] Build complete: 'adios.bin' ready.")

def boot():
    print("[AdiOS] Launching Simulation Layer...")
    cmd = [sys.executable, "vm/vm.py", "adios.bin"]
    subprocess.run(cmd)

def test():
    print("[AdiOS] Running automated test suite...")
    cmd = [sys.executable, "tests/test_shell.py"]
    subprocess.run(cmd)

if __name__ == "__main__":
    if "--build" in sys.argv:
        assemble()
    elif "--test" in sys.argv:
        assemble()
        test()
    else:
        assemble()
        boot()
