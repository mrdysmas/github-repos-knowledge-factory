TASK: Phase 4 Corpus Expansion Batch P4-B6 (Queue Drain + Deep Backfill)

PROMPT_AUDIT_HEADER:
  template_version: "p4-prompt-audit-v3"
  template_owner: "phase4-supervisor"
  template_change_control:
    parent_template_version: "p4-prompt-audit-v3"
    last_changed_utc: "2026-03-13T04:36:15Z"
    last_changed_by: "supervisor"
    change_reason: "Standardized template (approved). B6 drains final 8 queued repos and backfills 4 deep narratives."
    changelog_ref: "05142f2"

  run_identity:
    prompt_id: "P4-B6"
    run_class: "hybrid_queue_drain"
    primary_intent: "Drain the remaining 8 queued repos (shallow lane) and backfill 4 canonical repos missing deep narratives (deep lane). Final queue-drain batch before intake refill."

  immutable_context:
    workspace_root: "/Users/szilaa/scripts/ext_sources/github_repos"
    branch: "main"
    phase4_tracker_sha1: "f1f33d5a6ac080e089b36bd2bcf1022c44f82c24"
    rubric_sha1: "115f0adbe29786e5fd6a04898d5a51f7df23ad8d"
    prior_prompt_sha1:
      p4_b2: "c21d8cb4b3e28e814401011ff3e2dc8c69f52a6a"
      p4_b2_deep: "73c1a74775ce13d21510ea410f7a9120519d2269"
      p4_b3: "b73ad7c9a6279e1a02a907632dedb7a909ed74d3"
      p4_b4: "fa2f944f21c2c376a6fc4c08d580585d5430bfd7"
      p4_b5: "b6897b5c72eff82ee2c24dfd4bef76bcc35569d1"
    self_prompt_lock_ref: "reports/phase4/prompt_locks/P4-B6.lock.yaml"

  target_lock:
    shallow_target_count: 8
    deep_target_count: 4
    shallow_targets_sha1: "4ab1407dc7dc321cc4459838762f54b415f91ffa"
    deep_targets_sha1: "c8ef43f01df1d7ef86e2cd6d8ac0e9e6c4380ea1"
    lock_timestamp_utc: "2026-03-13T04:36:15Z"

  hard_gates:
    - "Queue sync PASS pre and post."
    - "All WS1/trust/validate/WS6/WS7 blocking gates PASS."
    - "WS7 strict-first mandatory; do not rely on --force for recovery (compatibility no-op)."
    - "Executor report accepted only if rubric evidence is complete."
    - "Commit scope must match whitelist-only rule."

  numeric_thresholds:
    queued_count_delta_expected: "-8"
    already_canonical_delta_expected: "+8"
    deep_facts_delta_min: 1
    deep_target_deep_files_required: "4"
    deep_target_fact_files_required: "4"
    deep_targets_with_facts_min: "4"
    per_target_fact_min: 1

  evidence_requirements:
    require_hash_stability_statement: true
    require_freshness_disclosure: true
    require_gate_table: true
    require_full_changed_files_list: true

  known_failure_modes:
    - "Prompt/hash drift mid-run."
    - "Strict WS7 skipped or --force assumed to recover a strict failure."
    - "Deep lane executed but deep_facts delta stays flat."
    - "Manifest/queue drift or shard misrouting."
    - "Undecided shard_hint repos routed to wrong shard."
    - "Mixed-intent commit contamination."

  acceptance_policy:
    reject_if_any_hard_gate_missing: true
    reject_if_numeric_thresholds_not_met: true
    reject_if_evidence_incomplete: true

MODE: EXECUTION (no exploratory detours)

WORKSPACE:
- Repo root: /Users/szilaa/scripts/ext_sources/github_repos
- Branch: main

OBJECTIVE:
- Execute one locked hybrid run with:
  - shallow lane: 8 queued repos (WS5 -> WS4 -> WS6 -> WS7) — this drains the queue to zero
  - deep lane: 4 already-canonical repos missing deep/deep_facts (deep authoring -> WS6 -> WS7)
- Preserve strict-first WS7 discipline.
- Produce executor evidence that is ACCEPT/ACCEPT WITH NOTES-ready against rubric.

