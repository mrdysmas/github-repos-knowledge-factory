# Soft Audit Tool — Kickoff Prompt

**Tool to build:** `tools/ws6_soft_audit.py`  
**Repo:** `https://github.com/mrdysmas/github-repos-knowledge-factory`  
**Branch:** `main`  
**Date:** 2026-03-18

---

## What you are building

A standalone audit script that reads `knowledge.db`, checks each repo against its archetype's coverage requirements, and emits a machine-readable per-repo coverage report.

This is a read-only diagnostic tool. It does not modify any facts, YAML files, or pipeline state. It produces a report file and exits.

Read `AGENTS.md` at the repo root before doing anything else.

---

## Why this tool exists

The contract redesign (`contracts/deep_narrative_contract.md` v2.0) introduced archetype requirements — three repo categories with required evidence families. The backfill ran and moved predicate counts significantly. This tool answers the question: *which repos still have coverage gaps, and what specifically are they missing?*

It also establishes the baseline for archetype expansion decisions. Future archetypes get added to the tool's configuration, not to its logic.

---

## Design specification

### Location and invocation

```
tools/ws6_soft_audit.py
```

```bash
python3 tools/ws6_soft_audit.py --workspace-root .
```

Optional flags:
- `--output-dir <path>` — where to write the report (default: `reports/ws6_soft_audit/`)
- `--db <path>` — path to knowledge.db (default: `<workspace-root>/knowledge.db`)
- `--archetype <name>` — audit only one archetype (default: all)

### Core data structures

Define these two constants at the top of the file. They are the only place archetype logic lives — adding a new archetype later means adding one entry to `ARCHETYPES`, nothing else.

```python
FAMILY_PREDICATES = {
    "structure":   ["has_component", "has_config_option"],
    "tasks":       ["supports_task"],
    "failures":    ["has_failure_mode"],
    "protocols":   ["uses_protocol", "exposes_api_endpoint", "has_extension_point"],
}

ARCHETYPES = {
    "inference_serving": {
        "categories": ["inference_serving"],
        "required_families": ["structure", "tasks", "failures"],
        "recommended_families": ["protocols"],
        "predicate_checks": {},
    },
    "vector_database": {
        "categories": ["vector_database", "vector_databases"],
        "required_families": ["structure", "failures"],
        "recommended_families": ["tasks", "protocols"],
        "predicate_checks": {},
    },
    "tunneling": {
        "categories": ["tunneling", "vpn_mesh", "network_infrastructure"],
        "required_families": ["structure", "protocols"],
        "recommended_families": ["failures", "tasks"],
        "predicate_checks": {
            # For this archetype, protocols family presence is not enough —
            # at least one uses_protocol fact is required specifically.
            # has_extension_point alone does not satisfy this archetype.
            "protocols": "uses_protocol",
        },
    },
}
```

### Logic

For each repo in `knowledge.db`:

1. Look up the repo's `category` from the `repos` table.
2. Match the category against `ARCHETYPES` — find the archetype whose `categories` list contains this category. If none match, the repo is unmatched (audit for unmapped sections only — see below).
3. For each family in the archetype's `required_families`:
   - Query the `facts` table: does this repo have at least one fact where `predicate` is in `FAMILY_PREDICATES[family]`?
   - If a `predicate_checks` entry exists for this family, additionally verify that at least one fact has that specific predicate (not just any predicate in the family).
4. Classify the repo:
   - `behavioral_coverage: full` — all required families present, all predicate checks pass
   - `behavioral_coverage: thin` — one or more required families absent or predicate check failed
   - `behavioral_coverage: unmatched` — repo category has no archetype definition

### Unmapped section check (all repos)

Separately from archetype coverage, flag any repo whose deep facts include a `source_section` value that is not in the recognized section list. These are unmapped sections — they produced no facts and indicate a contract violation or WS6 gap.

The recognized section list is available in `contracts/deep_narrative_contract.md` under "Section Reference". You can hardcode this list in the script or read it from the contract file — your choice, but hardcoding is simpler and more reliable.

---

## Output

### Report file

Write to `reports/ws6_soft_audit/<timestamp>_audit.yaml`. Timestamp format: `YYYYMMDD_HHMMSS`.

Also write a symlink or copy at `reports/ws6_soft_audit/latest_audit.yaml` pointing to the most recent run.

### Report structure

