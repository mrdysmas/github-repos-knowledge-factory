# Q7 Riskcheck Verification

Date: 2026-03-20
Source issue: `github_repos-et2`
Related: `github_repos-4lb`, `github_repos-63q`, `github_repos-vjq`, `github_repos-zfn`

## Purpose

Verify whether `riskcheck` materially improves Q7 advisory usefulness on realistic
coding-session prompts before defining Q7 slice 2.

This pass evaluates:

- whether `riskcheck` changes implementation direction, review plans, or caution posture
- whether weak results are caused by extraction gaps, term-shape mismatch, or thin-category bias
- whether Q7 slice 2 should be defined now

## Categories Used

Chosen from relatively high fact-density categories:

- `agent_cli`: 13 repos, about 46 facts/repo
- `vector_database`: 10 repos, about 51 facts/repo
- `tunneling`: 9 repos, about 50 facts/repo
- `agent_framework`: 8 repos, about 41 facts/repo
- `structured_outputs`: 4 repos, about 73 facts/repo

`structured_outputs` was intentionally kept as a stress test despite the thin repo count.

## Prompt Set

| # | Category | Proposed terms | Baseline prior |
|---|---|---|---|
| 1 | `agent_cli` | `plugin` pattern, `sqlite` component, `REST` protocol | plugin established; sqlite rare; REST rare |
| 2 | `vector_database` | `HNSW` pattern, `gRPC` protocol, `Python client` component | all established |
| 3 | `tunneling` | `QUIC` protocol, `config` component, `dashboard` component | QUIC rare-to-established; config established; dashboard rare |
| 4 | `agent_framework` | `memory` component, `tool` pattern, `JSON` protocol | memory established; tool-calling established; JSON uncertain/absent |
| 5 | `structured_outputs` | `pydantic` component, `streaming` pattern, `JSON schema` protocol | pydantic established; streaming uncertain; JSON schema established |

## Results

### 1. `agent_cli`

- Prior: plugin established, sqlite rare, REST rare
- Result: plugin rare (`1/13`), sqlite rare (`2/13`), REST absent
- Interpretation:
  - plugin being rare instead of established is decision-relevant
  - REST absence is a credible caution signal
- Diagnosis:
  - mostly genuine signal
- Score: `actionable`

### 2. `vector_database`

- Prior: all established
- Result: all absent
- Interpretation:
  - this is not trustworthy as a typicality judgment
- Diagnosis:
  - `uses_protocol` appears under-extracted for this category
  - `HNSW` not surfacing under `implements_pattern` may also reflect term/predicate mismatch
  - `Python client` as a component term is likely a query-shape mismatch as much as an extraction gap
- Score: `misleading`

### 3. `tunneling`

- Prior: QUIC rare-to-established, config established, dashboard rare
- Result: QUIC established (`3/9`), config established (`3/9`), dashboard absent
- Interpretation:
  - QUIC is a useful positive signal
  - dashboard absence is a useful caution signal
  - `config` is weaker than expected because substring matching hits path-shaped component values
- Diagnosis:
  - mix of genuine signal and term-shape/query-shape limitation
- Score: `actionable`

### 4. `agent_framework`

- Prior: memory established, tool-calling established, JSON uncertain
- Result: tool-calling established (`2/8`), memory rare (`1/8`), JSON absent
- Interpretation:
  - memory being rare is interesting, but not strong enough alone to redirect design
  - sample size is borderline for strong trust
- Diagnosis:
  - weak but possibly real signal
  - JSON absence may reflect weak `uses_protocol` coverage rather than true rarity
- Score: `weak improvement`

### 5. `structured_outputs`

- Prior: pydantic established, streaming uncertain, JSON schema established
- Result: pydantic established (`3/4`), streaming absent, JSON schema absent
- Interpretation:
  - pydantic is effectively circular in this category
  - absent signals are not reliable enough here
- Diagnosis:
  - compositionally biased thin category
  - likely protocol extraction weakness for JSON schema
- Score: `no useful signal`

## Summary Table

| # | Category | Outcome |
|---|---|---|
| 1 | `agent_cli` | actionable |
| 2 | `vector_database` | misleading |
| 3 | `tunneling` | actionable |
| 4 | `agent_framework` | weak improvement |
| 5 | `structured_outputs` | no useful signal |

Counts:

- actionable: `2/5`
- weak improvement: `1/5`
- misleading or no useful signal: `2/5`

## Recurring Failure Modes

### 1. Extraction coverage gaps

Most visible in `uses_protocol`.

Observed symptoms:

- `vector_database` returned zero useful protocol signal
- JSON-oriented protocol checks were frequently absent

This weakens trust in `absent_from_category` for protocol terms.

### 2. Term-shape and predicate-shape mismatch

Some proposed terms do not line up cleanly with the current ontology or fact wording.

Examples:

- `Python client` may not be represented as a `has_component` value
- `config` can match path-shaped component values rather than normalized conceptual components

These are not pure extraction failures.

### 3. Thin or compositionally biased categories

Categories with very small repo counts can produce noisy or circular signals.

Most visible in:

- `structured_outputs`

## Decision Rule

Use this threshold for deciding whether to define Q7 slice 2 from the current command:

- proceed to slice 2 definition only if at least `3/5` prompts are actionable
- and no more than `1/5` prompt is misleading due to obvious data-quality problems

This pass does **not** meet that bar.

## Recommendation

Do **not** define Q7 slice 2 yet.

The binding constraint is not query-shape anymore. It is signal reliability.

Near-term priority should be:

1. improve `riskcheck` reliability signaling in the query surface
2. audit and improve protocol/component coverage where Q7 is currently misleading
3. revisit slice 2 only after that reliability work lands

If forced to choose a later slice-2 direction:

- prefer Q3 linkage before repo-aware comparison

Reason:

- Q3 linkage can amplify the cases where Q7 already produces useful rare/absent signals
- repo-aware comparison needs stronger per-repo fact density and better coverage to avoid brittle output

## Forward Path

Recommended issue ordering:

1. `github_repos-63q` — add reliability metadata and documentation to `riskcheck`
2. targeted Q7 reliability/corpus issue for `uses_protocol` and component term coverage
3. only then revisit:
   - `github_repos-zfn`
   - `github_repos-vjq`
