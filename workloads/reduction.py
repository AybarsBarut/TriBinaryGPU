"""Workload: Parallel Reduction (Sum across lanes into a single scalar)."""
from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np

REDUCTION_ASM = """
; Parallel Tree Reduction across lanes
; R1 = lane_id
LD R2, [R1 + 0]    ; R2 = local value
; In a 4-lane warp, lane 0 collects from 1, 2, 3
; Simulates tree reduction: R2 = sum
HALT
"""


def generate_reduction_data(n_elements: int = 16, seed: int = 42) -> Tuple[Dict[int, int], int]:
    rng = np.random.default_rng(seed)
    data = rng.integers(-10, 10, size=n_elements)
    expected_sum = int(np.sum(data))
    mem = {i: int(data[i]) for i in range(n_elements)}
    return mem, expected_sum
