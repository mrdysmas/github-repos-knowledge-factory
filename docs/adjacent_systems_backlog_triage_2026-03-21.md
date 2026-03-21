# Adjacent Systems Backlog Triage

Date: 2026-03-21
Parent issue: github_repos-uto

## Purpose

Triage the adjacent-systems feature-gap backlog against the current Phase 5
anchor, which is now explicitly question-shaped and constrained by
non-inferability.

This is not a fresh roadmap. It is a filter:

- what should become near-term implementation work now
- what should wait until current core gains are validated
- what does not fit the current Phase 5 anchor as active product work

## Lightweight rubric pass

- Anchor questions served: primarily Q3 and Q7 now; secondarily Q1, Q4, and Q5
  later
- Non-inferable?: yes for cross-repo failure modes, typicality, solution
  variants, and reference-repo guidance; partial or weak for runtime/product
  surfaces
- Review note: current Phase 5 guidance prefers the smallest query-layer change
  that improves advisory usefulness before ontology expansion, runtime surfaces,
  or packaging

## Main conclusion

The backlog document is directionally useful, but it overstates how much of the
memory-system agenda belongs in the current Phase 5 path.

Current Phase 5 is not choosing among generic memory-platform features.
It is choosing the smallest non-inferable improvements to the coding-session
advisory surface.

That changes the triage:

- near-term work should stay query-first and question-shaped
- ontology-heavy work should wait until query limits are proven
- runtime, MCP, and UX packaging work should remain parked

## Near-term implementation work

### 1. Downstream usefulness evaluation

Decision: keep as near-term, but only as a narrow evaluation layer on top of
the new Q3/Q7 query surface.

Why:

- It directly tests whether the advisory output improves real coding-session
  judgment.
- It fits the Phase 5 rule that usefulness should be verified, not assumed.
- It keeps evaluation tied to the current product surface instead of drifting
  into generic benchmark or memory-platform work.

Existing tracker:

- github_repos-d6k
- github_repos-8qc

Bounded scope:

- evaluate `preflight`, `riskcheck`, and linked Q3/Q7 outputs
- do not broaden into generic agent-runtime evaluation

### 2. Hybrid retrieval policy, but only in a narrowed query-layer form

Decision: keep only the small part that improves advisory queries now; defer the
broader "memory retrieval system" interpretation.

Why:

- Category scope, frequency output, and advisory-shaped ranking already proved
  to be the right first slice for Q3 and Q7.
- The query-gap work shows that the immediate blocker is query design, not a
  full retrieval stack.
- The current phase should prefer inspectable ranking/scoping over opaque
  retrieval expansion.

What counts as near-term:

- query-layer ranking/scoping that sharpens Q1, Q4, or later Q7 slices
- explicit use of counts, distributions, category scope, and simple evidence
  selection

What does not count as near-term:

- embeddings-first retrieval expansion
- broad "memory engine" retrieval architecture
- schema work introduced only to support a speculative retrieval stack

Follow-on note:

- no new issue is required yet; the current Q3/Q7 track already established the
  right primitive direction, and the prioritized action-list task should decide
  the next question-shaped slice

## Later, after current core gains land

### 3. Explainable recall

Decision: later

Why:

- Worth doing once more query behavior needs debugging
- premature before the next advisory outputs are stable enough to explain

### 4. Operational observability for memory behavior

Decision: later

Why:

- useful once richer retrieval/lifecycle behavior exists
- current gains will come more from advisory-query refinement than runtime
  instrumentation

### 5. Consolidation / reflection layer

Decision: later

Why:

- potentially relevant to Q5, but the ontology/query surface is not ready to
  justify it yet
- high risk of creating abstract machinery before current advisory questions are
  answered well

### 6. Q5-style ontology work for solution-variant comparison

Decision: later

Why:

- the query-gap pass shows Q5 is blocked mainly by ontology shape
- this is real future work, but it should wait until the query-first path has
  been pushed further and the need is still sharp

No new tracker required right now:

- the need is documented clearly in the Q5 gap pass and should be reopened only
  when it becomes the next justified anchor-question target

## Not current Phase 5 anchor work

### 7. First-class temporal fact state

Decision: not current-anchor work

Why:

- broad schema and pipeline change
- framed in the backlog as a memory-semantic foundation, but current Phase 5
  guidance prefers query-layer gains first
- no current evidence says temporal semantics are the smallest change needed to
  improve one of the next anchor questions

### 8. Supersession / contradiction model

Decision: not current-anchor work

Why:

- same issue as temporal state: high ontology/pipeline cost before current
  advisory gaps are exhausted at the query layer

### 9. Memory lifecycle rules

Decision: not current-anchor work

Why:

- meaningful only after temporal/supersession semantics exist
- the current project is not yet operating as a live memory system

### 10. Agent-facing runtime surface

Decision: not current-anchor work

Why:

- current guidance explicitly parks new interface surfaces until query semantics
  are stable
- packaging an immature surface would amplify weak semantics rather than fix
  them

### 11. MCP-first integration package

Decision: not current-anchor work

Why:

- explicitly deprioritized in the architecture memo until the query contract is
  stable

### 12. Multi-layer memory segmentation

Decision: not current-anchor work

Why:

- taxonomy before behavior
- not justified by the current advisory surface needs

### 13. Visualization and debugging UX

Decision: not current-anchor work

Why:

- useful multiplier only after richer semantics and query behaviors exist

## Recommended active ordering

1. Keep the Phase 5 core on Q3/Q7 usefulness and next query-layer slices.
2. Treat evaluation as the main adjacent-systems backlog item that is near-term
   enough to activate once the local harness is ready.
3. Treat Q5-style ontology work as the first serious later candidate if query
   gains stop paying off.
4. Keep temporal/lifecycle/runtime/MCP work parked unless a future anchor
   question proves query design alone is insufficient.

## Bottom line

Near-term from this backlog is much smaller than the backlog document suggests.

Keep:

- downstream usefulness evaluation
- narrow query-layer retrieval/ranking refinement

Later:

- explainable recall
- operational observability
- consolidation/reflection
- Q5-style solution-variant ontology work

Not current-anchor work:

- temporal state
- supersession/contradiction
- lifecycle rules
- runtime surface
- MCP packaging
- segmentation
- visualization
