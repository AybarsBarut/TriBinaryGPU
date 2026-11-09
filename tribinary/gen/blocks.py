"""Block containers shared by the netlist generators and the verification harness."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np

from ..netlist import Netlist


@dataclass(frozen=True)
class Port:
    name: str
    n: int                  # number of digits
    kind: str = "word"      # "word": integer of n digits; "digit": a single digit value
    signed: bool = False    # binary words only: two's complement interpretation
    domain: Optional[tuple] = None  # allowed values of a digit port (None = all digit values)


@dataclass
class Block:
    """A generated circuit plus everything needed to verify it against a golden model.

    `golden` maps port name -> numpy integer array (value domain) for the input ports to a dict of
    expected output values for the output ports. Digits are laid out little endian per port, ports in
    declaration order; the netlist inputs/outputs follow the same order.
    """
    name: str
    system: str                         # value semantics: "b", "t" or "q"
    netlist: Netlist
    in_ports: List[Port]
    out_ports: List[Port]
    golden: Callable[[Dict[str, np.ndarray]], Dict[str, np.ndarray]]
    params: Dict[str, object] = field(default_factory=dict)
    encoding: str = "native"            # "native" or "bt2" (2 bits per trit on binary cells)

    def n_in_digits(self) -> int:
        return sum(p.n for p in self.in_ports)

    def n_out_digits(self) -> int:
        return sum(p.n for p in self.out_ports)

    def digit_counts(self) -> Dict[str, int]:
        return {p.name: p.n for p in self.in_ports}


class SysCfg:
    """Per-number-system cell names and constants used by the generators."""

    def __init__(self, system, radix, lib, FA, HA, MUX, zero_code, carry_codes, one_code):
        self.system = system
        self.radix = radix
        self.lib = lib
        self.FA = FA
        self.HA = HA
        self.MUX = MUX
        self.zero_code = zero_code
        self.carry_codes = carry_codes
        self.one_code = one_code


SYS = {
    "b": SysCfg("b", 2, "binary", "FA", "HA", "MUX2", 0, (0, 1), 1),
    "t": SysCfg("t", 3, "ternary", "TFA", "THA", "TMUX3", 1, (0, 1, 2), 2),
    "q": SysCfg("q", 4, "quaternary", "QFA", "QHA", "QMUX2", 0, (0, 1), 1),
}
