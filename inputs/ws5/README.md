# WS5 Remote Refresh Workflow

This document defines the remote-only refresh strategy used by
`tools/ws5_remote_ingestion.py`.

## Scope

- Remote repositories can be refreshed without local clone contents.
- Input comes from `inputs/ws5/ws5_input_manifest.yaml`.
- Supported remote sources remain `remote_api` and `remote_metadata`.

## Field Precedence

Refresh uses strict precedence for required repository fields:

1. API/manifest values (primary)
2. `readme_fallback` values (only when the required primary field is missing)
3. Manifest `defaults` (only after API + README fallback for that field)

Required fields affected by README fallback:

- `category`
- `summary`
- `core_concepts`
- `key_entry_points`
- `build_run`

`readme_fallback` must be a mapping when provided.

## Fallback Usage Metadata

Each materialized repo record stores refresh metadata under `extras.refresh`
or `extras.remote.refresh` (when `remote` metadata is present):

- `precedence: api_wins_readme_for_missing_required_fields`
- `fallback_source: readme_fallback`
- `fallback_used: <true|false>`
- `fields_filled_from_readme: [...]` (present only when fallback was used)

## Determinism Rules

- Write order is stable on the normalized tuple `(target_shard, file_stem, github_full_name)`.
- `target_shard` is compatibility-only for manifest inputs; committed WS5 repo records always resolve to the unified shard at `repos/knowledge/repos/`.
- `fields_filled_from_readme` is sorted.
- Report booleans and counters are deterministic for identical inputs.
- Rerunning with unchanged inputs produces hash-stable WS5 artifacts.
