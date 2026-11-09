"""Golden (reference) models: cell functions and number-system conversions.

Everything here works in the **value domain** (binary 0/1, balanced ternary -1/0/+1, quaternary 0..3)
and is written independently of the simulator. The Rust engine and the pure-Python reference
evaluator work in the **code domain** (non-negative integers); `to_code` / `from_code` convert.
"""
from __future__ import annotations

from typing import Callable, Dict, Tuple

import numpy as np

# --------------------------------------------------------------------------------------
# value <-> code
# --------------------------------------------------------------------------------------
RADIX = {"b": 2, "t": 3, "q": 4}
X_CODE = {"b": None, "t": 3, "q": None}


def to_code(system: str, value):
    """Value-domain integer(s) -> code(s). Works for scalars and numpy arrays."""
    return value + 1 if system == "t" else value


def from_code(system: str, code):
    if system == "t":
        if isinstance(code, np.ndarray):
            return code.astype(np.int64) - 1
        return int(code) - 1
    if isinstance(code, np.ndarray):
        return code.astype(np.int64)
    return code


def levels(system: str):
    return {"b": [0, 1], "t": [-1, 0, 1], "q": [0, 1, 2, 3]}[system]


# --------------------------------------------------------------------------------------
# number systems (digit vectors are little-endian lists/arrays of digit *values*)
# --------------------------------------------------------------------------------------

def word_range(system: str, n: int, signed: bool = False) -> Tuple[int, int]:
    """Inclusive range of representable values of an n-digit word."""
    if system == "t":
        h = (3 ** n - 1) // 2
        return -h, h
    r = RADIX[system]
    if signed and system == "b":
        return -(2 ** (n - 1)), 2 ** (n - 1) - 1
    return 0, r ** n - 1


def encode_digits(system: str, values, n: int, signed: bool = False):
    """Integers -> digit-value matrix [N, n] (little endian).

    Binary and quaternary words are taken modulo r^n (two's complement for negative binary
    values). Balanced-ternary values must lie inside the representable range (checked).
    """
    arr = np.asarray(values)
    if arr.dtype != object:
        arr = arr.astype(np.int64)
    flat = arr.reshape(-1)
    N = flat.shape[0]
    out = np.zeros((N, n), dtype=np.int8)
    if system == "t":
        lo, hi = word_range("t", n)
        if N and (flat.min() < lo or flat.max() > hi):
            raise ValueError("value outside balanced-ternary range")
        v = flat.copy()
        for i in range(n):
            d = ((v + 1) % 3) - 1
            out[:, i] = d.astype(np.int8)
            v = (v - d) // 3
        return out
    r = RADIX[system]
    v = flat % (r ** n)
    for i in range(n):
        out[:, i] = (v % r).astype(np.int8)
        v = v // r
    return out


def decode_digits(system: str, digits, signed: bool = False):
    """Digit-value matrix [N, n] -> integers (int64, or object when the range needs it)."""
    d = np.asarray(digits)
    n = d.shape[1]
    r = RADIX[system]
    big = r ** n >= 2 ** 62
    acc = np.zeros(d.shape[0], dtype=object if big else np.int64)
    for i in range(n - 1, -1, -1):
        col = d[:, i].astype(object) if big else d[:, i].astype(np.int64)
        acc = acc * r + col
    if signed and system == "b":
        half = 2 ** (n - 1)
        acc = np.where(acc >= half, acc - 2 ** n, acc)
    return acc


def balanced_split(v: int) -> Tuple[int, int]:
    """v = s + 3 c with s, c in {-1, 0, 1} (valid for |v| <= 4; |v| <= 3 used here)."""
    s = ((v + 1) % 3) - 1
    return s, (v - s) // 3


# --------------------------------------------------------------------------------------
# cell golden functions
# --------------------------------------------------------------------------------------
# name -> (system, n_in, n_out, function(*values) -> tuple of values)
CellFn = Callable[..., Tuple[int, ...]]
CELLS: Dict[str, Tuple[str, int, int, CellFn]] = {}


