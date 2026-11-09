"""L1 verification of adder blocks: exhaustive for small widths, random+corners for larger widths."""
from __future__ import annotations

import pytest

from radixlab import cells
from radixlab.gen.adders import adder_archs, build_adder
from radixlab.verify import VerificationGate


@pytest.fixture(scope="module")
def libs():
    return cells.load_all()


@pytest.fixture(scope="module")
def gate():
    return VerificationGate()


@pytest.mark.parametrize("system,n,expected_method", [
    ("b", 4, "exhaustive"),      # 2^9 = 512 states <= 262,144
    ("t", 3, "exhaustive"),      # 3^7 = 2,187 states <= 262,144
    ("q", 3, "exhaustive"),      # 4^7 = 16,384 states <= 262,144
    ("b", 8, "random+corners"),  # 2^17 states: depending on limit, tested with random+corners
    ("t", 6, "random+corners"),  # 3^13 states
    ("q", 6, "random+corners"),  # 4^13 states
])
def test_adder_ripple_verification(libs, gate, system, n, expected_method):
    block = build_adder(libs, system, n, arch="ripple")
    record = gate.verify_block(block, max_random_vectors=2048, check_differential=True)

    assert record.passed, f"Adder {block.name} failed verification: {record.error_sample}"
    assert record.method == expected_method
    assert record.mismatches == 0


@pytest.mark.parametrize("system,n,k", [
    ("b", 8, 4),
    ("t", 6, 3),
    ("q", 6, 2),
])
def test_adder_carry_select_verification(libs, gate, system, n, k):
    arch = f"csel:{k}"
    block = build_adder(libs, system, n, arch=arch)
    record = gate.verify_block(block, max_random_vectors=2048)

    assert record.passed, f"Carry-select adder {block.name} failed: {record.error_sample}"
    assert record.mismatches == 0
