"""Standard Workload Suite for RadixLab GPU benchmarking (Section 6)."""
from .bitnet_mlp import BITNET_TERNARY_ASM, generate_bitnet_data
from .circle_sdf import CIRCLE_SDF_ASM, generate_circle_data
from .conv2d import CONV2D_ASM, generate_conv2d_data
from .divergence import DIVERGENCE_ASM, generate_divergence_data
from .gemm import GEMM_ASM, generate_gemm_data
from .mandelbrot import MANDELBROT_ASM, generate_mandelbrot_data
from .nbody import NBODY_ASM, generate_nbody_data
from .raster_triangle import RASTER_TRIANGLE_ASM, generate_triangle_data
from .reduction import REDUCTION_ASM, generate_reduction_data
from .saxpy import SAXPY_ASM, generate_saxpy_data
from .vec_add import VEC_ADD_ASM, generate_vec_add_data
