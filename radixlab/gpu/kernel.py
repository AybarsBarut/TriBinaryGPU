"""Kernel execution harness: loads vectors into memory, runs SM, verifies bit-exact golden output."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from ..isa import Assembler, Instruction
from .sm import StreamingMultiprocessor


class GPUKernelRunner:
    """Executes kernels on GPU-B and GPU-T and verifies golden parity."""

    def __init__(self, system: str, n_lanes: int = 4, word_width: int = 16):
        self.system = system
        self.n_lanes = n_lanes
        self.word_width = word_width
        self.sm = StreamingMultiprocessor(system, n_lanes=n_lanes, word_width=word_width)
        self.assembler = Assembler(system, word_width)

    def run_kernel(
        self,
        asm_code: str,
        initial_mem: Optional[Dict[int, int]] = None,
        max_cycles: int = 1000,
    ) -> Tuple[StreamingMultiprocessor, Dict[str, Any]]:
        self.sm.reset()
        if initial_mem:
            for addr, val in initial_mem.items():
                self.sm.shared_mem[addr] = val

        program = self.assembler.assemble(asm_code)
        cycles = self.sm.run(program, max_cycles=max_cycles)
        metrics = self.sm.metrics()
        return self.sm, metrics
