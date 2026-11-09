"""L1 verification of multiplier blocks across all radices."""
from __future__ import annotations

import pytest

from radixlab import cells
from radixlab.gen.multipliers import build_multiplier
from radixlab.verify import VerificationGate


@pytest.fixture(scope="module")
def libs():
    return cells.load_all()


@pytest.fixture(scope="module")
def gate():
    return VerificationGate()


@pytest.mark.parametrize("system,n,signed,arch,expected_method", [
    ("b", 4, False, "wallace", "exhaustive"),  # 2^8 = 256 states
    ("b", 4, True, "wallace", "exhaustive"),   # 2^8 = 256 states (Baugh-Wooley signed)
    ("b", 4, False, "array", "exhaustive"),
    ("t", 3, False, "wallace", "exhaustive"),  # 3^6 = 729 states (balanced ternary)
    ("t", 3, False, "array", "exhaustive"),
    ("q", 2, False, "wallace", "exhaustive"),  # 4^4 = 256 states
    ("q", 2, False, "array", "exhaustive"),
    ("b", 8, True, "wallace", "random+corners"),
    ("t", 5, False, "wallace", "random+corners"),
])
def test_multiplier_verification(libs, gate, system, n, signed, arch, expected_method):
    block = build_multiplier(libs, system, n, arch=arch, final="ripple", signed=signed)
    record = gate.verify_block(block, max_random_vectors=2048, check_differential=True)

    assert record.passed, f"Multiplier {block.name} failed verification: {record.error_sample}"
    assert record.method == expected_method
    assert record.mismatches == 0
