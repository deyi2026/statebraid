# Harness ↔ StateBraid Integration Contract v0.1

This contract freezes the semantic boundary between an agent harness (LFL or any
other harness) and StateBraid.

The rule is intentionally strict:

> **Harness chooses and understands the task. StateBraid receives only mechanical
> compute identity/constraints and returns only mechanical compute facts.**

The contract is implemented in `statebraid.integration` and has no dependency on
LFL.

## Allowed harness → StateBraid inputs

Only these categories cross the boundary:

1. **backend identity** — an already selected, bounded mechanical backend identity;
2. **trusted ownership / trust-domain identity** — the cache isolation boundary,
   not task semantics;
3. **exact token/request identity** — exact token IDs used for compute identity;
4. **mechanical resource constraints** — sequence, byte, and transient-reserve
   limits.

`HarnessComputeRequest` has no extension bag. Unknown fields fail closed.
`MechanicalResourceConstraints` also has a closed schema.

Backend selection is deliberately **not** a StateBraid responsibility. A harness,
operator, or external serving gateway chooses the backend first. StateBraid may run
`check_backend_compatibility()` against that already-selected backend descriptor;
it does not rank providers, inspect the prompt, or choose a model.

### Identity provenance invariant

The shape checks in this contract do not prove semantic provenance. Therefore:

- `backend_identity` must come from a trusted operator/configured serving-backend
  identity after backend selection has already happened outside StateBraid. It must
  not be synthesized by StateBraid from prompt/task meaning or used by StateBraid
  to perform semantic model routing.
- `trust_domain` must come from a trusted authentication/ownership boundary (or
  from the mechanical trusted-ownership derivation below). StateBraid validates
  its bounded identity shape and isolation use; it does not authenticate the
  caller or infer tenant/task meaning from the token.

A syntactically valid identity string can still be misused by a faulty Harness.
Preventing that misuse is an integration/deployment responsibility, not an excuse
for StateBraid to inspect task semantics.

## Allowed StateBraid → harness outputs

`HarnessComputeFacts` may expose only factual compute continuity information:

- actual reused token prefix when known;
- cache-hit token count when actually reported/known;
- admission fact;
- eviction count;
- generation replay/recompute token fact;
- resident sequence count;
- resident byte count.

Unknown facts stay `None`. The schema does not contain narrative recommendation,
reason, summary, strategy, or task-state fields.

When both an actual reused prefix and cache-hit token count are present, they must
agree mechanically. A reported reused prefix must be an exact prefix of the request
token sequence.

## Forbidden semantic inputs and outputs

The v0.1 machine contract explicitly rejects these semantic/control-plane fields:

```text
goal
task_status
task_strategy
evidence_importance
selected_evidence
working_state
working_state_summary
checkpoint_meaning
tool_relevance
completion_state
next_action
fold_decision
retry_desirability
cache_tag
```

This list is not an invitation to rename semantic state. Any equivalent task,
evidence, planning, completion, tool, fold, retry, or checkpoint meaning remains
Harness/model-owned even if spelled differently.

In particular, a StateBraid-enabled serving path must **never** derive cache
admission, residency, eviction, or reuse authority from legacy semantic
`cache_tag` values such as `goal`, `evidence`, `identity`, `rules`, or `summary`.
Those tags may remain in legacy Cognitive research/control paths, but they do not
cross this integration contract.

## Trusted ownership → trust domain

`TrustedOwnership` and `TrustDomainDeriver` are optional mechanical primitives.
They do **not** authenticate a user, parse credentials, authorize a task, or decide
which backend to use.

A deployment first authenticates ownership outside StateBraid. It may then provide
an opaque trusted `(issuer, subject)` pair. StateBraid can derive:

```text
principal-<first 128 bits of HMAC-SHA256(issuer NUL subject)>
```

using a deployment key. Raw ownership strings do not appear in the derived trust
domain. Local single-user mode maps mechanically to `local-default`.

A harness may instead provide an already trusted `trust_domain` directly. The
important invariant is that an untrusted ordinary request cannot self-assign cache
ownership.

## Backend capability gate

`check_backend_compatibility()` answers only:

```text
For this already-selected backend identity and this declared mechanical operation,
which required Backend Contract capabilities are missing?
```

It never answers:

- which backend is best;
- which model is best for the task;
- whether to retry or fallback;
- whether the evidence is sufficient;
- whether the task is complete.

Those remain external serving/harness decisions.

## Cross-layer acceptance rule

A proposed integration feature belongs in StateBraid only if all of the following
are true:

1. its input can be expressed entirely with the allowed mechanical request schema;
2. its output can be expressed entirely with factual compute fields;
3. it does not require understanding task/evidence/tool/checkpoint semantics;
4. it does not choose a backend/model from prompt meaning;
5. it does not make cache telemetry an authority over task behavior.

If any condition fails, the feature belongs in the Harness, model, or external
serving gateway instead.

## LFL qualification interpretation

LFL may be used as an unchanged integration client to test the boundary. Such a
qualification may compare tool-call count, tool receipts, evidence provenance,
SubAgent settlement, external execution facts, interruption continuity, completion,
and cache/new-prefill telemetry under StateBraid ON/OFF.

Those are **regression signals**, not StateBraid-owned state. The expected result is
semantic equivalence in Harness behavior while only mechanical compute telemetry
changes.

The current committed read-only requalification used LFL
`22039c087adcdd60f0beb6f68848a3258e4262b5` and passed deterministic/static
continuity, cache/history/wire and full committed unit/static gates. A current-main
real-model StateBraid ON/OFF A/B was **not rerun**. Historical real-model ON/OFF
evidence remains scoped to immutable LFL snapshot
`5c8e8bc3344f27a2a2586d2e65c4a317353089a3`; it must not be relabeled as evidence
for `22039c0`. The live LFL dirty worktree is outside both claims.

Future requalification should continue to use committed Continuity Kernel state
without modifying LFL or enabling held model-authored working-state producers merely
for cache performance.

## Machine-readable inspection

```bash
statebraid-doctor integration --json
```

The output publishes the integration contract version, allowed input/output
categories, forbidden semantic fields, and the rule that backend selection is
external to StateBraid.