def _reg(name: str, system: str, n_in: int, n_out: int):
    def deco(fn):
        CELLS[name] = (system, n_in, n_out, fn)
        return fn
    return deco


# ---- binary ----
@_reg("NOT", "b", 1, 1)
def _not(a): return (1 - a,)
@_reg("NAND2", "b", 2, 1)
def _nand(a, b): return (1 - (a & b),)
@_reg("NOR2", "b", 2, 1)
def _nor(a, b): return (1 - (a | b),)
@_reg("AND2", "b", 2, 1)
def _and(a, b): return (a & b,)
@_reg("OR2", "b", 2, 1)
def _or(a, b): return (a | b,)
@_reg("XOR2", "b", 2, 1)
def _xor(a, b): return (a ^ b,)
@_reg("MUX2", "b", 3, 1)
def _mux2(s, d0, d1): return (d1 if s else d0,)
@_reg("DFF", "b", 1, 1)
def _dff(d): return (d,)
@_reg("HA", "b", 2, 2)
def _ha(a, b): return (a ^ b, a & b)
@_reg("FA", "b", 3, 2)
def _fa(a, b, c):
    t = a + b + c
    return (t & 1, t >> 1)


# ---- balanced ternary ----
@_reg("STI", "t", 1, 1)
def _sti(a): return (-a,)
@_reg("NTI", "t", 1, 1)
def _nti(a): return (1 if a == -1 else -1,)
@_reg("PTI", "t", 1, 1)
def _pti(a): return (1 if a <= 0 else -1,)
@_reg("TMIN", "t", 2, 1)
def _tmin(a, b): return (min(a, b),)
@_reg("TMAX", "t", 2, 1)
def _tmax(a, b): return (max(a, b),)
@_reg("TCONS", "t", 2, 1)
def _tcons(a, b): return (a if a == b else 0,)
@_reg("ZSEL", "t", 2, 1)
def _zsel(t, r): return (t if t != 0 else r,)
@_reg("TCMP", "t", 2, 1)
def _tcmp(a, b): return ((a > b) - (a < b),)
@_reg("THA", "t", 2, 2)
def _tha(a, b): return balanced_split(a + b)
@_reg("TFA", "t", 3, 2)
def _tfa(a, b, c): return balanced_split(a + b + c)
@_reg("TMUL", "t", 2, 1)
def _tmul(a, b): return (a * b,)
@_reg("TMUX3", "t", 4, 1)
def _tmux3(s, dn, dz, dp): return ((dn, dz, dp)[s + 1],)
@_reg("TREG", "t", 1, 1)
def _treg(d): return (d,)


# ---- quaternary ----
@_reg("QMIN", "q", 2, 1)
def _qmin(a, b): return (min(a, b),)
@_reg("QMAX", "q", 2, 1)
def _qmax(a, b): return (max(a, b),)
@_reg("QSUCC", "q", 1, 1)
def _qsucc(a): return ((a + 1) % 4,)
@_reg("QHA", "q", 2, 2)
def _qha(a, b):
    t = a + b
    return (t % 4, t // 4)
@_reg("QFA", "q", 3, 2)
def _qfa(a, b, c):
    t = a + b + c
    return (t % 4, t // 4)
@_reg("QMUL", "q", 2, 2)
def _qmul(a, b):
    t = a * b
    return (t % 4, t // 4)
@_reg("QMUX2", "q", 3, 1)
def _qmux2(s, d0, d1): return (d1 if s >= 1 else d0,)
@_reg("QREG", "q", 1, 1)
def _qreg(d): return (d,)


def table_rows(name: str):
    """Enumerate the full truth table of a golden cell as [(inputs, outputs)] in value domain.

    Order matches the code-domain row index sum(code_i * r^i) used by the simulator.
    """
    system, n_in, n_out, fn = CELLS[name]
    r = RADIX[system]
    lv = levels(system)
    rows = []
    for idx in range(r ** n_in):
        codes = [(idx // r ** i) % r for i in range(n_in)]
        vals = [from_code(system, c) for c in codes]
        rows.append((vals, list(fn(*vals))))
    return rows
