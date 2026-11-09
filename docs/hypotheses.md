# TriBinary — Pre-registered Hypotheses

Status: **frozen as `prereg-v1`** (2026-11-09, after M0 approval). Any later change follows §0.8.

The goal is to test hypotheses and report what is found. A negative result for ternary or quaternary
logic is as valid as a positive one.

## 0. Common definitions

### 0.1 Designs under test

| ID | Name | Number system | Hardware logic | Purpose |
|----|------|---------------|----------------|---------|
| GPU-B  | Binary | two's complement | binary cells | reference |
| GPU-T  | Balanced ternary | digits {-1,0,+1} | ternary cells | system under test |
| GPU-Q-1b | Quaternary, 1 bit/cell memory | base 4, digits {0,1,2,3} | quaternary logic cells, binary (1 bit/cell) memory macros | system under test; isolates the logic |
| GPU-Q-2b | Quaternary, 2 bit/cell memory | base 4, digits {0,1,2,3} | quaternary logic cells, multi-level (2 bit/cell) memory macros | system under test; adds the multi-level memory gain |
| GPU-BT | Binary-encoded ternary | balanced ternary, 2 bits per trit | binary cells | **control**: separates "ternary math" from "ternary hardware" |

GPU-Q-1b and GPU-Q-2b are always **reported separately** and never merged. A gain of GPU-Q-2b over
GPU-Q-1b is a multi-level-memory gain, not a logic-radix gain (decision Q8).

All designs share one microarchitecture template. Only the number system, the cell library and (for the
two GPU-Q variants) the memory macro differ.

### 0.2 Effect decomposition (used by H2, H3, H5)

For any metric `M`:

- Total effect = `M(GPU-T) / M(GPU-B)`
- Number-system and encoding effect = `M(GPU-BT) / M(GPU-B)`
- Hardware effect = `M(GPU-T) / M(GPU-BT)`

The total effect is the product of the other two. GPU-BT pays a 2-bit-per-trit encoding overhead, so the
encoding effect conflates "ternary arithmetic is cheaper or dearer" with "the encoding wastes
log2(4/3) ≈ 0.415 bit per trit". We report both and do not hide this.

### 0.3 Comparison modes

Every comparison is reported in **both** modes, as required.

- **ISO-PRECISION:** the smallest digit count `n` with `r^n ≥ 2^b` for a target of `b` effective bits.
  Examples: 8 bits → 6 trits (9.51 bits, over-provisioned) or 5 trits (7.92 bits, which fails the 8-bit
  target). The granularity loss is reported explicitly. For quaternary, `n = b/2`.
- **ISO-AREA:** lane and SM counts are scaled until total area (cell area plus macro area, reported with
  and without macros) is equal within 2%. Throughput, energy and perf/W are then compared at that scale.

### 0.4 Practical-significance threshold and decision rule (frozen in `prereg-v1`)

`δ = 10%` (decision Q13). Define the **relative saving** of design X over reference B for a metric where
lower is better:

`r = 1 − M(X) / M(B)`   (r > 0: X is better; for higher-is-better metrics, `r = 1 − M(B) / M(X)`).

`δ` applies to the **primary metric at nominal parameters**. The decision is based on the position of the
confidence interval `[r_lo, r_hi]` of `r` relative to `δ`. **A p-value alone never decides**, because it can
be made arbitrarily small by adding replications. For deterministic metrics (structural counts, static
timing) there is no sampling uncertainty and the interval is the point `[r, r]`.

Nominal decision (primary metric, nominal parameters):

| Condition | Nominal verdict |
|-----------|-----------------|
| `r_lo > δ` and Holm-adjusted p < α (where a p-value exists) | advantage established |
| `r_hi < δ` | advantage **not** established (refuted: effect smaller than δ, absent or reversed) |
| otherwise (interval contains δ, or Holm filter fails) | undecided |

