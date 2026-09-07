# AdiOS Kernel Architecture Specification

This document specifies the bare-metal kernel architecture, memory layout, interrupt handling, and system call ABI for AdiOS on 32-bit RISC-V (RV32IM).

---

## 1. Physical Memory Map

AdiOS manages up to 1024 MB (1.0 GB) of physical memory with memory-mapped I/O (MMIO) devices mapped into standard RISC-V address space regions:

| Address Range | Size | Description |
| :--- | :--- | :--- |
| `0x00000000 - 0x0000FFFF` | 64 KB | Boot ROM / Reset Vector |
| `0x02000000 - 0x0200FFFF` | 64 KB | CLINT (Core Local Interruptor: `mtime`, `mtimecmp`) |
| `0x0C000000 - 0x0FFFFFFF` | 64 MB | PLIC (Platform-Level Interrupt Controller) |
| `0x10000000 - 0x100000FF` | 256 B | 16550A Compatible UART Serial Interface |
| `0x30000000 - 0x30FFFFFF` | 16 MB | Sovereign VPU Linear Framebuffer (1280x720 32-bit ARGB) |
| `0x80000000 - 0xC0000000` | Up to 1024 MB | Physical DRAM Main Memory |

---

## 2. Virtual Memory Subsystem (RISC-V Sv32)

Virtual memory is implemented according to the RISC-V Privileged Architecture Specification (Sv32):

- **Page Size**: 4096 bytes (4 KB) standard pages; 4194304 bytes (4 MB) megapages.
- **Page Table Structure**: 2-level hierarchical radix tree.
  - `VPN[1]` (bits 31..22): Level 1 Page Table Index (1024 entries).
  - `VPN[0]` (bits 21..12): Level 0 Page Table Index (1024 entries).
  - `Offset` (bits 11..0): Byte offset within page.

### Page Table Entry (PTE) Flags
```text
31               20 19          10 9   8 7 6 5 4 3 2 1 0
+------------------+--------------+-----+---------------+
|      PPN[1]      |    PPN[0]    | RSW | D A G U X W R V |
+------------------+--------------+-----+---------------+
```
- `V` (bit 0): Valid entry.
- `R` (bit 1): Read permission.
- `W` (bit 2): Write permission.
- `X` (bit 3): Execute permission.
- `U` (bit 4): User-mode accessible.
- `G` (bit 5): Global mapping across address spaces.
- `A` (bit 6): Accessed by hardware translation.
- `D` (bit 7): Dirty bit (modified by store).

---

## 3. Preemptive Multi-Level Feedback Queue (MLFQ) Scheduler

The scheduler maintains 4 priority bands with quantum decay and anti-starvation boosting:

1. **Band 0 (Realtime)**: Audio synthesizer, DSP, and hardware blitter routines (Quantum: 20 ticks).
2. **Band 1 (High)**: Window manager, mouse compositor, and interactive user interface (Quantum: 15 ticks).
3. **Band 2 (Normal)**: Standard userland compute tasks and command shells (Quantum: 10 ticks).
4. **Band 3 (Idle)**: Background garbage collection and memory compaction (Quantum: 5 ticks).

### Priority Boosting
To prevent priority inversion and starvation, all tasks are boosted to Band 1 every 1,000 timer ticks.

---

## 4. System Call ABI

Userland applications issue system calls using the `ecall` instruction:

- **System Call Number**: Passed in register `a7`.
- **Arguments**: Passed in registers `a0`, `a1`, `a2`, `a3`, `a4`, `a5`.
- **Return Value**: Returned in register `a0` (non-negative on success, `-errno` on failure).
- **Preserved Context**: Callee-saved registers (`s0-s11`) preserved across call boundaries.
