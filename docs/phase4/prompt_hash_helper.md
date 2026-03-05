# Phase 4 Prompt Hash Helper

Use this helper to:
- generate/update the authoritative lock artifact at `reports/phase4/prompt_locks/<PROMPT_ID>.lock.yaml`
- populate `immutable_context` and `target_lock` fields in `PROMPT_AUDIT_HEADER`

Run from repo root and update:
- `prompt_id`
- `prompt_file`
- `shallow_targets`
- `deep_targets`

```bash
set -euo pipefail

prompt_id="P4-B4"
prompt_file="plan-drafts/Phase 4 Corpus Expansion Batch P4-B4.md"
lock_file="reports/phase4/prompt_locks/${prompt_id}.lock.yaml"

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
prompt_sha1="$(sha1_file "$prompt_file")"
shallow_sha1="$(hash_target_list "${shallow_targets[@]}")"
deep_sha1="$(hash_target_list "${deep_targets[@]}")"

mkdir -p "$(dirname "$lock_file")"

{
  cat <<YAML
artifact_type: phase4_prompt_lock
contract_version: 1.0.0
generated_at_utc: "$now_utc"
lock_id: "$prompt_id"

prompt:
  path: "$prompt_file"
  sha1: "$prompt_sha1"
  source_of_truth: "external_lock_file"
  note: "Authoritative prompt hash lives in this lock file."

immutable_context:
  phase4_tracker_sha1: "$(sha1_file "phase_4_progress_tracker.yaml")"
  rubric_sha1: "$(sha1_file "plan-drafts/Phase 4 Executor Report Review Rubric.md")"
  prior_prompt_sha1:
    p4_b2: "$(sha1_file "plan-drafts/Phase 4 Corpus Expansion Batch P4-B2.md")"
    p4_b2_deep: "$(sha1_file "plan-drafts/Phase 4 Corpus Expansion Batch P4-B2-Deep.md")"
    p4_b3: "$(sha1_file "plan-drafts/Phase 4 Corpus Expansion Batch P4-B3.md")"

target_lock:
  shallow_target_count: ${#shallow_targets[@]}
  deep_target_count: ${#deep_targets[@]}
  shallow_targets_sha1: "$shallow_sha1"
  deep_targets_sha1: "$deep_sha1"
  lock_timestamp_utc: "$now_utc"

locked_targets:
  shallow:
YAML
  for t in "${shallow_targets[@]}"; do
    printf '    - "%s"\n' "$t"
  done
  cat <<YAML
  deep:
YAML
  for t in "${deep_targets[@]}"; do
    printf '    - "%s"\n' "$t"
  done
} > "$lock_file"

cat <<YAML
immutable_context:
  phase4_tracker_sha1: "$(sha1_file "phase_4_progress_tracker.yaml")"
  rubric_sha1: "$(sha1_file "plan-drafts/Phase 4 Executor Report Review Rubric.md")"
  prior_prompt_sha1:
    p4_b2: "$(sha1_file "plan-drafts/Phase 4 Corpus Expansion Batch P4-B2.md")"
    p4_b2_deep: "$(sha1_file "plan-drafts/Phase 4 Corpus Expansion Batch P4-B2-Deep.md")"
    p4_b3: "$(sha1_file "plan-drafts/Phase 4 Corpus Expansion Batch P4-B3.md")"
  self_prompt_lock_ref: "$lock_file"

target_lock:
  shallow_target_count: ${#shallow_targets[@]}
  deep_target_count: ${#deep_targets[@]}
  shallow_targets_sha1: "$shallow_sha1"
  deep_targets_sha1: "$deep_sha1"
  lock_timestamp_utc: "$now_utc"

authoritative_prompt_hash:
  prompt_lock_ref: "$lock_file"
  prompt_sha1: "$prompt_sha1"
  prompt_hash_source: "external_lock_file"
YAML
```

Recommended enforcement:
- If `self_prompt_lock_ref` is missing, prompt draft is incomplete.
- If lock file is missing or `prompt.sha1` does not match the prompt file, stop and escalate.
