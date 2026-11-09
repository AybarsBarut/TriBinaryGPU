//! RadixLab simulator core: levelized bit-parallel evaluation, static timing,
//! event-driven timed simulation and sequential stepping for multi-valued logic.
//!
//! Host encoding (see docs/methodology.md section 5):
//! * radix 2: one bit plane, 64 test vectors per machine word;
//! * radix 3: two bit planes, codes 0,1,2 = values -1,0,+1 and code 3 = unknown X;
//! * radix 4: two bit planes, codes 0..3 = values 0..3.
//!
//! Cells are lookup tables. For radix 3 the table over the three values is extended to
//! the unknown state pessimistically: an output is known only if it is the same for every
//! substitution of the unknown inputs.

use serde::Deserialize;
use std::cmp::Reverse;
use std::collections::BinaryHeap;

#[cfg(feature = "python")]
pub mod pybind;

/// Number of 64-bit words (64 vectors each) processed per chunk.
pub const CHUNK_WORDS: usize = 16;

#[derive(Deserialize)]
struct CellTypeSpec {
    name: String,
    n_in: usize,
    n_out: usize,
    sequential: bool,
    tables: Vec<Vec<u8>>,
}

#[derive(Deserialize)]
struct CellSpec {
    t: usize,
    ins: Vec<usize>,
    outs: Vec<usize>,
}

#[derive(Deserialize)]
struct Spec {
    radix: usize,
    cell_types: Vec<CellTypeSpec>,
    n_nets: usize,
    inputs: Vec<usize>,
    outputs: Vec<usize>,
    consts: Vec<(usize, u8)>,
    cells: Vec<CellSpec>,
}

pub struct CellType {
    pub name: String,
    pub n_in: usize,
    pub n_out: usize,
    pub seq: bool,
    /// Extended table per output, indexed by sum(code_i * e^i).
    ext: Vec<Vec<u8>>,
    /// Rows where at least one output code is non-zero.
    active_rows: Vec<u32>,
}

#[derive(Clone)]
pub struct Cell {
    pub t: usize,
    pub ins: Vec<usize>,
    pub outs: Vec<usize>,
}

pub struct Engine {
    pub radix: usize,
    planes: usize,
    e: usize,
    log2e: usize,
    has_x: bool,
    pub types: Vec<CellType>,
    pub n_nets: usize,
    pub inputs: Vec<usize>,
    pub outputs: Vec<usize>,
    consts: Vec<(usize, u8)>,
    /// Combinational cells in topological order.
    pub comb: Vec<Cell>,
    /// Sequential cells (D flip-flop style): ins = [d], outs = [q].
    pub seq: Vec<Cell>,
    fanout: Vec<Vec<usize>>,
    state: Vec<u8>,
    n_lanes: usize,
}

fn pow(base: usize, exp: usize) -> usize {
    (0..exp).fold(1, |a, _| a * base)
}

impl Engine {
    pub fn from_json(json: &str) -> Result<Engine, String> {
        let spec: Spec = serde_json::from_str(json).map_err(|e| format!("bad netlist spec: {e}"))?;
        Engine::from_spec(spec)
    }

