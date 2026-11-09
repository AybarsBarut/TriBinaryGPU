"""M3 Verification: Multi-SM GPU Architecture (GPU-B, GPU-T, GPU-BT, GPU-Q-1b, GPU-Q-2b)."""
from __future__ import annotations

import pytest

from tribinary.gpu.device import Device
from workloads.vec_add import VEC_ADD_ASM


@pytest.mark.parametrize("design,width", [
    ("GPU-B", 16),
    ("GPU-T", 11),
    ("GPU-BT", 11),     # 2-bit per trit control design
    ("GPU-Q-1b", 8),    # quaternary logic, binary 1-bit memory
    ("GPU-Q-2b", 8),    # quaternary logic, MLC 2-bit memory
])
def test_multi_sm_device_launch(design, width):
    device = Device(
        design=design,
        n_sm=4,
        n_lanes_per_sm=8,
        word_width=width,
        global_mem_size=1024,
    )

    assert device.total_lanes == 32
    assert len(device.sms) == 4

    # Prepare input data across global memory
    data = {i: (i + 1) for i in range(32)}
    for i in range(32):
        data[16 + i] = (i + 1) * 2

    metrics = device.launch_grid(VEC_ADD_ASM, grid_data=data)

    assert metrics["n_sm"] == 4
    assert metrics["total_lanes"] == 32
    assert metrics["max_cycles"] > 0
    assert metrics["execution_time_ns"] > 0.0
    assert metrics["total_energy_fj"] > 0.0
    assert metrics["total_area_um2"] > 0.0
