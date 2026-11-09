"""GPU Register File model (dual-read, single-write, multi-lane).

Memory arrays are modeled as parametric macros (macro: true) with explicit tracking
of area, read/write energy, and leakage (see docs/methodology.md section 5).
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np

from .. import cells, golden


class RegisterFile:
    """Parametric Register File array for an N-lane warp."""

    def __init__(
        self,
        system: str,
        n_lanes: int,
        n_regs: int = 16,
        word_width: int = 16,
        macro_name: Optional[str] = None,
    ):
        self.system = system
        self.n_lanes = n_lanes
        self.n_regs = n_regs
        self.word_width = word_width
        self.is_macro = True  # explicitly flagged

        # Storage: [n_lanes, n_regs] integer values
        self.storage = np.zeros((n_lanes, n_regs), dtype=np.int64)

        # Macro record for energy and area accounting
        m_name = macro_name or ("sram_b" if system == "b" else "mlc_t")
        macros = cells.load_macros()
        self.macro_spec = macros.get(m_name, {})

        self.total_reads = 0
        self.total_writes = 0

    def reset(self) -> None:
        self.storage.fill(0)
        self.total_reads = 0
        self.total_writes = 0

    def read(self, reg_idx: int) -> np.ndarray:
        """Read value of `reg_idx` across all lanes. R0 is hardwired to 0."""
        self.total_reads += self.n_lanes
        if reg_idx == 0:
            return np.zeros(self.n_lanes, dtype=np.int64)
        return self.storage[:, reg_idx].copy()

    def write(self, reg_idx: int, values: np.ndarray, mask: Optional[np.ndarray] = None) -> None:
        """Write `values` to `reg_idx` for active lanes specified by `mask`."""
        if reg_idx == 0:
            return  # R0 is read-only zero
        active_mask = mask if mask is not None else np.ones(self.n_lanes, dtype=bool)
        self.total_writes += int(np.sum(active_mask))
        self.storage[active_mask, reg_idx] = values[active_mask]

    def energy_fj(self) -> float:
        """Estimate dynamic read/write energy from macro parameters."""
        r_cost = float(self.macro_spec.get("read_energy_per_cell", {}).value or 0.5)
        w_cost = float(self.macro_spec.get("write_energy_per_cell", {}).value or 0.7)
        # Total energy = (reads * r_cost + writes * w_cost) * word_width
        return (self.total_reads * r_cost + self.total_writes * w_cost) * self.word_width

    def area_um2(self) -> float:
        a_cell = float(self.macro_spec.get("area_per_cell", {}).value or 0.6)
        total_cells = self.n_lanes * self.n_regs * self.word_width
        return total_cells * a_cell
