# Adjacent Systems Feature-Gap Backlog

Date: 2026-03-19
Based on:

- `docs/adjacent_systems_report_2026-03-19.md`
- `docs/adjacent_systems_comparison_matrix_2026-03-19.md`
- `docs/adjacent_systems_shortlist_2026-03-19.md`

Target repo: `/Users/szilaa/scripts/ext_sources/github_repos`

## 1. Purpose

This backlog turns the adjacent-systems research into a concrete improvement list for this repo.

It is not a generic memory-system wishlist.
It is prioritized for this repo's current position:

- strong canonical pipeline
- strong validation and read-model discipline
- weak runtime memory semantics
- weak lifecycle behavior
- weak agent-facing access patterns

## 2. Guiding constraint

Do not throw away the trust model.

The repo's edge today is:

- YAML source of truth
- deterministic compilers
- explicit gates
- provenance-aware canonical artifacts

So the goal is:

- add memory semantics on top of the trust model

Not:

- replace the trust model with a looser runtime-first store

## 3. Priority Summary

### P0: Highest leverage

1. First-class temporal fact state
2. Supersession / contradiction model
3. Hybrid retrieval policy

### P1: Next layer

4. Memory lifecycle rules
5. Agent-facing runtime surface
6. Downstream usefulness evaluation

### P2: Important, but after the above

7. Consolidation / reflection layer
8. Explainable recall
9. Operational observability for memory behavior

### P3: Later / optional

10. MCP-first integration package
11. Multi-layer memory segmentation
12. Visualization and debugging UX

## 4. Backlog Items

### 4.1 P0. First-class temporal fact state

Why this matters:

- Adjacent systems repeatedly treat time as first-class.
- This repo currently has provenance timestamps, but not a real temporal truth model.
- Without this, the repo can answer "what facts exist" better than "what was true when."

What the feature should mean here:

- facts can carry `valid_from` and optional `valid_to`
- queries can ask for current truth or truth at a point in time
- newer facts do not merely accumulate; they can narrow or close earlier truth windows

What good looks like:

- the canonical fact contract supports time windows
- the read model can answer current and point-in-time queries
- conflicting temporal facts no longer silently coexist as equally current

Suggested first implementation slice:

- extend the deep-fact schema with temporal fields
- teach WS6/WS7 to preserve and materialize those fields
- add one query path for "as-of" lookups before attempting broader agent features

Primary references:

- Graphiti
- OpenMemory
- Hindsight

### 4.2 P0. Supersession / contradiction model

Why this matters:

- once time exists, the next problem is contradictory state
- the repo currently has little explicit machinery for "fact B replaces fact A"
- adjacent systems repeatedly hit stale-belief problems

What the feature should mean here:

- facts can be marked superseded, contradicted, or still-active
- the system distinguishes between:
  - historical truth
  - current truth
  - disputed/low-confidence truth

What good looks like:

- no silent pile-up of mutually incompatible current facts
- query results can prioritize active truth while still exposing history
- change events are machine-detectable

Suggested first implementation slice:

- add a minimal status model for facts:
  - `active`
  - `superseded`
  - `contradicted`
- define deterministic rules for status transitions

Primary references:

- Graphiti
- OpenMemory

### 4.3 P0. Hybrid retrieval policy

Why this matters:

- adjacent systems have converged on hybrid retrieval
- this repo already has graph/query capabilities, but not an explicit unified retrieval policy
- if the repo becomes agent-facing, retrieval quality will matter more than storage volume

What the feature should mean here:

- retrieval combines:
  - graph structure
  - exact/keyword matching
  - semantic similarity
  - recency/temporal relevance

What good looks like:

- a query policy exists instead of ad hoc command behavior
- retrieval ranking can be reasoned about and tuned
- current truth and relevant history are both available when needed

Suggested first implementation slice:

- define a retrieval-policy spec first
- add recency and exact-match weighting before attempting embeddings
- avoid jumping straight to a fully opaque ranking stack

Primary references:

- Hindsight
- Graphiti
- GraphRAG

### 4.4 P1. Memory lifecycle rules

Why this matters:

- adjacent systems keep rediscovering decay, reinforcement, and cleanup
- Mem0 issues suggest lifecycle correctness is where many systems break in practice
- this repo currently validates artifacts better than it manages memory aging

What the feature should mean here:

- old facts can weaken over time
- reinforced facts can remain strong
- deleted or invalidated knowledge propagates cleanly
- orphaned state becomes detectable and repairable

What good looks like:

- lifecycle rules are explicit and testable
- deletion is not just cosmetic
- stale state can be detected automatically

Suggested first implementation slice:

- start with orphan detection and invalidation propagation
- then add reinforcement/decay policy
- keep the first version simple and auditable

Primary references:

- OpenMemory
- Mem0 issue history
- Hindsight

### 4.5 P1. Agent-facing runtime surface

Why this matters:

- `query_master.py` is strong for operators
- it is not yet a thin runtime memory interface for agents
- adjacent systems increasingly expose API or MCP surfaces

What the feature should mean here:

- agents can perform core memory operations through a stable surface
- likely operations:
  - query current truth
  - query historical truth
  - store/update facts through validated pathways
  - inspect why something was recalled

What good looks like:

- the memory surface is thin and trust-aware
- it does not bypass canonical validation
- the runtime API is derived from the same source-of-truth model rather than creating a second truth store

Suggested first implementation slice:

- start with read-only runtime access
- only add write/update paths after temporal and contradiction rules exist

Primary references:

- Letta
- OpenMemory
- Graphiti

### 4.6 P1. Downstream usefulness evaluation

Why this matters:

