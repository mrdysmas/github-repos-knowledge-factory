# Intake Shard Routing Decision (D5)

Decision date (UTC): 2026-02-24T19:58:27Z

## Decision

Keep canonical shard routing to two shards (`llm_repos`, `ssh_repos`) during the current pilot.
Do not introduce a third canonical shard yet.

Add and maintain `domain_hint` as metadata in intake lifecycle records now to preserve future split options.

## Why

- Current WS contracts and tooling are explicitly two-shard:
  - WS5 `target_shard` accepts only `llm_repos` or `ssh_repos`.
  - WS1 validator iterates only `llm_repos` and `ssh_repos`.
  - WS4 compiler merges only `llm_repos` and `ssh_repos`.
- Adding a shard immediately creates cross-contract migration work (schemas, validators, mappings, compile path) before pilot throughput is proven.
- `domain_hint` gives us low-cost semantic classification today without changing gates.

## Tradeoff

- Short-term: some non-LLM repos are temporarily routed into `llm_repos`.
- Long-term: we avoid premature architecture churn and keep clean evidence for later shard extraction.

## Trigger To Revisit

Re-open shard expansion after pilot shallow canonicalization is stable and both conditions hold:

1. A recurring domain cluster emerges (e.g., enough repos with same `domain_hint`), and
2. That cluster needs different ontology, validation policy, or operational gates from current shards.

Until then, `domain_hint` remains metadata-only and non-blocking for current shard routing.
