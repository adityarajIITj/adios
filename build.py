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

    print("\n--- 7. Testing 3D Graphics Engine & Software Rasterizer ---")
    res_3d = subprocess.run([sys.executable, "tests/test_engine3d.py"])

    print("\n--- 8. Testing PC Speaker Music Tracker & Synthesizer ---")
    res_trk = subprocess.run([sys.executable, "tests/test_tracker.py"])

    print("\n--- 9. Testing AdiFS Contiguous Block Filesystem Subsystem ---")
    res_fs = subprocess.run([sys.executable, "tests/test_adifs.py"])

    print("\n--- 10. Testing Bare-Metal Shell Subsystem (with Disk & LS Commands) ---")
    assemble("kernel/asm_kernel.s", "adios.bin")
    res_cli = subprocess.run([sys.executable, "tests/test_shell.py"])

    print("\n--- 11. Testing Sovereign Desktop Window Manager & Compositor ---")
    res_wm = subprocess.run([sys.executable, "tests/test_desktop_wm.py"])

    print("\n--- 12. Testing In-OS Code Editor (AdiIDE) ---")
    res_ed = subprocess.run([sys.executable, "tests/test_editor.py"])

    print("\n--- 13. Testing CastleAdiOS 3D Raycasting Game Engine ---")
    res_cas = subprocess.run([sys.executable, "tests/test_castle3d.py"])

    print("\n--- 14. Testing Advanced Systems Standard Library (Block A) ---")
    res_stda = subprocess.run([sys.executable, "tests/test_stdlib_block_a.py"])

    print("\n--- 15. Testing High-Scale Compiler IR & Optimizer Pipeline (Block B) ---")
    res_opt = subprocess.run([sys.executable, "tests/test_compiler_block_b.py"])

    print("\n--- 16. Testing Core Bare-Metal Assembly Kernel Suite (Block C) ---")
    res_kblkc = subprocess.run([sys.executable, "tests/test_kernel_block_c.py"])

    print("\n--- 17. Testing Sovereign Interactive Cyber Suite (Block D) ---")
    res_blkd = subprocess.run([sys.executable, "tests/test_holy_block_d.py"])

    print("\n--- 18. Testing Networking & Communications Subsystem (Block E) ---")
    res_net = subprocess.run([sys.executable, "tests/test_net_block_e.py"])

    print("\n--- 19. Testing Advanced Cyber Security & Cryptography Subsystem (Block F) ---")
    res_cry = subprocess.run([sys.executable, "tests/test_crypto_block_f.py"])

    print("\n--- 20. Testing Virtual Memory, Sv32 Paging & TLB Subsystem (Block G) ---")
    res_mmu = subprocess.run([sys.executable, "tests/test_mmu_block_g.py"])

    print("\n--- 21. Testing Process, Signals, IPC & Syscall ABI Subsystem (Block H) ---")
    res_proc = subprocess.run([sys.executable, "tests/test_proc_block_h.py"])

    print("\n--- 22. Testing In-OS C Compiler & ELF32 Toolchain (Block I) ---")
    res_cc = subprocess.run([sys.executable, "tests/test_compiler_block_i.py"])

    print("\n--- 23. Testing Zero-Dependency Standard C Library (Block J) ---")
    res_libc = subprocess.run([sys.executable, "tests/test_libc_block_j.py"])

    print("\n--- 24. Testing Hardware Drivers & VirtIO Bus (Block K) ---")
    res_drv = subprocess.run([sys.executable, "tests/test_drivers_block_k.py"])

    print("\n--- 25. Testing Transmission Control Protocol Engine (Block L) ---")
    res_tcp = subprocess.run([sys.executable, "tests/test_tcp_block_l.py"])

    print("\n--- 26. Testing Layer-7 Network Application Protocols (Block M) ---")
    res_proto = subprocess.run([sys.executable, "tests/test_net_protocols_block_m.py"])

    print("\n--- 27. Testing POSIX Shell & Userland Utilities (Block N) ---")
    res_usr = subprocess.run([sys.executable, "tests/test_userland_block_n.py"])

    print("\n--- 28. Testing SovereignSQL Relational Database Engine (Block O) ---")
    res_db = subprocess.run([sys.executable, "tests/test_db_block_o.py"])

    print("\n--- 29. Testing Window Server & Vector GUI Toolkit (Block P) ---")
    res_ui = subprocess.run([sys.executable, "tests/test_ui_block_p.py"])

    print("\n--- 30. Testing Multi-Core SMP & Microkernel IPC (Block Q) ---")
    res_smp = subprocess.run([sys.executable, "tests/test_smp_block_q.py"])

    print("\n--- 31. Testing Digital Audio Synthesis & DSP Studio (Block R) ---")
    res_dsp = subprocess.run([sys.executable, "tests/test_dsp_block_r.py"])

    print("\n--- 32. Testing Native Filesystem Suite Ext2 & FAT32 (Block S) ---")
    res_vfs = subprocess.run([sys.executable, "tests/test_vfs_block_s.py"])

    print("\n--- 33. Testing TLS 1.3 Record Layer & Handshake Engine (Block T) ---")
    res_tls = subprocess.run([sys.executable, "tests/test_tls13_block_t.py"])

    print("\n--- 34. Testing In-OS Debugger & GDB Remote Serial Protocol (Block U) ---")
    res_dbg = subprocess.run([sys.executable, "tests/test_debug_block_u.py"])

    print("\n--- 35. Testing Bare-Metal Graphical Desktop & Mouse Subsystem ---")
    assemble("kernel/gui_kernel.s", "adios.bin")
    res_gui = subprocess.run([sys.executable, "tests/test_gui.py"])

    all_pass = all(r.returncode == 0 for r in [res_vm, res_ap, res_jit, res_dis, res_std, res_doc, res_3d, res_trk, res_fs, res_cli, res_wm, res_ed, res_cas, res_stda, res_opt, res_kblkc, res_blkd, res_net, res_cry, res_mmu, res_proc, res_cc, res_libc, res_drv, res_tcp, res_proto, res_usr, res_db, res_ui, res_smp, res_dsp, res_vfs, res_tls, res_dbg, res_gui])
    if all_pass:
        print("\n===========================================================")
        print("[AdiOS] ALL 35 SUBSYSTEMS PASSED WITH 100% SUCCESS!")
        print("  - Capable Simulation Layer (64MB RAM, Disk MMIO, RV32M): PASS")
        print("  - AdiPython In-House Language & Hardware Bridge:         PASS")
        print("  - AdiPython Native RV32IM JIT Compiler & Preprocessor:   PASS")
        print("  - RV32IM In-Memory Disassembler:                         PASS")
        print("  - AdiPython Standard Library (Math, Mem, Collections):   PASS")
        print("  - DolDoc Universal Hypertext Engine:                     PASS")
        print("  - 3D Software Rasterizer & Mesh Pipeline:                PASS")
        print("  - PC Speaker Music Tracker & Synthesizer:                PASS")
        print("  - AdiFS Contiguous Block Filesystem:                     PASS")
        print("  - Bare-Metal CLI Shell Subsystem (with Disk & LS):       PASS")
        print("  - Sovereign Window Manager & Desktop Compositor:         PASS")
        print("  - In-OS Code Editor & Syntax Highlighting:               PASS")
        print("  - CastleAdiOS 3D Raycasting Dungeon Game:                PASS")
        print("  - Advanced Systems Stdlib (Trees, Maps, Heaps, Matrix):  PASS")
        print("  - Compiler IR, CFG, Optimizer & Linear Scan RegAlloc:    PASS")
        print("  - Core Bare-Metal Assembly Kernel (Sched, PAlloc, VFS):  PASS")
        print("  - Sovereign Cyber Interactive Suite (Oracle, Synth, 3D): PASS")
        print("  - Networking Stack (SLIP, Ethernet, ARP, IPv4, UDP):     PASS")
        print("  - Cyber Security & Cryptography (SHA256, ChaCha, AEAD):  PASS")
        print("  - Virtual Memory & MMU (Sv32 Paging, 64-Entry TLB, AS):  PASS")
        print("  - Process, Signals & IPC (TCB, MLFQ, Pipes, Syscalls):   PASS")
        print("  - In-OS C Compiler & Toolchain (C99, RV32, ELF32):       PASS")
        print("  - Zero-Dependency Standard C Library (stdio, stdlib):    PASS")
        print("  - Hardware Drivers & VirtIO Bus (Net, Blk, PCI, RTC):    PASS")
        print("  - Transmission Control Protocol (TCP/IP 3-Way Engine):   PASS")
        print("  - Layer-7 Application Protocols (HTTP/1.1, DNS, DHCP):   PASS")
        print("  - POSIX Shell & Userland Utilities (Pipes, Redir, Core): PASS")
        print("  - SovereignSQL Relational Engine (ACID, WAL, Filter):    PASS")
        print("  - Window Server & Vector GUI (Canvas2D, Widgets, Z-Win): PASS")
        print("  - Multi-Core SMP & IPI Engine (Harts, CLINT, Stealing):  PASS")
        print("  - Digital Audio Synthesis & DSP Studio (PCM, WAV, ADSR): PASS")
        print("  - Native Filesystem Architecture (Ext2, FAT32 Inodes):   PASS")
        print("  - TLS 1.3 Record Layer & Handshake Engine (HKDF, AEAD):  PASS")
        print("  - In-OS Debugger & GDB Remote Serial Protocol (RSP):     PASS")
        print("  - Bare-Metal Windowing Desktop & Applications:           PASS")
        print("===========================================================")
    else:
        print("\n[AdiOS] Test failure detected.")
        sys.exit(1)

