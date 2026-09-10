# Phase 1: Reconstructing AdiOS — Architectural Reality & Substrate Grounding

> **Authoritative Specification & Reality Audit**  
> **Status:** Phase 1, Sub-Phase 1.1 Grounding (Push 01/52)  
> **Classification:** Experimental Software Operating System & Systems Model

---

## 1.1 Implemented or Executable Mechanisms

AdiOS contains verified, executable software implementations for the following subsystems:

1. **Software-Defined RV32IM / RV32I Execution Environment**:
   - Instruction interpreter executing 32-bit RISC-V integer, multiplication, and division instructions with trap and interrupt handling.
2. **Kernel-Like Process and Scheduling Abstractions**:
   - Task Control Block (`TaskControlBlock`), process lifecycle state machines (`READY`, `RUNNING`, `SLEEPING`, `ZOMBIE`, `TERMINATED`).
3. **Preemptive MLFQ Scheduler, Signals, and IPC**:
   - Multi-Level Feedback Queue scheduler across 4 priority bands (Realtime, High, Normal, Idle) with quantum decay and anti-starvation priority boosting.
4. **Physical-Memory-Like Management Backed by Host Memory**:
   - Virtual memory management and physical frame allocation backed by host Python bytearrays and structured slab pools.
5. **FluidRAM Slab and Pool Abstractions**:
   - Partitioned memory pools (`POOL_KERNEL_CORE`, `POOL_COMPOSITOR_FB`, `POOL_STREAM_RING`, `POOL_CHRONOS_DELTA`, `POOL_USER_APPS`, `POOL_DYNAMIC_MESH`).
6. **Slab Ownership, Classification, Pinning, Residency, and Accounting**:
   - Formal metadata tracking slab classification (`PAGE_PINNED`, `PAGE_RECONSTRUCTIBLE`, `PAGE_TRANSIENT`, `PAGE_CACHE`), residency state, and pressure counters.
7. **Borrowing, Repayment, Reclamation, and Elastic Allocation**:
   - Dynamic page lending between pools, tensile rebalancing, and non-destructive surface-tension dissipation sweeps.
8. **Temporal Contract Memory (TCM) Concepts & Temporal Residency Contracts (TRC)**:
   - Forward-looking residency contracts emitted by tasks specifying sleep horizons and working set page lists for speculative dispatch pre-warming.
9. **Chronos Finite-Field Reversible Transformations ($GF(2^8)$ and $GF(2^{16})$)**:
   - Invertible algebraic state chains and unitary automorphisms allowing bit-exact forward and reverse memory rewinds without raw page copies.
10. **Morphic In-Slab Cellular Operations**:
    - Software micro-kernels (`OP_REDUCE_SUM`, `OP_FILTER_PATTERN`, `OP_CONVOLVE_2D`, `OP_PERMUTE_UNITARY`) executing directly against slab-backed memory buffers.
11. **Void-Pipe Ephemeral Scanline Media Processing**:
    - Ring-buffered streaming video frame transduction evaporating scanline allocations within 16.6 ms to bound memory footprint < 4.0 MB.
12. **Desktop Workstation, Compositor, and Userland Applications**:
    - Interactive 1280x720 HD window manager, 8-channel polyphonic SoundTracker synthesizer, Code Studio IDE, 3D graphics simulator, and POSIX shell.
13. **Linux-Kernel-Derived Executable Memory-Management Models**:
    - Faithful algorithmic implementation of Linux `mm/vmscan.c` dual-list LRU reclaim, `include/linux/mmzone.h` watermarks, and `mm/oom_kill.c` badness heuristics.
14. **Automated Verification & Benchmark Orchestration**:
    - Comprehensive test harness with 273 passing unit/integration tests and calibrated performance profiling suites.

> [!NOTE]
> **Definitive Baseline**: These mechanisms are software implementations running within the experimental AdiOS runtime environment. They are not to be described as native custom-silicon hardware.

---

## 1.2 Modeled Abstractions

The following concepts are currently **architectural models, simulation representations, or software abstractions**, rather than physically demonstrated silicon mechanisms:

