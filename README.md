# AdiOS (v0.5.0-alpha) — Sovereign Computing Architecture

A minimalist, high-performance, bare-metal operating system, sovereign graphical desktop environment, 3D vector graphics engine, and in-house systems programming language (**AdiPython**) implemented from first principles for the 32-bit RISC-V (RV32IM) architecture.

Inspired by the sovereign, zero-bloat, ring-0 computing philosophy of Terry A. Davis's legendary operating system architecture, reimagined through a modern scientific, mathematical, and cyber-engineering framework.

---

## 1. System Overview

AdiOS is built from absolute scratch without external dependencies, bloat, or third-party engines. It features over **15,000 lines of code** verified across **18 automated subsystem test suites**:

1. **Bare-Metal RISC-V Simulation Layer**: Custom CPU core with 64 MB physical RAM, instruction decode caching (15–30 MIPS), full RV32M hardware math (`mul`, `div`, `rem`), MMIO peripherals (UART, real-time timer, power unit, audio synth, block storage, linear ARGB framebuffer, mouse).
2. **AdiPython In-House Systems Language**: Native systems language featuring Pythonic syntax with raw ring-0 hardware access (`peek`, `poke`, `pixel`, `rect`, `line`, `clear`, `tone`), instant execution, loops, recursion, and hardware bridges.
3. **High-Scale Compiler & Optimizer Pipeline**: Three-Address Code (TAC) Intermediate Representation, Control Flow Graph (CFG) generator, 4-pass optimizer (Constant Folding, Algebraic Strength Reduction, Dead Code Elimination, Peephole Optimization), and Linear Scan Register Allocator targeting 27 RISC-V physical registers.
4. **AdiFS Contiguous Block Filesystem**: Zero-fragmentation 512-byte sector architecture with 100% contiguous sector allocation, directory entries, Superblock metadata, and direct single-transfer DMA disk reads.
5. **Bare-Metal Assembly Kernel**: Preemptive priority round-robin task scheduler (TCB tables, 34-register context switching), dual-heap physical page frame bitmap allocator managing 16,384 4KB pages (64MB), and bare-metal VFS disk driver.
6. **Sovereign Window Manager & Desktop Compositor**: Multi-window Z-order compositor, active/inactive titlebars, drop shadows, window dragging, clipping rectangles, close buttons, and system taskbar.
7. **In-OS Code Editor (AdiIDE)**: Live code editor with keyword and literal syntax tokenization, instant compilation and execution via AdiPython, and contiguous disk persistence to `disk.img`.
8. **3D Graphics & Game Engines**:
   - **CastleAdiOS 3D**: First-person 3D DDA (Digital Differential Analysis) raycaster with 320 parallel rays, distance fog, real-time minimap, health HUD, and crosshair.
   - **StarFlight 3D**: Real-time 3D flight simulator with Euler perspective projection, terrain grids, navigational gates, and starfields.
   - **Cyber Citadel 3D**: Perspective wireframe architectural visualization with 12 Colonnade Pillars and central Quantum Core.
9. **Sovereign Cyber Interactive Suite**:
   - **Cosmic Entropy Oracle**: Hardware peripheral entropy harvester (`CSR_MCYCLE`, timer MMIO, mouse jitter) generating scientific and philosophical axioms.
   - **Baroque Polyphonic Synthesizer**: Algorithmic 4-part SATB counterpoint composer streaming voice frequencies to the PC speaker.
   - **DolDoc Hypertext Engine**: Rich text formatting with foreground/background colors, hyperlinks, buttons, and dynamic tree branching.

---

## 2. Architecture Diagram

