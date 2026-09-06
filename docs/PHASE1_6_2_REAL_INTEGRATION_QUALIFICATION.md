# Phase 1.6.2 -- Real LFL Integration Qualification

## Scope

Phase 1.6.2 qualifies StateBraid's mechanical compute-continuity policy through
an unchanged LFL agent path. LFL remains the owner of task, evidence, tool and
execution continuity. StateBraid remains blind to those semantics.

The qualification is intentionally limited to the already-supported
Ornith/Qwen hybrid non-trimmable MLX path. It does not claim generic trimmable
KV parity or make StateBraid the default production cache policy.

## Integrity of the comparison

An initial exploratory pair was discarded because the live LFL worktree changed
between the Cognitive and StateBraid arms while another executor was working on
that repository. No result from that pair is used for qualification.

The formal comparison instead used an immutable export of committed LFL revision:

`5c8e8bc3344f27a2a2586d2e65c4a317353089a3`

Both arms used the same:

- Ornith model and MLX server settings;
- `max_tokens=4096` and `max_iterations=8`;
- thinking enabled at the LFL request layer, with the server launcher left on
  its native model-thinking mode;
- prompt-cache size 8 and 4 GiB byte budget;
- read-only LFL source snapshot and provider definition;
- three tasks, prompts, tools and scoring rules;
- isolated fresh `DATA_DIR` per arm.

The only intended runtime difference was cache-policy ownership:

- Cognitive control: `CognitivePromptCache`;
- candidate: StateBraid mechanical policy through the Phase 1.6.1 MLX adapter.

The reusable harness is `bench/phase16_2_lfl_ab.py`. Raw result JSON, local
snapshots and server logs are deliberately not committed.

## Formal A/B result

| Metric | Cognitive | StateBraid |
| --- | ---: | ---: |
| Tasks completed | 3/3 | 3/3 |
| Evidence checks passed | 3/3 | 3/3 |
| Tool calls | 15 | 15 |
| Canonical duplicate tool calls | 0 | 0 |
| Truncated tasks | 0 | 0 |
| Input tokens | 144,467 | 144,467 |
| Output tokens | 5,839 | 5,839 |
| Cache-hit tokens | 103,872 | 103,872 |
| New-prefill tokens | 40,595 | 40,595 |
| Cache-hit ratio | 71.9002% | 71.9002% |
| Summed wall time | 223.021 s | 248.699 s |

For all three tasks, the result objects were exactly equal after ignoring only
`session_id` and `elapsed_seconds`. This includes final answers, tool-call
signatures, rounds, token accounting, completion checks and evidence checks.

The three tasks exercise:

1. the LFL legacy `cache_tag` contract;
2. working-state checkpoint consumer/producer wiring;
3. provider-truncation factual runtime continuity.

This is the important integration result: removing semantic cache authority from
StateBraid did not change LFL's observable agent behavior or cache reuse.

## Wall-time interpretation

The formal pair showed StateBraid 11.5% slower in summed wall time even though
the generated outputs, tool traces, input/output tokens, cache-hit tokens and
new-prefill tokens were identical. That single ordering is therefore not
enough to attribute the wall-time difference to cache policy.

A reverse-order replication of `cache_tag_contract` produced the opposite
direction:

| Reverse-order task | StateBraid | Cognitive |
| --- | ---: | ---: |
| Wall time | 34.102 s | 36.777 s |
| Input tokens | 21,715 | 21,715 |
| Cache-hit tokens | 13,305 | 13,305 |
| New-prefill tokens | 8,410 | 8,410 |
| Tool calls | 2 | 2 |

The reverse pair was again exactly equal apart from session ID and wall time.
The direction reversal means Phase 1.6.2 records wall time as noisy/order-sensitive
on this single workstation. It does **not** claim a StateBraid latency win, and
it does **not** find a reproducible StateBraid latency regression.

## Real exact-hit safety after P0 hardening

Phase 1.6.1 changed both semantic-tag handling and generation-safety ownership,
so Phase 1.6.2 repeated a real exact-hit canary on the StateBraid server.

The identical 575-token request deliberately carried legacy semantic
`cache_tag=rules` and `cache_tag=goal` values:

- cold request: `cached=0`, `new_prefill=575`, `finish_reason=stop`;
- exact repeat: `cached=574`, `new_prefill=1`, `finish_reason=stop`;
- both responses returned the expected exact content;
- server cache roles remained mechanical `system/user/assistant`, not
  `rules/goal`;
- fatal/traceback/IndexError/KeyError scan was clean.

This verifies the N-1 generation-safe replay path in the real Phase 1.6.1
StateBraid activation while also demonstrating that legacy semantic tags do not
recover cache-policy authority.

## Runtime restoration

After all StateBraid tests, the candidate server was stopped and the original
`/research/mlx-lm` Cognitive 8901 was restored. A bounded generation canary
completed with `finish_reason=stop`, Cognitive cache insertion markers were
present, and the fatal scan was clean.

## Qualification decision

**PASS for real LFL integration qualification.**

StateBraid has demonstrated, on the scoped Ornith/Qwen hybrid path:

- unchanged LFL task completion and evidence fidelity;
- unchanged tool behavior with zero canonical duplicate calls;
- identical cache-hit and new-prefill accounting against the Cognitive control;
- real N-1 exact-hit generation safety;
- semantic blindness to legacy `cache_tag` values;
- clean worker health and successful rollback to the prior runtime.

Phase 1.6.2 therefore qualifies the compute layer to enter **Compute Freeze**.
This qualification does not make StateBraid default-on, does not retire the
Cognitive control, and does not move LFL-owned evidence or task semantics into
StateBraid.
