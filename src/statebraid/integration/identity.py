"""Mechanical trusted-ownership to trust-domain derivation.

This module does not authenticate users or parse bearer tokens.  Callers must
supply an ownership identity that has already been established by a trusted
harness/gateway boundary.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

from statebraid.cache.namespace import DEFAULT_TRUST_DOMAIN, validate_trust_domain

MAX_OWNERSHIP_COMPONENT_BYTES = 1024
MIN_DERIVATION_KEY_BYTES = 16


@dataclass(frozen=True)
class TrustedOwnership:
    """Opaque authenticated ownership identity, not task/agent semantic state."""

    subject: str
    issuer: str = "statebraid-integration"
    local_single_user: bool = False

    def __post_init__(self) -> None:
        for label, value in (("subject", self.subject), ("issuer", self.issuer)):
            if not isinstance(value, str) or not value:
                raise ValueError(f"ownership {label} must be a non-empty string")
            if "\x00" in value:
                raise ValueError(f"ownership {label} must not contain NUL")
            if len(value.encode("utf-8")) > MAX_OWNERSHIP_COMPONENT_BYTES:
                raise ValueError(
                    f"ownership {label} exceeds {MAX_OWNERSHIP_COMPONENT_BYTES} bytes"
                )


class TrustDomainDeriver:
    """Derive a bounded opaque StateBraid trust domain from trusted ownership."""

    def __init__(self, derivation_key: bytes | None = None):
        if derivation_key is not None and len(derivation_key) < MIN_DERIVATION_KEY_BYTES:
            raise ValueError(
                f"derivation key must be at least {MIN_DERIVATION_KEY_BYTES} bytes"
            )
        self._key = derivation_key

    def derive(self, ownership: TrustedOwnership) -> str:
        if ownership.local_single_user:
            return DEFAULT_TRUST_DOMAIN
        if self._key is None:
            raise ValueError("non-local ownership requires a trusted derivation key")
        canonical = (
            ownership.issuer.encode("utf-8")
            + b"\x00"
            + ownership.subject.encode("utf-8")
        )
        digest = hmac.new(self._key, canonical, hashlib.sha256).hexdigest()[:32]
        return validate_trust_domain(f"principal-{digest}")


__all__ = [
    "MAX_OWNERSHIP_COMPONENT_BYTES",
    "MIN_DERIVATION_KEY_BYTES",
    "TrustedOwnership",
    "TrustDomainDeriver",
]
