"""Red Team Agent: Audits assumptions, hypotheses, and experimental setups for subtle biases."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..nim_client import NIMClient


class RedTeamAgent:
    """Uses NVIDIA Nemotron Ultra to critically examine simulation assumptions."""

    def __init__(self, client: Optional[NIMClient] = None):
        self.client = client or NIMClient()

    def review_assumptions(self, library_name: str, yaml_content: str) -> str:
        """Analyze a cell library's assumption parameters and point out potential bias or fragility."""
        prompt = f"""You are a senior computer architect and rigorous red-team peer reviewer.
Critically review the following cell library YAML specification for '{library_name}'.
Look specifically for:
1. Unfair advantages given to binary or non-binary logic.
2. Low-confidence placeholder assumptions that could skew energy, area, or critical-path delay.
3. Hidden assumptions regarding wire interconnects, fan-out limits, or noise margins.
4. Specific suggestions for sensitivity testing.

YAML CONTENT:
```yaml
{yaml_content}
```

Format your review into:
- Executive Assessment
- Potential Biases Identified
- Fragile Assumptions (confidence: low)
- Recommended Sensitivity Bounds
"""
        messages = [
            {"role": "system", "content": "You are a merciless, unbiased computer architecture red-team auditor."},
            {"role": "user", "content": prompt},
        ]
        return self.client.chat_completion(messages, temperature=0.1)

    def review_experiment_results(self, experiment_name: str, metrics_json: str) -> str:
        """Critique an experiment's conclusions and check if the hypothesis was honestly tested."""
        prompt = f"""You are a scientific peer reviewer evaluating the '{experiment_name}' experiment results.
Examine the raw data and evaluate whether:
1. The conclusion is justified by the data or over-claims.
2. The comparison was fair (iso-precision, baseline choices, effect decomposition).
3. Any unexpected or negative results were improperly minimized.

RAW METRICS JSON:
```json
{metrics_json}
```

Provide a concise, direct, peer-review critique.
"""
        messages = [
            {"role": "system", "content": "You are an expert scientific auditor enforcing honesty in computing research."},
            {"role": "user", "content": prompt},
        ]
        return self.client.chat_completion(messages, temperature=0.1)
