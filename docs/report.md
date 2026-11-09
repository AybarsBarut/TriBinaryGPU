# RadixLab — Automated Scientific Simulation Report

> **Rule Enforced:** All numerical results are injected by template from deterministic and verified gate-level simulations.

## 1. Executive Summary & Pre-Registered Outcomes

| Hypothesis | Focus | Primary Metric | Nominal Result | Outcome Label |
| :--- | :--- | :--- | :--- | :--- |
| **H1 (Radix Economy)** | Transistors & lines / bit | Transistor ratio | 0.946 ideal, break-even c* = 1.585x | **SUPPORTED-CONDITIONALLY** |
| **H2 (Sign Detect)** | MS non-zero trit priority | Delay (ps) | Ternary is 79% to 96% slower | **REFUTED** |
| **H2 (Comparator)** | Trichotomy sign(a - b) | Delay (ps) | Ternary is 20% to 24% faster | **SUPPORTED** |
| **H2 (Arithmetic / GEMM)** | Matrix Multiply Energy | Total Energy (fJ) | GPU-T saves 42.6% energy | **SUPPORTED** |
| **H3 (Geometry / Raster)** | Edge function & Circle SDF | Energy (fJ) | GPU-T saves 39% to 41% energy | **SUPPORTED** |
| **H4 (Noise Immunity)** | Gaussian sigma sweep | Symbol Error Rate | Half-margin shrinks (1/2 vs 1/4 vs 1/6) | **SUPPORTED** |
| **H5 (Neural BitNet)** | W in {-1,0,+1} inference | Perf / Watt | GPU-T saves 34.9% energy | **SUPPORTED** |

---

## 2. Multi-SM GPU Effect Decomposition (32 Lanes, 4 SMs)

To separate the effect of number-system arithmetic from native multi-valued hardware,
we compare GPU-B (binary baseline), GPU-BT (ternary arithmetic on binary cells, 2 bits/trit), and GPU-T (native ternary):

| Workload | Total Effect ($M(T)/M(B)$) | Encoding Effect ($M(BT)/M(B)$) | Hardware Effect ($M(T)/M(BT)$) | MLC Memory Effect ($Q2b/Q1b$) |
| :--- | :--- | :--- | :--- | :--- |
| **vec_add** | **0.7156x** | 1.605x | **0.4459x** | 1.0x |
| **gemm** | **0.574x** | 1.5845x | **0.3623x** | 1.0x |
| **bitnet_mlp** | **0.651x** | 1.5984x | **0.4073x** | 1.0x |
| **raster_triangle** | **0.5919x** | 1.5459x | **0.3829x** | 1.0x |
| **circle_sdf** | **0.6066x** | 1.5798x | **0.384x** | 1.0x |

---

## 3. Pareto Analysis: Execution Time vs Energy vs Area

| Workload | Design | Exec Time (ns) | Total Energy (fJ) | Total Area (um²) | Throughput (GOPS) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| vec_add | GPU-B     |   2.00 ns |   9272.8 fJ | 22336.0 um² |   80.0 |
| vec_add | GPU-T     |   2.12 ns |   6636.0 fJ | 23161.6 um² |   75.3 |
| vec_add | GPU-BT    |   2.60 ns |  14882.4 fJ | 37868.8 um² |   61.5 |
| vec_add | GPU-Q-1b  |   1.20 ns |   3613.2 fJ |  7718.4 um² |  133.3 |
| vec_add | GPU-Q-2b  |   1.20 ns |   3613.2 fJ |  7718.4 um² |  133.3 |
| gemm | GPU-B     |   4.40 ns |  23466.0 fJ | 22336.0 um² |   80.0 |
| gemm | GPU-T     |   4.67 ns |  13470.0 fJ | 23161.6 um² |   75.3 |
| gemm | GPU-BT    |   5.72 ns |  37182.0 fJ | 37868.8 um² |   61.5 |
| gemm | GPU-Q-1b  |   2.64 ns |   9221.2 fJ |  7718.4 um² |  133.3 |
| gemm | GPU-Q-2b  |   2.64 ns |   9221.2 fJ |  7718.4 um² |  133.3 |
| bitnet_mlp | GPU-B     |   4.40 ns |  25212.0 fJ | 22336.0 um² |   80.0 |
| bitnet_mlp | GPU-T     |   4.67 ns |  16412.4 fJ | 23161.6 um² |   75.3 |
| bitnet_mlp | GPU-BT    |   5.72 ns |  40300.0 fJ | 37868.8 um² |   61.5 |
| bitnet_mlp | GPU-Q-1b  |   2.64 ns |   9252.4 fJ |  7718.4 um² |  133.3 |
| bitnet_mlp | GPU-Q-2b  |   2.64 ns |   9252.4 fJ |  7718.4 um² |  133.3 |
| raster_triangle | GPU-B     |   3.60 ns |  18858.0 fJ | 22336.0 um² |   80.0 |
| raster_triangle | GPU-T     |   3.83 ns |  11162.0 fJ | 23161.6 um² |   75.3 |
| raster_triangle | GPU-BT    |   4.68 ns |  29153.2 fJ | 37868.8 um² |   61.5 |
| raster_triangle | GPU-Q-1b  |   2.16 ns |   7290.8 fJ |  7718.4 um² |  133.3 |
| raster_triangle | GPU-Q-2b  |   2.16 ns |   7290.8 fJ |  7718.4 um² |  133.3 |
| circle_sdf | GPU-B     |   3.60 ns |  21463.6 fJ | 22336.0 um² |   80.0 |
| circle_sdf | GPU-T     |   3.83 ns |  13020.4 fJ | 23161.6 um² |   75.3 |
| circle_sdf | GPU-BT    |   4.68 ns |  33908.0 fJ | 37868.8 um² |   61.5 |
| circle_sdf | GPU-Q-1b  |   2.16 ns |   8759.6 fJ |  7718.4 um² |  133.3 |
| circle_sdf | GPU-Q-2b  |   2.16 ns |   8759.6 fJ |  7718.4 um² |  133.3 |

---

## 4. Threat to Validity & Red-Team Audit Notes
- Standalone sign detection is inherently uncompetitive in balanced ternary due to dynamic non-zero trit priority resolution.
- Ternary energy advantage emerges as precision scales to >= 16 bits due to ~31% fewer lines and interconnect toggles.
- All non-binary cell parameters remain flagged as assumptions with `confidence: low` awaiting experimental foundry validation.

