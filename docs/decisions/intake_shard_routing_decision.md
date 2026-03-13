# Intake Shard Routing Decision (D5)

Decision date (UTC): 2026-02-24T19:58:27Z

## Decision

Use the unified canonical shard `repos` for intake-era canonical knowledge artifacts.
Do not require operators to route repos between `llm_repos` and `ssh_repos`.

Add and maintain `domain_hint` as metadata in intake lifecycle records now to preserve future split options.

## Why

- The active WS5/WS1/WS4/WS6/WS7 pipeline now operates on the unified canonical path under `repos/knowledge`.
- Retaining legacy shard labels as routing inputs would create operator confusion without changing downstream behavior.
- `domain_hint` still gives low-cost semantic classification without becoming a routing control.

## Tradeoff

- Short-term: compatibility fields such as `target_shard` may still appear in manifests and pilot artifacts.
- Long-term: those compatibility fields normalize to `repos`, so the active execution contract stays simple while preserving backward compatibility.

## Trigger To Revisit

Re-open shard expansion only if both conditions hold:

1. A recurring domain cluster emerges (e.g., enough repos with same `domain_hint`), and
2. That cluster needs different ontology, validation policy, or operational gates from the unified `repos` shard.

Until then, `domain_hint` remains metadata-only and non-blocking for canonical destination.
