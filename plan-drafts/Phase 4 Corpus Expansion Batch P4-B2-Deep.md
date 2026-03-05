TASK: Phase 4 Corpus Expansion Batch P4-B2-Deep (4 repo deep sub-batch)

PROMPT_AUDIT_HEADER:
  template_version: "p4-prompt-audit-v1"
  prompt_id: "P4-B2-DEEP"
  run_class: "deep_sub_batch_validation"
  primary_intent: "Generate deep narratives for 4 already-canonical repos and prove non-zero deep fact materialization."
  hard_gates:
    - "All WS6/WS7 blocking gates PASS."
    - "4 deep narrative files created under llm_repos/knowledge/deep."
    - "4 deep_facts files created under llm_repos/knowledge/deep_facts."
    - "Each target deep_facts file contains >= 1 fact."
    - "Batch deep_facts delta is > 0 versus preflight baseline."
    - "WS7 strict-first run required; --force allowed only for snapshot/timestamp-only failure."
  known_failure_modes:
    - "Identity header drift from shallow repo file causes WS6 mapping/traceability issues."
    - "Using unrecognized deep section names increases unmapped-section noise and reduces extractable facts."
    - "Clone availability gap blocks deep narrative generation from source code."
    - "Deep files created but facts remain flat (materialization failure or low-yield narrative structure)."
  report_tags:
    - "phase4"
    - "batch"
    - "deep-lane"
    - "hard-deep-gate"

MODE: EXECUTION (no exploratory detours)

WORKSPACE:
- Repo root: /Users/szilaa/scripts/ext_sources/github_repos
- Branch: codex/phase-2b-sb2

OBJECTIVE:
- Run a targeted deep pass for 4 already-canonical B2 repos.
- Materialize new deep facts via WS6 and validate strict-first WS7 behavior.
- Prove deep lane viability with a hard deep gate (non-zero deep_facts delta).

TARGET REPOS (already canonical):
1) pydantic/pydantic (file_stem: pydantic__pydantic)
2) pydantic/pydantic-core (file_stem: pydantic__pydantic-core)
3) pydantic/pydantic-settings (file_stem: pydantic__pydantic-settings)
4) dottxt-ai/outlines (file_stem: dottxt-ai__outlines)

CONSTRAINTS:
- Do not modify `inputs/intake/intake_queue.yaml`.
- Do not modify `inputs/ws5/ws5_input_manifest.yaml`.
- Do not run WS5 for this sub-batch.
- Do not modify contracts or AGENTS.md.
- Keep commit scope to deep lane artifacts + WS6/WS7 evidence only.

REQUIRED CONTRACT:
- Follow `contracts/deep_narrative_contract.md` exactly.
- Deep file location: `llm_repos/knowledge/deep/<file_stem>.yaml`.
- Copy identity fields from `llm_repos/knowledge/repos/<file_stem>.yaml` exactly:
  - `node_id`, `github_full_name`, `html_url`, `source`, `name`
- Set `provenance.shard: llm_repos` and `provenance.source_file` to the deep file path.
- Use only WS6-recognized section names to avoid unmapped-section noise.

PRE-FLIGHT (must pass):
1) `python3 tools/check_intake_queue_sync.py --workspace-root .`
2) `python3 tools/query_master.py stats` (record baseline counts)
3) Record baseline freshness timestamps:
   - `master_index.yaml.generated_at_utc`
   - `master_graph.yaml.generated_at_utc`
   - `master_deep_facts.yaml.generated_at_utc`
4) Confirm each target has:
   - existing shallow file in `llm_repos/knowledge/repos/<file_stem>.yaml`
   - no existing deep file in `llm_repos/knowledge/deep/<file_stem>.yaml`
   - no existing deep_facts file in `llm_repos/knowledge/deep_facts/<file_stem>.yaml`
5) Ensure source code access for each repo:
   - if local clone exists, use it
   - else clone-on-demand to `intake_repos/<owner>__<repo>-deep` (depth 1 is fine)

