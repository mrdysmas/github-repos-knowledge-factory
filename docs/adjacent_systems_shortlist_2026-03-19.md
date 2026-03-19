# Adjacent Systems Shortlist

Date: 2026-03-19
Based on:

- `docs/adjacent_systems_report_2026-03-19.md`
- `docs/adjacent_systems_comparison_matrix_2026-03-19.md`

Target repo: `/Users/szilaa/scripts/ext_sources/github_repos`

## 1. Purpose

This shortlist answers a narrower question than the landscape report:

- Which 5 adjacent repos are most worth ingesting or studying first?

The criterion is not general popularity. The criterion is:

- likely learning value for this repo
- relevance to the repo's current gaps
- complementarity across the set
- signal quality relative to noise / product framing

## 2. Shortlist

### 1. Graphiti

Repo: https://github.com/getzep/graphiti

Why it made the shortlist:

- strongest direct reference for temporal graph memory
- closest conceptual neighbor to where this repo may want to evolve
- explicitly models changing truth, provenance, episodes, and incremental updates

What to study:

- temporal fact model
- invalidation / supersession behavior
- provenance and episode linkage
- retrieval strategy mixing graph traversal with semantic and keyword search
- service and MCP exposure model

Why it is high priority:

- this repo's biggest gap is first-class temporal memory semantics
- Graphiti is the clearest reference for that exact gap

### 2. Hindsight

Repo: https://github.com/vectorize-io/hindsight

Why it made the shortlist:

- strongest reference for consolidation and reflection
- unusually explicit about memory as a learning loop, not just a retrieval store
- best example found of hybrid retrieval policy described cleanly

What to study:

- `retain`, `recall`, `reflect` split
- reflection/consolidation workflow
- four-path retrieval policy: semantic, keyword, graph, temporal
- reranking and token-budget trimming

Why it is high priority:

- this repo currently has ingestion and query, but almost no memory consolidation layer
- Hindsight is the cleanest reference for what that missing layer could look like

### 3. OpenMemory

Repo: https://github.com/CaviraOSS/OpenMemory

Why it made the shortlist:

- strongest reference for operational memory features
- explicit on decay, reinforcement, explainability, temporal endpoints, and MCP
- closest thing in the set to a "memory product surface" rather than just a backend

What to study:

- decay and reinforcement semantics
- temporal endpoint design
- explainable recall traces
- MCP/API/CLI packaging
- migration model from other memory systems

Why it is high priority:

- this repo is weak on lifecycle and runtime surfaces
- OpenMemory is the strongest reference for both in one place

### 4. Letta

Repo: https://github.com/letta-ai/letta

Why it made the shortlist:

- strongest reference for agent-loop integration
- treats memory as part of long-lived runtime behavior instead of just a datastore
- shows how the ecosystem is already thinking about pluggable memory providers

What to study:

- memory interaction inside the agent loop
- stateful-agent operating model
- external memory provider integration patterns
- how memory is segmented and edited during agent execution

Why it is high priority:

- this repo has a strong knowledge substrate but not an agent runtime surface
- Letta is the best reference for what "memory actually used by an agent" looks like

### 5. Mem0

Repo: https://github.com/mem0ai/mem0

Why it made the shortlist:

- strong demand signal from the ecosystem
- broad memory-layer framing that many builders are adopting
- issue tracker is one of the best sources for practical failure modes

What to study:

- deletion and cleanup behavior
- provider abstraction boundaries
- latency behavior during memory add/search
- where graph memory leaks implementation assumptions

Why it is high priority:

- not because it is the cleanest design
- because it is the clearest source of "what breaks in production memory layers"

## 3. Honorable Mentions

These were useful, but did not make the top 5.

### GraphRAG

Repo: https://github.com/microsoft/graphrag

Why it did not make the top 5:

- very useful for graph retrieval/indexing economics
- less directly aligned with runtime agent memory than the top 5

When to use it:

- when designing retrieval/indexing cost strategy
- when thinking about prompt tuning burden and graph extraction economics

### Cognee

Repo: https://github.com/topoteretes/cognee

Why it did not make the top 5:

- it is a good bridge system
- but each of the top 5 teaches a sharper, more differentiated lesson

When to use it:

- when mapping a transition from pipeline-centric architecture toward memory-engine architecture

### Neo4j MCP tools and memory visualizer

Repos:

- https://github.com/neo4j-contrib/mcp-neo4j
- https://github.com/neo4j-contrib/gds-agent
- https://github.com/mjherich/memory-visualizer

Why they did not make the top 5:

- valuable as tooling references
- less important than the core memory-engine systems for current design questions

When to use them:

- when implementing MCP integration
- when you need observability or graph debugging patterns

## 4. Why this exact mix

The shortlist is deliberately balanced.

It covers:

- temporal truth: Graphiti
- consolidation and hybrid recall: Hindsight
- lifecycle + runtime API + explainability: OpenMemory
- agent-loop integration: Letta
- production failure modes: Mem0

That mix is better than picking five repos that all solve the same slice.

## 5. Suggested Study Order

1. Graphiti
Reason: best match for the repo's most important missing semantic layer.

2. Hindsight
Reason: best reference for consolidation and multi-strategy recall.

3. OpenMemory
Reason: best reference for decay, explainability, and operational surfaces.

4. Letta
Reason: best reference for how memory behaves in a live agent runtime.

5. Mem0
Reason: best source of operational warning signs and common failure modes.

## 6. If the goal is ingestion instead of study

If these repos are being considered for ingestion into this repo's knowledge base, the order should be:

1. Graphiti
2. Hindsight
3. OpenMemory
4. Letta
5. Mem0

Reason:

- this order maximizes learning value relative to the repo's current gaps
- it also gives a good spread across temporal memory, lifecycle, runtime integration, and production risk

## 7. Bottom Line

If you only have bandwidth to go deep on five adjacent systems, these are the right five:

- Graphiti
- Hindsight
- OpenMemory
- Letta
- Mem0

Together they cover the most important missing layers around this repo:

- temporal memory
- consolidation
- forgetting and reinforcement
- runtime agent integration
- real-world failure modes
