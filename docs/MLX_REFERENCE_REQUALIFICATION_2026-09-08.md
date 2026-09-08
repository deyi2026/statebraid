# MLX reference requalification — 2026-09-08

## Decision

StateBraid v0.1 requalified its existing **narrow MLX reference runtime** on a
newer exact upstream `mlx-lm` base. This is a reference-identity replacement,
not a support-scope expansion.

The qualified source identity is:

- upstream base commit: `7fb4be44d560e5b74595210f83cb6003a57e52a7`;
- upstream base tree: `a47df2a0f9f3658677721dac2d846cb3db6cab06`;
- promoted patched-source commit: `404b970d12928d1c1db27317614982623abf0208`;
- promoted patched-source tree: `9212fdfe2412aa711dff937ebf34044d9d00ed77`;
- packaged patch SHA256:
  `7ae2816eabf76e1deb650257f32ca2209780c7cf4aef2ffa31e6509561584d8c`.

Applying the packaged patch to the exact base and staging the result produces
the exact promoted source tree above.

## Runtime profile held constant

The E4 requalification did **not** broaden the supported profile. The real-model
gate kept the same reference conditions:

- Apple Silicon / macOS;
- `Ornith-1.5-35B-A3B-MLX`, Qwen3.6-derived hybrid/non-trimmable cache shape;
- MLX batch generation;
- model-native thinking for Agent qualification;
- unquantized KV;
- prompt concurrency `1`, decode concurrency `1`;
- prompt cache size `8`, byte budget `4 GiB`;
- StateBraid activation explicit and default-off.

Quantized KV, generic trimmable-KV runtime parity, speculative decode,
non-batch generation, distributed execution, higher concurrency, multi-model
co-residency, broader model families, and non-macOS runtime qualification remain
outside the v0.1 reference-qualified profile.

## Strict-serial real-model evidence

Heavy inference was strictly serial: only one large model runtime was resident
at a time.

The frozen control and the new candidate produced identical token-level results
on the default-domain mechanical sequence:

| Case | Frozen control | New candidate |
| --- | ---: | ---: |
| cold A | `0 / 5781` cached | `0 / 5781` cached |
| exact A | `5780 / 5781` cached | `5780 / 5781` cached |
| shared-prefix B | `5766 / 5782` cached | `5766 / 5782` cached |
| A after B | `5780 / 5781` cached | `5780 / 5781` cached |

All four requests finished normally. The new candidate also passed explicit
trust-domain isolation: tenant A warmed independently, the identical tenant B
request remained cold, and returning to tenant A reused its exact prior prefix.

## Agent parity

A four-task read-only Agent A/B retained the same behavior shape in both arms:

- grounded tasks: `4 / 4` in both;
- completed within the fixed round budget: `2 / 4` in both;
- evidence checks: `9 / 18` in both;
- truncations: `0` in both;
- duplicate tool calls: `0` in both;
- tool errors: `0` in both.

The control made 46 tool calls and the candidate 43. New-prefill totals were
43,734 and 43,896 respectively. Wall-clock timing and exact tool trajectory are
treated as order/machine-sensitive observations, not qualification claims.

The historical immutable Phase 1.6.2 LFL qualification gate was also rerun on
the new candidate. It passed `3 / 3` completion, `3 / 3` evidence, 15 tool calls,
0 duplicates and 0 truncations. Candidate new-prefill was 40,270 tokens versus
the accepted historical baseline of 40,595, so the upstream migration did not
show a recompute regression on that formal gate.

## Promotion discipline

The real-model E4 tests ran against source commit `9934977739cd118714dd150992ae492f8ae008f8`
while it still declared `runtime_qualified=false` and
`candidate_requalification_pending`. Only after the gates passed was a separate
metadata-only promotion commit created. The promotion changes the reference
qualification marker/status and its contract tests; it does not change runtime
cache or generation logic.

The StateBraid Compute Contract remains `0.1`, Backend Contract remains `0.2`,
Harness Integration Contract remains `0.1`, and Supported Scope remains `0.1`.

## Evidence provenance

The privacy-safe research evidence used to prepare this public record had the
following SHA256 digests:

- compact JSON: `bdce9f3a2903b79abee2ad8a85e7d6dbb9aa260ff4f5b4f6f41798790e342003`;
- narrative Markdown: `f7759454da31458aeed94add95ce86f2e10f7f369ce600b312d26bfbbebea8fa`.

Raw runtime logs, local absolute paths, session identifiers, model reasoning,
and raw tool payloads are intentionally not part of this repository evidence.
