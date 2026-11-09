"""Workload: Circle Drawing via Signed Distance Function (SDF) / Midpoint (Hypothesis H3).

SDF(x, y) = (x - cx)^2 + (y - cy)^2 - r^2.
Point is inside circle if SDF <= 0.
"""
from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np

CIRCLE_SDF_ASM = """
; Circle SDF Kernel
; R1 = pixel_id
; R7 = r^2
LI R7, 25         ; r = 5, r^2 = 25

LD R2, [R1 + 0]   ; dx = (x - cx)
MUL R4, R2, R2    ; dx^2

LD R3, [R1 + 16]  ; dy = (y - cy)
MUL R5, R3, R3    ; dy^2

ADD R6, R4, R5    ; dist_sq = dx^2 + dy^2
SUB R6, R6, R7    ; SDF = dist_sq - r^2
ST [R1 + 32], R6  ; Store SDF value
HALT
"""


def generate_circle_data(n_pixels: int = 8, r: int = 5, seed: int = 42) -> Tuple[Dict[int, int], np.ndarray]:
    rng = np.random.default_rng(seed)
    dx = rng.integers(-8, 8, size=n_pixels)
    dy = rng.integers(-8, 8, size=n_pixels)
    expected_sdf = (dx ** 2) + (dy ** 2) - (r ** 2)

    mem = {}
    for i in range(n_pixels):
        mem[i] = int(dx[i])
        mem[16 + i] = int(dy[i])

    return mem, expected_sdf
