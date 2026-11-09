# RadixLab

Binary vs ternary vs quaternary logic: a reproducible gate-level simulation laboratory for comparing
GPU microarchitectures that differ only in number base and cell library.

**Status: M1 (simulator core, cell libraries, adder/multiplier verification, comparator micro-experiment).**
See `docs/status/` for the latest status note, `docs/hypotheses.md` for the frozen hypotheses
(`prereg-v1`) and `docs/open-questions.md` for known uncertainties.

All hardware parameters in `cells/` are **assumptions** (source note and `confidence` per value). Results
are valid only inside the stated assumption ranges.

## Quick start (development)

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install maturin pytest numpy scipy pyyaml matplotlib
.\.venv\Scripts\maturin develop --release
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m radixlab verify --suite m1
.\.venv\Scripts\python -m radixlab micro experiments/m1_comparator.yaml
```

Rust unit tests: `cd core; cargo test`.

License: Apache-2.0.
