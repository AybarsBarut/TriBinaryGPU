"""Differential testing: Rust engine vs pure-Python reference evaluator (closed decision Q9)."""
from __future__ import annotations

import numpy as np
import pytest

from radixlab import cells
from radixlab.gen.adders import build_adder
from radixlab.gen.comparators import build_sign_detect
from radixlab.gen.multipliers import build_multiplier
from radixlab.reference import ReferenceEvaluator


@pytest.fixture(scope="module")
def libs():
    return cells.load_all()


@pytest.mark.parametrize("system,n", [("b", 4), ("t", 3), ("q", 2)])
def test_differential_adder(libs, system, n):
    block = build_adder(libs, system, n, arch="ripple")
    nl = block.netlist
    ref = ReferenceEvaluator(nl.spec())

    # Generate random test vectors
    rng = np.random.default_rng(1234)
    r = libs[nl.lib.name].radix
    n_in = len(nl.inputs)
    test_vectors = rng.integers(0, r, size=(500, n_in), dtype=np.uint8)

    rust_out = nl.simulate(test_vectors)
    py_out = ref.eval_batch(test_vectors)

    np.testing.assert_array_equal(rust_out, py_out)


def test_differential_ternary_x_pessimism(libs):
    """Test that both engines propagate unknown X (code 3) identically and soundly."""
    block = build_sign_detect(libs, "t", 3, arch="tree")
    nl = block.netlist
    ref = ReferenceEvaluator(nl.spec())

    # Include code 3 (unknown X) in the input vectors
    inputs = np.array([
        [0, 0, 3],  # x0=-1, x1=-1, x2=X -> x2 is non-zero (either -1, 0, +1), sign is uncertain
        [3, 1, 1],  # x0=X, x1=0, x2=0 -> MS non-zero is x0 (X), sign is X
        [1, 1, 2],  # x0=0, x1=0, x2=+1 -> MS non-zero is x2 (+1), sign is +1 regardless of X if any
    ], dtype=np.uint8)

    rust_out = nl.simulate(inputs)
    py_out = ref.eval_batch(inputs)

    np.testing.assert_array_equal(rust_out, py_out)
