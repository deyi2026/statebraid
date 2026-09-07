from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import tarfile
import zipfile
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private user path", re.compile(r"/Users/[A-Za-z0-9._-]+/")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")),
    ("GitHub token", re.compile(r"\bgh(?:p|o|u|s|r)_[A-Za-z0-9]{20,}\b")),
    ("OpenAI-like key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("AWS access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
)


def tracked_text_files() -> list[Path]:
    payload = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    paths: list[Path] = []
    for raw in payload.split(b"\0"):
        if not raw:
            continue
        path = ROOT / raw.decode("utf-8")
        if path.is_file():
            paths.append(path)
    return paths


def verify_source() -> None:
    from statebraid import COMPUTE_CONTRACT_VERSION, SUPPORT_SCOPE_VERSION
    from statebraid.integrations.mlx import REFERENCE_PATCH_SHA256, reference_patch_bytes
    from statebraid.support import support_scope

    if COMPUTE_CONTRACT_VERSION != "0.1":
        raise SystemExit(f"unexpected compute contract: {COMPUTE_CONTRACT_VERSION}")
    if SUPPORT_SCOPE_VERSION != "0.1":
        raise SystemExit(f"unexpected support scope: {SUPPORT_SCOPE_VERSION}")

    scope = support_scope()
    reference = scope["reference_runtime"]
    if reference["activation_default"] is not False:
        raise SystemExit("StateBraid activation must remain default-off")
    if reference["prompt_concurrency"] != 1 or reference["decode_concurrency"] != 1:
        raise SystemExit("reference concurrency scope drifted")

    patch_digest = hashlib.sha256(reference_patch_bytes()).hexdigest()
    if patch_digest != REFERENCE_PATCH_SHA256:
        raise SystemExit("packaged MLX reference patch digest drifted")

    violations: list[str] = []
    for path in tracked_text_files():
        data = path.read_bytes()
        if b"\0" in data:
            continue
        text = data.decode("utf-8", errors="replace")
        rel = path.relative_to(ROOT)
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                violations.append(f"{rel}: {label}")
    if violations:
        raise SystemExit("privacy scan failed:\n" + "\n".join(sorted(violations)))

    print("source_contracts=PASS")
    print("privacy_scan=PASS")


def _single(paths: list[Path], label: str) -> Path:
    if len(paths) != 1:
        raise SystemExit(f"expected exactly one {label}, found {len(paths)}")
    return paths[0]


def verify_artifacts(dist_dir: Path) -> None:
    from statebraid import __version__
    from statebraid.integrations.mlx import REFERENCE_PATCH_NAME, REFERENCE_PATCH_SHA256

    wheel = _single(sorted(dist_dir.glob("*.whl")), "wheel")
    sdist = _single(sorted(dist_dir.glob("*.tar.gz")), "sdist")

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        patch_path = f"statebraid/integrations/mlx/{REFERENCE_PATCH_NAME}"
        required = {
            "statebraid/support.py",
            patch_path,
        }
        missing = required - names
        if missing:
            raise SystemExit(f"wheel missing required files: {sorted(missing)}")

        patch_digest = hashlib.sha256(archive.read(patch_path)).hexdigest()
        if patch_digest != REFERENCE_PATCH_SHA256:
            raise SystemExit("wheel reference patch digest mismatch")

        metadata_paths = [name for name in names if name.endswith(".dist-info/METADATA")]
        entrypoint_paths = [name for name in names if name.endswith(".dist-info/entry_points.txt")]
        metadata_path = _single([Path(name) for name in metadata_paths], "wheel METADATA")
        entrypoint_path = _single([Path(name) for name in entrypoint_paths], "wheel entry_points")
        metadata = BytesParser(policy=default).parsebytes(archive.read(metadata_path.as_posix()))
        if metadata["Name"] != "statebraid":
            raise SystemExit(f"unexpected package name: {metadata['Name']!r}")
        if metadata["Version"] != __version__:
            raise SystemExit(f"unexpected package version: {metadata['Version']!r}")
        if metadata["Requires-Python"] != ">=3.11":
            raise SystemExit(f"unexpected Requires-Python: {metadata['Requires-Python']!r}")
        entries = archive.read(entrypoint_path.as_posix()).decode("utf-8")
        for command in ("statebraid-doctor", "statebraid-reference"):
            if command not in entries:
                raise SystemExit(f"wheel missing console script: {command}")

    with tarfile.open(sdist, "r:gz") as archive:
        names = archive.getnames()
        suffixes = (
            "/README.md",
            "/pyproject.toml",
            "/src/statebraid/support.py",
            f"/src/statebraid/integrations/mlx/{REFERENCE_PATCH_NAME}",
        )
        for suffix in suffixes:
            if not any(name.endswith(suffix) for name in names):
                raise SystemExit(f"sdist missing required path suffix: {suffix}")

    print(f"wheel={wheel.name}")
    print(f"sdist={sdist.name}")
    print("package_content=PASS")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("source")
    artifacts = sub.add_parser("artifacts")
    artifacts.add_argument("dist_dir", type=Path)
    args = parser.parse_args(argv)

    if args.command == "source":
        verify_source()
    else:
        verify_artifacts(args.dist_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
