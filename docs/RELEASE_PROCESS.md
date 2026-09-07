# StateBraid Release Process

## Purpose

This document defines versioning, tagging and release mechanics. It does not widen
the runtime support claim in `SUPPORTED_SCOPE_V0_1.md` and does not change Compute
Contract v0.1.

## Versioning policy

StateBraid distribution versions use PEP 440:

- development work may use `X.Y.Z.devN`;
- release candidates use `X.Y.ZrcN`;
- a final release uses `X.Y.Z`.

The package version in `pyproject.toml` and `statebraid.__version__` must be exact
matches. A published version is immutable and must never be reused for different
artifacts.

`COMPUTE_CONTRACT_VERSION` and `SUPPORT_SCOPE_VERSION` are compatibility-contract
versions, not distribution versions. A distribution version bump does not by
itself widen either contract.

## Branch and CI policy

`main` is protected. Release preparation must use a feature branch and pull
request. Before merge, all required GitHub checks must pass on an up-to-date
branch:

- `quality`;
- `contracts`;
- `privacy`;
- `package`;
- `tests / py3.11`;
- `tests / py3.12`;
- `tests / py3.13`;
- `tests / py3.14`.

No release procedure may disable those checks, force-push protected `main`, or
replace a failed gate with a manually asserted result.

## Tag policy

Release tags use `v{distribution-version}` exactly:

- release candidate example: `v0.1.0rc1`;
- final example: `v0.1.0`.

A release tag may be created only from a protected-`main` commit whose required CI
checks are successful and whose package artifacts were rebuilt from that exact
commit. Tags are immutable: do not delete/recreate or force-move a published tag.

This release-preparation phase intentionally advances source metadata to
`0.1.0rc1` **without creating a tag or GitHub Release**. Tagging is deferred until
the final release-readiness audit explicitly passes.

## Artifact policy

Every wheel and sdist must contain or declare:

- distribution version matching `statebraid.__version__`;
- `License-Expression: Apache-2.0`;
- both `LICENSE` and `THIRD_PARTY_NOTICES.md` as PEP 639 license files;
- README-derived Markdown long description;
- the StateBraid console scripts;
- the exact packaged MLX reference patch with its frozen SHA256;
- the same Python floor and supported-scope contract as the source tree.

The `package` CI job is the mechanical gate for these requirements. A locally
built artifact is evidence only when it is reproduced from the exact candidate
commit.

## Release sequence

1. Prepare changes on a feature branch.
2. Update `CHANGELOG.md` and version metadata.
3. Run deterministic tests, Pyright, privacy/source and package-content gates.
4. Push the feature branch and wait for all required GitHub checks.
5. Merge through the protected-main pull-request path.
6. Verify `main` CI again.
7. Perform the final fresh-clone release-readiness audit.
8. Only after that audit passes, create the matching immutable tag from the exact
   verified `main` SHA and create any public release/distribution artifacts.

Public package-index upload credentials and automated publishing are deliberately
outside this v0.1 release-preparation phase; they must not be introduced as hidden
CI secrets merely to declare the source tree release-ready.