LOCKED TARGETS (do not change without regenerating header hashes):

Shallow lane (8 queued — all remaining):
1) kaitranntt/ccs           -> target_shard: llm_repos, category: agent_cli
2) katarmal-ram/codemoot    -> target_shard: llm_repos, category: agent_cli
3) MariaDB/server           -> target_shard: ssh_repos, category: data_pipelines
4) michaelshimeles/ralphy   -> target_shard: llm_repos, category: agent_cli
5) mlpack/mlpack            -> target_shard: ssh_repos, category: machine_learning
6) mscdex/ssh2              -> target_shard: ssh_repos, category: network_utils
7) obra/superpowers         -> target_shard: llm_repos, category: agent_framework
8) obsidianmd/obsidian-releases -> target_shard: llm_repos, category: documentation

Shard routing notes:
- MariaDB/server, mlpack/mlpack, mscdex/ssh2: SSH/systems-oriented → ssh_repos
- kaitranntt/ccs, katarmal-ram/codemoot, michaelshimeles/ralphy: LLM agent tools → llm_repos
- obra/superpowers: Claude skills/agent framework → llm_repos
- obsidianmd/obsidian-releases: documentation/plugin index → llm_repos

Deep lane (4 canonical missing deep/deep_facts):
1) tailscale/tailscale         (shard: ssh_repos, category: vpn_mesh)
2) cloudflare/cloudflared      (shard: ssh_repos, category: network_infrastructure)
3) containers/podman           (shard: ssh_repos, category: cli_tool)
4) weaviate/weaviate           (shard: llm_repos, category: vector_database)

CONSTRAINTS:
- Do not hand-edit `inputs/intake/intake_queue.yaml`; use queue sync tooling.
- Keep explicit `target_shard` on every manifest row.
- If any locked shallow target is no longer queued at preflight, stop and escalate with replacement options and new target hashes.
- Follow `contracts/deep_narrative_contract.md` for deep files.
- Do not modify contracts or AGENTS.md.
- YAML string values containing backticks, @, [, ], :, #, {, } must be quoted.

COMMIT-SCOPE WHITELIST (execution commit only):
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

PRE-FLIGHT (must pass):
1) `git status -sb`
2) Worktree isolation gate: if pre-existing dirty/untracked artifacts exist, resolve before execution. If unresolved, stop and escalate.
3) `git log --oneline --decorate -n 8`
4) `python3 tools/check_intake_queue_sync.py --workspace-root .`
5) `python3 tools/query_master.py stats`
6) `python3 tools/query_master.py aggregate --group-by predicate --top 15`
7) `python3 tools/query_master.py aggregate --group-by category --top 15`
8) Record freshness baselines:
   - `master_index.generated_at_utc`
   - `master_graph.generated_at_utc`
   - `master_deep_facts.generated_at_utc`
9) Record preflight unmapped-section baseline (required):
   - `python3 - <<'PY'`
   - `import yaml`
   - `from pathlib import Path`
   - `c=Path('reports/ws6_deep_integration/coverage.yaml')`
   - `v=Path('reports/ws6_deep_integration/validation_runs.yaml')`
   - `cd=yaml.safe_load(c.read_text()) if c.exists() else {}`
   - `vd=yaml.safe_load(v.read_text()) if v.exists() else {}`
   - `n=(cd.get('metrics') or {}).get('unmapped_sections_count')`
   - `if n is None: n=(vd.get('gate_metrics') or {}).get('unmapped_sections_count', 'unknown')`
   - `print('unmapped_sections_count_pre', n)`
   - `PY`
10) Record SHA1 hashes:
   - `phase_4_progress_tracker.yaml`
   - all prior prompt files (`P4-B2` through `P4-B5`)
   - authoritative prompt hash from lock artifact (`reports/phase4/prompt_locks/P4-B6.lock.yaml`, field: `prompt.sha1`)

IMPLEMENTATION ORDER:
1) Prepare manifest rows for shallow targets with explicit shard/category/source fields.
2) Author deep narratives for deep targets under `{shard}/knowledge/deep/<file_stem>.yaml`.
3) Run canonical pipeline:
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
4) WS7 execution rule:
   - Run strict compile once: `python3 tools/ws7_read_model_compiler.py --workspace-root .`
   - `--force` is compatibility-only (no-op) and must not be treated as a recovery path.
   - Any strict failure (blocking gate or otherwise) => stop and escalate.
