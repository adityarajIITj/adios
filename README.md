# AdiOS (v0.2.0-alpha)

A minimalist, bare-metal operating system, graphical windowing environment, and micro-simulation layer implemented for the 32-bit RISC-V (RV32I/M) instruction set architecture.

---

## 1. Overview

AdiOS is an educational and systems-research operating system built from first principles. It decouples the foundational computer science primitives of an operating system—preemptive multitasking, physical page allocation, trap handling, Memory-Mapped I/O (MMIO), and graphical window composition—from physical hardware driver complexity.

Rather than relying on modern physical graphics buses (PCIe, DRM/KMS, GPU command rings), AdiOS interfaces with a direct Memory-Mapped Framebuffer and peripheral bus. The bare-metal RISC-V kernel renders 2D primitives, bitmap typography, interactive window chrome, and desktop applications directly to video memory.

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
|       - 0x20000000: 640x480 32-bit ARGB Linear Framebuffer (1.2 MB)     |
|       - 0x20130000: Display Controller & Hardware Mouse Registers       |
+------------------------------------+------------------------------------+
                                     | Machine Instructions & MMIO Traps
+------------------------------------v------------------------------------+
|                         AdiOS BARE-METAL KERNEL                         |
|                                                                         |
|   * boot.s / gui_kernel.s : Bootstrap, trap vector, graphics engine     |
|   * font8x8.s             : 8x8 bitmap font blitter for ASCII 32-126    |
|   * Window Manager        : Compositor, window chrome, and drop shadows |
|   * Desktop App Suite     : Terminal, Paint Studio, SysMon, Calculator  |
|   * scheduler.c           : Preemptive, timer-driven Round-Robin        |
|   * memory.c              : Bitmap-managed physical page frame alloc    |
+-------------------------------------------------------------------------+
```

---

## 3. Graphical Desktop and Windowing System

AdiOS v0.2 introduces a complete 2D desktop windowing environment running directly on bare-metal RISC-V:

### 3.1 2D Graphics Engine & Typography
* **Linear Framebuffer**: Direct memory-mapped ARGB pixel memory spanning `0x20000000` to `0x2012C000`.
* **Rendering Primitives**: Optimized rectangle fills (`gfx_fill_rect`), borders (`gfx_draw_rect_outline`), and screen clearing (`gfx_clear`).
* **Monochrome Bitmap Blitter**: Built-in 8x8 font table supporting full ASCII (characters 32 to 126) for arbitrary text rendering with configurable foreground and background colors.

### 3.2 Desktop Compositor & Window Manager
* **Desktop Canvas**: Modern dark theme slate wallpaper with subtle drop-shadow window effects.
* **Global Taskbar**: Fixed top bar (`y=0..24`) featuring:
  * Interactive **"AdiOS" Start Pill Button** toggling an application launcher dropdown.
  * System architecture indicator.
  * Real-time hardware uptime / frame status monitor.
* **Window Chrome**: Rectangular window framing with title bars, close controls (`[X]`), and drop shadows.
* **Hardware Mouse Pointer**: 11x16 arrow cursor tracked through MMIO mouse registers (`0x20130010 - 0x20130018`).

### 3.3 Built-in Desktop Applications
1. **AdiOS Terminal Shell**: Embedded graphical console running the interactive shell command interpreter.
2. **Paint Studio**: Freehand mouse drawing canvas with multi-color palette swatches (Black, Red, Green, Blue, Yellow).
3. **System Monitor (SysMon)**: Hardware diagnostic widget featuring a live physical RAM allocation progress bar, CPU frequency display, and active scheduler task metrics.
4. **Desktop Calculator**: Arithmetic unit with a 12-button interactive keypad (`0-9`, `+`, `-`, `*`, `/`, `=`) and LCD readout.

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
| `0x20000000 - 0x2012C000` | Framebuffer | 640x480x4 bytes (32-bit `0x00RRGGBB` ARGB) |
| `0x20130000` | Display Width | Constant: 640 |
| `0x20130004` | Display Height | Constant: 480 |
| `0x20130008` | Display Stride | Constant: 2,560 bytes |
| `0x2013000C` | Display Flush | Write 1: Flush framebuffer to host screen |
| `0x20130010` | Mouse X | Read: Current cursor X coordinate (0-639) |
| `0x20130014` | Mouse Y | Read: Current cursor Y coordinate (0-479) |
| `0x20130018` | Mouse Buttons | Bit 0: Left button pressed; Bit 1: Right button pressed |

---

## 5. Toolchain and Build System

AdiOS includes a zero-dependency, self-contained two-pass RV32I/M assembler (`toolchain/assembler.py`). It encodes standard RISC-V assembly, labels, pseudo-instructions, and recursive `.include` directives directly into raw bootable machine code binaries (`adios.bin`) in ~40ms without requiring external GCC or Clang cross-compilers.

---

## 6. Getting Started

### Prerequisites
* Python 3.8+ (with standard `tkinter` for graphical desktop display)

### Execution Modes

```bash
# 1. Launch the full Graphical Desktop Windowing System
python build.py

# 2. Launch the headless Terminal Console Shell (CLI mode)
python build.py --cli

# 3. Run the complete automated regression test suite (CLI + GUI)
python build.py --test

# 4. Assemble kernel binaries only
python build.py --build
```

On Windows, `boot.bat` is also provided for single-click desktop startup.

---

## 7. Repository Layout

```
adios/
|-- kernel/
|   |-- gui_kernel.s       # Bare-metal Graphical Desktop Kernel (v0.2)
|   |-- font8x8.s          # 8x8 ASCII monochrome font table
|   |-- asm_kernel.s       # Bare-metal CLI Shell Kernel (v0.1)
|   |-- boot.s             # Assembly bootstrap and trap vector
|   |-- kernel.c           # C kernel entrypoint
|   |-- memory.c           # Physical page frame allocator
|   |-- scheduler.c        # Preemptive Round-Robin scheduler
|   |-- shell.c            # Command interpreter implementation
|   |-- uart.c             # Serial console driver
|   `-- linker.ld          # Linker script targeting 0x80000000
|-- vm/
|   |-- vm.py              # RV32I virtual machine with MMIO display bus
|   |-- display.py         # Tkinter 640x480 desktop window & mouse driver
|   |-- cpu.c / cpu.h      # Native C CPU core implementation
|   |-- bus.c / bus.h      # Native C MMIO bus controller
|   `-- main.c             # Native C terminal emulator entrypoint
|-- toolchain/
|   `-- assembler.py       # Two-pass RV32I assembler with .include support
|-- tests/
|   |-- test_gui.py        # Automated framebuffer & mouse MMIO tests
|   |-- test_shell.py      # Automated shell command tests
|   `-- test_boot.py       # CPU boot regression test
|-- build.py               # Unified build manager (GUI / CLI / Test)
|-- boot.bat               # Windows batch launcher
`-- README.md              # System documentation
```

---

## 8. License

This project is licensed under the MIT License.
