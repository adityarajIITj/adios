# AdiOS (v1.0.0 Sovereign Stable Release)

**AdiOS** is a minimalist, high-performance, bare-metal operating system, sovereign graphical desktop environment, 3D vector graphics engine, Type-1 hypervisor, and in-house systems programming language (**AdiPython**) designed and implemented from first principles for the 32-bit RISC-V (RV32IM) architecture.

Inspired by the sovereign, ring-0, zero-bloat computing philosophy of Terry A. Davis's legendary operating system architecture, AdiOS reimagines sovereign computing within a rigorous modern mathematical, cryptographic, and cyber-engineering framework.

- **Release Status**: `v1.0.0-LTS (First Stable Release)`
- **Target Architecture**: RISC-V 32-bit (RV32IM + H-Extension)
- **Codebase Scale**: **26,970 Lines of Code (>0.26 Lakh LOC)**
- **Verification Harness**: **40/40 Automated Subsystems Passing (100% Success)**
- **Dependencies**: None. Pure standard Python 3 simulation harness and direct RV32 bare-metal assembly.

---

## 1. Executive Summary & Design Tenets

AdiOS is engineered without third-party libraries, bloated frameworks, or black-box drivers. Every line of code -- from the cycle-accurate RV32IM CPU core with instruction pre-decode caching to the Type-1 bare-metal hypervisor, TLS 1.3 cryptographic record layer, software OpenGL 1.1 rasterizer, and in-OS C99 compiler -- is written and verified from first principles.

### Key Architectural Tenets:
1. **Sovereign Ring-0 Freedom**: The user and application have unrestricted, zero-overhead access to hardware registers, linear framebuffers, memory-mapped I/O, and CPU states.
2. **Absolute Determinism**: Instantaneous sub-second boot times, cycle-accurate instruction timing, zero garbage-collection pauses, and contiguous non-fragmented storage layouts.
3. **Cryptographic & Network Autonomy**: Complete in-house implementation of FIPS SHA-256, RFC 7539 ChaCha20-Poly1305 AEAD, RFC 793 TCP/IP, RFC 8446 TLS 1.3, and RFC 1035 DNS.
4. **Self-Contained Toolchain**: In-OS C99 compiler emitting native ELF32 binaries, custom two-pass RV32IM assembler, disassembler, GDB Remote Serial Protocol debugger, and dynamic bytecode VM.
5. **Unified Verification**: Every commit is strictly guarded by an automated 40-subsystem regression harness verifying hardware, kernel, protocols, graphics, compilers, and spatial engines.

---

## 2. Full Architecture Blueprint

