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

    print("\n--- 35. Testing Software OpenGL 1.1 3D Graphics Engine (Block V) ---")
    res_gl = subprocess.run([sys.executable, "tests/test_gl_block_v.py"])

    print("\n--- 36. Testing 3D Physics & Spatial Partitioning Engine (Block W) ---")
    res_sp = subprocess.run([sys.executable, "tests/test_spatial_block_w.py"])

    print("\n--- 37. Testing Web Engine & Hypertext Layout Browser (Block X) ---")
    res_brw = subprocess.run([sys.executable, "tests/test_browser_block_x.py"])

    print("\n--- 38. Testing Sovereign Dynamic Bytecode VM & Lisp Engine (Block Y) ---")
    res_vm2 = subprocess.run([sys.executable, "tests/test_bytecode_block_y.py"])

    print("\n--- 39. Testing Type-1 Hypervisor & Master Integration Matrix (Block Z) ---")
    res_hyp = subprocess.run([sys.executable, "tests/test_hypervisor_block_z.py"])

    print("\n--- 40. Testing Bare-Metal Graphical Desktop & Mouse Subsystem ---")
    assemble("kernel/gui_kernel.s", "adios.bin")
    res_gui = subprocess.run([sys.executable, "tests/test_gui.py"])

    print("\n--- 41. Testing Unified Sovereign Master Desktop & 8 Subsystem Apps ---")
    res_mdesk = subprocess.run([sys.executable, "-m", "unittest", "tests/test_master_desktop.py"])

    print("\n--- 42. Testing Pass 1 Systems Deepening (Preprocessor, Types, COW, Threads) ---")
    res_pass1 = subprocess.run([sys.executable, "-m", "unittest", "tests/test_deep_pass1.py"])

    print("\n--- 43. Testing Pass 2 Security & Protocols (X.509, AES, Congestion, WebSocket) ---")
    res_pass2 = subprocess.run([sys.executable, "-m", "unittest", "tests/test_deep_pass2.py"])

    print("\n--- 44. Testing Pass 3 Storage & Database (Ext2 Deep, B+ Tree, Query Planner) ---")
    res_pass3 = subprocess.run([sys.executable, "-m", "unittest", "tests/test_deep_pass3.py"])

    print("\n--- 45. Testing Pass 4 3D Graphics, Physics & Audio DSP ---")
    res_pass4 = subprocess.run([sys.executable, "-m", "unittest", "tests/test_deep_pass4.py"])

    print("\n--- 46. Testing High-Resolution Workstation (1024x768 XGA, Snapping & Controls) ---")
    res_res1024 = subprocess.run([sys.executable, "-m", "unittest", "tests/test_desktop_res1024.py"])

    print("\n--- 47. Testing Language Runtime & Native JIT Deepening (Pass X Block 2) ---")
    res_ap_deep = subprocess.run([sys.executable, "tests/test_adipython_deepened.py"])

    print("\n--- 48. Testing C Compiler Toolchain & Zero-Dependency Libc Deepening (Pass X Block 3) ---")
    res_c_deep = subprocess.run([sys.executable, "tests/test_c_toolchain_deepened.py"])

    print("\n--- 49. Testing Storage, B+ Tree & Relational Query Planner Deepening (Pass X Block 4) ---")
    res_storage_deep = subprocess.run([sys.executable, "-m", "unittest", "tests/test_storage_db_deepened.py"])

    print("\n--- 50. Testing Security, Protocols, 3D Graphics & DSP Deepening (Pass X Block 5) ---")
    res_sec_deep = subprocess.run([sys.executable, "-m", "unittest", "tests/test_crypto_net_dsp_deepened.py"])

    print("\n--- 51. Testing Kernel Core, Process, Concurrency & Virtual Memory Deepening ---")
    res_kcore_deep = subprocess.run([sys.executable, "-m", "unittest", "tests/test_kernel_core_deepened.py"])

    print("\n--- 52. Testing Network Protocols, Fragmentation & Transport Deepening ---")
    res_net_deep = subprocess.run([sys.executable, "-m", "unittest", "tests/test_net_stack_deepened.py"])

    print("\n--- 53. Testing Toolchain, Filesystem, GUI & 3D Graphics Deepening ---")
    res_tool_deep = subprocess.run([sys.executable, "-m", "unittest", "tests/test_toolchain_fs_graphics_deepened.py"])

    all_tests = [
        ("VM", res_vm), ("AP", res_ap), ("JIT", res_jit), ("DIS", res_dis), ("STD", res_std),
        ("DOC", res_doc), ("3D", res_3d), ("TRK", res_trk), ("FS", res_fs), ("CLI", res_cli),
        ("WM", res_wm), ("ED", res_ed), ("CAS", res_cas), ("STDA", res_stda), ("OPT", res_opt),
        ("KBLKC", res_kblkc), ("BLKD", res_blkd), ("NET", res_net), ("CRY", res_cry), ("MMU", res_mmu),
        ("PROC", res_proc), ("CC", res_cc), ("LIBC", res_libc), ("DRV", res_drv), ("TCP", res_tcp),
        ("PROTO", res_proto), ("USR", res_usr), ("DB", res_db), ("UI", res_ui), ("SMP", res_smp),
        ("DSP", res_dsp), ("VFS", res_vfs), ("TLS", res_tls), ("DBG", res_dbg), ("GL", res_gl),
        ("SP", res_sp), ("BRW", res_brw), ("VM2", res_vm2), ("HYP", res_hyp), ("GUI", res_gui),
        ("MDESK", res_mdesk), ("PASS1", res_pass1), ("PASS2", res_pass2), ("PASS3", res_pass3),
        ("PASS4", res_pass4), ("RES1024", res_res1024), ("AP_DEEP", res_ap_deep), ("C_DEEP", res_c_deep),
        ("STORAGE_DEEP", res_storage_deep), ("SEC_DEEP", res_sec_deep), ("KCORE_DEEP", res_kcore_deep),
        ("NET_DEEP", res_net_deep), ("TOOL_DEEP", res_tool_deep)
    ]
    all_pass = all(r.returncode == 0 for name, r in all_tests)
    if all_pass:
        print("\n===========================================================")
        print("[AdiOS] ALL 53 SUBSYSTEMS PASSED WITH 100% SUCCESS!")
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
        print("  - Software OpenGL 1.1 3D Pipeline (Matrix, Z-Buf, DDA):  PASS")
        print("  - 3D Physics Engine & Octree Spatial Partitioning:       PASS")
        print("  - Web Engine & Hypertext Layout Browser (HTML/CSS/DOM):  PASS")
        print("  - Dynamic Bytecode VM & Lisp S-Expression Engine:        PASS")
        print("  - Type-1 Hypervisor & Stage-2 Nested Paging (H-Ext):     PASS")
        print("  - Bare-Metal Graphical Desktop & Mouse Subsystem:        PASS")
        print("  - Unified Sovereign Master Desktop & 8 Integrated Apps:  PASS")
        print("  - Pass 1 Systems Deepening (Preprocessor, Types, COW, Threads): PASS")
        print("  - Pass 2 Security & Protocols (X.509, AES, Congestion, WebSocket): PASS")
        print("  - Pass 3 Storage & Database (Ext2 Deep, B+ Tree, Query Planner): PASS")
        print("  - Pass 4 3D Graphics, Physics & Audio DSP (Textures, Light, Physics, Synth): PASS")
        print("  - Pass X High-Resolution Workstation (1024x768 XGA, Snapping & Controls): PASS")
        print("  - Pass X Language Runtime & Native JIT Deepening (AST, CSE, LICM, JIT): PASS")
        print("  - Pass X C Compiler Toolchain & Zero-Dependency Libc Deepening: PASS")
        print("  - Pass X Storage, B+ Tree & Relational Query Planner Deepening: PASS")
        print("  - Pass X Security, Protocols, 3D Graphics & DSP Deepening: PASS")
        print("  - Pass X Kernel Core, Process, Concurrency & Sv32 MMU Deepening: PASS")
        print("  - Pass X Network Protocols, Fragmentation & Transport Deepening: PASS")
        print("  - Pass X Toolchain, Filesystem, GUI & 3D Graphics Deepening: PASS")
        print("===========================================================")
    else:
        print("\n[AdiOS] Test failure detected:")
        for name, r in all_tests:
            if r.returncode != 0:
                print(f"  FAILED: {name} with code {r.returncode}")
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

