"""Noise model and error injection (Hypothesis H4 and docs/methodology.md section 9).

Models additive Gaussian noise with standard deviation sigma expressed as a fraction
of the voltage swing V. Verifies that empirical symbol error rates match the analytical
formula P_sym(L, sigma) = 2 * (L - 1) / L * Q(m / sigma), where m = 1 / (2 * (L - 1)).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats

from . import golden


def q_function(x: float) -> float:
    """Standard normal tail probability Q(x) = 0.5 * erfc(x / sqrt(2))."""
    if x <= 0:
        return 1.0 - 0.5 * math.erfc(-x / math.sqrt(2))
    return 0.5 * math.erfc(x / math.sqrt(2))


def analytical_symbol_error_rate(L: int, sigma: float) -> float:
    """Analytical symbol error probability for L equally spaced levels under Gaussian noise."""
    if sigma <= 0:
        return 0.0
    half_margin = 1.0 / (2.0 * (L - 1))
    q_val = q_function(half_margin / sigma)
    return 2.0 * ((L - 1) / L) * q_val


def inject_noise(
    system: str,
    clean_digits: np.ndarray,
    sigma: float,
    rng: Optional[np.random.Generator] = None,
) -> Tuple[np.ndarray, float]:
    """Inject Gaussian noise into digit values and re-quantize to nearest valid level.

    Returns:
        (noisy_digits, empirical_symbol_error_rate)
    """
    if sigma <= 0:
        return clean_digits.copy(), 0.0

    r = golden.RADIX[system]
    generator = rng or np.random.default_rng()

    # Map logic values to normalized voltage levels in [0.0, 1.0]
    # For L levels, spacing is delta = 1 / (L - 1)
    # L=2: 0 -> 0.0, 1 -> 1.0
    # L=3: -1 -> 0.0, 0 -> 0.5, +1 -> 1.0
    # L=4: 0 -> 0.0, 1 -> 0.333, 2 -> 0.667, 3 -> 1.0
    delta = 1.0 / (r - 1)
    if system == "t":
        # Values in {-1, 0, 1} -> levels {0, 1, 2}
        level_indices = clean_digits + 1
    else:
        level_indices = clean_digits

    voltages = level_indices * delta

    # Add Gaussian noise: N(0, sigma^2)
    noise = generator.normal(loc=0.0, scale=sigma, size=voltages.shape)
    noisy_voltages = voltages + noise

    # Quantize to nearest level index in 0..r-1
    quantized_indices = np.clip(np.round(noisy_voltages / delta), 0, r - 1).astype(np.int64)

    if system == "t":
        noisy_digits = quantized_indices - 1
    else:
        noisy_digits = quantized_indices

    # Empirical symbol error rate
    errors = np.sum(noisy_digits != clean_digits)
    total_symbols = clean_digits.size
    ser = float(errors / total_symbols) if total_symbols > 0 else 0.0

    return noisy_digits, ser


@dataclass
class NoiseSweepResult:
    system: str
    L: int
    sigma: float
    analytical_ser: float
    empirical_ser: float
    n_samples: int
    ci_low: float
    ci_high: float
    binomial_p_value: float


def run_noise_sweep(
    system: str,
    sigmas: List[float],
    n_symbols: int = 50_000,
    seed: int = 42,
) -> List[NoiseSweepResult]:
    """Run empirical noise sweep across sigmas and test binomial agreement with theory."""
    r = golden.RADIX[system]
    rng = np.random.default_rng(seed)
    results = []

    # Generate equiprobable random digits
    clean_digits = rng.integers(0, r, size=n_symbols)
    if system == "t":
        clean_digits = clean_digits - 1

    for s in sigmas:
        theory = analytical_symbol_error_rate(r, s)
        _, emp = inject_noise(system, clean_digits, s, rng=rng)
        k_errors = int(round(emp * n_symbols))

        # Exact binomial two-sided test against analytical theory
        res_test = stats.binomtest(k_errors, n_symbols, theory, alternative="two-sided") if theory > 0 else None
        p_val = float(res_test.pvalue) if res_test else 1.0
        ci = res_test.proportion_ci(confidence_level=0.95) if res_test else (emp, emp)

        results.append(NoiseSweepResult(
            system=system,
            L=r,
            sigma=s,
            analytical_ser=theory,
            empirical_ser=emp,
            n_samples=n_symbols,
            ci_low=float(ci[0]),
            ci_high=float(ci[1]),
            binomial_p_value=p_val,
        ))

    return results