```text
+=======================================================================================+
|                     AdiOS HARDWARE SIMULATION LAYER & BUS (RV32IM)                    |
|                                                                                       |
|   - 32-bit RISC-V CPU Core with Fast Instruction Pre-Decode Cache (15-30 MIPS)        |
|   - RV32I Base ISA + RV32M Hardware Math (mul, mulh, div, divu, rem, remu)            |
|   - 64 MB Physical RAM Identity-Mapped [0x80000000 - 0x84000000]                      |
|   - Memory-Mapped I/O (MMIO) Peripheral Architecture:                                 |
|       * 0x10000000: 16550 Serial UART Console (Tx / Rx FIFO)                          |
|       * 0x10000010: Real-Time Hardware Timer & Clock Comparator                       |
|       * 0x10000040: Power Management Unit (Soft Reboot / ACPI Poweroff)               |
|       * 0x10000050: PC Speaker & Tone Synthesizer MMIO                                |
|       * 0x10001000: Virtual ATA Block Storage Controller (512B sectors, disk.img)     |
|       * 0x20000000: 640x480 32-bit ARGB Linear Framebuffer (1.2 MB VRAM)              |
|       * 0x20130000: Display Controller & Hardware Mouse Status Registers              |
+===========================================+===========================================+
                                            |
+===========================================v===========================================+
|                     CORE BARE-METAL KERNEL & HARDWARE MANAGEMENT                      |
|                                                                                       |
|   * sched.s       : Preemptive Round-Robin Scheduler with 34-Register Context Switch  |
|   * mem_manager.s : 16,384 Physical Page Frame Bitmap Allocator (64MB RAM Pool)       |
|   * vfs.s         : Contiguous DMA Block Filesystem Driver (AdiFS)                    |
|   * gui_kernel.s  : Direct Framebuffer Window Compositor & Event Loop                 |
+===========================================+===========================================+
                                            |
+===========================================v===========================================+
|                      THE 26 SOVEREIGN COMPUTING BLOCKS (A - Z)                        |
|                                                                                       |
|   [A] Systems Stdlib    : AVL/BST Trees, HashMaps, Min-Heaps, Fixed-Point Matrix3D    |
|   [B] Compiler IR & Opt : TAC IR, Control Flow Graphs, DCE, Linear Scan RegAlloc      |
|   [C] Assembly Kernel   : Dual-Heap PAlloc, Preemption, Task Control Blocks           |
|   [D] Sovereign Cyber   : Entropy Oracle, Algorithmic Baroque Synth, Citadel 3D       |
|   [E] Networking Stack  : SLIP, Ethernet II, ARP, IPv4, UDP Sockets, Telnet Server   |
|   [F] Cyber Security    : FIPS SHA-256, ChaCha20, Poly1305 AEAD, Disk Encryption      |
|   [G] Virtual Memory    : RISC-V Sv32 2-Level Paging, 64-Entry TLB, Address Spaces    |
|   [H] Process & Signals : TCB Lifecycle, 32-Signal Dispatcher, MLFQ, ecall ABI        |
|   [I] In-OS C Compiler  : C99 Lexer, Parser, RV32 Codegen, ELF32 Binary Builder      |
|   [J] Standard C Lib    : Zero-Dependency libc (stdio, stdlib, string, math)          |
|   [K] Hardware Drivers  : VirtIO Split Virtqueues (Net/Blk), PCI Host, CMOS RTC       |
|   [L] TCP/IP Engine     : RFC 793 11-State FSM, 3-Way Handshake, Flow Control, FIN    |
|   [M] Layer-7 Protocols : HTTP/1.1 Server/Router, RFC 1035 DNS, RFC 2131 DHCP DORA    |
|   [N] POSIX Userland    : Pipelines, Redirection, Unix CoreUtils (cat, grep, ls, wc)  |
|   [O] SovereignSQL      : Typed Relational DB, SQL Parser, ACID Transactions, WAL     |
|   [P] Window Server GUI : Canvas2D Vector Primitives, Alpha Blend, Widget Toolkit     |
|   [Q] Multi-Core SMP    : Multi-Hart, CLINT MSIP IPI, TicketLock, Work-Stealing       |
|   [R] DSP & Audio Synth : Oscillators (Sine, Saw, PWM), ADSR, Biquad Filter, WAV      |
|   [S] Native Storage    : Microsoft FAT32 & Linux Ext2 Filesystem Drivers             |
|   [T] TLS 1.3 Crypto    : RFC 8446 Record Layer, HKDF Key Schedule, AEAD Encryption   |
|   [U] In-OS Debugger    : GDB Remote Serial Protocol (RSP), Breakpoints, Stack Unwind |
|   [V] Software OpenGL   : Fixed-Function Pipeline, Matrix Stack, Barycentric Z-Buffer |
|   [W] Spatial Physics   : Rigid Dynamics, Restitution Impulses, 8-Way Octree Trees    |
|   [X] Web Browser       : HTML Parser, DOM Tree, CSS Cascade Engine, Box Model Layout |
|   [Y] Bytecode Lisp VM  : S-Expression Compiler, 16-Opcode Stack VM, Recursive Frames |
|   [Z] Hypervisor Matrix : Type-1 RISC-V Hypervisor, Stage-2 Paging, Master Matrix     |
+=======================================================================================+
```

