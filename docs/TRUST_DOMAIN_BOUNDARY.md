# StateBraid Trust-Domain Boundary

## Status

Qualified for the current v0.1
`Ornith-1.5-35B-A3B-MLX` Qwen3.6-derived hybrid/non-trimmable MLX reference path.
This trust-domain result does not widen the model-family support claim beyond the
profile in [`SUPPORTED_SCOPE_V0_1.md`](SUPPORTED_SCOPE_V0_1.md).

StateBraid cache identity remains mechanical: an exact token sequence belongs to
an explicit cache namespace. The MLX integration now composes that namespace from
the backend/model identity and a request-scoped trust-domain token.

## Request contract

StateBraid-enabled MLX requests may include:

```json
{"cache_namespace": "tenant-a"}
```

The field is a StateBraid serving extension, not model-visible semantic content.
When omitted, the integration uses the stable `local-default` domain so existing
single-user/local clients remain compatible.

An explicit namespace must:

- be a string;
- contain 1 to 128 ASCII bytes;
- begin with a letter or digit;
- contain only letters, digits, `.`, `_`, `:`, or `-`.

Empty, ambiguous, control-character, Unicode, path-like, or oversized values are
rejected. StateBraid does not trim, case-fold, normalize, or semantically classify
the token.

## Isolation mechanics

The cache key is conceptually:

```text
CacheNamespace(backend_identity, trust_domain) + exact prompt tokens
```

The compound namespace is the first key used by the backend prompt-cache trie.
Therefore a request in `tenant-b` cannot first fetch KV inserted under `tenant-a`
and then rely on a later policy check; the two domains are physically distinct
lookup roots.

The model-loading identity remains separate and unchanged. Trust-domain isolation
changes cache lookup/storage identity only.

## Security boundary

`cache_namespace` is an **isolation primitive, not authentication**.

A local single-user client may rely on the default namespace. A multi-user or
multi-tenant deployment must have a trusted harness/gateway derive and inject the
namespace from its authenticated ownership boundary. If an untrusted caller can
freely choose another tenant's namespace token, StateBraid does not itself prove
that caller is authorized to join that namespace.

StateBraid deliberately does not inspect user identity, task meaning, evidence,
or session semantics to derive this value.

## Qualification evidence

Deterministic gates cover:

- same backend + same tokens + different domains => no cache hit;
- same domain => normal prefix/exact reuse;
- actual-prefix hit attribution remains namespace-local;
- hostile namespace input rejection;
- transactional rollback, concurrency, and generation-safe N-1 behavior remain
  unchanged.

The real 8901 canary used one Ornith instance and one StateBraid cache policy at a
time. With an identical 1,223-token prompt:

| Request | Namespace | Cached tokens | New prefill |
| --- | --- | ---: | ---: |
| A1 | `tenant-a` | 0 | 1,223 |
| A2 | `tenant-a` | 1,222 | 1 |
| B1 | `tenant-b` | 0 | 1,223 |
| B2 | `tenant-b` | 1,222 | 1 |
| A3 | `tenant-a` | 1,222 | 1 |
| D1 | default | 0 | 1,223 |
| D2 | default | 1,222 | 1 |

All requests finished normally, the StateBraid fatal scan was clean, and the
prior Cognitive 8901 runtime was restored afterwards.
