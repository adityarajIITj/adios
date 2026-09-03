# AdiOS (v0.4.0-alpha)

A minimalist, bare-metal operating system, graphical windowing environment, 3D wireframe game engine, and custom in-house systems programming language (**AdiPython**) implemented for the 32-bit RISC-V (RV32IM) architecture.

Inspired by the sovereign, zero-bloat computing philosophy of Terry A. Davis's **TempleOS**.

---

## 1. Overview

AdiOS is an educational and systems-research operating system built entirely from first principles without external third-party dependencies. It provides:
1. **A Capable Virtual Simulation Layer**: A custom, high-performance in-house virtual machine (our own zero-dependency VMware/QEMU) providing 64 MB RAM, pre-decoded instruction caching (15-30 MIPS), full RV32M hardware math, persistent virtual block storage, audio synthesis, and framebuffer MMIO.
2. **The AdiPython In-House Systems Language**: A custom, Ring-0 systems language inspired by HolyC. Features clean Pythonic syntax with raw hardware access (`peek`, `poke`, `pixel`, `rect`, `line`, `clear`, `tone`), instant execution, and direct control over memory and peripherals.
3. **StarFlight 3D Wireframe Game Engine**: A real-time 3D flight and space exploration game featuring 3D rotation transformations, perspective projection, an infinite scrolling terrain grid, dynamic navigation rings, starfields, and flight HUD.
4. **Bare-Metal Graphical Desktop**: A 640x480 32-bit ARGB windowing environment running directly on bare-metal RISC-V assembly with Paint Studio, Calculator, Terminal, and System Monitor.

---

## 2. System Architecture

```
+-------------------------------------------------------------------------+
|                  AdiOS IN-HOUSE HARDWARE SIMULATION LAYER               |
|            (High-Performance RV32IM Virtual Machine + MMIO Bus)         |
|                                                                         |
|   * 32-bit RISC-V CPU Core with Instruction Decode Caching              |
|   * Complete RV32I Base ISA + Full RV32M Hardware Math                  |
|     (mul, mulh, mulhsu, mulhu, div, divu, rem, remu)                    |
|   * 64 MB Identity-Mapped Physical RAM (0x80000000 - 0x84000000)        |
|   * Memory-Mapped I/O Peripherals:                                      |
|       - 0x10000000: Serial UART Console (Tx / Rx Registers)             |
|       - 0x10000010: Real-Time Hardware Timer and Comparator Registers   |
|       - 0x10000040: Power Management Unit (Reboot / Poweroff Signals)   |
|       - 0x10000050: PC Speaker / Audio Tone Synthesizer Registers       |
|       - 0x10001000: Virtual ATA Block Storage Controller (disk.img)     |
|       - 0x20000000: 640x480 32-bit ARGB Linear Framebuffer (1.2 MB)     |
|       - 0x20130000: Display Controller & Hardware Mouse Registers       |
+------------------------------------+------------------------------------+
                                     |
+------------------------------------v------------------------------------+
|               AdiPython IN-HOUSE SYSTEMS LANGUAGE & RUNTIME             |
|                                                                         |
|   * Single-pass Lexer, Recursive-Descent Parser, and AST Engine         |
|   * Ring-0 Hardware Access: peek(), poke(), pixel(), line(), rect()     |
|   * Instant statement execution, loops, recursion, and functions        |
|   * Standalone script runner (.ap files)                                |
+------------------------------------+------------------------------------+
                                     |
+------------------------------------v------------------------------------+
|                     APPLICATIONS & GRAPHICS ENGINES                     |
|                                                                         |
|   * StarFlight 3D Engine  : Real-time 3D perspective flight simulator   |
|   * Graphical Desktop     : Paint Studio, Calculator, Terminal, Sysmon  |
|   * Bare-Metal CLI Shell  : Preemptive multitasking Round-Robin kernel  |
+-------------------------------------------------------------------------+
```

---

## 3. AdiPython: The In-House Language of AdiOS

