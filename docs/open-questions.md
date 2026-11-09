# Open Questions

Uncertain points are recorded here rather than guessed. Entries are answered or closed with a date and a
decision.

| ID | Question | Why it matters | Status |
|----|----------|----------------|--------|
| Q1 | How are the clock tree and sequential overhead (flip-flop clock energy) modelled? | Clock power can be a large part of total energy and differs by cell type. | Proposal: per-flop clock-toggle energy parameter, no tree. Open. |
| Q2 | Is switching energy per cell constant, or dependent on the level transition (e.g. 0→+1 vs −1→+1)? | Multi-level transitions plausibly cost more energy than binary toggles. | M1 implements constant energy per cell toggle. Optional transition matrix still open. |
| Q3 | What density, energy and latency to assume for ternary and quaternary memory macros? | Likely the largest single driver of H1 and H5; no verified source is available yet. | Open; M1 macro records exist with `confidence: low`; results must be shown with and without memory. |
| Q4 | Are wire length and capacitance modelled? | H1 is about lines. Ignoring wires may overstate or understate advantages. | Proposal: out of scope for v0.1; lines per bit reported. Open. |
| Q5 | For fixed-point workloads, is "same precision" the same number of distinct values or the same dynamic range? | They differ for non-power-of-two radices. | M1 iso-precision uses number of distinct values (`r^n ≥ 2^b`). Dynamic range variant still open. |
| Q6 | How is static power of multi-level logic modelled? | Some multi-level circuits draw static current. | Proposal: leakage parameter only, with high stress range. Open. |
| Q7 | How wide should the "technology maturity" factor range? | Controls how much binary's optimisation lead counts. | M1: nominal 1.0, group scaling over [0.5, 1.5]. Wider stress range still open. |
| Q8 | Does GPU-Q use multi-level memory macros by default? | Without MLC memory, GPU-Q differs from GPU-B only in logic. | **Closed 2026-11-09: two variants, GPU-Q-1b and GPU-Q-2b, reported separately.** |
| Q9 | Should there be a slow pure-Python reference simulator for differential testing of the Rust engine? | Independent check of engine correctness. | **Closed 2026-11-09: yes, deliberately simple, no performance target.** |
| Q10 | When is the optional CUDA backend built? | CPU path must be complete first. | Proposal: after v0.1, only if bit-identical to CPU. Open. |
| Q11 | Sign extraction in balanced ternary needs the most significant non-zero trit. Which implementation does the comparator use? | Directly affects H2/H3. | M1 generator library holds a linear-chain and a tree implementation; best per metric is selected. Partly closed. |
| Q12 | Result format: JSON only, or JSON plus Parquet? | Parquet needs an extra dependency but scales for large sweeps. | M1 uses JSON. Parquet optional, open. |
| Q13 | Practical-significance threshold δ. | Changes which results count as effects. | **Closed 2026-11-09: δ = 10% on the primary metric at nominal parameters; frozen in `prereg-v1`.** |
| Q14 | Primary comparison family for Holm correction. | Controls false-positive rate. | **Closed 2026-11-09: one primary metric per hypothesis and design pair; decision by CI position relative to δ; Holm p is an extra filter; other metrics exploratory.** |
| Q15 | Default NVIDIA NIM model for the `ai/` layer. | Model names must come from config, and availability changes. | Left to config in M5; no hard-coded default. |
| Q16 | GPU-B comparator design: a plain ripple-carry or the best of several architectures? | Affects fairness. | Decided in methodology §7: best-per-radix by search. |
| Q17 | "Sign of the effect preserved over the ±50% range" (decision Q13): how strictly? | Decides SUPPORTED vs SUPPORTED-CONDITIONALLY. | Implemented strictly: `r > 0` at every one-at-a-time ±50% point and group-scaling corner, 100% of global samples for the unconditional label. Revisit only with a new prereg tag. |
| Q18 | H2 has three metrics in its claim but Q14 requires one primary metric. | Prevents a conjunctive claim from hiding a loss. | Clarified at freeze: primary = static critical-path delay; area, transistors and energy are exploratory and shown beside it. |
| Q19 | Signed quaternary arithmetic. | Radix-4 two's complement equals 2n-bit two's complement, so signed Q multiplication needs a correction scheme. | M1 quaternary multiplier is **unsigned only**; the adder is modulus-4^n and sign-agnostic. Signed Q multiplier deferred to M2/M3. |
| Q20 | Operand value distribution for energy comparisons (same numeric values vs each design's native full range). | Switching activity depends on the distribution. | M1 micro-experiments report both; the paired "common range" value set is the primary. Open for other workloads. |
| Q21 | Source of the cell parameters. | All current ternary and quaternary cell values are placeholders (`confidence: low`). | A literature pass is still needed. Until then every verdict depends on the placeholders and carries that label. |
