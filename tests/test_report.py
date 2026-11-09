"""Verification tests for automated report generation."""
from __future__ import annotations

import pytest

from radixlab.report import generate_markdown_report


def test_generate_report(tmp_path):
    out = tmp_path / "report.md"
    generated = generate_markdown_report(out_path=out)
    assert generated.exists()
    content = generated.read_text(encoding="utf-8")
    assert "# RadixLab — Automated Scientific Simulation Report" in content
    assert "Effect Decomposition" in content
    assert "Pareto Analysis" in content
