#!/usr/bin/env python3
"""
AdiOS Unified Build & Boot Script (v0.4.0-alpha)
Usage:
  python build.py          # Assembles GUI kernel and boots interactive desktop
  python build.py --3d     # Launches TempleOS-style StarFlight 3D wireframe game
  python build.py --run <file.ap>  # Executes an AdiPython script
  python build.py --cli    # Assembles CLI kernel and runs in terminal mode
  python build.py --test   # Runs full regression test suite (VM + AdiPython + CLI + GUI)
  python build.py --build  # Assembles kernel binaries only
"""

import sys
import os
import time
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

def run_game_3d():
    print("=====================================================")
    print("        AdiOS StarFlight 3D Simulation Engine        ")
    print("=====================================================")
    print("[StarFlight 3D] Initializing 3D Wireframe Graphics Pipeline...")
    from vm.vm import VM
    from vm.display import DisplayWindow
    from games.flight3d import StarFlight3D

    vm = VM()
    game = StarFlight3D(vm)
    disp = DisplayWindow(vm.fb, uart_callback=lambda c: None)
    vm.display = disp

    print("[StarFlight 3D] Display: 640x480 32-bit Framebuffer")
    print("[StarFlight 3D] Controls: Move mouse to steer ship (pitch & bank). Close window to exit.")

    last_frame = time.time()
    try:
        while True:
            now = time.time()
            if now - last_frame >= 0.020:  # ~50 FPS
                game.step_frame(disp.mouse_x, disp.mouse_y)
                disp.render_frame()
                if not disp.update():
                    print("\n[StarFlight 3D] Flight session ended.")
                    break
                last_frame = now
            time.sleep(0.002)
    except KeyboardInterrupt:
        print("\n[StarFlight 3D] Stopped by user.")

def run_adipython(script_path):
    print(f"[AdiOS] Executing AdiPython Script: '{script_path}'...")
    from vm.vm import VM
    from adipython import AdiPython
    vm = VM()
    ap = AdiPython(vm)
    ap.execute_file(script_path)

def test():
    print("\n[AdiOS] Running Automated Regression Test Suite...")

    print("\n--- 1. Testing Capable Simulation Layer (Hardware, 64MB RAM, Disk MMIO, RV32M) ---")
    res_vm = subprocess.run([sys.executable, "tests/test_vm_capable.py"])

    print("\n--- 2. Testing In-House AdiPython Language & Ring-0 Hardware Runtime ---")
    res_ap = subprocess.run([sys.executable, "tests/test_adipython.py"])

    print("\n--- 3. Testing AdiPython Native RV32IM JIT Compiler & Preprocessor ---")
    res_jit = subprocess.run([sys.executable, "tests/test_jit_compiler.py"])

    print("\n--- 4. Testing RV32IM In-Memory Disassembler ---")
    res_dis = subprocess.run([sys.executable, "tests/test_disasm.py"])

    print("\n--- 5. Testing AdiPython Standard Library (Math, Mem, Collections) ---")
    res_std = subprocess.run([sys.executable, "tests/test_stdlib.py"])

    print("\n--- 6. Testing DolDoc Universal Hypertext Engine ---")
    res_doc = subprocess.run([sys.executable, "tests/test_doldoc.py"])

    print("\n--- 7. Testing AdiFS Contiguous Block Filesystem Subsystem ---")
    res_fs = subprocess.run([sys.executable, "tests/test_adifs.py"])

    print("\n--- 8. Testing Bare-Metal Shell Subsystem (with Disk & LS Commands) ---")
    assemble("kernel/asm_kernel.s", "adios.bin")
    res_cli = subprocess.run([sys.executable, "tests/test_shell.py"])

    print("\n--- 9. Testing Graphical Desktop & Mouse Subsystem ---")
    assemble("kernel/gui_kernel.s", "adios.bin")
    res_gui = subprocess.run([sys.executable, "tests/test_gui.py"])

    all_pass = all(r.returncode == 0 for r in [res_vm, res_ap, res_jit, res_dis, res_std, res_doc, res_fs, res_cli, res_gui])
    if all_pass:
        print("\n===========================================================")
        print("[AdiOS] ALL 9 SUBSYSTEMS PASSED WITH 100% SUCCESS!")
        print("  - Capable Simulation Layer (64MB RAM, Disk MMIO, RV32M): PASS")
        print("  - AdiPython In-House Language & Hardware Bridge:         PASS")
        print("  - AdiPython Native RV32IM JIT Compiler & Preprocessor:   PASS")
        print("  - RV32IM In-Memory Disassembler:                         PASS")
        print("  - AdiPython Standard Library (Math, Mem, Collections):   PASS")
        print("  - DolDoc Universal Hypertext Engine:                     PASS")
        print("  - AdiFS Contiguous Block Filesystem:                     PASS")
        print("  - Bare-Metal CLI Shell Subsystem (with Disk & LS):       PASS")
        print("  - Graphical Windowing Desktop & Applications:           PASS")
        print("===========================================================")
    else:
        print("\n[AdiOS] Test failure detected.")
        sys.exit(1)

if __name__ == "__main__":
    if "--build" in sys.argv:
        assemble("kernel/gui_kernel.s", "adios.bin")
    elif "--test" in sys.argv:
        test()
    elif "--3d" in sys.argv or "--game" in sys.argv:
        run_game_3d()
    elif "--run" in sys.argv:
        idx = sys.argv.index("--run")
        if idx + 1 < len(sys.argv):
            run_adipython(sys.argv[idx + 1])
        else:
            print("Error: Specify a script path after --run")
    elif "--cli" in sys.argv:
        assemble("kernel/asm_kernel.s", "adios.bin")
        boot(use_gui=False)
    else:
        assemble("kernel/gui_kernel.s", "adios.bin")
        boot(use_gui=True)