---

## 3. Subsystem Verification Matrix (40/40 Subsystems Passed)

The entire operating system is protected by a unified, automated 40-subsystem regression test harness (`python build.py --test`):

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
| 30 | Multi-Core SMP & IPI | `smp/` | Harts, CLINT MSIP IPI, Work-Stealing Scheduler | **PASS (100%)** |
| 31 | Digital Audio Synthesis | `dsp/` | Polyphonic Oscillators, ADSR, Biquad, WAV | **PASS (100%)** |
| 32 | Native Storage Suite | `vfs/` | Ext2 Superblock & Inodes, FAT32 Cluster Chains | **PASS (100%)** |
| 33 | TLS 1.3 Cryptography | `crypto/tls13.py` | RFC 8446 Record Layer, HKDF, Finished Tag | **PASS (100%)** |
| 34 | In-OS Debugger & GDB | `debug/gdb_stub.py` | GDB Remote Serial Protocol, Breakpoints, Unwind | **PASS (100%)** |
| 35 | Software OpenGL 1.1 | `gl/gl_core.py` | Matrix Stack, Perspective, Barycentric, Z-Buf | **PASS (100%)** |
| 36 | 3D Spatial Physics | `spatial/physics3d.py`| Rigid Dynamics, Impulse Restitution, Octree | **PASS (100%)** |
| 37 | Web Engine & Layout | `browser/layout_engine.py`| HTML/CSS DOM Tree, Box Model Flow, Links | **PASS (100%)** |
| 38 | Dynamic Bytecode VM | `bytecode/lisp_vm.py`| S-Expression Compiler, Call Frames, Recursion | **PASS (100%)** |
| 39 | Type-1 Hypervisor | `core/hypervisor.py` | H-Extension CSRs, Stage-2 Nested Paging (SLAT)| **PASS (100%)** |
| 40 | Windowing Desktop & Apps | `kernel/gui_kernel.s` | Interactive Graphical Desktop & Paint Studio | **PASS (100%)** |

---

## 4. Comprehensive Feature Catalogue (Blocks A - Z)

### Block A -- Advanced Systems Data Structures & Stdlib
- **Balanced Binary Search Trees (`trees.ap`)**: AVL trees with deterministic left/right rotations maintaining strict O(log N) lookups; recursive in-order traversals.
- **Open-Addressed Hash Table (`hashmap.ap`)**: Murmur3-inspired integer hashing, linear probing collision resolution, dynamic prime table sizing.
- **Binary Min-Heap (`heap.ap`)**: Complete binary tree array representation with sift-up and sift-down operations powering the kernel priority scheduler.
- **Fixed-Point 3D Mathematics (`matrix3d.ap`)**: 16.16 fixed-point 4x4 transformation matrices, yaw/pitch/roll rotations, normalized vector cross products.

### Block B -- Compiler IR, CFG & Multi-Pass Optimizer
- **Three-Address Code (TAC)**: Intermediate representation decoupling frontend AST from target machine code (`x = y op z`).
- **Control Flow Graph (CFG)**: Basic block partitioning with directed edge tracking and loop detection.
- **Optimization Passes**: Constant folding, algebraic strength reduction (e.g. x * 8 -> x << 3), dead code elimination, and instruction peephole tuning.
- **Linear Scan Register Allocator**: Computes variable live intervals and assigns across 27 general-purpose physical RISC-V registers, inserting spill/reload instructions when pressure exceeds capacity.

### Block C -- Core Bare-Metal Assembly Kernel
- **Preemptive Scheduler (`sched.s`)**: Context switches all 32 integer registers, Program Counter (`sepc`), and status registers (`sstatus`) upon timer tick interrupt.
- **Dual-Heap Physical Allocator (`mem_manager.s`)**: Manages 16,384 4KB page frames (64MB) using bitmap allocation and buddy-system coalescing.
- **VFS Contiguous Block Driver (`vfs.s`)**: Sector-level direct DMA transfers to virtual ATA disk images.

