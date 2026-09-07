"""Command-line compatibility diagnostics for StateBraid backends."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from statebraid.adapters.llama_cpp import LLAMA_CPP_BACKEND_DESCRIPTOR
from statebraid.adapters.mlx import MLX_BACKEND_DESCRIPTOR
from statebraid.backend import BACKEND_CONTRACT_VERSION, BACKEND_OWNS, STATEBRAID_OWNS
from statebraid.compat.llama_cpp import probe_llama_cpp_server
from statebraid.compat.mlx import probe_mlx_backend
from statebraid.support import support_scope


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="statebraid-doctor")
    subparsers = parser.add_subparsers(dest="backend", required=True)
    mlx = subparsers.add_parser("mlx", help="check the installed MLX backend")
    mlx.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    llama = subparsers.add_parser(
        "llama-cpp", help="check a running llama-server public API"
    )
    llama.add_argument(
        "--url", default="http://127.0.0.1:8080", help="llama-server base URL"
    )
    llama.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    contract = subparsers.add_parser(
        "contract", help="show the backend capability contract"
    )
    contract.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    scope = subparsers.add_parser("scope", help="show the v0.1 support boundary")
    scope.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.backend == "contract":
        report = {
            "backend_contract_version": BACKEND_CONTRACT_VERSION,
            "statebraid_owns": list(STATEBRAID_OWNS),
            "backend_owns": list(BACKEND_OWNS),
            "known_adapters": [
                MLX_BACKEND_DESCRIPTOR.to_dict(),
                LLAMA_CPP_BACKEND_DESCRIPTOR.to_dict(),
            ],
            "qualification_note": (
                "capability declaration does not widen the separately versioned support scope"
            ),
        }
        if args.json:
            print(json.dumps(report, sort_keys=True))
        else:
            print(f"StateBraid backend contract: {BACKEND_CONTRACT_VERSION}")
            for descriptor in (MLX_BACKEND_DESCRIPTOR, LLAMA_CPP_BACKEND_DESCRIPTOR):
                print(f"known adapter: {descriptor.name} ({descriptor.integration_level})")
                for item in descriptor.to_dict()["capabilities"]:
                    print(f"capability[{descriptor.name}]: {item}")
        return 0

    if args.backend == "llama-cpp":
        report = probe_llama_cpp_server(args.url)
        if args.json:
            print(json.dumps(report.to_dict(), sort_keys=True))
        else:
            verdict = "compatible" if report.compatible else "incompatible"
            print(f"llama.cpp capability profile: {verdict}")
            print(f"audited reference: {report.reference_sha}")
            print(f"running source: {report.source_commit or 'unknown'}")
            print(
                "reference source match: "
                f"{'yes' if report.reference_source_match else 'no'}"
            )
            print(f"slots endpoint: {'yes' if report.slots_endpoint else 'no'}")
            print(f"slot count: {report.slot_count}")
            print(f"reported total slots: {report.total_slots or 'unknown'}")
            print("namespace isolation: no")
            print("single-domain only: yes")
            print("runtime qualified: no")
            print(f"integration level: {report.integration_level}")
            for issue in report.issues:
                print(f"issue: {issue}")
        return 0 if report.compatible else 2

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
