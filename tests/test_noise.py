"""Verification tests for the Gaussian noise model and analytical P_sym agreement (Hypothesis H4)."""
from __future__ import annotations

import pytest

from radixlab.noise import analytical_symbol_error_rate, inject_noise, q_function, run_noise_sweep


def test_q_function():
    # Q(0) = 0.5
    assert abs(q_function(0.0) - 0.5) < 1e-7
    # Q(3) ~ 0.00135
    assert abs(q_function(3.0) - 0.001349898) < 1e-5


def test_analytical_symbol_error_rate_ordering():
    # For same noise sigma, L=4 has worse SER than L=3, which is worse than L=2
    sigma = 0.10
    ser_b = analytical_symbol_error_rate(2, sigma)
    ser_t = analytical_symbol_error_rate(3, sigma)
    ser_q = analytical_symbol_error_rate(4, sigma)

    assert ser_b < ser_t < ser_q
    # Half margins: m_b = 0.5, m_t = 0.25, m_q = 0.1667
    assert ser_b < 1e-5  # Binary has virtually zero errors at sigma=0.10
    assert ser_t > 0.005  # Ternary already incurs errors
    assert ser_q > 0.05   # Quaternary incurs significant errors


def test_empirical_noise_sweep_binomial_agreement():
    """Verify that empirical noise simulation matches the analytical formula within binomial CI."""
    sigmas = [0.15, 0.25]
    sweep_t = run_noise_sweep("t", sigmas=sigmas, n_symbols=20000, seed=123)

    for res in sweep_t:
        assert res.ci_low <= res.analytical_ser <= res.ci_high or res.binomial_p_value > 0.01
        assert abs(res.empirical_ser - res.analytical_ser) < 0.03
