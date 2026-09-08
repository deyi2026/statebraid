"""Reference integration metadata for the qualified MLX backend."""

from __future__ import annotations

import hashlib
from importlib import resources
from pathlib import Path

REFERENCE_MLX_BASE_SHA = "7fb4be44d560e5b74595210f83cb6003a57e52a7"
REFERENCE_MLX_BASE_TREE_SHA = "a47df2a0f9f3658677721dac2d846cb3db6cab06"
REFERENCE_MLX_COMMIT_SHA = "404b970d12928d1c1db27317614982623abf0208"
REFERENCE_MLX_SOURCE_TREE_SHA = "9212fdfe2412aa711dff937ebf34044d9d00ed77"
REFERENCE_MLX_STORAGE_API_VERSION = "0.1"
REFERENCE_MLX_SERVER_API_VERSION = "0.1"
REFERENCE_PATCH_NAME = "mlx-lm-7fb4be44-statebraid-api-0.1.patch"
REFERENCE_PATCH_SHA256 = "7ae2816eabf76e1deb650257f32ca2209780c7cf4aef2ffa31e6509561584d8c"


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
    "REFERENCE_MLX_BASE_TREE_SHA",
    "REFERENCE_MLX_COMMIT_SHA",
    "REFERENCE_MLX_SERVER_API_VERSION",
    "REFERENCE_MLX_SOURCE_TREE_SHA",
    "REFERENCE_MLX_STORAGE_API_VERSION",
    "REFERENCE_PATCH_NAME",
    "REFERENCE_PATCH_SHA256",
    "reference_patch_bytes",
    "verify_reference_patch",
    "write_reference_patch",
]
