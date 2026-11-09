"""Workload: BitNet b1.58 Ternary-Weight MLP Layer Inference (Hypothesis H5).

Weights W in {-1, 0, +1}. Activations X in integer range.
Compares:
  V1: Binary INT8 MAC with multiplier.
  V2: Binary multiplier-free conditional add/sub (honest baseline).
  V3: GPU-BT (binary-encoded ternary).
  V4: GPU-T (native balanced ternary).
"""
from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np

# Native Ternary BitNet Kernel (multipliers are eliminated; weights in {-1, 0, +1} act as conditional add/sub/skip)
BITNET_TERNARY_ASM = """
; BitNet b1.58 Layer: y[i] = sum_j (w_ij * x_j)
; Weights are {-1, 0, +1}
LI R6, 0          ; Accumulator y = 0

; j = 0
LD R2, [R1 + 0]   ; activation x[0]
LD R3, [R1 + 16]  ; weight w[0] in {-1, 0, +1}
MUL R4, R2, R3    ; in ternary, TMUL is a 1-gate sign product!
ADD R6, R6, R4

; j = 1
LD R2, [R1 + 1]   ; activation x[1]
LD R3, [R1 + 17]  ; weight w[1] in {-1, 0, +1}
MUL R4, R2, R3
ADD R6, R6, R4

ST [R1 + 32], R6  ; Output activation
HALT
"""


def generate_bitnet_data(
    n_lanes: int = 8,
    zero_fraction: float = 0.33,
    seed: int = 42,
) -> Tuple[Dict[int, int], np.ndarray, Dict[str, Any]]:
    rng = np.random.default_rng(seed)

    # Activations in range [-20, 20]
    acts = rng.integers(-20, 20, size=n_lanes + 4)

    # Ternary weights {-1, 0, +1} with controlled zero fraction
    raw = rng.uniform(0, 1, size=(n_lanes + 4))
    weights = np.zeros(n_lanes + 4, dtype=np.int64)
    for i in range(len(raw)):
        if raw[i] < zero_fraction:
            weights[i] = 0
        elif raw[i] < (zero_fraction + (1 - zero_fraction) / 2):
            weights[i] = -1
        else:
            weights[i] = 1

    expected_y = np.zeros(n_lanes, dtype=np.int64)
    for i in range(n_lanes):
        expected_y[i] = acts[i] * weights[i] + acts[i + 1] * weights[i + 1]

    mem = {}
    for i in range(len(acts)):
        mem[i] = int(acts[i])
        mem[16 + i] = int(weights[i])

    meta = {
        "zero_fraction": zero_fraction,
        "n_activations": len(acts),
        "actual_zero_ratio": float(np.mean(weights == 0)),
    }

    return mem, expected_y, meta
