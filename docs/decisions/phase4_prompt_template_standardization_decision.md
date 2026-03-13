# Phase 4 Prompt Template Standardization Decision (Draft)

Drafted at (UTC): 2026-03-12T02:41:04Z

## Proposed Decision

Standardize the locked Phase 4 batch prompt structure as the default execution template for future Phase 4 corpus-expansion runs.

Adopt the template with these required guardrails preserved:

- external prompt lock remains authoritative for active prompt hash
- unmapped-section reporting must use `reports/ws6_deep_integration/coverage.yaml -> metrics.unmapped_sections_count` first, with `validation_runs.yaml -> gate_metrics.unmapped_sections_count` only as fallback
- WS7 remains strict-first, and `--force` remains compatibility-only rather than a recovery path
- execution artifacts and control-plane/governance updates remain separate commits

This draft does not propose automatic acceptance of future runs.
It standardizes the execution contract, not the review judgment.

## Why

- The repo now has three hardened hybrid runs in sequence (`B3`, `B4`, `B5`) with no blocking WS1, trust-gate, validation, WS6, or WS7 regressions.
- `B5` specifically validated the two issues that were still blocking standardization:
  - canonical unmapped-section sourcing was used and disclosed from WS6 coverage metrics
  - WS7 strict-only semantics were preserved with `force_flag: false`
- The remaining `B5` note was not a prompt-shape failure. It was a control-plane lag: execution evidence landed before status files were updated.

That distinction matters. We should not keep re-editing the execution prompt to solve a governance/process issue that belongs in review and commit hygiene.

## Tradeoff

- Standardizing the template reduces prompt drift and rerun churn.
- It does not eliminate the need for supervisor review, especially around closure state, commit scope, and status-file synchronization.
- Keeping the template stable makes deviations easier to spot, but it also means process mistakes outside the prompt will stay visible instead of being papered over.

## Conditions To Approve

Approve this draft only if we agree on all of the following:

1. The prompt template should be treated as execution infrastructure, not as the place to encode every post-run governance task.
2. `ACCEPT`, `ACCEPT_WITH_NOTES`, or `REJECT` remains a supervisor decision based on evidence and current repo state.
3. Status-file synchronization after execution is enforced as a separate control-plane step when needed, not bundled implicitly into the execution lane.

## Trigger To Revisit

Re-open this decision if any of the following happens:

1. A future hardened batch reveals a real prompt-structure gap that causes repeated operator ambiguity or missed hard gates.
2. WS7/query preflight behavior changes enough that the standard preflight command set is no longer reliable without extra setup.
3. Commit-scope separation repeatedly breaks down in practice, which would mean the workflow contract needs stronger automation rather than just a standardized prompt.
