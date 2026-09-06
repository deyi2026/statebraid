"""StateBraid compute-continuity primitives."""

from .generation import ensure_generation_safe_exact_hit, is_generation_safe_hybrid_checkpoint
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
    "CacheCoordinator",
    "CacheKey",
    "EntryState",
    "Eviction",
    "PIN_ROLES",
    "TrimPlan",
    "WorkingSetPolicy",
    "ensure_generation_safe_exact_hit",
    "is_generation_safe_hybrid_checkpoint",
    "matched_prefix_key",
]
