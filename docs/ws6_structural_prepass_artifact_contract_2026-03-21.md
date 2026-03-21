# WS6 Structural Pre-Pass Artifact Contract

Date: 2026-03-21
Issue: `github_repos-kfk`
Related:
- `docs/ws6_structural_prepass_sketch_2026-03-20.md`
- `docs/decisions/ws6_retrieval_helper_decision_2026-03-21.md`
- `contracts/deep_narrative_contract.md`
- `phase_5_anchor_acceptance_rubric.yaml`

## 1. Decision Summary

This document defines the minimum viable contract for a proposed `ws6_structural_prepass` stage.

The contract is intentionally narrow:

- the artifact is non-canonical
- the artifact is generated from the checked-out repo, not from a retrieval service
- helper tools may assist generation later, but are not required and do not define the schema
- canonical facts still enter the system only through WS6

This contract is unblocked by `github_repos-5n8`.
Per `docs/decisions/ws6_retrieval_helper_decision_2026-03-21.md`, a Kodit-style helper is optional and deferred, so this artifact must stand on filesystem, manifest, entrypoint, config/routing, and import signals first.

`github_repos-6ju` was not activated, so this contract does not assume graph-native enrichment.

## 2. Phase 5 Rubric Pass

Acceptance rubric
- Anchor question served: `Q2` most directly, with support for `Q6`
- Non-inferable?: `partial`
- Primary layer touched: `extraction`
- Expected advisory output: cheaper, more consistent structural grounding so WS6 effort shifts toward failures, tasks, protocols, and other higher-value advisory facts
- Verification: review whether the artifact improves orientation without widening canonical scope; later compare pre-pass-assisted authoring against manual orientation on a bounded repo sample

Interpretation:

- this work is in scope because it improves how the system answers component-discovery and inspection-priority questions
- it only passes because it stays subordinate to higher-value non-inferable WS6 output
- if it starts acting like a second knowledge system, it fails the rubric intent

## 3. Scope

The contract covers:

- artifact location and naming
- minimum schema
- evidence and provenance requirements
- allowed and forbidden claim types
- WS6 consumption boundary
- the smallest likely WS6 provenance change if selected structural facts are later materialized

The contract does not define:

- a required implementation script
- a retrieval/indexing service
- a graph model
- direct canonical fact emission

## 4. Artifact Location and Naming

One artifact is produced per checked-out repo.

Canonical location pattern:

- `reports/ws6_structural_prepass/<batch_id>/<file_stem>.yaml`

Naming rules:

- `batch_id` must match the batch or execution context already used for the surrounding run
- `file_stem` should match the repo shallow/deep naming convention: `owner__repo`
- the artifact path is batch-scoped and disposable; regeneration is expected

Example:

- `reports/ws6_structural_prepass/B13/getzep__graphiti.yaml`

Rationale:

- reusing `file_stem` avoids inventing another repo identifier
- keeping output under `reports/` makes the non-canonical boundary explicit

## 5. Contract Goals

The artifact exists to answer three orientation questions cheaply:

1. where are the likely entrypoints and runtime surfaces?
2. what package roots, namespaces, and module groups shape the repo?
3. what should an author inspect first before writing deep behavioral sections?

It is not meant to answer:

- what failure modes exist
- what implementation patterns are significant across repos
- what tasks are important unless those tasks are present in machine-readable surfaces

## 6. Minimum Schema

Required top-level fields:

```yaml
schema_version: "0.1"
repo:
  github_full_name: "getzep/graphiti"
  node_id: "repo::getzep/graphiti"
  file_stem: "getzep__graphiti"
artifact:
  generated_at_utc: "2026-03-21T12:00:00Z"
  stage: "ws6_structural_prepass"
  mode: "filesystem_manifest_entrypoint"
  output_file: "reports/ws6_structural_prepass/B13/getzep__graphiti.yaml"
batch:
  batch_id: "B13"
  clone_manifest: "reports/ws6_clone_prep/B13/clone_manifest.yaml"
source:
  repo_root: "/abs/path/to/clone"
  languages:
    - "python"
    - "typescript"
signals_used:
  - "filesystem"
  - "manifest"
  - "entrypoint"
  - "config_routing"
  - "imports"
package_roots:
  - path: "graphiti/"
    evidence:
      - kind: "directory"
        path: "graphiti/"
entrypoints:
  - path: "server/main.py"
    kind: "app_entry"
    confidence: "high"
    evidence:
      - kind: "filepath"
        path: "server/main.py"
module_groups:
  - name: "retrieval"
    paths:
      - "graphiti/retrieval/"
    rationale: "directory grouping plus import concentration"
    confidence: "medium"
    evidence:
      - kind: "directory"
        path: "graphiti/retrieval/"
filesystem_signals:
  manifests:
    - path: "pyproject.toml"
      kind: "python_manifest"
  config_files:
    - path: "docker-compose.yml"
      kind: "runtime_config"
dependency_signals:
  internal_modules:
    - "graphiti.storage"
  external_packages:
    - "fastapi"
orientation_hints:
  likely_first_read:
    - "server/main.py"
    - "graphiti/retrieval/"
  likely_runtime_surfaces:
    - "server/main.py"
limitations:
  - "module groups are heuristic"
  - "no behavioral or cross-repo claims"
```

## 7. Field Semantics

### 7.1 Identity and run context

