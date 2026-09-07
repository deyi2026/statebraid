"""Mechanical cache namespace helpers.

Trust-domain labels are caller-supplied mechanical isolation tokens. They do not
carry semantic importance and are never interpreted as task, user, or evidence
meaning by StateBraid.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable
import re


DEFAULT_TRUST_DOMAIN = "local-default"
MAX_TRUST_DOMAIN_BYTES = 128
_TRUST_DOMAIN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*\Z")


@dataclass(frozen=True)
class CacheNamespace:
    """Compound namespace that isolates one backend identity by trust domain."""

    backend_identity: Hashable
    trust_domain: str


def validate_trust_domain(value: str) -> str:
    """Validate an opaque request trust-domain token without semantic rewriting."""
    if not isinstance(value, str):
        raise TypeError("cache namespace must be a string")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("cache namespace must contain ASCII characters only") from exc
    if not encoded:
        raise ValueError("cache namespace must not be empty")
    if len(encoded) > MAX_TRUST_DOMAIN_BYTES:
        raise ValueError(
            f"cache namespace exceeds {MAX_TRUST_DOMAIN_BYTES} ASCII bytes"
        )
    if _TRUST_DOMAIN_RE.fullmatch(value) is None:
        raise ValueError(
            "cache namespace may contain only letters, digits, '.', '_', ':', or '-'"
        )
    return value


def make_cache_namespace(
    backend_identity: Hashable,
    trust_domain: str = DEFAULT_TRUST_DOMAIN,
) -> CacheNamespace:
    """Return the exact compound cache namespace used for reuse isolation."""
    return CacheNamespace(
        backend_identity=backend_identity,
        trust_domain=validate_trust_domain(trust_domain),
    )
