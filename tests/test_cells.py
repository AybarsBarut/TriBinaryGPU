"""L0 verification: cell truth table checks and algebraic invariants (docs/methodology.md section 6)."""
from __future__ import annotations

import pytest

from tribinary import cells, golden


def test_load_all_libraries():
    libs = cells.load_all()
    assert set(libs.keys()) == {"binary", "ternary", "quaternary"}
    for name, lib in libs.items():
        assert lib.status == "reviewed"
        assert len(lib.cells) > 0


def test_cells_truth_tables_match_golden():
    libs = cells.load_all()
    all_problems = []
    for name, lib in libs.items():
        probs = cells.check_against_golden(lib)
        all_problems.extend(probs)
    assert not all_problems, f"Truth table mismatches detected: {all_problems}"


def test_ternary_algebraic_identities():
    """Verify algebraic properties of balanced ternary gates."""
    # STI involution: -(-x) = x
    for x in (-1, 0, 1):
        assert golden._sti(golden._sti(x)[0])[0] == x

    # TMIN / TMAX commutativity and De Morgan: -min(a, b) = max(-a, -b)
    for a in (-1, 0, 1):
        for b in (-1, 0, 1):
            assert golden._tmin(a, b)[0] == golden._tmin(b, a)[0]
            assert golden._tmax(a, b)[0] == golden._tmax(b, a)[0]
            neg_min = golden._sti(golden._tmin(a, b)[0])[0]
            max_negs = golden._tmax(golden._sti(a)[0], golden._sti(b)[0])[0]
            assert neg_min == max_negs

            # TMUL sign rule: a * b
            assert golden._tmul(a, b)[0] == a * b

            # Consensus: a if a == b else 0
            expected_cons = a if a == b else 0
            assert golden._tcons(a, b)[0] == expected_cons


def test_memory_macros_schema():
    macros = cells.load_macros()
    assert "sram_b" in macros
    assert "sram_bt" in macros
    assert "mlc_t" in macros
    assert "sram_q_1b" in macros
    assert "mlc_q_2b" in macros
    for name, m in macros.items():
        assert m["name"] == name
        assert isinstance(m["bits_per_cell"], (int, float))
        assert m["area_per_cell"].confidence in ("low", "medium", "high")
