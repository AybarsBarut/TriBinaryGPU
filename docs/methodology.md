# RadixLab — Methodology

Status: **M0 draft, awaiting approval.** Companion to `hypotheses.md` and `assumptions.md`.

## 1. Scope and non-claims

RadixLab is a **gate-level architectural simulation study**. It does not predict the performance of real
silicon. The hardware parameters are assumptions, and conclusions are valid only inside the assumption
ranges stated in each report. The study cannot say that ternary or quaternary chips are, or are not,
manufacturable. It can say under which cost assumptions an architectural advantage exists or vanishes.

## 2. Designs and control

See `hypotheses.md` §0.1. GPU-B, GPU-T, GPU-Q and the control GPU-BT use the same microarchitecture
template, the same ISA semantics and the same netlist generators, differing only in:

- the digit set and the number system;
- the cell library (`cells/binary.yaml`, `ternary.yaml`, `quaternary.yaml`);
- the digit counts derived from the comparison mode.

Quaternary is, logically, a pair of bits. Any observed difference between GPU-Q and GPU-B can come only
from multi-level signalling (MLC-like storage and interconnect), through the cell parameters.
This is documented in `faq.md` and repeated in every GPU-Q result.

## 3. Comparison modes

Defined in `hypotheses.md` §0.3: **ISO-PRECISION** and **ISO-AREA**, both always reported.

- Effective bits of an `n`-digit word in radix `r` are `n · log2(r)`.
- For fixed-point, "precision" means both the number of distinct values and the dynamic range; a
  workload specifies which one its golden model needs (open question Q5).
- Area for ISO-AREA is `Σ(cell area) + Σ(macro area)`. Results are reported both with macros and without.

## 4. Technology abstraction

A cell is a record, not a circuit: transistor count, area, delay, switching energy, leakage power, noise
margin, and a truth table (`assumptions.md` §3). The simulator never solves analogue behaviour.

Known limits of the abstraction (also in the threats-to-validity list, §12):
- No wire capacitance or routing: lines are counted, not placed (open question Q4).
- Energy is a fixed per-toggle cost per cell. Level-dependent transition energies are optional and
  modelled only if the cell file provides them (open question Q2).
- Static power of multi-level cells is modelled through the leakage parameter only (open question Q6).

## 5. Simulation engine

**Core language: Rust with PyO3 bindings** (rationale in `docs/decisions/0001-core-language.md`).

- **Logic values:** binary `{0,1}`; balanced ternary `{-1,0,+1}` plus unknown `X` (high-impedance `Z` is read
  as `X` on inputs); quaternary `{0,1,2,3}`.
- **Host encoding:**
  - Binary: bit-parallel packing, 64 independent test vectors per machine word.
  - Ternary: 2-bit host code per trit. The four codes are `-1, 0, +1, X`, so the unknown state fits
    without an extra bit.
  - Quaternary: 2-bit host code per digit.
- **Evaluation:** the netlist is levelized for zero-delay functional simulation (fast, used for
  equivalence testing). An event-driven mode with per-cell delays gives timing, glitches and switching
  activity. Both modes must agree on settled outputs. This is tested.
- **Reports:** critical path (static, from the levelized graph, and dynamic, from event timing), switching
  activity → dynamic power, leakage × time, area, and cycles/CPI for the full GPU.
- **Memory macros:** SRAM arrays (register file, shared memory, L1 data and tag arrays) may be a
  parametric macro model. Each macro instance is **explicitly flagged** (`macro: true`) in the netlist and
  in the report. Everything else is a real gate-level netlist. Macro area and energy come from
  assumption parameters and are also reported separately.
- **Noise injection:** Gaussian noise is added to cell outputs (and optionally inputs). The perturbed
  value is re-quantised to the nearest level with the cell's thresholds. The injection is per node and per
  evaluation, with the seed derived deterministically (§8.4).
- **Determinism:** with a fixed seed and a fixed thread count the result is bit-identical. Parallelism must
  not change results (parallel reductions are made order-independent).
- **CPU first.** The CPU path is complete. An optional CUDA backend must be bit-identical to it on the
  equivalence suite and is deferred to after v0.1 (open question Q10).

## 6. Verification policy (a verification gate)

No circuit contributes to a result until it is verified.

- **L0, cells:** each cell's truth table in YAML is checked against a golden Python function, for all
  input combinations.
- **L1, blocks:** every block (adder, multiplier, comparator, ALU, ...) is checked against a golden Python
  model. If the block has `≤ 2^22` input combinations, the check is exhaustive. Otherwise it is random
  with `≥ 10^6` vectors plus mandatory corner vectors (min, max, zero, ±1, carry-propagate extremes,
  X inputs for ternary).
- **L2, system:** every workload's output on every GPU is compared with the golden output.
- **Encoding equivalence:** ternary and quaternary blocks are checked by *numeric value*, via an
  explicit encode/decode pair that is itself tested for round-trip.
- **The gate:** a passing check writes a certificate (`verified.json`) containing the netlist hash,
  generator version and vector counts. The experiment runner refuses to run a netlist without a
  matching certificate. A change to a netlist invalidates its certificate.
- **AI-generated artifacts** (cells, netlists, kernels) go through exactly the same gate and are
  stored in a quarantine location until they pass. Failing artifacts are rejected and logged.
- Cross-check: a slow, simple, independent pure-Python reference evaluator is used to check the Rust engine
  on random netlists (differential testing; open question Q9).

## 7. Netlist generation and fairness

- Generators are parametrised by `(radix, digit count, architecture)`, and every architecture available for
  one radix is available for the others, within the limits of the cell library.
- For each block and each metric the best architecture per radix is chosen by automated search over the
  generator library. No hand-tuning on one side.
