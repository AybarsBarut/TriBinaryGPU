"""Verification tests for the gate-level GPU Lane ALU (Binary and Balanced Ternary)."""
from __future__ import annotations

import pytest

from tribinary import cells
from tribinary.gen.alu import build_alu
from tribinary.verify import VerificationGate


@pytest.fixture(scope="module")
def libs():
    return cells.load_all()


@pytest.fixture(scope="module")
def gate():
    return VerificationGate()


@pytest.mark.parametrize("system,n", [
    ("b", 8),
    ("t", 6),
])
def test_alu_verification(libs, gate, system, n):
    alu_blk = build_alu(libs, system, n)
    record = gate.verify_block(alu_blk, max_random_vectors=1024)

    assert record.passed, f"ALU {alu_blk.name} failed verification: {record.error_sample}"
    assert record.mismatches == 0
