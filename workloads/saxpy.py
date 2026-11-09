"""Workload 2: SAXPY (a * X + Y -> Y).

Each SIMT lane computes y[i] = a * x[i] + y[i].
"""
from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np

SAXPY_ASM = """
; SAXPY Kernel
; R1 = lane_id
; R5 = scalar constant a
LI R5, 2           ; a = 2
LD R2, [R1 + 0]    ; R2 = X[lane_id]
LD R3, [R1 + 16]   ; R3 = Y[lane_id]
MUL R4, R5, R2     ; R4 = a * X[i]
ADD R4, R4, R3     ; R4 = a * X[i] + Y[i]
ST [R1 + 32], R4   ; Output[lane_id] = R4
HALT
"""


def generate_saxpy_data(n_lanes: int, a_scalar: int = 2, seed: int = 42) -> Tuple[Dict[int, int], np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.integers(-20, 20, size=n_lanes)
    y = rng.integers(-20, 20, size=n_lanes)
    expected = a_scalar * x + y

    mem = {}
    for i in range(n_lanes):
        mem[i] = int(x[i])
        mem[16 + i] = int(y[i])

    return mem, expected
