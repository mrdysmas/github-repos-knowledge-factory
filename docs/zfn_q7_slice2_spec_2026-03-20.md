# Q7 Slice 2 Spec — Q3-Linked Preflight Integration

Date: 2026-03-20
Issue: `github_repos-zfn`
Status: **accepted**

## Background

Q7 slice 1 (`riskcheck`) is verified actionable at 3/5 prompts after protocol and
pattern extraction fixes (lri, a2y). The next slice extends riskcheck with on-demand
failure-mode warnings for rare and absent signals, linking it to the existing Q3
preflight surface.

## Design Decisions

### Q1 — Trigger: `--preflight` flag on `riskcheck`

Add an optional `--preflight` flag to the existing `riskcheck` command. When set,
each rare and absent signal in the output gains a `preflight_warnings` list populated
from the Q3 (`has_failure_mode`) surface, filtered to the signal's term.

**Rejected alternatives:**
- **Auto (always-on)**: bloats the base riskcheck output for callers that only need
  typicality signals. riskcheck is frequently called as a fast preliminary check;
  warning embeds should be opt-in.
- **Separate command**: adds CLI surface without benefit. Requires two calls with
  shared arguments. A flag on the existing command is strictly simpler.

### Q2 — Scope preservation: term-filtered, category-scoped preflight

For each rare or absent signal, run the equivalent of:

```
preflight --category <riskcheck_category> --term <signal.input_term> --limit 3
```

Rules:
- Only attach warnings to `rare_in_category` and `absent_from_category` signals.
  `established_in_category` signals get no `preflight_warnings` key — no warning
  is needed for typical behavior, and attaching one would dilute the established signal.
- If the preflight query returns `scope_repo_count: 0` (no failure modes tracked for
  the category at all), emit `preflight_warnings: []`. Do not pad with unrelated modes.
- If the term filter matches no failure modes, emit `preflight_warnings: []`. Do not
  broaden the search — an empty result is informative ("no documented failure modes
  for this term in this category").

### Q3 — Evidence attachment: inline `preflight_warnings` per signal

Each rare/absent signal entry gains:

```yaml
preflight_warnings:
  - failure_mode: <object_value from has_failure_mode>
    example_repos:
      - <github_full_name>
    evidence_notes:
      - <truncated cause/fix note, max 120 chars>
```

Up to 3 warnings per signal (consistent with default preflight limit). Sorted by
`repo_count` descending (same as preflight sort order — most-attested failure modes
first).

If empty: `preflight_warnings: []` (key always present on rare/absent entries when
`--preflight` is set, so callers can distinguish "no warnings" from "warnings not
fetched").

### Q4 — Output contract: YAML-inline, machine-usable, one new flag

**New input**: `--preflight` boolean flag on `riskcheck`. No other new inputs.

**Output changes when `--preflight` is set:**
- Top-level field added: `preflight_mode: true`
- Each entry in `signals.rare_in_category` gains `preflight_warnings: [...]`
- Each entry in `signals.absent_from_category` gains `preflight_warnings: [...]`
- Entries in `signals.established_in_category` are unchanged (no `preflight_warnings`)

**Output unchanged when `--preflight` is not set**: the base riskcheck surface is
untouched. Existing callers are unaffected.

Full annotated output example (vector_database, gRPC was rare/absent before lri fix,
used here for illustration):

```yaml
artifact_type: master_query_riskcheck
category_filter: vector_database
preflight_mode: true
scope_repo_count: 10
corpus_health:
  scope_repo_count: 10
  fact_count_in_scope: 189
proposal:
  protocols:
    - gRPC
signal_counts:
  established_in_category: 0
  rare_in_category: 1
  absent_from_category: 0
signals:
  established_in_category: []
  rare_in_category:
    - input_kind: protocol
      input_term: gRPC
      predicate: uses_protocol
      matched_repo_count: 1
      matched_repo_fraction: 0.1
      matched_values:
        - gRPC
      example_repos:
        - weaviate/weaviate
      preflight_warnings:
        - failure_mode: gRPC connection refused on port expected to be available
          example_repos:
            - weaviate/weaviate
          evidence_notes:
            - "cause: Weaviate startup wiring in configure_api.go initializes gRPC
               after REST; if module registration fails, gRPC server may not start"
        - failure_mode: Service fails to start with address already in use on port 6334
          example_repos:
            - qdrant/qdrant
          evidence_notes:
            - "cause: Another process is bound to the gRPC port (6334); configured
               in service.grpc_port"
  absent_from_category: []
```

### Q5 — Absent vs. rare: no behavioral distinction

The same query strategy applies to both buckets. For absent signals, the category-scoped
preflight with term filter may return results (failure modes that mention the term in
note text, even if no repos in the category have a matching `uses_protocol` or
`implements_pattern` fact). This is the honest answer — the corpus knows about the term
through failure mode documentation even if no repo formally implements it.

If the absent signal's term is truly unknown to the category's failure modes, the
result is `preflight_warnings: []`. That too is informative.

The bucket label (absent/rare) is already present in the output. Agent callers can
weight warnings from absent signals differently from rare signals in their own reasoning.
No distinction is needed in the query implementation.

## Non-Inferability Statement

An agent reading the target repo's code and README can learn what patterns/protocols
the repo uses and how to configure them. It cannot learn:

1. Which of those patterns are rare or absent across N category peers (requires corpus
   aggregation).
2. Which failure modes have been observed specifically in category peers that implement
   the same pattern (requires cross-repo fact lookup filtered by term).

Both are what the Q7+Q3 linkage provides. The value is the cross-repo signal, not
per-repo description.

## Implementation Scope

One function change in `query_master.py`:

- In `command_riskcheck_sqlite`: when `--preflight` is set, for each rare/absent
  signal item, call the preflight query logic (already exists as
  `command_preflight_sqlite`) with the signal's `input_term` as `term_filter` and
  the same `category` and a `limit` of 3. Embed the result's `results` list as
  `preflight_warnings` on the signal item. Add `preflight_mode: True` to the top-level
  output dict.
- Add `--preflight` boolean argument to the `riskcheck_parser` in `main()`.
- No schema changes, no new commands, no new data sources.

Estimated scope: ~30 lines of new code, no new dependencies.

## Follow-On Issue

`github_repos-<TBD>` — Implement riskcheck --preflight flag (Q7 slice 2)
