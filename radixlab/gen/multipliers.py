"""Multiplier generators: partial-product bit heap with Wallace-style (tree) or array-style (chain)
compression, followed by a final adder (ripple or carry-select). Works for every radix.

* binary: unsigned AND array, or signed Baugh-Wooley
* ternary: signed (balanced), one TMUL per digit pair
* quaternary: unsigned, one QMUL (two output digits) per digit pair; the signed quaternary
  multiplier is not part of M1 (open question Q19)
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np

from ..cells import Library
from ..netlist import Netlist
from .adders import add
from .blocks import SYS, Block, Port, SysCfg


def _compress(nl: Netlist, S: SysCfg, cols: List[List[int]], strategy: str) -> List[List[int]]:
    ncols = len(cols)
    if strategy == "wallace":
        guard = 0
        while max(len(c) for c in cols) > 2:
            guard += 1
            if guard > 200:
                raise RuntimeError("compression did not converge")
            new: List[List[int]] = [[] for _ in range(ncols + 1)]
            for c in range(ncols):
                items = cols[c]
                i = 0
                while len(items) - i >= 3:
                    s, cy = nl.cell(S.FA, items[i], items[i + 1], items[i + 2])
                    new[c].append(s)
                    new[c + 1].append(cy)
                    i += 3
                new[c].extend(items[i:])
            cols = new[:ncols]
        return cols
    if strategy == "array":
        cols = [list(c) for c in cols]
        for c in range(ncols):
            items = cols[c]
            while len(items) >= 3:
                a, b, d = items.pop(0), items.pop(0), items.pop(0)
                s, cy = nl.cell(S.FA, a, b, d)
                items.insert(0, s)
                if c + 1 < ncols:
                    cols[c + 1].append(cy)
            cols[c] = items
        return cols
    raise ValueError(f"unknown compression strategy {strategy}")


def build_multiplier(libs: Dict[str, Library], system: str, n: int, arch: str = "wallace",
                     final: str = "ripple", signed: bool = False) -> Block:
    """arch in {wallace, array}; final is an adder architecture string (see adders.add)."""
    S = SYS[system]
    if system == "q" and signed:
        raise ValueError("signed quaternary multiplier is not implemented in M1 (open question Q19)")
    tag = f"mul_{system}{n}{'s' if signed else ''}_{arch}_{final}"
    nl = Netlist(libs[S.lib], tag)
    a = [nl.inp(f"a[{i}]") for i in range(n)]
    b = [nl.inp(f"b[{i}]") for i in range(n)]
    W = 2 * n
    cols: List[List[int]] = [[] for _ in range(W)]

    if system == "b":
        for i in range(n):
            for j in range(n):
                inv = signed and ((i == n - 1) != (j == n - 1))
                net = nl.g("NAND2" if inv else "AND2", a[i], b[j])
                cols[i + j].append(net)
        if signed:
            one = nl.const(1)
            cols[n].append(one)
            cols[W - 1].append(one)
    elif system == "t":
        for i in range(n):
            for j in range(n):
                cols[i + j].append(nl.g("TMUL", a[i], b[j]))
    else:
        for i in range(n):
            for j in range(n):
                lo, hi = nl.cell("QMUL", a[i], b[j])
                cols[i + j].append(lo)
                if i + j + 1 < W:
                    cols[i + j + 1].append(hi)

    cols = _compress(nl, S, cols, arch)
    zero = nl.const(S.zero_code)
    row0 = [c[0] if len(c) > 0 else zero for c in cols]
    row1 = [c[1] if len(c) > 1 else zero for c in cols]
    prod, _ = add(nl, S, row0, row1, zero, final)
    for i, p in enumerate(prod):
        nl.out(f"p[{i}]", p)

    R = S.radix

    def gold(v):
        A, B = v["a"], v["b"]
        P = A * B
        if system == "t":
            return {"p": P}
        return {"p": P % (R ** W)}

    return Block(
        name=tag, system=system, netlist=nl,
        in_ports=[Port("a", n, signed=signed), Port("b", n, signed=signed)],
        out_ports=[Port("p", W)],
        golden=gold, params={"kind": "multiplier", "n": n, "arch": arch, "final": final, "signed": signed},
    )


def multiplier_archs(n: int) -> List[Tuple[str, str]]:
    finals = ["ripple"]
    for k in (2, 4, 8):
        if k < 2 * n:
            finals.append(f"csel:{k}")
    return [(a, f) for a in ("wallace", "array") for f in finals]
