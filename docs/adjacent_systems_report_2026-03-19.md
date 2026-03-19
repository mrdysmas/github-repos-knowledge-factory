# Adjacent Systems Report

Date: 2026-03-19
Repo scope: `/Users/szilaa/scripts/ext_sources/github_repos`
Branch: `main`
Commit: `389a1561adbd6147d4e09bd59e4266952c925aba`

## 1. Why this report exists

This report is a reusable reference for follow-on work:

- comparison matrix
- shortlist of 5 repos to ingest or study
- feature-gap backlog for this repo

The target repo is not a generic agent-memory project. It is a canonical repository-knowledge pipeline with YAML as source of truth and SQLite as the read model. Current repo context:

- source of truth: `project_status.yaml`
- canonical outputs: `master_index.yaml`, `master_graph.yaml`, `master_deep_facts.yaml`, `knowledge.db`
- pipeline shape: `WS5 -> WS4 -> WS6 -> WS7`
- operational focus today: ingestion, validation, canonicalization, queryability, and corpus expansion

This matters because many adjacent systems optimize for runtime agent memory, while this repo currently optimizes for trusted compilation and queryability.

## 2. Research method

I looked for:

- GitHub repos adjacent to `getzep/graphiti`
- recent or popular open-source systems for agent memory, temporal memory, graph memory, and graph-based retrieval
- forum and discussion signals about what breaks in practice

I treated primary repo READMEs and issue trackers as the highest-signal sources. Forum threads were used mainly for implementation pain points and repeated design themes.

## 3. Executive summary

### 3.1 Main finding

There is a real cluster of systems now converging around a shared idea:

- RAG is not enough for long-lived agents
- graph structure alone is not enough
- memory needs time, consolidation, forgetting, contradiction handling, and operational interfaces

`getzep/graphiti` is one strong example, but it is not the only one. The adjacent landscape now includes:

- temporal graph memory systems
- layered memory systems
- stateful agent platforms
- graph-based retrieval systems
- MCP-exposed memory services

### 3.2 Main implication for this repo

This repo appears stronger than many of those systems on:

- canonical source-of-truth discipline
- deterministic compilation
- validation gates
- provenance awareness

This repo appears weaker than many of those systems on:

- runtime memory semantics
- first-class temporal belief updates
- memory lifecycle rules
- agent-facing APIs and tool surfaces
- downstream task-quality evaluation

### 3.3 The cleanest framing

This repo is currently closer to a trusted knowledge warehouse than a live memory substrate.

That is not a weakness by itself. It is a product choice. But if the goal is to become more useful to long-lived agents, the adjacent systems are showing where the next pressure points are.

## 4. Verified findings by system

This section keeps source-grounded findings separate from interpretation.

### 4.1 Graphiti

Repo: https://github.com/getzep/graphiti

Verified from the current README:

- Graphiti describes itself as a framework for building and querying temporal context graphs for AI agents.
- It explicitly contrasts itself with static knowledge graphs and traditional RAG.
- It models entities, facts/relationships, episodes, and ontology.
- Facts have validity windows.
- It emphasizes provenance to source data.
- It supports incremental graph construction instead of full recomputation.
- It emphasizes hybrid retrieval: semantic + keyword + graph traversal.
- It includes an `mcp_server` and a `server` in the repo.
- It supports multiple graph backends, not only Neo4j: Neo4j, FalkorDB, Kuzu, and Amazon Neptune are listed.
- It defaults to OpenAI for LLM inference and embeddings, with Anthropic, Groq, and Google Gemini support mentioned as extras.
- The README positions Graphiti as the open-source engine and Zep as the managed production platform.

What seems genuinely distinctive:

- temporal fact invalidation
- explicit provenance via episodes
- incremental updates as a first-class concept
- graph memory optimized for changing data instead of static corpora

Important caution:

- some of the strongest performance claims are part of the Graphiti/Zep framing, so they should be treated as product claims until independently verified in code or benchmarks

### 4.2 Mem0

Repo: https://github.com/mem0ai/mem0

Verified from the current repo and issues:

- Mem0 describes itself as a universal memory layer for AI agents.
- Its framing centers on personalization, continuous learning, and memory as an attachable layer for assistants and agents.
- It offers hosted and self-hosted paths.
- It is broad and popular enough that issue volume exposes operational pain points clearly.

Relevant issues found:

- deletion inconsistency with graph store cleanup:
  https://github.com/mem0ai/mem0/issues/3245
- timeout / empty results until re-instantiation:
  https://github.com/mem0ai/mem0/issues/2672
- add-memory latency concerns:
  https://github.com/mem0ai/mem0/issues/2813
- graph-memory provider coupling to OpenAI structured output:
  https://github.com/mem0ai/mem0/issues/3711
