# Dolt Integration Proposal

Date: 2026-03-19
Target repo: `/Users/szilaa/scripts/ext_sources/github_repos`
Tracking issue: `github_repos-0d8`

## 1. Purpose

This proposal explores how Dolt could enhance this repo's canonical data workflow.

The goal is not "use Dolt because Dolt is interesting."
The goal is to answer:

- where Dolt fits naturally in this repo
- what problem it would actually solve
- what should remain unchanged
- what adoption path gives real value without destabilizing the current system

## 2. Current repo shape

This matters because Dolt should be mapped onto the real architecture, not onto an imagined one.

Current system:

- source of truth: canonical YAML artifacts
- pipeline shape: `WS5 -> WS4 -> WS6 -> WS7`
- compiled outputs:
  - `master_index.yaml`
  - `master_graph.yaml`
  - `master_deep_facts.yaml`
  - `knowledge.db` as the derived SQLite read model
- trust model:
  - explicit contracts
  - validation gates
  - deterministic compile steps
  - read/query layer via `query_master.py`

Current strengths:

- canonicalization
- provenance discipline
- deterministic rebuilds
- queryable compiled outputs

Current weaknesses, relative to Dolt-style workflows:

- YAML diffs are less ergonomic than table diffs for some review tasks
- regression datasets are fixture-based, not versioned as first-class data releases
- data review is more artifact-centric than row-diff-centric

## 3. Why Dolt is a credible fit here

Dolt is relevant for this repo for the same reason it is useful for "golden tables":

- the data itself is part of the product
- changes to data need review
- regressions in data matter as much as regressions in code
- rollback and diff should be easy

The Dolt blog frames two especially relevant patterns:

- a **data staging area**, where changes land on branches, get diffed/tested/reviewed, then merge
- **version controlled gold tables**, where curated downstream data is treated like a release artifact with diffs, tags, and rollback

That maps surprisingly well to this repo.

This repo already produces something very close to gold tables:

- curated canonical repository data
- curated compiled facts
- a derived read model consumed by tooling

## 4. The strongest observation

The repo already adopted Beads, and Beads already depends on Dolt.

That means Dolt is no longer an abstract external dependency in your workflow.
It is already part of the project's operating environment.

That makes Dolt more attractive here than it would be in a clean-sheet repo, because:

- there is less conceptual sprawl
- there is already a local Dolt server workflow in place
- the team is already implicitly accepting Dolt as part of the toolchain

But that does **not** automatically mean Dolt should replace the current canonical model.

## 5. Integration options

### Option A. Use Dolt only for Beads and nothing else

What it means:

- Beads continues to use Dolt for issue tracking
- the canonical data pipeline remains unchanged
- no new Dolt integration is added to repo data

Upsides:

- zero architecture risk
- no new migration work
- no new source-of-truth ambiguity

Downsides:

- misses the obvious opportunity to use Dolt where data review and rollback would actually help repo outputs

Assessment:

- safe, but probably underuses Dolt relative to the repo's actual needs

### Option B. Dolt as a golden-dataset and regression-review layer

What it means:

- keep YAML as canonical source of truth
- create one or more Dolt-managed golden datasets derived from a vetted subset of canonical outputs
- use Dolt branches, diffs, and tags for regression review around pipeline/query changes

Candidate tables:

- `repos`
- `nodes`
- `edges`
- `facts`
- selected validation/gate result tables

Candidate sources:

- `master_index.yaml`
- `master_graph.yaml`
- `master_deep_facts.yaml`
- `knowledge.db`

Best use cases:

- review "what changed?" after pipeline edits
- keep a small stable regression subset for canonical fixtures
- tag known-good data releases
- compare candidate ontology/query changes against a vetted baseline

Upsides:

- high value
- low architecture risk
- preserves current trust model
- very close to the Dolt "gold tables" pattern

Downsides:

- adds another representation of the data
- needs import/export tooling
- can create drift if not clearly scoped as derived testing/review data

Assessment:

- strongest first adoption path

### Option C. Dolt as a review mirror for full compiled outputs

What it means:

- after WS7, compile the full read-model tables or canonical artifacts into Dolt tables
- use Dolt as the main review surface for large data changes
- continue to treat YAML as canonical and SQLite as the operational read model

Upsides:

- best human-readable / SQL-queryable diff surface for data changes
- easier rollback and tagging of full data snapshots
- aligns with "version controlled gold tables"

Downsides:

- larger operational footprint than Option B
- more duplicated state
- review ergonomics improve, but source-of-truth remains split unless carefully documented

Assessment:

- viable, but heavier than needed for first adoption

### Option D. Dolt as an intermediate canonical store

What it means:

- YAML still exists, but the canonical data model is loaded into Dolt tables as a first-class intermediate layer
- WS7 and query tooling could read from Dolt-derived tables or exports

Upsides:

- richer data workflows without fully abandoning current artifacts
- cleaner branching/diff/release story than pure YAML

Downsides:

- significantly raises system complexity
- introduces dual-source ambiguity unless the ownership rules are extremely clear
- would force deeper changes to validation and compile stages

Assessment:

- interesting, but not justified yet

### Option E. Full migration: Dolt becomes the canonical source of truth

What it means:

- move canonical repo/graph/fact storage from YAML to Dolt tables
- YAML becomes export or compatibility artifact

