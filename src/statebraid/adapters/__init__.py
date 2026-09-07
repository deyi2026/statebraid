"""Optional backend adapters for StateBraid."""

from .llama_cpp import (
    LLAMA_CPP_BACKEND_DESCRIPTOR,
    LLAMA_CPP_REFERENCE_SHA,
    LlamaCppHTTPAdapter,
    LlamaCppReuseHandle,
    LlamaCppReuseStats,
    llama_cpp_cache_namespace,
    llama_cpp_reference_source_match,
    llama_cpp_source_commit,
    normalize_llama_cpp_reuse,
)
from .llama_cpp_managed import (
    LLAMA_CPP_MANAGED_BACKEND_DESCRIPTOR,
    LLAMA_CPP_MANAGED_REFERENCE_SHA,
    LlamaCppManagedHTTPAdapter,
    LlamaCppManagedRestore,
    LlamaCppManagedStateHandle,
    LlamaCppManagedStorageBackend,
    LlamaCppStateBraidPromptCache,
    llama_cpp_managed_reference_source_match,
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
    "llama_cpp_managed_reference_source_match",
    "llama_cpp_reference_source_match",
    "llama_cpp_source_commit",
    "LlamaCppReuseStats",
    "LlamaCppReuseHandle",
    "LlamaCppHTTPAdapter",
    "LlamaCppManagedHTTPAdapter",
    "LlamaCppManagedRestore",
    "LlamaCppManagedStateHandle",
    "LlamaCppManagedStorageBackend",
    "LlamaCppStateBraidPromptCache",
    "LLAMA_CPP_REFERENCE_SHA",
    "LLAMA_CPP_BACKEND_DESCRIPTOR",
    "LLAMA_CPP_MANAGED_REFERENCE_SHA",
    "LLAMA_CPP_MANAGED_BACKEND_DESCRIPTOR",
    "MLX_BACKEND_DESCRIPTOR",
    "MLXPromptCacheBackend",
    "MLXStateBraidPromptCache",
    "generation_safe_prompt_cache_hit",
]
