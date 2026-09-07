"""Backend capability contracts and reusable conformance tooling."""

from .contract import (
    BACKEND_CONTRACT_VERSION,
    BACKEND_OWNS,
    STATEBRAID_OWNS,
    BackendCapability,
    BackendDescriptor,
    BackendObservationProfile,
    BackendQualificationProfile,
    LookupObservation,
    ObservationMode,
    PrefixLookupBackend,
    TransactionalMutationBackend,
    UnsupportedBackendCapability,
    capability_values,
)
from .conformance import (
    BackendConformanceDriver,
    BackendConformanceReport,
    ConformanceFailure,
    ConformanceResult,
    ConformanceStatus,
    DriverFactory,
    run_backend_conformance,
)

__all__ = [
    "BACKEND_CONTRACT_VERSION",
    "BACKEND_OWNS",
    "STATEBRAID_OWNS",
    "BackendCapability",
    "BackendConformanceDriver",
    "BackendConformanceReport",
    "BackendDescriptor",
    "BackendObservationProfile",
    "BackendQualificationProfile",
    "ConformanceFailure",
    "ConformanceResult",
    "ConformanceStatus",
    "DriverFactory",
    "LookupObservation",
    "ObservationMode",
    "PrefixLookupBackend",
    "TransactionalMutationBackend",
    "UnsupportedBackendCapability",
    "capability_values",
    "run_backend_conformance",
]
