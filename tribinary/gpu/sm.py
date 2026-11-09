"""Single-SM Mini-GPU execution engine (SIMT warp lanes, gate-level ALUs, macro storage)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .. import cells, golden
from ..cells import Library, Resolved
from ..gen.alu import build_alu
from ..isa import Instruction
from .regfile import RegisterFile


class StreamingMultiprocessor:
    """Single-SM SIMT execution core executing unified ISA programs."""

    def __init__(
        self,
        system: str,
        n_lanes: int = 4,
        word_width: int = 16,
        n_regs: int = 16,
        shared_mem_size: int = 128,
    ):
        self.system = system
        self.n_lanes = n_lanes
        self.word_width = word_width
        self.shared_mem_size = shared_mem_size

        self.libs = cells.load_all()
        self.res = self.libs[SYS_TO_LIB[system]].resolve()

        # Gate-level lane ALU
        self.alu_block = build_alu(self.libs, system, word_width)
        self.alu_nl = self.alu_block.netlist
        self.alu_summary = self.alu_nl.summary(self.res)

        # Storage components (flagged parametric macros)
        self.rf = RegisterFile(system, n_lanes, n_regs, word_width)
        self.shared_mem = np.zeros(shared_mem_size, dtype=np.int64)
        self.shared_mem_reads = 0
        self.shared_mem_writes = 0

        # Architectural registers
        self.pc = 0
        self.active_mask = np.ones(n_lanes, dtype=bool)
        self.halted = False
        self.cycles = 0

        # Activity & energy accounting
        self.total_alu_toggles = np.zeros(len(self.res.transistors), dtype=np.float64)

    def reset(self, initial_pc: int = 0) -> None:
        self.pc = initial_pc
        self.active_mask = np.ones(self.n_lanes, dtype=bool)
        self.halted = False
        self.cycles = 0
        self.rf.reset()
        self.shared_mem.fill(0)
        self.shared_mem_reads = 0
        self.shared_mem_writes = 0
        self.total_alu_toggles.fill(0)

        # Set lane IDs in R1: R1 = lane_id (0..n_lanes-1)
        lane_ids = np.arange(self.n_lanes, dtype=np.int64)
        self.rf.write(1, lane_ids)

    def step(self, program: List[Instruction]) -> bool:
        """Execute 1 warp instruction cycle. Returns False if halted."""
        if self.halted or self.pc >= len(program):
            self.halted = True
            return False

        inst = program[self.pc]
        op = inst.op
        self.cycles += 1

        if op == "HALT":
            self.halted = True
            return False

        if op == "NOP":
            self.pc += 1
            return True

        if op == "BRA":
            self.pc += inst.imm
            return True

        # Read register operands across active lanes
        rs1_vals = self.rf.read(inst.rs1)
        rs2_vals = self.rf.read(inst.rs2)

        # Branch instructions
        if op == "BEQ":
            cond = (rs1_vals == rs2_vals)
            # Divergence handling: branch taken if any active lane matches
            if np.any(cond & self.active_mask):
                self.pc += inst.imm
            else:
                self.pc += 1
            return True

        if op == "BLT":
            cond = (rs1_vals < rs2_vals)
            if np.any(cond & self.active_mask):
                self.pc += inst.imm
            else:
                self.pc += 1
            return True

        # Memory instructions
        if op == "LD":
            # LD rd, [rs1 + imm]
            loaded = np.zeros(self.n_lanes, dtype=np.int64)
            for lane in range(self.n_lanes):
                if self.active_mask[lane]:
                    addr = int(rs1_vals[lane] + inst.imm)
                    if 0 <= addr < self.shared_mem_size:
                        loaded[lane] = self.shared_mem[addr]
                        self.shared_mem_reads += 1
            self.rf.write(inst.rd, loaded, self.active_mask)
            self.pc += 1
            return True

        if op == "ST":
            # ST [rs1 + imm], rs2
            for lane in range(self.n_lanes):
                if self.active_mask[lane]:
                    addr = int(rs1_vals[lane] + inst.imm)
                    if 0 <= addr < self.shared_mem_size:
                        self.shared_mem[addr] = rs2_vals[lane]
                        self.shared_mem_writes += 1
            self.pc += 1
            return True

        # Arithmetic / Logic instructions executed via gate-level ALU
        if op == "LI":
            res_vals = np.full(self.n_lanes, inst.imm, dtype=np.int64)
            self.rf.write(inst.rd, res_vals, self.active_mask)
            self.pc += 1
            return True

        # Drive gate-level ALU netlist for active lanes
        n_active = int(np.sum(self.active_mask))
        if n_active > 0:
            active_a = rs1_vals[self.active_mask]
            active_b = rs2_vals[self.active_mask]
            sub_flag = 1 if op == "SUB" else 0

            # Encode operands to digit codes
            in_a_codes = golden.to_code(self.system, golden.encode_digits(self.system, active_a, self.word_width, signed=(self.system == "b")))
            in_b_codes = golden.to_code(self.system, golden.encode_digits(self.system, active_b, self.word_width, signed=(self.system == "b")))
            sub_codes = golden.to_code(self.system, np.full((n_active, 1), sub_flag, dtype=np.int64))

            alu_inputs = np.concatenate([in_a_codes, in_b_codes, sub_codes], axis=1).astype(np.uint8)

            # Evaluate ALU netlist and record switching toggles
            out_codes, toggles = self.alu_nl.simulate_activity(alu_inputs)
            self.total_alu_toggles += np.sum(toggles, axis=0)

            # Map op to ALU output port name
            port_map = {
                "ADD": "add", "SUB": "add", "NEG": "neg",
                "MUL": "mul", "MIN": "min", "MAX": "max",
                "XOR": "xor", "SHL": "shl", "SHR": "shr", "MOV": "mov",
            }
            port_name = port_map.get(op, "add")

            # Extract output digits and decode to signed integers
            p_idx = [p.name for p in self.alu_block.out_ports].index(port_name)
            port_obj = self.alu_block.out_ports[p_idx]
            col_start = p_idx * self.word_width
            res_codes = out_codes[:, col_start : col_start + self.word_width]
            res_digits = golden.from_code(self.system, res_codes)
            computed = golden.decode_digits(self.system, res_digits, signed=(self.system == "b"))

            writeback_vals = np.zeros(self.n_lanes, dtype=np.int64)
            writeback_vals[self.active_mask] = computed
            self.rf.write(inst.rd, writeback_vals, self.active_mask)

        self.pc += 1
        return True

    def run(self, program: List[Instruction], max_cycles: int = 1000) -> int:
        """Run program until completion or max_cycles."""
        while not self.halted and self.cycles < max_cycles:
            if not self.step(program):
                break
        return self.cycles

    def metrics(self) -> Dict[str, Any]:
        """Aggregate total execution metrics for this SM."""
        e_per_cell = np.array(self.res.energy)
        alu_dyn_e = float(self.total_alu_toggles @ e_per_cell)
        rf_e = self.rf.energy_fj()
        # Shared memory energy
        sram_r = float(self.rf.macro_spec.get("read_energy_per_cell", {}).value or 0.5)
        sram_w = float(self.rf.macro_spec.get("write_energy_per_cell", {}).value or 0.7)
        smem_e = (self.shared_mem_reads * sram_r + self.shared_mem_writes * sram_w) * self.word_width

        total_dyn_e = alu_dyn_e + rf_e + smem_e
        cycle_time_ps = self.alu_summary["delay_ps"] + 50.0  # ALU delay + clock setup/register overhead

        return {
            "system": self.system,
            "cycles": self.cycles,
            "clock_cycle_ps": cycle_time_ps,
            "execution_time_ns": (self.cycles * cycle_time_ps) / 1000.0,
            "alu_gate_area_um2": self.alu_summary["area_um2"] * self.n_lanes,
            "alu_transistors": self.alu_summary["transistors"] * self.n_lanes,
            "rf_area_um2": self.rf.area_um2(),
            "total_energy_fj": total_dyn_e,
            "alu_energy_fj": alu_dyn_e,
            "storage_energy_fj": rf_e + smem_e,
        }


SYS_TO_LIB = {"b": "binary", "t": "ternary", "q": "quaternary"}