- this repo already measures pipeline integrity well
- it does not yet measure whether the knowledge actually helps agent behavior
- adjacent systems often over-index on marketing claims, but they are right that utility has to be measured somehow

What the feature should mean here:

- evaluate memory quality in terms of downstream task lift, not just corpus completeness

What good looks like:

- a small eval suite exists
- example questions/tasks have baseline vs improved results
- retrieval changes are judged partly on user or agent outcome quality

Suggested first implementation slice:

- create a tiny benchmark set:
  - current-truth lookup
  - historical-truth lookup
  - contradiction resolution
  - multi-hop graph lookup

Primary references:

- Hindsight
- GraphRAG

### 4.7 P2. Consolidation / reflection layer

Why this matters:

- adjacent systems like Hindsight distinguish between raw memory capture and higher-level learning
- this repo currently compiles extracted facts, but does not clearly consolidate them into more stable abstractions

What the feature should mean here:

- raw facts can generate higher-level summaries, observations, or reusable patterns
- the system distinguishes:
  - event-like facts
  - stable learned knowledge

What good looks like:

- consolidation is explicit, not accidental
- higher-level synthesized knowledge is provenance-linked back to its source facts

Suggested first implementation slice:

- create one derived layer for "observations" or "learned summaries"
- do not collapse raw facts into summaries irreversibly

Primary references:

- Hindsight
- Letta

### 4.8 P2. Explainable recall

Why this matters:

- if retrieval gets richer, debugging gets harder
- adjacent systems are starting to expose why a memory was selected
- this repo currently exposes facts and graph data, but not a recall explanation model

What the feature should mean here:

- a query response can explain which signals caused recall:
  - exact text match
  - graph hop
  - recency
  - temporal overlap
  - semantic similarity

What good looks like:

- recall is inspectable
- ranking changes are debuggable
- trust does not degrade as the system gets smarter

Suggested first implementation slice:

- add explanation fields to one query path
- keep the explanation simple and structured

Primary references:

- OpenMemory

### 4.9 P2. Operational observability for memory behavior

Why this matters:

- operational bugs in memory systems often show up as latency, stale state, and leaks
- this repo already audits compile gates well, but not runtime memory behavior

What the feature should mean here:

- track memory-specific operational metrics

Useful metrics:

- stale fact count
- superseded fact count
- contradiction count
- orphaned state count
- current-truth query latency
- historical-truth query latency
- retrieval-path contribution mix

What good looks like:

- regressions are visible
- lifecycle bugs are measurable
- tuning decisions are evidence-based

Primary references:

- Mem0 issue history
- GraphRAG's explicit ops caution

### 4.10 P3. MCP-first integration package

Why this matters:

- MCP is increasingly the standard integration path for memory tools
- but this is not the first thing to build unless runtime semantics already exist

What the feature should mean here:

- an MCP wrapper around the validated memory/query surface

Why this is not earlier:

- exposing weak runtime semantics through MCP just makes them easier to misuse

Primary references:

- OpenMemory
- Graphiti
- Neo4j MCP tools

### 4.11 P3. Multi-layer memory segmentation

Why this matters:

- adjacent systems often split memory into layers like episodic, semantic, procedural
- useful, but premature unless the repo has stronger temporal/lifecycle basics first

What the feature should mean here:

- deliberate memory classes with different retention and retrieval behavior

Why this is later:

- segmentation before lifecycle rules risks taxonomy without behavior

Primary references:

- OpenMemory
- Hindsight

### 4.12 P3. Visualization and debugging UX

Why this matters:

- debugging memory systems gets hard quickly
- graph/memory visualizers will become more useful as semantics deepen

What the feature should mean here:

- inspect fact histories
- inspect supersession chains
- inspect recall paths

Why this is later:

- the semantics need to exist before the visualization becomes worth building

Primary references:

- memory-visualizer
- Neo4j tooling patterns

## 5. Recommended Execution Sequence

This is the sequence that best fits the current repo, not a generic product roadmap.

### Phase 1: Semantics

1. First-class temporal fact state
2. Supersession / contradiction model
3. Hybrid retrieval policy spec

Why:

- these define what the system believes before changing how it is exposed

### Phase 2: Behavior

4. Memory lifecycle rules
5. Downstream usefulness evaluation
6. Read-only runtime surface

Why:

- lifecycle without eval is hard to trust
- runtime access before semantic grounding is risky

### Phase 3: Ergonomics

7. Consolidation / reflection layer
8. Explainable recall
9. Operational observability

Why:

- these make the system usable and debuggable once core behavior exists

### Phase 4: Packaging

10. MCP integration
11. Memory segmentation
12. Visualization

Why:

- these are multipliers, not foundations

## 6. What to avoid

### Do not start with MCP

That would expose an immature memory model rather than fix it.

### Do not start with embeddings-heavy retrieval

The repo can get meaningful gains from temporal, graph, exact-match, and recency logic first.

### Do not start with memory taxonomy

Naming layers before lifecycle behavior exists is likely to produce architecture theater.

### Do not loosen the canonical model

The adjacent systems suggest new capabilities, not a reason to weaken source-of-truth discipline.

## 7. One concrete next action

If only one thing is started next, it should be:

- define a temporal extension to the deep-fact and read-model contracts

Why:

- it is the foundation for contradiction handling
- it is the foundation for historical queries
- it is the foundation for lifecycle rules
- it is the cleanest bridge from current repo strengths to the gaps exposed by adjacent systems

## 8. Bottom Line

The repo does not most urgently need:

- more repos
- more facts
- more APIs

It most urgently needs:

- temporal truth semantics
- contradiction and lifecycle behavior
- a retrieval model that understands time and structure

That is the highest-value path suggested by the adjacent systems work.
