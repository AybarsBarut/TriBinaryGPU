"""Tests for NVIDIA NIM AI integration, caching, and templated report drafting."""
from __future__ import annotations

import pytest

from ai.config import NIMConfig
from ai.nim_client import NIMClient
from ai.agents.report_drafter import ReportDrafterAgent
from ai.agents.cell_designer import CellDesignerAgent


def test_nim_config_defaults():
    cfg = NIMConfig.load()
    assert "nvidia.com" in cfg.base_url
    assert "nemotron" in cfg.default_model.lower()


def test_report_drafter_placeholder_validation():
    # Valid template with all placeholders present in data
    valid_template = (
        "The primary metric saving is {{saving_pct}}%. "
        "Binary critical path delay was {{binary_delay_ps}} ps whereas ternary achieved {{ternary_delay_ps}} ps."
    )
    data = {
        "saving_pct": "-14.2",
        "binary_delay_ps": "25.0",
        "ternary_delay_ps": "28.55",
    }
    rendered, errors = ReportDrafterAgent.render_and_validate(valid_template, data)
    assert not errors
    assert "The primary metric saving is -14.2%." in rendered
    assert "28.55 ps." in rendered

    # Template with missing placeholder
    bad_template = "Value is {{missing_key}}."
    _, errs = ReportDrafterAgent.render_and_validate(bad_template, data)
    assert len(errs) > 0
    assert "missing_key" in errs[0]


def test_nim_client_cache_and_offline(tmp_path):
    cfg = NIMConfig(cache_dir=tmp_path, enabled=False)
    client = NIMClient(cfg)
    assert not client.is_available

    with pytest.raises(RuntimeError, match="NVIDIA NIM is not configured"):
        client.chat_completion([{"role": "user", "content": "hi"}])