Sensitivity condition (the ±50% parameter range of "Sensitivity and robustness" below): the **sign of `r`**
must be preserved over the sensitivity range. "Preserved" is defined strictly: `r > 0` at every
one-at-a-time ±50% point and every group-scaling corner, and the fraction of global-sample points with
`r > 0` is reported (for the label it must be 100%; a smaller fraction makes the label conditional and the
favourable region is written out). See open question Q17 for this interpretation.

Equivalence ("no meaningful difference") is tested with TOST using the margin `δ` and is only used on
secondary metrics.

### 0.5 Outcome classes

Each hypothesis (and sub-hypothesis) receives exactly one label per design pair, determined by the
nominal verdict and the sensitivity condition of §0.4:

1. **SUPPORTED:** advantage established at nominal parameters **and** the sign of `r` is preserved over the whole ±50% range.
2. **SUPPORTED-CONDITIONALLY:** advantage established at nominal parameters, but the sign is not preserved everywhere. The report states the favourable subrange.
3. **REFUTED:** advantage not established at nominal parameters. If the sensitivity analysis finds a region where `r > δ`, the label stays REFUTED and the region is reported as an annotation.
4. **INCONCLUSIVE:** the nominal verdict is undecided (interval contains δ, or the Holm filter fails).

Metrics other than the single primary metric of a hypothesis and design pair are **exploratory**. They are
reported and labelled "exploratory" and never decide a label.

### 0.6 Units of replication

Deterministic simulations give the same answer on every run, so repeating them is not replication.
Replication units are therefore:

- noise seeds (noisy experiments, ≥30);
- workload input seeds (random data, random scenes, random weights; ≥30);
- parameter-sampling draws (sensitivity analysis; ≥1024).

Tests are applied across these units and never across repeated identical runs.

### 0.7 Multiplicity

The primary comparisons form one family (decision Q14): **one primary metric per hypothesis and design
pair** (see `methodology.md` §8). The family-wise error rate is controlled with Holm correction at
α = 0.05, and the Holm-adjusted p-value is an **additional filter** on top of the interval rule of §0.4,
not a decision criterion on its own. All other analyses are labelled exploratory.

### 0.8 Freeze

This file is frozen by the git tag `prereg-v1` and by `docs/prereg-v1.lock` (SHA-256 of the normalised
text, checked by a test). A later change requires a new tag (`prereg-v2`), an entry in
`docs/prereg-changelog.md`, and must be made before the affected experiments run.

---

## H1 — Radix economy

**Claim.** For equal information capacity, a ternary data path needs fewer lines and cells. Does the higher
per-cell cost cancel this?

**Theory (checked in code, not assumed).** The radix-economy cost of a number of range `N` in radix `r` is
`E(r,N) = r · ⌈log_r N⌉`. In the continuous limit the cost per unit of information is proportional to
`r / ln r`:

| r | r / ln r | relative to r=2 |
|---|----------|-----------------|
| 2 | 2.885 | 1.000 |
| 3 | 2.731 | 0.946 |
| 4 | 2.885 | 1.000 |

So radix 3 is about 5.4% better than radix 2 in this idealised metric, and **radix 4 equals radix 2**
(consistent with quaternary being a pair of bits). The ideal advantage is small. The per-cell cost
multiplier is the dominant term, so H1 is a break-even question.

- **H0₁:** At iso-precision, transistor count per effective bit (and line count per effective bit) of
  ternary storage and data-path blocks is at least `(1 − δ)` times the binary value.
- **H1₁:** It is lower than `(1 − δ)` times the binary value.

**Metrics.**
- Lines per effective bit.
- Transistors per effective bit, for these blocks: register bit, 2:1 mux, N-bit adder, N-bit bus.
- **Break-even cell-cost multiplier `c*`:** the factor on ternary per-cell transistor cost at which the
  advantage vanishes. Analytical lower bound for lines: `c* = log2(3) ≈ 1.585`. The empirical value comes
  from the generated netlists.
- Granularity loss (the over-provisioning from §0.3).

**Refutation condition.** Under the central parameter set the ternary ratio is ≥ `1 − δ`, or `c*` is below
the plausible range of the ternary-to-binary cell-cost ratio in `cells/*.yaml`.