IMPLEMENTATION:
1) Produce 4 deep narratives (one per target repo) under:
   - `llm_repos/knowledge/deep/pydantic__pydantic.yaml`
   - `llm_repos/knowledge/deep/pydantic__pydantic-core.yaml`
   - `llm_repos/knowledge/deep/pydantic__pydantic-settings.yaml`
   - `llm_repos/knowledge/deep/dottxt-ai__outlines.yaml`
2) For each deep narrative, include high-yield recognized sections when applicable:
   - `architecture`
   - `configuration`
   - `code_patterns` and/or `implementation_patterns`
   - `core_modules`
   - `key_features`
   - `key_files`
   - `testing`
   - `integrations`
   - `quick_reference`
   - `commands` and/or `cli_arguments`
   - `api_surface` and/or `api_structure`
3) Run WS6 materialization + validation suite:
   - `python3 tools/ws6_deep_integrator.py --workspace-root . --reports-dir reports/ws6_deep_integration --materialize-spec reports/ws6_deep_integration/spec.yaml --run-validation-suite`
4) Run WS7 strict compile:
   - `python3 tools/ws7_read_model_compiler.py --workspace-root .`
5) WS7 fallback policy:
   - Do NOT use `--force` by default.
   - Use `--force` only if strict failure is snapshot/timestamp consistency only.
   - If any blocking gate fails (`row_count_parity`, `orphan_edge_detection`, `query_parity`, `deterministic_rebuild`), stop and escalate.
6) Post-run checks:
   - `python3 tools/query_master.py stats`
   - confirm deep_facts files now exist for all 4 targets
   - compute per-file fact counts from `llm_repos/knowledge/deep_facts/<file_stem>.yaml`
   - `python3 tools/query_master.py aggregate --group-by predicate`

HARD ACCEPTANCE CRITERIA (all required):
- All WS6/WS7 blocking gates pass.
- 4 deep narrative files created.
- 4 deep_facts files created.
- Each of the 4 deep_facts files contains at least 1 fact.
- Batch-level `query_master stats.deep_facts` delta is > 0 vs preflight baseline.
- WS7 strict-first policy honored; any fallback explicitly justified.

SOFT QUALITY TARGETS (non-blocking but report):
- Keep unmapped section growth minimal (report exact delta from WS6 mismatch report).
- Prefer at least 10 facts per target repo when possible.

FILES EXPECTED TO CHANGE:
- `llm_repos/knowledge/deep/*.yaml` (4 new files)
- `llm_repos/knowledge/deep_facts/*.yaml` (4 new files)
- `master_deep_facts.yaml`
- `reports/ws6_deep_integration/coverage.yaml`
- `reports/ws6_deep_integration/mismatch_report.yaml`
- `reports/ws6_deep_integration/validation_runs.yaml`
- `reports/ws7_read_model/compile_log.yaml`
- possibly `llm_repos/knowledge/trust-gates-report.yaml` and `ssh_repos/knowledge/trust-gates-report.yaml` from validation suite

FINAL REPORT FORMAT:
1) Baseline vs final counts:
   - `query_master stats` (`repos`, `nodes`, `edges`, `deep_facts`), with deltas
2) Deep output table (per target repo):
   - `github_full_name`
   - deep file path
   - deep_facts file path
   - deep_facts count
   - status (pass/fail)
3) Freshness disclosure:
   - `master_index/generated_at_utc` (before -> after)
   - `master_graph/generated_at_utc` (before -> after)
   - `master_deep_facts/generated_at_utc` (before -> after)
   - WS7 snapshot status (`pass` or `warn`) and fallback usage
4) WS6 quality disclosure:
   - unmapped section count (before -> after)
5) Files changed (paths only)
6) Gate summary table (command + pass/fail)
7) Blockers/fallbacks with exact reason

BLOCKER PROTOCOL:
- If blocked, stop immediately and report:
  - expected vs found
  - 2-3 options with tradeoffs
  - recommended option
- Do not proceed past blocker without user confirmation.
