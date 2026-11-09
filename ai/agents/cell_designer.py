"""Cell and Netlist Designer Agent: drafts cells or kernels, gated by strict verification."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..nim_client import NIMClient
from radixlab.verify import VerificationGate


class CellDesignerAgent:
    """Uses NIM (e.g. DeepSeek v4.1 Flash) to draft cells or optimized netlists."""

    def __init__(self, client: Optional[NIMClient] = None, gate: Optional[VerificationGate] = None):
        self.client = client or NIMClient()
        self.gate = gate or VerificationGate()
        self.quarantine_dir = Path(__file__).resolve().parent.parent.parent / ".quarantine"
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    def draft_cell_spec(self, prompt: str) -> Dict[str, Any]:
        """Ask LLM to draft a cell specification. Output is quarantined until verified."""
        sys_msg = (
            "You are an expert digital logic architect. Generate a JSON cell specification with fields:\n"
            "name, description, radix, inputs, outputs, truth_table: list of {in: [...], out: [...]}\n"
            "Return ONLY valid JSON."
        )
        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "user", "content": prompt},
        ]
        resp = self.client.chat_completion(messages, model=self.client.config.fast_model, temperature=0.1)
        # Strip potential markdown code blocks
        clean = resp.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1]
            if clean.endswith("```"):
                clean = clean.rsplit("\n", 1)[0]
        data = json.loads(clean.strip())

        # Save to quarantine
        q_file = self.quarantine_dir / f"{data.get('name', 'draft')}_quarantine.json"
        q_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return data
