# Phase 4 Supervisor Docs

High-signal references for drafting and auditing the next Phase 4 batch prompt.

Files:
- `prompt_audit_header_v3.yaml`: canonical header template for next-run prompts.
- `prompt_hash_helper.md`: preflight snippet to generate hash fields for `immutable_context` and `target_lock`.
- `reports/phase4/prompt_locks/<PROMPT_ID>.lock.yaml`: authoritative prompt hash source (`prompt.sha1`).

Use order:
1. Draft new batch prompt from prior approved prompt.
2. Paste `PROMPT_AUDIT_HEADER` from `prompt_audit_header_v3.yaml`.
3. Run helper snippet from `prompt_hash_helper.md`, generate/update `reports/phase4/prompt_locks/<PROMPT_ID>.lock.yaml`, and paste the lock reference into header (`immutable_context.self_prompt_lock_ref`).
4. Verify acceptance/report sections align with:
   - `plan-drafts/Phase 4 Executor Report Review Rubric.md`

Stop rule:
- Do not hand off to executor if `self_prompt_lock_ref` is missing, lock file is missing, or lock `prompt.sha1` is unverified.

Unmapped-section metric policy:
- Canonical read path: `reports/ws6_deep_integration/coverage.yaml` -> `metrics.unmapped_sections_count`.
- Fallback only: `reports/ws6_deep_integration/validation_runs.yaml` -> `gate_metrics.unmapped_sections_count`.