**Statistics.** Structural counts are deterministic and need no hypothesis test. Uncertainty comes from the
cell parameters, and is handled by Monte Carlo over the ±50% range. We report the fraction of the
parameter space in which H1₁ holds. For the set of blocks we also report a bootstrap CI of the geometric
mean ratio, so the result is not one lucky block.

**Out of scope for H1.** Wire capacitance and routing (open question Q4). Lines are counted but not
physically placed.

---

## H2 — Balanced-ternary arithmetic

**Claim.** Negation is a per-trit flip, truncation equals round-to-nearest, and the sign comes from the
top trit. Does this give gate-count or delay advantages in the adder, multiplier and comparator?

**Premise check (done before testing).**
- *Negation* is a per-trit flip: **true.** Two's-complement negation needs an invert plus a +1 carry
  (or a fused adder), so ternary saves a carry chain.
- *Truncation equals round-to-nearest:* **true.** Dropping `k` low trits leaves a remainder in
  `[-(3^k−1)/2, +(3^k−1)/2]`. This is symmetric and tie-free, and therefore unbiased.
- *"The sign is the top trit":* **only partly true.** The sign of a balanced-ternary number is the sign of
  the **most significant non-zero trit**. If the top trit is 0, the sign cannot be read from it. Two's
  complement reads the sign in O(1) from the MSB. Sign extraction in ternary needs a leading-zero scan
  (O(log n) depth) or must be produced by the subtractor's carry logic. This may remove part of the
  claimed comparator advantage. We keep the claim in the hypothesis and let the data decide.
- *Multiplication:* a trit × trit product is a sign product, which is cheap. But the number of partial
  products and the adder tree it feeds are what matter. This has to be measured.

- **H0₂:** For each operation in {add, subtract, negate, round-to-nearest, sign, compare, multiply, MAC}
  at iso-precision, at least one of gate count, critical-path delay or energy per operation of GPU-T
  is not lower than GPU-B's by more than `δ`.
- **H1₂:** GPU-T is lower than GPU-B by more than `δ` on all three metrics, for the stated operations.
  This is evaluated per operation, never aggregated into one headline.

**Primary metric (clarification made at freeze time, per decision Q14).** Each (operation, design pair,
iso-precision width) is one comparison with **one primary metric: static critical-path delay**, because the
sign-detection premise is a statement about logic depth. Gate count, transistor count, area and
energy per operation are **exploratory** for the label. The break-even cost multiplier `c*` of the primary
metric is reported next to it. The conjunctive H1₂ wording above is the *scientific claim*; the label of
each comparison follows the primary metric only, and the exploratory metrics are shown beside it so a
delay win that costs area or energy is visible.

**Metrics.** Per operation: gate count, transistor count, critical-path delay (gate levels and ps),
switching energy per operation (activity-weighted), and leakage. All four designs, with effect
decomposition per §0.2. Architectures: every adder and multiplier architecture in the generator library
(ripple, lookahead, carry-select, Wallace or equivalent) is built for every radix. The best per
radix per metric is selected by automated search. This avoids hand-tuned bias.

**Refutation condition.** Under the ±50% parameter range, GPU-T fails to beat GPU-B by `δ` on an
operation. That operation is refuted. A sub-hypothesis is refuted if the advantage appears only in GPU-BT
(then it is "math", not hardware) or only in GPU-T (then it depends on the hardware cell assumptions).

**Statistics.** Gate counts and delay are deterministic. Energy is measured on `≥10^4` random operand
pairs per operation. The pairs are matched by **numeric value** across encodings, and each pair is
simulated on every design. Test: Wilcoxon signed-rank on per-operation energy, Hodges–Lehmann shift
estimate with bootstrap CI (10k resamples), paired rank-biserial correlation as effect size. Equivalence
by TOST with margin `δ`.

---

## H3 — Geometry and rasterisation

**Claim.** Triangle (edge-function sign test) and circle (SDF / midpoint) drawing are dominated by sign
tests and rounding. In balanced ternary these workloads are cheaper.

