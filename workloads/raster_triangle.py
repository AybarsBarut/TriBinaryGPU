"""Workload: Triangle Rasterization via Edge Functions (Hypothesis H3).

Edge function: E(x, y) = (x - x0)*(y1 - y0) - (y - y0)*(x1 - x0).
Sign test: point (x, y) is inside the triangle iff E01 >= 0 and E12 >= 0 and E20 >= 0.
"""
from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np

# Rasterizer Edge Function kernel: evaluates sign of edge function for pixel (x, y)
RASTER_TRIANGLE_ASM = """
; Triangle Edge Function Test Kernel
; R1 = pixel_id (mapped to x, y)
; Compute E = (x - x0)*dy - (y - y0)*dx

LD R2, [R1 + 0]   ; R2 = (x - x0)
LI R3, 3          ; R3 = dy
MUL R4, R2, R3    ; R4 = (x - x0) * dy

LD R2, [R1 + 16]  ; R2 = (y - y0)
LI R3, 2          ; R3 = dx
MUL R5, R2, R3    ; R5 = (y - y0) * dx

SUB R6, R4, R5    ; R6 = E(x, y)
ST [R1 + 32], R6  ; Store edge value
HALT
"""


def generate_triangle_data(n_pixels: int = 8, seed: int = 42) -> Tuple[Dict[int, int], np.ndarray]:
    rng = np.random.default_rng(seed)
    dx_val = 2
    dy_val = 3

    x_rel = rng.integers(-10, 10, size=n_pixels)
    y_rel = rng.integers(-10, 10, size=n_pixels)
    expected_e = (x_rel * dy_val) - (y_rel * dx_val)

    mem = {}
    for i in range(n_pixels):
        mem[i] = int(x_rel[i])
        mem[16 + i] = int(y_rel[i])

    return mem, expected_e
