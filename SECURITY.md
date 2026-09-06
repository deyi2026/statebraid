# Security and Privacy Boundary

StateBraid handles state that may contain private prompts, tool outputs, source code, and local paths. Correct cache reuse is therefore a security property, not only a performance feature.

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

- Cross-session cache hits must respect explicit ownership/trust boundaries.
- A cache hit must never cause content from another session to become conversational state.
- Evidence selection must preserve provenance and complete tool protocol groups.
- Provider interruption metadata must not be confused with human-authored text.
- Safety and authorization boundaries remain mechanical hard constraints even under an LLM-first policy.

## Before every remote push

Run a scoped privacy review of the exact commit range, not only the current worktree.
