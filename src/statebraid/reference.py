"""Export version-bound backend reference integrations."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from statebraid.integrations.llama_cpp_managed import (
    MANAGED_LLAMA_CPP_BASE_SHA,
    MANAGED_LLAMA_CPP_BASE_TREE_SHA,
    MANAGED_LLAMA_CPP_PATCH_NAME,
    MANAGED_LLAMA_CPP_PATCH_SHA256,
    MANAGED_LLAMA_CPP_SOURCE_SHA,
    MANAGED_LLAMA_CPP_SOURCE_TREE_SHA,
    check_managed_patch,
    write_managed_patch,
)
from statebraid.integrations.mlx import (
    REFERENCE_MLX_BASE_SHA,
    REFERENCE_PATCH_NAME,
    REFERENCE_PATCH_SHA256,
    write_reference_patch,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="statebraid-reference")
    subparsers = parser.add_subparsers(dest="backend", required=True)
    mlx = subparsers.add_parser("mlx", help="export the qualified MLX reference patch")
    mlx.add_argument(
        "--output",
        default=REFERENCE_PATCH_NAME,
        help="destination path for the patch",
    )
    managed = subparsers.add_parser(
        "llama-cpp-managed",
        help="export the experimental frozen llama.cpp managed M1 patch",
    )
    managed.add_argument(
        "--output",
        default=MANAGED_LLAMA_CPP_PATCH_NAME,
        help="destination path for the patch",
    )
    managed.add_argument(
        "--check-base",
        help="optional exact llama.cpp base checkout to verify with git apply --check",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.backend == "mlx":
        destination = write_reference_patch(args.output)
        print(f"patch: {destination}")
        print(f"base: {REFERENCE_MLX_BASE_SHA}")
        print(f"sha256: {REFERENCE_PATCH_SHA256}")
        return 0
    if args.backend == "llama-cpp-managed":
        if args.check_base:
            check_managed_patch(args.check_base)
            print(f"apply-check: PASS ({Path(args.check_base).resolve()})")
        destination = write_managed_patch(args.output)
        print(f"patch: {destination}")
        print(f"base: {MANAGED_LLAMA_CPP_BASE_SHA}")
        print(f"base-tree: {MANAGED_LLAMA_CPP_BASE_TREE_SHA}")
        print(f"source: {MANAGED_LLAMA_CPP_SOURCE_SHA}")
        print(f"source-tree: {MANAGED_LLAMA_CPP_SOURCE_TREE_SHA}")
        print(f"sha256: {MANAGED_LLAMA_CPP_PATCH_SHA256}")
        return 0
    raise AssertionError(args.backend)  # pragma: no cover - argparse owns this boundary


if __name__ == "__main__":
    raise SystemExit(main())