- `schema_version` identifies the artifact contract version, not a canonical schema version
- `repo.*` must match existing canonical repo identity values where those already exist
- `artifact.output_file` records the artifact path relative to repo root for traceability
- `batch.clone_manifest` points to the clone-prep artifact that established the local checkout

### 7.2 Signal disclosure

- `signals_used` is required so downstream consumers know how rich or weak the artifact is
- allowed values for v0.1 are:
  - `filesystem`
  - `manifest`
  - `entrypoint`
  - `config_routing`
  - `imports`
  - `targeted_ast`
- `targeted_ast` is optional and should appear only when simpler signals were insufficient for a specific claim

### 7.3 Structural sections

Required sections:

- `package_roots`
- `entrypoints`
- `module_groups`
- `filesystem_signals`
- `orientation_hints`
- `limitations`

Optional sections:

- `dependency_signals`
- `structural_candidates`
- `api_surfaces`
- `extension_points`

Optional sections should be omitted when the signal quality is weak.
Do not emit empty arrays just to satisfy shape expectations.

## 8. Evidence and Provenance Requirements

Every non-trivial structural claim must carry evidence.

Minimum evidence rules:

- every `package_roots` entry must cite at least one directory or manifest path
- every `entrypoints` entry must cite at least one concrete file path
- every `module_groups` entry must cite one or more concrete paths
- every optional `structural_candidates`, `api_surfaces`, or `extension_points` entry must cite direct evidence paths and a confidence level

Evidence object shape for v0.1:

```yaml
- kind: "filepath|directory|manifest|import|route_decl|ast_anchor"
  path: "relative/path/from/repo/root"
  detail: "optional short note"
```

Provenance rules:

- all paths in evidence objects are repo-relative
- `source.repo_root` may be absolute because it describes the checked-out environment, but no downstream canonical consumer should rely on that absolute path as stable identity
- rationales must stay short and local to the claim they support
- limitations must explicitly state where heuristics or partial coverage apply

## 9. Allowed and Forbidden Claims

The artifact may claim:

- package roots
- likely entrypoints
- likely runtime surfaces
- module groups based on concrete path/layout/import evidence
- config/routing surfaces
- candidate extension points or API surfaces when directly evidenced

The artifact may not claim:

- failure modes
- remediation advice
- cross-repo typicality
- implementation-risk judgments
- behavioral task importance inferred from code shape alone
- canonical component identity beyond a local candidate label

The artifact may contain heuristics, but each heuristic claim must carry:

- explicit evidence
- `confidence`
- a matching limitation when over-grouping or under-grouping is plausible

## 10. Consumption Boundary

WS6 may consume the artifact in exactly two ways.

### 10.1 Authoring aid

Deep authoring may read the artifact as an orientation sheet to:

- find likely entrypoints faster
- identify candidate subsystem boundaries
- prioritize files for code/document review

This use is advisory only.
The artifact does not replace source review, doc review, or evidence collection for deep narrative sections.

### 10.2 Evidence support for selected structural facts

WS6 may later use this artifact as supporting evidence for a narrow subset of structural predicates, such as:

- `has_component`
- `has_extension_point`
- `has_config_option` when grounded in machine-readable config surfaces

Boundary rules:

- WS6 remains the only canonical fact emitter
- the artifact does not write canonical files directly
- canonical normalization still happens in WS6, not in the pre-pass
- the full artifact is never treated as canonical inventory

## 11. Likely WS6 Contract Changes If Materialization Is Added

No immediate change to canonical `source` semantics is recommended.

If WS6 later materializes selected structural facts from this artifact, prefer the smallest provenance extension:

- add a fact-level provenance marker such as `extraction_mode: structural_prepass_assisted`
- allow evidence objects that reference the generated artifact path in addition to repo-relative code paths
- keep direct repo evidence paths attached whenever possible so canonical facts are not justified only by the generated artifact

Preferred rule:

- the artifact may assist selection and grouping
- canonical provenance should still point back to concrete repo paths, with the artifact recorded as an assistive source rather than the sole source

This avoids turning the artifact into a second canonical source enum.

## 12. Validation Expectations

The artifact should be reviewable with simple checks before any pipeline coupling:

1. identity fields match the repo being analyzed
2. every required section is present
3. every non-trivial claim has at least one evidence object
4. no forbidden behavioral or cross-repo claims appear
5. limitations disclose heuristic use

Early usefulness review should ask:

- could an author find entrypoints faster from this file?
- do module groups look like human-meaningful subsystems rather than parser trivia?
- did the artifact stay narrow enough that it did not become a shadow ontology?

## 13. First Implementation Slice

The smallest acceptable first implementation for this contract is:

1. read clone paths from the existing clone manifest
2. detect languages, manifests, package roots, and obvious entrypoints
3. emit `package_roots`, `entrypoints`, `module_groups`, `filesystem_signals`, and `orientation_hints`
4. omit AST-derived enrichment unless a concrete repo needs it
5. keep consumption manual at first: deep authoring reads the file before any WS6 automation change

This is the narrow contract that current decisions support.

## 14. Bottom Line

The `ws6_structural_prepass` artifact is a disposable orientation scaffold, not a new source of truth.

Its value comes from making repo-local structure cheaper to recover so WS6 attention can move toward the harder and more valuable behavioral facts.
If the artifact starts widening into a queryable structural mirror of the repo, it has crossed the intended boundary.
