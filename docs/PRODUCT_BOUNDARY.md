# StateBraid v0.1 Product Boundary

## Product statement

StateBraid is an **agent-aware compute-continuity runtime** for long-running local
agents. It preserves mechanical model-serving state so repeated work can reuse
valid compute without introducing a second semantic decision system.

The v0.1 boundary exists to keep StateBraid narrow: it is not a second agent
harness, memory system, planner, or task-state authority.

## What StateBraid owns

### 1. Exact compute identity

Cache identity is mechanical. A cache key is defined by an ownership/trust
namespace and the exact token sequence. StateBraid may match and credit only the
prefix actually served.

Semantic labels from an upstream agent harness do not redefine cache identity.

### 2. Stable and active compute continuity

StateBraid manages two important transient roles:

- **stable**: a reusable shared prefix whose value has been established from
  observed reuse facts;
- **active**: the exact current successor/tail needed to continue generation
  safely.

Stable admission and active replacement are based on exact token lineage,
observed reuse, and resource pressure, not task meaning.

### 3. Bounded KV/prompt-cache residency

StateBraid owns mechanical cache residency under independent constraints:

- sequence-slot capacity;
- byte capacity;
- transient reserve;
- optional operator-declared mechanical pin roles.

Hard resource limits ultimately win. A long-lived entry must not silently starve
all transient capacity.

### 4. Transactional cache mutation

Admission, eviction, trim, backend mutation and policy bookkeeping form one
transactional boundary. Failed mutation must restore both backend state and
policy state rather than leaving split-brain cache bookkeeping.

### 5. Generation-safe reuse

An exact cache hit must still leave valid generation input. For the validated
hybrid/non-trimmable MLX path, an exact N hit is recovered through an N-1
checkpoint plus one replay token, or through full recompute when no safe shorter
checkpoint exists.

### 6. Factual compute telemetry

StateBraid may expose facts such as cache mode, cache-hit tokens, stable/active
entry counts, bytes, admissions, evictions, or generation replay tokens.

Telemetry is observational. StateBraid does not use telemetry to decide task
strategy, evidence relevance, tool choice, fold policy, or task completion.

## What the agent harness owns

Task/evidence/execution continuity is outside StateBraid. The agent harness owns,
when those capabilities exist:

- selected raw evidence and evidence provenance;
- fold/receipt projection and recovery;
- working-state/checkpoint storage and projection;
- provider-interruption and partial-output continuation;
- durable Session/EventLog state;
- Goal/handoff state;
- SubAgent ownership and orchestration;
- ExecutionWorkspace state;
- tool protocol and task lifecycle state.

A harness may use StateBraid as its serving runtime without giving StateBraid
semantic authority over any of those mechanisms.

## What the model owns

The model keeps semantic judgment:

- what evidence matters;
- whether evidence is sufficient;
- task strategy;
- tool choice;
- what state to preserve when the harness offers a model-authored capability;
- whether to continue or answer.

StateBraid does not infer these decisions from cache state, request labels, or
telemetry.

## Integration boundary

The intended relationship is:

```text
Agent harness
  owns task / evidence / execution continuity
          |
          | serving requests + opaque semantic content
          v
StateBraid Runtime
  owns compute continuity only
          |
          | backend cache/storage operations
          v
Model-serving backend
```

StateBraid should not require an LFL-specific Python dependency. The current LFL
integration is a qualification client that verifies compute changes do not alter
observable agent behavior.

## Validated v0.1 scope

The current production canary/qualification evidence covers the Ornith/Qwen
hybrid non-trimmable MLX path with:

- explicit opt-in StateBraid activation;
- StateBraid and CognitivePromptCache as mutually exclusive policy owners;
- StateBraid default-off;
- exact-hit N-1 generation safety;
- stable/active reuse under sequence and byte budgets;
- semantic blindness to legacy `cache_tag` values;
- successful rollback to the Cognitive control after qualification.

Generic trimmable-KV production parity is not yet claimed.

## Success criteria

A v0.1 compute candidate should demonstrate all of the following:

1. warm stable-prefix reuse without ownership/trust-domain contamination;
2. bounded residency under both sequence and byte pressure;
3. stable/active lineage based on exact tokens rather than semantic labels;
4. correct rollback after failed cache mutation;
5. generation-safe exact hits;
6. factual telemetry that distinguishes reported cache reuse from unknown values;
7. no semantic cache authority from agent-layer labels;
8. unchanged agent completion/evidence/tool behavior in a frozen integration
   qualification when compute policy is the only intended variable.

The last criterion is a regression gate, not a transfer of agent semantics into
StateBraid.

## Tagline interpretation

**Less recompute. Less redo.** remains the project tagline. StateBraid directly
implements the first half by preserving compute continuity. The second half is a
system-level outcome achieved when a continuity-aware agent harness uses a
compute runtime without losing its own task/evidence/execution state.
