"""Workload: Branch Divergence Synthetic Kernel.

Lanes execute divergent execution paths depending on condition.
Tests SIMT warp divergence penalties across radices.
"""
from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np

DIVERGENCE_ASM = """
; Warp Divergence Synthetic Kernel
; R1 = lane_id
LD R2, [R1 + 0]   ; value
LI R3, 0          ; threshold = 0
BLT R2, R3, NEGATIVE_PATH

; Positive path
LI R4, 10
ADD R5, R2, R4
BRA END

NEGATIVE_PATH:
LI R4, 5
SUB R5, R2, R4

END:
ST [R1 + 32], R5
HALT
"""


def generate_divergence_data(n_lanes: int = 8, seed: int = 42) -> Tuple[Dict[int, int], np.ndarray]:
    rng = np.random.default_rng(seed)
    # Balanced mix of positive and negative values to force 50% warp divergence
    vals = rng.integers(-20, 20, size=n_lanes)
    # Ensure at least one positive and one negative
    vals[0] = 5
    vals[1] = -5

    expected = np.zeros(n_lanes, dtype=np.int64)
    for i in range(n_lanes):
        if vals[i] < 0:
            expected[i] = vals[i] - 5
        else:
            expected[i] = vals[i] + 10

    mem = {i: int(vals[i]) for i in range(n_lanes)}
    return mem, expected