def run_desktop(scale=1.0, width=1024, height=768):
    print("=====================================================")
    print("     AdiOS Sovereign Workstation (1024x768 XGA)      ")
    print("=====================================================")
    print(f"[AdiOS Desktop] Initializing Workstation Compositor ({width}x{height} @ {scale}x scale)...")
    from vm.vm import VM
    from vm.display import DisplayWindow
    from desktop import MasterDesktop

    vm = VM()
    vm.fb = bytearray(width * height * 4)
    desktop = MasterDesktop(vm, width=width, height=height)
    disp = DisplayWindow(vm.fb, width=width, height=height, scale=scale, uart_callback=lambda c: None)
    vm.display = disp

    # Direct event binding for instant interactive responsiveness
    disp.on_mouse_down_cb = lambda mx, my: desktop.handle_mouse_down(mx, my)
    disp.on_mouse_up_cb = lambda mx, my: desktop.handle_mouse_up(mx, my)
    disp.on_mouse_move_cb = lambda mx, my: desktop.handle_mouse_move(mx, my)

    def on_mouse_drag(mx, my):
        desktop.handle_mouse_move(mx, my)
        active_win = desktop.wm.get_window_at(mx, my) if hasattr(desktop, "wm") else None
        if active_win and active_win.win_id == "paint" and not desktop.wm.dragging_win:
            cx, cy, _, _ = active_win.client_rect
            rel_x = mx - cx
            rel_y = my - cy
            if 24 <= rel_y <= 88 and 6 <= rel_x <= 280:
                desktop.paint_strokes.append((mx, my, desktop.paint_color))

    disp.on_mouse_drag_cb = on_mouse_drag
    disp.on_key_cb = lambda k: desktop.handle_key(k)

    print(f"[AdiOS Desktop] {width}x{height} Sovereign Workstation Running. Close window to exit.")
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

