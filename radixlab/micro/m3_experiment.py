"""M3 Full Multi-SM GPU experiment runner with effect decomposition (docs/hypotheses.md section 0.2)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from ..gpu.device import Device
from ..paths import results_dir
from workloads import (
    BITNET_TERNARY_ASM,
    CIRCLE_SDF_ASM,
    GEMM_ASM,
    RASTER_TRIANGLE_ASM,
    VEC_ADD_ASM,
    generate_bitnet_data,
    generate_circle_data,
    generate_gemm_data,
    generate_triangle_data,
    generate_vec_add_data,
)


def run_m3_experiment(seed: int = 42) -> Dict[str, Any]:
    designs = ["GPU-B", "GPU-T", "GPU-BT", "GPU-Q-1b", "GPU-Q-2b"]
    widths = {
        "GPU-B": 16,
        "GPU-T": 11,
        "GPU-BT": 11,
        "GPU-Q-1b": 8,
        "GPU-Q-2b": 8,
    }

    workloads = [
        ("vec_add", VEC_ADD_ASM, generate_vec_add_data),
        ("gemm", GEMM_ASM, generate_gemm_data),
        ("bitnet_mlp", BITNET_TERNARY_ASM, generate_bitnet_data),
        ("raster_triangle", RASTER_TRIANGLE_ASM, generate_triangle_data),
        ("circle_sdf", CIRCLE_SDF_ASM, generate_circle_data),
    ]

    results = {
        "experiment": "m3_full_gpu_benchmarking",
        "date": "2026-11-09",
        "seed": seed,
        "n_sm": 4,
        "lanes_per_sm": 8,
        "total_lanes": 32,
        "runs": [],
        "effect_decomposition": {},
    }

    for wl_name, asm_code, gen_fn in workloads:
        if wl_name == "gemm":
            data, _ = generate_gemm_data(size=4, seed=seed)
        elif wl_name == "bitnet_mlp":
            data, _, _ = generate_bitnet_data(n_lanes=32, seed=seed)
        elif wl_name == "raster_triangle":
            data, _ = generate_triangle_data(n_pixels=32, seed=seed)
        elif wl_name == "circle_sdf":
            data, _ = generate_circle_data(n_pixels=32, seed=seed)
        else:
            data, _ = generate_vec_add_data(n_lanes=32, seed=seed)

        wl_results = {}
        for d in designs:
            dev = Device(design=d, n_sm=4, n_lanes_per_sm=8, word_width=widths[d])
            metrics = dev.launch_grid(asm_code, grid_data=data)
            wl_results[d] = metrics

        # Compute effect decomposition per docs/hypotheses.md section 0.2:
        # Total effect = M(GPU-T) / M(GPU-B)
        # Number-system / encoding effect = M(GPU-BT) / M(GPU-B)
        # Hardware effect = M(GPU-T) / M(GPU-BT)
        # Multi-level memory effect = M(GPU-Q-2b) / M(GPU-Q-1b)
        t_b = wl_results["GPU-B"]["total_energy_fj"]
        t_t = wl_results["GPU-T"]["total_energy_fj"]
        t_bt = wl_results["GPU-BT"]["total_energy_fj"]
        q_1b = wl_results["GPU-Q-1b"]["total_energy_fj"]
        q_2b = wl_results["GPU-Q-2b"]["total_energy_fj"]

        decomp = {
            "energy_ratio_total_T_vs_B": round(t_t / t_b, 4),
            "energy_ratio_encoding_BT_vs_B": round(t_bt / t_b, 4),
            "energy_ratio_hardware_T_vs_BT": round(t_t / t_bt, 4),
            "mlc_memory_gain_Q2b_vs_Q1b": round(q_2b / q_1b, 4),
        }

        results["runs"].append({
            "workload": wl_name,
            "metrics_by_design": wl_results,
            "decomposition": decomp,
        })

    return results


def save_m3_results(results: Dict[str, Any], path: Optional[Path] = None) -> Path:
    p = path or (results_dir() / "m3_full_gpu_results.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return p
