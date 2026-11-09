"""Workload: Dense Matrix Multiplication (GEMM, C = A * B).

Matrix dimensions: 4x4 matrices (16 elements each).
Each lane computes one row/column dot product.
"""
from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np

# GEMM Kernel: Lane i computes C[row, col] = sum(A[row, k] * B[k, col])
GEMM_ASM = """
; 4x4 GEMM Dot Product Kernel
; Lane i computes element C[i]:
; Row = i / 4, Col = i % 4
; Dot product of 4 elements: sum_{k=0..3} A[row*4 + k] * B[k*4 + col]

LI R6, 0          ; Accumulator R6 = 0

; k = 0
LD R2, [R1 + 0]   ; A element
LD R3, [R1 + 16]  ; B element
MUL R4, R2, R3
ADD R6, R6, R4

; k = 1
LD R2, [R1 + 4]
LD R3, [R1 + 20]
MUL R4, R2, R3
ADD R6, R6, R4

; Store result
ST [R1 + 32], R6
HALT
"""


def generate_gemm_data(size: int = 4, seed: int = 42) -> Tuple[Dict[int, int], np.ndarray]:
    rng = np.random.default_rng(seed)
    A = rng.integers(-5, 5, size=(size, size))
    B = rng.integers(-5, 5, size=(size, size))
    C = A @ B

    mem = {}
    for i in range(size * size):
        r, c = i // size, i % size
        mem[i] = int(A[r, c])
        mem[16 + i] = int(B[r, c])

    return mem, C
