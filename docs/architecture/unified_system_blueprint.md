# Unified System Blueprint (CMF Phase 12)

## 12.1 End-to-End Operating System Architecture

The **AdiOS Unified Architecture** synthesizes the entire operating system into an integrated, self-regulating computational substrate:

```mermaid
graph TD
    subgraph Userland[Userland Space & Processes]
        App1[Application Process A]
        App2[Application Process B]
    end

    subgraph KernelCore[AdiOS Kernel Core]
        Sched[MLFQ Multilevel Feedback Queue Scheduler]
        TCM[Temporal Causal Memory Engine]
        Sec[CMF Security Guard & ACLs]
        MMU[Hardware Causal MMU Sv32]
        CMF[Causal Object Store & DAG Engine]
        Bridge[FluidRAMCMFBridge]
    end

    subgraph MemorySubstrate[Hydrodynamic Physical Memory Substrate]
        Mesh[FluidRAM Physical Mesh]
        Pool1[POOL_USER_APPS]
        Pool2[POOL_STREAM_RING]
        Pool3[POOL_DYNAMIC_MESH]
        Pool4[POOL_KERNEL_CORE]
        Pool5[POOL_COMPOSITOR_FB]
        Pool6[POOL_CHRONOS_DELTA]
        
        Mesh --> Pool1
        Mesh --> Pool2
        Mesh --> Pool3
        Mesh --> Pool4
        Mesh --> Pool5
        Mesh --> Pool6
    end

    App1 -->|Instructions & Loads| MMU
    App2 -->|Temporal Contracts TRC| TCM
    Sched -->|Pre-Warm Hints| CMF
    MMU -->|FAULT_CAUSAL_MISS| CMF
    CMF -->|Topological Derivation| Bridge
    Bridge -->|Physical Allocation & Dissipation| Mesh
    Sec -->|ACL & Quota Authorization| CMF
```

---

## 12.2 Master Subsystem Coordination Loop

Every operating system clock tick executes an integrated three-stage pipeline:

1. **Scheduling & Temporal Contracts**:
   - The MLFQ scheduler updates priority levels and dispatches runnable processes.
   - Sleeping processes declare future wake horizons ($T_{\text{wake}}$) via Temporal Residency Contracts (TRCs).
2. **Anticipatory CMF Pre-Warming**:
   - The `RematerializationScheduler` checks TRC wake horizons approaching within $2$ ticks.
   - In-memory derivations are eagerly dispatched within the allotted CPU quantum budget ($250 \ \mu\text{s}$ limit), ensuring target working sets reside hot in RAM before dispatch.
3. **Hydrodynamic Surface-Tension Dissipation**:
   - If physical DRAM pressure exceeds threshold ($\Pi \ge 0.70$), the `FluidRAMCMFBridge` consults the `RematerializationCostEngine`.
   - Cheaply derivable and cold objects are evaporated, releasing physical frames while preserving 100% of causal recipes.
4. **Transparent Hardware MMU Traps**:
   - When a thread accesses an evaporated or unmaterialized page, the hardware MMU triggers **`FAULT_CAUSAL_MISS`**.
   - The kernel resolves the fault in **$< 45 \ \mu\text{s}$**, marks the hardware PTE valid (`V=1`), and resumes instruction flow without disk swap I/O.

---

## 12.3 Diagnostic Telemetry State

The unified kernel exposes holistic telemetry encompassing:
- Physical DRAM used vs. virtual causal expansion ratio ($> 3.5\times$ capacity amplification).
- Monitored surface-tension pressure across all 6 pools.
- Microsecond-level re-materialization latency distributions.
- Zero OOM terminations and zero disk swap operations.
