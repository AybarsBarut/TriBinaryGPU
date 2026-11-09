"""Workload: Fixed-Point Mandelbrot Fractal Iteration."""
from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np

# Mandelbrot 1-step iteration: x_next = (x^2 - y^2)//scale + cx, y_next = (2*x*y)//scale + cy
MANDELBROT_ASM = """
; Fixed-Point Mandelbrot Step Kernel
; Inputs: cx at [R1 + 0], cy at [R1 + 16]
; R2 = x, R3 = y
LD R2, [R1 + 0]   ; cx
LD R3, [R1 + 16]  ; cy

MUL R4, R2, R2    ; x^2
MUL R5, R3, R3    ; y^2
SUB R6, R4, R5    ; x^2 - y^2
SHR R6, R6        ; scaled
ADD R6, R6, R2    ; x_next

ST [R1 + 32], R6  ; store x_next
HALT
"""


def generate_mandelbrot_data(n_points: int = 8, seed: int = 42) -> Tuple[Dict[int, int], np.ndarray]:
    rng = np.random.default_rng(seed)
    cx = rng.integers(-10, 10, size=n_points)
    cy = rng.integers(-10, 10, size=n_points)

    expected = np.zeros(n_points, dtype=np.int64)
    for i in range(n_points):
        x, y = cx[i], cy[i]
        diff = (x ** 2) - (y ** 2)
        # Shift right by 1
        scaled = diff >> 1
        expected[i] = scaled + x

    mem = {}
    for i in range(n_points):
        mem[i] = int(cx[i])
        mem[16 + i] = int(cy[i])

    return mem, expected
