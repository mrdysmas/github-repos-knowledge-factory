# WS6 Structural Pre-Pass Sketch

Date: 2026-03-20
Target repo: `/Users/szilaa/scripts/ext_sources/github_repos`
Related:
- `docs/architecture_refinement_memo_2026-03-20.md`
- `phase_5_anchor_acceptance_rubric.yaml`
- `contracts/deep_narrative_contract.md`
- `contracts/ws1/deep_fact.schema.yaml`
- `tools/ws6_clone_prep.py`
- `tools/ws6_deep_integrator.py`

## 1. Purpose

This note sketches a possible new pipeline stage that runs after clone prep and before deep authoring.

The goal is narrow:

- reduce structural-fact authoring cost
- reduce orientation time for WS6 deep work
- shift attention toward non-inferable facts such as failure modes, tasks, patterns, and implementation risks

This is not a proposal to replace the canonical YAML -> WS6 -> WS7 architecture.

## 2. Problem

The current pipeline overproduces structural facts because structure is the easiest thing to observe and write down.

That creates two problems:

1. expensive human or LLM attention is spent rediscovering repo-local structure
2. behavioral and advisory facts receive less attention even though they are more valuable for the coding-session use case

This is now a Phase 5 quality problem, not just a throughput problem.

Per `phase_5_anchor_acceptance_rubric.yaml`, core value should come from non-inferable cross-repo advisory knowledge.
Repo-local structure is useful, but it should not dominate the system.

## 3. Lightweight Rubric Pass

- Anchor question served: `Q2` most directly, with support for `Q3`, `Q6`, and `Q7`
- Non-inferable?: `partial`
- Primary layer touched: `extraction`
- Expected advisory output: cheaper structural grounding so deeper passes can produce better failure-mode, task, and risk answers
- Verification: confirm the stage reduces structural authoring effort without reducing structural fact usefulness or behavioral fact quality

Interpretation:

- this work is allowed because it supports core advisory questions
- it is not itself the core product value
- it should therefore stay narrow and avoid becoming a second canonical knowledge system

## 4. Proposed Insertion Point

Recommended run order:

1. `tools/ws5_remote_ingestion.py`
2. `tools/ws4_master_compiler.py`
3. `tools/ws6_clone_prep.py`
4. `tools/ws6_structural_prepass.py` proposed
5. WS6 deep authoring against code + docs + pre-pass artifact
6. `tools/ws6_deep_integrator.py --run-validation-suite`
7. `tools/ws7_read_model_compiler.py`

The pre-pass belongs after clone prep because it depends on a local code checkout.
It does not belong before intake or WS4 because it is repo-local analysis, not intake metadata.

## 5. Core Design

The pre-pass should produce a non-canonical structural artifact.

That artifact should be:

- deterministic or mostly deterministic
- cheap to regenerate
- grounded in the checked-out source tree
- detailed enough to help orientation
- narrow enough that it does not become a shadow ontology

The pre-pass should not directly write canonical facts.

Instead:

- deep authoring can read the artifact to understand the repo quickly
- WS6 can optionally materialize selected structural facts from it through the normal canonical path

This preserves the existing trust boundary.

## 6. Proposed Artifact Shape

Suggested artifact location:

- `reports/ws6_structural_prepass/<batch_id>/<repo_slug>.yaml`

Suggested top-level shape:

```yaml
repo: getzep/graphiti
node_id: repo::getzep/graphiti
generated_at_utc: "2026-03-20T12:00:00Z"
generator:
  tool: ws6_structural_prepass.py
  version: "0.1"
  mode: "ast_plus_filesystem"
source_root: /abs/path/to/clone
languages:
  - python
  - typescript
entrypoints:
  - path: server/main.py
    kind: app_entry
  - path: mcp_server/main.py
    kind: mcp_entry
package_roots:
  - path: graphiti/
module_groups:
  - name: graph_core
    paths:
      - graphiti/core/
    rationale: "contains graph model and retrieval logic"
  - name: ingestion
    paths:
      - graphiti/ingest/
filesystem_signals:
  config_files:
    - pyproject.toml
    - docker-compose.yml
  manifests:
    - requirements.txt
symbol_index:
  classes: 114
  functions: 389
dependency_signals:
  internal_modules:
    - graphiti.retrieval
    - graphiti.storage
  external_packages:
    - neo4j
    - fastapi
    - openai
structural_candidates:
  components:
    - name: retrieval engine
      evidence:
        - path: graphiti/retrieval/
    - name: mcp server
      evidence:
        - path: mcp_server/
  extension_points:
    - name: storage backend
      evidence:
        - path: graphiti/storage/
orientation_hints:
  likely_first_read:
    - graphiti/retrieval/
    - graphiti/storage/
    - server/main.py
  likely_runtime_surfaces:
    - fastapi app
    - mcp server
limitations:
  - "component grouping is heuristic"
  - "no behavioral claims"
```

The artifact should avoid free-form prose except for short rationale fields.

## 7. What the Pre-Pass Should and Should Not Do

### It should do

