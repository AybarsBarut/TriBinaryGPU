"""Report Drafter Agent: Drafts reports with templated placeholders; never hallucinated numbers."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from ..nim_client import NIMClient


class ReportDrafterAgent:
    """Uses NIM to draft human-readable report narrative adhering to the no-typed-numbers rule."""

    def __init__(self, client: Optional[NIMClient] = None):
        self.client = client or NIMClient()

    def draft_micro_report(self, experiment_id: str, available_keys: List[str], summary_stats: Dict[str, Any]) -> str:
        prompt = f"""You are a scientific technical writer preparing a simulation report for '{experiment_id}'.
RULES YOU MUST OBEY UNDER PENALTY OF IMMEDIATE REJECTION:
1. NEVER output a raw numeric result or measurement directly in your text.
2. Every number MUST be referenced via a template placeholder in double curly braces: `{{{{placeholder}}}}`.
3. You may ONLY use placeholders from this exact allowed list:
{available_keys}

Context / Data Summary (for conceptual understanding only):
{summary_stats}

Write a concise scientific summary comparing the designs.
Use placeholders like `{{{{primary_metric_saving}}}}`, `{{{{binary_delay_ps}}}}`, `{{{{ternary_delay_ps}}}}` etc.
"""
        messages = [
            {"role": "system", "content": "You are a scientific writer who strictly writes templated text with {{placeholder}} tags."},
            {"role": "user", "content": prompt},
        ]
        return self.client.chat_completion(messages, temperature=0.1)

    @staticmethod
    def render_and_validate(template_text: str, data: Dict[str, Any]) -> Tuple[str, List[str]]:
        """Validate template against data and render exact values."""
        errors = []
        # Find all {{key}}
        placeholders = re.findall(r"\{\{([a-zA-Z0-9_\.]+)\}\}", template_text)
        rendered = template_text

        for p in set(placeholders):
            if p not in data:
                errors.append(f"Missing placeholder in data: '{p}'")
            else:
                val = data[p]
                rendered = rendered.replace(f"{{{{{p}}}}}", str(val))

        # Check for un-substituted {{...}}
        leftovers = re.findall(r"\{\{[^}]+\}\}", rendered)
        if leftovers:
            errors.append(f"Unresolved placeholders: {leftovers}")

        return rendered, errors