    fn from_spec(spec: Spec) -> Result<Engine, String> {
        let radix = spec.radix;
        if !(radix == 2 || radix == 3 || radix == 4) {
            return Err(format!("unsupported radix {radix}"));
        }
        let (planes, e, log2e, has_x) = match radix {
            2 => (1, 2, 1, false),
            3 => (2, 4, 2, true),
            _ => (2, 4, 2, false),
        };
        let mut types = Vec::new();
        for ct in &spec.cell_types {
            if ct.n_in == 0 || ct.n_in > 4 {
                return Err(format!("cell type {} has unsupported fan-in {}", ct.name, ct.n_in));
            }
            if ct.tables.len() != ct.n_out {
                return Err(format!("cell type {}: expected {} tables", ct.name, ct.n_out));
            }
            let nvalrows = pow(radix, ct.n_in);
            for t in &ct.tables {
                if t.len() != nvalrows {
                    return Err(format!("cell type {}: table has {} rows, expected {}", ct.name, t.len(), nvalrows));
                }
                if t.iter().any(|&c| (c as usize) >= radix) {
                    return Err(format!("cell type {}: output code out of range", ct.name));
                }
            }
            let nrows = pow(e, ct.n_in);
            let mut ext = vec![vec![0u8; nrows]; ct.n_out];
            for row in 0..nrows {
                let digits: Vec<usize> = (0..ct.n_in).map(|i| (row >> (log2e * i)) & (e - 1)).collect();
                if radix == 3 && digits.iter().any(|&d| d == 3) {
                    // pessimistic X evaluation
                    let xpos: Vec<usize> = (0..ct.n_in).filter(|&i| digits[i] == 3).collect();
                    for o in 0..ct.n_out {
                        let mut first: Option<u8> = None;
                        let mut same = true;
                        for sub in 0..pow(3, xpos.len()) {
                            let mut d2 = digits.clone();
                            let mut s = sub;
                            for &p in &xpos {
                                d2[p] = s % 3;
                                s /= 3;
                            }
                            let idx: usize = (0..ct.n_in).map(|i| d2[i] * pow(3, i)).sum();
                            let v = ct.tables[o][idx];
                            match first {
                                None => first = Some(v),
                                Some(f) => {
                                    if f != v {
                                        same = false
                                    }
                                }
                            }
                        }
                        ext[o][row] = if same { first.unwrap() } else { 3 };
                    }
                } else {
                    let idx: usize = (0..ct.n_in).map(|i| digits[i] * pow(radix, i)).sum();
                    for o in 0..ct.n_out {
                        ext[o][row] = ct.tables[o][idx];
                    }
                }
            }
            let active_rows = (0..nrows)
                .filter(|&r| (0..ct.n_out).any(|o| ext[o][r] != 0))
                .map(|r| r as u32)
                .collect();
            types.push(CellType {
                name: ct.name.clone(),
                n_in: ct.n_in,
                n_out: ct.n_out,
                seq: ct.sequential,
                ext,
                active_rows,
            });
        }

        // driver bookkeeping
        let n = spec.n_nets;
        let mut driven = vec![false; n];
        let mut mark = |net: usize, what: &str| -> Result<(), String> {
            if net >= n {
                return Err(format!("{what}: net {net} out of range"));
            }
            if driven[net] {
                return Err(format!("{what}: net {net} has multiple drivers"));
            }
            driven[net] = true;
            Ok(())
        };
        for &i in &spec.inputs {
            mark(i, "input")?;
        }
        for &(c, code) in &spec.consts {
            if (code as usize) >= e {
                return Err("const code out of range".into());
            }
            mark(c, "const")?;
        }
        let mut comb_cells = Vec::new();
        let mut seq_cells = Vec::new();
        for c in &spec.cells {
            if c.t >= types.len() {
                return Err("cell type index out of range".into());
            }
            let ct = &types[c.t];
            if c.ins.len() != ct.n_in || c.outs.len() != ct.n_out {
                return Err(format!("cell of type {} has wrong pin count", ct.name));
            }
            for &o in &c.outs {
                mark(o, "cell output")?;
            }
            for &i in &c.ins {
                if i >= n {
                    return Err("cell input net out of range".into());
                }
            }
            let cell = Cell { t: c.t, ins: c.ins.clone(), outs: c.outs.clone() };
            if ct.seq {
                if ct.n_in != 1 || ct.n_out != 1 {
                    return Err("sequential cells must have one input and one output".into());
                }
                seq_cells.push(cell);
            } else {
                comb_cells.push(cell);
            }
        }
        for c in comb_cells.iter().chain(seq_cells.iter()) {
            for &i in &c.ins {
                if !driven[i] {
                    return Err(format!("net {i} is used but never driven"));
                }
            }
        }
        for &o in &spec.outputs {
            if o >= n || !driven[o] {
                return Err(format!("output net {o} is undriven"));
            }
        }

        // levelize combinational cells (Kahn)
        let mut comb_driver = vec![usize::MAX; n];
        for (ci, c) in comb_cells.iter().enumerate() {
            for &o in &c.outs {
                comb_driver[o] = ci;
            }
        }
        let mut indeg = vec![0usize; comb_cells.len()];
        let mut users: Vec<Vec<usize>> = vec![Vec::new(); comb_cells.len()];
        for (ci, c) in comb_cells.iter().enumerate() {
            for &i in &c.ins {
                let d = comb_driver[i];
                if d != usize::MAX {
                    indeg[ci] += 1;
                    users[d].push(ci);
                }
            }
        }
        let mut order = Vec::with_capacity(comb_cells.len());
        let mut queue: Vec<usize> = (0..comb_cells.len()).filter(|&i| indeg[i] == 0).collect();
        let mut head = 0;
        while head < queue.len() {
            let c = queue[head];
            head += 1;
            order.push(c);
            for &u in &users[c] {
                indeg[u] -= 1;
                if indeg[u] == 0 {
                    queue.push(u);
                }
            }
        }
        if order.len() != comb_cells.len() {
            return Err("combinational loop detected".into());
        }
        let comb: Vec<Cell> = order.iter().map(|&i| comb_cells[i].clone()).collect();
        let mut fanout = vec![Vec::new(); n];
        for (ci, c) in comb.iter().enumerate() {
            for &i in &c.ins {
                if !fanout[i].contains(&ci) {
                    fanout[i].push(ci);
                }
            }
        }
        let init = if has_x { 3 } else { 0 };
        let nseq = seq_cells.len();
        Ok(Engine {
            radix,
            planes,
            e,
            log2e,
            has_x,
            types,
            n_nets: n,
            inputs: spec.inputs,
            outputs: spec.outputs,
            consts: spec.consts,
            comb,
            seq: seq_cells,
            fanout,
            state: vec![init; nseq],
            n_lanes: 1,
        })
    }

