# TriBinary: Binary vs Ternary/Quaternary Logic GPU Simulation Laboratory

[![CI](https://github.com/tribinary/tribinary/actions/workflows/ci.yml/badge.svg)](https://github.com/tribinary/tribinary/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-0.1.0-green.svg)](pyproject.toml)

TriBinary is a reproducible, open-source scientific simulation laboratory and gate-level benchmark suite designed to answer a fundamental computer architecture research question:

> **Research Question:** Under identical microarchitectural templates and physical silicon budget assumptions, how do binary, balanced-ternary, and quaternary GPU architectures compare in speed, dynamic energy, silicon area, and noise resilience across diverse compute workloads?

All findings are pre-registered and locked under git tag [`prereg-v1`](docs/hypotheses.md). Negative results are reported directly without bias.

---

## Architecture Overview

```mermaid
flowchart TD
    subgraph Multi-SM GPU Architecture
        GM["Global Memory (DRAM/HBM Macro)"] --> SM0["SM 0 (8 Lanes)"]
        GM --> SM1["SM 1 (8 Lanes)"]
        GM --> SM2["SM 2 (8 Lanes)"]
        GM --> SM3["SM 3 (8 Lanes)"]
    end

    subgraph Streaming Multiprocessor (SM)
        Warp["SIMT Warp Sequencer & PC"] --> Dec["Instruction Decoder"]
        Dec --> RF["Register File Array (Macro: true)"]
        RF --> ALU["Gate-Level Netlist ALU Lanes (0..7)"]
        ALU --> SMEM["Shared Memory Scratchpad (Macro: true)"]
    end

    subgraph Logic Systems Evaluated
        GPUB["GPU-B: Binary Reference"]
        GPUT["GPU-T: Balanced Ternary {-1, 0, +1}"]
        GPUBT["GPU-BT: Control (Ternary Math on Binary Cells)"]
        GPUQ1["GPU-Q-1b: Quaternary Logic, 1-bit Memory"]
        GPUQ2["GPU-Q-2b: Quaternary Logic, 2-bit MLC Memory"]
    end
```

---

## Key Scientific Findings (v0.1)

1. **Sign Detection vs Full Comparison (Finding 2 / H2):**
   - **Standalone Sign Detection:** Balanced ternary is **79% to 96% slower** and requires **125% to 150% more transistors** than binary. In binary two's complement, sign extraction is an $O(1)$ zero-gate operation (tapping the MSB wire), whereas balanced ternary must dynamically evaluate the *most significant non-zero trit* through an $O(\log n)$ priority tree. **(H2 Sign-Detect REFUTED)**.
   - **Relational Comparator ($a < b$):** Balanced ternary is **20% to 24% faster** and uses **33% to 41% fewer transistors**. The native ternary `TCMP` gate computes the full trichotomy ($<, =, >$) in a single logic level without a borrow/subtract carry-chain. **(H2 Comparator SUPPORTED)**.
2. **Multi-SM Effect Decomposition (H2 & H5):**
   - **Math vs Hardware:** Simulating ternary arithmetic on binary hardware (**GPU-BT**) consumes **~1.58x MORE energy** than native binary due to 2-bit-per-trit encoding overhead. However, **native ternary hardware (GPU-T)** achieves an energy ratio of **0.36x to 0.44x relative to GPU-BT**. The net energy saving (**42.6% on GEMM, 34.9% on BitNet**) is strictly a native hardware and interconnect advantage.
3. **Noise Margin Penalty (H4):**
   - Gaussian noise sweeps confirm that reducing half-margins ($0.50V$ in binary vs $0.25V$ in ternary vs $0.167V$ in quaternary) causes non-binary systems to experience symbol errors at substantially lower noise levels (crossover at $\sigma/V \approx 0.07$). **(H4 SUPPORTED)**.

---

## 10-Minute Quickstart

### 1. Prerequisites & Toolchain
- Python 3.10+
- Rust 1.75+ and Cargo

### 2. Installation
```powershell
# Clone repository
git clone https://github.com/tribinary/tribinary.git
cd tribinary

# Set up virtual environment
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies and build Rust simulator core
pip install --upgrade pip maturin pytest numpy scipy pyyaml httpx
maturin develop --release
```

### 3. Verify Gate-Level Netlists & Equivalence
```powershell
tribinary verify --suite m1
```

### 4. Run Multi-SM GPU Experiments
```powershell
# Run 32-lane multi-SM benchmark across all 5 designs
tribinary run experiments/m3_full_gpu.yaml

# Run noise sensitivity sweep
tribinary run experiments/h4_noise.yaml

# Run parameter sensitivity analysis (1024 Monte Carlo samples)
tribinary run experiments/h1_sensitivity.yaml
```

### 5. Generate Automated Report
```powershell
tribinary report
# View report in docs/report.md
```

---

## NVIDIA NIM AI Integration

TriBinary integrates with NVIDIA AI Foundation endpoints (`build.nvidia.com`) via `ai/nim_client.py`:
- **Red Team Auditor (`ai/agents/red_team.py`):** Uses `nvidia/nemotron-3-ultra-550b-a55b` to audit assumptions for bias.
- **Report Drafter (`ai/agents/report_drafter.py`):** Drafts report narratives enforcing the zero-hallucinated-number template rule.
- **Cell Designer (`ai/agents/cell_designer.py`):** Drafts candidate gate netlists with mandatory quarantine and verification gates.

To run the Red Team agent:
```powershell
$env:NVIDIA_API_KEY="nvapi-..."
tribinary review
```

---

## License & Citation

Licensed under [Apache-2.0](LICENSE). See [CITATION.cff](CITATION.cff) for citations in academic publications.
