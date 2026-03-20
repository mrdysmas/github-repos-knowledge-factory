# Q7 Signal Audit — Extraction Gap vs. Term-Shape vs. Thin-Category

Date: 2026-03-20
Source issue: `github_repos-iaq`
Feeds: `github_repos-vjq`, `github_repos-zfn`

## Purpose

Classify the five Q7 verification failures from `q7_riskcheck_verification_2026-03-20.md`
into extraction gap, term-shape / predicate mismatch, and thin-category bias. Avoid
collapsing the diagnosis into a generic "WS6 is weak" finding unless predicate coverage
data supports that claim.

## Predicate Coverage — Baseline Facts

The following were queried directly from `knowledge.db`:

| Category | Repos | implements_pattern (facts / repos-with-facts) | has_component (facts / repos-with-facts) | uses_protocol (facts / repos-with-facts) |
|---|---|---|---|---|
| agent_cli | 13 | 49 / 8 | 270 / 13 | **0 / 0** |
| vector_database | 10 | 46 / 6 | 236 / 10 | **0 / 0** |
| tunneling | 9 | 104 / 9 | 89 / 9 | 60 / 9 |
| agent_framework | 8 | 41 / 5 | 163 / 8 | **0 / 0** |
| structured_outputs | 4 | 48 / 4 | 100 / 4 | **0 / 0** |

Critical observation: `uses_protocol` is completely absent in four of five categories.
Tunneling has rich protocol coverage (37 distinct values, 9/9 repos). This means WS6
is capable of protocol extraction — the gap is category-selective, not a global failure.

---

## Failure Classification

### 1. Extraction Gap

**`uses_protocol` in agent_cli, vector_database, agent_framework, structured_outputs**

- All four categories have zero protocol facts. Zero repos covered.
- Affected verification signals: REST (agent_cli), gRPC (vector_database), JSON
  (agent_framework), JSON schema (structured_outputs).
- All `absent_from_category` findings for protocol terms in these categories are
  extraction gaps, not genuine rarity signals.
- Tunneling contrast: TCP, QUIC, WebSocket, gRPC, TLS, SOCKS5 are all extracted,
  covering all 9 repos. The extraction mechanism works when protocol vocabulary is
  present in source content.
- Working hypothesis: agent/ML category repos do not naturally expose protocol terms
  in the form WS6 looks for, or WS6 was not run with protocol extraction enabled for
  these categories. Requires further investigation before treating as a pure WS6 fix.

**HNSW absent from `vector_database` implements_pattern**

- 46 pattern facts exist across 6/10 repos, but HNSW returns zero hits.
- Actual pattern values: test coverage patterns, storage layouts, transaction models,
  schema-on-write validation. None are algorithm names.
- WS6 extracted architectural and test-coverage patterns, not algorithm names. HNSW,
  IVF-Flat, etc. were either not represented in source content as patterns, or were
  not extracted at the right level of abstraction.
- Diagnosis: extraction gap at the conceptual level (algorithm vocabulary not in
  corpus), compounded by WS6 choosing test/structural patterns over algorithm terms.

**Streaming absent from `structured_outputs` implements_pattern**

- 48 pattern facts exist across all 4 repos, zero streaming hits.
- Streaming as an implementation pattern concept is simply not present in the extracted
  facts for this category. Extraction gap or genuine absence in source content.

---

### 2. Term-Shape / Predicate Mismatch

**`vector_database` "Python client" (has_component)**

- `has_component` has 236 facts across 10/10 repos — coverage is dense.
- Actual values include: "Python / PyBind11", path values like
  "python/python/lancedb/table.py", "usearch.Index (Python)", "Python".
- "Python client" as a compound term does not substring-match any of these. The
  concept is present in the data, but the compound form of the query term does not
  find it.
- Diagnosis: term-shape mismatch. Querying "Python" alone would return results.
  Multi-word compound component terms are unreliable with substring matching.

**`agent_cli` "plugin" (queried as implements_pattern)**

- Verification used `--pattern plugin` → implements_pattern. Returned 1/13 (rare).
- But plugin vocabulary is primarily in `has_component`: "Plugin extension surface",
  "Plugin runtime", "Plugin support", "plugins/" — across 4 repos (4/13).
- The concept is present and well-attested, but it was queried against the wrong
  predicate. `implements_pattern` has only 1 repo with plugin-related patterns.
- Diagnosis: predicate mismatch. Plugin is a component in this corpus, not a pattern.
  Callers need predicate awareness when querying Q7.

**`tunneling` "config" (has_component)**

- Returns 3/9 (established), but matched values are file paths: `pkg/config/v1/`,
  `src/config.rs`, `src/config_watcher.rs`, `src/config.rs`.
- `has_component` in tunneling has path-shaped values, not normalized conceptual
  component names. "Config" as a substring is hitting file and module paths, not
  a component named "config".
- Diagnosis: normalization problem in WS6 extraction — path-shaped values in
  `has_component` pollute substring queries. The "config established" finding from
  the verification is a false positive.

**`agent_framework` "tool-calling" (has_component)**

