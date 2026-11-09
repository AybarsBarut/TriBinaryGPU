"""M1 Micro-experiment: Binary vs Balanced-Ternary Sign Detection and Comparator (Finding 2 / H2).

Evaluates whether balanced ternary's sign-detection (finding the most significant non-zero trit)
provides an architectural advantage over two's complement binary sign-detection (O(1) MSB check).
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

from .. import cells, golden
from ..gen.comparators import build_cmp, build_sign_detect, cmp_archs, sign_detect_archs
from ..netlist import Netlist
from ..paths import results_dir


def run_comparator_micro_experiment(
    widths: List[Tuple[int, int]] = None,
    n_vectors: int = 10_000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compare binary and balanced ternary sign detection and comparators at iso-precision widths.

    `widths` is a list of (n_bits, n_trits). Default: [(8, 6), (16, 11), (32, 21)].
    """
    if widths is None:
        widths = [(8, 6), (16, 11), (32, 21)]

    libs = cells.load_all()
    res_b = libs["binary"].resolve()
    res_t = libs["ternary"].resolve()

    rng = np.random.default_rng(seed)
    results = {
        "experiment": "m1_comparator_and_sign_detect",
        "date": "2026-11-09",
        "seed": seed,
        "n_vectors": n_vectors,
        "sign_detect": [],
        "comparator": [],
    }

    # 1. Sign Detection Comparison
    for n_b, n_t in widths:
        # Common integer numeric range for paired fair stimulus
        lo_b, hi_b = golden.word_range("b", n_b, signed=True)
        lo_t, hi_t = golden.word_range("t", n_t)
        common_lo = max(lo_b, lo_t)
        common_hi = min(hi_b, hi_t)

        test_vals = rng.integers(common_lo, common_hi + 1, size=n_vectors)
        # Ensure zero and edge values are represented
        test_vals[0] = 0
        test_vals[1] = 1
        test_vals[2] = -1
        test_vals[3] = common_lo
        test_vals[4] = common_hi

        # Binary sign detect (scan arch: MSB for neg, tree for zero)
        blk_b = build_sign_detect(libs, "b", n_b, arch="scan")
        summ_b = blk_b.netlist.summary(res_b)
        in_codes_b = golden.to_code("b", golden.encode_digits("b", test_vals, n_b, signed=True))
        _, tg_b = blk_b.netlist.simulate_activity(in_codes_b)
        # Switching energy = sum(toggles * energy_per_cell)
        e_per_cell_b = np.array(res_b.energy)
        dyn_e_b = float(np.sum(tg_b @ e_per_cell_b) / n_vectors)

        # Ternary sign detect: test both "chain" and "tree"
        t_variants = []
        for arch in ("chain", "tree"):
            blk_t = build_sign_detect(libs, "t", n_t, arch=arch)
            summ_t = blk_t.netlist.summary(res_t)
            in_codes_t = golden.to_code("t", golden.encode_digits("t", test_vals, n_t))
            _, tg_t = blk_t.netlist.simulate_activity(in_codes_t)
            e_per_cell_t = np.array(res_t.energy)
            dyn_e_t = float(np.sum(tg_t @ e_per_cell_t) / n_vectors)
            t_variants.append({
                "arch": arch,
                "summary": summ_t,
                "dyn_energy_fj": dyn_e_t,
            })

        # Pick best ternary architecture by static delay (primary metric)
        best_t = min(t_variants, key=lambda x: x["summary"]["delay_ps"])

        # Relative saving r = 1 - T / B for delay
        delay_b = summ_b["delay_ps"]
        delay_t = best_t["summary"]["delay_ps"]
        delay_saving = 1.0 - (delay_t / delay_b)

        # Transistor & energy saving
        tx_b = summ_b["transistors"]
        tx_t = best_t["summary"]["transistors"]
        tx_saving = 1.0 - (tx_t / tx_b)

        e_b = dyn_e_b
        e_t = best_t["dyn_energy_fj"]
        e_saving = 1.0 - (e_t / e_b) if e_b > 0 else 0.0

        results["sign_detect"].append({
            "iso_pair": f"{n_b}b_vs_{n_t}t",
            "n_bits": n_b,
            "n_trits": n_t,
            "effective_bits_t": round(n_t * 1.58496, 2),
            "binary": {
                "arch": "scan",
                "summary": summ_b,
                "dyn_energy_fj": dyn_e_b,
            },
            "ternary_variants": t_variants,
            "best_ternary": best_t["arch"],
            "relative_savings": {
                "delay_primary": delay_saving,
                "transistors": tx_saving,
                "energy": e_saving,
            },
            "nominal_verdict": "REFUTED" if delay_saving < 0.10 else "SUPPORTED",
        })

    # 2. Full Comparator Comparison
    for n_b, n_t in widths:
        lo_b, hi_b = golden.word_range("b", n_b, signed=True)
        lo_t, hi_t = golden.word_range("t", n_t)
        common_lo = max(lo_b, lo_t)
        common_hi = min(hi_b, hi_t)

        a_vals = rng.integers(common_lo, common_hi + 1, size=n_vectors)
        b_vals = rng.integers(common_lo, common_hi + 1, size=n_vectors)
        # Add equal and corner cases
        a_vals[:100] = b_vals[:100]

        # Best binary comparator (test "tree" vs "sub:ripple")
        b_variants = []
        for arch in ("tree", "sub:ripple"):
            blk = build_cmp(libs, "b", n_b, arch=arch)
            summ = blk.netlist.summary(res_b)
            in_a = golden.to_code("b", golden.encode_digits("b", a_vals, n_b, signed=True))
            in_b = golden.to_code("b", golden.encode_digits("b", b_vals, n_b, signed=True))
            in_both = np.concatenate([in_a, in_b], axis=1)
            _, tg = blk.netlist.simulate_activity(in_both)
            dyn_e = float(np.sum(tg @ np.array(res_b.energy)) / n_vectors)
            b_variants.append({"arch": arch, "summary": summ, "dyn_energy_fj": dyn_e})
        best_b = min(b_variants, key=lambda x: x["summary"]["delay_ps"])

        # Best ternary comparator (test "tree" vs "sub:ripple")
        t_variants = []
        for arch in ("tree", "sub:ripple"):
            blk = build_cmp(libs, "t", n_t, arch=arch)
            summ = blk.netlist.summary(res_t)
            in_a = golden.to_code("t", golden.encode_digits("t", a_vals, n_t))
            in_b = golden.to_code("t", golden.encode_digits("t", b_vals, n_t))
            in_both = np.concatenate([in_a, in_b], axis=1)
            _, tg = blk.netlist.simulate_activity(in_both)
            dyn_e = float(np.sum(tg @ np.array(res_t.energy)) / n_vectors)
            t_variants.append({"arch": arch, "summary": summ, "dyn_energy_fj": dyn_e})
        best_t = min(t_variants, key=lambda x: x["summary"]["delay_ps"])

        delay_saving = 1.0 - (best_t["summary"]["delay_ps"] / best_b["summary"]["delay_ps"])
        tx_saving = 1.0 - (best_t["summary"]["transistors"] / best_b["summary"]["transistors"])
        e_saving = 1.0 - (best_t["dyn_energy_fj"] / best_b["dyn_energy_fj"])

        results["comparator"].append({
            "iso_pair": f"{n_b}b_vs_{n_t}t",
            "n_bits": n_b,
            "n_trits": n_t,
            "best_binary": best_b["arch"],
            "best_ternary": best_t["arch"],
            "binary_metrics": best_b,
            "ternary_metrics": best_t,
            "relative_savings": {
                "delay_primary": delay_saving,
                "transistors": tx_saving,
                "energy": e_saving,
            },
            "nominal_verdict": "REFUTED" if delay_saving < 0.10 else "SUPPORTED",
        })

    return results


def save_and_report_comparator_results(results: Dict[str, Any], out_path: Optional[Path] = None) -> Path:
    p = out_path or (results_dir() / "m1_comparator_results.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return p