5) Queue refresh:
   - `python3 tools/check_intake_queue_sync.py --workspace-root . --fix`
   - `python3 tools/check_intake_queue_sync.py --workspace-root .`
6) Post-run checks:
   - `python3 tools/query_master.py stats`
   - `python3 tools/query_master.py aggregate --group-by predicate --top 15`
   - `python3 tools/query_master.py aggregate --group-by category --top 15`
   - `python3 - <<'PY'`
   - `import yaml`
   - `from pathlib import Path`
   - `c=Path('reports/ws6_deep_integration/coverage.yaml')`
   - `v=Path('reports/ws6_deep_integration/validation_runs.yaml')`
   - `cd=yaml.safe_load(c.read_text()) if c.exists() else {}`
   - `vd=yaml.safe_load(v.read_text()) if v.exists() else {}`
   - `n=(cd.get('metrics') or {}).get('unmapped_sections_count')`
   - `if n is None: n=(vd.get('gate_metrics') or {}).get('unmapped_sections_count', 'unknown')`
   - `print('unmapped_sections_count_post', n)`
   - `PY`

HARD ACCEPTANCE CRITERIA:
- Queue sync PASS pre and post.
- All WS1/trust/validate/WS6/WS7 blocking gates PASS.
- WS7 strict-first observed; `--force` not used as a recovery path.
- Worktree isolation gate passed before execution started.
- Deep lane outputs:
  - 4 deep files exist.
  - 4 deep_facts files exist.
  - each has >=1 fact.
- Batch-level `query_master stats.deep_facts` delta is > 0.
- All evidence required by rubric is complete.
- Post-run queued_count should be 0 (queue fully drained).

SOFT QUALITY DISCLOSURE (required to report, non-blocking):
- Unmapped-section count: before -> after, with explicit delta and attribution.
- Metric source rule: use `reports/ws6_deep_integration/coverage.yaml` -> `metrics.unmapped_sections_count` as canonical source; use `reports/ws6_deep_integration/validation_runs.yaml` -> `gate_metrics.unmapped_sections_count` only as fallback.

FINAL REPORT FORMAT:
1) Baseline vs final counts:
   - `queued_count`, `already_canonical_count`, `repos`, `nodes`, `edges`, `deep_facts`
2) Freshness disclosure:
   - `master_index.generated_at_utc` (before -> after)
   - `master_graph.generated_at_utc` (before -> after)
   - `master_deep_facts.generated_at_utc` (before -> after)
   - WS7 snapshot status (`pass` or `warn`) + `--force` invocation status (expected `false`; no-op if `true`)
3) Evidence hash block:
   - SHA1 for `phase_4_progress_tracker.yaml`
   - SHA1 for prior prompts (`P4-B2` through `P4-B5`)
   - active prompt hash from lock artifact (`reports/phase4/prompt_locks/P4-B6.lock.yaml` -> `prompt.sha1`)
   - Hash stability statement (stable or drifted)
4) Deep lane table:
   - `github_full_name`, deep file, deep_facts file, fact count, status
5) Shallow lane table:
   - `github_full_name`, manifest updated, canonical file path, `query_master repo` status
6) Gate summary table (command + pass/fail)
7) Files changed list (paths only)
8) Unmapped-sections disclosure:
   - `unmapped_sections_count_pre`, `unmapped_sections_count_post`, delta
   - source used (`coverage.metrics.unmapped_sections_count` or `validation_runs.gate_metrics.unmapped_sections_count` fallback)
9) Blockers/fallbacks with exact reason

RUBRIC ACCEPTANCE GATE:
- Executor report acceptance must be judged against:
  - `/Users/szilaa/scripts/ext_sources/github_repos/plan-drafts/Phase 4 Executor Report Review Rubric.md`

BLOCKER PROTOCOL:
- If blocked, stop immediately and report expected vs found, 2-3 options with tradeoffs, and recommended option.
- Do not proceed past blocker without user confirmation.
