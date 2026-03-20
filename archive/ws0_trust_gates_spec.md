# WS0 Trust Gates Spec

Date: 2026-02-22  
Status: Draft for execution

## Purpose

Define mandatory trust gates that must pass before any master-graph merge work proceeds.

This fixes the current false-green state where artifacts can show `READY` or `COMPLETE` while still being machine-invalid or semantically contradictory.

## Problem Statement

Current issues observed:

- Some `audit-progress.yaml` files are not valid YAML but still report successful outcomes.
- Validation behavior does not match workflow/spec claims (docs imply full-file coverage; scripts validate narrower scope).
- `progress.yaml` can mark `status: complete` while pending work remains.
- Output quality signals are therefore not reliable enough to gate downstream merge automation.

## Scope

In scope:

- Parser validity gates for all knowledge artifacts.
- Status-semantic consistency checks.
- Release/blocking policy for `READY` and `COMPLETE`.
- Minimal reporting format for gate results.

Out of scope:

- Canonical identity model (`node_id`, `github_full_name`) design.
- Relation ontology redesign.
- Master graph compiler implementation.

## Gate Definitions

### Gate G1: Parse Integrity

All tracked artifacts must parse successfully as YAML.

Required paths (per knowledge directory):

- `index.yaml`
- `graph.yaml`
- `progress.yaml`
- `audit-progress.yaml` (if present)
- `repos/*.yaml`
- `deep/*.yaml`

Failure behavior:

- Any parse error = gate fail.
- Pipeline status must be `BLOCKED`.
- `READY` or `COMPLETE` cannot be set.

### Gate G2: Status Semantic Integrity

Statuses must match actual state.

Progress rules:

- If top-level `status: complete`, then all phase statuses must be `complete`.
- If `phases.deepening.status: complete`, then `phases.deepening.pending` must be empty.
- `phases.deepening.current_batch` must be empty when deepening is complete.
- If `phases.audit.status: complete`, audit report file must exist and pass G1.

Audit rules:

- `overall_verdict: READY_FOR_PRODUCTION` or `VERIFIED_DEEP` is allowed only if file is parseable.
- If `issues_found.critical` or `issues_found.high` is non-empty, verdict cannot be a ready state.

Failure behavior:

- Any contradiction = gate fail.
- Effective run status = `BLOCKED`.

### Gate G3: Spec/Validator Contract Integrity

Documented validation scope must match implemented validation scope.

Rules:

- Skill spec cannot claim "ALL files" if validator only checks subsets.
- If behavior differs intentionally, spec must explicitly state exact scope and limits.

Failure behavior:

- Mark `WARN` initially.
- Escalate to `FAIL` for production runs after grace period.

## Required Output Artifact

Create a deterministic gate report for each run:

`knowledge/trust-gates-report.yaml`

Minimum fields:

- `metadata.run_at`
- `metadata.knowledge_dir`
- `gates.g1_parse_integrity.status`
- `gates.g1_parse_integrity.parse_errors`
- `gates.g2_status_semantics.status`
- `gates.g2_status_semantics.violations`
- `gates.g3_spec_validator_contract.status`
- `gates.g3_spec_validator_contract.findings`
- `overall_status` (`PASS`, `WARN`, `FAIL`, `BLOCKED`)
- `ready_state_allowed` (`true` or `false`)

## Enforcement Policy

Blocking rules:

- `FAIL` or `BLOCKED` means no transition to `READY` or `COMPLETE`.
- Master merge tasks (`WS1+`) cannot start until WS0 overall status is `PASS`.

Transition rules:

- `WARN` can exist only for non-production exploratory runs.
- Any production-marked run requires `PASS`.

## Implementation Plan (WS0)

1. Add parser sweep command/script for full artifact coverage.
2. Add semantic-check command/script for progress/audit consistency.
3. Add gate report generator (`trust-gates-report.yaml`).
4. Wire gate checks into current validation workflow before existing validators.
5. Update skill docs so Phase 6 scope matches implementation exactly.
6. Add regression fixture: parse-invalid audit file.
7. Add regression fixture: `complete` plus non-empty `pending` progress file.
8. Add regression fixture: clean pass case.

## Acceptance Criteria

- 100% of tracked artifacts parse in baseline run, or run is blocked.
- 0 status contradictions in baseline run, or run is blocked.
- `READY`/`COMPLETE` flags are impossible when any trust gate fails.
- Spec text and validator behavior are aligned and testable.

## Known Current Baseline Risks

- Parse-invalid audit files currently exist in observed datasets.
- Skill-bank sample corpus contains parse-invalid deep files.
- At least one progress artifact shows completion-state contradiction.

These are expected initial WS0 failures and should be used as validation fixtures.

## Open Decisions

Strict mode timing:

- Option A: enforce blocking immediately for all runs.
- Option B: one transition cycle with `WARN`, then enforce blocking.

Tooling location:

- Option A: integrate into existing `validate.py`.
- Option B: add a separate `trust_gates.py` and call it before validators.

## Recommendation

Use strict enforcement immediately and implement `trust_gates.py` as a separate preflight step.

Why:

- Separate preflight keeps responsibilities clear.
- Easier to test and reuse across all repo groups.
- Avoids silently weakening existing validators with mixed responsibilities.
