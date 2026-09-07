"""StateBraid compute-continuity primitives."""

from .generation import ensure_generation_safe_exact_hit, is_generation_safe_hybrid_checkpoint
from .namespace import (
    DEFAULT_TRUST_DOMAIN,
    MAX_TRUST_DOMAIN_BYTES,
    CacheNamespace,
    make_cache_namespace,
    validate_trust_domain,
)
from .policy import (
    AdmissionPlan,
    CacheCoordinator,
    CacheKey,
    EntryState,
    Eviction,
    PIN_ROLES,
    TrimPlan,
    WorkingSetPolicy,
    matched_prefix_key,
)

__all__ = [
    "AdmissionPlan",
    "CacheNamespace",
    "CacheCoordinator",
    "CacheKey",
    "DEFAULT_TRUST_DOMAIN",
    "EntryState",
    "Eviction",
    "PIN_ROLES",
    "MAX_TRUST_DOMAIN_BYTES",
    "TrimPlan",
    "WorkingSetPolicy",
    "ensure_generation_safe_exact_hit",
    "is_generation_safe_hybrid_checkpoint",
    "make_cache_namespace",
    "matched_prefix_key",
    "validate_trust_domain",
]
