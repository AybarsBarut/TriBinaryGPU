"""M2 Verification: Single-SM Mini-GPU execution (GPU-B and GPU-T)."""
from __future__ import annotations

import numpy as np
import pytest

from radixlab.gpu.kernel import GPUKernelRunner
from workloads.saxpy import SAXPY_ASM, generate_saxpy_data
from workloads.vec_add import VEC_ADD_ASM, generate_vec_add_data


@pytest.mark.parametrize("system,n_lanes,word_width", [
    ("b", 4, 8),    # GPU-B: 4 lanes, 8-bit words
    ("t", 4, 6),    # GPU-T: 4 lanes, 6-trit words (9.51 eff bits)
    ("b", 8, 16),   # GPU-B: 8 lanes, 16-bit words
    ("t", 8, 11),   # GPU-T: 8 lanes, 11-trit words (17.43 eff bits)
])
def test_gpu_vector_addition_bit_exact(system, n_lanes, word_width):
    runner = GPUKernelRunner(system, n_lanes=n_lanes, word_width=word_width)
    init_mem, expected_c = generate_vec_add_data(n_lanes=n_lanes, seed=123)

    sm, metrics = runner.run_kernel(VEC_ADD_ASM, initial_mem=init_mem)

    assert sm.halted, "SM did not reach HALT"
    assert sm.cycles == 5, f"Expected 5 cycles, took {sm.cycles}"

    # Verify output in shared memory
    actual_c = np.array([sm.shared_mem[32 + i] for i in range(n_lanes)], dtype=np.int64)
    np.testing.assert_array_equal(actual_c, expected_c)
    assert metrics["total_energy_fj"] > 0.0


@pytest.mark.parametrize("system,n_lanes,word_width", [
    ("b", 4, 8),
    ("t", 4, 6),
])
def test_gpu_saxpy_bit_exact(system, n_lanes, word_width):
    runner = GPUKernelRunner(system, n_lanes=n_lanes, word_width=word_width)
    init_mem, expected = generate_saxpy_data(n_lanes=n_lanes, a_scalar=2, seed=456)

    sm, metrics = runner.run_kernel(SAXPY_ASM, initial_mem=init_mem)

    assert sm.halted
    assert sm.cycles == 7  # LI, LD, LD, MUL, ADD, ST, HALT

    actual = np.array([sm.shared_mem[32 + i] for i in range(n_lanes)], dtype=np.int64)
    np.testing.assert_array_equal(actual, expected)


def test_gpu_branch_loop():
    """Test branching and loop control in unified ISA on both GPU-B and GPU-T."""
    asm_loop = """
    ; Compute sum of 1..3 = 6
    LI R2, 0   ; sum = 0
    LI R3, 1   ; counter = 1
    LI R5, 4   ; limit = 4
    LOOP:
    ADD R2, R2, R3
    LI R4, 1
    ADD R3, R3, R4
    BLT R3, R5, LOOP
    ST [R1 + 0], R2
    HALT
    """
    for sys_ in ("b", "t"):
        width = 8 if sys_ == "b" else 6
        runner = GPUKernelRunner(sys_, n_lanes=2, word_width=width)
        sm, metrics = runner.run_kernel(asm_loop)
        assert sm.halted
        # Verify sum == 6 stored at address 0
        assert sm.shared_mem[0] == 6
