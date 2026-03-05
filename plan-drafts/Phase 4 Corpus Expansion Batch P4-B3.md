TASK: Phase 4 Corpus Expansion Batch P4-B3 (Hybrid repeatability run)

PROMPT_AUDIT_HEADER:
  template_version: "p4-prompt-audit-v2"
  prompt_id: "P4-B3"
  run_class: "hybrid_repeatability_validation"
  primary_intent: "Run one controlled hybrid batch that drains queue and proves deep-lane yield under hardened WS6/WS7 policy."
  hard_gates:
    - "Queue sync PASS at preflight and post-run."
    - "All WS1/trust/validate/WS6/WS7 blocking gates PASS."
    - "WS7 strict-first is mandatory; --force allowed only for snapshot/timestamp-only failure."
    - "If deep lane is included, batch deep_facts delta must be > 0."
    - "Executor report acceptance is judged against plan-drafts/Phase 4 Executor Report Review Rubric.md."
    - "Commit scope must follow whitelist-only rule (no unrelated docs/hygiene edits bundled)."
  known_failure_modes:
    - "Strict WS7 skipped and --force used prematurely."
    - "Deep files created but deep_facts delta remains flat (gate failure)."
    - "Mixed-intent commit scope contaminates execution evidence."
    - "Queue drift between preflight snapshot and execution target list."
  report_tags:
    - "phase4"
    - "batch"
    - "hybrid"
    - "ws7-strict-first"
    - "hard-deep-gate"

MODE: EXECUTION (no exploratory detours)

WORKSPACE:
- Repo root: /Users/szilaa/scripts/ext_sources/github_repos
- Branch: codex/phase-2b-sb2

OBJECTIVE:
- Execute one hybrid batch with two lanes in a single run:
  - shallow lane: 8 queued repos via WS5 -> WS4 -> WS6 -> WS7
  - deep lane: 4 already-canonical repos via deep narratives -> WS6 -> WS7
- Confirm hardened policy repeatability with strict-first WS7 behavior.
- Capture acceptance evidence in rubric-compatible format.

POLICY ENFORCEMENT (non-negotiable):
1) WS7 strict-first policy:
   - Run `python3 tools/ws7_read_model_compiler.py --workspace-root .` first.
   - Use `--force` only when strict failure is snapshot/timestamp consistency only.
   - If any blocking gate fails (`row_count_parity`, `orphan_edge_detection`, `query_parity`, `deterministic_rebuild`), stop and escalate.
2) Deep hard gate:
   - Because this is hybrid (deep lane included), `query_master stats.deep_facts` delta must be `> 0`.
3) Commit-scope whitelist rule:
   - Allowed changed paths are only:
     - `inputs/ws5/ws5_input_manifest.yaml`
     - `inputs/intake/intake_queue.yaml`
     - `llm_repos/knowledge/repos/*.yaml`
     - `llm_repos/knowledge/deep/*.yaml`
     - `llm_repos/knowledge/deep_facts/*.yaml`
     - `llm_repos/knowledge/index.yaml`
     - `llm_repos/knowledge/trust-gates-report.yaml`
     - `ssh_repos/knowledge/repos/*.yaml`
     - `ssh_repos/knowledge/deep/*.yaml`
     - `ssh_repos/knowledge/deep_facts/*.yaml`
     - `ssh_repos/knowledge/index.yaml`
     - `ssh_repos/knowledge/trust-gates-report.yaml`
     - `master_index.yaml`
     - `master_graph.yaml`
     - `master_deep_facts.yaml`
     - `reports/ws5_remote_ingestion/*.yaml`
     - `reports/ws4_master_build/*.yaml`
     - `reports/ws6_deep_integration/*.yaml`
     - `reports/ws7_read_model/*.yaml`
   - Explicitly disallowed in execution commit:
     - `project_status.yaml`
     - `phase_4_progress_tracker.yaml`
     - any `plan-drafts/*.md`
     - any unrelated workspace files

SHALLOW LANE TARGETING:
- Use exactly 8 repos selected at preflight from currently queued entries in `inputs/intake/intake_queue.yaml`.
- Lock selected 8 in the report before running WS5.
- Require explicit `target_shard` on every manifest row.
- Current queued candidate pool (snapshot):
  1) avelino/awesome-go
  2) butlerx/wetty
  3) code-yeongyu/oh-my-opencode
  4) frankbria/ralph-claude-code
  5) haifengl/smile
  6) henryboldi/felony
  7) iluwatar/java-design-patterns
  8) infiniflow/infinity
  9) kaitranntt/ccs
  10) katarmal-ram/codemoot
  11) MariaDB/server
  12) michaelshimeles/ralphy

