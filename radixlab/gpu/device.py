"""Multi-SM GPU Device Architecture (GPU-B, GPU-T, GPU-BT, GPU-Q-1b, GPU-Q-2b).

Template: Scalable SM array (e.g. 4 SM x 8 lanes = 32 lanes), global memory,
warp dispatch, and total area/energy aggregation (docs/hypotheses.md section 0.1).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .. import cells, golden
from ..isa import Assembler, Instruction
from .sm import StreamingMultiprocessor


class Device:
    """Multi-SM GPU Device representing one of the 5 architectural designs."""

    def __init__(
        self,
        design: str,
        n_sm: int = 4,
        n_lanes_per_sm: int = 8,
        word_width: int = 16,
        global_mem_size: int = 2048,
        shared_mem_per_sm: int = 256,
    ):
        self.design = design
        self.n_sm = n_sm
        self.n_lanes_per_sm = n_lanes_per_sm
        self.total_lanes = n_sm * n_lanes_per_sm
        self.word_width = word_width
        self.global_mem_size = global_mem_size

        # Resolve system and macro library
        # GPU-B: binary logic, sram_b
        # GPU-T: ternary logic, mlc_t
        # GPU-BT: binary cells (control), sram_bt (2 bits/trit)
        # GPU-Q-1b: quaternary logic, sram_q_1b (1 bit/cell)
        # GPU-Q-2b: quaternary logic, mlc_q_2b (2 bit/cell)
        if design == "GPU-B":
            self.system = "b"
            self.macro_name = "sram_b"
        elif design == "GPU-T":
            self.system = "t"
            self.macro_name = "mlc_t"
        elif design == "GPU-BT":
            self.system = "b"  # binary hardware
            self.macro_name = "sram_bt"
        elif design == "GPU-Q-1b":
            self.system = "q"
            self.macro_name = "sram_q_1b"
        elif design == "GPU-Q-2b":
            self.system = "q"
            self.macro_name = "mlc_q_2b"
        else:
            raise ValueError(f"Unknown design '{design}'")

        # Instantiate SMs
        # For GPU-BT, SM uses binary cell library but with word width sized for 2 bits per trit
        effective_width = (word_width * 2) if design == "GPU-BT" else word_width
        self.effective_width = effective_width

        sys_for_sm = "b" if design in ("GPU-B", "GPU-BT") else ("t" if design == "GPU-T" else "b")
        self.sms: List[StreamingMultiprocessor] = [
            StreamingMultiprocessor(
                system=sys_for_sm,
                n_lanes=n_lanes_per_sm,
                word_width=effective_width,
                shared_mem_size=shared_mem_per_sm,
            )
            for _ in range(n_sm)
        ]

        # Global Memory
        self.global_mem = np.zeros(global_mem_size, dtype=np.int64)
        self.global_mem_reads = 0
        self.global_mem_writes = 0

        # Memory macro params
        macros = cells.load_macros()
        self.macro_spec = macros.get(self.macro_name, {})

        self.assembler = Assembler("b" if design in ("GPU-B", "GPU-BT") else "t", effective_width)

    def reset(self) -> None:
        self.global_mem.fill(0)
        self.global_mem_reads = 0
        self.global_mem_writes = 0
        for sm in self.sms:
            sm.reset()

    def launch_grid(
        self,
        asm_code: str,
        grid_data: Optional[Dict[int, int]] = None,
        max_cycles: int = 5000,
    ) -> Dict[str, Any]:
        """Load data into global memory, broadcast kernel, and execute across all SMs."""
        self.reset()
        if grid_data:
            for addr, val in grid_data.items():
                if 0 <= addr < self.global_mem_size:
                    self.global_mem[addr] = val

        program = self.assembler.assemble(asm_code)

        # Distribute chunks of data from global memory to SM shared memories
        chunk_size = 64
        for sm_idx, sm in enumerate(self.sms):
            start = sm_idx * chunk_size
            end = min(start + chunk_size, self.global_mem_size)
            sm.shared_mem[: end - start] = self.global_mem[start:end]

        # Execute all SMs concurrently
        sm_cycles = []
        for sm in self.sms:
            c = sm.run(program, max_cycles=max_cycles)
            sm_cycles.append(c)

        # Writeback from SM shared memories back to global memory
        for sm_idx, sm in enumerate(self.sms):
            start = sm_idx * chunk_size
            end = min(start + chunk_size, self.global_mem_size)
            self.global_mem[start:end] = sm.shared_mem[: end - start]

        # Aggregate metrics across SMs
        total_alu_area = sum(sm.alu_summary["area_um2"] * sm.n_lanes for sm in self.sms)
        total_alu_tx = sum(sm.alu_summary["transistors"] * sm.n_lanes for sm in self.sms)
        total_rf_area = sum(sm.rf.area_um2() for sm in self.sms)

        # Global memory macro energy
        sram_r = float(self.macro_spec.get("read_energy_per_cell", {}).value or 0.5)
        sram_w = float(self.macro_spec.get("write_energy_per_cell", {}).value or 0.7)
        gmem_e = (self.global_mem_reads * sram_r + self.global_mem_writes * sram_w) * self.word_width

        total_energy = sum(sm.metrics()["total_energy_fj"] for sm in self.sms) + gmem_e
        max_c = max(sm_cycles) if sm_cycles else 0
        clock_ps = self.sms[0].metrics()["clock_cycle_ps"]
        exec_time_ns = (max_c * clock_ps) / 1000.0

        return {
            "design": self.design,
            "n_sm": self.n_sm,
            "total_lanes": self.total_lanes,
            "max_cycles": max_c,
            "clock_cycle_ps": clock_ps,
            "execution_time_ns": exec_time_ns,
            "alu_gate_area_um2": total_alu_area,
            "rf_area_um2": total_rf_area,
            "total_area_um2": total_alu_area + total_rf_area,
            "alu_transistors": total_alu_tx,
            "total_energy_fj": total_energy,
            "throughput_gops": (self.total_lanes * max_c) / (exec_time_ns + 1e-9) if exec_time_ns > 0 else 0.0,
        }
