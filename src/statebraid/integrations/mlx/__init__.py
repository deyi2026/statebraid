"""Reference integration metadata for the qualified MLX backend."""

from __future__ import annotations

import hashlib
from importlib import resources
from pathlib import Path

REFERENCE_MLX_BASE_SHA = "6d21ce4b065a2e163fa6de76a9936c61aeb5784a"
REFERENCE_MLX_COMMIT_SHA = "7dc145e0b4786eb5a107a4a3002251ef062e6afe"
REFERENCE_MLX_STORAGE_API_VERSION = "0.1"
REFERENCE_MLX_SERVER_API_VERSION = "0.1"
REFERENCE_PATCH_NAME = "mlx-lm-6d21ce4-statebraid-api-0.1.patch"
REFERENCE_PATCH_SHA256 = "7c6968cea46141219f50f28e6d0b1c7f9e06813c6c18db74c648ec7b906b7e47"


def reference_patch_bytes() -> bytes:
    return resources.files(__package__).joinpath(REFERENCE_PATCH_NAME).read_bytes()


def verify_reference_patch() -> bool:
    return hashlib.sha256(reference_patch_bytes()).hexdigest() == REFERENCE_PATCH_SHA256


def write_reference_patch(path: str | Path) -> Path:
    destination = Path(path)
    data = reference_patch_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != REFERENCE_PATCH_SHA256:
        raise RuntimeError(
            "packaged MLX reference patch digest mismatch: "
            f"expected {REFERENCE_PATCH_SHA256}, got {digest}"
        )
    destination.write_bytes(data)
    return destination


__all__ = [
    "REFERENCE_MLX_BASE_SHA",
    "REFERENCE_MLX_COMMIT_SHA",
    "REFERENCE_MLX_SERVER_API_VERSION",
    "REFERENCE_MLX_STORAGE_API_VERSION",
    "REFERENCE_PATCH_NAME",
    "REFERENCE_PATCH_SHA256",
    "reference_patch_bytes",
    "verify_reference_patch",
    "write_reference_patch",
]