```
+-------------------------------------------------------------------------------+
|                    AdiOS SOVEREIGN HARDWARE SIMULATION LAYER                  |
|              (High-Performance RV32IM Virtual Machine + MMIO Bus)             |
|                                                                               |
|   * 32-bit RISC-V CPU Core with Instruction Pre-Decode Caching                |
|   * RV32I Base ISA + RV32M Hardware Math (mul, mulh, div, divu, rem, remu)    |
|   * 64 MB Identity-Mapped Physical RAM (0x80000000 - 0x84000000)              |
|   * Memory-Mapped I/O Peripherals:                                            |
|       - 0x10000000: Serial UART Console (Tx / Rx FIFO)                        |
|       - 0x10000010: Real-Time Hardware Timer and Comparator                   |
|       - 0x10000040: Power Management Unit (Reboot / Poweroff)                 |
|       - 0x10000050: PC Speaker / Audio Tone Synthesizer                       |
|       - 0x10001000: Virtual ATA Block Storage Controller (disk.img)           |
|       - 0x20000000: 640x480 32-bit ARGB Linear Framebuffer (1.2 MB)           |
|       - 0x20130000: Display Controller & Hardware Mouse Registers             |
+---------------------------------------+---------------------------------------+
                                        |
+---------------------------------------v---------------------------------------+
|                       CORE BARE-METAL ASSEMBLY KERNEL                         |
|                                                                               |
|   * sched.s       : Preemptive Round-Robin Multi-Tasking Scheduler (TCBs)     |
|   * mem_manager.s : 16,384 Physical Page Frame Bitmap Allocator (4KB pages)   |
|   * vfs.s         : Zero-Fragmentation Contiguous Block Driver (AdiFS)        |
+---------------------------------------+---------------------------------------+
                                        |
+---------------------------------------v---------------------------------------+
|                    COMPILER PIPELINE & LANGUAGE RUNTIME                       |
|                                                                               |
|   * AdiPython     : Lexer, Parser, AST Engine, and Ring-0 Hardware Bridge     |
|   * Compiler IR   : Three-Address Code (TAC) & Control Flow Graphs (CFG)      |
|   * Optimizer     : Constant Folding, Strength Reduction, DCE, Peephole       |
|   * RegAlloc      : Linear Scan Register Allocator (27 RISC-V Registers)      |
|   * JIT Compiler  : Native RV32IM Machine Code Generator                      |
+---------------------------------------+---------------------------------------+
                                        |
+---------------------------------------v---------------------------------------+
|                    DESKTOP, GRAPHICS & SOVEREIGN ENGINES                      |
|                                                                               |
|   * Sovereign Desktop WM : Z-order Compositor, Windows, Taskbar, Apps         |
|   * AdiIDE Code Editor   : Syntax Highlighting, Compiler Run, Disk Save       |
|   * CastleAdiOS 3D       : First-Person 3D DDA Raycaster Dungeon Crawler      |
|   * StarFlight 3D        : 6-DOF Perspective Wireframe Flight Simulator       |
|   * Cyber Citadel 3D     : 3D Vector Architectural Sanctuary                  |
|   * Baroque Synthesizer  : 4-Part SATB Algorithmic Counterpoint Music         |
|   * Cosmic Oracle        : Hardware Entropy Divination & Philosophical Axioms |
|   * Sovereign Cyber Shell: Unified Interactive Command Terminal               |
+-------------------------------------------------------------------------------+
```

---

## 3. Subsystem Verification Matrix (30/30 Subsystems Passed)

The entire operating system is protected by a unified, automated 30-subsystem regression test harness (`python build.py --test`):

