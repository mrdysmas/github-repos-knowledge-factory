# Path Audit: `ext_sources/github_repos` Move

Date: 2026-03-20
Issue: `github_repos-t0t`
Audited path: `/home/abe/scripts/ext_sources/github_repos`
Planned target: `/home/abe/scripts/github_repos`

## Scope

Audit command used for workspace scan:

```bash
rg -n --hidden --glob '!**/.git/**' \
  '/home/abe/scripts/ext_sources/github_repos|~/scripts/ext_sources/github_repos|/Users/szilaa/scripts/ext_sources/github_repos|ext_sources/github_repos' \
  /home/abe/scripts
```

Additional code-only check inside this repo:

```bash
rg -n '/home/abe/scripts/ext_sources/github_repos|~/scripts/ext_sources/github_repos|/Users/szilaa/scripts/ext_sources/github_repos|ext_sources/github_repos' tools
```

## Result

No hardcoded repo-root references were found in `tools/`.

The remaining hits fall into three groups:

1. Move-blocking manifests and generated canonical/intake artifacts inside this repo.
2. Documentation and historical notes that mention the old path.
3. Generated reports and repo metadata that embed local paths and should be regenerated after the move.

No additional matches were found in sibling repos or helper scripts elsewhere under `/home/abe/scripts`.

## Move-Blocking Files

These should be updated before or immediately after the directory move because they are treated as live inputs or current status artifacts.

- `inputs/intake/intake_manifest.yaml`
  - 9 matches
  - Encodes canonical intake locations, queue generator paths, and active batch references.
- `inputs/intake/pilot_batch.yaml`
  - 13 matches
  - Encodes queue path, intake directory, and per-repo `intake_path` values.
- `inputs/intake/intake_queue.yaml`
  - 116 matches
  - Encodes queued clone locations for the current intake backlog.
- `master_repo_list.yaml`
  - 121 matches
  - Encodes `local_path` for backlog candidates.
- `master_index.yaml`
  - 40 matches
  - Encodes canonical compiled repo `directory` and `intake_path` values for current corpus entries.
- `repos/knowledge/progress.yaml`
  - 1 match
  - `target_directory` still points at the old repo root.
- `repos/knowledge/progress_llm.yaml`
  - 1 match
  - Same issue for the legacy LLM shard progress tracker.

## Non-Blocking But Stale After Move

These do not appear to drive the live pipeline, but they will become inaccurate after the move.

- `docs/query_master_reference.md`
  - 4 matches
  - Example paths for `knowledge.db`, `master_index.yaml`, `master_graph.yaml`, and `master_deep_facts.yaml`.
- `docs/phase4/prompt_audit_header_v3.yaml`
  - 1 match
  - Stores an old `workspace_root`.
- `docs/gbabe_migration_log_2026-03-20.yaml`
  - 5 matches
  - Historical migration notes with both `/home/abe/...` and `/Users/szilaa/...` paths.
- Multiple planning/docs files under `docs/` and `plan-drafts/`
  - Reference the current repo location in prose.
  - These can be updated selectively if they are still considered active operator guidance.

## Regenerate After Move

These files contain embedded local paths and are better regenerated than hand-edited.

- `reports/ws6_clone_prep/*.yaml`
  - Clone workspace paths are embedded in output.
- `reports/run_batch/*.yaml`
  - Batch verdicts reference the old workspace location.
- `reports/ws5_remote_ingestion/validation_runs.yaml`
  - Validation output references the old workspace.
- `repos/knowledge/repos/*.yaml`
  - Some shallow repo records embed old `local_path` values.
- `repos/knowledge/deep/*.yaml`
  - Some deep narratives embed old `directory` values.

## Observations

- The operational Python and shell tooling is already mostly path-relative via `--workspace-root` or `Path(...).resolve()`.
- The main migration risk is not executable code. It is stale YAML state that preserves absolute local paths.
- The scan found many `/Users/szilaa/...` paths in canonical artifacts. Those are also stale for the planned move and should be normalized, not preserved.

## Recommended Sequence

1. Move the repo to `/home/abe/scripts/github_repos`.
2. Update the move-blocking YAML inputs/status files listed above.
3. Re-run the canonical generators/compilers that rebuild derived artifacts.
4. Re-run the audit command and confirm no remaining live references to `ext_sources/github_repos`.

## Verification

Expected clean check for executable code:

```bash
rg -n '/home/abe/scripts/ext_sources/github_repos|~/scripts/ext_sources/github_repos|/Users/szilaa/scripts/ext_sources/github_repos|ext_sources/github_repos' tools
```

Expected post-move cleanup check for live artifacts:

```bash
rg -n --hidden --glob '!**/.git/**' \
  '/home/abe/scripts/ext_sources/github_repos|~/scripts/ext_sources/github_repos|/Users/szilaa/scripts/ext_sources/github_repos|ext_sources/github_repos' \
  inputs/intake master_repo_list.yaml master_index.yaml repos/knowledge/progress.yaml repos/knowledge/progress_llm.yaml
```