```yaml
audit_metadata:
  generated_at: "2026-03-18T14:23:00Z"
  total_repos: 122
  archetypes_checked: [inference_serving, vector_database, tunneling]
  repos_matched: 42
  repos_unmatched: 80
  repos_thin: 7
  repos_full: 35

summary_by_archetype:
  inference_serving:
    total: 6
    full: 6
    thin: 0
    thin_repos: []
  vector_database:
    total: 10
    full: 9
    thin: 1
    thin_repos: [ladybugdb/ladybug]
  tunneling:
    total: 17
    full: 14
    thin: 3
    thin_repos: [ekzhang/bore, ...]

coverage_records:
  - repo: ladybugdb/ladybug
    node_id: "repo::ladybugdb/ladybug"
    category: vector_database
    archetype: vector_database
    families_present: [structure]
    families_missing: [failures]
    predicate_check_failures: []
    behavioral_coverage: thin
    flags:
      - "required family 'failures' absent — no has_failure_mode facts"

  - repo: ekzhang/bore
    node_id: "repo::ekzhang/bore"
    category: tunneling
    archetype: tunneling
    families_present: [structure, protocols]
    families_missing: []
    predicate_check_failures: []
    behavioral_coverage: full
    flags: []

  - repo: some/repo
    node_id: "repo::some/repo"
    category: agent_framework
    archetype: null
    families_present: []
    families_missing: []
    predicate_check_failures: []
    behavioral_coverage: unmatched
    flags: []
```

Only include repos where `behavioral_coverage` is `thin` or `unmatched` in `coverage_records` by default. Full repos are counted in the summary but not listed individually — the report would be unreadably long otherwise. Add a `--include-full` flag to include them if needed.

### stdout summary

Print a brief human-readable summary after writing the report:

```
Soft audit complete — 122 repos checked.

Archetype coverage:
  inference_serving  6/6 full
  vector_database    9/10 full  (1 thin)
  tunneling         14/17 full  (3 thin)
  unmatched         80 repos (no archetype defined)

Thin repos:
  vector_database:
    ladybugdb/ladybug — missing: failures
  tunneling:
    ekzhang/bore — missing: (none — full)
    ...

Report written to: reports/ws6_soft_audit/20260318_142300_audit.yaml
```

---

## Database access pattern

Connect to `knowledge.db` directly via `sqlite3`. Do not invoke `query_master.py` as a subprocess — query the DB directly. The schema is:

```sql
-- Repos table
repos (node_id, name, github_full_name, html_url, category, shard, summary, source, raw_yaml)

-- Facts table
facts (fact_id, node_id, fact_type, predicate, object_kind, object_value,
       confidence, note, as_of, source_file, source_section, raw_yaml)
```

Key queries you'll need:

```sql
-- All repos and their categories
SELECT node_id, name, github_full_name, category FROM repos ORDER BY category, name;

-- Does this repo have any facts for a given predicate?
SELECT COUNT(*) FROM facts WHERE node_id = ? AND predicate = ?;

-- Does this repo have any facts from a list of predicates?
SELECT COUNT(*) FROM facts WHERE node_id = ? AND predicate IN (?, ?, ...);

-- All distinct source_section values for a repo (for unmapped section check)
SELECT DISTINCT source_section FROM facts WHERE node_id = ? AND source_section IS NOT NULL;
```

---

## Error handling

- If `knowledge.db` does not exist, exit with a clear error message: `knowledge.db not found at <path>. Run ws7_read_model_compiler.py first.`
- If a repo has no facts at all (not just no matching facts), note it in the coverage record with a flag: `"no facts extracted — deep file may be missing or empty"`
- Do not crash on unexpected category values — treat them as unmatched

---

## What good output looks like after B12

After the B12 backfill, the expected state is approximately:

- `inference_serving`: all 6 repos full (vllm, ollama, llama.cpp, xinference, lmdeploy, nexa_sdk all have Tasks + Failures)
- `vector_database`: 9/10 full (milvus was already covered; all 9 backfill targets now have Failures). One possible thin: if any file's troubleshooting section didn't parse into facts for some reason.
- `tunneling`: most should be full after the backfill added protocol sections. A few may still be thin if the agent wrote weak entries that WS6 couldn't extract.

If the actual results differ significantly from this, that's useful signal — not an error in the tool.

---

## Commit instructions

After the tool is written and produces clean output:

1. Run it against the current `knowledge.db` and confirm the report generates without errors
2. Commit in a single commit:
   - `tools/ws6_soft_audit.py`
   - `reports/ws6_soft_audit/<timestamp>_audit.yaml` (the first run output)
   - `reports/ws6_soft_audit/latest_audit.yaml`
3. Do NOT modify `project_status.yaml` or `phase_4_progress_tracker.yaml` — the supervisor handles control-plane updates

Commit message format: `add ws6_soft_audit.py — archetype coverage audit tool`

---

## Reference files

| File | Why |
|---|---|
| `AGENTS.md` | Read before any work |
| `contracts/deep_narrative_contract.md` | Archetype definitions and section reference |
| `tools/query_master.py` | Reference for how to connect to knowledge.db and query it |
| `tools/ws7_read_model_compiler.py` | SQLite schema source of truth (see `CREATE TABLE` blocks) |
| `reports/ws6_deep_integration/` | Example of how existing report files are structured |
