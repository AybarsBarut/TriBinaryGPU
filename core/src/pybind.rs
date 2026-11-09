//! PyO3 bindings. Byte buffers are used for bulk data so that no numpy build dependency is needed:
//! inputs are row-major `[n_vec, n_inputs]` u8 codes; outputs are `[n_vec, n_outputs]` u8 codes;
//! toggle counts are little-endian u32 `[n_vec, n_cell_types]`.

use crate::Engine;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;

fn err(e: String) -> PyErr {
    PyValueError::new_err(e)
}

#[pyclass(name = "Engine")]
pub struct PyEngine {
    inner: Engine,
}

#[pymethods]
impl PyEngine {
    #[new]
    fn new(spec_json: &str) -> PyResult<Self> {
        Ok(PyEngine { inner: Engine::from_json(spec_json).map_err(err)? })
    }

    #[getter]
    fn n_inputs(&self) -> usize {
        self.inner.n_inputs()
    }
    #[getter]
    fn n_outputs(&self) -> usize {
        self.inner.n_outputs()
    }
    #[getter]
    fn n_types(&self) -> usize {
        self.inner.n_types()
    }
    #[getter]
    fn n_cells(&self) -> usize {
        self.inner.comb.len() + self.inner.seq.len()
    }

    fn type_counts(&self) -> Vec<u64> {
        self.inner.type_counts()
    }

    fn eval<'py>(&self, py: Python<'py>, inputs: &[u8], n_vec: usize) -> PyResult<Bound<'py, PyBytes>> {
        let out = py.allow_threads(|| self.inner.eval(inputs, n_vec)).map_err(err)?;
        Ok(PyBytes::new(py, &out))
    }

    fn eval_activity<'py>(
        &self,
        py: Python<'py>,
        inputs: &[u8],
        n_vec: usize,
    ) -> PyResult<(Bound<'py, PyBytes>, Bound<'py, PyBytes>)> {
        let (out, tg) = py.allow_threads(|| self.inner.eval_activity(inputs, n_vec)).map_err(err)?;
        let mut raw = Vec::with_capacity(tg.len() * 4);
        for t in tg {
            raw.extend_from_slice(&t.to_le_bytes());
        }
        Ok((PyBytes::new(py, &out), PyBytes::new(py, &raw)))
    }

    fn reset(&mut self, n_lanes: usize) {
        self.inner.reset(n_lanes);
    }

    fn step<'py>(&mut self, py: Python<'py>, inputs: &[u8]) -> PyResult<Bound<'py, PyBytes>> {
        let out = self.inner.step(inputs).map_err(err)?;
        Ok(PyBytes::new(py, &out))
    }

    fn sta(&self, delays: Vec<Vec<f64>>) -> PyResult<(f64, Vec<usize>, Vec<f64>)> {
        self.inner.sta(&delays).map_err(err)
    }

    fn event_sim<'py>(
        &self,
        py: Python<'py>,
        prev: &[u8],
        new: &[u8],
        delays: Vec<Vec<f64>>,
    ) -> PyResult<(Bound<'py, PyBytes>, f64, u64, Vec<u64>)> {
        let (o, t, ev, per) = self.inner.event_sim(prev, new, &delays).map_err(err)?;
        Ok((PyBytes::new(py, &o), t, ev, per))
    }
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyEngine>()?;
    Ok(())
}
