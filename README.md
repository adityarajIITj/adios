# AdiOS (v0.1.0-alpha)

A minimalist, bare-metal operating system and micro-simulation layer implemented for the 32-bit RISC-V (RV32I/M) instruction set architecture.

---

## 1. Overview

AdiOS is an educational, research-oriented operating system built from first principles. It decouples the core computer science primitives of an operating system—task scheduling, memory allocation, trap handling, and userland execution—from modern physical hardware driver complexity.

Rather than targeting proprietary chipset interfaces (such as UEFI, xHCI, or NVMe protocols), AdiOS executes on a purpose-built paravirtualization layer. The host simulation environment exposes clean Memory-Mapped I/O (MMIO) registers to the bare-metal kernel, allowing direct execution of low-level algorithms without hardware bloat.

---

## 2. System Architecture

```
+-------------------------------------------------------------------------+
|                        HOST SIMULATION LAYER                            |
|       (Python / Native C RISC-V Hardware Simulator + MMIO Bus)          |
|                                                                         |
|   * 32-bit RISC-V Core (32 Registers, Program Counter, Trap Engine)     |
|   * 32 MB Virtual Physical RAM (8,192 Pages of 4 KB)                    |
|   * Memory-Mapped I/O Peripherals:                                      |
|       - 0x10000000: Serial UART Console (Tx / Rx Registers)             |
|       - 0x10000010: Real-Time Hardware Timer and Comparator Registers   |
|       - 0x10000040: Power Management Unit (Reboot / Poweroff Signals)   |
+------------------------------------+------------------------------------+
                                     | Machine Instructions & Traps
+------------------------------------v------------------------------------+
|                         AdiOS BARE-METAL KERNEL                         |
|                                                                         |
|   * boot.s       : Bootstrap sequence, stack init, trap vector setup    |
|   * memory.c     : Bitmap-managed physical page frame allocator (4 KB)  |
|   * scheduler.c  : Preemptive, timer-driven Round-Robin task scheduler  |
|   * shell.c      : Interactive command interpreter and runtime monitor  |
|   * uart.c       : MMIO serial driver and formatted I/O (printf)        |
+-------------------------------------------------------------------------+
```

---

## 3. Core Subsystems

### 3.1 Bootstrap and Trap Vector
Execution begins at base address `0x80000000`. The bootstrap routine initializes the stack pointer at `0x81000000` (16 MB mark), configures the Machine Trap-Vector Base-Address (`mtvec`), enables Machine Timer Interrupts (`mie.MTIE`), and transitions control to the kernel main entrypoint.

### 3.2 Preemptive Multitasking Scheduler
The kernel incorporates a preemptive Round-Robin scheduler driven by machine timer interrupts (`mcause = 0x80000007`):
* Context switching preserves the full 32-register execution frame into the current task's Process Control Block (PCB).
* Timer compare registers (`mtimecmp`) are dynamically re-armed on every quantum expiration (50,000 cycles).
* Supports dynamic task creation (`task_create`) with dedicated, isolated stacks.

### 3.3 Physical Memory Allocation
Memory is managed through a physical page frame allocator over 32 MB of contiguous virtual RAM:
* Divides physical memory into 8,192 pages (4,096 bytes per page).
* First 4 MB (`0x80000000` to `0x80400000`) is statically reserved for kernel binary, bootstrap stack, and static data.
* Dynamic allocations are tracked via an in-memory page bitmap.

### 3.4 Interactive Shell and Monitor
A lightweight command shell executes as Task 1, providing real-time kernel observability and diagnostic tools:
* `help` - Command reference and syntax guide
* `info` - Hardware architecture, paravirtualization specifications, and memory sizing
* `mem` - Live page allocation statistics and free memory metrics
* `ps` - Process table inspection (PID, state, stack pointer, task name)
* `spawn` - Launches concurrent background worker threads to demonstrate timer preemption
* `matrix` - Terminal visual diagnostic display
* `clear` - ANSI terminal display reset
* `reboot` - Soft restart via MMIO power management register
* `shutdown` - Graceful virtual machine halt

---

## 4. Hardware Simulation Layer (MMIO Specification)

The simulation environment communicates with the kernel exclusively through defined memory regions:

| Address Range | Device | Function |
| :--- | :--- | :--- |
| `0x80000000 - 0x82000000` | System RAM | 32 MB Physical Memory (R/W/X) |
| `0x10000000` | UART Data | Read: Pop Rx buffer; Write: Output character to stdout |
| `0x10000004` | UART Status | Bit 0: Rx ready; Bit 1: Tx ready |
| `0x10000010 - 0x10000014` | Timer Counter | 64-bit cycle counter (`mtime`) |
| `0x10000018 - 0x1000001C` | Timer Compare | 64-bit interrupt comparator (`mtimecmp`) |
| `0x10000040` | Power Management | Write 1: System Halt; Write 2: System Reboot |

---

## 5. Toolchain and Build System

AdiOS includes a zero-dependency, self-contained two-pass RV32I/M assembler (`toolchain/assembler.py`). It encodes standard RISC-V assembly, labels, pseudo-instructions, and directives directly into raw bootable machine code binaries (`adios.bin`) without requiring external GCC or Clang cross-compilers.

For modular development, a C kernel codebase (`kernel/*.c`) and linker script (`kernel/linker.ld`) are also provided for compilation with LLVM/Clang (`-target riscv32 -nostdlib`).

---

## 6. Getting Started

### Prerequisites
* Python 3.8+ (for toolchain and simulation layer)

### Execution
Clone the repository and run the unified build script:

```bash
# Assemble kernel and launch the interactive operating system
python build.py

# Alternatively, run automated regression tests
python build.py --test
```

On Windows, `boot.bat` is also provided for single-click execution.

---

## 7. Repository Layout

```
adios/
|-- kernel/
|   |-- asm_kernel.s       # Production bare-metal assembly kernel
|   |-- boot.s             # Assembly bootstrap and trap vector
|   |-- kernel.c           # C kernel entrypoint and panic handling
|   |-- kernel.h           # System types, prototypes, and MMIO definitions
|   |-- memory.c           # Physical page frame allocator
|   |-- scheduler.c        # Round-Robin preemptive task scheduler
|   |-- shell.c            # Command interpreter implementation
|   |-- uart.c             # Serial console driver and formatted output
|   `-- linker.ld          # Linker script targeting 0x80000000
|-- vm/
|   |-- vm.py              # Pure-Python RV32I virtual machine
|   |-- cpu.c / cpu.h      # Native C CPU core implementation
|   |-- bus.c / bus.h      # Native C MMIO bus controller
|   `-- main.c             # Native C terminal emulator entrypoint
|-- toolchain/
|   `-- assembler.py       # Two-pass RV32I assembler and linker
|-- tests/
|   |-- test_boot.py       # CPU boot regression test
|   `-- test_shell.py      # Automated shell command tests
|-- build.py               # Unified build manager
|-- boot.bat               # Windows batch launcher
`-- README.md              # Project documentation
```

---

## 8. License

This project is licensed under the MIT License.
