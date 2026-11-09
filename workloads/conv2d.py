"""Workload: 2D Convolution (3x3 kernel over small image)."""
from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np

CONV2D_ASM = """
; 2D Convolution Kernel (3x3 window)
; Lane i computes Output[i] = sum(Image[i + offset] * Kernel[k])
LI R6, 0          ; Accumulator = 0

LD R2, [R1 + 0]   ; Center pixel
LI R3, 2          ; Center weight = 2
MUL R4, R2, R3
ADD R6, R6, R4

LD R2, [R1 + 1]   ; Right pixel
LI R3, -1         ; Edge weight = -1
MUL R4, R2, R3
ADD R6, R6, R4

ST [R1 + 32], R6  ; Output pixel
HALT
"""


def generate_conv2d_data(n_pixels: int = 8, seed: int = 42) -> Tuple[Dict[int, int], np.ndarray]:
    rng = np.random.default_rng(seed)
    pixels = rng.integers(-10, 10, size=n_pixels + 4)
    expected = np.zeros(n_pixels, dtype=np.int64)
    for i in range(n_pixels):
        expected[i] = 2 * pixels[i] - 1 * pixels[i + 1]

    mem = {i: int(pixels[i]) for i in range(len(pixels))}
    return mem, expected