| # | Subsystem | Module | Description | Status |
|---|---|---|---|---|
| 1 | Simulation Layer | `vm/vm.py` | 64MB RAM, RV32M Math, Disk MMIO | **PASS (100%)** |
| 2 | Language Runtime | `adipython/runtime.py` | Ring-0 Hardware Bridge (`peek`, `poke`, `tone`) | **PASS (100%)** |
| 3 | JIT Compiler | `adipython/jit.py` | Native RV32IM JIT Code Generation | **PASS (100%)** |
| 4 | Disassembler | `toolchain/disasm.py` | RV32IM In-Memory Instruction Disassembly | **PASS (100%)** |
| 5 | Standard Library | `adipython/stdlib/` | Math, Memory, and High-Performance Collections | **PASS (100%)** |
| 6 | Hypertext Engine | `doldoc/doldoc.py` | DolDoc Universal Hypertext Engine & Links | **PASS (100%)** |
| 7 | 3D Software Rasterizer | `graphics/rasterizer3d.py` | Fixed-point 3D Transformations & Projection | **PASS (100%)** |
| 8 | Music Tracker | `sound/tracker.py` | PC Speaker Synthesizer & Note Sequences | **PASS (100%)** |
| 9 | Contiguous Filesystem | `fs/adifs.py` | AdiFS 512-byte Sector Contiguous Allocation | **PASS (100%)** |
| 10 | Bare-Metal CLI Shell | `kernel/asm_kernel.s` | Direct Assembly Shell with Disk Commands | **PASS (100%)** |
| 11 | Sovereign Window Manager | `desktop/window_manager.py` | Z-Order Multi-Window Desktop Compositor | **PASS (100%)** |
| 12 | In-OS Code Editor | `desktop/editor.py` | AdiIDE Syntax Highlighting, Run & Save | **PASS (100%)** |
| 13 | 3D Dungeon Crawler | `games/castle3d.py` | CastleAdiOS 3D DDA Raycaster Engine | **PASS (100%)** |
| 14 | Advanced Systems Stdlib | `adipython/stdlib/` | AVL/BST Trees, HashMaps, Min-Heaps, Matrix3D | **PASS (100%)** |
| 15 | Compiler & Optimizer | `adipython/optimizer.py` | TAC IR, CFG, DCE, Strength Reduction, RegAlloc | **PASS (100%)** |
| 16 | Assembly Kernel Suite | `kernel/sched.s` | Preemptive Scheduler, Dual-Heap PAlloc, VFS | **PASS (100%)** |
| 17 | Sovereign Cyber Suite | `holy/` | Cosmic Entropy Oracle, Baroque Synth, Citadel 3D | **PASS (100%)** |
| 18 | Networking & Comms Stack | `net/` | SLIP Framing, Ethernet II, ARP, IPv4, UDP, Telnet | **PASS (100%)** |
| 19 | Cyber Security & Crypto | `crypto/` | FIPS SHA-256, ChaCha20, Poly1305 AEAD, Disk Enc | **PASS (100%)** |
| 20 | Virtual Memory & MMU | `mmu/` | Sv32 2-Level Paging, 64-Entry TLB, AddressSpace | **PASS (100%)** |
| 21 | Process, Signals & IPC | `proc/` | TaskControlBlock, 32 Signals, Pipes, MLFQ, Syscall | **PASS (100%)** |
| 22 | In-OS C Toolchain | `compiler/` | C99 Lexer, Parser, RV32 Codegen, ELF32 Builder | **PASS (100%)** |
| 23 | Standard C Library | `libc/` | string, stdio (sprintf, streams), stdlib, math | **PASS (100%)** |
| 24 | Hardware Drivers & VirtIO | `drivers/` | Split Virtqueues, VirtIO Net/Blk, PCI, RTC | **PASS (100%)** |
| 25 | TCP/IP Transport Engine | `net/tcp.py` | RFC 793 3-Way Handshake, Flow Control, Teardown | **PASS (100%)** |
| 26 | Layer-7 Protocols | `net/protocols.py` | HTTP/1.1 Server/Router, DNS Resolver, DHCP DORA | **PASS (100%)** |
| 27 | POSIX Shell & Userland | `userland/` | Shell Pipelines, Redirection, CoreUtils Suite | **PASS (100%)** |
| 28 | SovereignSQL Database | `db/engine.py` | SQL Parser, ACID Transactions, WAL Recovery | **PASS (100%)** |
| 29 | Window Server & GUI | `ui/` | Canvas2D Vector Primitives, Widgets, Compositor | **PASS (100%)** |
| 30 | Windowing Desktop & Apps | `kernel/gui_kernel.s` | Interactive Graphical Desktop & Paint Studio | **PASS (100%)** |

---

## 4. Quick Start Guide

### Running the Full 30-Subsystem Regression Test Suite
```bash
python build.py --test
```

