"""RadixLab Command-Line Interface (CLI)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import cells
from .micro.comparator import run_comparator_micro_experiment, save_and_report_comparator_results
from .paths import repo_root, results_dir
from .verify import VerificationGate


if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def cmd_verify(args) -> int:
    gate = VerificationGate()
    libs = cells.load_all()
    print("=" * 60)
    print("RadixLab Verification Gate (L0 Cells & L1 Blocks)")
    print("=" * 60)

    # L0
    print("\n--- L0: Truth Table Integrity ---")
    for name, lib in libs.items():
        probs = cells.check_against_golden(lib)
        if probs:
            print(f"FAILED {name}: {probs}")
            return 1
        print(f"PASSED {name}: {len(lib.cells)} cells match golden functions")

    # L1
    print("\n--- L1: Block Verification ---")
    from .gen.adders import build_adder
    from .gen.comparators import build_cmp, build_sign_detect
    from .gen.multipliers import build_multiplier

    suite = [
        # (type, block)
        ("Adder", build_adder(libs, "b", 4, "ripple")),
        ("Adder", build_adder(libs, "t", 3, "ripple")),
        ("Adder", build_adder(libs, "q", 3, "ripple")),
        ("Adder", build_adder(libs, "b", 8, "csel:4")),
        ("Adder", build_adder(libs, "t", 6, "csel:3")),
        ("Multiplier", build_multiplier(libs, "b", 4, arch="wallace", signed=False)),
        ("Multiplier", build_multiplier(libs, "b", 4, arch="wallace", signed=True)),
        ("Multiplier", build_multiplier(libs, "t", 3, arch="wallace")),
        ("Multiplier", build_multiplier(libs, "q", 2, arch="wallace")),
        ("SignDetect", build_sign_detect(libs, "b", 8, "scan")),
        ("SignDetect", build_sign_detect(libs, "t", 6, "tree")),
        ("Comparator", build_cmp(libs, "b", 8, "tree")),
        ("Comparator", build_cmp(libs, "t", 5, "tree")),
    ]

    for category, blk in suite:
        rec = gate.verify_block(blk, max_random_vectors=2048)
        status = "PASSED" if rec.passed else "FAILED"
        print(f"[{status}] {category:<12} {blk.name:<25} ({rec.method:<14}, {rec.n_vectors:>5} vectors, {rec.duration_ms:>6.2f} ms)")
        if not rec.passed:
            print(f"  Error: {rec.error_sample}")
            return 1

    print("\nAll blocks verified successfully. Certificates saved to verified.json.")
    return 0


def cmd_run(args) -> int:
    exp_path = Path(args.config)
    if not exp_path.exists():
        print(f"Experiment config not found: {exp_path}")
        return 1

    print(f"Running experiment from {exp_path}...")
    res = run_comparator_micro_experiment()
    out = save_and_report_comparator_results(res)
    print(f"Results saved to {out}")

    print("\n--- Sign Detection Iso-Precision Summary ---")
    for item in res["sign_detect"]:
        p = item["iso_pair"]
        r = item["relative_savings"]
        print(f"Pair: {p:<12} | Delay Saving: {r['delay_primary']*100:>6.1f}% | Transistors: {r['transistors']*100:>6.1f}% | Verdict: {item['nominal_verdict']}")

    print("\n--- Comparator Iso-Precision Summary ---")
    for item in res["comparator"]:
        p = item["iso_pair"]
        r = item["relative_savings"]
        print(f"Pair: {p:<12} | Delay Saving: {r['delay_primary']*100:>6.1f}% | Transistors: {r['transistors']*100:>6.1f}% | Verdict: {item['nominal_verdict']}")

    return 0


def cmd_assumptions(args) -> int:
    libs = cells.load_all()
    print("=" * 80)
    print("RadixLab Assumption Catalog (docs/assumptions.md)")
    print("=" * 80)
    for lib_name, lib in libs.items():
        print(f"\nLibrary: {lib_name.upper()} (Status: {lib.status})")
        print(f"  Voltage swing: {lib.voltage_swing.value} {lib.voltage_swing.unit} (confidence: {lib.voltage_swing.confidence})")
        for p in lib.all_params():
            if not p.id.endswith("transistors") and not p.id.endswith("delay_stages"):
                print(f"  - {p.id:<35} = {str(p.value):<8} {p.unit:<12} [{p.confidence:<6}] ({p.source})")
    return 0


def cmd_review(args) -> int:
    from ai.agents.red_team import RedTeamAgent
    from ai.nim_client import NIMClient

    client = NIMClient()
    if not client.is_available:
        print("NVIDIA NIM is not configured. Set NVIDIA_API_KEY to run red-team reviews.")
        return 1

    print("Running Red Team Agent via NVIDIA NIM...")
    agent = RedTeamAgent(client)
    res_path = results_dir() / "m1_comparator_results.json"
    if not res_path.exists():
        print("Run 'radixlab run experiments/m1_comparator.yaml' first.")
        return 1

    critique = agent.review_experiment_results("M1 Comparator & Sign Detection", res_path.read_text(encoding="utf-8"))
    print("\n=== NVIDIA Red Team Critique ===")
    print(critique)
    return 0


def main():
    parser = argparse.ArgumentParser(prog="radixlab", description="RadixLab CLI")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_v = sub.add_parser("verify", help="Run verification gate suite")
    p_v.add_argument("--suite", default="m1", choices=["m1", "all"])
    p_v.set_defaults(func=cmd_verify)

    p_r = sub.add_parser("run", help="Run an experiment YAML")
    p_r.add_argument("config", help="Path to experiment YAML")
    p_r.set_defaults(func=cmd_run)

    p_a = sub.add_parser("assumptions", help="Display assumption parameters catalog")
    p_a.set_defaults(func=cmd_assumptions)

    p_rev = sub.add_parser("review", help="Run NVIDIA NIM Red-Team audit")
    p_rev.set_defaults(func=cmd_review)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
