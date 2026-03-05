# Phase 4 Prompt Hash Helper

Use this helper at preflight to populate `immutable_context` and `target_lock` fields in `PROMPT_AUDIT_HEADER`.

Run from repo root and update:
- `prompt_file`
- `shallow_targets`
- `deep_targets`

```bash
set -euo pipefail

prompt_file="plan-drafts/Phase 4 Corpus Expansion Batch P4-B4.md"

shallow_targets=(
  "owner1/repo1"
  "owner2/repo2"
)

deep_targets=(
  "openai/codex"
  "anthropics/claude-code"
  "ansible/ansible"
  "gin-gonic/gin"
)

sha1_file() {
  shasum "$1" | awk '{print $1}'
}

hash_target_list() {
  # normalize: lowercase, trim empties, sort unique
  printf '%s\n' "$@" \
    | tr '[:upper:]' '[:lower:]' \
    | sed '/^[[:space:]]*$/d' \
    | sort -u \
    | shasum \
    | awk '{print $1}'
}

now_utc="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

cat <<YAML
immutable_context:
  phase4_tracker_sha1: "$(sha1_file "phase_4_progress_tracker.yaml")"
  rubric_sha1: "$(sha1_file "plan-drafts/Phase 4 Executor Report Review Rubric.md")"
  prior_prompt_sha1:
    p4_b2: "$(sha1_file "plan-drafts/Phase 4 Corpus Expansion Batch P4-B2.md")"
    p4_b2_deep: "$(sha1_file "plan-drafts/Phase 4 Corpus Expansion Batch P4-B2-Deep.md")"
    p4_b3: "$(sha1_file "plan-drafts/Phase 4 Corpus Expansion Batch P4-B3.md")"
  self_prompt_sha1: "$(sha1_file "$prompt_file")"

target_lock:
  shallow_target_count: ${#shallow_targets[@]}
  deep_target_count: ${#deep_targets[@]}
  shallow_targets_sha1: "$(hash_target_list "${shallow_targets[@]}")"
  deep_targets_sha1: "$(hash_target_list "${deep_targets[@]}")"
  lock_timestamp_utc: "$now_utc"
YAML
```

Recommended enforcement:
- If hash fields are missing, prompt draft is incomplete.
- If hashes drift during execution, stop and escalate.
