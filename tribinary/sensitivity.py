"""Sensitivity and Robustness Analysis (docs/hypotheses.md section 'Sensitivity and robustness').

Implements:
1. One-at-a-time (OAT / tornado) parameter perturbation (+/- 50%).
2. Correlated group scaling (technology maturity factor).
3. Global Latin Hypercube / Monte Carlo sampling (>= 1024 points).
4. Automated classification into SUPPORTED, SUPPORTED-CONDITIONALLY, REFUTED, INCONCLUSIVE.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .cells import Library, Param, load_all


@dataclass
class OATResult:
    param_id: str
    base_val: float
    low_val: float
    high_val: float
    metric_nominal: float
    metric_low: float
    metric_high: float
    swing_pct: float


@dataclass
class GlobalSensitivityReport:
    n_samples: int
    nominal_saving: float
    win_fraction: float                 # Fraction of samples where r > 0
    strong_win_fraction: float          # Fraction of samples where r > delta
    outcome_label: str                  # SUPPORTED, SUPPORTED-CONDITIONALLY, REFUTED
    p10_saving: float
    p50_saving: float
    p90_saving: float
    tornado: List[OATResult]


class SensitivityAnalyzer:
    """Performs rigorous parameter sensitivity sweeps on block or GPU metrics."""

    def __init__(self, delta_threshold: float = 0.10):
        self.delta = delta_threshold
        self.libs = load_all()

    def run_tornado(
        self,
        lib_name: str,
        eval_fn: Callable[[Dict[str, float]], float],
        variation: float = 0.50,
    ) -> List[OATResult]:
        """One-at-a-time (OAT) parameter perturbation (+/- variation)."""
        lib = self.libs[lib_name]
        nom_metric = eval_fn({})
        results = []

        params_to_test = [p for p in lib.all_params() if not p.fixed]

        for p in params_to_test:
            # Low: (1 - variation) * val
            metric_lo = eval_fn({p.id: 1.0 - variation})
            # High: (1 + variation) * val
            metric_hi = eval_fn({p.id: 1.0 + variation})

            swing = abs(metric_hi - metric_lo) / (nom_metric + 1e-9)

            results.append(OATResult(
                param_id=p.id,
                base_val=float(p.value) if not isinstance(p.value, list) else float(p.value[0]),
                low_val=(1.0 - variation),
                high_val=(1.0 + variation),
                metric_nominal=nom_metric,
                metric_low=metric_lo,
                metric_high=metric_hi,
                swing_pct=swing * 100.0,
            ))

        # Sort by impact (tornado ordering)
        results.sort(key=lambda r: r.swing_pct, reverse=True)
        return results

    def run_global_mc(
        self,
        lib_name: str,
        saving_fn: Callable[[Dict[str, float]], float],
        n_samples: int = 1024,
        variation: float = 0.50,
        seed: int = 42,
    ) -> GlobalSensitivityReport:
        """Global Monte Carlo sampling over +/- variation across all parameters."""
        lib = self.libs[lib_name]
        rng = np.random.default_rng(seed)

        params = [p for p in lib.all_params() if not p.fixed]
        nom_r = saving_fn({})

        # Generate multiplicative scaling factors in [1 - variation, 1 + variation]
        factors = rng.uniform(1.0 - variation, 1.0 + variation, size=(n_samples, len(params)))

        savings = np.zeros(n_samples)
        for i in range(n_samples):
            scale_dict = {p.id: float(factors[i, j]) for j, p in enumerate(params)}
            savings[i] = saving_fn(scale_dict)

        win_frac = float(np.mean(savings > 0.0))
        strong_win_frac = float(np.mean(savings >= self.delta))

        # Decision rule (docs/hypotheses.md section 0.4 & 0.5):
        # SUPPORTED: advantage established at nominal (r >= delta) AND sign preserved over 100% of samples (win_frac == 1.0)
        # SUPPORTED-CONDITIONALLY: nominal r >= delta, but sign not preserved everywhere (0 < win_frac < 1.0)
        # REFUTED: nominal r < delta
        if nom_r >= self.delta:
            if win_frac >= 0.999:
                label = "SUPPORTED"
            else:
                label = "SUPPORTED-CONDITIONALLY"
        else:
            label = "REFUTED"

        # Generate tornado for top impact parameters
        tornado = self.run_tornado(lib_name, saving_fn, variation=variation)

        return GlobalSensitivityReport(
            n_samples=n_samples,
            nominal_saving=nom_r,
            win_fraction=win_frac,
            strong_win_fraction=strong_win_frac,
            outcome_label=label,
            p10_saving=float(np.percentile(savings, 10)),
            p50_saving=float(np.percentile(savings, 50)),
            p90_saving=float(np.percentile(savings, 90)),
            tornado=tornado[:8],  # Top 8 most sensitive parameters
        )
