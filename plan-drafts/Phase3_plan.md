# Phase 3 Plan: SQLite Read Model + Query Migration

**Version:** 1.0
**Created:** 2026-03-04
**Status:** Draft — pending supervisor approval before execution begins.

---

## Objective

Build a SQLite read model that is materialized from canonical YAML artifacts as a first-class compile stage. Migrate `query_master.py` from YAML linear scans to SQLite reads. Unlock graph edge queries and cross-repo lookups through SQL joins.

Canonical YAML remains the authoritative write layer. SQLite is a read cache rebuilt on every compile. No dual-write. No runtime writes to SQLite.

---

## Why Now

The current query path (`query_master.py`) loads all YAML into memory and scans linearly. At 73 repos and 2921 facts, this works. At 500+ repos it won't. More importantly, the 152 graph edges in `master_graph.yaml` are generated and validated but no query path touches them. They represent cross-repo relationships (alternative_to, extends, integrates_with) that are the most valuable thing in the corpus for agent use cases, and they're completely inaccessible.

Building new query features on top of the YAML scan approach creates rewrite debt — anything built there gets thrown away when the read model arrives. Building the read model first means every query improvement from here on is durable.

---

## Out of Scope

- DuckDB analytics engine. Deferred to Phase 4. No analytics-class queries exist yet. Decision to activate DuckDB is gated on workload evidence that emerges from Phase 3 usage.
- Schema or contract modifications to WS1. Canonical YAML format is unchanged.
- New repo intake. Phase 3 is infrastructure, not corpus expansion.
- Deep narrative generation workflow changes. The contract at `contracts/deep_narrative_contract.md` is stable.
- Shard model redesign.

---

## Architecture

```
Canonical Write Layer (unchanged)
┌─────────────────────────────────────────────────┐
│ master_index.yaml                               │
│ master_graph.yaml                               │
│ master_deep_facts.yaml                          │
│                                                 │
│ Written by: WS4 (compiler), WS6 (deep facts)   │
│ Governed by: contracts/ws1/*                    │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
              Materializer (new)
┌─────────────────────────────────────────────────┐
│ tools/ws7_read_model_compiler.py                │
│                                                 │
│ Reads canonical YAML → writes SQLite            │
│ Validates row-count parity + orphan edges       │
│ Atomic publish (temp → validate → rename)       │
│ Concise stdout, verbose logs to file            │
└──────────────────────┬──────────────────────────┘
                       │
                       ▼
             Read Layer (new)
┌─────────────────────────────────────────────────┐
│ knowledge.db (SQLite, gitignored)               │
│                                                 │
│ Tables: repos, nodes, edges, facts              │
│ Indexes on node_id, src_id, dst_id, predicate   │
│ Read by: query_master.py (migrated)             │
│ Never written to at runtime                     │
└─────────────────────────────────────────────────┘
```

---

## SQLite Schema

Four tables, mapping directly to the three canonical YAML files. Foreign key constraints are enforced (`PRAGMA foreign_keys=ON`) to catch referential integrity violations at insert time, not just in post-hoc validation.

### repos

From `master_index.yaml → repos[]`. One row per repo.

| Column | Type | Source |
|--------|------|--------|
| node_id | TEXT PK | `repo.node_id` |
| name | TEXT | `repo.name` |
| github_full_name | TEXT | `repo.github_full_name` |
| html_url | TEXT | `repo.html_url` |
| category | TEXT | `repo.category` |
| shard | TEXT | `repo.provenance.shard` |
| summary | TEXT | `repo.summary` |
| source | TEXT | `repo.source` |
| raw_yaml | TEXT | Full repo dict as JSON (preserves all fields) |

Indexes: `name`, `github_full_name`, `category`, `shard`.

### nodes

From `master_graph.yaml → nodes[]`. One row per graph node (repos + external tools/concepts).

| Column | Type | Source |
|--------|------|--------|
| node_id | TEXT PK | `node.node_id` |
| kind | TEXT | `node.kind` |
| label | TEXT | `node.label` |

Index: `kind`.

### edges

From `master_graph.yaml → edges[]`. One row per relationship.