def run_castle3d():
    print("=====================================================")
    print("        CastleAdiOS 3D: Dungeon Crawler              ")
    print("=====================================================")
    print("[CastleAdiOS 3D] Initializing DDA Raycasting Engine...")
    from vm.vm import VM
    from vm.display import DisplayWindow
    from games.castle3d import CastleAdiOS3D

    vm = VM()
    game = CastleAdiOS3D(vm)
    disp = DisplayWindow(vm.fb, uart_callback=lambda c: None)
    vm.display = disp

    print("[CastleAdiOS 3D] Move mouse to look. Close window to exit.")
    last_frame = time.time()
    last_mouse_x = disp.mouse_x
    try:
        while True:
            now = time.time()
            if now - last_frame >= 0.025:  # ~40 FPS
                dx = disp.mouse_x - last_mouse_x
                last_mouse_x = disp.mouse_x
                game.render_frame(mouse_dx=dx)
                disp.render_frame()
                if not disp.update():
                    break
                last_frame = now
            time.sleep(0.002)
    except KeyboardInterrupt:
        print("\n[CastleAdiOS 3D] Exited.")

def run_desktop():
    print("=====================================================")
    print("        AdiOS Sovereign Desktop Environment          ")
    print("=====================================================")
    print("[AdiOS Desktop] Initializing Window Compositor, DolDoc & 3D Viewport...")
    from vm.vm import VM
    from vm.display import DisplayWindow
    from desktop import SovereignDesktop

    vm = VM()
    desktop = SovereignDesktop(vm)
    disp = DisplayWindow(vm.fb, uart_callback=lambda c: None)
    vm.display = disp

    print("[AdiOS Desktop] 640x480 Sovereign Desktop Running. Close window to exit.")
    last_frame = time.time()
    try:
        while True:
            now = time.time()
            if now - last_frame >= 0.025:  # ~40 FPS
                desktop.step_frame(disp.mouse_x, disp.mouse_y)
                desktop.render(vm.fb)
                disp.render_frame()
                if not disp.update():
                    break
                last_frame = now
            time.sleep(0.002)
    except KeyboardInterrupt:
        print("\n[AdiOS Desktop] Closed.")

def play_hymn():
    from vm.vm import VM
    from audio import AudioTracker, HYMN_OF_ADIOS
def run_cyber_shell():
    from holy.holy_shell import SovereignCyberShell
    from vm.vm import VM
    print("[AdiOS] Launching Sovereign Cyber Shell...")
    vm = VM()
    shell = SovereignCyberShell(vm)
    print(shell.cmd_help())
    while shell.running:
        try:
            line = input("adios-cyber> ")
            if line.strip():
                print(shell.execute_line(line))
        except (KeyboardInterrupt, EOFError):
            print("\nExiting AdiOS Cyber Shell.")
            break

if __name__ == "__main__":
    if "--build" in sys.argv:
        assemble("kernel/gui_kernel.s", "adios.bin")
    elif "--test" in sys.argv:
        test()
    elif "--desktop" in sys.argv:
        run_desktop()
    elif "--shell" in sys.argv or "--cyber" in sys.argv:
        run_cyber_shell()
    elif "--castle" in sys.argv or "--fps" in sys.argv:
        run_castle3d()
    elif "--hymn" in sys.argv or "--song" in sys.argv:
        play_hymn()
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