    pub fn n_inputs(&self) -> usize {
        self.inputs.len()
    }
    pub fn n_outputs(&self) -> usize {
        self.outputs.len()
    }
    pub fn n_types(&self) -> usize {
        self.types.len()
    }

    /// Count of cell instances per cell type (combinational and sequential).
    pub fn type_counts(&self) -> Vec<u64> {
        let mut v = vec![0u64; self.types.len()];
        for c in self.comb.iter().chain(self.seq.iter()) {
            v[c.t] += 1;
        }
        v
    }

    #[inline]
    fn idx(&self, net: usize, p: usize, w: usize) -> usize {
        (net * self.planes + p) * CHUNK_WORDS + w
    }

    fn eval_cell_packed(&self, cell: &Cell, vals: &mut [u64], nw: usize) {
        let ct = &self.types[cell.t];
        let e = self.e;
        for w in 0..nw {
            let mut eq = [[0u64; 4]; 4];
            for (i, &net) in cell.ins.iter().enumerate() {
                if self.planes == 1 {
                    let v = vals[self.idx(net, 0, w)];
                    eq[i][0] = !v;
                    eq[i][1] = v;
                } else {
                    let lo = vals[self.idx(net, 0, w)];
                    let hi = vals[self.idx(net, 1, w)];
                    eq[i][0] = !lo & !hi;
                    eq[i][1] = lo & !hi;
                    eq[i][2] = !lo & hi;
                    eq[i][3] = lo & hi;
                }
            }
            let mut acc = [[0u64; 2]; 4];
            for &row in &ct.active_rows {
                let row = row as usize;
                let mut m = !0u64;
                for i in 0..ct.n_in {
                    m &= eq[i][(row >> (self.log2e * i)) & (e - 1)];
                }
                if m == 0 {
                    continue;
                }
                for o in 0..ct.n_out {
                    let c = ct.ext[o][row];
                    for p in 0..self.planes {
                        if (c >> p) & 1 == 1 {
                            acc[o][p] |= m;
                        }
                    }
                }
            }
            for (o, &net) in cell.outs.iter().enumerate() {
                for p in 0..self.planes {
                    let k = self.idx(net, p, w);
                    vals[k] = acc[o][p];
                }
            }
        }
    }

