TASK: Phase 4 Corpus Expansion Batch P4-B2 (12 queued repos)

PROMPT_AUDIT_HEADER:
  template_version: "p4-prompt-audit-v1"
  prompt_id: "P4-B2"
  run_class: "shallow_batch_policy_validation"
  primary_intent: "Validate stabilized WS6/WS7 operating policy while ingesting 12 queued repos."
  hard_gates:
    - "Queue sync PASS at preflight and post-run."
    - "All WS1/trust/validate/WS6/WS7 blocking gates PASS."
    - "WS7 strict-first run required; --force allowed only for snapshot/timestamp-only failure."
    - "All 12 repos resolve via query_master repo checks, including one mixed-case identifier."
  known_failure_modes:
    - "Manifest row missing explicit target_shard causes shard misrouting."
    - "Accidental commit scope contamination from unrelated dirty/untracked files."
    - "WS7 strict run failed by blocking integrity gate (non-snapshot)."
    - "Shallow-only success mistaken for deep success (edges/deep_facts unchanged)."
  report_tags:
    - "phase4"
    - "batch"
    - "policy-validation"
    - "ws7-strict-first"

MODE: EXECUTION (no exploratory detours)

WORKSPACE:
- Repo root: /Users/szilaa/scripts/ext_sources/github_repos
- Branch: codex/phase-2b-sb2

OBJECTIVE:
- Process this 12-repo batch end-to-end through WS5 -> WS4 -> WS1/trust -> WS6 -> WS7.
- Keep routing explicit (`target_shard` per repo) and avoid queue drift.
- Validate the stabilization policies under real batch load.

POLICY DELTAS TO ENFORCE (v2 hardening):
1) Routing policy: every manifest row must set explicit `target_shard`.
2) WS7 policy: strict WS7 first; `--force` is conditional fallback only.
3) Freshness policy: report before/after generated timestamps for index/graph/deep_facts.
4) Identifier policy: include mixed-case query check to confirm case-insensitive resolution holds.
5) Scope policy: do not commit/report unrelated dirty files.

STABILIZATION ASSUMPTIONS (already merged):
- `tools/query_master.py` resolves `name`/`github_full_name` case-insensitively in YAML + SQLite paths.
- `tools/ws6_deep_integrator.py --run-validation-suite` uses `query_master --source yaml stats`.
- `tools/ws7_read_model_compiler.py` treats snapshot timestamp divergence as warning/non-blocking; integrity gates remain blocking.

APPROVED BATCH + EXPLICIT ROUTING:
1) airtable/airtable.js | target_shard=llm_repos | category=workflow_builder
2) ansible/ansible | target_shard=llm_repos | category=agent_orchestration
3) coder/code-server | target_shard=llm_repos | category=remote_access
4) containers/podman | target_shard=llm_repos | category=cli_tool
5) dottxt-ai/outlines | target_shard=llm_repos | category=structured_outputs
6) pydantic/pydantic | target_shard=llm_repos | category=structured_outputs
7) pydantic/pydantic-core | target_shard=llm_repos | category=structured_outputs
8) pydantic/pydantic-settings | target_shard=llm_repos | category=structured_outputs
9) Krosebrook/archdesigner | target_shard=llm_repos | category=workflow_builder
10) brianpetro/obsidian-smart-connections | target_shard=llm_repos | category=workflow_builder
11) PaddlePaddle/PaddleOCR | target_shard=llm_repos | category=office_automation
12) Stirling-Tools/Stirling-PDF | target_shard=llm_repos | category=office_automation

CONSTRAINTS:
- Do not hand-edit `inputs/intake/intake_queue.yaml`.
- Use queue tooling only (`tools/check_intake_queue_sync.py`, `tools/add_repo_candidate.py`).
- Do not modify contracts or AGENTS.md.
- Keep edits scoped to ingestion/pipeline artifacts for this batch.
- Do not sweep unrelated local changes into this batch commit.

PRE-FLIGHT (must pass before implementation):
1) `python3 tools/check_intake_queue_sync.py --workspace-root .`
2) `python3 tools/query_master.py stats`
3) Verify all 12 repos are still `canonical_status=queued` in `inputs/intake/intake_queue.yaml`.
4) Record baseline freshness timestamps:
   - `master_index.yaml.generated_at_utc`
   - `master_graph.yaml.generated_at_utc`
   - `master_deep_facts.yaml.generated_at_utc`
