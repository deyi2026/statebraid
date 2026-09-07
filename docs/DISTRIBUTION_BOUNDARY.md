# StateBraid v0.1 Distribution Boundary

## Purpose

StateBraid is distributed as an independent Python package. The package does not
vendor MLX-LM and does not assume that an arbitrary `mlx-lm` version is compatible.
The first backend integration is a version-bound reference patch against one clean
upstream MLX-LM commit.

The distribution boundary has three separate artifacts:

1. the `statebraid` Python package: compute policy, MLX adapter, compatibility
   probe, and the reference-patch resource;
2. an upstream MLX-LM checkout at the exact qualified base SHA plus the exported
   StateBraid reference patch;
3. explicit runtime activation through `MLX_LM_STATEBRAID=1`.

The research MLX-LM fork is **not** a StateBraid distribution artifact.

## Qualified reference

- upstream repository: `ml-explore/mlx-lm`;
- exact base SHA: `6d21ce4b065a2e163fa6de76a9936c61aeb5784a`;
- local qualification commit: `7dc145e0b4786eb5a107a4a3002251ef062e6afe`;
- storage capability API: `0.1`;
- server capability API: `0.1`;
- packaged patch:
  `mlx-lm-6d21ce4-statebraid-api-0.1.patch`;
- packaged patch SHA256:
  `7c6968cea46141219f50f28e6d0b1c7f9e06813c6c18db74c648ec7b906b7e47`.

The qualification commit is provenance for the generated patch. It is not a
published fork dependency and does not need to exist on a remote for users to
apply the packaged patch.

## Install and materialize the reference patch

During private release preparation, install StateBraid from a source checkout or
built wheel:

```bash
python -m pip install .
```

Export the exact reference patch shipped inside the installed package:

```bash
statebraid-reference mlx --output statebraid-mlx.patch
```

The command prints the required base SHA and the expected patch SHA256 before the
user applies it.

Prepare MLX-LM from the exact qualified upstream base:

```bash
git clone https://github.com/ml-explore/mlx-lm.git
cd mlx-lm
git checkout 6d21ce4b065a2e163fa6de76a9936c61aeb5784a
git apply --check ../statebraid-mlx.patch
git apply ../statebraid-mlx.patch
```

Do not apply the v0.1 reference patch to a different MLX-LM commit and infer
compatibility from a clean apply. A different upstream SHA requires separate
qualification because server/cache behavior may have changed.

## Compatibility gate

After the patched MLX-LM package is importable in the environment that will run
the server, run:

```bash
statebraid-doctor mlx
```

The doctor is capability-based rather than version-string-based. It requires all
of the following:

- `STATEBRAID_STORAGE_API_VERSION == "0.1"`;
- `LRUPromptCache.transactional_storage()`;
- `STATEBRAID_SERVER_API_VERSION == "0.1"`;
- request-scoped `GenerationArguments.cache_namespace` support.

The command exits `0` only when all requirements are present and exits `2` for an
incompatible or unpatched backend. `statebraid-doctor mlx --json` exposes the same
facts for automation.

## Activation

StateBraid remains default-off. Start the patched MLX-LM server with the explicit
activation environment variable:

```bash
MLX_LM_STATEBRAID=1 python -m mlx_lm.server --model <model> ...
```

When active, the reference integration constructs a plain MLX `LRUPromptCache`
storage object and places `MLXStateBraidPromptCache` above its versioned
transactional-storage capability. StateBraid is the sole admission/eviction
authority for that cache object.

Requests may carry the StateBraid extension:

```json
{"cache_namespace": "tenant-a"}
```

Missing `cache_namespace` uses the stable single-user default domain. In a
multi-tenant deployment, a trusted authenticated gateway or harness must derive
and inject the namespace. The namespace field is a cache-isolation primitive, not
an authentication mechanism.

## Rollback

Rollback does not require uninstalling StateBraid or reversing the patch. Stop the
server, unset the activation variable, and restart:

```bash
unset MLX_LM_STATEBRAID
python -m mlx_lm.server --model <model> ...
```

With StateBraid disabled, the reference patch uses the upstream/native
`LRUPromptCache` path. Native `insert_cache`, capacity enforcement, and server
behavior remain the control path and are covered by upstream regression tests.

## What is intentionally not distributed

The v0.1 reference patch does not contain:

- `CognitivePromptCache` or semantic `cache_tag` policy;
- Ornith-specific launch scripts or local model paths;
- the research embeddings endpoint or unrelated server experiments;
- LFL code or an LFL Python dependency;
- model weights, logs, conversations, benchmark outputs, credentials, or user
  paths.

The patch touches only the MLX prompt-cache storage capability, server activation,
and a reference integration test.

## Security boundary

The upstream MLX-LM HTTP server itself warns that it implements only basic
security checks. The reference integration does not turn it into a multi-tenant
authentication gateway. Production exposure must provide authentication,
authorization, transport security, and trusted `cache_namespace` derivation
outside StateBraid.

## Qualification evidence

Against the exact upstream base above:

- StateBraid reference contract: 9/9 PASS;
- StateBraid adapter on the real MLX cache: 14/14 PASS;
- upstream native `test_prompt_cache.py`: 24/24 before and after the patch;
- upstream native `test_server.py`: 27/27 before and after the patch;
- Pyright on upstream `server.py` + `cache.py`: 131 existing errors / 2 warnings
  before and 131 / 2 after, therefore zero new diagnostics;
- capability doctor: patched reference accepted; unpatched exact upstream base
  rejected with exit code 2;
- real clean-reference Ornith canary, one model at a time: for the same 1,844
  prompt tokens, `tenant-a` was cold `0` then exact-repeat `1,843` cached;
  switching to `tenant-b` was cold `0` then `1,843` cached; returning to
  `tenant-a` remained `1,843` cached; the default domain was `0 -> 1,843`.
  All seven candidate requests finished with `stop`, candidate fatal scan was
  zero, and the original Cognitive 8901 runtime was restored afterwards.

These gates define the distribution compatibility boundary. Model-family support
and broader runtime support claims are documented separately from the packaging
mechanism.
