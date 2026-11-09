# Preregistration changelog

`docs/hypotheses.md` is frozen by a git tag. Every later change is listed here with the new tag, the
reason, and the confirmation that no affected experiment had been run yet.

## prereg-v1 (2026-11-09)

Initial freeze after M0 approval. Changes made between the M0 draft and the freeze, all before any
experiment was run:

1. GPU-Q split into GPU-Q-1b and GPU-Q-2b, reported separately (decision Q8).
2. Decision rule: δ = 10% applied to the primary metric at nominal parameters; label from the position of the
   confidence interval of the relative saving relative to δ; Holm-adjusted p only as an extra filter;
   sign of the effect must be preserved over ±50% for the unconditional label (decisions Q13, Q14).
3. Outcome classes redefined in terms of that rule.
4. H2 primary metric clarified as static critical-path delay; other H2 metrics exploratory (Q18).
