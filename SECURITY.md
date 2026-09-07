# Security and Privacy Boundary

StateBraid handles model-serving state derived from private prompts, tool outputs,
source code, and local paths. Correct cache reuse is therefore a security property,
not only a performance feature.

## Repository hygiene

Do not commit:

- API keys, tokens, passwords, cookies, or credential files;
- `.env` files;
- local model weights;
- raw production conversations or tool outputs;
- user-specific absolute paths when a relative or symbolic path is sufficient;
- generated audit/evidence data unless explicitly scrubbed and reviewed;
- private companion-memory repositories or their contents.

## Runtime principles

- Cross-session cache hits must respect explicit namespace/ownership/trust boundaries.
- `cache_namespace` is a cache-isolation token, not authentication; multi-tenant
  deployments must derive it from a trusted authenticated ownership boundary.
- A cache hit must never cause content from another trust domain to become visible as
  conversational state.
- Cache identity and reuse decisions are based on mechanical token/namespace facts,
  not semantic labels supplied by an agent harness.
- StateBraid and another cache policy must not silently own admission/eviction at the
  same time.
- Failed transactional mutation must restore both backend and policy state.
- Exact hits must remain generation-safe; an empty generation input is not a valid
  performance optimization.
- Factual cache telemetry must not be promoted into agent strategy or semantic
  decisions inside StateBraid.
- Safety, authorization, privacy, and hard resource limits remain mechanical hard
  constraints.

## Harness integration boundary

Harness/model semantics must not cross into StateBraid through integration metadata.
The Integration Contract rejects task/evidence/working-state/checkpoint/tool/
completion/fold/retry fields and legacy semantic `cache_tag` authority. Backend
selection is also external to StateBraid; the runtime may check an already-selected
backend's mechanical capabilities but must not route from prompt meaning.

Trusted ownership→trust-domain derivation is a mechanical cache-isolation helper,
not authentication. The caller must establish ownership in a trusted external
boundary before providing it to StateBraid.

## Agent-layer security boundary

Selected evidence, fold/receipt recovery, provider-interruption continuation,
Goal/handoff, SubAgent, ExecutionWorkspace, and durable session/event state are not
StateBraid responsibilities. Their protocol and privacy rules belong to the agent
harness. StateBraid should receive only the serving inputs and mechanical namespace
information required for safe compute reuse.

## Before every remote push

Run a scoped privacy review of the exact commit range, not only the current worktree.