### Block D -- Sovereign Cyber Interactive Suite
- **Cosmic Entropy Oracle (`oracle.py`)**: Hardware entropy harvester collecting uninitialized RAM jitter, timer ticks, and mouse entropy to seed algorithmic philosophical axiom generation.
- **Baroque Polyphonic Synthesizer (`hymn.py`)**: Algorithmic 4-part SATB counterpoint generator observing Johann Sebastian Bach's voice leading rules (preventing parallel fifths and octaves) rendered via tone MMIO.
- **Cyber Citadel 3D (`sanctuary3d.py`)**: Perspective wireframe rendering of the Sovereign Sanctuary with 12 Doric colonnade pillars and central glowing core.

### Block E -- RFC-Compliant Networking & Communications
- **SLIP Framing Driver (`slip.py`)**: RFC 1055 byte-stuffed serial framing (`0xC0` END, `0xDB 0xDC` ESC).
- **Ethernet & IPv4 Stack (`ipv4.py`, `transport.py`)**: ARP request/reply cache, IPv4 packet routing, ICMP echo responder, UDP socket demultiplexing.
- **Sovereign Telnet Server (`telnet.py`)**: RFC 854 remote interactive command shell over virtual sockets.

### Block F -- Advanced Cyber Security & Cryptography
- **FIPS 180-4 SHA-256 (`sha256.py`)**: 64-round cryptographic hashing and RFC 2104 HMAC-SHA256 authenticated message authentication.
- **RFC 7539 ChaCha20 Stream Cipher (`chacha20.py`)**: 256-bit symmetric encryption with 64-bit quarter-round matrix permutation.
- **RFC 7539 Poly1305 AEAD (`poly1305.py`)**: Authenticated Encryption with Associated Data (AEAD) generating 128-bit authentication tags.
- **Encrypted Block Storage (`disk_crypto.py`)**: Sector-level on-the-fly hardware block encryption.

### Block G -- Virtual Memory & Sv32 MMU
- **RISC-V Sv32 Paging Engine (`sv32.py`)**: 2-level hierarchical page table walks translating 32-bit Virtual Addresses to Physical Addresses with 4KB pages and 4MB megapages.
- **Associative TLB (`tlb.py`)**: 64-entry fully associative Translation Lookaside Buffer with LRU eviction and `sfence.vma` address space invalidation.
- **Address Space Manager (`address_space.py`)**: Per-process isolated address spaces and kernel identity mappings.

### Block H -- Process Lifecycle, Signals, IPC & Syscalls
- **Task Control Block (`process.py`)**: Process states (`READY`, `RUNNING`, `BLOCKED`, `ZOMBIE`), parent-child tree hierarchy, process IDs.
- **32-Signal Dispatcher (`signals.py`)**: Synchronous and asynchronous signal handling, signal masks, pending queues, and `sigreturn` stack frame restoration.
- **Inter-Process Communication (`ipc.py`)**: Circular ring-buffer anonymous pipes, priority message queues, shared memory, and mutual exclusion locks.
- **RISC-V Syscall ABI (`syscall.py`)**: Standard RISC-V `ecall` convention dispatching POSIX-compatible system calls (`read`, `write`, `fork`, `exec`, `yield`, `exit`).

### Block I -- In-OS C99 / AdiC Self-Hosting Compiler
- **C Lexer & Parser (`c_lexer.py`, `c_parser.py`)**: Full lexical stream analysis and recursive-descent parsing for C99 expressions, types, and control flow.
- **Native RV32IM Codegen (`c_codegen.py`)**: Lowers typed AST into register-allocated RISC-V assembly instructions.
- **ELF32 Binary Builder (`elf32.py`)**: Packages compiled assembly into standard ELF executable format with ELF Header, Section Headers (`.text`, `.data`, `.rodata`, `.bss`), and Symbol Tables.

