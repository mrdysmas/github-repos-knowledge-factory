## Scope Control

Default mode is execution and supervision, not exploration.

- Do not perform exploratory analysis unless explicitly requested.
- If context is sufficient to execute, execute.
- If blocked, report blocker and 2-3 options with tradeoffs.
- Keep responses concise and decision-oriented.
- Re-audit or broad re-scans require explicit user request.
- Treat unsolicited exploration as scope creep.
- Ask for confirmation before any broad discovery step.

## Status Routing

- Current status source of truth: `project_status.yaml`.
- Historical phase tracker and evidence narrative: `master_graph_merge_progress.yaml`.
- Canonical generated artifacts: `master_index.yaml` and `master_graph.yaml`.
- Canonical update path: `inputs/ws5/ws5_input_manifest.yaml` -> `tools/ws5_remote_ingestion.py` -> WS1/trust/shard gates -> `tools/ws4_master_compiler.py`.
- `kgraph-repos` is non-canonical (draft/raw discovery only) and must be mapped through WS1/WS5 pipeline before master compile.

## Intake Enforcement

- Intake source catalog: `master_repo_list.yaml` (intake backlog only; not canonical).
- Intake queue artifact: `inputs/intake/intake_queue.yaml` (generated).
- Queue generator: `tools/build_intake_queue_from_master_repo_list.py`.
- Queue sync gate: `tools/check_intake_queue_sync.py` (must pass before intake execution).
- Add new candidates using `tools/add_repo_candidate.py`; do not hand-edit queue files.

Required preflight before intake work:
- `python3 tools/check_intake_queue_sync.py --workspace-root .`

Required command to add a new candidate:
- `python3 tools/add_repo_candidate.py --workspace-root . --github-url https://github.com/<owner>/<repo>`

## Runbook Command Policy

- Any `required_commands` or `first_commands` entries in status/runbook artifacts must be directly executable from repo root.
- Do not use pseudo-command aliases (example: `spec.yaml --run-validation-suite`); use canonical interpreter-prefixed commands (example: `python3 tools/ws6_deep_integrator.py ...`).
