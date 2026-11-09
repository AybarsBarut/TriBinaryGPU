"""Workload 1: Vector Addition (A + B -> C).

Each SIMT lane processes element `i = lane_id`.
"""
from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np

VEC_ADD_ASM = """
; Vector Addition Kernel
; Precondition: R1 contains lane_id (0..n_lanes-1)
; Input vector A stored at addresses 0..15
; Input vector B stored at addresses 16..31
; Output vector C written to addresses 32..47

LD R2, [R1 + 0]    ; R2 = A[lane_id]
LD R3, [R1 + 16]   ; R3 = B[lane_id]
ADD R4, R2, R3     ; R4 = A[i] + B[i]
ST [R1 + 32], R4   ; C[lane_id] = R4
HALT
"""


def generate_vec_add_data(n_lanes: int, seed: int = 42) -> Tuple[Dict[int, int], np.ndarray]:
    rng = np.random.default_rng(seed)
    # Range safe for both 8-bit binary and 6-trit ternary
    a = rng.integers(-50, 50, size=n_lanes)
    b = rng.integers(-50, 50, size=n_lanes)
    expected_c = a + b

    mem = {}
    for i in range(n_lanes):
        mem[i] = int(a[i])
        mem[16 + i] = int(b[i])

    return mem, expected_c