    fn lane_code(&self, vals: &[u64], net: usize, v: usize) -> u8 {
        let (w, b) = (v / 64, v % 64);
        let mut c = 0u8;
        for p in 0..self.planes {
            c |= (((vals[self.idx(net, p, w)] >> b) & 1) as u8) << p;
        }
        c
    }

    fn run(
        &self,
        inputs: &[u8],
        n_vec: usize,
        mut state: Option<&mut Vec<u8>>,
        mut toggles: Option<&mut Vec<u32>>,
    ) -> Result<Vec<u8>, String> {
        let n_in = self.inputs.len();
        let n_out = self.outputs.len();
        let n_seq = self.seq.len();
        if inputs.len() != n_vec * n_in {
            return Err(format!("expected {} input codes, got {}", n_vec * n_in, inputs.len()));
        }
        if let Some(&c) = inputs.iter().find(|&&c| (c as usize) >= self.e) {
            return Err(format!("input code {c} out of range"));
        }
        let ntypes = self.types.len();
        if let Some(t) = toggles.as_deref_mut() {
            t.clear();
            t.resize(n_vec * ntypes, 0);
        }
        let mut out = vec![0u8; n_vec * n_out];
        let mut vals = vec![0u64; self.n_nets * self.planes * CHUNK_WORDS];
        let mut last_code = vec![0u8; self.n_nets];
        let chunk = 64 * CHUNK_WORDS;
        let mut start = 0;
        while start < n_vec {
            let nv = (n_vec - start).min(chunk);
            let nw = (nv + 63) / 64;
            for (i, &net) in self.inputs.iter().enumerate() {
                for p in 0..self.planes {
                    for w in 0..nw {
                        let k = self.idx(net, p, w);
                        vals[k] = 0;
                    }
                }
                for v in 0..nv {
                    let c = inputs[(start + v) * n_in + i];
                    for p in 0..self.planes {
                        if (c >> p) & 1 == 1 {
                            let k = self.idx(net, p, v / 64);
                            vals[k] |= 1u64 << (v % 64);
                        }
                    }
                }
            }
            for &(net, code) in &self.consts {
                for p in 0..self.planes {
                    let fill = if (code >> p) & 1 == 1 { !0u64 } else { 0 };
                    for w in 0..nw {
                        let k = self.idx(net, p, w);
                        vals[k] = fill;
                    }
                }
            }
            if let Some(st) = state.as_deref() {
                for (s, cell) in self.seq.iter().enumerate() {
                    let net = cell.outs[0];
                    for p in 0..self.planes {
                        for w in 0..nw {
                            let k = self.idx(net, p, w);
                            vals[k] = 0;
                        }
                    }
                    for v in 0..nv {
                        let c = st[(start + v) * n_seq + s];
                        for p in 0..self.planes {
                            if (c >> p) & 1 == 1 {
                                let k = self.idx(net, p, v / 64);
                                vals[k] |= 1u64 << (v % 64);
                            }
                        }
                    }
                }
            } else if n_seq > 0 {
                return Err("netlist has sequential cells; use reset/step".into());
            }
            for ci in 0..self.comb.len() {
                let cell = &self.comb[ci];
                self.eval_cell_packed(cell, &mut vals, nw);
                if let Some(tg) = toggles.as_deref_mut() {
                    for w in 0..nw {
                        let mut diff = 0u64;
                        for &net in &cell.outs {
                            for p in 0..self.planes {
                                let cur = vals[self.idx(net, p, w)];
                                let carry = if w == 0 {
                                    ((last_code[net] >> p) & 1) as u64
                                } else {
                                    vals[self.idx(net, p, w - 1)] >> 63
                                };
                                diff |= cur ^ ((cur << 1) | carry);
                            }
                        }
                        let lanes_here = (nv - w * 64).min(64);
                        if lanes_here < 64 {
                            diff &= (1u64 << lanes_here) - 1;
                        }
                        if start == 0 && w == 0 {
                            diff &= !1u64;
                        }
                        while diff != 0 {
                            let b = diff.trailing_zeros() as usize;
                            diff &= diff - 1;
                            let vi = start + w * 64 + b;
                            tg[vi * ntypes + cell.t] += 1;
                        }
                    }
                }
            }
            if toggles.is_some() {
                for cell in &self.comb {
                    for &net in &cell.outs {
                        last_code[net] = self.lane_code(&vals, net, nv - 1);
                    }
                }
            }
            for (k, &net) in self.outputs.iter().enumerate() {
                for v in 0..nv {
                    out[(start + v) * n_out + k] = self.lane_code(&vals, net, v);
                }
            }
            if let Some(st) = state.as_deref_mut() {
                for (s, cell) in self.seq.iter().enumerate() {
                    let d = cell.ins[0];
                    for v in 0..nv {
                        st[(start + v) * n_seq + s] = self.lane_code(&vals, d, v);
                    }
                }
            }
            start += nv;
        }
        Ok(out)
    }

