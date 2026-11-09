"""Sign detection and comparator generators (M1 micro-experiment, hypotheses H2/H3).

Blocks
------
sign_detect(x): sign class of an n-digit signed word x.
    binary : outputs neg (= MSB, no cell) and zero (NOR/NAND reduction tree)
    ternary: output sgn in {-1,0,+1}: the sign of the most significant NON-ZERO trit
cmp(a, b): sign(a - b) with the same output convention.

Architectures (all offered where meaningful, best per metric chosen by the experiment):
    binary  sign_detect: "scan" (only one)
    binary  cmp: "sub:<adder arch>" (widened subtract), "tree" (log-depth magnitude comparator)
    ternary sign_detect: "chain" (linear priority), "tree" (log-depth priority)
    ternary cmp: "tree" (TCMP per trit + priority tree), "sub:<adder arch>" (STI + adder + scan)
"""
from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import numpy as np

from ..cells import Library
from ..netlist import Netlist
from .adders import add, adder_archs
from .blocks import SYS, Block, Port


# ---------------------------------------------------------------- binary helpers
def or_tree_zero_flag(nl: Netlist, nets: Sequence[int]) -> int:
    """Return a net that is 1 iff all `nets` are 0, using alternating NOR2/NAND2 levels."""
    items = list(nets)
    inverted = False  # items represent OR-partial results; `inverted` means they hold the complement
    if len(items) == 1:
        return nl.g("NOT", items[0])
    while len(items) > 1:
        nxt = []
        i = 0
        while i + 1 < len(items):
            if not inverted:
                nxt.append(nl.g("NOR2", items[i], items[i + 1]))     # complement of OR
            else:
                nxt.append(nl.g("NAND2", items[i], items[i + 1]))    # true OR of the true values
            i += 2
        if i < len(items):
            # bring the leftover to the polarity of the new level
            nxt.append(nl.g("NOT", items[i]))
        items = nxt
        inverted = not inverted
    return items[0] if inverted else nl.g("NOT", items[0])


def build_sign_detect_b(libs, n: int, arch: str = "scan") -> Block:
    nl = Netlist(libs["binary"], f"signdet_b{n}_{arch}")
    x = [nl.inp(f"x[{i}]") for i in range(n)]
    nl.out("neg", x[n - 1])
    nl.out("zero", or_tree_zero_flag(nl, x))
    return Block(
        name=nl.name, system="b", netlist=nl,
        in_ports=[Port("x", n, signed=True)],
        out_ports=[Port("neg", 1, "digit"), Port("zero", 1, "digit")],
        golden=lambda v: {"neg": (v["x"] < 0).astype(np.int64), "zero": (v["x"] == 0).astype(np.int64)},
        params={"kind": "sign_detect", "n": n, "arch": arch},
    )


def build_cmp_b(libs, n: int, arch: str) -> Block:
    nl = Netlist(libs["binary"], f"cmp_b{n}_{arch}")
    a = [nl.inp(f"a[{i}]") for i in range(n)]
    b = [nl.inp(f"b[{i}]") for i in range(n)]
    S = SYS["b"]
    if arch.startswith("sub:"):
        sub_arch = arch[4:]
        nb = [nl.g("NOT", b[i]) for i in range(n)]
        a_ext = a + [a[n - 1]]
        b_ext = nb + [nb[n - 1]]
        d, _ = add(nl, S, a_ext, b_ext, nl.const(1), sub_arch)
        neg = d[n]
        zero = or_tree_zero_flag(nl, d[:n])
    elif arch == "tree":
        nodes: List[Tuple[int, int]] = []
        for i in range(n):
            if i < n - 1:
                nb_i = nl.g("NOT", b[i])
                lt = nl.g("NOR2", a[i], nb_i)             # (not a) and b
            else:
                na = nl.g("NOT", a[i])
                lt = nl.g("NOR2", na, b[i])               # a and (not b): negative a is smaller (signed MSB)
            eq = nl.g("NOT", nl.g("XOR2", a[i], b[i]))
            nodes.append((lt, eq))
        while len(nodes) > 1:
            nxt = []
            i = 0
            while i + 1 < len(nodes):
                lt_lo, eq_lo = nodes[i]
                lt_hi, eq_hi = nodes[i + 1]
                lt = nl.g("OR2", lt_hi, nl.g("AND2", eq_hi, lt_lo))
                eq = nl.g("AND2", eq_hi, eq_lo)
                nxt.append((lt, eq))
                i += 2
            if i < len(nodes):
                nxt.append(nodes[i])
            nodes = nxt
        neg, zero = nodes[0]
    else:
        raise ValueError(arch)
    nl.out("neg", neg)
    nl.out("zero", zero)
    return Block(
        name=nl.name, system="b", netlist=nl,
        in_ports=[Port("a", n, signed=True), Port("b", n, signed=True)],
        out_ports=[Port("neg", 1, "digit"), Port("zero", 1, "digit")],
        golden=lambda v: {"neg": (v["a"] < v["b"]).astype(np.int64), "zero": (v["a"] == v["b"]).astype(np.int64)},
        params={"kind": "cmp", "n": n, "arch": arch},
    )