- memory/thread/resource leak concerns:
  https://github.com/mem0ai/mem0/issues/3376

What this means:

- Mem0 is a strong signal for what users want from a memory layer
- its issue tracker is also a strong signal that lifecycle correctness, latency, provider abstraction, and cleanup are hard in practice

### 4.3 Letta

Repo: https://github.com/letta-ai/letta

Verified from the current repo and docs:

- Letta describes itself as a platform for building stateful agents.
- It was formerly MemGPT.
- It exposes both CLI and API paths.
- It positions advanced memory as a core part of the agent runtime.
- Letta Code supports skills and subagents.
- Letta docs explicitly show integration with external memory backends including Graphiti, Mem0, Weaviate, and Zep:
  https://docs.letta.com/tutorials/integrations/external-memory/

What this means:

- Letta treats memory less as a static datastore and more as a runtime concern in the agent loop
- it is also evidence that the ecosystem is already thinking in terms of pluggable memory providers, not one blessed backend

### 4.4 Cognee

Repo: https://github.com/topoteretes/cognee

Verified from the current README:

- Cognee calls itself a knowledge engine for AI agent memory.
- It combines vector search, graph databases, and cognitive-science-inspired approaches.
- It positions itself as persistent, learning-oriented, and traceable.
- It supports a simple pipeline shape: add -> cognify -> search.
- The README explicitly emphasizes continuous learning and context provision for agents.

What seems important:

- Cognee makes the ingest/build/search loop explicit
- it is close to this repo in pipeline feel, but more overtly aimed at runtime memory than canonical corpus management

### 4.5 OpenMemory

Repo: https://github.com/CaviraOSS/OpenMemory

Verified from the current README:

- OpenMemory positions itself as a local persistent memory store for LLM applications, including Claude, Copilot, Codex, and similar clients.
- It exposes HTTP API endpoints, temporal endpoints, and an MCP server.
- It frames itself explicitly against "just vectors" and generic RAG.
- It claims multi-sector memory: episodic, semantic, procedural, emotional, reflective.
- It supports temporal reasoning with `valid_from` / `valid_to`.
- It includes decay and reinforcement instead of hard TTL-only thinking.
- It includes explainable traces for why recall happened.
- It exposes an MCP workflow and a CLI.
- It includes migration paths from Mem0, Zep, and Supermemory.

What stands out:

- it is unusually explicit about forgetting, reinforcement, and explainability
- it tries to package memory as an operational product surface, not only a library

Important caution:

- its README is ambitious and product-heavy; specific claims around quality and behavior should be treated as design intent until validated

### 4.6 Hindsight

Repo: https://github.com/vectorize-io/hindsight

Verified from the current README:

- Hindsight describes itself as an agent memory system meant to work more like human memory.
- It explicitly critiques both basic vector search and plain knowledge graphs.
- It organizes memory into world facts, experiences, opinions, and observations.
- It exposes `retain`, `recall`, and `reflect`.
- Recall runs four retrieval strategies in parallel: semantic, keyword, graph, and temporal.
- It uses reranking and explicit trimming for token limits.
- Reflection is treated as a mechanism for generating higher-level observations from existing memories.
- It claims strong benchmark performance on long-term memory tasks.

What stands out:

- Hindsight is one of the clearest examples of "memory as learning loop" rather than just "memory as storage"
- the `reflect` operation is especially relevant because it maps to consolidation rather than retrieval alone

Important caution:

- some benchmark comparisons are described as self-reported by vendors; the performance framing is useful, but should be treated carefully

### 4.7 GraphRAG

Repo: https://github.com/microsoft/graphrag

Verified from the current README:

- GraphRAG describes itself as a modular graph-based retrieval-augmented generation system.
- It is a pipeline for extracting structured data from unstructured text using LLMs.
- Microsoft explicitly warns that indexing can be expensive.
- Microsoft explicitly recommends prompt tuning rather than assuming good out-of-box results.
- The repo is framed as a methodology / demonstration rather than an officially supported Microsoft product.

What this means:

- GraphRAG is adjacent, but not equivalent, to runtime agent memory
- it is most relevant here as a graph-based retrieval/indexing reference and as a reminder that graph pipelines often move cost and tuning complexity upstream

### 4.8 MCP-oriented graph memory examples

Repos:

- https://github.com/neo4j-contrib/mcp-neo4j
- https://github.com/neo4j-contrib/gds-agent
- https://github.com/mjherich/memory-visualizer

Verified from repo descriptions and pages:

- `mcp-neo4j` exposes Model Context Protocol integration with Neo4j
- `gds-agent` exposes an MCP server around Neo4j Graph Data Science tools
- `memory-visualizer` exists specifically to inspect Anthropic memory-MCP graph structures