5) If any approved repo is already canonical, stop and return:
   - skipped repo(s),
   - 3 queued replacements,
   - recommended replacement set.

IMPLEMENTATION:
1) Add/update rows for all 12 repos in `inputs/ws5/ws5_input_manifest.yaml`.
2) Set explicit `target_shard: llm_repos` on every row.
3) Ensure required WS5 fields exist per row:
   - `name`, `github_full_name`, `html_url`, `category`, `summary`, `core_concepts`, `key_entry_points`, `build_run`, `as_of`, `source`.
4) Use `source: remote_metadata` and `local_cache_dir: null`.
5) Run pipeline gates in this order:
   - `python3 tools/ws5_remote_ingestion.py --workspace-root . --input inputs/ws5/ws5_input_manifest.yaml --reports-dir reports/ws5_remote_ingestion`
   - `python3 tools/ws4_master_compiler.py --workspace-root . --master-index master_index.yaml --master-graph master_graph.yaml --reports-dir reports/ws4_master_build`
   - `python3 tools/ws1_contract_validator.py --workspace-root . --external-node-policy first_class`
   - `python3 tools/ws1_contract_validator.py --workspace-root . --external-node-policy label_only`
   - `python3 tools/trust_gates.py llm_repos/knowledge --production`
   - `python3 tools/trust_gates.py ssh_repos/knowledge --production`
   - `cd llm_repos/knowledge && python3 validate.py`
   - `cd ssh_repos/knowledge && python3 validate.py`
   - `cd /Users/szilaa/scripts/ext_sources/github_repos`
   - `python3 tools/ws6_deep_integrator.py --workspace-root . --reports-dir reports/ws6_deep_integration --materialize-spec reports/ws6_deep_integration/spec.yaml --run-validation-suite`
   - `python3 tools/ws7_read_model_compiler.py --workspace-root .`
6) WS7 fallback rule:
   - Do NOT run `--force` by default.
   - If strict WS7 exits non-zero, inspect gate failure reason.
   - Run `python3 tools/ws7_read_model_compiler.py --workspace-root . --force` only when strict failure is snapshot/timestamp consistency only.
   - If any blocking gate fails (`row_count_parity`, `orphan_edge_detection`, `query_parity`, `deterministic_rebuild`), stop and escalate.
7) Refresh queue state:
   - `python3 tools/check_intake_queue_sync.py --workspace-root . --fix`
   - `python3 tools/check_intake_queue_sync.py --workspace-root .`
8) Regression checks:
   - `python3 tools/query_master.py stats`
   - `python3 tools/query_master.py aggregate --group-by category`
   - For each of the 12 repos: `python3 tools/query_master.py repo --id <owner/repo>`
   - Mixed-case check on one repo from batch:
     - `python3 tools/query_master.py repo --id Stirling-Tools/Stirling-PDF`

ACCEPTANCE CRITERIA:
- Queue sync PASS at start and end.
- `queued_count` decreases by 12; `already_canonical_count` increases by 12.
- All listed gates pass.
- WS7 strict-first policy is followed; fallback usage (if any) is explicitly justified.
- `query_master repo` passes for all 12 repos.
- Mixed-case repo lookup passes.

FINAL REPORT FORMAT:
1) Baseline vs final counts:
   - `queued_count`, `already_canonical_count`, `query_master stats` (`repos`, `nodes`, `edges`, `deep_facts`).
2) Freshness disclosure:
   - `master_index.generated_at_utc` (before -> after)
   - `master_graph.generated_at_utc` (before -> after)
   - `master_deep_facts.generated_at_utc` (before -> after)
   - WS7 snapshot gate status (`pass` or `warn`) and whether fallback was used.
3) Files changed (paths only).
4) Per-repo outcome table:
   - `github_full_name`, manifest row added/updated (yes/no), canonical file path, `query_master repo` check (pass/fail).
5) Gate summary table (command + pass/fail).
6) Blockers/fallbacks with exact reason.

BLOCKER PROTOCOL:
- If blocked, stop immediately and report:
  - expected vs found,
  - 2-3 options with tradeoffs,
  - recommended option.
- Do not proceed past blocker without user confirmation.
