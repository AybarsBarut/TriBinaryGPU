"""Pure-Python reference evaluator for differential testing (closed decision Q9).

Deliberately simple, slow, and transparent: no bit-parallel packing, no multi-threading,
no heuristics. Evaluates a netlist specification one vector at a time, gate-by-gate,
to cross-check the Rust simulation engine.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence, Tuple
import numpy as np


class ReferenceEvaluator:
    """Independent golden evaluator for netlist specs."""

    def __init__(self, spec: Dict[str, Any]):
        self.radix = int(spec["radix"])
        self.cell_types = spec["cell_types"]
        self.n_nets = int(spec["n_nets"])
        self.inputs = list(spec["inputs"])
        self.outputs = list(spec["outputs"])
        self.consts = {int(net): int(code) for net, code in spec.get("consts", [])}
        self.cells = spec["cells"]

        # Build topological evaluation order using Kahn's algorithm
        driver = {}
        for ci, cell in enumerate(self.cells):
            for out_net in cell["outs"]:
                driver[out_net] = ci

        indeg = [0] * len(self.cells)
        users: List[List[int]] = [[] for _ in range(len(self.cells))]
        for ci, cell in enumerate(self.cells):
            for in_net in cell["ins"]:
                if in_net in driver:
                    d_ci = driver[in_net]
                    indeg[ci] += 1
                    users[d_ci].append(ci)

        queue = [ci for ci, deg in enumerate(indeg) if deg == 0]
        order = []
        while queue:
            cur = queue.pop(0)
            order.append(cur)
            for u in users[cur]:
                indeg[u] -= 1
                if indeg[u] == 0:
                    queue.append(u)

        if len(order) != len(self.cells):
            raise ValueError("Combinational loop detected in netlist")
        self.eval_order = order

    def eval_vector(self, in_codes: Sequence[int]) -> List[int]:
        if len(in_codes) != len(self.inputs):
            raise ValueError(f"Expected {len(self.inputs)} inputs, got {len(in_codes)}")

        nets = [0] * self.n_nets
        for net, code in self.consts.items():
            nets[net] = code
        for in_net, code in zip(self.inputs, in_codes):
            nets[in_net] = code

        for ci in self.eval_order:
            cell = self.cells[ci]
            ct = self.cell_types[cell["t"]]
            in_vals = [nets[net] for net in cell["ins"]]

            # Table row index calculation: sum(in_vals[i] * (radix ** i))
            # Note: For radix 3, if unknown state 3 is present, evaluate pessimistically.
            row_idx = 0
            has_x = self.radix == 3 and any(v == 3 for v in in_vals)

            if not has_x:
                for i, v in enumerate(in_vals):
                    row_idx += v * (self.radix ** i)
                for o_idx, out_net in enumerate(cell["outs"]):
                    nets[out_net] = ct["tables"][o_idx][row_idx]
            else:
                # Pessimistic X propagation: try all ternary substitutions (0, 1, 2)
                x_positions = [i for i, v in enumerate(in_vals) if v == 3]
                sub_count = 3 ** len(x_positions)
                for o_idx, out_net in enumerate(cell["outs"]):
                    cand_outs = set()
                    for sub in range(sub_count):
                        test_vals = list(in_vals)
                        curr = sub
                        for pos in x_positions:
                            test_vals[pos] = curr % 3
                            curr //= 3
                        r_idx = sum(test_vals[i] * (3 ** i) for i in range(len(test_vals)))
                        cand_outs.add(ct["tables"][o_idx][r_idx])
                    if len(cand_outs) == 1:
                        nets[out_net] = cand_outs.pop()
                    else:
                        nets[out_net] = 3  # Output is unknown X

        return [nets[out_net] for out_net in self.outputs]

    def eval_batch(self, in_codes_matrix: np.ndarray) -> np.ndarray:
        """Evaluates batch of inputs [N, n_inputs] -> returns [N, n_outputs]."""
        arr = np.asarray(in_codes_matrix, dtype=np.uint8)
        N = arr.shape[0]
        n_out = len(self.outputs)
        result = np.zeros((N, n_out), dtype=np.uint8)
        for i in range(N):
            result[i, :] = self.eval_vector(arr[i, :])
        return result
