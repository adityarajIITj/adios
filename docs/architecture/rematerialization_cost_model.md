# Re-Materialization Engine & Cost Model (CMF Phase 5)

## 5.1 The Economic & Physical Cost Formulation

Classical virtual memory models eviction as a binary choice: either a page stays in RAM, or it is written to persistent swap storage. Because reading from swap involves millisecond storage I/O, the kernel treats every eviction as a high-risk penalty.

In the **Causal Materialization Framework (CMF)**, eviction is an **economic optimization**. The kernel continuously balances:
1. **The Cost of Re-Materialization ($C_{\text{remat}}$)**: The latency to recompute the object from its upstream dependencies.
2. **The Penalty of Retention ($P_{\text{retain}}$)**: The DRAM space occupied by the object weighted by the current hydrodynamic surface-tension pressure of the system.

### Re-Materialization Cost Equation

$$C_{\text{remat}}(\mathcal{C}) = \bar{T}_{\text{exec}}(f) + \frac{\sum_{p \in \text{Parents}} \text{Size}(p)}{B_{\text{bus}}}$$

Where:
- $\bar{T}_{\text{exec}}(f)$ is the monitored exponential moving average of transformation $f$'s CPU execution time in microseconds.
- $\sum \text{Size}(p)$ is the aggregate byte footprint of all parent dependencies.
- $B_{\text{bus}}$ is the live host memory bus bandwidth (e.g. $6.0 \text{ GB/s} \approx 6.0 \text{ bytes/ns}$).

### Retention Penalty Equation

$$P_{\text{retain}}(\mathcal{C}) = \left(\frac{\text{Size}(\mathcal{C})}{1024}\right) \times \Pi_{\text{pressure}}^{1.5} \times \left(1.0 + \frac{\text{Ticks}_{\text{idle}}}{100}\right)$$

Where:
- $\text{Size}(\mathcal{C}) / 1024$ is the resident size in kilobytes.
- $\Pi_{\text{pressure}} \in [0.0, 1.0]$ is the FluidRAM surface-tension pressure metric.
- $\text{Ticks}_{\text{idle}}$ is the elapsed clock ticks since the object was last accessed by any process.

---

## 5.2 Eviction Decision Rules

The `RematerializationCostEngine` evaluates whether a causal memory object should be evaporated:

$$\text{ShouldEvaporate}(\mathcal{C}) = \text{True} \iff \begin{cases}
\Pi_{\text{pressure}} \ge 0.70 \quad \text{and} \quad C_{\text{remat}}(\mathcal{C}) < 0.5 \times \tau_{\text{swap\_stall}} \\
\text{or} \\
\Pi_{\text{pressure}} \ge 0.95 \quad \text{and} \quad \text{Ticks}_{\text{idle}} > 10
\end{cases}$$

Where $\tau_{\text{swap\_stall}} \approx 15,000 \ \mu\text{s}$ (the baseline NVMe swap fault stall). Because in-memory derivations typically take $10 – 100 \ \mu\text{s}$, evaporating derived objects is **over $150\times$ faster** to recover from than classical Linux swap page faults.

---

## 5.3 Materialization Budget & CPU Protection

Recomputing memory in software introduces a potential failure mode: if an operating system greedily re-materializes dozens of objects simultaneously, it could starve application worker threads.

To prevent CPU jitter and priority inversion, CMF enforces the **Materialization Budget**:

$$\text{Budget}_{\text{quantum}} = T_{\text{quantum}} \times \alpha_{\text{remat\_ratio}}$$

- Default: $T_{\text{quantum}} = 1,000 \ \mu\text{s}$ (1 ms), $\alpha = 0.25 \implies \mathbf{250 \ \mu\text{s}}$ maximum re-materialization budget per tick.
- If re-materialization requests exceed the budget, low-priority pre-warming contracts are deferred to subsequent ticks.

---

## 5.4 Scheduling Policies & TCM Pre-Warming

The `RematerializationScheduler` supports three formal policies:

1. **`LAZY`**: Objects remain `EVICTED` or `UNMATERIALIZED` until an explicit read or page fault triggers re-materialization.
2. **`EAGER_PREWARM`**: Coordinated with **Temporal Causal Memory (TCM)**. When a suspended thread emits a Temporal Contract (TRC) indicating it will wake at tick $T_{\text{wake}}$, the scheduler enqueues the thread's causal working set and materializes it within $T_{\text{wake}} - 2$ ticks, ensuring **zero-stall hot wakeups**.
3. **`SPECULATIVE`**: When system pressure is low ($\Pi < 0.30$) and CPU idle time is detected, high-frequency derived objects are pre-materialized opportunistically.
