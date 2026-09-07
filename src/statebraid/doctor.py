"""Command-line compatibility diagnostics for StateBraid backends."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from statebraid.compat.mlx import probe_mlx_backend
from statebraid.support import support_scope


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="statebraid-doctor")
    subparsers = parser.add_subparsers(dest="backend", required=True)
    mlx = subparsers.add_parser("mlx", help="check the installed MLX backend")
    mlx.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    scope = subparsers.add_parser("scope", help="show the v0.1 support boundary")
    scope.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.backend == "scope":
        scope = support_scope()
        if args.json:
            print(json.dumps(scope, sort_keys=True))
        else:
            reference = scope["reference_runtime"]
            print(f"StateBraid support scope: {scope['support_scope_version']}")
            print(
                "reference runtime: "
                f"{reference['backend']} on {reference['platform']}"
            )
            print(
                "qualified model/cache: "
                f"{reference['model']} ({reference['model_lineage']}, "
                f"{reference['cache_shape']})"
            )
            print("activation default: off")
            for item in scope["unqualified_runtime_features"]:
                print(f"not qualified: {item}")
        return 0

    if args.backend != "mlx":  # pragma: no cover - argparse owns this boundary
        raise AssertionError(args.backend)

    report = probe_mlx_backend()
    if args.json:
        print(json.dumps(report.to_dict(), sort_keys=True))
    else:
        verdict = "compatible" if report.compatible else "incompatible"
        print(f"MLX backend: {verdict}")
        print(f"mlx-lm version: {report.mlx_lm_version or 'unknown'}")
        print(f"storage API: {report.storage_api_version or 'missing'}")
        print(f"server API: {report.server_api_version or 'missing'}")
        print(f"transactional storage: {'yes' if report.transactional_storage else 'no'}")
        print(f"request namespace: {'yes' if report.request_namespace else 'no'}")
        for issue in report.issues:
            print(f"issue: {issue}")
    return 0 if report.compatible else 2


if __name__ == "__main__":
    raise SystemExit(main())
