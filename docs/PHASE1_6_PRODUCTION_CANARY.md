# Phase 1.6 Production Activation Canary

## Status

Phase 1.6 verifies that the Phase 1 compute-continuity policy and Phase 1.5 MLX
storage adapter can run inside a real local MLX server without becoming the
default policy.

The activation remains **explicit opt-in**. The normal runtime was restored
after the canary.

## Activation boundary

The MLX companion uses one explicit activation flag. When disabled, the
existing server path is unchanged. When enabled:

- the storage object is a plain MLX prompt cache exposing the Phase 1.5
  transactional-storage capability;
- `MLXStateBraidPromptCache` becomes the prompt-cache facade seen by the server;
- StateBraid owns admission, eviction, sequence capacity, byte capacity, stable
  admission, active-lineage compaction, and hit accounting;
- MLX owns KV payload construction, nearest-prefix lookup, and exact storage;
- the server continues to choose mechanical segment/checkpoint timing;
- StateBraid and `CognitivePromptCache` are mutually exclusive;
- Phase 1.6 fails closed if quantized KV would force the unsupported single
  generation path.

The StateBraid package still does not access MLX-LM private trie, LRU, or byte
counter fields.

## Deterministic qualification

Before starting a model, the candidate passed:

- StateBraid standard-library suite: **26/26 PASS** in the zero-MLX path, with
  the real-MLX class skipped as designed;
- StateBraid Pyright: **0 errors / 0 warnings / 0 informations**;
- real MLX adapter suite: **10/10 PASS**;
- MLX cache / activation / launcher focused suite: **59/59 PASS**;
- new/modified MLX activation tests: Pyright **0/0/0**;
- MLX server static A/B: **41 existing errors -> 41 existing errors**, so the
  canary introduced no new server type diagnostics;
- compile and diff checks: PASS;
- StateBraid private-MLX-field scan: PASS;
- local-path / credential privacy scan: PASS.

The MLX static A/B intentionally does not expand Phase 1.6 into repairing
unrelated pre-existing type debt.

## Real cache canary

The real canary used one local model server at a time, with prompt and decode
concurrency both kept at one. No second benchmark model was started.

A new 881-token prompt family produced this sequence:

| Request | Relationship | Cached tokens | Result |
| --- | --- | ---: | --- |
| S1 | cold | 0 / 881 | correct |
| S2 | same system, different user | 862 / 881 | correct |
| S2 repeat | identical prompt | 880 / 881 | correct |
| S3 | same system, different user | 862 / 881 | correct |

This verifies both levels required by the product boundary:

- the shared stable prefix survives across different user turns instead of
  dropping to zero reuse;
- an identical warm prompt uses a generation-safe `N-1` cache hit.

Runtime logs showed one stable entry alongside active entries throughout the
sequence. Divergent active branches remained bounded by the StateBraid policy.
No `Traceback`, `IndexError`, `KeyError`, fatal Python error, or generation-thread
exception was observed.

## Read-only agent smoke

The canary then ran one real two-round read-only tool workflow:

1. the model selected `read_file` itself and requested the exact allowed
   fixture path;
2. the harness mechanically executed that read-only call;
3. the second model turn completed with the exact key `STATEBRAID_TOOL_OK` and
   value `42`.

The second round reported **334 cached tokens out of 395 prompt tokens**, so the
tool continuation also exercised warm-prefix continuity.

The first harness validator expected the key and value to be rendered as one
literal `KEY=VALUE` string and therefore reported a local assertion failure when
the model rendered separate `Key` and `Value` lines. Inspection of the actual
tool call and final answer showed the workflow itself was correct, so the model
was not rerun merely to satisfy formatting in the validator.

## Restoration

After the canary, the StateBraid-enabled process was stopped and the prior
Cognitive prompt-cache runtime was restarted from its original working tree.

The restored runtime then demonstrated a fresh **0 -> 233/234 (`N-1`)** cache
transition and recreated its cognitive stable/active entries with zero fatal
log matches. StateBraid was not left enabled.

## Decision

Phase 1.6 establishes **activation eligibility**, not default enablement.

The compute-continuity stack is now sufficiently grounded to stop changing its
policy surface while the next v0.1 pillar is developed. The recommended next
phase is selected-evidence context continuity, with the existing model-selected
raw-evidence design kept separate from cache-policy semantics.
