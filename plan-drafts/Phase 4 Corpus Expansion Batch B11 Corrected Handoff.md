TASK: Phase 4 Corpus Expansion Batch B11 Corrected Handoff

PROMPT_AUDIT_HEADER:
  template_version: "b11-corrected-handoff-v1"
  template_owner: "codex"
  template_change_control:
    parent_template_version: "supervisor-b11-draft"
    last_changed_utc: "2026-03-18T00:00:00Z"
    last_changed_by: "codex"
    change_reason: "Corrected clone-prep interface, WS5 manifest shape, deep-header sequencing, and control-plane file scope."

MODE: EXECUTION

WORKSPACE:
- Repo root: /Users/szilaa/scripts/ext_sources/github_repos
- Branch: main
- Commit: 7e63e55ffec7

OBJECTIVE:
- Execute batch `B11_gitnexus_ladybugdb_deepagents` for three repos:
  - `abhigyanpatwari/GitNexus`
  - `LadybugDB/ladybug`
  - `langchain-ai/deepagents`
- Use the real pipeline order and tool interfaces in this repo.
- Stop on any duplicate/overwrite ambiguity, queue sync failure, clone-prep failure, WS6 blocking failure, or zero deep-facts growth.

CONSTRAINTS:
- Read before writing.
- Do not invent category labels, file stems, paths, function names, or config keys.
- Do not touch `inputs/ws5/ws5_input_manifest.yaml`.
- Do not overwrite an existing canonical shallow file without explicit supervisor approval.
- Use a batch-local WS5 manifest.
- Keep execution artifacts and control-plane updates in separate commits.
- Quote YAML string values containing any of: `` ` ``, `@`, `[`, `]`, `{`, `}`, `:`, `#`.

REQUIRED READING:
1. `AGENTS.md`
2. `docs/INGESTION_WORKFLOW.md`
3. `contracts/deep_narrative_contract.md`
4. `repos/knowledge/deep/bore.yaml`
5. `repos/knowledge/deep/anything_llm.yaml`

Then run:

```bash
python3 tools/query_master.py --workspace-root . aggregate --group-by category
```

Use the live output as the category vocabulary. Do not rely on guessed labels.

BATCH ID:
- `B11_gitnexus_ladybugdb_deepagents`

MANIFEST PATH:
- `inputs/ws5/B11_gitnexus_ladybugdb_deepagents_manifest.yaml`

TARGET DEEP FILES:
- `repos/knowledge/deep/abhigyanpatwari__gitnexus.yaml`
- `repos/knowledge/deep/ladybugdb__ladybug.yaml`
- `repos/knowledge/deep/langchain-ai__deepagents.yaml`

STEP 0 — PREFLIGHT DUPLICATE AND OVERWRITE CHECKS:

Run:

```bash
python3 tools/check_intake_queue_sync.py --workspace-root .
```

Check whether any target already exists in:
- `master_repo_list.yaml`
- `inputs/ws5/ws5_input_manifest.yaml`
- canonical shallow files under `repos/knowledge/repos/`
- canonical master artifacts

Commands:

```bash
grep -i "gitnexus\\|GitNexus" master_repo_list.yaml
grep -i "ladybug" master_repo_list.yaml
grep -i "deepagents" master_repo_list.yaml

grep -i "gitnexus\\|GitNexus" inputs/ws5/ws5_input_manifest.yaml
grep -i "ladybug" inputs/ws5/ws5_input_manifest.yaml
grep -i "deepagents" inputs/ws5/ws5_input_manifest.yaml

rg -n "(GitNexus|abhigyanpatwari/GitNexus|LadybugDB/ladybug|langchain-ai/deepagents|gitnexus|ladybug|deepagents)" repos/knowledge/repos master_index.yaml
```

Decision rules:
- If a repo is already in `master_repo_list.yaml` only: do not re-register it.
- If a repo already has a canonical shallow file in `repos/knowledge/repos/`: stop and report.
- If any target appears in an existing manifest or canonical artifact in a way that creates overwrite ambiguity: stop and report.

STEP 1 — REGISTER MISSING CANDIDATES:

For any repo missing from `master_repo_list.yaml`, register it with a category chosen from the live aggregate output.

Commands:

```bash
python3 tools/add_repo_candidate.py --workspace-root . --github-url https://github.com/abhigyanpatwari/GitNexus --category <chosen_category>
python3 tools/add_repo_candidate.py --workspace-root . --github-url https://github.com/LadybugDB/ladybug --category <chosen_category>
python3 tools/add_repo_candidate.py --workspace-root . --github-url https://github.com/langchain-ai/deepagents --category <chosen_category>
```

After registration, re-run:

```bash
python3 tools/check_intake_queue_sync.py --workspace-root .
```

This must pass before continuing.

STEP 2 — WRITE THE BATCH MANIFEST IN THE CORRECT WS5 SHAPE:

Create `inputs/ws5/B11_gitnexus_ladybugdb_deepagents_manifest.yaml` as a WS5 manifest mapping, not a bare list.

Required shape:

```yaml
artifact_type: ws5_remote_ingestion_input_manifest
contract_version: 1.0.0-ws1
defaults:
  target_shard: repos
  as_of: "2026-03-18"
  source: remote_metadata
repos:
  - name: ...
    github_full_name: ...
    html_url: ...
    target_shard: repos
    source: remote_metadata
    category: ...
    summary: ...
    core_concepts:
      - ...
    key_entry_points:
      - ...
    build_run:
      language: ...
      build: See upstream README for project build steps.
      test: See upstream README for project test steps.
    as_of: "2026-03-18"
    local_cache_dir: null
```

Content guidance:

1. GitNexus
- `name: gitnexus`
- `github_full_name: abhigyanpatwari/GitNexus`
- `html_url: https://github.com/abhigyanpatwari/GitNexus`
- Summary: zero-server code intelligence engine using Tree-sitter parsing and LadybugDB, exposed through MCP tools and a browser UI
- `key_entry_points`: `README.md`, `gitnexus/src/`, `gitnexus-web/src/`
- `language: TypeScript`

2. LadybugDB
- `name: ladybug`
- `github_full_name: LadybugDB/ladybug`
- `html_url: https://github.com/LadybugDB/ladybug`
- Summary: embedded columnar graph database with a property graph model and Cypher query language, forked from Kuzu
- `key_entry_points`: `README.md`, `src/`
- `language: C++`

3. deepagents
- `name: deepagents`
- `github_full_name: langchain-ai/deepagents`
- `html_url: https://github.com/langchain-ai/deepagents`
- Summary: LangChain/LangGraph agent harness with planning, filesystem access, sub-agent spawning, context summarization, plus a terminal CLI
- `key_entry_points`: `README.md`, `libs/deepagents/deepagents/`, `libs/cli/deepagents_cli/`
- `language: Python`

After writing the manifest, run:

```bash
python3 tools/check_intake_queue_sync.py --workspace-root .
```

If this fails, stop and report.

STEP 3 — CHECK CLONE SIZE USING THE ACTUAL MANIFEST:

Do not use `ws6_clone_prep.py --github-url`; that interface does not exist here.

Run:

```bash
python3 tools/ws6_clone_prep.py \
  --workspace-root . \
  --manifest inputs/ws5/B11_gitnexus_ladybugdb_deepagents_manifest.yaml \
  --clone-workdir workspace/clones \
  --size-limit-mb 500 \
  --batch-id B11_gitnexus_ladybugdb_deepagents
```

If clone prep halts on repo size, re-run:

```bash
python3 tools/ws6_clone_prep.py \
  --workspace-root . \
  --manifest inputs/ws5/B11_gitnexus_ladybugdb_deepagents_manifest.yaml \
  --clone-workdir workspace/clones \
  --size-limit-mb 2000 \
  --batch-id B11_gitnexus_ladybugdb_deepagents \
  --force-large
```

Decision rules:
- If LadybugDB still fails clone prep even with `--force-large --size-limit-mb 2000`, stop and report.
- If the large-repo path was required, later set `clone_size_limit_mb: 2000` in `batch_spec.yaml`.

STEP 4 — MATERIALIZE SHALLOW FILES BEFORE AUTHORING DEEP FILES:

You need the exact shallow headers before writing deep files.

Run:

```bash
python3 tools/ws5_remote_ingestion.py \
  --workspace-root . \
  --input inputs/ws5/B11_gitnexus_ladybugdb_deepagents_manifest.yaml

python3 tools/ws4_master_compiler.py \
  --workspace-root .
```

Then read:

```bash
cat repos/knowledge/repos/abhigyanpatwari__gitnexus.yaml
cat repos/knowledge/repos/ladybugdb__ladybug.yaml
cat repos/knowledge/repos/langchain-ai__deepagents.yaml
```

For each deep file, copy exactly:
- `name`
- `node_id`
- `github_full_name`
- `html_url`
- `source`
- `directory`
- `category`

Also set:
- `provenance.shard: repos`
- `provenance.source_file` to the deep file path
- `provenance.as_of: "2026-03-18"`
- `provenance.sourcing_method: code_verified`
- `provenance.extraction_agent: codex`

Only add `extraction_model` if known with confidence.

STEP 5 — USE THE CLONE MANIFEST TO LOCATE SOURCE:

Read:

```bash
cat reports/ws6_clone_prep/B11_gitnexus_ladybugdb_deepagents_clones.yaml
```

Use the local clone paths from that report. Do not guess clone directories.

Every deep-file claim must be grounded in actual source from those clones.

STEP 6 — WRITE THE DEEP YAML FILES:

Use only recognized contract section names. Highest-value sections for this batch:
- `architecture`
- `core_modules`
- `api_surface`
- `configuration`
- `implementation_patterns`
- `key_features`
- `key_files`

