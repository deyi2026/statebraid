"""Mechanical compatibility probe for the optional MLX reference backend."""

from __future__ import annotations

import importlib
import importlib.metadata
from dataclasses import asdict, dataclass
from typing import Any, Callable

from statebraid.adapters.mlx import MLX_BACKEND_DESCRIPTOR
from statebraid.backend import BACKEND_CONTRACT_VERSION, capability_values
from statebraid.integrations.mlx import REFERENCE_MLX_BASE_SHA

REQUIRED_MLX_STORAGE_API_VERSION = "0.1"
REQUIRED_MLX_SERVER_API_VERSION = "0.1"


@dataclass(frozen=True)
class MLXCompatibilityReport:
    installed: bool
    compatible: bool
    mlx_lm_version: str | None
    storage_api_version: str | None
    server_api_version: str | None
    transactional_storage: bool
    request_namespace: bool
    reference_base_revision: str | None
    reference_runtime_qualified: bool | None
    reference_status: str | None
    reference_identity_match: bool
    issues: tuple[str, ...]
    backend_contract_version: str = BACKEND_CONTRACT_VERSION
    declared_capabilities: tuple[str, ...] = capability_values(
        MLX_BACKEND_DESCRIPTOR.capabilities
    )
    integration_level: str = MLX_BACKEND_DESCRIPTOR.integration_level

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _package_version() -> str | None:
    try:
        return importlib.metadata.version("mlx-lm")
    except importlib.metadata.PackageNotFoundError:
        return None


def probe_mlx_backend(
    *,
    importer: Callable[[str], Any] = importlib.import_module,
    version_reader: Callable[[], str | None] = _package_version,
) -> MLXCompatibilityReport:
    """Report whether the installed MLX backend satisfies StateBraid v0.1.

    Compatibility is capability-based.  A package version alone is never used
    as evidence that the backend exposes the required transactional storage,
    activation, or request-scoped namespace boundary.
    """

    version = version_reader()
    try:
        cache_module = importer("mlx_lm.models.cache")
    except Exception as exc:
        missing = isinstance(exc, (ImportError, ModuleNotFoundError))
        issue = (
            "mlx-lm is not importable"
            if missing
            else f"mlx-lm cache import failed: {type(exc).__name__}: {exc}"
        )
        return MLXCompatibilityReport(
            installed=(version is not None or not missing),
            compatible=False,
            mlx_lm_version=version,
            storage_api_version=None,
            server_api_version=None,
            transactional_storage=False,
            request_namespace=False,
            reference_base_revision=None,
            reference_runtime_qualified=None,
            reference_status=None,
            reference_identity_match=False,
            issues=(issue,),
        )

    issues: list[str] = []
    storage_api = getattr(cache_module, "STATEBRAID_STORAGE_API_VERSION", None)
    cache_type = getattr(cache_module, "LRUPromptCache", None)
    transactional = bool(
        cache_type is not None
        and callable(getattr(cache_type, "transactional_storage", None))
    )
    if storage_api != REQUIRED_MLX_STORAGE_API_VERSION:
        issues.append(
            "MLX transactional storage API must be "
            f"{REQUIRED_MLX_STORAGE_API_VERSION}; found {storage_api!r}"
        )
    if not transactional:
        issues.append("LRUPromptCache.transactional_storage() is unavailable")

    try:
        server_module = importer("mlx_lm.server")
    except Exception as exc:
        server_module = None
        issues.append(
            f"mlx-lm server import failed: {type(exc).__name__}: {exc}"
        )

    server_api = (
        getattr(server_module, "STATEBRAID_SERVER_API_VERSION", None)
        if server_module is not None
        else None
    )
    generation_args = (
        getattr(server_module, "GenerationArguments", None)
        if server_module is not None
        else None
    )
    dataclass_fields = getattr(generation_args, "__dataclass_fields__", {}) or {}
    request_namespace = "cache_namespace" in dataclass_fields
    reference_base_revision = (
        getattr(server_module, "STATEBRAID_REFERENCE_BASE_REVISION", None)
        if server_module is not None
        else None
    )
    reference_runtime_qualified = (
        getattr(server_module, "STATEBRAID_REFERENCE_RUNTIME_QUALIFIED", None)
        if server_module is not None
        else None
    )
    reference_status = (
        getattr(server_module, "STATEBRAID_REFERENCE_STATUS", None)
        if server_module is not None
        else None
    )
    reference_identity_match = bool(
        reference_base_revision == REFERENCE_MLX_BASE_SHA
        and reference_runtime_qualified is True
        and reference_status == "reference_qualified"
    )
    if server_api != REQUIRED_MLX_SERVER_API_VERSION:
        issues.append(
            "MLX StateBraid server API must be "
            f"{REQUIRED_MLX_SERVER_API_VERSION}; found {server_api!r}"
        )
    if not request_namespace:
        issues.append("server request-scoped cache_namespace capability is unavailable")
    if reference_base_revision != REFERENCE_MLX_BASE_SHA:
        issues.append(
            "MLX StateBraid reference base must be "
            f"{REFERENCE_MLX_BASE_SHA}; found {reference_base_revision!r}"
        )
    if reference_runtime_qualified is not True:
        issues.append(
            "MLX StateBraid reference runtime qualification marker must be true; "
            f"found {reference_runtime_qualified!r}"
        )
    if reference_status != "reference_qualified":
        issues.append(
            "MLX StateBraid reference status must be 'reference_qualified'; "
            f"found {reference_status!r}"
        )

    return MLXCompatibilityReport(
        installed=True,
        compatible=not issues,
        mlx_lm_version=version,
        storage_api_version=storage_api,
        server_api_version=server_api,
        transactional_storage=transactional,
        request_namespace=request_namespace,
        reference_base_revision=reference_base_revision,
        reference_runtime_qualified=reference_runtime_qualified,
        reference_status=reference_status,
        reference_identity_match=reference_identity_match,
        issues=tuple(issues),
    )
