# Supervisor Notes

**Created:** 2026-03-18  
**Purpose:** Durable context for a Claude Code agent picking up project supervision.  
This document captures the *why* behind decisions, lessons from failures, and forward
priorities. It supplements the repo's own state files — it does not replace them.

Read this alongside:
- `project_status.yaml` — current quantitative state
- `phase_4_progress_tracker.yaml` — batch history and progress
- `AGENTS.md` — agent instruction file (read before any work)
- `contracts/deep_narrative_contract.md` — the output contract (v2.0, Active)
- `docs/INGESTION_WORKFLOW.md` — authoritative ingestion reference

---

## Project orientation

This is a personal data engineering pipeline that ingests GitHub repos, extracts
structured knowledge, and produces queryable canonical facts with provenance. The
core insight: decouple the cost of understanding a codebase from the moment of
querying it. This differentiates it from RAG tools like Cursor/Copilot — it produces
durable, structured, auditable facts rather than ephemeral retrieval results.

The owner (Abe) has no prior coding background. The entire project has been built by
directing Codex and other agents. The supervisor role — previously Claude chat — is
now being transferred to Claude Code. That means the supervisor/executor split
partially collapses: you can both reason about the project and act on the repo
directly.

**Codex tokens are on a promotional free rate.** Token-heavy tasks should be
prioritized while this lasts. The pipeline is intentionally reading/analysis/
processing-heavy to take advantage of this.

---

## Current state (as of 2026-03-18)

- **Phase:** 4, IN_PROGRESS
- **Branch:** main
- **Corpus:** 122 repos, 5,687 facts
- **Soft audit:** All three archetypes at full coverage (inference_serving 6/6,
  vector_database 10/10, tunneling 16/16). 90 repos unmatched.
- **Last completed batch:** B12 — v2.0 contract backfill, 27 files modified.
  `has_failure_mode` 78→128, `uses_protocol` 47→146.
- **All gates clean.** Remote up to date.

Key tools:
- `tools/query_master.py` — 9 commands, contract 1.2.0. Primary query interface.
- `tools/ws7_read_model_compiler.py` — builds `knowledge.db` (gitignored).
- `tools/run_batch.py` — orchestrator, chains WS5→WS4→clone_prep→WS6→WS7.
- `tools/ws6_soft_audit.py` — post-extraction behavioral coverage audit.

---

## Architecture decisions and their rationale

### Shard consolidation (done in Phase 4)
`llm_repos/` and `ssh_repos/` were collapsed into a single `repos/knowledge/`
directory. The shards were load-bearing (gating file paths and identity contracts
through WS5) but analytically worthless — `domain_hint` already carries semantic
taxonomy. Consolidation removed accidental complexity. `target_shard` normalizes to
`"repos"`; `domain_hint` carries taxonomy only.

### SQLite as read cache, YAML as write layer
`knowledge.db` is rebuilt on every `ws7` compile. It is the query layer (1ms vs.
multi-second YAML loads) but is never the source of truth. YAML is. This means
`knowledge.db` is gitignored and safe to delete — it rebuilds atomically. DuckDB
has been evaluated and deferred; SQLite is fine to ~500 repos.

### Evidence families over tiers (contract v2.0 change)
The original contract ranked sections by extraction ease (Tier 1/2/3). This caused
structural inventory (`has_component`, `has_config_option`) to dominate — ~88% of
all facts — while behaviorally rich predicates (`has_failure_mode`, `uses_protocol`)
were starved. v2.0 replaced tiers with four evidence families (Structure, Tasks,
Failures, Protocols & Integrations) and three repo archetypes with required families.
This is a breaking change for how deep narratives are written. The backfill (B12)
applied this to the 27 most important repos.

### Soft audit as non-blocking gate
The audit checks behavioral coverage by archetype but does not block ingestion. The
decision was Option 2 (contract redesign + lightweight post-generation soft audit,
not a hard gate). Rationale: learn from failures before preventing them. A hard gate
on behavioral coverage would have blocked ingestion of repos that are genuinely thin.

### Training knowledge as fallback (opt-in)
Deep narrative generation from training knowledge is only permitted when (1) no local
clone is available, (2) the repo is well-known with stable APIs, and (3) the batch
spec explicitly sets `sourcing_fallback: training_knowledge_permitted`. Without this
opt-in, WS6 expects code-verified content. This was added after early narratives
produced unverifiable claims.

---

## Lessons from failures — watch-outs for agents

### WS5 file_stem bug (critical, unfixed)
`ws5_remote_ingestion.py` defaults `file_stem` to `name`, not `owner__repo`. The
contract and workflow docs describe `owner__repo` as canonical, but the tool doesn't
enforce it. **Every manifest entry must set explicit `file_stem: owner__repo`** (e.g.
`abhigyanpatwari__gitnexus`) or WS5 produces the wrong stem and downstream files are
misnamed. Long-term fix: WS5 should default `file_stem` to `owner__repo`. This has
not been done yet — it requires a Codex task.

### WS5 overwrites existing shallow files unconditionally
WS5 does not check whether a shallow file already exists — it overwrites. Before
adding any manifest entry, read the existing shallow file at
`repos/knowledge/repos/<file_stem>.yaml` and carry forward any fields you want to
preserve. This burned us in B11 when a re-run overwrote correct data.