| Abstraction | Current Implementation Reality | What It Represents |
| :--- | :--- | :--- |
| **1 GB FluidRAM Physical Memory** | Host Python bytearray allocation and virtual memory tracking. | Simulated 1024 MB physical address space for the RV32 environment. |
| **Fluid Computational Memory Substrate** | Software algorithms managing memory like a fluid (Navier-Stokes-inspired flow vectors and surface tension). | An algorithmic design pattern for elastic memory reclamation. |
| **Modeled Bus-Traffic Reduction** | Software accounting of bytes transferred across a modeled DDR bus vs. compact CXL descriptor tokens. | A mathematical model of von Neumann bus traffic savings. |
| **Physical In-Memory Computation** | Near-memory micro-kernels executed in host CPU memory within the slab's byte buffer. | The software abstraction of future Near-Memory Computing (NMC) and CXL PIM hardware. |
| **Hardware-Like Pressure & Flow** | Computational tensile dissipation loops iterating over slab queues. | Software simulation of hydrodynamic memory rebalancing. |
| **Hardware Media Decoding through Void-Pipe** | Host CPU-driven scanline streaming and buffer evaporation. | The algorithmic architecture of hardware-accelerated ephemeral media pipelines. |
| **Physical Thermodynamic Reversibility** | Galois Field finite-field algebraic permutations ($GF(2^{16})$ with Rijndael tables). | Mathematical reversibility, demonstrating zero-information-loss undo at the algorithmic layer. |
| **Native Linux-Kernel Execution** | Algorithmic state machine modeled after Linux `mm/vmscan.c` and `mm/oom_kill.c` combined with live host I/O calibration. | A high-fidelity software model, distinct from booting the actual Linux monolithic kernel on bare metal. |
| **Physical DRAM-Bus Measurements** | High-resolution CPU timing of memory buffer scans and cache-line touches scaled to bus width. | Derived software profiling of memory latency, not hardware oscilloscope or logic analyzer probe data. |
| **Universal Compression (Assumed 2.8:1 Ratio)** | Algorithmic parameter used in continuous overcommit stress tests. | A modeled compression factor, to be replaced by content-dependent entropy measurements. |

---

## 1.3 Measurements & Provenance Framework

The AdiOS system measures multiple empirical and simulated properties. To ensure research-grade integrity, every metric in AdiOS must declare its explicit provenance according to five standardized categories:

1. **`[HOST_MEASUREMENT]`**:
   - Physical hardware characteristics measured directly on the host machine at runtime.
   - *Examples*: Host disk read/write throughput via synchronous blocks (`22.9 MB/s`), host DRAM memory buffer scan rate (`7.4 GB/s`), monotonic execution clock intervals.
2. **`[SOFTWARE_EXECUTION]`**:
   - Timing and memory allocation of actual software algorithms executing in the runtime.
   - *Examples*: Microsecond latency of Galois $GF(2^{16})$ state chain inversions, in-situ slab reduction runtime, process dispatch pre-warming latency (`15.8 µs`).
3. **`[MODELED_VALUE]`**:
   - Outputs generated by algorithmic state-machine simulations of hardware or third-party kernels.
   - *Examples*: Linux `mm/vmscan.c` dual-list LRU page reclaim counts, `mm/oom_kill.c` `oom_badness()` victim selection, modeled DDR bus roundtrip latencies.
4. **`[ARCHITECTURAL_PARAMETER]`**:
   - Declared system boundaries, zone limits, or layout constants defining an experimental trial.
   - *Examples*: 32 MB zone size limit, 4 KB page size, 50 concurrent worker tasks, 512 KB working set per thread.
5. **`[ASSUMPTION]`**:
   - Theoretical or parameterized scaling hypotheses subject to falsification.
   - *Examples*: The 2.8:1 Tensegrity dynamic folding compression ratio under overcommit pressure.

### Current System Measurements Audit

| Measured Property | Value / Range | Explicit Provenance | Scientific Reality |
| :--- | :--- | :--- | :--- |
| **Host Disk Throughput** | ~15 – 45 MB/s | `[HOST_MEASUREMENT]` | Live synchronous host storage block read/write speed. |
| **Host DRAM Throughput** | ~5 – 8 GB/s | `[HOST_MEASUREMENT]` | High-resolution timed stride memory scans across host buffers. |
| **Software Execution Time** | 0.015 – 16.8 ms | `[SOFTWARE_EXECUTION]` | Measured with monotonic clock (`clock_gettime` / `time.perf_counter`). |
| **Reversible Galois Cost** | 0.45 – 1.2 ms | `[SOFTWARE_EXECUTION]` | Actual CPU computation time to invert $GF(2^{16})$ state chains. |
| **Memory Reclamation Count** | 12 – 48 MB freed | `[SOFTWARE_EXECUTION]` | Actual byte capacity reclaimed by evaporating transient slabs. |
| **Modeled Memory Bus Traffic** | 64.1 MB vs 37.5 KB | `[MODELED_VALUE]` | Modeled von Neumann DDR transfer vs. CXL descriptor packet tokens. |
| **Linux OOM Murders** | 17 – 28 killed | `[MODELED_VALUE]` | Algorithmic execution of Linux `mm/oom_kill.c` scoring model. |
| **Tensegrity Folding Ratio** | 2.8 : 1 | `[ASSUMPTION]` | Modeled dynamic memory compaction factor. |

> [!IMPORTANT]
> **Provenance Imperative**: A modeled descriptor count is not a physical hardware bus-counter measurement. A Linux-derived model is not the Linux kernel running on bare-metal hardware. Clear provenance prevents conflating models with physical measurements.
