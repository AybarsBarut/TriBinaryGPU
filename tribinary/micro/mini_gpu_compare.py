"""M2 Mini-GPU comparison experiment runner: evaluates GPU-B vs GPU-T on standard kernels."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from ..gpu.kernel import GPUKernelRunner
from ..paths import results_dir
from workloads.saxpy import SAXPY_ASM, generate_saxpy_data
from workloads.vec_add import VEC_ADD_ASM, generate_vec_add_data


def run_mini_gpu_experiment(
    configs: List[Tuple[int, int, int]] = None,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compare GPU-B and GPU-T at iso-precision configurations.

    configs: list of (n_lanes, bits, trits). Default: [(4, 8, 6), (8, 16, 11)].
    """
    if configs is None:
        configs = [(4, 8, 6), (8, 16, 11)]

    results = {
        "experiment": "m2_mini_gpu_comparison",
        "date": "2026-11-09",
        "seed": seed,
        "runs": [],
    }

    workloads = [
        ("vec_add", VEC_ADD_ASM, generate_vec_add_data),
        ("saxpy", SAXPY_ASM, generate_saxpy_data),
    ]

    for n_lanes, bits, trits in configs:
        for wl_name, asm_code, gen_fn in workloads:
            # 1. Run GPU-B
            runner_b = GPUKernelRunner("b", n_lanes=n_lanes, word_width=bits)
            init_mem_b, exp_b = gen_fn(n_lanes=n_lanes, seed=seed)
            sm_b, metrics_b = runner_b.run_kernel(asm_code, initial_mem=init_mem_b)
            # Verify correctness
            out_b = np.array([sm_b.shared_mem[32 + i] for i in range(n_lanes)], dtype=np.int64)
            assert np.array_equal(out_b, exp_b), f"GPU-B failed golden check on {wl_name}"

            # 2. Run GPU-T
            runner_t = GPUKernelRunner("t", n_lanes=n_lanes, word_width=trits)
            init_mem_t, exp_t = gen_fn(n_lanes=n_lanes, seed=seed)
            sm_t, metrics_t = runner_t.run_kernel(asm_code, initial_mem=init_mem_t)
            out_t = np.array([sm_t.shared_mem[32 + i] for i in range(n_lanes)], dtype=np.int64)
            assert np.array_equal(out_t, exp_t), f"GPU-T failed golden check on {wl_name}"

            # Compute relative savings r = 1 - T / B
            # Primary metric: execution time in ns (cycles * clock_cycle_ps)
            t_b = metrics_b["execution_time_ns"]
            t_t = metrics_t["execution_time_ns"]
            r_time = 1.0 - (t_t / t_b)

            e_b = metrics_b["total_energy_fj"]
            e_t = metrics_t["total_energy_fj"]
            r_energy = 1.0 - (e_t / e_b)

            a_b = metrics_b["alu_gate_area_um2"] + metrics_b["rf_area_um2"]
            a_t = metrics_t["alu_gate_area_um2"] + metrics_t["rf_area_um2"]
            r_area = 1.0 - (a_t / a_b)

            results["runs"].append({
                "workload": wl_name,
                "n_lanes": n_lanes,
                "iso_pair": f"{bits}b_vs_{trits}t",
                "gpu_b": metrics_b,
                "gpu_t": metrics_t,
                "relative_savings": {
                    "execution_time_primary": r_time,
                    "energy": r_energy,
                    "area": r_area,
                },
                "verdict": "SUPPORTED" if r_time >= 0.10 else "REFUTED",
            })

    return results


def save_mini_gpu_results(results: Dict[str, Any], path: Optional[Path] = None) -> Path:
    p = path or (results_dir() / "m2_mini_gpu_results.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return p
