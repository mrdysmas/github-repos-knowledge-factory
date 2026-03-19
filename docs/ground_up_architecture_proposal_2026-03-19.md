# Ground-Up Architecture Proposal

Date: 2026-03-19
Target repo: `/Users/szilaa/scripts/ext_sources/github_repos`
Tracking issue: `github_repos-i4n`
Status: directional proposal

## 1. Purpose

This proposal answers a high-level question:

- If this project were being built from the ground up now, with the intended use case fully understood, how should it be designed?

The intended use case is now clear:

- ingest GitHub repositories
- generate normalized deep facts
- compile those facts into a queryable local substrate
- use that substrate to improve agentic coding sessions from an advisory, pattern-learning, and real-world-examples angle

This is not a detailed implementation plan.
It is an architecture and product-shape proposal intended to guide future design.

## 2. Executive Summary

If rebuilding this project from scratch today, I would make it:

- a **coding-session advisory substrate**
- not a memory system
- not a generic code search engine
- not a generic RAG product

The system would have five major layers:

1. canonical ingestion and normalization pipeline
2. compiled local read model
3. question-shaped advisory query layer
4. thin read-only agent interface
5. workflow and regression tooling around the data

The most important design choice would be:

- custom-build the knowledge model, extraction logic, normalization pipeline, and advisory query interface
- adopt off-the-shelf tools for workflow, issue tracking, local storage primitives, and optional supporting context tools

The strongest recommendation is:

- keep the trust-first canonical pipeline as the core differentiator
- shape everything else around the actual coding-session questions the tool should answer well

## 3. Product Boundary

### 3.1 What the project is

At its best, this project is:

- a local, structured implementation-prior database
- built from normalized cross-repo knowledge
- used to improve early coding decisions
- especially valuable for smaller local models that need stronger priors

In practical terms, the system should help answer questions like:

- How do adjacent repos usually solve this kind of problem?
- What components are likely involved?
- What failure modes are common?
- Which reference repos should I inspect first?
- Does the implementation direction I’m considering look typical or risky?

### 3.2 What the project is not

The project should **not** be framed as:

- a long-term memory system
- a chat transcript memory layer
- a codebase semantic search replacement
- a source-of-truth for the live target repo being edited
- an autonomous decision engine

Its job is:

- improve judgment before implementation

Its job is **not**:

- replace source inspection

## 4. Design Goals

### Primary goals

- Build a trustworthy cross-repo knowledge substrate
- Normalize implementation-relevant facts into a stable ontology
- Make those facts queryable locally and cheaply
- Improve small-model coding-session decisions before code inspection
- Preserve reviewability, provenance, and deterministic rebuilds

### Secondary goals

- Make the read layer easy to expose through a skill or MCP server
- Keep regression and data-quality review manageable
- Support iterative ontology growth without collapsing into schema drift

### Non-goals

- General-purpose memory management
- General-purpose vector retrieval platform
- Full autonomous coding orchestration
- Replacing specialized code search/indexing tools

## 5. Architecture Overview

The system should be built in five layers.

### Layer 1. Canonical ingestion and normalization

This layer ingests repositories and produces normalized canonical artifacts.

Responsibilities:

- acquire shallow repo metadata
- clone or inspect repo sources when needed
- extract raw deep narrative / structured observations
- normalize those observations into a canonical ontology
- validate contracts and trust gates

Output:

- canonical repo records
- canonical graph relationships
- canonical deep facts

This is the core product layer.
It should remain custom-built.

### Layer 2. Compiled local read model

This layer materializes the canonical data into a fast local query substrate.

Responsibilities:

- compile canonical artifacts into a query-friendly local database
- enforce staleness detection
- support deterministic rebuilds
- keep operational query latency low

Output:

- local SQLite read model

This is a derived layer, not the source of truth.

### Layer 3. Advisory query layer

This layer exposes the substrate in terms of coding-session questions, not raw storage details.

Responsibilities:

- answer pattern-level questions
- answer risk/preflight questions
- answer reference-repo selection questions
- answer solution-variant questions
- answer inspection-priority questions

This layer should be shaped around the actual question set, not around arbitrary SQL.

### Layer 4. Thin agent interface

This layer exposes the advisory query layer to local models or coding agents.

