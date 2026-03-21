# Adjacent Systems Prioritized Action List

Date: 2026-03-21
Parent issue: github_repos-i9p

## Purpose

Convert the adjacent-systems review into the smallest actionable set of goals
 that fit the current Phase 5 direction.

This list is intentionally narrower than the adjacent-systems backlog.
It reflects the current product anchor:

- coding-session advisory substrate, not generic memory platform
- question-shaped query surface, not broad ontology expansion first
- non-inferable cross-repo value, not repo-local convenience

## Prioritized actions

### 1. Keep Phase 5 centered on Q3/Q7 query-surface refinement

Why this is first:

- Q3 and Q7 are the strongest non-inferable advisory wins already identified by
  the query-gap pass.
- Recent work proves the best near-term gains come from inspectable query-layer
  improvements, not broad schema or runtime changes.
- This preserves the repo's trust-first architecture while improving the actual
  product surface.

What this means in practice:

- continue with small question-shaped slices after `preflight` and `riskcheck`
- prefer category scope, frequency, ranking, and evidence selection over broad
  retrieval or interface expansion

### 2. Make downstream usefulness evaluation the next adjacent-systems-backed workstream

Why this is second:

- The adjacent-systems scan is most useful if it changes coding-session outcomes,
  not just architecture language.
- Evaluation is the smallest next step that can confirm whether the new
  advisory surface is actually helping smaller or cheaper models make better
  decisions.
- This is also the cleanest way to keep adjacent-systems work tied to product
  usefulness rather than drifting into speculative design.

Existing trackers:

- github_repos-d6k
- github_repos-8qc

### 3. Queue Graphiti and Hindsight, then fold them into the next corpus-maintenance batch

Why this is third:

- They remain the best add-next adjacent references for bounded corpus
  expansion.
- The earlier hold is now cleared because the WS6 structural pre-pass contract
  is defined and the retrieval-helper decision stayed optional rather than
  workflow-shaping.

Existing tracker:

- github_repos-grj

Current rule:

- keep both repos queued via the canonical intake path
- select them as part of the next normal corpus-maintenance batch rather than
  creating a dedicated adjacent-systems batch

### 4. Treat Q5-style ontology work as the first serious later candidate

Why this is fourth:

- The adjacent-systems review surfaced a real gap around solution-variant
  comparison and tradeoff representation.
- But Phase 5 evidence says this should wait until query-first improvements stop
  paying off.
- This is the best later candidate because it would strengthen a high-value
  anchor question without collapsing into generic memory-platform work.

## Explicit non-actions for now

Do not treat these as active near-term goals:

- temporal fact state
- supersession / contradiction modeling
- lifecycle rules
- runtime memory surface
- MCP packaging
- memory segmentation
- visualization/debug UX

Why:

- they are broader memory-system moves, not the smallest current improvements to
  the coding-session advisory surface

## Bottom line

The adjacent-systems review does not justify turning the project into a memory
runtime next.

It justifies a tighter sequence:

1. keep improving the Q3/Q7 advisory query surface
2. verify those gains with downstream usefulness evaluation
3. hold the best new corpus candidates in reserve
4. revisit ontology-heavy work only when query-first gains flatten
