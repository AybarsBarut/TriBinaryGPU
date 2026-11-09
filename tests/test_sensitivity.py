"""Verification tests for Tornado and Global Monte Carlo sensitivity analysis."""
from __future__ import annotations

import pytest

from tribinary.sensitivity import SensitivityAnalyzer


def test_tornado_analysis():
    analyzer = SensitivityAnalyzer(delta_threshold=0.10)

    # Simple mock evaluation function where param 'ternary.energy_per_transistor' has highest impact
    def eval_fn(scale_dict):
        f1 = scale_dict.get("ternary.energy_per_transistor", 1.0)
        f2 = scale_dict.get("ternary.tau", 1.0)
        return 10.0 * f1 + 2.0 * f2

    tornado = analyzer.run_tornado("ternary", eval_fn, variation=0.50)
    assert len(tornado) > 0
    # Top impact should be energy_per_transistor
    assert tornado[0].param_id == "ternary.energy_per_transistor"
    assert tornado[0].swing_pct > tornado[-1].swing_pct


def test_global_monte_carlo_classification():
    analyzer = SensitivityAnalyzer(delta_threshold=0.10)

    # 1. Function that is always > delta
    rep_supported = analyzer.run_global_mc("ternary", lambda sc: 0.25, n_samples=50)
    assert rep_supported.outcome_label == "SUPPORTED"
    assert rep_supported.win_fraction == 1.0

    # 2. Function with nominal < delta
    rep_refuted = analyzer.run_global_mc("ternary", lambda sc: -0.15, n_samples=50)
    assert rep_refuted.outcome_label == "REFUTED"
