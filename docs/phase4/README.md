# Phase 4 Supervisor Docs

High-signal references for drafting and auditing the next Phase 4 batch prompt.

Files:
- `prompt_audit_header_v3.yaml`: canonical header template for next-run prompts.
- `prompt_hash_helper.md`: preflight snippet to generate hash fields for `immutable_context` and `target_lock`.

Use order:
1. Draft new batch prompt from prior approved prompt.
2. Paste `PROMPT_AUDIT_HEADER` from `prompt_audit_header_v3.yaml`.
3. Run helper snippet from `prompt_hash_helper.md` and paste results into header.
4. Verify acceptance/report sections align with:
   - `plan-drafts/Phase 4 Executor Report Review Rubric.md`

Stop rule:
- Do not hand off to executor if header hashes are missing or unverified.
