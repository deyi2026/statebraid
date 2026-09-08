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
- exact base SHA: `7fb4be44d560e5b74595210f83cb6003a57e52a7`;
- exact base tree: `a47df2a0f9f3658677721dac2d846cb3db6cab06`;
- local qualification commit: `404b970d12928d1c1db27317614982623abf0208`;
- qualified source tree: `9212fdfe2412aa711dff937ebf34044d9d00ed77`;
- storage capability API: `0.1`;
- server capability API: `0.1`;
- packaged patch:
  `mlx-lm-7fb4be44-statebraid-api-0.1.patch`;
- packaged patch SHA256:
  `7ae2816eabf76e1deb650257f32ca2209780c7cf4aef2ffa31e6509561584d8c`.

The qualification commit is provenance for the generated patch. It is not a
published fork dependency and does not need to exist on a remote for users to
apply the packaged patch.

This exact reference was requalified after the upstream migration described in
[`MLX_REFERENCE_REQUALIFICATION_2026-09-08.md`](MLX_REFERENCE_REQUALIFICATION_2026-09-08.md).
The migration replaces the previous exact MLX-LM reference identity; it does not
widen the v0.1 supported runtime profile.

## Install and materialize the reference patch

Install StateBraid from a source checkout or built wheel in the Python environment
that will also host the qualified MLX-LM backend:

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
git checkout 7fb4be44d560e5b74595210f83cb6003a57e52a7
git apply --check ../statebraid-mlx.patch
git apply ../statebraid-mlx.patch
python -m pip install .
```

Do not apply the v0.1 reference patch to a different MLX-LM commit and infer
compatibility from a clean apply. A different upstream SHA requires separate
qualification because server/cache behavior may have changed.

The `python -m pip install .` step is intentional: it installs the exact patched
checkout and its declared dependencies into the serving environment. Do not treat
`git apply` alone, or an unrelated pre-installed `mlx-lm`, as satisfying the v0.1
backend qualification. Run the compatibility doctor from this same environment.

## Compatibility gate

After the patched MLX-LM package is importable in the environment that will run
the server, run:

```bash
statebraid-doctor mlx
```

The doctor is capability-and-reference-identity based rather than package-version
string based. It requires all of the following:

- `STATEBRAID_STORAGE_API_VERSION == "0.1"`;
- `LRUPromptCache.transactional_storage()`;
- `STATEBRAID_SERVER_API_VERSION == "0.1"`;
- request-scoped `GenerationArguments.cache_namespace` support;
- `STATEBRAID_REFERENCE_BASE_REVISION` equal to the exact qualified upstream base;
- `STATEBRAID_REFERENCE_RUNTIME_QUALIFIED is True`;
- `STATEBRAID_REFERENCE_STATUS == "reference_qualified"`.

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
mechanism in [`SUPPORTED_SCOPE_V0_1.md`](SUPPORTED_SCOPE_V0_1.md). Passing the
backend capability doctor is necessary but is not, by itself, a claim that an
arbitrary model/cache/server configuration is v0.1 reference-qualified.
