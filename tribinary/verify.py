"""Verification harness and certification gate (docs/methodology.md section 6).

Implements L0 (cells) and L1 (blocks) equivalence checks against golden models.
Rules:
1. Blocks with <= EXHAUSTIVE_LIMIT input states are verified exhaustively.
2. Larger blocks are tested with deterministic corner cases plus pseudo-random vectors.
3. Passed checks produce a signed/hashed certificate. Unverified blocks cannot contribute to results.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import golden
from .cells import Library, check_against_golden
from .gen.blocks import Block, Port
from .netlist import Netlist
from .paths import repo_root
from .reference import ReferenceEvaluator

EXHAUSTIVE_LIMIT = 32_768  # 2^15 vectors threshold for exhaustive verification


@dataclass
class VerificationRecord:
    block_name: str
    system: str
    netlist_hash: str
    method: str  # "exhaustive" or "random+corners"
    n_vectors: int
    passed: bool
    duration_ms: float
    mismatches: int = 0
    error_sample: Optional[str] = None


class VerificationGate:
    def __init__(self, cert_file: Optional[Path] = None):
        self.cert_file = cert_file or (repo_root() / "verified.json")
        self.certificates: Dict[str, dict] = self._load()

    def _load(self) -> Dict[str, dict]:
        if self.cert_file.exists():
            try:
                return json.loads(self.cert_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def save(self) -> None:
        self.cert_file.write_text(json.dumps(self.certificates, indent=2), encoding="utf-8")

    def is_verified(self, netlist_hash: str) -> bool:
        cert = self.certificates.get(netlist_hash)
        return bool(cert and cert.get("passed"))

    def verify_block(
        self,
        block: Block,
        max_random_vectors: int = 65_536,
        base_seed: int = 42,
        check_differential: bool = False,
    ) -> VerificationRecord:
        """Verify block netlist against its golden model."""
        start_time = time.perf_counter()
        sys_ = block.system
        r = golden.RADIX[sys_]
        nl = block.netlist

        # Calculate input state space
        total_digits = sum(p.n for p in block.in_ports)
        # Port domain checks
        port_domains = []
        for p in block.in_ports:
            if p.domain is not None:
                port_domains.append(len(p.domain) ** p.n)
            else:
                port_domains.append(r ** p.n)
        total_states = 1
        for d in port_domains:
            total_states *= d

        method = "exhaustive" if total_states <= EXHAUSTIVE_LIMIT else "random+corners"

        if method == "exhaustive":
            # Generate all possible input states
            inputs_dict = {}
            # Build cartesian product across ports
            grids = []
            for p in block.in_ports:
                if p.kind == "digit":
                    dom = list(p.domain) if p.domain is not None else golden.levels(sys_)
                    grids.append(np.array(dom, dtype=np.int64))
                else:
                    lo, hi = golden.word_range(sys_, p.n, signed=p.signed)
                    grids.append(np.arange(lo, hi + 1, dtype=np.int64))

            mesh = np.meshgrid(*grids, indexing="ij")
            N = mesh[0].size
            for p, m in zip(block.in_ports, mesh):
                inputs_dict[p.name] = m.reshape(-1)
        else:
            # Deterministic corners + random samples
            rng = np.random.default_rng(base_seed)
            corner_dict: Dict[str, List[int]] = {p.name: [] for p in block.in_ports}

            # Generate corner combinations per port
            for p in block.in_ports:
                if p.kind == "digit":
                    dom = list(p.domain) if p.domain is not None else golden.levels(sys_)
                    c = dom
                else:
                    lo, hi = golden.word_range(sys_, p.n, signed=p.signed)
                    c = [lo, hi, 0, 1, -1]
                    # Add alternating digit patterns
                    c.extend([lo // 2, hi // 2])
                    c = [v for v in c if lo <= v <= hi]
                corner_dict[p.name] = c

            # Cartesian product of corners (bounded)
            corner_grids = np.meshgrid(*[corner_dict[p.name] for p in block.in_ports], indexing="ij")
            n_corners = corner_grids[0].size
            corners_flattened = {p.name: corner_grids[i].reshape(-1) for i, p in enumerate(block.in_ports)}

            # Generate remaining random samples
            n_random = max_random_vectors
            random_inputs = {}
            for p in block.in_ports:
                if p.kind == "digit":
                    dom = list(p.domain) if p.domain is not None else golden.levels(sys_)
                    random_inputs[p.name] = rng.choice(dom, size=n_random)
                else:
                    lo, hi = golden.word_range(sys_, p.n, signed=p.signed)
                    random_inputs[p.name] = rng.integers(lo, hi + 1, size=n_random)

            # Combine corners and random
            inputs_dict = {}
            for p in block.in_ports:
                inputs_dict[p.name] = np.concatenate([corners_flattened[p.name], random_inputs[p.name]])

            N = inputs_dict[block.in_ports[0].name].shape[0]

        # Convert input port values to flat input code matrix [N, n_inputs]
        code_cols = []
        for p in block.in_ports:
            val_col = inputs_dict[p.name]
            if p.kind == "digit":
                digit_matrix = val_col.reshape(-1, 1)
            else:
                digit_matrix = golden.encode_digits(sys_, val_col, p.n, signed=p.signed)
            code_matrix = golden.to_code(sys_, digit_matrix)
            code_cols.append(code_matrix)

        in_codes = np.concatenate(code_cols, axis=1).astype(np.uint8)

        # 1. Run simulation via Rust engine
        sim_out_codes = nl.simulate(in_codes)

        # Optional 1b. Run differential test against Python reference evaluator
        if check_differential:
            ref = ReferenceEvaluator(nl.spec())
            ref_out = ref.eval_batch(in_codes)
            if not np.array_equal(sim_out_codes, ref_out):
                diff_idx = np.where(np.any(sim_out_codes != ref_out, axis=1))[0][0]
                record = VerificationRecord(
                    block_name=block.name,
                    system=block.system,
                    netlist_hash=nl.hash(),
                    method=method,
                    n_vectors=N,
                    passed=False,
                    duration_ms=(time.perf_counter() - start_time) * 1000.0,
                    mismatches=int(np.sum(np.any(sim_out_codes != ref_out, axis=1))),
                    error_sample=f"Rust engine vs Python Reference mismatch at vector {diff_idx}: Rust={sim_out_codes[diff_idx]}, Python={ref_out[diff_idx]}",
                )
                return record

        # 2. Run golden model
        golden_outputs = block.golden(inputs_dict)

        # 3. Decode simulation outputs and compare with golden outputs
        mismatches = 0
        error_sample = None
        col_offset = 0
        for p in block.out_ports:
            port_codes = sim_out_codes[:, col_offset : col_offset + p.n]
            port_digit_vals = golden.from_code(sys_, port_codes)
            if p.kind == "digit":
                sim_vals = port_digit_vals.reshape(-1)
            else:
                sim_vals = golden.decode_digits(sys_, port_digit_vals, signed=p.signed)

            expected_vals = golden_outputs[p.name]
            diff = sim_vals != expected_vals
            diff_count = int(np.sum(diff))
            if diff_count > 0:
                mismatches += diff_count
                if error_sample is None:
                    first_bad = np.where(diff)[0][0]
                    bad_inputs = {k: inputs_dict[k][first_bad] for k in inputs_dict}
                    error_sample = f"Port '{p.name}' mismatch at vector {first_bad}: inputs={bad_inputs}, sim={sim_vals[first_bad]}, expected={expected_vals[first_bad]}"
            col_offset += p.n

        passed = (mismatches == 0)
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        record = VerificationRecord(
            block_name=block.name,
            system=block.system,
            netlist_hash=nl.hash(),
            method=method,
            n_vectors=N,
            passed=passed,
            duration_ms=duration_ms,
            mismatches=mismatches,
            error_sample=error_sample,
        )

        if passed:
            self.certificates[nl.hash()] = {
                "block_name": block.name,
                "system": block.system,
                "method": method,
                "n_vectors": N,
                "passed": True,
                "timestamp": time.time(),
                "duration_ms": duration_ms,
            }
            self.save()

        return record