GitNexus:
- File: `repos/knowledge/deep/abhigyanpatwari__gitnexus.yaml`
- Target: 150–200 lines
- Focus: dual-mode architecture, indexing pipeline, LadybugDB-backed graph storage, MCP server layer, resource/tool surface, CLI commands
- Verify exact MCP tool names and CLI commands from source before writing

LadybugDB:
- File: `repos/knowledge/deep/ladybugdb__ladybug.yaml`
- Target: 100–150 lines
- Be conservative
- Focus: embedded/in-process architecture, storage/query model, durability model only if verified, CLI and bindings, configuration modes, interop claims only if supported by source

deepagents:
- File: `repos/knowledge/deep/langchain-ai__deepagents.yaml`
- Target: 150–200 lines
- Focus: monorepo structure, `create_deep_agent()` path, middleware composition, backend abstraction, CLI app, configuration model, implementation patterns only if verified in code

STEP 7 — CREATE BATCH SPEC:

Create `batch_spec.yaml` at repo root.

Standard case:

```yaml
batch_id: B11_gitnexus_ladybugdb_deepagents
manifest: inputs/ws5/B11_gitnexus_ladybugdb_deepagents_manifest.yaml
clone_workdir: workspace/clones
clone_size_limit_mb: 500
clone_cleanup: false
gates:
  ws6_fail_on_any_false: true
  ws7_fail_on_any_non_pass: false
dry_run: false
```

If LadybugDB required the large-repo path, use:
- `clone_size_limit_mb: 2000`

Do not change thresholds mid-run after this point.

STEP 8 — RUN THE BATCH:

Dry run:

```bash
python3 tools/run_batch.py --spec batch_spec.yaml --workspace-root . --dry-run
```

Live run:

```bash
python3 tools/run_batch.py --spec batch_spec.yaml --workspace-root .
```

STEP 9 — VERIFY:

Read:

```bash
cat reports/run_batch/B11_gitnexus_ladybugdb_deepagents_verdict.yaml
```

Required outcome:
- `result: ok`
- every `ws6_gate_bools` value is `true`
- `snapshot_consistency: warn` is acceptable and non-blocking
- no other WS7 failure

Then verify deep facts increased beyond the pre-run baseline of 5329:

```bash
python3 tools/query_master.py --workspace-root . stats
```

If `deep_facts` did not increase, stop and report.

STEP 10 — COMMIT IN TWO CLEAN COMMITS:

Commit 1: execution artifacts only
- `repos/knowledge/repos/abhigyanpatwari__gitnexus.yaml`
- `repos/knowledge/repos/ladybugdb__ladybug.yaml`
- `repos/knowledge/repos/langchain-ai__deepagents.yaml`
- `repos/knowledge/deep/abhigyanpatwari__gitnexus.yaml`
- `repos/knowledge/deep/ladybugdb__ladybug.yaml`
- `repos/knowledge/deep/langchain-ai__deepagents.yaml`
- `repos/knowledge/deep_facts/abhigyanpatwari__gitnexus.yaml`
- `repos/knowledge/deep_facts/ladybugdb__ladybug.yaml`
- `repos/knowledge/deep_facts/langchain-ai__deepagents.yaml`
- `master_index.yaml` if changed
- `master_graph.yaml` if changed
- `master_deep_facts.yaml` if changed

Message:

```bash
git commit -m "feat(B11): ingest gitnexus + ladybugdb + deepagents [3 repos]"
```

Commit 2: control-plane only
- `project_status.yaml`
- `phase_4_progress_tracker.yaml`
- `inputs/ws5/B11_gitnexus_ladybugdb_deepagents_manifest.yaml`
- `master_repo_list.yaml` if registration occurred
- `inputs/intake/intake_queue.yaml` if registration occurred

Message:

```bash
git commit -m "chore(B11): update project status and tracker"
```

Do not mix execution artifacts and control-plane updates.

BLOCKING STOPS:
- `check_intake_queue_sync.py --workspace-root .` fails after registration or after manifest writing
- any target repo already has a canonical shallow file in `repos/knowledge/repos/`
- manifest parsing or WS5 input shape fails
- LadybugDB clone prep fails even with `--force-large --size-limit-mb 2000`
- any `ws6_gate_bools` value is `false`
- `deep_facts` does not increase above 5329 after a successful run
- generated shallow file stems differ from:
  - `abhigyanpatwari__gitnexus`
  - `ladybugdb__ladybug`
  - `langchain-ai__deepagents`

FINAL REPORT BACK TO SUPERVISOR:
1. Exact categories chosen for each repo
2. Whether LadybugDB required the large-repo path
3. Verdict summary from `reports/run_batch/B11_gitnexus_ladybugdb_deepagents_verdict.yaml`
4. Pre-run vs post-run `deep_facts`
5. The two commit SHAs