### Block J -- Zero-Dependency Standard C Library
- **`string.h` (`libc/string.py`)**: `strlen`, `strcmp`, `strncmp`, `strcpy`, `strncpy`, `strcat`, `strstr`, `memcpy`, `memmove`, `memset`.
- **`stdio.h` (`libc/stdio.py`)**: Formatted printing (`sprintf`, `snprintf`), file stream buffers (`fopen`, `fread`, `fwrite`, `fseek`, `fclose`).
- **`stdlib.h` (`libc/stdlib.py`)**: Buddy-heap allocator (`malloc`, `calloc`, `realloc`, `free`), numerical conversions (`atoi`, `itoa`), quicksort (`qsort`), pseudo-random generator (`rand`).
- **`math.h` (`libc/math.py`)**: Fixed-point and IEEE floating-point trigonometry (`sin`, `cos`, `tan`), power (`pow`, `sqrt`), logarithms (`log`, `exp`), and absolute values.

### Block K -- Hardware Drivers & VirtIO Bus Architecture
- **VirtIO v1.0 Ring Buffers (`virtio_ring.py`)**: Standard split virtqueues with Descriptor Tables, Available Rings, and Used Rings.
- **VirtIO Block Driver (`virtio_blk.py`)**: Asynchronous sector-level storage device requests.
- **VirtIO Network Adapter (`virtio_net.py`)**: High-throughput packet receive and transmit virtqueues.
- **PCI Host Controller (`pci.py`)**: Type-0 and Type-1 PCI configuration space address decoding and device discovery.
- **Motorola MC146818 RTC (`rtc.py`)**: BCD-decoded hardware CMOS real-time calendar and clock.

### Block L -- Transmission Control Protocol (TCP/IP)
- **RFC 793 State Machine (`net/tcp.py`)**: 11 standard states (`CLOSED`, `LISTEN`, `SYN_SENT`, `SYN_RECEIVED`, `ESTABLISHED`, `FIN_WAIT_1`, `FIN_WAIT_2`, `CLOSE_WAIT`, `CLOSING`, `LAST_ACK`, `TIME_WAIT`).
- **Flow Control & Congestion**: Sequence and acknowledgment tracking, sliding window advertised receive buffer, selective acknowledgment, and retransmission timeouts.

### Block M -- Layer-7 Application Protocols
- **HTTP/1.1 Web Server (`net/protocols.py`)**: Full request parser, URI routing, MIME headers, `Content-Length` framing, and 404 response handler.
- **RFC 1035 DNS Resolver (`net/protocols.py`)**: UDP query builder, response parser, and DNS label pointer decompression (`0xC00C`).
- **RFC 2131 DHCP Client (`net/protocols.py`)**: Four-phase DORA state machine (`INIT` -> `SELECTING` -> `REQUESTING` -> `BOUND`) acquiring IP, subnet mask, and gateway.

### Block N -- POSIX Userland Utilities & Command Shell
- **Unix CoreUtils (`userland/coreutils.py`)**: Zero-dependency implementations of `cat`, `ls`, `cp`, `mv`, `rm`, `touch`, `echo`, `grep`, `wc`, `head`, `tail`, `sha256sum`, `uname`.
- **Command Shell Interpreter (`userland/sh.py`)**: Environment variable expansion (`$VAR`), multi-stage piping (`cmd1 | cmd2 | cmd3`), and file redirection (`>`, `>>`).

### Block O -- SovereignSQL Relational Database Engine
- **Relational Storage Engine (`db/engine.py`)**: Strongly-typed schemas (`INT`, `FLOAT`, `TEXT`, `BOOL`).
- **SQL Parser**: Supports `CREATE TABLE`, `INSERT INTO`, `SELECT ... WHERE`, `UPDATE ... WHERE`, `DELETE FROM`.
- **ACID Transactions & WAL**: `BEGIN`, `COMMIT`, and `ROLLBACK` restoring transactional snapshots; write-ahead log recovery.

