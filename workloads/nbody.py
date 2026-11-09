"""Workload: N-Body Gravitational / Coulomb Particle Step (Fixed-Point)."""
from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np

NBODY_ASM = """
; 2-Body Interaction Step Kernel
; Lane i computes force from particle j=1 on particle i: F_x = dx * G
LD R2, [R1 + 0]   ; x_i
LI R3, 10         ; x_target = 10
SUB R4, R3, R2    ; dx = x_target - x_i
LI R5, 3          ; G = 3
MUL R6, R4, R5    ; F_x = dx * G
ST [R1 + 32], R6  ; store force
HALT
"""


def generate_nbody_data(n_particles: int = 8, seed: int = 42) -> Tuple[Dict[int, int], np.ndarray]:
    rng = np.random.default_rng(seed)
    x = rng.integers(-20, 20, size=n_particles)
    x_target = 10
    G = 3
    expected_f = (x_target - x) * G

    mem = {i: int(x[i]) for i in range(n_particles)}
    return mem, expected_f
