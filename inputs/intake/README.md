# Intake Queue Workflow

Use this folder as the intake control plane.

Files:
- `intake_manifest.yaml`: Lifecycle model and progression gates.
- `prune_policy.yaml`: Clone retention/deletion safety rules.
- `intake_queue.yaml`: Pull-on-demand queue generated from `master_repo_list.yaml`.
- `pilot_batch.yaml`: Active pilot execution state (selected repos, provenance, lifecycle status, `domain_hint` metadata).

## Refresh Queue

```bash
python3 tools/build_intake_queue_from_master_repo_list.py \
  --workspace-root . \
  --source master_repo_list.yaml \
  --master-index master_index.yaml \
  --output inputs/intake/intake_queue.yaml
```

## Add New Candidate (Enforced Path)

```bash
python3 tools/add_repo_candidate.py \
  --workspace-root . \
  --github-url https://github.com/<owner>/<repo>
```

This updates:
- `master_repo_list.yaml`
- `inputs/intake/intake_queue.yaml`

## Queue Sync Check (Required Preflight)

```bash
python3 tools/check_intake_queue_sync.py --workspace-root .
```

This check is strict: it validates queue sync and blocks invalid `domain_hint` values in `pilot_batch.yaml` using the allowlist in `intake_manifest.yaml` (`classification_strategy.domain_hint.suggested_values`).
It also enforces alias normalization via `classification_strategy.domain_hint.alias_map`: alias values fail by default, and `--fix` rewrites aliases to canonical values.

## How to Use

1. Refresh queue.
2. Select `canonical_status: queued` entries for next batch (8-12 recommended).
3. Clone selected repos only when needed for scanning.
4. Assign/confirm `domain_hint` metadata for selected repos (metadata-only; does not change shard gates).
5. Run shallow-first canonicalization flow.
6. Mark top deep candidates and apply deep scan on demand.
7. Apply prune policy to remove clones after extraction when safe.

For Phase 4 batch execution (full end-to-end), run in this order:
`tools/ws5_remote_ingestion.py` -> `tools/ws4_master_compiler.py` ->
`tools/ws6_deep_integrator.py --run-validation-suite` ->
`tools/ws7_read_model_compiler.py` (strict first; use `--force` only for
snapshot/timestamp-only mismatch).