Like **HolyC** was to TempleOS, **AdiPython** is the native systems programming language of AdiOS. It combines an intuitive, readable syntax with raw "God Mode" access to bare-metal hardware.

### 3.1 Direct Hardware MMIO Control
```python
# Read and write arbitrary 32-bit physical memory addresses
poke(0x80050000, 0x12345678)
val = peek(0x80050000)

# Direct Framebuffer 2D drawing
rect(100, 100, 60, 40, RED)       # Filled rectangle
line(0, 0, 200, 150, GREEN)       # Bresenham line
pixel(320, 240, CYAN)             # Single pixel

# Play audio frequencies through MMIO sound synthesizer
tone(440, 100)                    # 440 Hz (A4) for 100ms
```

### 3.2 Functions, Recursion, and Control Flow
```python
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)

print("6! =", factorial(6))

sum = 0
for i in range(1, 101):
    sum += i
print("Sum 1..100 =", sum)
```

---

## 4. StarFlight 3D Wireframe Game Engine

Inspired by Terry A. Davis's iconic 3D flight games in TempleOS:
* **Real-time 3D Math**: 3D rotation transformations, Euler angle camera controls, and perspective projection ($S_x = \text{Center}_X + \frac{X \cdot f}{Z}$, $S_y = \text{Center}_Y - \frac{Y \cdot f}{Z}$).
* **3D Wireframe Starfighter**: Responsive banking and pitching starfighter with twin afterburners.
* **Infinite 3D Ground Terrain Grid**: Perspective wireframe ground grid converging towards the horizon.
* **3D Navigational Rings & Gateways**: Dynamic octagonal gates to navigate through with collision detection and real-time MMIO audio chimes.
* **Flight HUD**: 3D artificial horizon pitch ladder and altitude tracking.

---

## 5. Quick Start & Command Reference

### Launching the Desktop GUI
```bash
python build.py
```

### Launching the StarFlight 3D Game
```bash
python build.py --3d
```

### Running an AdiPython Script
```bash
python build.py --run scripts/cube3d.ap
```

### Running the Bare-Metal CLI Shell
```bash
python build.py --cli
```

### Running the Automated Regression Test Suite
Runs all 4 subsystem verification suites (Simulation Layer Hardware + AdiPython + CLI Shell + GUI Desktop):
```bash
python build.py --test
```

---

## 6. Repository Layout

```
adios/
|-- adipython/              # In-house systems language
|   |-- lexer.py            # Stream tokenizer
|   |-- parser.py           # Recursive-descent AST parser
|   |-- runtime.py          # Ring-0 hardware MMIO execution engine
|   `-- compiler.py         # Compiler driver & API
|-- games/                  # 3D games & graphics
|   `-- flight3d.py         # StarFlight 3D flight simulator
|-- scripts/                # AdiPython scripts
|   `-- cube3d.ap           # 3D wireframe cube renderer
|-- kernel/                 # Bare-metal RISC-V kernel source
|   |-- gui_kernel.s        # Graphical windowing system & applications
|   |-- asm_kernel.s        # Preemptive multitasking CLI shell
|   `-- font8x8.s           # 8x8 bitmap font blitter
|-- vm/                     # In-house hardware simulation layer
|   |-- vm.py               # 64MB RV32IM CPU core with decode cache
|   `-- display.py          # Tkinter 640x480 Framebuffer window
|-- toolchain/              # Zero-dependency RV32I/M assembler
|   `-- assembler.py        # Two-pass assembler and linker
|-- tests/                  # Automated test suites
|   |-- test_vm_capable.py  # 64MB RAM, RV32M math, and disk MMIO tests
|   |-- test_adipython.py   # AdiPython language verification
|   |-- test_gui.py         # GUI desktop and application tests
|   `-- test_shell.py       # Shell command regression tests
`-- build.py                # Unified build and boot script
```

---

## 7. License

AdiOS is open-source software released under the MIT License.