Responsibilities:

- provide a small read-only interface
- return structured outputs
- keep the tool contract narrow
- avoid bypassing the canonical query semantics

This should likely be:

- a skill
- or a thin MCP server
- or both

### Layer 5. Workflow, regression, and review tooling

This layer supports safe iteration on the knowledge substrate.

Responsibilities:

- issue tracking
- golden dataset review
- regression checks
- data-diff inspection
- operational documentation

This layer should lean heavily on existing tools.

## 6. What Should Be Custom-Built

These components are too central to the product to outsource.

### 6.1 Canonical ontology

Custom build:

- fact types
- predicates
- object kinds
- relationship semantics
- category/archetype model

Why:

- the ontology is the product boundary
- off-the-shelf tools do not share your use case precisely
- this is where implementation priors become structured, queryable knowledge

### 6.2 Deep-fact extraction logic

Custom build:

- extraction rules
- narrative-to-fact normalization
- evidence attachment
- repo-specific heuristic handling

Why:

- this is not generic document extraction
- the target is normalized implementation guidance, not free-form summaries

### 6.3 Trust and validation gates

Custom build:

- schema validation
- trust gates
- deterministic rebuild checks
- read-model freshness guarantees

Why:

- the tool's value depends on confidence that the substrate is coherent

### 6.4 Advisory query interface

Custom build:

- question-oriented query recipes
- rank/selection logic over normalized facts
- structured answer forms for agents

Why:

- this is how the system becomes useful in coding sessions
- generic DB access is too weak and too leaky

## 7. What Should Be Adopted

These are not the differentiator.
Use existing tools unless they create clear friction.

### 7.1 Issue and workflow tracking

Use:

- Beads

Why:

- the repo already adopted it
- it is graph-aware, git-friendly, and agent-oriented
- task tracking is important, but not worth custom-building

### 7.2 Local operational database

Use:

- SQLite

Why:

- fast
- local
- easy to distribute
- works well for small-model advisory workflows
- already aligned with the current read-model pattern

### 7.3 Optional data-diff / regression review layer

Use:

- Dolt, but narrowly

Why:

- strong fit for golden datasets and regression review
- not yet justified as the canonical store

### 7.4 Optional external code retrieval support

Consider later:

- Kodit or a similar repo indexing/search MCP

Why:

- useful for concrete external examples
- complementary to your substrate
- not a foundation for the canonical model

## 8. Recommended Knowledge Model

If building from scratch now, I would intentionally keep the first ontology narrower than many knowledge-graph projects try to.

Core fact families:

- components
- configuration points
- implementation patterns
- protocols and integration surfaces
- common tasks
- failure modes
- reference relationships between repos

Derived views:

- archetype/category
- likely solution variants
- likely implementation risks
- likely inspection starting points

Why this narrower model:

- it maps directly to coding-session questions
- it avoids ontology bloat
- it makes the query layer easier to keep high-signal

## 9. Recommended Query Model

I would design the query layer around the 7 coding-session questions already identified, rather than around generic commands first.

Core query families:

- adjacent-pattern discovery
- likely-component discovery
- failure-mode preflight
- reference-repo selection
- solution-variant comparison
- inspection-priority guidance
- implementation-risk check

The low-level storage can still support generic commands, but the public interface should be optimized for these question shapes.

That means:

- question-first contracts
- structured outputs
- evidence and repo references included
- confidence and uncertainty surfaced

## 10. Recommended Agent Interface

The first agent-facing surface should be:

- narrow
- read-only
- structured

Not:

- broad
- write-capable
- free-form natural-language-over-database

Recommended first interface shape:

- a thin MCP or skill wrapper over the advisory query layer

Recommended first operations:

- find reference repos
- list common patterns
- list likely components
- list common failure modes
- compare solution variants
- suggest inspection targets
- assess implementation risk

Guardrails:

- no raw SQL as the main interface
- no direct mutation path into the canonical substrate
- no treating the substrate as proof of the current target repo

## 11. Recommended Workflow Shape

The healthy usage loop should be:

1. ask the advisory substrate what is likely relevant
2. narrow the search space
3. inspect the actual target codebase
4. implement using both local evidence and cross-repo priors

This sequence matters.

