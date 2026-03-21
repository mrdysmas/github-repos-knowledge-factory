# Adjacent Systems Corpus Recommendation

Date: 2026-03-21
Parent issue: github_repos-8yv

## Purpose

Turn the adjacent-systems shortlist into a bounded corpus recommendation for this
repo's current direction: which shortlisted repos should be added now, deferred,
or rejected for now.

Decision standard:

- prefer repos that improve coding-session implementation priors, not generic
  memory-product inspiration
- prefer repos that strengthen current Phase 5 priorities such as failure-mode
  preflight, retrieval-policy comparison, and non-inferable cross-repo advisory
  value
- avoid spending corpus bandwidth on runtime surfaces that are interesting but
  not yet on the near-term path

## Current state check

- Already canonical in corpus: mem0ai/mem0
- Already canonical in corpus: microsoft/graphrag
- Not currently canonical or queued: getzep/graphiti
- Not currently canonical or queued: vectorize-io/hindsight
- Not currently canonical or queued: CaviraOSS/OpenMemory
- Not currently canonical or queued: letta-ai/letta

## Recommendation

### Add now

#### getzep/graphiti

Why:

- Best match for the highest-signal semantic gap identified in the adjacent
  systems review: temporal truth, supersession, and provenance-aware updates.
- More likely than the other candidates to improve question-shaped advisory
  output with non-inferable cross-repo patterns rather than generic product
  framing.
- Relevant both to architecture comparison and to likely failure-mode/riskcheck
  style advisory work.

#### vectorize-io/hindsight

Why:

- Strongest reference for consolidation, reflection, and explicit hybrid
  retrieval policy.
- Most likely to sharpen advisory usefulness around "what should I expect before
  I start coding?" because it expresses retrieval strategy and memory shaping
  more clearly than the runtime-platform candidates.
- Complements Graphiti well without collapsing into the same lesson.

### Defer

#### CaviraOSS/OpenMemory

Why:

- Valuable for lifecycle, explainability, MCP, and operational surface design,
  but those are not the current Phase 5 core.
- Product-surface ambition is higher than source-grounded design confidence in
  the current docs, so it is better as a second-wave corpus candidate after the
  query/core-advisory path is firmer.
- Revisit when lifecycle semantics, explainable recall, or MCP surface work
  becomes active rather than speculative.

#### letta-ai/letta

Why:

- Strong runtime/agent-loop reference, but the project is explicitly not
  positioning itself as an agent runtime first.
- Near-term value is more about integration shape than canonical advisory
  knowledge, so it is less aligned with the current "smallest useful layer"
  rule.
- Revisit if the roadmap shifts toward an agent-facing runtime layer or external
  memory-provider integration.

### Reject for now

#### mem0ai/mem0

Why:

- It should not be added as a new corpus candidate because it is already in the
  canonical corpus.
- It remains useful as a warning/reference repo for operational failure modes,
  but there is no corpus-expansion action to take here.

## Narrow add/defer/reject list

- Add now: getzep/graphiti, vectorize-io/hindsight
- Defer: CaviraOSS/OpenMemory, letta-ai/letta
- Reject for now: mem0ai/mem0 (already canonical; no new intake action)

## Follow-on

- Create one intake-tracking issue for Graphiti and Hindsight.
- Do not open intake issues for OpenMemory or Letta yet; revisit only if Phase 5
  core work moves toward lifecycle semantics, explainability, MCP, or agent-loop
  runtime integration.