- All generated netlists are validated for fan-in/fan-out and acyclicity before verification.
- The ISA is unified (§ architecture, M3). The assembler per radix lowers it to radix-specific
  immediates and encodings. Kernel instruction counts are reported so that per-radix code-size differences
  are visible.
- The binary baseline benefits from decades of optimisation, while multi-level cell designs are
  immature. Neither is a defensible default, so the "technology maturity" factor is a separate,
  explicit sensitivity dimension and is never folded silently into cell values.

## 8. Experiment protocol and statistics

### 8.1 Experiment definition
A YAML file with: experiment id, hypothesis id, designs, comparison mode, workload and its parameters,
parameter set (reference to `assumptions`), number of replications, base seed, and output paths.

### 8.2 Replication
See `hypotheses.md` §0.6. Noisy experiments: `≥30` seeds. Workload-input experiments: `≥30` seeds.
Sensitivity: `≥1024` samples. Seeds are never reused across replication units in a way that creates
dependence between treatments, but the **same seed is used for all designs within one replicate** so that
comparisons are paired.

### 8.3 Statistics

| Purpose | Method |
|---------|--------|
| Paired difference, non-normal | Wilcoxon signed-rank; Hodges–Lehmann estimate |
| Confidence intervals | percentile or BCa bootstrap, 10,000 resamples |
| Effect size | paired rank-biserial correlation; Cliff's δ (unpaired); ratio of geometric means with log-scale CI |
| Rates (errors) | Wilson and Clopper–Pearson intervals; exact binomial test against the analytical reference |
| Rare events | importance sampling with recorded weights |
| Equivalence | TOST with margin `δ` |
| Family-wise error | Holm correction, α = 0.05, over the primary family |

The primary family is the following set of comparisons: for each of H2–H5, the primary metric and
design pair given in the experiment YAML marked `primary: true`. H1 is deterministic and is assessed
by sensitivity analysis only. All other comparisons are exploratory and labelled so.

### 8.4 Seeds
All randomness derives from `numpy.random.SeedSequence(base_seed, spawn_key=(experiment, replicate,
component))` (or an equivalent Rust derivation with the same semantics). No call uses global or time-based
seeds.

### 8.5 Provenance
Every result file includes: git commit hash and dirty flag, the versions of Rust, Python and dependencies,
the platform, the hash of every input file (experiment YAML, cell files, assumption set, netlist
certificates), the seed, and the wall-clock time.

### 8.6 Stopping and data handling
The replication count is fixed in advance and not extended after looking at results. Failed or invalid runs
are listed in the report and never silently dropped.

## 9. Noise model details (H4)

- Noise is Gaussian with standard deviation `σ` expressed as a fraction of the voltage swing `V`. The
  sweep grid is logarithmic and fixed in the experiment YAML.
- For `L` levels, thresholds lie midway between adjacent levels. This is the optimal placement for
  equiprobable levels and equal variance.
- Per-symbol error → per-effective-bit conversion: a symbol error in an `L`-level digit is counted as a
  digit error for logic-level analysis. For information-level comparison the report uses
  **error per effective bit** = (symbol error rate) / (log2 L), as an upper-level approximation, together with
  the exact value for the Gray-mapped case for L=4. Both are shown.
- The simulator's measured symbol error rates must agree with the analytical `P_sym` formula (H4). A
  disagreement fails the test suite.

## 10. Reporting and the AI text rule

- `radixlab report` produces `report.md` from result files with a template engine. Every number appears via a
  reference to a field in a result file.
- **AI-written text never contains typed numbers.** The AI layer receives result fields and writes prose with
  placeholders (`{{h2.add.energy_ratio}}`). A validator rejects a draft that contains a numeric literal not
  produced by a placeholder, and rejects references to missing fields. Prose that fails the validator is
  discarded.
- The report always includes: the assumption set and each parameter's confidence, the sensitivity result,
  outcome labels (`hypotheses.md` §0.5), failed and invalid runs, and the "red-team" review output.
- Plots: Pareto fronts for speed–energy–area, noise–error curves, tornado diagrams, break-even surfaces.

## 11. Reproducibility

Pinned dependencies (lock file), a Dockerfile, a single-command install, and a fixed-seed "smoke"
experiment that must reproduce a committed result exactly (bit-for-bit for deterministic outputs, and
within the stated CI for stochastic ones) in CI.

## 12. Threats to validity

| Threat | Mitigation or disclosure |
|--------|--------------------------|
| All hardware parameters are assumptions | YAML source notes, `confidence`, ±50% analysis, stress test for low confidence |
| Binary has far greater optimisation maturity | maturity factor as explicit sensitivity dimension |
| Ternary/quaternary memory is the biggest unknown | macros flagged and reported separately; results with and without memory (Q3) |
| Generator bias | same architecture set for all radices; automated best-per-radix search |
| Granularity of digit counts at iso-precision | over-provisioning reported; both ISO modes |
| Wire and routing costs omitted | disclosed (Q4); lines per bit reported separately |
| Noise model is abstract Gaussian | validated against analytic P_sym; no claim about physical noise sources |
| LLM bias or hallucination | AI output is gated by equivalence tests; no numbers in AI text; red-team agent output is reviewed, not trusted |
| Small designs (4 SM × 8 lane) may not scale | scaling experiments reported; design parameterised |
| Researcher degrees of freedom | hypotheses and δ frozen before runs; fixed replication counts; Holm correction |

## 13. Milestone gates

Each milestone ends with: tests passing, `docs/` updated, and a short status note in `docs/status/`.
Uncertainty is written in `docs/open-questions.md`; guesses are not substituted for it.
