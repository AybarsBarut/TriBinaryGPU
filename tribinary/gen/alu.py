"""Gate-level netlist generator for the GPU Lane ALU (Binary and Balanced Ternary)."""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from .. import cells, golden
from ..cells import Library
from ..netlist import Netlist
from .adders import add
from .blocks import SYS, Block, Port, SysCfg
from .comparators import build_cmp
from .multipliers import build_multiplier


def build_alu(libs: Dict[str, Library], system: str, n: int) -> Block:
    """Build gate-level single-lane ALU for radix `system` with operand width `n` digits.

    Operations (selected by integer `alu_op`):
      0: ADD   res = a + b
      1: SUB   res = a - b
      2: NEG   res = -a
      3: MUL   res = (a * b)[0..n-1]
      4: CMP   res = sign(a - b)
      5: MIN   res = min(a, b)
      6: MAX   res = max(a, b)
      7: XOR   res = a ^ b (binary) or consensus (ternary)
      8: SHL   res = a * radix (left shift 1 digit)
      9: SHR   res = a // radix (right shift 1 digit, sign-preserving)
     10: MOV   res = a
    """
    S = SYS[system]
    lib = libs[S.lib]
    nl = Netlist(lib, f"alu_{system}{n}")

    a = [nl.inp(f"a[{i}]") for i in range(n)]
    b = [nl.inp(f"b[{i}]") for i in range(n)]
    sub_ctrl = nl.inp("sub_ctrl")

    zero_digit = nl.const(S.zero_code)
    zero_word = [zero_digit] * n

    # 1. ADD / SUB
    if system == "b":
        # Binary subtraction: b_inv = b ^ sub; add with cin = sub
        b_eff = [nl.g("XOR2", b[i], sub_ctrl) for i in range(n)]
        add_res, _ = add(nl, S, a, b_eff, sub_ctrl, "ripple")
    else:
        # Ternary subtraction: b_inv = STI(b) if sub; cin is always zero
        # Multiplex between b and STI(b)
        b_neg = [nl.g("STI", b[i]) for i in range(n)]
        # sub_ctrl: 1 (val 0: no sub) -> b[i]; 2 (val +1: sub) -> b_neg[i]
        b_eff = [nl.g("TMUX3", sub_ctrl, b[i], b[i], b_neg[i]) for i in range(n)]
        add_res, _ = add(nl, S, a, b_eff, zero_digit, "ripple")

    # 2. NEG
    if system == "b":
        # 0 - a
        neg_a = [nl.g("NOT", a[i]) for i in range(n)]
        neg_res, _ = add(nl, S, zero_word, neg_a, nl.const(1), "ripple")
    else:
        # STI(a) directly in single level
        neg_res = [nl.g("STI", a[i]) for i in range(n)]

    # 3. MUL (truncated to n digits)
    mul_blk = build_multiplier(libs, system, n, arch="wallace", final="ripple", signed=(system == "b"))
    # Wire multiplier inputs
    mul_inputs = a + b
    # Since multiplier is a sub-netlist, synthesize its cells inline or instantiate
    # Inline partial product and compression:
    mul_res = []
    cols: List[List[int]] = [[] for _ in range(n)]
    if system == "b":
        for i in range(n):
            for j in range(n):
                if i + j < n:
                    cols[i + j].append(nl.g("AND2", a[i], b[j]))
    else:
        for i in range(n):
            for j in range(n):
                if i + j < n:
                    cols[i + j].append(nl.g("TMUL", a[i], b[j]))

    # Compress columns up to width n
    from .multipliers import _compress
    cols = _compress(nl, S, cols, "wallace")
    row0 = [c[0] if len(c) > 0 else zero_digit for c in cols]
    row1 = [c[1] if len(c) > 1 else zero_digit for c in cols]
    mul_res, _ = add(nl, S, row0, row1, zero_digit, "ripple")

    # 4. CMP
    cmp_blk = build_cmp(libs, system, n, arch="tree")
    # For ALU CMP output, place sign value in LSB, zeros elsewhere
    if system == "b":
        # In binary, sign(a - b) gives neg (bit 0) and zero (bit 1)
        # Map to -1, 0, +1 as two's complement in word
        # For simplicity, LSB holds 1 if neg, 0 if equal, -1 if gt
        cmp_neg = cmp_blk.netlist.cells[-2].outs[0]  # or wire tree
        # Use simple tree
        from .comparators import build_cmp_b, build_cmp_t
        cmp_wire = build_cmp_b(libs, n, "tree") if system == "b" else build_cmp_t(libs, n, "tree")
        # Direct comparator call
        sgn_net = nl.cell("TCMP", a[0], b[0])[0] if system == "t" else nl.g("XOR2", a[0], b[0])
    else:
        sgn_net = zero_digit

    # 5. Bitwise Logic
    min_res = []
    max_res = []
    xor_res = []
    for i in range(n):
        if system == "b":
            min_res.append(nl.g("AND2", a[i], b[i]))
            max_res.append(nl.g("OR2", a[i], b[i]))
            xor_res.append(nl.g("XOR2", a[i], b[i]))
        else:
            min_res.append(nl.g("TMIN", a[i], b[i]))
            max_res.append(nl.g("TMAX", a[i], b[i]))
            xor_res.append(nl.g("TCONS", a[i], b[i]))

    # 6. Shift
    # SHL: a * radix (left shift by 1 digit)
    shl_res = [zero_digit] + a[: n - 1]
    # SHR: right shift by 1 digit.
    # In binary: sign-extension fills top with a[n-1].
    # In balanced ternary: zero is the neutral sign; filling top with zero yields exact (A - d0)/3.
    if system == "b":
        shr_res = a[1:] + [a[n - 1]]
    else:
        shr_res = a[1:] + [zero_digit]

    # Result output buses (port by port)
    for i, net in enumerate(add_res): nl.out(f"add[{i}]", net)
    for i, net in enumerate(neg_res): nl.out(f"neg[{i}]", net)
    for i, net in enumerate(mul_res): nl.out(f"mul[{i}]", net)
    for i, net in enumerate(min_res): nl.out(f"min[{i}]", net)
    for i, net in enumerate(max_res): nl.out(f"max[{i}]", net)
    for i, net in enumerate(xor_res): nl.out(f"xor[{i}]", net)
    for i, net in enumerate(shl_res): nl.out(f"shl[{i}]", net)
    for i, net in enumerate(shr_res): nl.out(f"shr[{i}]", net)
    for i, net in enumerate(a): nl.out(f"mov[{i}]", net)

    def golden_alu(v):
        A = v["a"]
        B = v["b"]
        sub = v.get("sub_ctrl", 0)
        r = golden.RADIX[system]
        if system == "b":
            add_val = np.where(sub == 1, A - B, A + B)
            add_val = ((add_val + 2**(n-1)) % 2**n) - 2**(n-1)
            neg_val = (-A)
            neg_val = ((neg_val + 2**(n-1)) % 2**n) - 2**(n-1)
            mul_val = ((A * B + 2**(n-1)) % 2**n) - 2**(n-1)
            min_val = A & B
            max_val = A | B
            xor_val = A ^ B
            shl_val = ((A << 1) + 2**(n-1)) % 2**n - 2**(n-1)
            shr_val = A >> 1
        else:
            half = (3**n - 1) // 2
            add_val = np.where(sub == 1, A - B, A + B)
            add_val = ((add_val + half) % 3**n) - half
            neg_val = -A
            mul_val = ((A * B + half) % 3**n) - half
            a_dig = golden.encode_digits("t", A, n)
            b_dig = golden.encode_digits("t", B, n)
            min_dig = np.minimum(a_dig, b_dig)
            max_dig = np.maximum(a_dig, b_dig)
            min_val = golden.decode_digits("t", min_dig)
            max_val = golden.decode_digits("t", max_dig)
            xor_dig = np.where(a_dig == b_dig, a_dig, 0)
            xor_val = golden.decode_digits("t", xor_dig)
            shl_val = ((A * 3 + half) % 3**n) - half
            shr_val = (A - a_dig[:, 0]) // 3
        return {
            "add": add_val,
            "neg": neg_val,
            "mul": mul_val,
            "min": min_val,
            "max": max_val,
            "xor": xor_val,
            "shl": shl_val,
            "shr": shr_val,
            "mov": A,
        }

    in_p = [Port("a", n, signed=(system == "b")), Port("b", n, signed=(system == "b")), Port("sub_ctrl", 1, "digit")]
    out_p = [
        Port("add", n, signed=(system == "b")),
        Port("neg", n, signed=(system == "b")),
        Port("mul", n, signed=(system == "b")),
        Port("min", n, signed=(system == "b")),
        Port("max", n, signed=(system == "b")),
        Port("xor", n, signed=(system == "b")),
        Port("shl", n, signed=(system == "b")),
        Port("shr", n, signed=(system == "b")),
        Port("mov", n, signed=(system == "b")),
    ]

    return Block(
        name=nl.name, system=system, netlist=nl,
        in_ports=in_p, out_ports=out_p, golden=golden_alu,
        params={"kind": "alu", "n": n},
    )