    /// Combinational evaluation of `n_vec` independent vectors.
    pub fn eval(&self, inputs: &[u8], n_vec: usize) -> Result<Vec<u8>, String> {
        self.run(inputs, n_vec, None, None)
    }

    /// Evaluation that also returns toggle counts per (vector, cell type): vector `v`
    /// is compared with vector `v-1`; a cell toggles if any of its outputs changes code.
    pub fn eval_activity(&self, inputs: &[u8], n_vec: usize) -> Result<(Vec<u8>, Vec<u32>), String> {
        let mut t = Vec::new();
        let out = self.run(inputs, n_vec, None, Some(&mut t))?;
        Ok((out, t))
    }

    /// Reset sequential state of `n_lanes` independent machines (X for ternary, 0 otherwise).
    pub fn reset(&mut self, n_lanes: usize) {
        let init = if self.has_x { 3 } else { 0 };
        self.n_lanes = n_lanes;
        self.state = vec![init; n_lanes * self.seq.len()];
    }

    /// One clock cycle for all lanes: returns primary outputs computed from the current
    /// state, then latches D into Q.
    pub fn step(&mut self, inputs: &[u8]) -> Result<Vec<u8>, String> {
        let n_vec = self.n_lanes;
        let mut st = std::mem::take(&mut self.state);
        let r = self.run(inputs, n_vec, Some(&mut st), None);
        self.state = st;
        r
    }

    /// Static timing. `delays[type][output]` in ps. Returns (critical delay, critical path as
    /// cell indices into `comb`, arrival time per primary output).
    pub fn sta(&self, delays: &[Vec<f64>]) -> Result<(f64, Vec<usize>, Vec<f64>), String> {
        if delays.len() != self.types.len() {
            return Err("delays must have one entry per cell type".into());
        }
        let mut arr = vec![0.0f64; self.n_nets];
        let mut pred_cell = vec![usize::MAX; self.n_nets];
        for (ci, c) in self.comb.iter().enumerate() {
            let d = &delays[c.t];
            if d.len() != c.outs.len() {
                return Err(format!("type {} needs {} delays", self.types[c.t].name, c.outs.len()));
            }
            let mut a_in = 0.0f64;
            for &i in &c.ins {
                a_in = a_in.max(arr[i]);
            }
            for (o, &net) in c.outs.iter().enumerate() {
                arr[net] = a_in + d[o];
                pred_cell[net] = ci;
            }
        }
        let mut ends: Vec<usize> = self.outputs.clone();
        for c in &self.seq {
            ends.push(c.ins[0]);
        }
        let mut best = 0.0f64;
        let mut best_net = usize::MAX;
        for &n in &ends {
            if arr[n] > best || best_net == usize::MAX {
                best = arr[n];
                best_net = n;
            }
        }
        let mut path = Vec::new();
        let mut net = best_net;
        while net != usize::MAX && pred_cell[net] != usize::MAX {
            let ci = pred_cell[net];
            path.push(ci);
            let c = &self.comb[ci];
            let mut nxt = usize::MAX;
            let mut a = -1.0;
            for &i in &c.ins {
                if arr[i] > a {
                    a = arr[i];
                    nxt = i;
                }
            }
            net = nxt;
        }
        path.reverse();
        let outs = self.outputs.iter().map(|&n| arr[n]).collect();
        Ok((best, path, outs))
    }