**Reformulation.** "Drawing shapes is easier when not binary" is **not** a testable statement as phrased.
It becomes: *what share of the cycles and energy of these workloads is spent on sign and rounding
operations, and how much cheaper are those operations on GPU-T?* Both the share and the saving are
measured. If the share is small, the effect is bounded by it (Amdahl) whatever the saving is.

Complications we expect and record:
- The edge function `E(x,y) = (x−x0)(y1−y0) − (y−y0)(x1−x0)` is two multiplies and a subtract. The sign
  test is a small part. Multiplier cost is expected to dominate.
- Midpoint circle uses doublings and quadruplings. These are shifts in binary and ×3 scalings in ternary,
  so the incremental coefficients differ by radix. The golden model is defined on pixel results, and the
  kernel is derived separately per radix.
- Frame-buffer addressing assumes a power-of-two width in binary and a power-of-three width in ternary.
  The scene sizes and the address-cost accounting are fixed in the experiment YAML.

Sub-hypotheses:
- **H3a (number system):** GPU-BT vs GPU-B.
- **H3b (hardware):** GPU-T vs GPU-BT.
- **H3c (attribution):** the share of energy and cycles in sign/round operations (measured per workload
  with an instruction-class profile).

- **H0₃:** The cycle count and energy per covered pixel of GPU-T is not lower than GPU-B's by more
  than `δ`.
- **H1₃:** It is lower by more than `δ`.

**Metrics.** Cycles per pixel, energy per pixel, instruction-class profile, attribution share (H3c),
and **correctness**: the coverage mask is bit-exact with the golden reference (top-left fill rule fixed).
A run that is not bit-exact is invalid.

**Statistics.** `≥30` random scenes (seeded triangles with varied area and aspect ratio, and circles with
varied radii). Paired by scene. Wilcoxon signed-rank, bootstrap CI, Cliff's δ.

**Refutation condition.** The CI includes 0, or the effect is < `δ`, or the attribution share (H3c) is
too small to explain the effect.

**Related side experiment.** A 3-level pixel channel is tried as a workload (it is a workload, not a
justification of logic radix). See `faq.md`.

---

## H4 — Noise

**Claim.** For a fixed voltage swing, adding levels shrinks the noise margin, roughly as `1/(2(L−1))` of
the swing. Do the error rate and the cost of correction cancel the density advantage?

**Analytical reference (a cross-check on the Monte Carlo, not a replacement).** With `L` equally spaced
levels over a swing `V`, spacing is `V/(L−1)` and the half-margin is `m = V/(2(L−1))`. With Gaussian noise
of standard deviation `σ`, the symbol error probability averaged over equiprobable levels is:

`P_sym(L, σ) = 2 (L−1)/L · Q(m/σ)`

(edge levels have one-sided error, interior levels two-sided). The margins relative to `V` are:
binary 1/2, ternary 1/4, quaternary 1/6. The Monte Carlo output must agree with this formula within the
binomial CI. If it does not, the simulator has a bug.

The per-symbol error must also be converted to per-effective-bit information loss. Otherwise L=4
(2 bits per symbol) and L=2 are not on the same footing. The conversion rule is fixed in
`methodology.md` §9.

- **H0₄:** At the `σ` where GPU-B reaches a target residual error rate, the total cost
  (area × energy × delay of the data path plus ECC) of GPU-T/Q is not lower than GPU-B's.
- **H1₄:** It is lower by more than `δ`.

**Metrics.**
- Symbol and bit error rate vs `σ/V` (curves, per `L`).
- Workload-level silent data corruption (SDC) rate, which accounts for logical masking.
- ECC overhead needed to reach residual error targets (initial targets `10^-6` and `10^-9` per word
  operation). ECC encoders and decoders are generated as netlists, like everything else: SECDED
  (Hamming) for binary, and a ternary Hamming-type code over GF(3) for ternary.
- Cost with correction, and the **crossover `σ*`**: the noise level at which one design overtakes another.

