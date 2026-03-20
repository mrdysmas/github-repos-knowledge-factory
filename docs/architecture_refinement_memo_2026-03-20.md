# Architecture Refinement Memo

Date: 2026-03-20
Target repo: `/Users/szilaa/scripts/ext_sources/github_repos`
Related documents:
- `docs/ground_up_architecture_proposal_2026-03-19.md`
- `docs/coding_session_enhancement_positioning_memo_2026-03-19.md`
Related issue:
- `github_repos-byr`

## 1. Purpose

This memo refines the ground-up architecture proposal using the current repo state rather than a greenfield viewpoint.

The goal is not to replace the proposal.
The goal is to sharpen it into a better guide for near-term architectural decisions.

## 2. Current Read

The current project is stronger than many adjacent systems in its core architecture.

Its main strengths are already present:

- canonical YAML as the source of truth
- trust-gated compilation rather than free-form accumulation
- explicit separation between canonical artifacts and the derived SQLite read model
- a practical query surface in `tools/query_master.py`
- operator-facing status and runbook artifacts
- unusually useful emphasis on tasks and failure modes

This means the project does not primarily need reinvention.
It primarily needs tighter product-shape discipline.

## 3. Main Architectural Conclusion

The project should be treated as a **coding-session advisory substrate**.

That means its job is to improve implementation judgment before code changes are made.

It should be optimized to answer a small set of advisory questions well, not to maximize general knowledge capture.

This also implies a broader efficiency framing:

- the system should help smaller or cheaper models produce better coding decisions
  by supplying structured implementation priors

In other words, the architectural value is not tied only to local deployment.
It is tied to low-cost inference plus non-inferable cross-repo advisory context.

## 4. What Still Looks Correct

The following elements should remain architectural constants unless a strong counterexample appears:

- WS-style staged pipeline execution
- trust and validation gates as first-class policy
- canonical artifacts separate from the operational read model
- `query_master.py` as the conceptual center of the query surface
- category/archetype framing as a support layer
- explicit modeling of tasks and failure modes
- operator-facing docs and status artifacts

These are not incidental implementation details.
They are part of what makes the project credible and useful.

## 5. What Needs Sharpening

### 5.1 Make the question set an invariant

The seven coding-session questions should become the project anchor for future ontology, query, and interface work.

This is stronger than a roadmap preference.
It should function as an architectural acceptance rule:

- new schema work should improve at least one question
- new query work should map to at least one question
- new interface work should preserve the question-oriented contract

If work does not improve one of those questions, it should face a higher bar for inclusion.

### 5.2 Optimize for advisory usefulness, not ontology breadth

The main risk is not too few repos.
The main risk is collecting more structured data than can be turned into useful advisory answers.

The ontology should grow only where it improves:

- pattern comparison
- likely-component discovery
- failure-mode preflight
- reference-repo selection
- solution-variant comparison
- inspection-priority guidance
- implementation-risk checks

### 5.3 Treat the query layer as the product surface

The real product is not raw YAML and not raw SQLite.
The real product surface is the advisory query layer.

This means:

- raw SQL should not be the primary agent interface
- table exposure should remain an implementation detail
- `query_master.py` should evolve toward question-shaped commands and outputs

### 5.4 Introduce agent packaging only on top of stable semantics

The earlier proposal said to introduce the MCP/skill surface earlier.
That is still directionally right, but with a constraint:

- the thin agent interface should sit on top of stable question-shaped query semantics
- it should not expose unstable internal tables or accidental schema details

The packaging layer should be thin because the real work belongs in the query contract.

### 5.5 Keep workflow tooling outside the canonical core

Beads and possible Dolt adoption are useful, but they are support layers.

They should remain clearly separate from:

- canonical knowledge representation
- canonical compilation flow
- advisory query semantics

This separation will make future tooling changes cheaper and less disruptive.

### 5.6 Make non-inferability an architectural constraint

The system should be judged not only by whether it is correct, but also by
whether it provides knowledge that the agent could not have obtained by simply
reading the target repository.

This means the core should prioritize:

- cross-repo pattern distributions
- failure-mode norms and preflight warnings
- solution-variant comparisons
- typicality or atypicality signals
- reference-repo selection guidance

And it should avoid treating these as core responsibilities:

- reproducing target-repo structure
- repeating README or setup information
- surfacing standard build or test commands
- restating facts an agent would discover in its first few local searches

Non-inferability should therefore act as an acceptance filter for future query,
schema, and extraction work.

## 6. Revision to the Original Proposal

The most important refinement to the ground-up proposal is this:

The project should not merely be "smaller" or "more advisory-focused."
It should be explicitly optimized around a very small set of decisions:

- what patterns are common
- what components are likely involved
- what breaks
- which repos to inspect
- which solution path looks normal versus risky

That is the real center of gravity.

If a future feature does not help the system answer one of those questions better, it is probably peripheral.

## 7. Strategic Interpretation

The repo already has better core architecture than many adjacent systems.

The next gains are more likely to come from refinement than expansion:

- tighten the advisory contract
- narrow ontology growth to decision support
- make query behavior more explicitly question-oriented
- preserve trust-first compilation and read-model separation

In other words:

- strengthen and polish the core first
- add new surfaces and infrastructure second

## 8. Implications for Future Work

Future work should generally prefer the following sequence:

1. clarify which coding-session question needs improvement
2. identify whether the gap is in ontology, extraction, query logic, or packaging
3. change the smallest layer that improves the answer
4. verify the change improves advisory usefulness without weakening trust or rebuild discipline

This implies a bias toward:

- smaller ontology changes
- sharper query design
- explicit acceptance criteria
- fewer infrastructure detours

## 9. Recommended Near-Term Principle

Treat the seven coding-session questions as the architectural anchor for all near-term changes.

That anchor should guide:

- feature selection
- schema evolution
- query-surface changes
- MCP/skill packaging decisions
- evaluation design

## 10. Bottom Line

The current project does not need a new foundation.
It needs a tighter center of gravity.

That center should be:

- a trust-first, question-shaped, coding-session advisory substrate

The strongest path forward is to make that framing more explicit in the architecture and use it to constrain future growth.
