"""Optional backend adapters for StateBraid."""

from .llama_cpp import (
    LLAMA_CPP_BACKEND_DESCRIPTOR,
    LLAMA_CPP_REFERENCE_SHA,
    LlamaCppHTTPAdapter,
    LlamaCppReuseHandle,
    LlamaCppReuseStats,
    llama_cpp_cache_namespace,
    normalize_llama_cpp_reuse,
)

from .mlx import (
    MLX_BACKEND_DESCRIPTOR,
    MLXPromptCacheBackend,
    MLXStateBraidPromptCache,
    generation_safe_prompt_cache_hit,
)

__all__ = [
    "normalize_llama_cpp_reuse",
    "llama_cpp_cache_namespace",
    "LlamaCppReuseStats",
    "LlamaCppReuseHandle",
    "LlamaCppHTTPAdapter",
    "LLAMA_CPP_REFERENCE_SHA",
    "LLAMA_CPP_BACKEND_DESCRIPTOR",
    "MLX_BACKEND_DESCRIPTOR",
    "MLXPromptCacheBackend",
    "MLXStateBraidPromptCache",
    "generation_safe_prompt_cache_hit",
]
