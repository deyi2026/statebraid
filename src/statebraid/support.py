"""Machine-readable StateBraid v0.1 support-scope metadata.

This module describes where the frozen compute contract has end-to-end runtime
qualification.  It is deliberately narrower than the backend-neutral core API:
having a compatible adapter surface is not, by itself, a claim that every model,
cache shape, server mode, platform, or concurrency profile is supported.
"""

from __future__ import annotations

from typing import Any

from statebraid.cache.namespace import DEFAULT_TRUST_DOMAIN, MAX_TRUST_DOMAIN_BYTES
from statebraid.integrations.mlx import (
    REFERENCE_MLX_BASE_SHA,
    REFERENCE_MLX_SERVER_API_VERSION,
    REFERENCE_MLX_STORAGE_API_VERSION,
    REFERENCE_PATCH_SHA256,
)


SUPPORT_SCOPE_VERSION = "0.1"
PYTHON_REQUIRES = ">=3.11"

REFERENCE_BACKEND = "mlx"
REFERENCE_PLATFORM = "Apple Silicon / macOS"
REFERENCE_MODEL = "Ornith-1.5-35B-A3B-MLX"
REFERENCE_MODEL_LINEAGE = "Qwen3.6-derived"
REFERENCE_CACHE_SHAPE = "hybrid/non-trimmable"
REFERENCE_GENERATION_PATH = "batch"
REFERENCE_THINKING_MODE = "model-native"
REFERENCE_KV_MODE = "unquantized-kv"
REFERENCE_PROMPT_CONCURRENCY = 1
REFERENCE_DECODE_CONCURRENCY = 1
REFERENCE_PROMPT_CACHE_SIZE = 8
REFERENCE_PROMPT_CACHE_BYTES = 4 * 1024 * 1024 * 1024
REFERENCE_ACTIVATION_DEFAULT = False

CONDITIONAL_SUPPORT = (
    "multiple trust domains are supported only as a cache-isolation primitive; "
    "a trusted authenticated gateway or harness must derive cache_namespace",
    "Python >=3.11 is the package contract; the per-minor CI matrix is a separate "
    "release gate and is not implied by this scope document",
)

UNQUALIFIED_RUNTIME_FEATURES = (
    "arbitrary mlx-lm commits other than the exact reference base",
    "blanket support for all Qwen-derived or all MLX models",
    "generic trimmable-KV runtime parity",
    "quantized-KV StateBraid runtime paths",
    "draft-model or speculative-decoding paths",
    "non-batch/single-generation StateBraid paths",
    "distributed MLX execution",
    "server concurrency profiles above prompt=1 and decode=1",
    "multi-model co-residency or concurrent multi-model serving",
    "serving backends other than the qualified MLX reference",
    "Linux/Windows runtime qualification for the MLX reference path",
    "persistent cache recovery across process restart",
    "StateBraid acting as an authentication, authorization, or TLS boundary",
)


def support_scope() -> dict[str, Any]:
    """Return a fresh machine-readable description of the v0.1 support boundary."""

    return {
        "support_scope_version": SUPPORT_SCOPE_VERSION,
        "python_requires": PYTHON_REQUIRES,
        "core_contract": {
            "backend_neutral": True,
            "mlx_import_required": False,
            "runtime_qualification_is_narrower_than_core_api": True,
        },
        "reference_runtime": {
            "backend": REFERENCE_BACKEND,
            "platform": REFERENCE_PLATFORM,
            "mlx_base_sha": REFERENCE_MLX_BASE_SHA,
            "storage_api_version": REFERENCE_MLX_STORAGE_API_VERSION,
            "server_api_version": REFERENCE_MLX_SERVER_API_VERSION,
            "patch_sha256": REFERENCE_PATCH_SHA256,
            "model": REFERENCE_MODEL,
            "model_lineage": REFERENCE_MODEL_LINEAGE,
            "cache_shape": REFERENCE_CACHE_SHAPE,
            "generation_path": REFERENCE_GENERATION_PATH,
            "thinking_mode": REFERENCE_THINKING_MODE,
            "kv_mode": REFERENCE_KV_MODE,
            "prompt_concurrency": REFERENCE_PROMPT_CONCURRENCY,
            "decode_concurrency": REFERENCE_DECODE_CONCURRENCY,
            "prompt_cache_size": REFERENCE_PROMPT_CACHE_SIZE,
            "prompt_cache_bytes": REFERENCE_PROMPT_CACHE_BYTES,
            "activation_default": REFERENCE_ACTIVATION_DEFAULT,
            "single_user_default_namespace": DEFAULT_TRUST_DOMAIN,
            "max_trust_domain_bytes": MAX_TRUST_DOMAIN_BYTES,
        },
        "conditional_support": list(CONDITIONAL_SUPPORT),
        "unqualified_runtime_features": list(UNQUALIFIED_RUNTIME_FEATURES),
    }


__all__ = [
    "CONDITIONAL_SUPPORT",
    "PYTHON_REQUIRES",
    "REFERENCE_ACTIVATION_DEFAULT",
    "REFERENCE_BACKEND",
    "REFERENCE_CACHE_SHAPE",
    "REFERENCE_DECODE_CONCURRENCY",
    "REFERENCE_GENERATION_PATH",
    "REFERENCE_KV_MODE",
    "REFERENCE_MODEL",
    "REFERENCE_MODEL_LINEAGE",
    "REFERENCE_PLATFORM",
    "REFERENCE_PROMPT_CACHE_BYTES",
    "REFERENCE_PROMPT_CACHE_SIZE",
    "REFERENCE_PROMPT_CONCURRENCY",
    "REFERENCE_THINKING_MODE",
    "SUPPORT_SCOPE_VERSION",
    "UNQUALIFIED_RUNTIME_FEATURES",
    "support_scope",
]
