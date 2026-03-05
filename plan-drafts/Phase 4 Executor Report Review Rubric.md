# Phase 4 Executor Report Review Rubric

Use this rubric to accept or reject a Phase 4 batch report before any commit/merge decision.

## Purpose

This rubric enforces three priorities:
- Pipeline correctness (gates and integrity)
- Deep-lane outcomes (not just shallow throughput)
- Commit hygiene (no scope contamination)

If a report looks good but fails any hard gate below, reject it and request rerun or correction.

## Hard Acceptance Gates (Must All Pass)

1) **Integrity gates pass**
- WS1/trust/validate/WS6/WS7 blocking gates all PASS.
- WS7 strict-first was used.
- `--force` is only acceptable if strict WS7 failed solely on snapshot/timestamp consistency.

2) **Required metrics are coherent**
- Baseline and final counts are present and internally consistent.
- `query_master stats` values in report match current workspace values.
- Queue metrics (`queued_count`, `already_canonical_count`) match queue summary.

3) **Freshness disclosure is complete**
- Report includes before/after for:
  - `master_index.generated_at_utc`
  - `master_graph.generated_at_utc`
  - `master_deep_facts.generated_at_utc`
- Report explicitly states WS7 snapshot status (`pass` or `warn`) and fallback usage.

4) **Deep lane gate (for any deep-designated run)**
- Target deep files exist.
- Target deep_facts files exist.
- Each target deep_facts file contains at least one fact.
- Batch-level `query_master stats.deep_facts` delta is `> 0`.

5) **Evidence scope is complete and honest**
- "Files changed" list includes all touched evidence artifacts (especially WS6/WS7/trust reports).
- No hidden/omitted changed files that materially affect acceptance.

## Soft Quality Targets (Report But Do Not Auto-Fail)

- Unmapped section growth is explained and attributed.
- Per-repo deep fact counts are reasonable for repo complexity.
- Mixed-case identifier check included where required.
- Predicate/category aggregates still run normally post-change.

## Fast Validation Commands (Supervisor)

Run these before accepting report:

```bash
python3 tools/check_intake_queue_sync.py --workspace-root .
python3 tools/query_master.py stats
python3 - <<'PY'
import yaml
for p in ['master_index.yaml','master_graph.yaml','master_deep_facts.yaml']:
    d=yaml.safe_load(open(p))
    print(p, d.get('generated_at_utc'))
PY
python3 - <<'PY'
import yaml
from pathlib import Path
p=Path('reports/ws7_read_model/compile_log.yaml')
d=yaml.safe_load(p.read_text())
print('ws7_result', d['compile_run'].get('result'))
print('ws7_force_flag', d['compile_run'].get('force_flag'))
print('snapshot_status', d.get('gates',{}).get('snapshot_consistency',{}).get('status'))
PY
```

If deep run, also verify target deep_facts counts directly.

## Decision Matrix

- **ACCEPT**
  - All hard gates pass.
  - Report is complete and consistent with workspace.

- **ACCEPT WITH NOTES**
  - All hard gates pass.
  - Only soft-quality concerns remain.

- **REJECT (RERUN REQUIRED)**
  - Any hard gate fails.
  - Evidence is incomplete, inconsistent, or scope-contaminated.

## Commit Hygiene Rule

Never accept a mixed commit that bundles:
- execution artifacts and
- unrelated docs/hygiene edits

Split commits by intent:
1) execution artifacts/evidence
2) tracker/prompt/docs updates

## Required Evidence Header (Recommended Standard)

Each executor report should start with:
- hash of `phase_4_progress_tracker.yaml`
- hash of active batch prompt file
- statement whether both stayed stable during run

This makes prompt-drift and context-drift auditable.
