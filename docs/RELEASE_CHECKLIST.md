# StateBraid v0.1 Release Checklist

Use this checklist against the exact candidate commit. A checked item requires
mechanical evidence; prose confidence is not a substitute.

## Source and contract

- [ ] working tree is clean and candidate SHA is recorded;
- [ ] Compute Contract v0.1 tests pass;
- [ ] Supported Scope v0.1 tests pass and no support claim was widened implicitly;
- [ ] StateBraid remains default-off in the reference runtime;
- [ ] trust-domain isolation/security wording remains intact;
- [ ] LFL/task/evidence/execution semantics remain outside StateBraid ownership.

## Deterministic gates

- [ ] full zero-MLX unit suite passes;
- [ ] Pyright reports 0 errors / 0 warnings / 0 informations;
- [ ] compile checks pass;
- [ ] source/privacy gate passes;
- [ ] all required GitHub Actions checks pass on the candidate PR;
- [ ] all required GitHub Actions checks pass again on merged `main`.

## Licensing and package metadata

- [ ] `LICENSE` contains the StateBraid MIT license;
- [ ] `THIRD_PARTY_NOTICES.md` retains the Apple Inc. mlx-lm MIT notice;
- [ ] `pyproject.toml` declares SPDX `license = "MIT"`;
- [ ] PEP 639 `license-files` includes both legal files;
- [ ] project version equals `statebraid.__version__`;
- [ ] README long description, authors, project URLs, keywords and Python
      classifiers are present;
- [ ] no deprecated `License ::` classifier is present.

## Built artifacts

- [ ] wheel and sdist build from a fresh checkout of the candidate SHA;
- [ ] wheel metadata has `License-Expression: MIT`;
- [ ] wheel metadata lists both legal files with `License-File` headers;
- [ ] wheel physically contains both legal files;
- [ ] sdist physically contains both legal files;
- [ ] wheel contains `statebraid/support.py` and the frozen MLX reference patch;
- [ ] installed `statebraid-doctor scope --json` matches source metadata;
- [ ] installed zero-MLX `statebraid-doctor mlx` fails closed as incompatible.

## Repository protection and privacy

- [ ] private/public repository visibility is intentionally chosen for this release;
- [ ] `main` protection and required checks are still enforced for everyone;
- [ ] force-push and branch deletion remain disabled;
- [ ] privacy scan finds no local user paths, credentials, tokens or private keys;
- [ ] release diff contains no experiment logs, local model files or research-only
      artifacts.

## Tag/release gate

- [ ] final release-readiness audit has passed with no P0 blocker;
- [ ] changelog entry matches the candidate version;
- [ ] tag name will be exactly `v{distribution-version}`;
- [ ] tag target is the exact protected-main SHA with successful required checks;
- [ ] no existing published version/tag is being reused or moved.

Until every applicable item above is satisfied, do **not** create the formal v0.1
tag, GitHub Release or public package-index upload.