### Block P -- Sovereign Window Server & 2D Vector GUI
- **Canvas2D Graphics Toolkit (`ui/canvas2d.py`)**: 32-bit ARGB framebuffer rasterizer, Bresenham line drawing, anti-aliased circles, solid/rounded rectangles, scissor clipping stacks, and alpha blending.
- **Widget Hierarchy (`ui/widgets.py`)**: `Label`, `Button`, `TextBox` (text editing, backspace, focus), `Slider` (draggable value tracking), `WindowWidget` (titlebar drag, minimize, close).
- **Window Server & Compositor (`ui/window_server.py`)**: Multi-window Z-order compositor, active window promotion, mouse pointer rendering, event dispatch.

### Block Q -- Multi-Core Symmetric Multiprocessing (SMP)
- **Multi-Hart Hardware Model (`smp/cpu_core.py`)**: Multi-threaded RISC-V execution contexts, per-CPU caches, and Core Local Interruptor (CLINT) MSIP registers.
- **Synchronization**: Fair FIFO `TicketLock` preventing thread starvation.
- **Inter-Processor Interrupts (IPI)**: Cross-core remote function dispatch (`smp_call_function`).
- **Work-Stealing Scheduler (`smp/smp_scheduler.py`)**: Per-core runqueues with automatic thread migration and idle-core work stealing.

### Block R -- Digital Audio Synthesis & DSP Studio
- **Oscillators (`dsp/synth.py`)**: Sine, Square (PWM), Triangle, Sawtooth, and White Noise generators.
- **Envelope & Filter**: 4-stage ADSR envelope generator (Attack, Decay, Sustain, Release) and 2-Pole Resonant Low-Pass Biquad Filter.
- **PCM & WAV Packaging**: Polyphonic voice mixer serializing 16-bit 44.1kHz CD-quality RIFF/WAV audio files.

### Block S -- Extensible Native Storage Architecture
- **Microsoft FAT32 Driver (`vfs/fat32.py`)**: BIOS Parameter Block (BPB) parsing, File Allocation Table (FAT) cluster chain traversal, 32-byte directory entry decoding (8.3 filenames, size, cluster pointers).
- **Linux Ext2 Driver (`vfs/ext2.py`)**: Superblock verification (Magic `0xEF53`), Block Group Descriptors (BGD), Inode table traversal (direct blocks `i_block[0..11]`), directory records (`ext2_dir_entry_2`).

### Block T -- RFC 8446 Transport Layer Security (TLS 1.3)
- **Record Layer Framing (`crypto/tls13.py`)**: Packs and unpackages TLS records (`handshake`, `application_data`, `alert`).
- **RFC 5869 HKDF Key Schedule**: Computes `early_secret`, `handshake_secret`, and `master_secret`, deriving client/server handshake and application write keys.
- **Authenticated Encryption**: ChaCha20-Poly1305 AEAD record encryption with sequence number nonces and Finished HMAC-SHA256 authentication tags.

### Block U -- In-OS Debugger & GDB Remote Serial Protocol
- **GDB Remote Protocol (`debug/gdb_stub.py`)**: `$packet#checksum` encoding, register inspection (`g`), memory reading/writing (`m`/`M`), and software breakpoints (`Z0`/`z0`) injecting `ebreak` opcodes.
- **Call Stack Unwinder**: Reconstructs frame pointers (`s0`/`fp`) and return addresses (`ra`) to resolve function backtraces.

### Block V -- Software OpenGL 1.1 3D Graphics Engine
- **Matrix Stack Pipeline (`gl/gl_core.py`)**: `GL_MODELVIEW` and `GL_PROJECTION` stacks, `glLoadIdentity`, `glPushMatrix`, `glPopMatrix`, `glTranslatef`, `glScalef`, `gluPerspective`.
- **Rasterization & Depth Buffer**: Barycentric coordinate triangle rasterizer with 32-bit floating-point Z-buffering (depth testing), Gouraud color interpolation, and Blinn-Phong lighting.

