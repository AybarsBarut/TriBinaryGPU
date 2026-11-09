# Contributing to TriBinary

Thank you for your interest in contributing to TriBinary. This repository is dedicated to **reproducible, unvarnished scientific simulation** of multi-valued logic architectures.

## Core Rules of Engagement

1. **Maintain Scientific Neutrality:** Never bias simulations or select parameters to favour or disadvantage any logic radix. Report negative or unexpected results honestly.
2. **Assumption Tracking:** Every new hardware parameter (delay, transistor count, energy, area) must be accompanied by an explicit source note and a `confidence: low|medium|high` indicator. Low-confidence parameters are automatically subject to ±50% sensitivity analysis.
3. **The Verification Gate:** Any new cell, block netlist, or ISA instruction must pass exhaustive (for small widths) or random (for large widths) equivalence tests against an independent golden mathematical model before being admitted into simulation results.
4. **No Naked Numbers in AI Summaries:** LLM-assisted text or reporting must strictly use template placeholders (e.g. `{{metric_name}}`). Manually typed or hallucinated numerical literals in report narratives are rejected.

---

## How to Add a New Cell Library

1. Create or edit `cells/<library_name>.yaml`.
2. Follow the assumption schema specified in `docs/assumptions.md`.
3. Add the corresponding golden truth table function in `tribinary/golden.py`.
4. Run `pytest tests/test_cells.py` to ensure truth table integrity (L0).

---

## How to Add a New Workload

1. Place the workload definition under `workloads/<workload_name>.py`.
2. Provide:
   - The unified assembly kernel text (`*_ASM`).
   - A golden reference evaluation function (`generate_*_data`).
3. Add a parity test in `tests/test_workloads_m3.py`.
4. Include the workload in `experiments/m3_full_gpu.yaml` and re-run `tribinary run experiments/m3_full_gpu.yaml`.

---

## How to Contribute Community Results

Share verified results by opening a pull request with your output JSON file in `results/community/<your_experiment_name>.json`. Include environmental provenance (commit hash, platform, and dependencies).
