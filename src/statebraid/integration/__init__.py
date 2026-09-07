"""Harness integration boundary for compute-only StateBraid use."""

from .contract import (
    FORBIDDEN_SEMANTIC_FIELDS,
    HARNESS_INTEGRATION_CONTRACT_VERSION,
    BackendCompatibilityVerdict,
    HarnessComputeFacts,
    HarnessComputeRequest,
    IntegrationContractViolation,
    MechanicalResourceConstraints,
    check_backend_compatibility,
    integration_contract_metadata,
)
from .identity import (
    MAX_OWNERSHIP_COMPONENT_BYTES,
    MIN_DERIVATION_KEY_BYTES,
    TrustedOwnership,
    TrustDomainDeriver,
)

__all__ = [
    "FORBIDDEN_SEMANTIC_FIELDS",
    "HARNESS_INTEGRATION_CONTRACT_VERSION",
    "MAX_OWNERSHIP_COMPONENT_BYTES",
    "MIN_DERIVATION_KEY_BYTES",
    "BackendCompatibilityVerdict",
    "HarnessComputeFacts",
    "HarnessComputeRequest",
    "IntegrationContractViolation",
    "MechanicalResourceConstraints",
    "TrustedOwnership",
    "TrustDomainDeriver",
    "check_backend_compatibility",
    "integration_contract_metadata",
]