| Column | Type | Source |
|--------|------|--------|
| id | INTEGER PK | Auto-increment |
| src_id | TEXT FK → nodes.node_id | `edge.src_id` |
| dst_id | TEXT FK → nodes.node_id | `edge.dst_id` |
| dst_kind | TEXT | `edge.dst_kind` |
| relation | TEXT | `edge.relation` |
| note | TEXT | `edge.note` |
| as_of | TEXT | `edge.as_of` |

Indexes: `src_id`, `dst_id`, `relation`, compound `(src_id, relation)`, compound `(dst_id, relation)`.

### facts

From `master_deep_facts.yaml → facts[]`. One row per deep fact.

| Column | Type | Source |
|--------|------|--------|
| fact_id | TEXT PK | `fact.fact_id` |
| node_id | TEXT FK → repos.node_id | `fact.node_id` |
| fact_type | TEXT | `fact.fact_type` |
| predicate | TEXT | `fact.predicate` |
| object_kind | TEXT | `fact.object_kind` |
| object_value | TEXT | `fact.object_value` |
| confidence | REAL | `fact.confidence` |
| note | TEXT | `fact.note` |
| as_of | TEXT | `fact.as_of` |
| source_file | TEXT | `fact.provenance.source_file` |
| source_section | TEXT | `fact.provenance.source_section` |
| raw_yaml | TEXT | Full fact dict as JSON (preserves all fields) |

Indexes: `node_id`, `predicate`, `fact_type`, `object_kind`, compound `(node_id, predicate)`.

### compile_metadata

Single-row table tracking materialization provenance.

| Column | Type | Content |
|--------|------|---------|
| schema_version | TEXT | e.g. "1.0.0" |
| compiled_at_utc | TEXT | ISO timestamp |
| source_index_hash | TEXT | SHA256 of master_index.yaml |
| source_graph_hash | TEXT | SHA256 of master_graph.yaml |
| source_facts_hash | TEXT | SHA256 of master_deep_facts.yaml |
| source_index_generated_at | TEXT | `generated_at_utc` from master_index.yaml |
| source_graph_generated_at | TEXT | `generated_at_utc` from master_graph.yaml |
| source_facts_generated_at | TEXT | `generated_at_utc` from master_deep_facts.yaml |
| repo_count | INTEGER | Parity check value |
| node_count | INTEGER | Parity check value |
| edge_count | INTEGER | Parity check value |
| fact_count | INTEGER | Parity check value |

---

## Materializer Tool

New tool: `tools/ws7_read_model_compiler.py`

### Compile Steps

1. Read canonical YAML files (`master_index.yaml`, `master_graph.yaml`, `master_deep_facts.yaml`).
2. Snapshot consistency gate: compare `generated_at_utc` across all three files. If timestamps diverge by more than 5 minutes, fail compile (no publish). On this failure, surface all three source hashes and generated timestamps in stdout and in `reports/ws7_read_model/compile_log.yaml` for fast diagnosis. Record all three timestamps in `compile_metadata` on successful compile.
3. Create SQLite database in a temporary file.
4. Create tables and indexes per schema above, with foreign key constraints enabled (`PRAGMA foreign_keys=ON`).
5. Insert all rows.
6. Run validation gates (see below).
7. If all gates pass, atomically rename temp file to `knowledge.db`.
8. If any gate fails, delete temp file and exit non-zero.

### Validation Gates

| Gate | Check |
|------|-------|
| Row-count parity | `repos` row count == YAML repos count. Same for nodes, edges, facts. |
| Orphan edge detection | Every `edges.src_id` and `edges.dst_id` exists in `nodes.node_id`. |
| Representative query parity | Run `stats`, one `repo`, one `neighbors`, one `facts` query and compare output to current YAML-based query_master.py results. |
| Deterministic rebuild | Compile twice from same inputs, compare logical fingerprints (sorted row-hashes per table, excluding compile_metadata timestamps). File-level byte comparison is not reliable — SQLite page allocation can differ between identical logical states. |

### Stdout Contract

Normal output is concise and token-lean:

```
compile: ok
  schema_version: 1.0.0
  repos: 73
  nodes: 87
  edges: 152
  facts: 2921
  duration_ms: 340
  output: knowledge.db
```

On failure:

```
compile: FAILED
  gate: orphan_edge_detection
  detail: edge src_id 'repo::missing/repo' has no matching node
```