Upsides:

- strongest row-level diff/review/release workflow
- one data version-control system instead of layered file artifacts

Downsides:

- highest migration cost
- highest trust-model risk
- rewrites a large part of the repo's current architectural intent
- likely breaks the clean mental model the repo currently has

Assessment:

- not recommended now

## 6. Recommendation

Recommended path:

- **Adopt Option B first**
- optionally evolve to **Option C** later if the review value proves real
- **Do not** jump to Option D or E now

This means:

- keep YAML as canonical
- keep WS7 SQLite as the operational query cache
- add Dolt around vetted subsets and regression datasets first

Why this is the right move:

- it captures the main value of Dolt with the least architectural risk
- it uses Dolt where it is strongest:
  - branching
  - diff
  - tagging
  - rollback
  - review of tabular changes
- it does not weaken the current source-of-truth discipline

## 7. What "golden tables" should mean in this repo

This repo should interpret "golden tables" narrowly and usefully.

Not:

- "everything in the repo moved into Dolt"

Instead:

- a carefully selected, vetted subset of canonical compiled data used for experimentation and regression validation

Strong candidate golden slices:

### Golden slice A. Stable representative repos

A curated set of repos across core categories/archetypes, chosen because they stress different parts of the ontology.

Purpose:

- detect schema, compiler, or query regressions

### Golden slice B. High-value fact families

Focused subsets around:

- `supports_task`
- `has_failure_mode`
- `uses_protocol`
- `has_component`

Purpose:

- verify that the most decision-relevant facts remain stable when extraction rules evolve

### Golden slice C. Query-answer fixtures

Small tables that represent expected outputs for specific `query_master.py` scenarios.

Purpose:

- verify coding-session enhancement questions still produce sane structured answers

## 8. Concrete adoption plan

### Phase 0. Document boundaries

Define clearly:

- YAML remains canonical
- Dolt golden tables are derived validation/review artifacts
- SQLite remains the operational query cache

This prevents a source-of-truth muddle.

### Phase 1. Create one golden dataset

Build one initial Dolt dataset from a vetted subset of:

- `repos`
- `edges`
- `facts`

Keep it intentionally small.

Success condition:

- a pipeline/query change can be run and reviewed with meaningful `dolt diff`

### Phase 2. Add regression workflow

For selected changes:

- regenerate the golden dataset on a Dolt branch
- diff against the current golden baseline
- inspect unexpected revisions

Success condition:

- data regressions become easier to review than raw YAML diff alone

### Phase 3. Add release tags for data baselines

Tag vetted golden versions as named baselines.

Success condition:

- "known good" data baselines exist and are cheap to compare/restore

### Phase 4. Evaluate whether a full review mirror is worth it

Only after Phases 1-3 prove value, evaluate Option C:

- full compiled-output review mirror in Dolt

Success condition:

- enough review pain exists in full datasets to justify the larger operational footprint

## 9. Where Dolt should not go yet

### Not as the canonical write path

This repo's canonical model is one of its strengths.
Do not dissolve that prematurely.

### Not as a replacement for existing validation gates

Dolt helps with versioning and diffing.
It does not replace contract validation, trust gates, or compile invariants.

### Not as a general-purpose runtime query backend

`knowledge.db` and `query_master.py` already fill that role cleanly.

## 10. Risks

### Risk 1. Dual-source confusion

If Dolt tables are introduced without explicit ownership rules, people may stop knowing whether YAML, SQLite, or Dolt is authoritative.

Mitigation:

- write the boundary rules first
- treat Dolt outputs as derived until a deliberate architecture decision says otherwise

### Risk 2. Tooling overhead exceeds review benefit

If the golden dataset is too large or too broad, Dolt becomes another chore instead of a clarity tool.

Mitigation:

- start very small
- optimize for review usefulness, not completeness

### Risk 3. False confidence from diffability

Nice diffs do not mean the data is semantically correct.

Mitigation:

- keep existing gates
- pair diff review with validation and targeted query checks

## 11. Open questions that should decide later phases

These are intentionally open-ended.

### Q1. What kind of data change hurts most today?

Is the pain mostly:

- "I can't tell what changed in the facts"
- "I can't validate that a query answer stayed stable"
- "I can't safely experiment with ontology or compiler changes"

The answer changes which Dolt option is most valuable.

### Q2. Do you want Dolt mainly for testing, or for human review?

Those are related but not identical.

- testing pushes toward small golden datasets
- human review pushes toward broader table mirrors

### Q3. Would you actually review row-level diffs regularly?

If the answer is no, full-output Dolt mirrors are probably overkill.

### Q4. Is the long-term interest "better regression control" or "eventual canonical data branching"?

Those are very different trajectories.

- the first points to Option B
- the second points to Option D or E later

### Q5. Do you want the Dolt layer to stay invisible to the coding-session tool?

If yes, that strongly argues for keeping it as a validation/review layer only.

## 12. Bottom line

Dolt looks genuinely aligned with this repo.

But the right first move is not:

- "replace the canonical YAML system with Dolt"

The right first move is:

- "use Dolt to version and review carefully chosen golden data slices derived from the canonical system"

That gives you:

- better regression control
- better data diffs
- better rollback and baseline tagging

without giving up the source-of-truth discipline the repo already has.
