# ADR 0001 — Core simulator language

Status: **Proposed (M0).**

## Decision

Implement the simulator core in **Rust**, exposed to Python through **PyO3**, built and packaged with
**maturin**. Python is used for the CLI, the experiment manager, the golden models, statistics and
reporting.

## Reasons

- **Correctness of a scientific tool.** Memory safety rules out a class of undefined behaviour that would
  produce silently wrong simulation results. Parallel evaluation (rayon) is data-race-free by construction.
- **Performance.** Levelized evaluation with bit-parallel packing and event-driven simulation are
  tight-loop, cache-sensitive workloads where Rust and C++ perform equally well.
- **Distribution.** `pip install tribinary` needs prebuilt wheels. maturin plus `cibuildwheel`-style CI gives
  Linux, macOS and Windows wheels with less build-system friction than CMake with pybind11 and nanobind.
- **Testing.** `cargo test` and property-based tests (`proptest`) fit equivalence checking.
- **Local toolchain.** Rust 1.97, Cargo and Python 3.12 are available on the development machine.

## Alternative considered: C++20

Comparable speed and a large existing EDA ecosystem. Rejected because of manual memory management risk,
and a heavier packaging path for pure-pip distribution. It would be the right choice if the project needed
to link existing C++ EDA libraries, which it does not.

## Consequences

- Contributors need Rust to modify the core; plugin authors (cells, workloads, GPU variants) work in
  YAML and Python and do not need Rust.
- A CPU-only path is the reference. An optional CUDA backend (Q10) must match it bit for bit.
- A small pure-Python reference evaluator may be kept for differential testing (Q9).