### Launching the Sovereign Cyber Shell (Interactive Command Terminal)
```bash
python build.py --shell
```
Available Shell Commands:
* `oracle [n]` — Consult the hardware entropy oracle for $n$ scientific/philosophical words.
* `axiom` — Generate a philosophical or scientific axiom.
* `synth [mode]` — Compose and synthesize an algorithmic 4-part baroque counterpoint piece (`Major`, `Minor`, `Dorian`, `Lydian`, `Mixolydian`).
* `citadel` — Render the 3D Cyber Citadel wireframe into the framebuffer.
* `palloc` — Display physical 4KB page frame allocator status (16,384 pages / 64MB).
* `tasks` / `ps` — Display active Task Control Blocks (TCBs) and scheduler states.
* `ls` — List contiguous files on the virtual hard disk via AdiFS.
* `cat <file>` — Read and display file contents directly from disk.
* `disk` — Display virtual disk superblock and drive geometry.
* `matrix` — Display sovereign cyberpunk cyberspace banner.

### Launching the CastleAdiOS 3D Dungeon Crawler
```bash
python build.py --castle
```
* **Controls**: `W/S` (Move forward/back), `A/D` (Turn left/right), `Q/E` (Strafe left/right), `Space` (Fire / Open).

### Launching the Sovereign Desktop GUI
```bash
python build.py --desktop
```

### Launching the StarFlight 3D Flight Simulator
```bash
python build.py --3d
```

### Executing an AdiPython Script
```bash
python build.py --run scripts/cube3d.ap
```

---

## 5. Repository Layout

