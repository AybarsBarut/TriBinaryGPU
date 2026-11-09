"""L1 verification of sign detection and comparator blocks (M1 micro-experiment scope)."""
from __future__ import annotations

import pytest

from radixlab import cells
from radixlab.gen.comparators import build_cmp, build_sign_detect
from radixlab.verify import VerificationGate


@pytest.fixture(scope="module")
def libs():
    return cells.load_all()


@pytest.fixture(scope="module")
def gate():
    return VerificationGate()


@pytest.mark.parametrize("system,n,arch,expected_method", [
    ("b", 4, "scan", "exhaustive"),     # 2^4 = 16 states
    ("t", 3, "chain", "exhaustive"),    # 3^3 = 27 states
    ("t", 3, "tree", "exhaustive"),     # 3^3 = 27 states
    ("b", 8, "scan", "exhaustive"),     # 2^8 = 256 states
    ("t", 6, "tree", "exhaustive"),     # 3^6 = 729 states
])
def test_sign_detect_verification(libs, gate, system, n, arch, expected_method):
    block = build_sign_detect(libs, system, n, arch=arch)
    record = gate.verify_block(block, check_differential=True)

    assert record.passed, f"Sign detector {block.name} failed: {record.error_sample}"
    assert record.method == expected_method
    assert record.mismatches == 0


@pytest.mark.parametrize("system,n,arch,expected_method", [
    ("b", 4, "tree", "exhaustive"),        # 2^8 = 256 states
    ("b", 4, "sub:ripple", "exhaustive"),  # 2^8 = 256 states
    ("t", 3, "tree", "exhaustive"),        # 3^6 = 729 states
    ("t", 3, "sub:ripple", "exhaustive"),  # 3^6 = 729 states
    ("b", 8, "tree", "random+corners"),    # 2^16 = 65,536 states
    ("t", 5, "tree", "random+corners"),    # 3^10 = 59,049 states
])
def test_comparator_verification(libs, gate, system, n, arch, expected_method):
    block = build_cmp(libs, system, n, arch=arch)
    record = gate.verify_block(block, max_random_vectors=2048)

    assert record.passed, f"Comparator {block.name} failed: {record.error_sample}"
    assert record.mismatches == 0
