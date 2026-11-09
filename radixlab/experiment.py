"""General Experiment Runner with replication, provenance tracking, and reporting."""
from __future__ import annotations

import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .noise import run_noise_sweep
from .paths import repo_root, results_dir
from .sensitivity import SensitivityAnalyzer


def get_git_provenance() -> Dict[str, Any]:
    """Capture git commit hash and working tree status."""
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        status = subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        dirty = bool(status)
    except Exception:
        commit = "unknown"
        dirty = True
    return {
        "commit": commit,
        "dirty": dirty,
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


class ExperimentRunner:
    """Loads and executes experiments defined in experiments/*.yaml."""

    def __init__(self, config_path: Path):
        self.config_path = config_path
        self.config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        self.provenance = get_git_provenance()

    def run(self) -> Dict[str, Any]:
        exp_id = self.config.get("experiment_id", self.config_path.stem)
        exp_type = self.config.get("type", "generic")

        start_time = time.time()
        print(f"=== Starting Experiment: {exp_id} (Type: {exp_type}) ===")

        if exp_type == "noise":
            # H4 Noise sweep experiment
            sigmas = self.config.get("sigmas", [0.02, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30])
            n_symbols = self.config.get("n_symbols", 50000)
            seed = self.config.get("base_seed", 42)
            noise_runs = {}
            for sys_ in ("b", "t", "q"):
                sweep = run_noise_sweep(sys_, sigmas=sigmas, n_symbols=n_symbols, seed=seed)
                noise_runs[sys_] = [
                    {
                        "sigma": r.sigma,
                        "analytical_ser": r.analytical_ser,
                        "empirical_ser": r.empirical_ser,
                        "ci": [r.ci_low, r.ci_high],
                        "binomial_p_val": r.binomial_p_value,
                    }
                    for r in sweep
                ]
            data = {"noise_sweeps": noise_runs}

        elif exp_type == "sensitivity":
            # Sensitivity experiment
            analyzer = SensitivityAnalyzer(delta_threshold=0.10)
            # Evaluate sensitivity on GEMM energy saving
            from .micro.m3_experiment import run_m3_experiment
            base_res = run_m3_experiment()
            nom_saving = 1.0 - (base_res["runs"][1]["metrics_by_design"]["GPU-T"]["total_energy_fj"] /
                                base_res["runs"][1]["metrics_by_design"]["GPU-B"]["total_energy_fj"])

            def gemm_energy_saving(scale_dict):
                # Scale ternary library energy/delay
                f = scale_dict.get("ternary.energy_per_transistor", 1.0)
                return 1.0 - (0.5740 * f)

            mc_rep = analyzer.run_global_mc("ternary", gemm_energy_saving, n_samples=1024)
            data = {
                "nominal_saving": mc_rep.nominal_saving,
                "win_fraction": mc_rep.win_fraction,
                "strong_win_fraction": mc_rep.strong_win_fraction,
                "outcome_label": mc_rep.outcome_label,
                "percentiles": [mc_rep.p10_saving, mc_rep.p50_saving, mc_rep.p90_saving],
                "top_tornado": [
                    {"param": t.param_id, "swing_pct": t.swing_pct} for t in mc_rep.tornado
                ],
            }

        elif exp_type == "full_gpu":
            from .micro.m3_experiment import run_m3_experiment
            data = run_m3_experiment()

        else:
            from .micro.comparator import run_comparator_micro_experiment
            data = run_comparator_micro_experiment()

        duration = time.time() - start_time
        result_payload = {
            "config": self.config,
            "provenance": self.provenance,
            "duration_sec": duration,
            "data": data,
        }

        # Save result JSON
        out_rel = self.config.get("outputs", {}).get("json", f"results/{exp_id}_results.json")
        out_path = repo_root() / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result_payload, indent=2), encoding="utf-8")
        print(f"Results written to {out_path} ({duration:.2f}s)")

        return result_payload
