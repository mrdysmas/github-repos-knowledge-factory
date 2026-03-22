---
name: pipeline-orient
description: Pipeline data-flow orientation for this repo's corpus operations. Required reading before running any ws4/ws5/ws6/ws7 command, writing to repos/knowledge/, or executing a bead that involves adding or updating a repo. Prevents silent pipeline failures caused by writing to the wrong directory.
---

# pipeline-orient

Orient yourself to the corpus pipeline before touching it.

## Directory Data Flow

```
repos/knowledge/repos/      ← INPUT  — shallow repo entries (name, category, summary, URLs)
repos/knowledge/deep/       ← INPUT  — narrative YAML files (architecture, tasks, failures, protocols)
repos/knowledge/deep_facts/ ← OUTPUT — do NOT write here; WS6 writes this from the two inputs above
```

Writing a file to `deep_facts/` directly is silently ignored — the pipeline will not pick it up and
will produce no error. Always write to `repos/` (shallow) and `deep/` (narrative), then run the pipeline.

## Operation → Stage Mapping

| Operation | Files to write | Pipeline stages to run |
|---|---|---|
| Add new repo | `repos/<stem>.yaml` + `deep/<stem>.yaml` | ws4 → ws6 → ws7 |
| Fix category on existing repo | Edit `deep/<stem>.yaml` (change `category:`) | ws4 → ws6 → ws7 |
| Backfill narrative (update facts) | Edit `deep/<stem>.yaml` | ws6 → ws7 |
| Archetype-only change | Edit `tools/ws6_soft_audit.py` only | ws7 only |
| Pre-pass calibration batch | Uses `ws6_structural_prepass.py` — entirely separate, not part of the main sequence |

## Canonical Pipeline Sequence

```bash
python3 tools/ws4_master_compiler.py --workspace-root .
python3 tools/ws6_deep_integrator.py --workspace-root . --run-validation-suite
python3 tools/ws7_read_model_compiler.py --workspace-root .
python3 tools/ws6_soft_audit.py --workspace-root .   # verification pass
```

ws5 (`ws5_remote_ingestion.py`) is only needed when pulling fresh remote metadata for a new repo.
Skip it for category fixes, backfills, and archetype changes.

## Category Assignment

The `category:` field in the narrative file (`deep/<stem>.yaml`) determines which archetype the repo
matches in the soft audit. Pre-pass manifests use provisional categories (e.g. `infra_ops`) — these
must be replaced with the specific category for the intended archetype in the deep file.

Current archetype → category mappings for new shapes:

| Archetype | Category value to set |
|---|---|
| `helm_chart_repo` | `helm_chart_repo` |
| `k8s_operator` | `k8s_operator` |
| `sdk_library` | `sdk_client` or `sdk_monorepo` |
| `plugin_ecosystem` | `plugin_ecosystem` |

Full archetype list: `tools/ws6_soft_audit.py` → `ARCHETYPES` dict.
Design guidance: `docs/decisions/archetype_definition_process_decision_2026-03-22.md`.

## Verification

After any pipeline run, confirm with:

```bash
python3 tools/ws6_soft_audit.py --workspace-root .
```

Check that the target repo's archetype shows `full` in the summary, not `unmatched` or `thin`.