**Refutation condition.** Total cost with correction is not lower than binary's at any realistic
`σ/V` range. Realistic means within the parameter's stated range. If an advantage exists only at a
`σ` where binary has near-zero errors anyway, the result is reported as "no practical advantage".

**Statistics.** `≥30` independent noise seeds per `(L, σ)` point. Error rates have Wilson/Clopper–Pearson
intervals. Rare events (`<10^-6`) use importance sampling with the weights recorded. Comparison is
a log-ratio of rates with a bootstrap CI. Agreement with the analytical `P_sym` is tested with an
exact binomial test.

**Documented non-claim.** Quaternary is logically a pair of bits. Any quaternary difference arises only
from multi-level signalling (MLC-like), and not from the logic (`faq.md`).

---

## H5 — Neural workloads (ternary-weight inference)

**Claim.** Inference with weights in {-1,0,+1} (BitNet b1.58 style) needs no multiplier on ternary
hardware. What is the perf/W difference?

**Honest baseline.** Ternary-weight inference is also multiplier-free on binary hardware: a 2-bit
weight selects `+x`, `0` or `−x`, and the MAC becomes a conditional negate-and-add. If the comparison were
against a binary INT8 MAC kernel only, the result would credit ternary hardware for an advantage that
comes from the *model*. The following four variants are therefore all compared:

| Variant | Hardware | Kernel |
|---------|----------|--------|
| V1 | GPU-B | INT8 multiply-accumulate |
| V2 | GPU-B | ternary-weight conditional add/sub (multiplier-free) — **the correct baseline** |
| V3 | GPU-BT | ternary-weight kernel |
| V4 | GPU-T | ternary-weight kernel, run **with** and **without** the activation-format conversion cost (activations are produced as INT8 in BitNet-style models) |

Zero-weight skipping and weight-sparsity are varied (zero fraction ∈ {1/3, 0.5, 0.7}), because ternary
hardware and binary hardware may exploit zeros differently.

Weight-storage density (1.58 bits per weight vs 2) depends on the memory-macro assumption, which is the
most uncertain parameter in the study (open question Q3). Results are reported with and without
the memory term.

- **H0₅:** The perf/W of V4 is not above V2's by more than `δ`.
- **H1₅:** It is above V2's by more than `δ`.

**Metrics.** Cycles, energy and perf/W per inference; inferences per second per mm²-equivalent area;
accuracy parity with the golden reference (outputs are integers, so parity means exact equality; the
accuracy of the model on a task is not the object of study); memory footprint.

**Statistics.** `≥30` random seeds for weights, activations and sparsity patterns. Paired by seed.
Wilcoxon signed-rank, bootstrap CI, paired rank-biserial correlation. Effect decomposition per §0.2 using
V2, V3, V4 (V1 is reported for context only).

**Refutation condition.** V4 does not beat V2 by `δ` in perf/W under the central parameters, or the advantage
disappears with the activation-conversion cost included, or only appears when the memory term is excluded.

---

## Sensitivity and robustness (applies to all hypotheses)

Every hardware parameter is an assumption, tracked in YAML with a source note and `confidence`
(`assumptions.md`). Each hypothesis is tested:

1. **One-at-a-time ±50%** of each parameter (tornado diagram).
2. **Group scaling:** parameters expected to be systematically biased together (e.g. all ternary cell
   parameters scaled by a common factor, a "technology maturity" factor) are scaled jointly, because
   independent sampling understates correlated bias.
3. **Global sampling:** Latin hypercube or Sobol sample (≥1024 points) within ±50%, giving the win
   fraction, rank-correlation sensitivity indices and break-even surfaces.
4. **Stress (supplementary, not primary):** parameters with `confidence: low` are also widened to ±100%
   to show whether a conclusion is fragile.

A conclusion that holds only in a subrange is reported as SUPPORTED-CONDITIONALLY with the range written
out.

## Reporting rules

- Unexpected and negative results go in the report body.
- Numbers in the narrative are injected from result files by template. Neither a person nor an LLM types
  a number into the text (`methodology.md` §10).
- A conclusion that depends on a parameter with `confidence: low` carries that label in the report.
