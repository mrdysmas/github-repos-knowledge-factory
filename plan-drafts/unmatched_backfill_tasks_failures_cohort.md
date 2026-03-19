# Handoff: Tasks + Failures Cohort Backfill

**Date:** 2026-03-19
**State when written:** 12 archetypes / all full / 5,985 facts / main branch clean

---

## What this is

Second cohort of the unmatched-repo backfill pass. The first cohort ("failures only" — dify, borg, tmux, gin, hugo, wezterm, capistrano) is complete. Those repos already had `supports_task` facts; we only added `troubleshooting` sections.

This cohort is the harder group: **zero or near-zero on both `supports_task` and `has_failure_mode`**. Both sections need to be written from training knowledge and added to the deep files.

---

## The 7 repos

Current predicate counts (from scan on 2026-03-19):

| repo | deep file | struct | task | fail |
|---|---|---|---|---|
| puppeteer/puppeteer | `repos/knowledge/deep/puppeteer__puppeteer.yaml` | 64 | 0 | 0 |
| mariadb/server | `repos/knowledge/deep/mariadb__server.yaml` | 75 | 0 | 0 |
| stirling-tools/stirling-pdf | `repos/knowledge/deep/stirling-tools__stirling-pdf.yaml` | 55 | 0 | 0 |
| paddlepaddle/paddleocr | `repos/knowledge/deep/paddlepaddle__paddleocr.yaml` | 45 | 1 | 0 |
| mscdex/ssh2 | `repos/knowledge/deep/mscdex__ssh2.yaml` | 48 | 0 | 0 |
| xtermjs/xterm.js | `repos/knowledge/deep/xtermjs__xterm.js.yaml` | 28 | 0 | 0 |
| mindsdb/mindsdb | `repos/knowledge/deep/mindsdb__mindsdb.yaml` | 11 | 0 | 0 |

> **Note:** Deep file paths above are inferred from naming convention — confirm with `Glob repos/knowledge/deep/*<name>*` before editing. paddleocr and stirling-pdf were already read in this session; paths confirmed.

---

## What to add to each file

Both sections, appended at the end of the deep file (after all existing sections):

**`common_tasks:`** — list-of-dicts with `name` and `description` keys. 4–6 entries. Usage patterns, not just CLI invocations.

**`troubleshooting:`** — list-of-dicts with `symptom`, `cause`, and `fix` keys. 4–5 entries. Real, documented failure modes.

**YAML gotcha:** Any value containing `: ` (colon-space) must be quoted. This burned 3 files last time (capistrano, hugo, tmux). Quote the entire value string if it contains colons.

**Format reference** (from existing files):
```yaml
common_tasks:
- name: Short task name
  description: What the user does and what it achieves.

troubleshooting:
- symptom: What the user observes going wrong
  cause: Root cause of the failure
  fix: How to resolve it
```

---

## Provenance note

These sections are training-knowledge based, not code-verified. The original deep files were extracted by codex/kgraph-repos agents with `sourcing_method: code_verified`. The backfill sections have no version anchor and carry lower confidence. **Do not update the file-level provenance headers** — this is documented at the system level in `memory/project_knowledge_provenance.md`. A structured Option B convention for future backfill is planned but not yet established.

---

## Pipeline sequence

After editing all 7 files:

```
python3 tools/ws6_deep_integrator.py --workspace-root .
```
Check for `blocking_mismatches: 0` and `gate_ready: true`. If YAML parse errors, fix them (usually unquoted colons).

```
python3 tools/ws4_master_compiler.py --workspace-root .
python3 tools/ws7_read_model_compiler.py --workspace-root .
```

Verify fact counts per repo:
```python
import sqlite3
conn = sqlite3.connect('knowledge.db')
for r in ['puppeteer/puppeteer', 'mariadb/server', ...]:
    t = conn.execute('SELECT COUNT(*) FROM facts WHERE node_id=? AND predicate=?', (f'repo::{r}', 'supports_task')).fetchone()[0]
    f = conn.execute('SELECT COUNT(*) FROM facts WHERE node_id=? AND predicate=?', (f'repo::{r}', 'has_failure_mode')).fetchone()[0]
    print(f'{r}: task={t} fail={f}')
```

Then commit:
```
git add repos/knowledge/deep/<files> repos/knowledge/deep_facts/ master_deep_facts.yaml reports/
git commit -m "feat: backfill common_tasks and troubleshooting for tasks+failures cohort ..."
```

---

## After this cohort is done

Two remaining topics:
1. **Option B provenance convention** — establish `augmentation_provenance` structure in the provenance block for future backfill sessions.
2. **Soft audit** — run `python3 tools/ws6_soft_audit.py --workspace-root .` to confirm final unmatched count and total facts, update `memory/project_archetype_expansion_state.md` and `memory/project_next_task.md`.