DEEP LANE TARGETS (already canonical, missing deep + deep_facts):
1) openai/codex (agent_cli)
2) anthropics/claude-code (agent_cli)
3) ansible/ansible (agent_orchestration)
4) gin-gonic/gin (web_framework)

DEEP CONTRACT:
- Follow `contracts/deep_narrative_contract.md` exactly.
- Deep file location: `{shard}/knowledge/deep/<file_stem>.yaml`.
- Copy identity fields exactly from `{shard}/knowledge/repos/<file_stem>.yaml`:
  - `node_id`, `github_full_name`, `html_url`, `source`, `name`
- Use WS6-recognized section names only.

PRE-FLIGHT (must pass):
1) `git status -sb`
2) `git log --oneline --decorate -n 8`
3) `python3 tools/check_intake_queue_sync.py --workspace-root .`
4) `python3 tools/query_master.py stats`
5) `python3 tools/query_master.py aggregate --group-by predicate --top 15`
6) `python3 tools/query_master.py aggregate --group-by category --top 15`
7) Record freshness baselines:
   - `master_index.generated_at_utc`
   - `master_graph.generated_at_utc`
   - `master_deep_facts.generated_at_utc`
8) Record SHA1 hashes (for drift audit):
   - `phase_4_progress_tracker.yaml`
   - `plan-drafts/Phase 4 Corpus Expansion Batch P4-B2.md`
   - `plan-drafts/Phase 4 Corpus Expansion Batch P4-B2-Deep.md`

IMPLEMENTATION ORDER:
1) Prepare shallow manifest rows (8 repos, explicit shard/category/source fields).
2) Author 4 deep narrative files for deep targets.
3) Run pipeline in canonical order:
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
4) Apply WS7 fallback policy only if strict fails on snapshot/timestamp consistency:
   - `python3 tools/ws7_read_model_compiler.py --workspace-root . --force`
5) Queue refresh + verification:
   - `python3 tools/check_intake_queue_sync.py --workspace-root . --fix`
   - `python3 tools/check_intake_queue_sync.py --workspace-root .`
6) Post-run checks:
   - `python3 tools/query_master.py stats`
   - `python3 tools/query_master.py aggregate --group-by predicate --top 15`
   - `python3 tools/query_master.py aggregate --group-by category --top 15`

HARD ACCEPTANCE CRITERIA:
- Queue sync PASS pre and post.
- All blocking gates PASS.
- WS7 strict-first observed; fallback (if used) is snapshot-only justified.
- Deep lane files exist for all 4 targets in both `deep/` and `deep_facts/`.
- Each target deep_facts file has at least 1 fact.
- Batch-level `query_master stats.deep_facts` delta is `> 0`.
- Execution evidence is complete and satisfies rubric at:
  - `/Users/szilaa/scripts/ext_sources/github_repos/plan-drafts/Phase 4 Executor Report Review Rubric.md`

FINAL REPORT FORMAT (required):
1) Baseline vs final counts:
   - queue: `queued_count`, `already_canonical_count`
   - query stats: `repos`, `nodes`, `edges`, `deep_facts`
2) Freshness disclosure:
   - `master_index.generated_at_utc` (before -> after)
   - `master_graph.generated_at_utc` (before -> after)
   - `master_deep_facts.generated_at_utc` (before -> after)
   - WS7 snapshot status (`pass` or `warn`) + fallback usage
3) Evidence hash block:
   - SHA1 for `phase_4_progress_tracker.yaml`
   - SHA1 for active batch prompt file
   - SHA1 for prior prompt file(s) used as reference
   - Explicit statement whether hashes stayed stable during run
4) Deep lane table (per target):
   - `github_full_name`, deep file path, deep_facts file path, deep_facts count, status
5) Shallow lane table (per target):
   - `github_full_name`, manifest updated (yes/no), canonical repo file path, `query_master repo` result
6) Gate summary table (command + pass/fail)
7) Files changed (paths only; must satisfy whitelist)
8) Blockers/fallbacks with exact reason

BLOCKER PROTOCOL:
- Stop immediately if any hard gate fails.
- Report expected vs found, 2-3 options with tradeoffs, and recommended option.
- Do not proceed past blocker without user confirmation.
