# StateBraid v0.1 Supported Scope

> **Backend Contract note:** Backend Contract v0.2 is additive adapter mechanics,
> not a broader runtime support claim. `statebraid-doctor contract --json` may show
> capabilities that are mechanically implemented while this document remains the
> authority for end-to-end qualification.

## Purpose

This document defines the boundary of the **v0.1 support claim**. It is narrower
than the backend-neutral StateBraid core API and narrower than what may happen to
work experimentally.

The distinction is deliberate:

- **core-supported** means the behavior is part of Compute Contract v0.1 and is
  covered by deterministic StateBraid tests;
- **reference-qualified** means the behavior has also passed the real MLX serving
  qualification described below;
- **conditional** means StateBraid provides the mechanical primitive, but a
  deployment must provide an external security or operational condition;
- **not qualified** means v0.1 makes no runtime support claim, even if a unit test,
  upstream feature, or experimental research path exists.

`statebraid-doctor mlx` answers whether an installed backend exposes the required
StateBraid capability contract. **Backend compatibility is necessary but not
sufficient for the v0.1 runtime support claim.** The deployment must also stay
inside the reference-qualified profile in this document.

The machine-readable form of this boundary is available from:

```bash
statebraid-doctor scope --json
```

and from `statebraid.support.support_scope()`.

## Supported core contract

The backend-neutral StateBraid core supports the frozen Compute Contract v0.1:

- exact cache identity from mechanical namespace + exact token sequence;
- actual-prefix cache-hit attribution;
- mechanically established stable-prefix reuse;
- exact active-successor lineage;
- independent sequence and byte residency limits;
- transactional cache mutation and rollback;
- generation-safe exact reuse;
- factual compute telemetry;
- backend adapters that preserve those invariants.

This core support does **not** imply that every backend, cache implementation,
model family, platform, or server mode is runtime-qualified.

The Python package declares `requires-python = ">=3.11"`. A per-minor Python CI
matrix is a separate release gate and is not implied by this support-scope phase.

## Reference-qualified runtime profile

| Area | v0.1 reference-qualified boundary |
| --- | --- |
| Backend | MLX through the packaged StateBraid reference integration |
| Upstream MLX-LM base | `6d21ce4b065a2e163fa6de76a9936c61aeb5784a` only |
| Reference patch SHA256 | `7c6968cea46141219f50f28e6d0b1c7f9e06813c6c18db74c648ec7b906b7e47` |
| Storage/server capability | StateBraid API `0.1` / `0.1`; `statebraid-doctor mlx` must pass |
| Platform | Apple Silicon / macOS |
| Qualified model | `Ornith-1.5-35B-A3B-MLX` |
| Model lineage | `Qwen3.6-derived`; this is **not a blanket Qwen-family support claim** |
| Cache shape | `hybrid/non-trimmable` |
| Generation path | MLX batch path only |
| Thinking | model-native thinking as used in qualification |
| KV mode | unquantized reference path |
| Prompt concurrency | prompt concurrency = 1 |
| Decode concurrency | decode concurrency = 1 |
| Prompt-cache sequence budget | 8 in the qualified reference profile |
| Prompt-cache byte budget | 4 GiB in the qualified reference profile |
| Activation | explicit `MLX_LM_STATEBRAID=1`; **default-off** |
| Rollback | unset activation and restart on native `LRUPromptCache` |
| Single-user namespace | missing `cache_namespace` -> `local-default` |
| Explicit trust-domain token | bounded ASCII token, maximum 128 bytes |

The qualification profile records the configuration for which end-to-end evidence
exists. The backend-neutral policy accepts other mechanical sequence/byte budgets,
but v0.1 does not turn every untested runtime configuration into a performance or
production qualification claim.

## Trust-domain support

### Single-user / single trust domain

This is reference-qualified. If the request omits `cache_namespace`, StateBraid
uses the stable `local-default` domain and keeps cache identity scoped by backend
identity + that domain + exact tokens.

### Multiple trust domains

The **cache-isolation primitive is reference-qualified**: the same model and exact
prompt tokens in `tenant-a` and `tenant-b` do not reuse each other's KV, while
same-domain repeats still reuse their own KV.

Multi-tenant deployment is nevertheless **conditional**, because
`cache_namespace` is not authentication. A trusted authenticated gateway or agent
harness must derive and inject the namespace from an identity/authorization
boundary. An untrusted caller must not be allowed to choose another tenant's cache
namespace arbitrarily.

StateBraid v0.1 does not provide authentication, authorization, TLS termination, or
a hardened internet-facing multi-tenant server.

## Agent-harness qualification

StateBraid has no LFL Python dependency and does not own task/evidence/execution
continuity. The real integration qualification used one immutable LFL client path
as a regression oracle to demonstrate that changing only the compute policy did
not change completion, evidence, tool-call, or cache-accounting behavior.

That evidence qualifies the compute integration; it does not make StateBraid an
LFL-specific runtime and does not claim that every third-party agent harness has
received the same end-to-end qualification.

## Explicitly not qualified for v0.1

The following are **outside the v0.1 runtime support claim**:

- arbitrary `mlx-lm` commits other than the exact reference base above;
- blanket support for all Qwen-derived models or all MLX models;
- generic trimmable-KV runtime parity;
- quantized-KV StateBraid runtime paths;
- draft-model or speculative-decoding paths;
- non-batch / single-generation StateBraid paths;
- distributed MLX execution;
- server concurrency profiles above prompt concurrency `1` and decode concurrency
  `1`;
- multi-model co-residency or concurrent multi-model serving;
- serving backends other than the qualified MLX reference;
- Linux/Windows runtime qualification for the MLX reference path;
- persistent cache recovery across a process restart;
- semantic cache ranking from `goal`, `rules`, `evidence`, `identity`, or other
  agent-layer labels;
- selected-evidence, fold/receipt, working-state/checkpoint, provider-interruption,
  Goal/handoff, SubAgent, ExecutionWorkspace, planning, tool-choice, or completion
  semantics;
- authentication, authorization, TLS, or tenant identity assignment.

### Important: deterministic algorithm coverage is not runtime qualification

StateBraid has deterministic tests for generation-safe behavior on both trimmable
and non-trimmable abstract cache shapes. Those tests protect the core contract.
They do **not** establish generic trimmable-KV production parity on real MLX model
implementations. v0.1 runtime qualification remains the hybrid/non-trimmable
reference profile above.

Likewise, `Qwen3.6-derived` describes the lineage of the exact qualified Ornith
canary model. It must not be shortened into a claim that “Qwen models are
supported.” A different Qwen-derived model/cache implementation requires its own
qualification evidence.

## Scope-widening rule

Compute Contract v0.1 remains frozen. This document constrains **where** that
contract is claimed to be runtime-qualified; it does not change the contract's
semantics.

Widening the support claim to another MLX-LM base, model/cache shape, KV mode,
generation path, concurrency profile, platform, or serving backend requires:

1. deterministic StateBraid contract tests;
2. backend compatibility/parity tests;
3. generation-safe real-model canary evidence;
4. trust-domain isolation evidence where shared serving is relevant;
5. agent-level regression qualification when cache behavior is harness-visible;
6. an explicit update to this support-scope contract and its machine-readable
   metadata.

“It imports”, “the patch applies”, “the model is Qwen-derived”, or “the backend
passes the capability doctor” is not sufficient evidence for a widened support
claim.