```
adios/
|-- adipython/              # In-house systems programming language
|   |-- lexer.py            # Stream tokenizer
|   |-- parser.py           # Recursive-descent AST parser
|   |-- runtime.py          # Ring-0 hardware MMIO execution engine
|   |-- ir.py               # Three-Address Code & CFG representation
|   |-- ir_gen.py           # AST-to-IR lowering compiler
|   |-- optimizer.py        # Multi-pass optimization pipeline
|   |-- regalloc.py         # Linear scan physical register allocator
|   |-- jit.py              # Native RV32IM machine code generator
|   |-- disassembler.py     # RV32IM runtime disassembler
|   `-- stdlib/             # Advanced systems standard library
|       |-- trees.ap        # Balanced Binary Search Trees (AVL/BST)
|       |-- hashmap.ap      # Open-addressed hash table with linear probing
|       |-- heap.ap         # Binary Min-Heap Priority Queue
|       |-- matrix3d.ap     # Fixed-point 4x4 matrix & quaternion math
|       |-- memory_pool.ap  # Slab allocator & Arena scratchpad pools
|       `-- string_lib.ap   # Dynamic StringBuilder & string algorithms
|-- kernel/                 # Core bare-metal RISC-V assembly kernel
|   |-- sched.s             # Preemptive multi-tasking scheduler (TCBs)
|   |-- mem_manager.s       # Dual-heap 16,384 physical page frame allocator
|   |-- vfs.s               # Zero-fragmentation contiguous VFS & block driver
|   |-- gui_kernel.s        # Graphical windowing system & applications
|   |-- asm_kernel.s        # Bare-metal interactive CLI shell
|   `-- game3d.s            # Bare-metal assembly 3D vector engine
|-- holy/                   # Sovereign interactive cyber environment
|   |-- oracle.py           # Hardware entropy oracle & axiom generator
|   |-- hymn.py             # Algorithmic 4-part SATB polyphonic synthesizer
|   |-- sanctuary3d.py      # 3D Cyber Citadel & Quantum Core wireframe engine
|   `-- holy_shell.py       # Unified interactive Sovereign Cyber Shell
|-- net/                    # Networking & communications subsystem
|   |-- slip.py             # RFC 1055 SLIP packet framing driver
|   |-- ipv4.py             # Ethernet II, ARP, and IPv4 header engine
|   |-- transport.py        # ICMP echo, UDP sockets, and NetworkStack
|   |-- tcp.py              # RFC 793 Transmission Control Protocol engine
|   |-- protocols.py        # HTTP/1.1 Web Server, DNS Resolver, DHCP DORA
|   `-- telnet.py           # RFC 854 Sovereign Cyber Telnet server
|-- crypto/                 # In-house cryptographic subsystem
|   |-- sha256.py           # FIPS 180-4 SHA-256 & RFC 2104 HMAC-SHA256
|   |-- chacha20.py         # RFC 7539 ChaCha20 256-bit stream cipher
|   |-- poly1305.py         # RFC 7539 Poly1305 MAC & ChaCha20-Poly1305 AEAD
|   `-- disk_crypto.py      # Encrypted virtual disk block storage driver
|-- mmu/                    # Virtual memory & hardware MMU subsystem
|   |-- sv32.py             # RISC-V Sv32 2-level paging & hardware page faults
|   |-- tlb.py              # 64-entry fully associative TLB with LRU & sfence.vma
|   `-- address_space.py    # Process address space manager & 64MB identity maps
|-- proc/                   # Process, signals & IPC subsystem
|   |-- process.py          # TaskControlBlock & parent-child process lifecycle
|   |-- signals.py          # POSIX & Sovereign 32-signal dispatcher & sigreturn
|   |-- ipc.py              # Ring-buffer pipes, priority MQs, shm, mutexes
|   |-- scheduler.py        # MLFQ 4-band preemptive scheduler & priority boost
|   `-- syscall.py          # RISC-V ecall ABI system call dispatcher
|-- compiler/               # In-OS C99 / AdiC native self-hosting compiler
|   |-- c_lexer.py          # Stream tokenizer for C keywords, literals, ops
|   |-- c_parser.py         # Recursive-descent AST parser with type system
|   |-- c_codegen.py        # Native RV32IM assembly code generator
|   `-- elf32.py            # Standard RISC-V ELF32 executable binary builder
|-- libc/                   # Zero-dependency Standard C Library
|   |-- string.py           # strlen, strcmp, strstr, strcpy, memcpy, memset
|   |-- stdio.py            # sprintf, snprintf, fopen, fread, fwrite, fseek
|   |-- stdlib.py           # malloc, free, calloc, realloc, atoi, qsort, rand
|   `-- math.py             # sin, cos, tan, sqrt, pow, exp, log, fabs
|-- drivers/                # Hardware device drivers & bus architecture
|   |-- virtio_ring.py      # VirtIO v1.0 standard split virtqueues
|   |-- virtio_blk.py       # VirtIO block storage sector I/O driver
|   |-- virtio_net.py       # VirtIO network adapter RX/TX driver
|   |-- pci.py              # PCI Host controller & configuration space
|   `-- rtc.py              # Motorola MC146818 CMOS Real-Time Clock
|-- userland/               # POSIX & sovereign userland utilities & shell
|   |-- coreutils.py        # cat, ls, cp, mv, rm, touch, wc, grep, sha256sum
|   `-- sh.py               # POSIX shell with pipelines and redirections
|-- db/                     # SovereignSQL relational database engine
|   `-- engine.py           # SQL parser, ACID transactions, WAL recovery
|-- ui/                     # Vector GUI toolkit & Window Server
|   |-- canvas2d.py         # 2D vector primitives, clipping, alpha blend
|   |-- widgets.py          # Hierarchy, Button, TextBox, Slider, Window
|   `-- window_server.py    # Multi-window compositor & event router
|-- desktop/                # Sovereign Desktop Environment
|   |-- window_manager.py   # Multi-window Z-order compositor
|   |-- desktop.py          # Taskbar, Start Pill, and app integration
|   `-- editor.py           # In-OS AdiIDE code editor with syntax highlighting
|-- games/                  # 3D Games & Graphics
|   |-- castle3d.py         # CastleAdiOS 3D DDA raycaster engine
|   `-- flight3d.py         # StarFlight 3D perspective flight simulator
|-- fs/                     # Filesystem
|   `-- adifs.py            # AdiFS contiguous block filesystem driver
|-- doldoc/                 # DolDoc Hypertext Subsystem
|   `-- doldoc.py           # Universal hypertext markup parser & renderer
|-- sound/                  # Audio Subsystems
|   `-- tracker.py          # PC Speaker music tracker & synthesizer
|-- vm/                     # In-house hardware simulation layer
|   |-- vm.py               # 64MB RV32IM CPU core with decode cache
|   `-- display.py          # 640x480 Framebuffer window & mouse driver
|-- toolchain/              # Toolchain & Assembler
|   |-- assembler.py        # Two-pass RV32I/M assembler & linker
|   `-- disasm.py           # RV32IM disassembler
|-- tests/                  # 30 Automated Subsystem Test Suites
`-- build.py                # Unified build, test, and launcher driver
```

---

## 6. License

AdiOS is open-source software released under the MIT License.