If the tool is used to skip source inspection, it will create confident mistakes.
If it is used to improve the quality of source inspection, it will be very valuable.

## 12. Relationship to the Current Project

The current project already has a lot of the right bones.

### What I would explicitly preserve

- canonical source-of-truth separation
- deterministic compile stages
- trust-gate mindset
- compiled local read model
- `query_master.py` as the seed of the query surface
- category/archetype thinking
- emphasis on failure modes and tasks

### What I would sharpen earlier

- define the product as a coding-session advisory system earlier
- define the target question set earlier
- keep the first ontology smaller and more question-driven
- introduce the read-only agent interface earlier
- separate workflow tooling from the knowledge substrate more explicitly

## 13. Relationship to Nearby Tools

This project should not try to outcompete everything.

Instead, it should occupy a clean slot:

- code search tools answer: "where in this repo should I look?"
- your system answers: "what solution shapes and risks should I expect before I look?"

That distinction should guide all future design.

## 14. Data Versioning and Review

If building from scratch now, I would plan for data regression and review from the start.

Recommended approach:

- keep canonical source of truth in explicit artifacts
- add golden datasets for regression review
- consider Dolt as the backing tool for those golden datasets

I would **not** start by making Dolt the canonical store.

The better initial stance is:

- canonical artifacts remain primary
- Dolt supports golden tables, review, and baseline tagging

That keeps the trust model clean while improving data review ergonomics.

## 15. What I Would Defer

These are interesting, but should not be early foundations.

### 15.1 Full memory-system behavior

Defer:

- long-term memory semantics
- session continuity
- general memory lifecycle features

Reason:

- wrong product boundary for the current use case

### 15.2 Embeddings-heavy retrieval

Defer:

- broad semantic ranking as a core dependency

Reason:

- graph + exact match + category/archetype priors + structured predicates likely get you far before embeddings become necessary

### 15.3 Canonical-store migration

Defer:

- replacing the canonical artifact model with a different primary data store

Reason:

- too much architecture churn before the advisory interface is proven

### 15.4 Rich UI/plugin productization

Defer:

- editor plugins
- broad dashboarding
- large runtime orchestration layer

Reason:

- the substrate and question-layer quality matter more first

## 16. Architectural Invariants

These are the rules I would want future work to preserve.

### Invariant 1. Source inspection remains mandatory for code-specific claims

The substrate is advisory, not authoritative about the live target repo.

### Invariant 2. Canonical data remains more important than retrieval cleverness

Bad facts plus fancy retrieval is worse than good facts plus modest retrieval.

### Invariant 3. Query surfaces should reflect user questions, not storage internals

The tool contract should stay aligned with coding-session needs.

### Invariant 4. Derived layers must stay replaceable

The read model and agent interface should be derived and replaceable.
The canonical substrate should remain stable.

### Invariant 5. Build-vs-buy should favor buying non-differentiators

Custom-build only what creates the product's distinct value.

## 17. Open Questions

These are intentionally left open because they depend on future usage evidence.

### Q1. Should the first agent interface be a skill, MCP server, or both?

This is mostly a packaging decision.
It should be decided based on actual agent workflow constraints, not fashion.

### Q2. When do embeddings become worth the added complexity?

This should be answered only after structured query pathways are tested.

### Q3. Does external code indexing materially help enough to justify another subsystem?

This is where Kodit-like tooling may help, but only if the concrete benefit is clear.

### Q4. Should Dolt remain a regression/review layer, or become more central later?

This should depend on real review pain and the value of row-level branching/diff.

### Q5. What is the smallest useful query surface that still materially improves small-model coding sessions?

This should be answered by evaluation against the 7 question set.

## 18. Bottom Line

If building this project from scratch today, I would build:

- a custom canonical knowledge pipeline
- a compiled local SQLite read model
- a narrow advisory query layer shaped around coding-session questions
- a thin read-only MCP/skill interface
- Beads for work tracking
- optional Dolt for golden datasets and review
- optional external repo indexing later as a complement

I would not build:

- a memory system
- a generic RAG product
- a code-search replacement
- a heavy runtime agent platform

The central idea would remain:

- give coding agents better early judgment by exposing normalized, cross-repo implementation priors from real-world repositories

That is the strongest and clearest future for the project.
