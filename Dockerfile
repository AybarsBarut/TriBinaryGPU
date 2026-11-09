# RadixLab: Binary vs Ternary/Quaternary Logic GPU Simulation Laboratory
FROM python:3.12-slim

# Install system dependencies including Rust toolchain
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    ca-certificates \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /workspace

# Copy dependencies first for caching
COPY pyproject.toml /workspace/
COPY core/ /workspace/core/
COPY radixlab/ /workspace/radixlab/
COPY cells/ /workspace/cells/
COPY experiments/ /workspace/experiments/
COPY workloads/ /workspace/workloads/
COPY ai/ /workspace/ai/
COPY tools/ /workspace/tools/
COPY docs/ /workspace/docs/
COPY tests/ /workspace/tests/
COPY verified.json /workspace/

# Install python dependencies and build maturin package
RUN pip install --no-cache-dir --upgrade pip maturin pytest numpy scipy pyyaml httpx \
    && maturin develop --release

# Run verification and experiments by default
CMD ["sh", "-c", "radixlab verify --suite m1 && radixlab run experiments/m3_full_gpu.yaml && radixlab report && cat docs/report.md"]