Why these matter:

- they show that memory is increasingly being operationalized via MCP, not only SDK calls
- they also show that visualization and debugging are already becoming part of the memory-tooling stack

## 5. Discussion and forum signals

These are not treated as authoritative specifications. They are used as "what builders keep tripping over" signals.

### 5.1 RAG is still widely seen as insufficient for memory

Threads and discussions repeatedly say that retrieval alone does not solve:

- persistence across sessions
- contradiction handling
- recency
- preference learning
- memory consolidation

Useful discussion examples:

- memory consolidation discussion:
  https://www.reddit.com/r/learnmachinelearning/comments/1r2hrib/built_a_memory_consolidation_system_for_my_llm/
- dual-layer memory discussion:
  https://www.reddit.com/r/Rag/comments/1rs7d81/i_built_a_duallayer_memory_system_for_llm_agents/
- persistent Claude memory discussion:
  https://www.reddit.com/r/ClaudeAI/comments/1rduovs/i_built_a_persistent_memory_system_for_claude_it/
- self-hosted agentic memory discussion:
  https://www.reddit.com/r/SideProject/comments/1rhwjgy/i_built_a_selfhosted_agentic_memory_system_tested/
- HN thread on agent memory as a top unsolved pain:
  https://news.ycombinator.com/item?id=44683110

Repeated pattern:

- people keep reinventing layered memory
- people keep adding consolidation after the fact
- people keep asking how to handle conflicting facts over time

### 5.2 Performance and indexing are recurring pain points

Graph memory systems are often more operationally fragile than their top-level pitch suggests.

Concrete example:

- Graphiti retrieval thread:
  https://www.reddit.com/r/Rag/comments/1r1db1z/graphiti_retrieval_neo4j_taking_exceptionally_long/

Reported problems in that thread:

- index-building accidentally running per request
- protocol choice affecting latency
- reranking likely dominating query time
- vector index usage being sensitive to query syntax / implementation details

The thread is especially useful because the problem was not conceptual. It was operational.

### 5.3 Cleanup and lifecycle correctness are common failure modes

The Mem0 issue tracker is a strong example:

- deletion can fail to clean graph state
- re-instantiation may be needed after timeout conditions
- ingestion latency can be high
- provider assumptions can leak into graph-memory internals

This matters because "memory that accumulates incorrectly" is worse than "no memory" for many agent systems.

## 6. What I infer from the landscape

This section is interpretation, not direct source text.

### 6.1 The adjacent systems are solving a different layer than this repo

This repo today is strongest at:

- canonicalization
- validation
- provenance discipline
- deterministic rebuilds
- queryable compiled outputs

Most adjacent systems are strongest at:

- runtime recall
- session continuity
- temporal belief updates
- consolidation and reflection
- ergonomic integration into agent loops

So the cleanest comparison is not "they are better" or "this repo is better."
It is:

- this repo is better at trusted corpus construction
- they are more focused on live agent memory behavior

### 6.2 The main missing capability is not more storage

The biggest gap does not look like "store more facts."

It looks like:

- decide what stays true
- decide what stopped being true
- decide what should decay
- decide what should consolidate into a higher-level principle
- explain why a recalled memory was selected

That is a different problem than current corpus expansion.

### 6.3 Time is now table stakes for serious memory systems

Graphiti and OpenMemory are explicit about temporal truth windows.
Hindsight is explicit about experiences over time and reflective learning.
Forum builders keep hitting contradictions and stale beliefs.

Inference:

- if this repo ever wants to serve as a more live memory substrate, temporal state needs to become first-class rather than implicit in provenance timestamps alone

### 6.4 Lifecycle rules matter as much as retrieval

The ecosystem is converging on:

- forgetting
- decay
- reinforcement
- supersession
- contradiction management
- cleanup

Inference:

- this repo's existing strength in validation and gating could be a major advantage if extended into lifecycle rules
- many adjacent projects appear weaker than this repo on correctness discipline

### 6.5 Agent-facing interfaces are becoming mandatory

The strong pattern across Letta, Graphiti MCP, OpenMemory MCP, Neo4j MCP, and memory visualizers:

- memory is being exposed as a live tool surface
- not just as a database or a batch-generated artifact

Inference:

- `query_master.py` is a solid operator/read-model CLI
- but it is not yet a memory runtime API
- an MCP or thin service surface would be the natural adjacent move if runtime integration becomes a goal

### 6.6 Evaluation is becoming part of the product, not just internal QA

Hindsight emphasizes benchmark framing.
GraphRAG emphasizes prompt tuning and operational limitations.
Mem0 and others center "works in production" claims.

Inference:

