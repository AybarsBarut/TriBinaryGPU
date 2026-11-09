"""Cell library loader, assumption-record validation and parameter resolution.

Implements the rules of docs/assumptions.md: every numeric parameter is a record with value, unit,
source_type, source and confidence. Short forms in YAML expand from the library `defaults`.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import yaml

from . import golden
from .paths import cells_dir

CONFIDENCE = ("low", "medium", "high")
SOURCE_TYPES = ("measured", "published", "derived", "estimate", "guess", "design")
TECH_PARAMS = ("tau", "area_per_transistor", "energy_per_transistor", "leakage_per_transistor", "maturity_factor")

try:  # pragma: no cover
    _Loader = yaml.CSafeLoader
except AttributeError:  # pragma: no cover
    _Loader = yaml.SafeLoader


class AssumptionError(ValueError):
    pass


@dataclass(frozen=True)
class Param:
    id: str
    value: Any                      # float, or list of floats (per-output delay stages)
    unit: str
    source_type: str
    source: str
    confidence: str
    group: Optional[str] = None
    range: Optional[Tuple[float, float]] = None
    notes: str = ""

    @property
    def fixed(self) -> bool:
        """True if the sensitivity range was narrowed to a single value (structural fact)."""
        return self.range is not None and self.range[0] == self.range[1]


def make_param(pid: str, raw: Mapping[str, Any], status: str = "reviewed") -> Param:
    for key in ("value", "unit", "source_type", "source", "confidence"):
        if key not in raw:
            raise AssumptionError(f"{pid}: missing required field '{key}'")
    if raw["confidence"] not in CONFIDENCE:
        raise AssumptionError(f"{pid}: confidence must be one of {CONFIDENCE}")
    if raw["source_type"] not in SOURCE_TYPES:
        raise AssumptionError(f"{pid}: source_type must be one of {SOURCE_TYPES}")
    src = str(raw["source"]).strip()
    if not src:
        raise AssumptionError(f"{pid}: empty source")
    if src.upper().startswith("TODO") and status != "draft":
        raise AssumptionError(f"{pid}: TODO source is only allowed in status: draft")
    if raw["source_type"] == "published" and raw["confidence"] == "low":
        raise AssumptionError(f"{pid}: a 'published' value cannot be low confidence; use estimate or guess")
    rng = None
    if "range" in raw and raw["range"] is not None:
        rng = (float(raw["range"]["min"]), float(raw["range"]["max"]))
        if not str(raw.get("notes", "")).strip():
            raise AssumptionError(f"{pid}: a range override requires an explanation in notes")
    return Param(
        id=pid,
        value=raw["value"],
        unit=str(raw["unit"]),
        source_type=raw["source_type"],
        source=src,
        confidence=raw["confidence"],
        group=raw.get("group"),
        range=rng,
        notes=str(raw.get("notes", "")),
    )


@dataclass
class CellDef:
    name: str
    description: str
    inputs: List[str]
    outputs: List[str]
    sequential: bool
    macro: bool
    function: str
    tables: List[List[int]]         # code domain, one list per output, indexed by sum(code_i * radix^i)
    transistors: Param
    delay_stages: Param
    notes: str = ""

    @property
    def n_in(self) -> int:
        return len(self.inputs)

    @property
    def n_out(self) -> int:
        return len(self.outputs)


@dataclass
class Resolved:
    """Numeric parameters of a library after scaling, indexed like Library.order."""
    transistors: List[float]
    area: List[float]               # um2
    energy: List[float]             # fJ per output toggle event of the cell
    leakage: List[float]            # nW
    delay: List[List[float]]        # ps per output
    maturity: float


@dataclass
class Library:
    name: str
    system: str
    radix: int
    levels: List[int]
    status: str
    version: str
    tech: Dict[str, Param]
    voltage_swing: Param
    cells: Dict[str, CellDef]
    order: List[str]
    sha256: str
    source_path: str = ""

    @property
    def noise_margin_fraction(self) -> float:
        """Default half-margin as a fraction of the swing: 1 / (2 (L - 1))."""
        return 1.0 / (2.0 * (self.radix - 1))

    def all_params(self) -> List[Param]:
        ps = list(self.tech.values())
        for c in self.cells.values():
            ps.append(c.transistors)
            ps.append(c.delay_stages)
        return ps

    def resolve(self, scale: Optional[Mapping[str, float]] = None) -> Resolved:
        """Evaluate area / energy / leakage / delay with optional multiplicative parameter scaling.

        `scale` maps a parameter id to a factor. Derived values follow docs/assumptions.md section 2.
        """
        sc = scale or {}

        def v(p: Param):
            f = sc.get(p.id, 1.0)
            if isinstance(p.value, list):
                return [x * f for x in p.value]
            return p.value * f

        tau = v(self.tech["tau"])
        a_t = v(self.tech["area_per_transistor"])
        e_t = v(self.tech["energy_per_transistor"])
        l_t = v(self.tech["leakage_per_transistor"])
        m = v(self.tech["maturity_factor"])
        T, A, E, L, D = [], [], [], [], []
        for name in self.order:
            c = self.cells[name]
            t = v(c.transistors)
            T.append(t)
            A.append(t * a_t * m)
            E.append(t * e_t * m)
            L.append(t * l_t * m)
            D.append([s * tau * m for s in v(c.delay_stages)])
        return Resolved(T, A, E, L, D, m)

    def engine_types(self) -> List[dict]:
        out = []
        for name in self.order:
            c = self.cells[name]
            out.append({
                "name": c.name, "n_in": c.n_in, "n_out": c.n_out,
                "sequential": c.sequential, "tables": c.tables,
            })
        return out


def _expand(default: Mapping[str, Any], raw: Any) -> Dict[str, Any]:
    d = dict(default)
    if isinstance(raw, Mapping):
        d.update(raw)
    else:
        d["value"] = raw
    return d


def load_library(path_or_name) -> Library:
    p = Path(path_or_name)
    if not p.exists():
        p = cells_dir() / f"{path_or_name}.yaml"
    text = p.read_bytes().replace(b"\r\n", b"\n")
    data = yaml.load(text.decode("utf-8"), Loader=_Loader)
    name = data["library"]
    status = data.get("status", "draft")
    system = data["system"]
    radix = int(data["radix"])
    if golden.RADIX[system] != radix:
        raise AssumptionError(f"{name}: radix {radix} does not match system {system}")
    tech = {}
    for key in TECH_PARAMS:
        if key not in data["technology"]:
            raise AssumptionError(f"{name}: technology.{key} missing")
        tech[key] = make_param(f"{name}.{key}", data["technology"][key], status)
    swing = make_param(f"{name}.voltage_swing", data["voltage_swing"], status)
    defaults = data["defaults"]
    cells: Dict[str, CellDef] = {}
    order: List[str] = []
    for raw in data["cells"]:
        cname = raw["name"]
        if cname in cells:
            raise AssumptionError(f"{name}: duplicate cell {cname}")
        n_in = len(raw["inputs"])
        n_out = len(raw["outputs"])
        rows = raw["truth_table"]
        if len(rows) != radix ** n_in:
            raise AssumptionError(f"{name}.{cname}: truth table needs {radix ** n_in} rows, has {len(rows)}")
        tables = [[0] * len(rows) for _ in range(n_out)]
        seen = set()
        for row in rows:
            ins, outs = row["in"], row["out"]
            if len(ins) != n_in or len(outs) != n_out:
                raise AssumptionError(f"{name}.{cname}: malformed truth-table row {row}")
            idx = sum(int(golden.to_code(system, v)) * radix ** i for i, v in enumerate(ins))
            if idx in seen or not 0 <= idx < len(rows):
                raise AssumptionError(f"{name}.{cname}: duplicate or invalid row {row}")
            seen.add(idx)
            for o, ov in enumerate(outs):
                code = int(golden.to_code(system, ov))
                if not 0 <= code < radix:
                    raise AssumptionError(f"{name}.{cname}: output value {ov} outside the logic levels")
                tables[o][idx] = code
        t_raw = _expand(defaults["transistors"], raw["transistors"])
        d_raw = _expand(defaults["delay_stages"], raw["delay_stages"])
        if not isinstance(d_raw["value"], list) or len(d_raw["value"]) != n_out:
            raise AssumptionError(f"{name}.{cname}: delay_stages needs one value per output")
        cells[cname] = CellDef(
            name=cname,
            description=raw.get("description", ""),
            inputs=list(raw["inputs"]),
            outputs=list(raw["outputs"]),
            sequential=bool(raw.get("sequential", False)),
            macro=bool(raw.get("macro", False)),
            function=raw.get("function", ""),
            tables=tables,
            transistors=make_param(f"{name}.{cname}.transistors", t_raw, status),
            delay_stages=make_param(f"{name}.{cname}.delay_stages", d_raw, status),
            notes=raw.get("notes", ""),
        )
        order.append(cname)
    return Library(
        name=name, system=system, radix=radix, levels=list(data["levels"]), status=status,
        version=str(data.get("version", "0")), tech=tech, voltage_swing=swing, cells=cells,
        order=order, sha256=hashlib.sha256(text).hexdigest(), source_path=str(p),
    )


def check_against_golden(lib: Library) -> List[str]:
    """L0 verification: compare every YAML truth table with its golden function. Returns problems."""
    problems: List[str] = []
    for name in lib.order:
        c = lib.cells[name]
        if name not in golden.CELLS:
            problems.append(f"{name}: no golden function registered")
            continue
        system, n_in, n_out, _ = golden.CELLS[name]
        if system != lib.system or n_in != c.n_in or n_out != c.n_out:
            problems.append(f"{name}: arity or system mismatch with golden model")
            continue
        for idx, (ins, outs) in enumerate(golden.table_rows(name)):
            for o in range(n_out):
                want = int(golden.to_code(lib.system, outs[o]))
                got = c.tables[o][idx]
                if want != got:
                    problems.append(f"{name}: row {ins} output {o}: yaml code {got}, golden code {want}")
    return problems


def load_all() -> Dict[str, Library]:
    return {n: load_library(n) for n in ("binary", "ternary", "quaternary")}


def load_macros(path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """Load memory macro records with every numeric field expanded into a validated Param."""
    p = path or (cells_dir() / "memory_macros.yaml")
    data = yaml.load(Path(p).read_bytes().decode("utf-8"), Loader=_Loader)
    defaults = data["defaults"]
    out: Dict[str, Dict[str, Any]] = {}
    for m in data["macros"]:
        if m.get("macro") is not True:
            raise AssumptionError(f"macro {m.get('name')}: macro: true flag is mandatory")
        rec: Dict[str, Any] = {"name": m["name"], "bits_per_cell": m["bits_per_cell"]}
        for key, d in defaults.items():
            rec[key] = make_param(f"memory_macros.{m['name']}.{key}", _expand(d, m[key]), data.get("status", "draft"))
        out[m["name"]] = rec
    return out