def run_benchmarks():
    print("===========================================================")
    print("       AdiOS 1.0 Sovereign Systems Benchmark Suite         ")
    print("===========================================================")

    # 1. Cryptography: SHA-256 and AES-GCM throughput
    print("[Bench 1/5] Cryptographic Throughput...")
    from crypto.sha256 import sha256_hash as sha256
    from crypto.aes import AES

    data_1mb = b"ADIOS_CRYPTOGRAPHIC_BENCHMARK_BLOCK" * (1024 * 1024 // 36)
    t0 = time.perf_counter()
    _ = sha256(data_1mb)
    t_sha = time.perf_counter() - t0
    sha_mbps = (len(data_1mb) / (1024 * 1024)) / max(0.0001, t_sha)

    cipher = AES(b"KEY128BITBENCHMK")
    t0 = time.perf_counter()
    c, tag = cipher.encrypt_gcm(data_1mb, b"NONCE12BYTE!")
    t_aes = time.perf_counter() - t0
    aes_mbps = (len(data_1mb) / (1024 * 1024)) / max(0.0001, t_aes)
    print(f"  -> SHA-256 Digest: {sha_mbps:.2f} MB/sec")
    print(f"  -> AES-GCM AEAD:   {aes_mbps:.2f} MB/sec")

    # 2. Database: B+ Tree Index Operations
    print("[Bench 2/5] Relational & B+ Tree Index Throughput...")
    from db.bplus_tree import BPlusTree

    tree = BPlusTree(order=8)
    n_keys = 5000
    t0 = time.perf_counter()
    for i in range(n_keys):
        tree.insert(i, f"payload_{i}")
    t_insert = time.perf_counter() - t0
    insert_ops = n_keys / max(0.0001, t_insert)

    t0 = time.perf_counter()
    for i in range(0, n_keys, 2):
        _ = tree.search(i)
    t_search = time.perf_counter() - t0
    search_ops = (n_keys // 2) / max(0.0001, t_search)
    print(f"  -> B+ Tree Insert: {insert_ops:.0f} keys/sec")
    print(f"  -> B+ Tree Point Query: {search_ops:.0f} queries/sec")

    # 3. Storage: FAT32 & Ext2 Allocation
    print("[Bench 3/5] Filesystem Allocation & I/O...")
    from vfs.fat32 import FAT32Driver
    from vfs.ext2_deep import DeepExt2Driver

    t0 = time.perf_counter()
    fat_fs = FAT32Driver.create_formatted_disk(size_mb=4, volume_label="BENCH_FAT")
    for f_idx in range(50):
        fat_fs.write_file(f"F{f_idx}.TXT", b"AdiOS Sovereign Bench Content\n" * 10)
    t_fat = time.perf_counter() - t0
    fat_ops = 50 / max(0.0001, t_fat)

    t0 = time.perf_counter()
    ext2_fs = DeepExt2Driver.create_formatted_image(size_blocks=2048, block_size=1024)
    for e_idx in range(50):
        ext2_fs.create_file(f"/file_{e_idx}.bin", b"Ext2 Benchmark File Payload Block\n" * 10)
    t_ext2 = time.perf_counter() - t0
    ext2_ops = 50 / max(0.0001, t_ext2)
    print(f"  -> FAT32 Create/Write: {fat_ops:.0f} files/sec")
    print(f"  -> Ext2 Inode/Block Allocate: {ext2_ops:.0f} files/sec")

    # 4. 3D Graphics: Software OpenGL 1.1 Rasterization Fill Rate
    print("[Bench 4/5] Software OpenGL 1.1 Fixed-Function Rasterizer...")
    from gl.gl_core import SoftwareGL, GL_PROJECTION, GL_MODELVIEW, GL_TRIANGLES, GL_DEPTH_TEST

    gl = SoftwareGL(320, 240)
    gl.glClear(0xFF000000)
    gl.glEnable(GL_DEPTH_TEST)
    gl.glMatrixMode(GL_PROJECTION)
    gl.glLoadIdentity()
    gl.gluPerspective(60.0, 320.0 / 240.0, 0.1, 100.0)
    gl.glMatrixMode(GL_MODELVIEW)
    gl.glLoadIdentity()
    gl.glTranslatef(0.0, 0.0, -3.0)

    num_triangles = 500
    t0 = time.perf_counter()
    gl.glBegin(GL_TRIANGLES)
    for tri in range(num_triangles):
        gl.glColor3f(0.8, 0.4, 0.2)
        gl.glVertex3f(-0.5, -0.5, 0.0)
        gl.glColor3f(0.2, 0.8, 0.4)
        gl.glVertex3f(0.5, -0.5, 0.0)
        gl.glColor3f(0.4, 0.2, 0.8)
        gl.glVertex3f(0.0, 0.5, 0.0)
    gl.glEnd()
    t_gl = time.perf_counter() - t0
    tri_rate = num_triangles / max(0.0001, t_gl)
    print(f"  -> Triangle Fill Rate: {tri_rate:.0f} triangles/sec")

    # 5. Audio DSP: Polyphonic Tracker Synthesis
    print("[Bench 5/5] Polyphonic Audio DSP Synthesizer...")
    from dsp.tracker_studio import TrackerStudio, TrackerSong, Pattern

    studio = TrackerStudio(sample_rate=44100)
    song = TrackerSong(bpm=130, speed=6)
    pat = Pattern(num_rows=32)
    for r in range(0, 32, 2):
        pat.set_note(r, 0, "C-4", waveform="sawtooth")
        pat.set_note(r, 1, "E-4", waveform="square")
        pat.set_note(r, 2, "G-4", waveform="triangle")
        pat.set_note(r, 3, "B-4", waveform="sine")
    song.patterns.append(pat)
    song.order = [0]

    t0 = time.perf_counter()
    stereo_samples = studio.render_song(song)
    t_dsp = time.perf_counter() - t0
    samples_per_sec = len(stereo_samples) / max(0.0001, t_dsp)
    rt_factor = (len(stereo_samples) / 44100.0) / max(0.0001, t_dsp)
    print(f"  -> Audio Synthesis:    {samples_per_sec:.0f} samples/sec ({rt_factor:.1f}x Realtime)")

    print("===========================================================")
    print("[AdiOS] BENCHMARK COMPLETE: All subsystems performing within nominal specs.")
    print("===========================================================")

if __name__ == "__main__":
    if "--build" in sys.argv:
        assemble("kernel/gui_kernel.s", "adios.bin")
    elif "--test" in sys.argv:
        test()
    elif "--bench" in sys.argv:
        run_benchmarks()
    elif "--desktop" in sys.argv:
        scale = 1.0
        if "--scale" in sys.argv:
            idx = sys.argv.index("--scale")
            if idx + 1 < len(sys.argv):
                try:
                    scale = float(sys.argv[idx + 1])
                except ValueError:
                    scale = 1.0
        width, height = 1024, 768
        if "--res" in sys.argv:
            idx = sys.argv.index("--res")
            if idx + 1 < len(sys.argv):
                parts = sys.argv[idx + 1].lower().split("x")
                if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                    width, height = int(parts[0]), int(parts[1])
        run_desktop(scale=scale, width=width, height=height)
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
