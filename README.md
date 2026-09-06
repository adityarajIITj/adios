# AdiOS

> A sovereign, bare-metal 1280x720 HD graphical operating system, desktop environment, in-OS developer studio, online package manager, and 3D spatial computing workstation built from first principles for 32-bit RISC-V (RV32IM).

---

## Overview

AdiOS is a modern, zero-bloat, bare-metal operating system and graphical workstation designed from first principles. It requires no third-party OS kernels or black-box drivers. Every component—from the cycle-accurate RISC-V CPU emulator and Type-1 hypervisor to the 2D vector compositor, software 3D rasterizer, audio server, in-OS C99 compiler, and online package manager—is implemented from scratch.

<div align="center">
  <img src="docs/assets/adios_v3_beta_workstation.png" alt="AdiOS Workstation 1280x720 HD" width="920"/>
  <p><em>AdiOS Workstation (1280x720 HD @ 60 FPS) running in Nordic Slate theme with In-OS Code Studio, 3D Scene Studio, and Taskbar.</em></p>
</div>

<div align="center">
  <img src="docs/assets/adios_v3_beta_packages_explorer.png" alt="AdiOS Online Package Manager and File Explorer" width="920"/>
  <p><em>Online Package Manager installing PyPI packages asynchronously alongside the AdioFiles dual-pane visual file explorer.</em></p>
</div>

---

## Key Features

- **In-OS Code Studio IDE**: Full-featured code editor with syntax highlighting, line numbers, execution runner sandbox, and instant output telemetry.
- **Online Package Manager (`pip install`)**: Live background PyPI package installer inside the OS with real-time log streaming and runtime library importing.
- **AdioFiles Visual File Explorer**: Dual-pane file manager with Places bookmarks (`Root`, `Scripts`, `Desktop`, `Graphics`, `Tests`), file type badges, and direct launcher hooks.
- **3D Spatial Scene Studio**: Real-time 3D model inspector with smooth mouse drag rotation, directional diffuse lighting, wireframe mode, and geometric primitives (Cube, Pyramid, Octahedron, Prism, Monolith).
- **Minimalist Modern Theme Engine**: Four clean, light/subdued aesthetic palettes (Nordic Slate, Monochrome Silver, Arctic Minimal, Emerald Code) with hairline window borders and 1-click taskbar switching.
- **Sovereign YouTube Player**: Real YouTube video and audio streaming at 640x360 @ 60 FPS HD with a 32-band spectrum EQ visualizer and sub-10ms audio lip sync.
- **Zero-Bloat Foundation**: In-house RISC-V RV32IM CPU core, 512 MB physical memory management, preemptive scheduler, TLS 1.3 crypto, TCP/IP stack, and C99 compiler.

---

## Quick Start (30 Seconds)

### Prerequisites
- Python 3.10+
- Pygame (for desktop window compositing and audio)
- Pillow (for image processing)

```bash
pip install pygame pillow
```

### Launch AdiOS Workstation
```bash
# Clone the repository
git clone https://github.com/adityarajIITj/adios.git
cd adios

# Run the 1280x720 HD 60 FPS Desktop Workstation
python run_desktop.py
```

### Run Verification & Tests
```bash
# Run the v3 Beta application test suite
python -m unittest tests/test_v3_beta_apps.py

# Run the master 56-subsystem verification suite
python verify_all.py
```

---

## Core System Architecture

| Layer | Subsystems | Key Capabilities |
| :--- | :--- | :--- |
| **Layer 3: Desktop Workstation** | Master Desktop, Code Studio, AdioFiles, Scene3D Studio, Theme Engine, YouTube Player | 1280x720 HD 60 FPS compositing, online pip package manager, 3D mouse rotation, vector window chrome |
| **Layer 2: Runtimes & Protocols** | C99 Compiler, AdiPython, SovereignSQL, TLS 1.3, TCP/IP, Audio Server | In-OS code building, Volcano query planner, ChaCha20/AES-GCM crypto, low-latency audio mixing |
| **Layer 1: Bare-Metal Kernel** | Preemptive Scheduler, Buddy Allocator, Sv32 MMU, VFS | 34-register context switching, 512 MB RAM management, Ext2/FAT32/AdiFS, IPC futex/pipes |
| **Layer 0: Hardware Simulation** | RV32IM CPU Core, MMIO VPU (0x30000000), Framebuffer | Fast instruction pre-decode cache, hardware DMA frame blitter, linear 32-bit ARGB surface |

---

## Project Structure

```text
adios/
├── desktop/             # Sovereign Workstation UI, Windows, Code Studio & Themes
│   ├── master_desktop.py   # Desktop compositor, top taskbar, system flyouts
│   ├── code_studio.py      # In-OS IDE with syntax highlighting & pip package installer
│   ├── file_explorer.py    # Dual-pane visual file manager with Places bookmarks
│   ├── scene3d_studio.py   # Interactive 3D spatial studio with mouse drag rotation
│   ├── theme.py            # Minimalist theme engine (Nordic, Mono, Arctic, Emerald)
│   └── window_manager.py   # Window chrome, dragging, focus, hairline borders
├── graphics/            # 2D vector compositor and 3D software rasterizer
├── audio/               # Low-latency PCM sound server & audio track synthesizer
├── net/                 # Sovereign network stack, TLS 1.3, and YouTube streaming relay
├── kernel/              # RV32IM kernel, preemptive scheduler, buddy allocator, MMU
├── tests/               # Automated regression tests and application test suites
├── run_desktop.py       # Sovereign Workstation launcher entry point
└── verify_all.py        # Master 56-subsystem automated verification harness
```

---

## License & Credits

AdiOS is developed from first principles by Aditya Raj. Licensed under the MIT License.