# ---------------------------------------------------------------- ternary helpers
def zsel_scan(nl: Netlist, digits: Sequence[int], arch: str) -> int:
    """Sign of the most significant non-zero digit of `digits` (little endian)."""
    if arch == "chain":
        s = digits[0]
        for i in range(1, len(digits)):
            s = nl.g("ZSEL", digits[i], s)
        return s
    if arch == "tree":
        items = list(digits)
        while len(items) > 1:
            nxt = []
            i = 0
            while i + 1 < len(items):
                nxt.append(nl.g("ZSEL", items[i + 1], items[i]))  # (hi, lo)
                i += 2
            if i < len(items):
                nxt.append(items[i])
            items = nxt
        return items[0]
    raise ValueError(arch)


def build_sign_detect_t(libs, n: int, arch: str) -> Block:
    nl = Netlist(libs["ternary"], f"signdet_t{n}_{arch}")
    x = [nl.inp(f"x[{i}]") for i in range(n)]
    nl.out("sgn", zsel_scan(nl, x, arch))
    return Block(
        name=nl.name, system="t", netlist=nl,
        in_ports=[Port("x", n)],
        out_ports=[Port("sgn", 1, "digit")],
        golden=lambda v: {"sgn": np.sign(v["x"]).astype(np.int64)},
        params={"kind": "sign_detect", "n": n, "arch": arch},
    )


def build_cmp_t(libs, n: int, arch: str) -> Block:
    nl = Netlist(libs["ternary"], f"cmp_t{n}_{arch}")
    a = [nl.inp(f"a[{i}]") for i in range(n)]
    b = [nl.inp(f"b[{i}]") for i in range(n)]
    S = SYS["t"]
    if arch == "tree":
        c = [nl.g("TCMP", a[i], b[i]) for i in range(n)]
        sgn = zsel_scan(nl, c, "tree")
    elif arch.startswith("sub:"):
        nb = [nl.g("STI", b[i]) for i in range(n)]
        s, cout = add(nl, S, a, nb, nl.const(S.zero_code), arch[4:])
        # value = s + 3^n * cout and |s| < 3^n / 2, so cout (if non-zero) decides the sign
        sgn = nl.g("ZSEL", cout, zsel_scan(nl, s, "tree"))
    else:
        raise ValueError(arch)
    nl.out("sgn", sgn)
    return Block(
        name=nl.name, system="t", netlist=nl,
        in_ports=[Port("a", n), Port("b", n)],
        out_ports=[Port("sgn", 1, "digit")],
        golden=lambda v: {"sgn": np.sign(v["a"] - v["b"]).astype(np.int64)},
        params={"kind": "cmp", "n": n, "arch": arch},
    )


def sign_detect_archs(system: str, n: int) -> List[str]:
    return ["scan"] if system == "b" else ["chain", "tree"]


def cmp_archs(system: str, n: int) -> List[str]:
    subs = [f"sub:{a}" for a in adder_archs(n + 1 if system == "b" else n)]
    return subs + ["tree"]


def build_sign_detect(libs, system: str, n: int, arch: str) -> Block:
    return build_sign_detect_b(libs, n, arch) if system == "b" else build_sign_detect_t(libs, n, arch)


def build_cmp(libs, system: str, n: int, arch: str) -> Block:
    return build_cmp_b(libs, n, arch) if system == "b" else build_cmp_t(libs, n, arch)
