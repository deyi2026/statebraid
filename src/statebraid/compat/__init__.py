"""Runtime compatibility probes for optional StateBraid backends."""

from .llama_cpp import (
    LlamaCppCompatibilityReport,
    probe_llama_cpp_server,
)

from .mlx import (
    MLXCompatibilityReport,
    REQUIRED_MLX_SERVER_API_VERSION,
    REQUIRED_MLX_STORAGE_API_VERSION,
    probe_mlx_backend,
)

__all__ = [
    "probe_llama_cpp_server",
    "LlamaCppCompatibilityReport",
    "MLXCompatibilityReport",
    "REQUIRED_MLX_SERVER_API_VERSION",
    "REQUIRED_MLX_STORAGE_API_VERSION",
    "probe_mlx_backend",
]