- this repo has strong pipeline-health validation
- it has less explicit measurement of downstream utility for agents
- future work likely needs "does this improve agent behavior?" metrics, not only corpus correctness metrics

## 7. Implications for this repo

These are the most likely improvement areas suggested by the adjacent landscape.

### 7.1 Strengths to preserve

Do not lose these:

- YAML source-of-truth model
- deterministic compile steps
- strict gate discipline
- provenance-aware modeling
- canonical artifact separation from derived read model

These are real differentiators, especially relative to many memory repos that appear faster-moving but looser.

### 7.2 Likely feature gaps

Likely gaps, ordered by leverage:

1. First-class temporal fact state
2. Supersession and contradiction model
3. Memory lifecycle rules: decay, reinforcement, deletion propagation
4. Agent-facing runtime API / MCP surface
5. Hybrid retrieval policy that combines graph, keyword, semantic, and recency
6. Consolidation / reflection layer that turns raw events into stable knowledge
7. Explainability for recall decisions
8. Downstream evaluation metrics for agent usefulness
9. Operational observability for latency, stale memory, orphan state, and contradiction counts

### 7.3 What not to overlearn

Do not overlearn from product language.

Some adjacent repos are clearly stronger at:

- packaging
- memory framing
- runtime ergonomics

But not necessarily stronger at:

- ground-truth discipline
- deterministic correctness
- lifecycle integrity
- source verifiability

This repo should borrow their runtime ideas, not their trust assumptions.

## 8. Most important takeaways

If the goal is only to improve the current repository-knowledge pipeline:

- study GraphRAG and Cognee for graph/retrieval pipeline ideas
- study Graphiti for temporal graph modeling
- study Mem0 issues for lifecycle failure modes to avoid

If the goal is to move toward a true agent-memory substrate:

- Graphiti, Letta, OpenMemory, and Hindsight are the highest-value references

If the goal is to stay trust-first while adding memory behavior:

- the opportunity is probably to combine this repo's canonicalization strengths with:
  - temporal truth windows
  - lifecycle rules
  - explainable recall
  - agent-facing runtime interfaces

## 9. Source index

Primary repos and docs:

- Graphiti: https://github.com/getzep/graphiti
- Mem0: https://github.com/mem0ai/mem0
- Letta: https://github.com/letta-ai/letta
- Letta external memory integrations: https://docs.letta.com/tutorials/integrations/external-memory/
- Cognee: https://github.com/topoteretes/cognee
- OpenMemory: https://github.com/CaviraOSS/OpenMemory
- Hindsight: https://github.com/vectorize-io/hindsight
- GraphRAG: https://github.com/microsoft/graphrag
- Neo4j MCP: https://github.com/neo4j-contrib/mcp-neo4j
- Neo4j GDS agent: https://github.com/neo4j-contrib/gds-agent
- Anthropic memory visualizer: https://github.com/mjherich/memory-visualizer

Issue and discussion references:

- Graphiti retrieval latency thread:
  https://www.reddit.com/r/Rag/comments/1r1db1z/graphiti_retrieval_neo4j_taking_exceptionally_long/
- Mem0 deletion / orphaned graph state:
  https://github.com/mem0ai/mem0/issues/3245
- Mem0 timeout / re-instantiation issue:
  https://github.com/mem0ai/mem0/issues/2672
- Mem0 add-memory latency:
  https://github.com/mem0ai/mem0/issues/2813
- Mem0 provider-coupling issue:
  https://github.com/mem0ai/mem0/issues/3711
- Mem0 memory/thread leak issue:
  https://github.com/mem0ai/mem0/issues/3376
- Reddit memory consolidation thread:
  https://www.reddit.com/r/learnmachinelearning/comments/1r2hrib/built_a_memory_consolidation_system_for_my_llm/
- Reddit dual-layer memory thread:
  https://www.reddit.com/r/Rag/comments/1rs7d81/i_built_a_duallayer_memory_system_for_llm_agents/
- Reddit persistent Claude memory thread:
  https://www.reddit.com/r/ClaudeAI/comments/1rduovs/i_built_a_persistent_memory_system_for_claude_it/
- Reddit self-hosted memory thread:
  https://www.reddit.com/r/SideProject/comments/1rhwjgy/i_built_a_selfhosted_agentic_memory_system_tested/
- HN thread:
  https://news.ycombinator.com/item?id=44683110

## 10. Known limits of this report

- This is a landscape scan, not a code-level implementation audit of each repo.
- Some sources are README/product framing, so any strong performance claims should be verified independently before they influence design decisions.
- Forum threads are useful for failure patterns, not for architecture truth.
- I did not yet inspect each repo deeply enough to score data models, APIs, or ops posture side-by-side. That belongs in the next comparison-matrix step.