For `snapshot_consistency` failures, the failure detail includes:
- `source_index_hash`, `source_index_generated_at`
- `source_graph_hash`, `source_graph_generated_at`
- `source_facts_hash`, `source_facts_generated_at`

Verbose diagnostics (row-level logs, full gate output) go to `reports/ws7_read_model/compile_log.yaml`. LLM agents only read the log on failure or explicit debug.

### Integration with Existing Pipeline

The materializer runs after WS4 and WS6 in the pipeline:

```
WS5 → WS4 → WS6 → WS7 (read model compile)
```

It becomes a non-negotiable gate for Phase 3 onwards. The `knowledge.db` file is gitignored — it's a derived artifact, not a source-of-truth.

WS7 is operationally mandatory as soon as M1 ships (execution behavior). M4 formalizes this requirement in project docs/status artifacts.

---

## query_master.py Migration

The existing `query_master.py` has 5 commands: `contract`, `stats`, `repo`, `neighbors`, `facts`. All 5 need to read from SQLite instead of loading YAML.

### Migration Approach

Replace `load_master_artifacts()` with a SQLite connection. Each command becomes a SQL query:

| Command | Current (YAML) | Migrated (SQLite) |
|---------|----------------|-------------------|
| `stats` | Count list lengths | `SELECT COUNT(*) FROM repos` etc. |
| `repo --id X` | Dict lookup by node_id/name/full_name | `SELECT * FROM repos WHERE node_id=? OR name=? OR github_full_name=?` |
| `neighbors --id X` | Linear scan of edges list | `SELECT * FROM edges WHERE src_id=? OR dst_id=?` with direction/relation filters |
| `facts --id X` | Linear scan of facts list | `SELECT * FROM facts WHERE node_id=?` with optional predicate filter |
| `contract` | Static dict | No change (no DB needed) |

### Backward Compatibility

Add a `--source` flag: `--source sqlite` (default after migration) and `--source yaml` (legacy, for comparison/debugging). This lets us run both paths side-by-side during validation. The YAML path is retired after M3 is complete and all M2 parity tests have been green for the duration of Phase 3.

### Stale-Read Protection

When `query_master.py` opens `knowledge.db`, it reads the `source_*_hash` values from `compile_metadata` and compares them to the current canonical YAML file hashes. If any hash doesn't match, the tool exits with a clear error:

```
ERROR: knowledge.db is stale — master_deep_facts.yaml has changed since last compile.
Run: python3 tools/ws7_read_model_compiler.py --workspace-root .
```

This prevents silently querying outdated data after a WS4 or WS6 run that wasn't followed by WS7.

### New Query Capabilities Unlocked

Once on SQLite, these queries become trivial to add:

- **Cross-repo pattern search:** `SELECT DISTINCT node_id, object_value FROM facts WHERE predicate='implements_pattern' AND object_value LIKE '%Factory%'` — "which repos use the Factory pattern?"
- **Graph traversal:** `SELECT e.dst_id, e.relation, r.category FROM edges e JOIN repos r ON e.dst_id = r.node_id WHERE e.src_id=?` — "what does repo X relate to, and what categories are those repos?"
- **Aggregate stats:** `SELECT predicate, COUNT(*) FROM facts GROUP BY predicate ORDER BY COUNT(*) DESC` — "what kinds of facts do we have the most of?"
- **Category exploration:** `SELECT node_id, name FROM repos WHERE category=?` — "show me all backup tools."
- **Multi-hop traversal:** Two-join edge walks for "repos similar to repos similar to X."

These are Phase 3 M3 deliverables, not M1. But they become straightforward once the foundation is in place.

---

## Milestones

### M1: Foundation — Materializer Tool

Build `tools/ws7_read_model_compiler.py`. It reads canonical YAML, produces `knowledge.db`, validates parity, publishes atomically.

**Done-when:**
- Tool exists and runs from repo root: `python3 tools/ws7_read_model_compiler.py --workspace-root .`
- All four validation gates pass.
- `knowledge.db` is produced and gitignored.
- Compile stdout follows the token-lean contract.
- Verbose log written to `reports/ws7_read_model/compile_log.yaml`.
- WS7 compile is required in runtime execution flow immediately after M1 delivery.

**Not in M1:** query_master.py changes, new query types.

### M2: Query Migration