### Block W -- Cyberpunk Spatial Environment & 3D Physics
- **Vector & Quaternion Math (`spatial/physics3d.py`)**: 3D vector operations (dot, cross, norm) and orientation quaternions.
- **Rigid Body Dynamics**: Symplectic Euler numerical integrator computing linear velocity and position under gravity and forces.
- **Impulse Collisions**: Sphere-sphere collision resolution with elastic restitution coefficients.
- **Hierarchical Octree**: 8-way spatial subdivision tree accelerating broad-phase spatial queries from O(N^2) to O(N log N).

### Block X -- Web Engine & Hypertext Layout Browser
- **HTML/XML Parser (`browser/layout_engine.py`)**: Tokenizes tags, attributes, and text nodes into an in-memory Document Object Model (DOM) tree.
- **CSS Cascade Engine**: Parses stylesheet rules and cascades calculated styles down DOM nodes.
- **Box Model Layout**: Calculates geometry for block and inline formatting contexts; extracts clickable hyperlink hitboxes.

### Block Y -- Sovereign Dynamic Bytecode VM & Lisp Engine
- **S-Expression Parser (`bytecode/lisp_vm.py`)**: Tokenizes and parses recursive Lisp AST forms.
- **Bytecode Compiler**: Lowers forms into a 16-opcode stack-based Virtual Machine ISA with jump relocation.
- **Virtual Machine Runtime**: Activation call frames, local variable scoping, arithmetic evaluation, and recursive execution (e.g. factorial/fibonacci).

### Block Z -- Type-1 Hypervisor & Master Integration Matrix
- **RISC-V H-Extension Hypervisor (`core/hypervisor.py`)**: Hardware virtualization supporting Virtual Supervisor (VS) and Virtual User (VU) modes, hypervisor CSRs (`hstatus`, `hedeleg`, `hideleg`, `hgatp`).
- **Stage-2 Nested Paging (SLAT)**: Translates Guest Physical Addresses (GPA) to Host Physical Addresses (HPA) with page-fault trapping.
- **VM-Exit Trapping**: Intercepts guest MMIO accesses, virtualizes virtual devices, advances guest PC, and resumes execution.
- **Master Sovereign System Matrix (`core/system_matrix.py`)**: Automated cross-subsystem orchestration test verifying MMU, SMP, Crypto, Storage, Graphics, Physics, Web, and Bytecode engines concurrently.

---

## 5. Quick Start Guide

### Running the Full 40-Subsystem Regression Test Suite
```bash
python build.py --test
```

### Launching the Bare-Metal Assembly Desktop (Interactive GUI)
```bash
python build.py
```
Contains:
* Interactive Paint Studio (click swatches to paint, click [CLEAR] to wipe).
* Bare-Metal Calculator (hardware RISC-V integer arithmetic: 7 + 5 = 12).
* Taskbar with Start Pill, hardware clock, and drop-down menu.

### Launching the Sovereign Cyber Shell (Interactive Command Terminal)
```bash
python build.py --shell
```
Available Shell Commands:
* `oracle [n]` -- Consult the hardware entropy oracle for n scientific/philosophical words.
* `axiom` -- Generate a philosophical or scientific axiom.
* `synth [mode]` -- Compose and synthesize an algorithmic 4-part baroque counterpoint piece (`Major`, `Minor`, `Dorian`, `Lydian`, `Mixolydian`).
* `citadel` -- Render the 3D Cyber Citadel wireframe into the framebuffer.
* `palloc` -- Display physical 4KB page frame allocator status (16,384 pages / 64MB).
* `tasks` / `ps` -- Display active Task Control Blocks (TCBs) and scheduler states.
* `ls` -- List contiguous files on the virtual hard disk via AdiFS.
* `cat <file>` -- Read and display file contents directly from disk.
* `disk` -- Display virtual disk superblock and drive geometry.
* `matrix` -- Display sovereign cyberpunk cyberspace banner.

