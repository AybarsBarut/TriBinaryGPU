"""Unified ISA definition and assembler for TriBinary GPU architectures.

Unified instruction set supported across all radices:
  Arithmetic:
    ADD  rd, rs1, rs2     ; rd = rs1 + rs2
    SUB  rd, rs1, rs2     ; rd = rs1 - rs2
    NEG  rd, rs1          ; rd = -rs1
    MUL  rd, rs1, rs2     ; rd = rs1 * rs2 (truncated to word width)
    MAC  rd, rs1, rs2     ; rd = rd + (rs1 * rs2)
  Logic / Relational:
    CMP  rd, rs1, rs2     ; rd = sign(rs1 - rs2)  {-1, 0, +1} in ternary, {-1(neg), 0, +1} in binary
    MIN  rd, rs1, rs2     ; rd = min(rs1, rs2)  (bitwise AND in binary, TMIN in ternary)
    MAX  rd, rs1, rs2     ; rd = max(rs1, rs2)  (bitwise OR in binary, TMAX in ternary)
    XOR  rd, rs1, rs2     ; bitwise XOR in binary; consensus / diff in ternary
  Data Movement & Shifts:
    MOV  rd, rs1          ; rd = rs1
    LI   rd, imm          ; rd = immediate value
    SHL  rd, rs1          ; rd = rs1 * radix (shift left 1 digit)
    SHR  rd, rs1          ; rd = rs1 // radix (shift right 1 digit)
  Memory & Control:
    LD   rd, [rs1 + imm]  ; load from memory
    ST   [rs1 + imm], rs2 ; store to memory
    BEQ  rs1, rs2, offset ; branch if equal
    BLT  rs1, rs2, offset ; branch if rs1 < rs2
    BRA  offset           ; unconditional branch
    NOP                   ; no operation
    HALT                  ; terminate execution

Machine code layout (32-bit equivalent, fixed 4-field structure):
  [opcode: 5 bits / 3 trits] [rd: 5 bits / 3 trits] [rs1: 5 bits / 3 trits] [rs2_or_imm: 17 bits / 11 trits]
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import numpy as np

from . import golden

OPCODES = {
    "NOP": 0,
    "ADD": 1,
    "SUB": 2,
    "NEG": 3,
    "MUL": 4,
    "MAC": 5,
    "CMP": 6,
    "MIN": 7,
    "MAX": 8,
    "XOR": 9,
    "SHL": 10,
    "SHR": 11,
    "MOV": 12,
    "LI": 13,
    "LD": 14,
    "ST": 15,
    "BEQ": 16,
    "BLT": 17,
    "BRA": 18,
    "HALT": 31,
}

OPCODE_REV = {v: k for k, v in OPCODES.items()}


@dataclass
class Instruction:
    op: str
    rd: int = 0
    rs1: int = 0
    rs2: int = 0
    imm: int = 0
    label: Optional[str] = None


class Assembler:
    """Assembles unified assembly text into instruction words and memory images."""

    def __init__(self, system: str, word_width: int):
        self.system = system
        self.word_width = word_width
        self.r = golden.RADIX[system]

    @staticmethod
    def _parse_reg(token: str) -> int:
        token = token.strip().upper()
        if not token.startswith("R"):
            raise ValueError(f"Invalid register name '{token}', expected R0..R31")
        return int(token[1:])

    def assemble(self, asm_text: str) -> List[Instruction]:
        lines = asm_text.strip().splitlines()
        labels: Dict[str, int] = {}
        parsed: List[Tuple[Optional[str], Optional[Instruction]]] = []

        # Pass 1: parse labels and instructions
        for line_no, raw_line in enumerate(lines):
            line = raw_line.split(";", 1)[0].split("#", 1)[0].strip()
            if not line:
                continue

            lbl = None
            if ":" in line:
                parts = line.split(":", 1)
                lbl = parts[0].strip()
                line = parts[1].strip()
                labels[lbl] = len(parsed)

            if not line:
                continue

            # Normalize spaces inside memory brackets: e.g. [R1 + 32] -> [R1+32]
            line = re.sub(r"\[\s*([^]]*?)\s*\]", lambda m: "[" + "".join(m.group(1).split()) + "]", line)

            tokens = [t.strip() for t in re.split(r"[,\s]+", line) if t.strip()]
            op = tokens[0].upper()
            if op not in OPCODES:
                raise ValueError(f"Unknown opcode '{op}' at line {line_no}: {raw_line}")

            inst = Instruction(op=op)
            if op in ("NOP", "HALT"):
                pass
            elif op == "LI":
                inst.rd = self._parse_reg(tokens[1])
                inst.imm = int(tokens[2])
            elif op in ("MOV", "NEG", "SHL", "SHR"):
                inst.rd = self._parse_reg(tokens[1])
                inst.rs1 = self._parse_reg(tokens[2])
            elif op in ("ADD", "SUB", "MUL", "MAC", "CMP", "MIN", "MAX", "XOR"):
                inst.rd = self._parse_reg(tokens[1])
                inst.rs1 = self._parse_reg(tokens[2])
                inst.rs2 = self._parse_reg(tokens[3])
            elif op in ("BEQ", "BLT"):
                inst.rs1 = self._parse_reg(tokens[1])
                inst.rs2 = self._parse_reg(tokens[2])
                inst.label = tokens[3]
            elif op == "BRA":
                inst.label = tokens[1]
            elif op == "LD":
                # LD rd, [rs1 + imm]
                inst.rd = self._parse_reg(tokens[1])
                mem_part = "".join(tokens[2:]).strip("[]")
                mem_toks = mem_part.split("+")
                inst.rs1 = self._parse_reg(mem_toks[0])
                inst.imm = int(mem_toks[1]) if len(mem_toks) > 1 else 0
            elif op == "ST":
                # ST [rs1 + imm], rs2
                mem_part = tokens[1].strip("[]")
                mem_toks = mem_part.split("+")
                inst.rs1 = self._parse_reg(mem_toks[0])
                inst.imm = int(mem_toks[1]) if len(mem_toks) > 1 else 0
                inst.rs2 = self._parse_reg(tokens[2])
            else:
                raise ValueError(f"Unhandled instruction format: {line}")

            parsed.append((lbl, inst))

        # Pass 2: resolve label offsets
        instructions = []
        for pc, (lbl, inst) in enumerate(parsed):
            if inst.label:
                if inst.label not in labels:
                    raise ValueError(f"Undefined label '{inst.label}'")
                target_pc = labels[inst.label]
                inst.imm = target_pc - pc  # Relative offset
            instructions.append(inst)

        return instructions
