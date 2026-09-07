"""Export version-bound backend reference integrations."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.backend != "mlx":  # pragma: no cover - argparse owns this boundary
        raise AssertionError(args.backend)
    destination = write_reference_patch(args.output)
    print(f"patch: {destination}")
    print(f"base: {REFERENCE_MLX_BASE_SHA}")
    print(f"sha256: {REFERENCE_PATCH_SHA256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