- enumerate files, modules, packages, and likely entrypoints
- detect package roots and major internal namespaces
- extract low-risk structural candidates such as components, extension points, and API surfaces
- surface orientation hints for later passes
- expose raw evidence paths for every structural claim

### It should not do

- infer failure modes
- infer implementation patterns from structure alone
- infer operational tasks unless directly documented in machine-readable sources
- emit canonical facts directly
- replace repo documentation review

This line matters because structure is inferable and cheap; behavior is where the advisory value lives.

## 8. How WS6 Should Consume It

WS6 should consume the artifact in two ways.

### 8.1 Authoring aid

The artifact becomes the orientation sheet for deep authoring.

Benefits:

- less time spent finding entrypoints and module boundaries
- more consistent structural coverage
- more attention available for tasks, failures, and protocols

### 8.2 Structural fact source, but only through WS6

WS6 may use the artifact as evidence for selected structural predicates such as:

- `has_component`
- `has_extension_point`
- `has_config_option` when derived from machine-readable config surfaces

But those facts should still be emitted by WS6 through normal canonical logic with explicit provenance.

That keeps canonical generation in one place.

## 9. Recommended Canonical Boundary

Two boundary choices were discussed.

### Option A

- pre-pass produces a non-canonical artifact
- WS6 converts selected structural signals into canonical structural facts
- full detailed index remains external

### Option B

- pre-pass produces a non-canonical artifact
- deep authoring reads it
- canonical system keeps only a normalized structural summary, or even none

Recommendation: prefer **Option A**, but narrowly.

Reason:

- the system still needs some canonical structural facts to answer cross-repo component questions
- removing structural canonicalization entirely would weaken `Q2`
- keeping the full index external avoids polluting the ontology with low-value detail

So the best boundary is:

- full structural map stays non-canonical
- only selected normalized structural facts enter canonical WS6 output

This is a shrinkage strategy, not a deletion strategy.

## 10. Provenance and Contract Implications

If WS6 starts materializing facts derived from the pre-pass, the current deep-fact contract likely needs a small provenance extension.

Current provenance is oriented around:

- source files
- sections
- extraction mode
- evidence objects

That is close, but not quite enough for a structural pre-pass source.

Likely need:

- a provenance marker such as `extraction_mode: structural_prepass_assisted`
- evidence entries that point to file paths, module roots, or generated artifact references
- a clear rule that the pre-pass is evidence support, not an alternate canonical source enum

Preferred first move:

- do not add a new canonical `source`
- keep canonical source semantics unchanged
- encode pre-pass assistance in fact-level provenance first

That is the smallest change with the least architectural spill.

## 11. Likely Implementation Slice

Smallest useful first slice:

1. read clone path from the existing clone manifest
2. scan filesystem shape and language manifests
3. identify package roots and entrypoints
4. emit `module_groups`, `entrypoints`, `dependency_signals`, and `orientation_hints`
5. do not yet emit component names automatically beyond obvious directory/service names
6. feed the artifact to one deep-authoring workflow manually before any WS6 automation change

This keeps the first version cheap, inspectable, and reversible.

## 12. Risks

### Over-fragmentation

AST and symbol tools can produce too much detail.
If every module or class becomes a candidate component, the artifact becomes noisy and harms orientation instead of helping it.

### False confidence

A clean structural map can make a repo feel understood when only its shape is understood.
This is especially risky for tasks, failures, and patterns.

### Ontology drift

If pre-pass labels become canonical too early, the ontology will start reflecting tool heuristics instead of cross-repo normalization needs.

### Second-system risk

If the artifact grows query features, graph logic, and its own semantics, it becomes a parallel knowledge system.
That should be avoided.

## 13. What Success Looks Like

Success is not "we built a clever indexer."

Success is:

- WS6 authors spend less time reconstructing repo shape
- structural fact generation becomes cheaper and more consistent
- behavioral sections improve because attention shifts toward them
- canonical facts remain normalized and provenance-aware

## 14. Verification by Stage

The pre-pass cannot be verified as a full system yet because it does not exist.

So verification should happen in stages.

### Stage 1: design verification

Check that the sketch preserves:

- canonical YAML as source of truth
- WS6 as the only canonical structural fact emitter
- non-inferability as the Phase 5 constraint

### Stage 2: artifact usefulness verification

On a small repo sample, check whether the artifact helps a human or LLM answer:

- where are the entrypoints?
- what are the main internal subsystems?
- what should be read first?

### Stage 3: pipeline usefulness verification

Compare a small batch before and after pre-pass assistance:

- time spent producing structural sections
- structural fact parity or quality
- behavioral fact count and quality
- mismatch and audit behavior

This is enough to validate the direction before any broad pipeline rewrite.

## 15. Bottom Line

The right move is not to eliminate structural facts.

The right move is to make structural understanding cheaper, more mechanical, and less attention-hungry so that the expensive pass can focus on non-inferable advisory value.

A `ws6_structural_prepass` stage is a plausible way to do that if it remains:

- non-canonical
- narrow
- evidence-oriented
- subordinate to WS6 rather than parallel with it