    fn eval_cell_scalar(&self, cell: &Cell, vals: &[u8]) -> Vec<u8> {
        let ct = &self.types[cell.t];
        let mut row = 0usize;
        for (i, &net) in cell.ins.iter().enumerate() {
            row |= (vals[net] as usize) << (self.log2e * i);
        }
        (0..ct.n_out).map(|o| ct.ext[o][row]).collect()
    }

    /// Event-driven timed simulation of one input transition (transport delays).
    /// Returns (settled outputs, settle time in ps, applied events, events per cell type).
    pub fn event_sim(
        &self,
        prev: &[u8],
        new: &[u8],
        delays: &[Vec<f64>],
    ) -> Result<(Vec<u8>, f64, u64, Vec<u64>), String> {
        if !self.seq.is_empty() {
            return Err("event_sim supports combinational netlists only".into());
        }
        if prev.len() != self.inputs.len() || new.len() != self.inputs.len() {
            return Err("wrong input length".into());
        }
        let mut vals = vec![0u8; self.n_nets];
        for (i, &net) in self.inputs.iter().enumerate() {
            vals[net] = prev[i];
        }
        for &(net, c) in &self.consts {
            vals[net] = c;
        }
        for c in &self.comb {
            let o = self.eval_cell_scalar(c, &vals);
            for (k, &net) in c.outs.iter().enumerate() {
                vals[net] = o[k];
            }
        }
        let mut proj = vals.clone();
        let to_fs = |d: f64| -> u64 { (d * 1000.0).round().max(0.0) as u64 };
        // driver cell per net for event bookkeeping
        let mut driver_type = vec![usize::MAX; self.n_nets];
        for c in &self.comb {
            for &o in &c.outs {
                driver_type[o] = c.t;
            }
        }
        let mut heap: BinaryHeap<Reverse<(u64, u64, usize, u8)>> = BinaryHeap::new();
        let mut seq_no = 0u64;
        for (i, &net) in self.inputs.iter().enumerate() {
            if new[i] != vals[net] {
                heap.push(Reverse((0, seq_no, net, new[i])));
                seq_no += 1;
                proj[net] = new[i];
            }
        }
        let mut events = 0u64;
        let mut per_type = vec![0u64; self.types.len()];
        let mut last_t = 0u64;
        while let Some(Reverse((t, _, _, _))) = heap.peek().cloned() {
            let mut dirty: Vec<usize> = Vec::new();
            while let Some(Reverse((t2, _, net, v))) = heap.peek().cloned() {
                if t2 != t {
                    break;
                }
                heap.pop();
                if vals[net] != v {
                    vals[net] = v;
                    events += 1;
                    last_t = t;
                    if driver_type[net] != usize::MAX {
                        per_type[driver_type[net]] += 1;
                    }
                    for &c in &self.fanout[net] {
                        if !dirty.contains(&c) {
                            dirty.push(c);
                        }
                    }
                }
            }
            for ci in dirty {
                let c = &self.comb[ci];
                let o = self.eval_cell_scalar(c, &vals);
                for (k, &net) in c.outs.iter().enumerate() {
                    if o[k] != proj[net] {
                        proj[net] = o[k];
                        let d = to_fs(delays[c.t][k]);
                        heap.push(Reverse((t + d, seq_no, net, o[k])));
                        seq_no += 1;
                    }
                }
            }
        }
        let outs = self.outputs.iter().map(|&n| vals[n]).collect();
        Ok((outs, last_t as f64 / 1000.0, events, per_type))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn nand_not_json(radix: usize) -> String {
        // radix 2 only: NAND2 and NOT, out = NOT(NAND(a,b)) = AND
        let _ = radix;
        r#"{"radix":2,
          "cell_types":[
            {"name":"NAND2","n_in":2,"n_out":1,"sequential":false,"tables":[[1,1,1,0]]},
            {"name":"NOT","n_in":1,"n_out":1,"sequential":false,"tables":[[1,0]]}],
          "n_nets":4,"inputs":[0,1],"outputs":[3],"consts":[],
          "cells":[{"t":0,"ins":[0,1],"outs":[2]},{"t":1,"ins":[2],"outs":[3]}]}"#
            .to_string()
    }

