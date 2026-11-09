"""Run RedTeamAgent on M2 Mini-GPU experimental results."""
from __future__ import annotations

import json
from pathlib import Path

from ai.agents.red_team import RedTeamAgent
from ai.nim_client import NIMClient
from tribinary.paths import results_dir

res_file = results_dir() / "m2_mini_gpu_results.json"
if not res_file.exists():
    print("Results file not found.")
    exit(1)

client = NIMClient()
if not client.is_available:
    print("NVIDIA NIM is not available.")
    exit(0)

agent = RedTeamAgent(client)
try:
    critique = agent.review_experiment_results("M2 Single-SM Mini-GPU Comparison", res_file.read_text(encoding="utf-8"))
    print("=== NVIDIA Red Team Critique (M2 Mini-GPU) ===")
    print(critique)

    if critique:
        critique_path = Path("docs/status/m2_red_team_critique.md")
        critique_path.write_text(critique, encoding="utf-8")
        print(f"Critique written to {critique_path}")
except Exception as e:
    print(f"NVIDIA NIM review skipped/failed: {e}")
