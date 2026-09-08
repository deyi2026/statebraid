"""Frozen distribution artifact for the experimental llama.cpp managed M1 path."""

from __future__ import annotations

import hashlib
import subprocess
from importlib import resources
from pathlib import Path

MANAGED_LLAMA_CPP_BASE_SHA = "465e49b9cea78a68b9c244ffb48d0ee24a82873d"
MANAGED_LLAMA_CPP_BASE_TREE_SHA = "4e34a10914c334511b880e641a75260d0be6ad0e"
MANAGED_LLAMA_CPP_SOURCE_SHA = "04329aacab48f91c79cd33490c2b4b33b29a7ef5"
MANAGED_LLAMA_CPP_SOURCE_TREE_SHA = "f064027f09970857a7ed53bf258706084a530fdf"
MANAGED_LLAMA_CPP_PATCH_NAME = "llama.cpp-465e49b9-statebraid-managed-m1.patch"
MANAGED_LLAMA_CPP_PATCH_SHA256 = (
    "6ff061ba996ca5a2ae95dd930099507b31bf8f9aa933a48e628e12a5657bba76"
)


def managed_patch_bytes() -> bytes:
    return resources.files(__package__).joinpath(MANAGED_LLAMA_CPP_PATCH_NAME).read_bytes()


def verify_managed_patch() -> bool:
    return (
        hashlib.sha256(managed_patch_bytes()).hexdigest()
        == MANAGED_LLAMA_CPP_PATCH_SHA256
    )


def write_managed_patch(path: str | Path) -> Path:
    destination = Path(path)
    data = managed_patch_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != MANAGED_LLAMA_CPP_PATCH_SHA256:
        raise RuntimeError(
            "packaged llama.cpp managed M1 patch digest mismatch: "
            f"expected {MANAGED_LLAMA_CPP_PATCH_SHA256}, got {digest}"
        )
    destination.write_bytes(data)
    return destination


def check_managed_patch(checkout: str | Path) -> Path:
    """Verify the frozen M1 patch clean-applies to the exact audited base checkout."""

    if not verify_managed_patch():
        raise RuntimeError("packaged llama.cpp managed M1 patch digest mismatch")

    root = Path(checkout).resolve()
    if not root.is_dir():
        raise RuntimeError(f"llama.cpp checkout does not exist: {root}")

    def _git(*args: str, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    top = _git("rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise RuntimeError(
            "llama.cpp managed M1 apply-check requires a Git checkout: "
            + top.stderr.decode("utf-8", errors="replace").strip()
        )

    head = _git("rev-parse", "HEAD")
    actual = head.stdout.decode("ascii", errors="replace").strip()
    if head.returncode != 0 or actual != MANAGED_LLAMA_CPP_BASE_SHA:
        raise RuntimeError(
            "llama.cpp managed M1 patch requires exact base "
            f"{MANAGED_LLAMA_CPP_BASE_SHA}; got {actual or '<unknown>'}"
        )

    status = _git("status", "--porcelain")
    if status.returncode != 0 or status.stdout:
        raise RuntimeError("llama.cpp managed M1 apply-check requires a clean checkout")

    result = _git(
        "apply",
        "--check",
        "--whitespace=nowarn",
        "-",
        input_bytes=managed_patch_bytes(),
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"llama.cpp managed M1 patch does not apply cleanly: {detail}")
    return root


__all__ = [
    "MANAGED_LLAMA_CPP_BASE_SHA",
    "MANAGED_LLAMA_CPP_BASE_TREE_SHA",
    "MANAGED_LLAMA_CPP_PATCH_NAME",
    "MANAGED_LLAMA_CPP_PATCH_SHA256",
    "MANAGED_LLAMA_CPP_SOURCE_SHA",
    "MANAGED_LLAMA_CPP_SOURCE_TREE_SHA",
    "check_managed_patch",
    "managed_patch_bytes",
    "verify_managed_patch",
    "write_managed_patch",
]