### dict-of-dicts shape in WS6 is silently skipped
WS6 expects list-of-dicts for sections like `commands`/`cli_commands`. If a section
is authored as a dict-of-dicts (e.g. `{"serve": {...}, "run": {...}}`), WS6 silently
skips it — no error, no facts. Always verify section shape against the contract
expected shapes before assuming extraction succeeded. This burned us when `cli_commands`
entries were authored incorrectly and produced zero facts with no warning.

### YAML quoting rule (causes WS6 gate failures)
Always quote string values containing: `` ` `` `@` `[` `]` `:` `#` `{` `}`.
Without quotes, WS6 gate failures occur. This must be checked in every deep narrative
before running the pipeline. It's in the contract (v2.0, YAML Quoting Rules section)
but agents consistently miss it.

### Deep narrative generation must be bundled into ingestion kickoffs
Learned from Phase 2B SB1: omitting deep narrative generation from an ingestion
kickoff produced a full batch of shallow-only repos with zero deep facts. Every
ingestion kickoff prompt must explicitly include the deep file generation step.
`docs/INGESTION_WORKFLOW.md` now documents this, but it's easy to miss.

### run_batch has no skip/resume
`tools/run_batch.py` always re-runs all steps including clone prep. Clone prep
detects already-cloned repos and skips the size check for them. `--force-large`
exists on `ws6_clone_prep.py` but is NOT wired through `run_batch`. For oversized
repos: run clone prep manually with `--force-large` first, then run_batch with
`clone_size_limit_mb` set high enough to pass re-check.

### html_url case sensitivity
`html_url` in manifest entries must match the shallow file exactly — case matters.
This has caused gate failures when capitalization differed (e.g. `Ngt` vs `ngt`).
Always copy `html_url` from the shallow file, never from memory or a URL you typed.

### Batch-specific manifests are the right pattern
Use `inputs/ws5/B<N>_*_manifest.yaml` for scoped runs, not the global manifest.
This keeps each batch's ingestion scope explicit and auditable.

---

## Predicate distribution context

Before B12 backfill (pre-v2.0):

| predicate | count |
|---|---|
| `has_component` | 2,354 |
| `has_config_option` | 1,055 |
| `implements_pattern` | 773 |
| `has_extension_point` | 676 |
| `supports_task` | 464 |
| `exposes_api_endpoint` | 91 |
| `has_failure_mode` | 78 |
| `uses_protocol` | 47 |

Post-B12: `has_failure_mode` 128, `uses_protocol` 146. Structural predicates still
dominate but the behavioral gap has narrowed. The v2.0 contract requirements should
produce more balanced distributions for future ingestion.

Fact yield is roughly 55–80 facts/repo regardless of repo size. Narrative density is
the extraction bottleneck, not source code richness.

---

## Open flags (low-priority, non-blocking)

1. `infinity.yaml` provenance: kept `code_verified` from a prior session — may need
   downgrade to `training_knowledge` if that session didn't actually clone the repo.
2. `vectordbbench` failure modes are benchmark-execution oriented, not storage-engine
   level — this is correct for that repo but worth noting when interpreting facts.
3. `nexa_sdk` silent-CPU-fallback entry is moderate-confidence — inferred behavior,
   not explicitly documented.
4. 33 unmapped section types across the corpus (1 instance each). Non-blocking,
   long-tail. Not worth pursuing before corpus expansion.
5. WS5 `file_stem` default (see watch-outs above) — known bug, not yet fixed.

---

## Forward priorities

### Immediate: archetype expansion
The soft audit now has data: 90 unmatched repos across many categories. That's the
input for deciding which archetype to define next. The trigger is audit data, not a
calendar. Sequence guidance already in memory:

1. `agent_framework` + `agent_cli` first (shared Tasks shape)
2. `rag_frameworks` second, if Protocols gaps are confirmed from audit data

Ceiling: ~6-8 archetypes total. Keep definitions narrow — vague requirements produce
audit-gaming, not better facts. Each new archetype implies a backfill class.

### Corpus expansion
Queue is currently drained. Next ingestion batch should apply v2.0 contract from the
start — no need to backfill new repos. Use batch-specific manifests.

### WS5 file_stem bug fix
This should be a Codex task: modify `ws5_remote_ingestion.py` to default `file_stem`
to `owner__repo` (replacing `/` with `__`). Low risk, high value — eliminates a
recurring source of errors in kickoff prompts.

### DuckDB (deferred)
Deferred to later in Phase 4, pending workload evidence. SQLite is fine to ~500 repos.
Revisit when corpus approaches that threshold.

---

## Supervisor/executor split — how this project works

Abe directs the work. The supervisor (previously Claude chat, now Claude Code) holds
context and rationale, drafts locked kickoff prompts for Codex, reviews Codex output
by pulling the repo and running verification commands. Abe pushes/commits and confirms.

**Decisions are made before Codex is handed a prompt.** Architecture decisions, phase
plans, and contract changes are committed to the repo before any agent runs. Gate-first
discipline: all pipeline stages have hard gates; nothing proceeds with failing gates.

For kickoff prompts specifically:
- Use tool code for CLI syntax/manifest schema/sequencing, not doc summaries
- Include the YAML quoting rule in every narrative generation prompt
- Include the `file_stem: owner__repo` requirement in every manifest entry
- Correct ingestion order: write manifest → clone prep → WS5 → WS4 → read shallow
  files → author deep headers → run_batch

---

## Communication preferences

Abe prefers:
- Conversational pacing, fewer ideas per sentence
- One-liner summaries when appropriate
- Fresh sessions for strategic exploration of new threads
- Dry or heavily structured output creates cognitive overhead — avoid