- `has_component` has 163 facts across 8/8 repos. "Tool" substring returns 3 hits,
  but they are: "Skill creator toolchain", "Curated catalog of Claude Skills",
  "Development & Code Tools" — none are tool-calling infrastructure.
- The category itself (agent_framework in this corpus) is dominated by skills/catalog
  repos, not mainstream agent frameworks. The term hits but hits conceptually unrelated values.
- Diagnosis: category composition mismatch — the actual repos in `agent_framework`
  are skills-catalog repos, not tool-calling infrastructure repos. This is partly
  thin-category bias and partly that the category label overpromises.

---

### 3. Thin-Category Bias

**`structured_outputs` (4 repos)**

- Fraction signals at n=4 are unreliable. 3/4 for pydantic looks established but
  the category is dominated by pydantic's own repos (pydantic/pydantic,
  pydantic/pydantic-core) — making pydantic hits circular, not typicality evidence.
- Any absent signal here could be extraction gap or genuine rarity; the sample size
  does not distinguish them.

**`agent_framework` (8 repos)**

- Borderline. 1/8 for memory is noisy but not wrong. 2/8 for tool-calling is
  misleading given the composition issue above.

---

## Summary Classification

| Verification case | Category | Signal | Classification |
|---|---|---|---|
| REST absent | agent_cli | uses_protocol | **Extraction gap** |
| gRPC absent | vector_database | uses_protocol | **Extraction gap** |
| HNSW absent | vector_database | implements_pattern | **Extraction gap** (abstraction level) |
| JSON absent | agent_framework | uses_protocol | **Extraction gap** |
| JSON schema absent | structured_outputs | uses_protocol | **Extraction gap** |
| streaming absent | structured_outputs | implements_pattern | **Extraction gap** |
| "Python client" absent | vector_database | has_component | **Term-shape mismatch** |
| plugin rare (not established) | agent_cli | implements_pattern | **Predicate mismatch** |
| config false-positive | tunneling | has_component | **Normalization gap (path values)** |
| tool-calling signal weak | agent_framework | has_component | **Category composition** |
| pydantic circular | structured_outputs | has_component | **Thin/compositional bias** |

---

## Key Anti-Collapse Finding

**Do not generalize the `uses_protocol` gap as "WS6 is weak."**

Tunneling shows that protocol extraction works well when the source content
contains protocol vocabulary. The gap in agent_cli / vector_database / agent_framework /
structured_outputs may reflect genuine source-content sparsity for protocol terms
(these repos do not expose protocol-layer vocabulary prominently) rather than
a global WS6 failure. A targeted investigation — e.g. checking whether source content
for agent_cli repos contains protocol terms at all — should precede any WS6 backfill.

`has_component` is reliably extracted across all categories (10/10, 13/13, 8/8, 4/4
repos covered). Failures on component queries are term-shape or category-composition
issues, not extraction failures.

---

## Recommendations

### Concrete next steps

**1. Investigate uses_protocol source-content coverage before backfill**

Before treating the uses_protocol gap as a WS6 backfill target, verify whether the
source content for agent_cli / vector_database / agent_framework repos actually
contains extractable protocol terms. If the repos do not use protocol vocabulary,
WS6 backfill won't help and category-level warnings are the right response.

Create: targeted investigation issue (Q7 protocol source-content coverage check).

**2. Component normalization: remove path-shaped values from has_component**

`has_component` in several categories contains file paths and module paths as values
(e.g. `pkg/config/v1/`, `pydantic/json_schema.py`, `skills/writing-skills/SKILL.md`).
These pollute substring queries and produce false positives for generic terms.

WS6 backfill or extraction guidance should normalize `has_component` to conceptual
component names, not file system artifacts.

Create: WS6 normalization issue for has_component path-valued facts.

**3. Add predicate-mismatch guidance to Q7 usage docs**

The plugin/agent_cli case shows that callers need to think about whether a concept
is a pattern or a component before choosing the query flag. The docs should note
which predicate best represents which concept type.

No new issue needed — update `query_master_reference.md` with guidance.

**4. Add category reliability warnings for thin categories and uses_protocol gaps**

The `corpus_health.fact_count_in_scope` added in `github_repos-63q` provides the
right hook. A uses_protocol fact count of 0 in a category should surface as a
warning to callers, not just a silent absent signal.

This may already be addressed by the corpus_health signal reliability note added in
63q. No new issue unless callers need an explicit flag field.

**5. Document agent_framework as a reliability risk category**

The repos in `agent_framework` are skills-catalog repos, not mainstream agent
framework infrastructure. Signals from this category should carry a note that category
composition may not match the label.

---

## Follow-on Issue Candidates

Issues to create only where diagnosis is concrete:

1. **uses_protocol source-content investigation** — Before backfill: check whether
   agent_cli, vector_database, agent_framework repos contain protocol vocabulary in
   source. Classify as "content sparse" or "extraction failure."

2. **has_component normalization: filter path-shaped values** — WS6 extraction should
   not emit file paths or directory paths as component values. Audit current facts and
   add normalization filter.
