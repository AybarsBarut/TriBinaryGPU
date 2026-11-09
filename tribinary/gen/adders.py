"""Adder generators: ripple-carry and carry-select, for every radix."""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .. import golden
from ..cells import Library
from ..netlist import Netlist
from .blocks import SYS, Block, Port, SysCfg


def stage(nl: Netlist, S: SysCfg, x: int, y: int, c: int) -> Tuple[int, int]:
    """One digit position: x + y + c -> (sum, carry), propagating constant-zero operands."""
    zero = nl.const(S.zero_code)
    nz = [n for n in (x, y, c) if nl.const_code(n) != S.zero_code]
    if len(nz) == 0:
        return zero, zero
    if len(nz) == 1:
        return nz[0], zero
    if len(nz) == 2:
        o = nl.cell(S.HA, *nz)
        return o[0], o[1]
    o = nl.cell(S.FA, x, y, c)
    return o[0], o[1]


def ripple(nl: Netlist, S: SysCfg, a: Sequence[int], b: Sequence[int], cin: int) -> Tuple[List[int], int]:
    sums = []
    c = cin
    for x, y in zip(a, b):
        s, c = stage(nl, S, x, y, c)
        sums.append(s)
    return sums, c


def carry_select(nl: Netlist, S: SysCfg, a: Sequence[int], b: Sequence[int], cin: int, k: int) -> Tuple[List[int], int]:
    n = len(a)
    k = max(1, min(k, n))
    sums, c = ripple(nl, S, a[:k], b[:k], cin)
    pos = k
    while pos < n:
        hi = min(pos + k, n)
        cands = []
        for code in S.carry_codes:
            s_v, c_v = ripple(nl, S, a[pos:hi], b[pos:hi], nl.const(code))
            cands.append((s_v, c_v))
        new_sums = []
        for i in range(hi - pos):
            new_sums.append(nl.g(S.MUX, c, *[cd[0][i] for cd in cands]))
        sums += new_sums
        c = nl.g(S.MUX, c, *[cd[1] for cd in cands])
        pos = hi
    return sums, c


def add(nl: Netlist, S: SysCfg, a, b, cin, arch: str) -> Tuple[List[int], int]:
    if arch == "ripple":
        return ripple(nl, S, a, b, cin)
    if arch.startswith("csel:"):
        return carry_select(nl, S, a, b, cin, int(arch.split(":")[1]))
    raise ValueError(f"unknown adder architecture {arch}")


def adder_archs(n: int) -> List[str]:
    archs = ["ripple"]
    for k in (2, 3, 4, 6, 8):
        if k < n:
            archs.append(f"csel:{k}")
    return archs


def _lib(libs: Dict[str, Library], S: SysCfg) -> Library:
    return libs[S.lib]


def build_adder(libs: Dict[str, Library], system: str, n: int, arch: str = "ripple") -> Block:
    S = SYS[system]
    nl = Netlist(libs[S.lib], f"adder_{system}{n}_{arch}")
    a = [nl.inp(f"a[{i}]") for i in range(n)]
    b = [nl.inp(f"b[{i}]") for i in range(n)]
    cin = nl.inp("cin")
    sums, cout = add(nl, S, a, b, cin, arch)
    for i, s in enumerate(sums):
        nl.out(f"s[{i}]", s)
    nl.out("cout", cout)
    R = S.radix

    def gold(v):
        A, B, C = v["a"], v["b"], v["cin"]
        tot = A + B + C
        if system == "t":
            half = (3 ** n - 1) // 2
            s = ((tot + half) % (3 ** n)) - half
            cy = (tot - s) // (3 ** n)
        else:
            s = tot % (R ** n)
            cy = tot // (R ** n)
        return {"s": s, "cout": cy}

    return Block(
        name=nl.name, system=system, netlist=nl,
        in_ports=[Port("a", n), Port("b", n), Port("cin", 1, "digit", domain=(0, 1) if system == "q" else None)],
        out_ports=[Port("s", n), Port("cout", 1, "digit")],
        golden=gold, params={"kind": "adder", "n": n, "arch": arch},
    )
