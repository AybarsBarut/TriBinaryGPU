"""Gate-level netlist container and builder.

Nets are integers. Primary inputs, constants, cell outputs and sequential outputs are the only drivers.
Signal values are **codes** (see golden.py): binary 0/1, ternary 0/1/2 for -1/0/+1 (3 = X),
quaternary 0..3.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import golden
from .cells import Library, Resolved


@dataclass
class Instance:
    type: str
    ins: Tuple[int, ...]
    outs: Tuple[int, ...]


class Netlist:
    def __init__(self, lib: Library, name: str = "netlist"):
        self.lib = lib
        self.name = name
        self.n_nets = 0
        self.inputs: List[Tuple[int, str]] = []
        self.outputs: List[Tuple[int, str]] = []
        self.consts: Dict[int, int] = {}      # net -> code
        self._const_by_code: Dict[int, int] = {}
        self.cells: List[Instance] = []
        self.macro_instances: List[str] = []  # names of parametric macro instances (flagged, not simulated)
        self._engine = None
        self._spec = None

    # ---- building ----
    def new_net(self) -> int:
        self.n_nets += 1
        self._engine = None
        self._spec = None
        return self.n_nets - 1

    def inp(self, name: str) -> int:
        n = self.new_net()
        self.inputs.append((n, name))
        return n

    def const(self, code: int) -> int:
        """Return the (shared) constant net holding `code`."""
        if code not in self._const_by_code:
            n = self.new_net()
            self.consts[n] = code
            self._const_by_code[code] = n
        return self._const_by_code[code]

    def const_code(self, net: int) -> Optional[int]:
        return self.consts.get(net)

    def cell(self, type_name: str, *ins: int) -> Tuple[int, ...]:
        c = self.lib.cells[type_name]
        if len(ins) != c.n_in:
            raise ValueError(f"{type_name} expects {c.n_in} inputs, got {len(ins)}")
        outs = tuple(self.new_net() for _ in range(c.n_out))
        self.cells.append(Instance(type_name, tuple(ins), outs))
        return outs

    def g(self, type_name: str, *ins: int) -> int:
        """Instantiate a cell and return its first output net."""
        return self.cell(type_name, *ins)[0]

    def out(self, name: str, net: int) -> None:
        self.outputs.append((net, name))
        self._spec = None
        self._engine = None

    # ---- introspection ----
    @property
    def input_names(self) -> List[str]:
        return [n for _, n in self.inputs]

    @property
    def output_names(self) -> List[str]:
        return [n for _, n in self.outputs]

    def type_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for c in self.cells:
            counts[c.type] = counts.get(c.type, 0) + 1
        return counts

    def count_vector(self) -> np.ndarray:
        """Cell counts indexed like lib.order."""
        tc = self.type_counts()
        return np.array([tc.get(n, 0) for n in self.lib.order], dtype=np.float64)

    # ---- engine interface ----
    def spec(self) -> dict:
        if self._spec is None:
            idx = {n: i for i, n in enumerate(self.lib.order)}
            self._spec = {
                "radix": self.lib.radix,
                "cell_types": self.lib.engine_types(),
                "n_nets": self.n_nets,
                "inputs": [n for n, _ in self.inputs],
                "outputs": [n for n, _ in self.outputs],
                "consts": [[n, c] for n, c in self.consts.items()],
                "cells": [{"t": idx[c.type], "ins": list(c.ins), "outs": list(c.outs)} for c in self.cells],
            }
        return self._spec

    def hash(self) -> str:
        """Content hash: structure plus the truth tables of the library it uses."""
        s = self.spec()
        used = sorted(set(c.type for c in self.cells))
        tables = {n: self.lib.cells[n].tables for n in used}
        payload = {
            "radix": s["radix"], "lib": self.lib.name, "tables": tables,
            "inputs": self.input_names, "outputs": self.output_names,
            "consts": sorted(s["consts"]),
            "cells": [(c.type, c.ins, c.outs) for c in self.cells],
        }
        blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(blob).hexdigest()

    def engine(self):
        if self._engine is None:
            from . import _core  # type: ignore
            self._engine = _core.Engine(json.dumps(self.spec()))
        return self._engine

    # ---- simulation helpers ----
    def simulate(self, in_codes: np.ndarray) -> np.ndarray:
        """in_codes: uint8 [N, n_inputs] -> uint8 [N, n_outputs]."""
        a = np.ascontiguousarray(in_codes, dtype=np.uint8)
        n = a.shape[0]
        out = self.engine().eval(a.tobytes(), n)
        return np.frombuffer(out, dtype=np.uint8).reshape(n, len(self.outputs))

    def simulate_activity(self, in_codes: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Returns (outputs, toggles) with toggles uint32 [N, n_cell_types] indexed like lib.order."""
        a = np.ascontiguousarray(in_codes, dtype=np.uint8)
        n = a.shape[0]
        out, tg = self.engine().eval_activity(a.tobytes(), n)
        return (
            np.frombuffer(out, dtype=np.uint8).reshape(n, len(self.outputs)),
            np.frombuffer(tg, dtype="<u4").reshape(n, len(self.lib.order)),
        )

    def sta(self, res: Resolved):
        """Static critical path: (delay_ps, path as list of Instance, per-output arrival)."""
        delay, path, arr = self.engine().sta(res.delay)
        comb = [c for c in self.cells if not self.lib.cells[c.type].sequential]
        # engine orders combinational cells topologically; map indices back via output nets
        return delay, path, arr

    def levels(self) -> int:
        """Logic depth in cell levels (every output of every cell counted as one unit)."""
        unit = [[1.0] * self.lib.cells[n].n_out for n in self.lib.order]
        d, _, _ = self.engine().sta(unit)
        return int(round(d))

    def summary(self, res: Resolved) -> dict:
        cv = self.count_vector()
        delay, _, _ = self.sta(res)
        return {
            "cells": int(cv.sum()),
            "transistors": float(cv @ np.array(res.transistors)),
            "area_um2": float(cv @ np.array(res.area)),
            "leakage_nw": float(cv @ np.array(res.leakage)),
            "delay_ps": float(delay),
            "levels": self.levels(),
        }