    #[test]
    fn binary_and_truth_table() {
        let e = Engine::from_json(&nand_not_json(2)).unwrap();
        let inputs = vec![0, 0, 1, 0, 0, 1, 1, 1];
        assert_eq!(e.eval(&inputs, 4).unwrap(), vec![0, 0, 0, 1]);
    }

    #[test]
    fn many_vectors_cross_chunk_boundaries() {
        let e = Engine::from_json(&nand_not_json(2)).unwrap();
        let n = 5000;
        let mut inputs = Vec::new();
        for v in 0..n {
            inputs.push((v & 1) as u8);
            inputs.push(((v >> 1) & 1) as u8);
        }
        let out = e.eval(&inputs, n).unwrap();
        for v in 0..n {
            assert_eq!(out[v], ((v & 1) & ((v >> 1) & 1)) as u8);
        }
    }

    #[test]
    fn toggles_and_sta() {
        let e = Engine::from_json(&nand_not_json(2)).unwrap();
        let inputs = vec![0, 0, 1, 1, 0, 0, 1, 1];
        let (_, t) = e.eval_activity(&inputs, 4).unwrap();
        // NAND output: 1,0,1,0 -> toggles at v=1,2,3 ; NOT output follows
        assert_eq!(t.iter().sum::<u32>(), 6);
        let (d, path, _) = e.sta(&[vec![10.0], vec![5.0]]).unwrap();
        assert_eq!(d, 15.0);
        assert_eq!(path.len(), 2);
    }

    #[test]
    fn ternary_x_is_pessimistic_and_sound() {
        // MIN over {-1,0,1} coded 0,1,2 ; table index = a + 3*b
        let mut t = Vec::new();
        for b in 0..3u8 {
            for a in 0..3u8 {
                t.push(a.min(b));
            }
        }
        let json = format!(
            r#"{{"radix":3,"cell_types":[{{"name":"MIN","n_in":2,"n_out":1,"sequential":false,"tables":[{:?}]}}],
              "n_nets":3,"inputs":[0,1],"outputs":[2],"consts":[],"cells":[{{"t":0,"ins":[0,1],"outs":[2]}}]}}"#,
            t
        );
        let e = Engine::from_json(&json).unwrap();
        // X=3. min(-1, X) = -1 (known); min(+1, X) = X
        let out = e.eval(&[0, 3, 2, 3], 2).unwrap();
        assert_eq!(out, vec![0, 3]);
    }

    #[test]
    fn event_sim_matches_levelized() {
        let e = Engine::from_json(&nand_not_json(2)).unwrap();
        let (o, t, ev, _) = e.event_sim(&[0, 0], &[1, 1], &[vec![10.0], vec![5.0]]).unwrap();
        assert_eq!(o, vec![1]);
        assert_eq!(t, 15.0);
        assert_eq!(ev, 4); // two primary-input changes + NAND output + NOT output
    }
}
