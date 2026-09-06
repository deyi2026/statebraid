# Phase 1.6.1 P0 Hardening

## Objective

Make StateBraid mechanically cache-aware but semantically blind before any
LFL -> StateBraid qualification is accepted.

The boundary is:

- StateBraid may observe exact token identity, matched-prefix reuse, lineage,
  byte usage, sequence usage and backend mutation success/failure;
- StateBraid must not assign higher residency value because an upstream agent
  labels bytes as `goal`, `rules`, `evidence` or `identity`;
- the MLX companion may keep legacy semantic tagging for
  `CognitivePromptCache`, because that implementation remains the rollback/A-B
  control;
- StateBraid and CognitivePromptCache remain mutually exclusive.

## P0 correction: semantic labels are not policy authority

`WorkingSetPolicy` now defaults to an empty `pin_roles` set. Built-in ranking
contains only mechanical cache roles used by the serving path:

- `assistant`
- `user`
- `system`
- `active`
- `stable`

An operator can still opt into an explicit mechanical pin contract by passing
`pin_roles`, but StateBraid does not ship semantic pin labels as defaults.

The MLX activation companion separates two switches:

- `working_set_cache_on`: CognitivePromptCache or StateBraid; controls only
  mechanical segment/checkpoint handling;
- `semantic_cache_tags_on`: CognitivePromptCache only; controls reading and
  promoting legacy `cache_tag` labels.

Therefore `rules`, `goal`, `evidence`, `identity`, and arbitrary custom tags are
ignored as policy inputs when StateBraid is active. A cold system segment still
arrives at the StateBraid working-set path as `system`, where reuse evidence can
establish the `stable` lane.

## P1 correction: one generation-safety source in StateBraid mode

When StateBraid is active, exact-hit generation safety is delegated to
`statebraid.adapters.mlx.generation_safe_prompt_cache_hit()`.

The existing MLX-local helper remains only for non-StateBraid control modes.
This keeps rollback behavior intact while preventing two StateBraid-mode
implementations of the same N-1 invariant from drifting.

## Capability scope

Phase 1.6/1.6.1 production evidence currently covers the **Ornith/Qwen hybrid
non-trimmable path**. The transactional storage facade deliberately bypasses
native MLX LRU eviction and prefix-pruning policy so StateBraid can own capacity
decisions. Trimmable-KV behavior therefore needs a separate parity phase before
StateBraid can claim generic MLX-model support.

## Deterministic qualification

The Phase 1.6.1 candidate is required to pass all of the following before a
real LFL integration A/B is allowed:

1. default semantic labels are not pinned or privileged in StateBraid core;
2. explicit operator pin roles still preserve the mechanical pin contract;
3. `rules`, `goal`, `evidence`, `identity`, and hostile custom `cache_tag`
   values do not change StateBraid system/user segmentation;
4. CognitivePromptCache control mode still observes its legacy tags;
5. StateBraid mode routes exact-hit safety through the StateBraid helper;
6. real MLX transactional storage retains rollback, concurrency and N-1 parity;
7. zero-MLX install/test and Pyright gates remain clean;
8. no StateBraid source accesses MLX private trie/LRU/byte-counter fields.

Current qualification results:

- StateBraid zero-MLX suite: **28 tests PASS** with the real-MLX class skipped
  as designed;
- StateBraid Pyright: **0 errors / 0 warnings / 0 informations**;
- MLX companion focused suite: **63/63 PASS**;
- StateBraid adapter against real MLX storage: **11/11 PASS**;
- modified MLX activation tests: Pyright **0/0/0**;
- MLX `server.py` static A/B: **42 existing errors -> 42 existing errors**,
  so Phase 1.6.1 adds no new server diagnostics;
- compile, diff, private-field and staged privacy/scope checks: PASS.

## Non-goals

This phase does not:

- change LFL code or configuration;
- remove CognitivePromptCache;
- make StateBraid the default 8901 policy;
- add selected-evidence, checkpoint, task-completion or fold decisions to
  StateBraid;
- enable 8-bit KV by default;
- claim trimmable-KV production parity.

The next phase is a strict serial integration qualification using the existing
LFL request path as an unmodified client.