### Launching the CastleAdiOS 3D Dungeon Crawler
```bash
python build.py --castle
```
* **Controls**: `W/S` (Move forward/back), `A/D` (Turn left/right), `Q/E` (Strafe left/right), `Space` (Fire / Open).

### Launching the Sovereign Multi-Window Desktop
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

## 6. Complete Repository Layout

```text
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
|   |-- tls13.py            # RFC 8446 TLS 1.3 Record Layer & HKDF Key Schedule
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
|-- libc/                   # Zero-Dependency Standard C Library
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
|-- smp/                    # Multi-Core SMP & Microkernel IPC
|   |-- cpu_core.py         # Harts, CLINT MSIP IPI, TicketLock
|   `-- smp_scheduler.py    # Work-stealing multi-queue task scheduler
|-- desktop/                # Sovereign Desktop Environment
|   |-- window_manager.py   # Multi-window Z-order compositor
|   |-- desktop.py          # Taskbar, Start Pill, and app integration
|   `-- editor.py           # In-OS AdiIDE code editor with syntax highlighting
|-- games/                  # 3D Games & Graphics
|   |-- castle3d.py         # CastleAdiOS 3D DDA raycaster engine
|   `-- flight3d.py         # StarFlight 3D perspective flight simulator
|-- fs/                     # Filesystem
|   `-- adifs.py            # AdiFS contiguous block filesystem driver
|-- vfs/                    # Native Storage Architecture
|   |-- fat32.py            # Microsoft FAT32 filesystem driver
|   `-- ext2.py             # Linux Ext2 filesystem driver
|-- doldoc/                 # DolDoc Hypertext Subsystem
|   `-- doldoc.py           # Universal hypertext markup parser & renderer
|-- sound/                  # Audio Subsystems
|   `-- tracker.py          # PC Speaker music tracker & synthesizer
|-- dsp/                    # Digital Audio Synthesis & DSP Studio
|   `-- synth.py            # Oscillators, ADSR, Biquad filter, WAV
|-- vm/                     # In-house hardware simulation layer
|   |-- vm.py               # 64MB RV32IM CPU core with decode cache
|   `-- display.py          # 640x480 Framebuffer window & mouse driver
|-- toolchain/              # Toolchain & Assembler
|   |-- assembler.py        # Two-pass RV32I/M assembler & linker
|   `-- disasm.py           # RV32IM disassembler
|-- debug/                  # In-OS Debugger & GDB Remote Serial Protocol
|   `-- gdb_stub.py         # RSP server, breakpoints, call stack unwinder
|-- gl/                     # Software OpenGL 1.1 3D Graphics Engine
|   `-- gl_core.py          # Fixed-function pipeline, matrix stack, Z-buffer
|-- spatial/                # 3D Physics Engine & Spatial Partitioning
|   `-- physics3d.py        # Rigid dynamics, impulse restitution, Octree
|-- browser/                # Web Engine & Hypertext Layout Browser
|   `-- layout_engine.py    # HTML/CSS parser, DOM tree, Box Model flow
|-- bytecode/               # Sovereign Dynamic Bytecode VM & Lisp Engine
|   `-- lisp_vm.py          # S-Expression compiler, call frames, stack VM
|-- core/                   # Type-1 Hypervisor & Master Integration
|   |-- hypervisor.py       # RISC-V H-Extension, Stage-2 nested paging (SLAT)
|   `-- system_matrix.py    # Cross-subsystem autonomous verification
|-- tests/                  # 40 Automated Subsystem Test Suites
`-- build.py                # Unified build, test, and launcher driver
```

---

## 7. License

AdiOS is sovereign, open-source software released under the **MIT License**.