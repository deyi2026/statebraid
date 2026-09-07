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


def _verify_distribution_metadata(metadata: object, version: str, label: str) -> None:
    get = getattr(metadata, "get")
    get_all = getattr(metadata, "get_all")
    if get("Name") != "statebraid":
        raise SystemExit(f"{label}: unexpected package name: {get('Name')!r}")
    if get("Version") != version:
        raise SystemExit(f"{label}: unexpected package version: {get('Version')!r}")
    if get("Requires-Python") != ">=3.11":
        raise SystemExit(f"{label}: unexpected Requires-Python: {get('Requires-Python')!r}")
    if get("License-Expression") != "MIT":
        raise SystemExit(
            f"{label}: unexpected License-Expression: {get('License-Expression')!r}"
        )
    license_headers = set(get_all("License-File", []))
    if not {"LICENSE", "THIRD_PARTY_NOTICES.md"}.issubset(license_headers):
        raise SystemExit(f"{label}: missing License-File headers: {sorted(license_headers)}")
    if get("Description-Content-Type") != "text/markdown":
        raise SystemExit(
            f"{label}: README long description is not text/markdown: "
            f"{get('Description-Content-Type')!r}"
        )
    if get("Author") != "StateBraid contributors":
        raise SystemExit(f"{label}: unexpected Author: {get('Author')!r}")
    keywords = get("Keywords") or ""
    for keyword in ("ai-agents", "inference", "kv-cache", "prompt-cache", "mlx"):
        if keyword not in keywords:
            raise SystemExit(f"{label}: missing keyword: {keyword}")
    project_urls = {
        value.split(",", 1)[0].strip()
        for value in get_all("Project-URL", [])
        if "," in value
    }
    for url_label in ("Homepage", "Repository", "Issues", "Changelog"):
        if url_label not in project_urls:
            raise SystemExit(f"{label}: missing Project-URL label: {url_label}")
    classifiers = set(get_all("Classifier", []))
    if any(value.startswith("License ::") for value in classifiers):
        raise SystemExit(f"{label}: deprecated License :: classifier must not be emitted")
    for minor in ("3.11", "3.12", "3.13", "3.14"):
        if f"Programming Language :: Python :: {minor}" not in classifiers:
            raise SystemExit(f"{label}: missing Python classifier: {minor}")
    if "StateBraid" not in str(getattr(metadata, "get_payload")()):
        raise SystemExit(f"{label}: missing README long description payload")


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
        _verify_distribution_metadata(metadata, __version__, "wheel")
        license_entries = {
            name.rsplit("/", 1)[-1]
            for name in names
            if ".dist-info/licenses/" in name
        }
        if not {"LICENSE", "THIRD_PARTY_NOTICES.md"}.issubset(license_entries):
            raise SystemExit(
                f"wheel missing physical license files: {sorted(license_entries)}"
            )
        entries = archive.read(entrypoint_path.as_posix()).decode("utf-8")
        for command in ("statebraid-doctor", "statebraid-reference"):
            if command not in entries:
                raise SystemExit(f"wheel missing console script: {command}")

    with tarfile.open(sdist, "r:gz") as archive:
        names = archive.getnames()
        suffixes = (
            "/CHANGELOG.md",
            "/LICENSE",
            "/docs/RELEASE_CHECKLIST.md",
            "/docs/RELEASE_PROCESS.md",
            "/THIRD_PARTY_NOTICES.md",
            "/README.md",
            "/pyproject.toml",
            "/src/statebraid/support.py",
            f"/src/statebraid/integrations/mlx/{REFERENCE_PATCH_NAME}",
        )
        for suffix in suffixes:
            if not any(name.endswith(suffix) for name in names):
                raise SystemExit(f"sdist missing required path suffix: {suffix}")
        root_pkg_info = _single(
            [Path(name) for name in names if name.count("/") == 1 and name.endswith("/PKG-INFO")],
            "root sdist PKG-INFO",
        )
        member = archive.extractfile(root_pkg_info.as_posix())
        if member is None:
            raise SystemExit("unable to read root sdist PKG-INFO")
        sdist_metadata = BytesParser(policy=default).parsebytes(member.read())
        _verify_distribution_metadata(sdist_metadata, __version__, "sdist")

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
