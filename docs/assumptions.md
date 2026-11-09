# RadixLab — Assumption Schema

Status: **M0 draft, awaiting approval.** The machine-readable JSON Schema is written in M1 from this
specification and enforced by the loader and in CI.

**Every hardware parameter is an assumption.** Nothing in RadixLab is a measurement of real silicon unless
a field says so. Each parameter carries a source note and a confidence level. Results are reported with
sensitivity analysis over ±50%.

## 1. Parameter record

Every numeric parameter in any cell or microarchitecture YAML file has this form:

```yaml
param_name:
  value: 4                   # central value (required)
  unit: transistors          # required; SI-prefixed units, e.g. ps, fJ, nW, um2
  source_type: derived       # required: measured | published | derived | estimate | guess
  source: "CMOS NAND2 topology (4 transistors)"   # required, non-empty, honest
  confidence: high           # required: low | medium | high
  group: binary_cell_cost    # optional: correlated-scaling group (see §2)
  range:                     # optional override of the default sensitivity range
    min: 4
    max: 4
  notes: ""                  # optional
```

Rules:

1. `value`, `unit`, `source_type`, `source` and `confidence` are all required. A loader rejects a parameter
   missing any of them.
2. `source` must say what the number is based on. The value `TODO` is allowed **only** in a file
   marked `status: draft`, and a draft file cannot be used in a result.
3. Citations must be real and checkable. A reference we have not verified is written as `estimate` or
   `guess`, never as `published`.
4. `confidence` is a judgement about how well the number represents a plausible real implementation:
   - `high`: derived from structure or topology (e.g. transistor count of a standard CMOS gate).
   - `medium`: published values in a comparable technology, adapted by a documented rule.
   - `low`: an estimate, a scaled guess, or technology that is not established (most ternary and
     quaternary cell values).
5. The default sensitivity range is `[0.5 × value, 1.5 × value]` (±50%). `range` can only be used
   to *narrow* a physically bounded parameter (e.g. an integer transistor count that cannot be fractional),
   and the reason must be given in `notes`. Primary sensitivity analysis always uses the default range
   unless this override is present.
6. Parameters with `confidence: low` are additionally stressed at ±100% (`hypotheses.md`, stress test).
7. Parameter values are never changed after results are produced without re-running the affected
   experiments. Every result file stores the hash of its assumption set.

## 2. Parameter groups and derived parameters

- `group` ties parameters that are expected to be biased together (for example `ternary_cell_cost`,
  `ternary_cell_delay`, `memory_macro_density`). Group scaling multiplies all members by one common random
  factor. This is the "technology maturity" dimension (`hypotheses.md`).
- A **derived** parameter (e.g. area from transistor count and a per-transistor area) is declared
  with `derived_from` and a formula, and is recomputed during sensitivity sampling rather than sampled
  independently:

```yaml
area:
  derived_from: [transistors, area_per_transistor]
  formula: "transistors * area_per_transistor"
  unit: um2
  source_type: derived
  source: "product of two parameters above"
  confidence: low        # the minimum of its inputs' confidence
```

## 3. Cell record

Each file in `cells/` has a header and a list of cells.

```yaml
library: ternary            # binary | ternary | quaternary
version: 0.1.0
status: draft               # draft | reviewed ; only `reviewed` can enter results
levels: [-1, 0, 1]          # logic values; ternary may also use X
voltage_swing:
  value: 1.0
  unit: V
  source_type: guess
  source: "normalised swing; absolute value cancels in ratios"
  confidence: medium
cells:
  - name: STI
    inputs: 1
    function: "-a"                    # reference to a golden function in the golden-model registry
    truth_table_ref: golden.ternary.sti
    macro: false                      # true only for memory-array macros
    transistors: {value: ..., unit: transistors, ...}   # full parameter record
    area:        {...}
    delay:       {value: ..., unit: ps, ...}
    switch_energy: {value: ..., unit: fJ, ...}
    leakage:     {value: ..., unit: nW, ...}
    noise_margin_fraction: {value: ..., unit: fraction_of_swing, ...}
```

Required fields per cell: `name`, `inputs`, `function`, `macro`, `transistors`, `area`, `delay`,
`switch_energy`, `leakage`, `noise_margin_fraction`. A cell also carries (or references) a **truth table**
that is checked against the golden function (verification level L0).

`noise_margin_fraction` defaults to `1 / (2 (L − 1))` for `L` levels if a cell file does not override it,
and the default is recorded as `source_type: derived`.

Planned cell sets (M1):
- **Binary:** NOT, NAND, NOR, XOR, MUX, D-flip-flop, full adder.
- **Ternary:** STI/NTI/PTI, MIN, MAX, consensus, half adder, full adder, trit multiplier, trit register.
- **Quaternary:** MIN, MAX, successor, adder cells.

## 4. Memory macros

Macro models (register file, shared memory, L1) are parametric and are the only non-gate-level
blocks. A macro record has: capacity, word width, `bits_per_cell` (1 for SRAM-like binary storage, `log2 L`
for multi-level), area per bit, read/write energy per access, leakage per bit, read latency, and a mandatory
`macro: true` flag. The same record format carries source and confidence. Macro parameters are
`confidence: low` for multi-level storage unless a specific source is verified.

## 5. Microarchitecture parameters

Template parameters (SM count, lanes, warp size, register count, cache sizes) are **design choices**, not
assumptions, and live in the experiment or GPU YAML with `source_type: design`. They are not subject to
±50% sensitivity unless a scaling experiment varies them on purpose.

## 6. Illustrative example (not used in any result)

This example shows the format only. The values are placeholders that illustrate the structure and must not
be quoted. Real values are sourced in M1.

```yaml
- name: NAND2
  library: binary
  status: draft
  transistors:
    value: 4
    unit: transistors
    source_type: derived
    source: "static CMOS NAND2 topology"
    confidence: high
    range: {min: 4, max: 4}
    notes: "integer topology count; not varied by sensitivity analysis"
  delay:
    value: 1.0
    unit: normalized_unit_delay
    source_type: guess
    source: "unit-delay normalisation; absolute value fixed by technology scaling factor"
    confidence: low
    group: binary_cell_delay
```

## 7. Where assumptions are shown

- The `radixlab assumptions` command prints every parameter with confidence and group.
- Each report has an assumptions table and lists which conclusions depend on `low` confidence values.
- This file defines the format. The current values are the YAML files in `cells/` and are not duplicated
  here.