Migrate `query_master.py` to read from SQLite. Add `--source` flag for backward compatibility. Validate output parity between YAML and SQLite paths.

**Done-when:**
- All 5 commands produce identical output from both `--source yaml` and `--source sqlite`.
- Default source is `sqlite`.
- `query_master.py stats` works off `knowledge.db` without loading YAML files.
- Existing test suite passes with SQLite path.
- Performance is measurably faster (should be obvious at any corpus size, but worth recording).
- Add explicit per-command query duration capture/logging so "measurably faster" is evidenced, not inferred.

**Not in M2:** New query commands, graph traversal expansion.

### M3: Query Expansion

Add new query capabilities that are only possible (or practical) with the SQL backend.

**Candidate commands (scope TBD based on M2 experience):**
- `search` — full-text search across fact object_values and notes.
- `pattern` — cross-repo pattern matching ("which repos implement X?").
- `graph` — multi-hop graph traversal ("repos connected to X within N hops").
- `aggregate` — corpus-level statistics by predicate, category, fact_type.

**Done-when:**
- At least 3 new query commands are implemented and tested.
- Graph edges are queryable through at least one command.
- Test coverage for new commands.

### M4: Documentation + Gate Formalization

Formalize in project artifacts what is already operational since M1: WS7 compile is a non-negotiable gate in the pipeline. Update AGENTS.md, project_status.yaml, and phase tracker. The read model compile remains part of the standard WS5 → WS4 → WS6 → WS7 flow.

**Done-when:**
- WS7 compile is listed in non-negotiable gates for future phases.
- AGENTS.md Status Routing section references the read model.
- `project_status.yaml` documents WS7 as a complete workstream.
- Future intake kickoffs include the WS7 compile step.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| SQLite file grows large at scale | Low (YAML is ~4MB at 73 repos; SQLite will be smaller) | Low | Monitor file size. SQLite handles hundreds of MB without issues. |
| Stale knowledge.db after pipeline run without WS7 | Medium (easy to forget WS7 step) | High (silently wrong query results) | Startup hash check in query_master.py fails fast with "recompile required" message. |
| Parity gate false positives | Medium (edge cases in YAML parsing vs SQL types) | Medium | The `--source yaml` fallback lets us compare. Fix parity issues before removing YAML path. |
| Executor builds SQLite-specific query ergonomics that don't survive schema changes | Low | Medium | Schema is versioned in `compile_metadata`. Schema changes require materializer update first. |
| Token cost of debugging compile failures | Low | Low | Verbose logs go to file, not stdout. LLM only reads logs on failure. |

---

## DuckDB Decision Gate

DuckDB is not in Phase 3 scope. The trigger to revisit is:

1. A recurring analytics question emerges that requires corpus-scale scans (e.g., "distribution of fact types across all repos," "which categories have the least deep coverage").
2. That question can't be answered efficiently with a single SQLite query.
3. The question is asked frequently enough to justify a second engine.

Until all three conditions are met, SQLite serves both interactive and light-analytics workloads. Record analytics-shaped queries that hit SQLite performance limits — that's the workload evidence for Phase 4.

---

## Exit Criteria for Phase 3

Phase 3 is complete when:

1. `knowledge.db` is produced by a deterministic, gate-validated materializer.
2. `query_master.py` reads from SQLite by default.
3. Graph edges are queryable (at least: "what repos relate to X?").
4. At least one cross-repo or aggregate query capability exists.
5. WS7 compile is a documented pipeline stage.
6. YAML-path backward compatibility is preserved for debugging.
7. No rewrite debt — everything built in Phase 3 survives to Phase 4+.

---

## Files This Plan Will Produce

| File | Purpose |
|------|---------|
| `tools/ws7_read_model_compiler.py` | Materializer tool |
| `knowledge.db` | SQLite read model (gitignored) |
| `.gitignore` update | Add `knowledge.db` |
| `reports/ws7_read_model/compile_log.yaml` | Verbose compile diagnostics |
| `query_master.py` (modified) | SQLite read path + `--source` flag |
| `tests/ws7_read_model/test_*.py` | Materializer and parity tests |
| `AGENTS.md` (updated) | WS7 reference in Status Routing |
| `project_status.yaml` (updated) | WS7 workstream documentation |
| `phase_3_progress_tracker.yaml` | New execution tracker for Phase 3 |
