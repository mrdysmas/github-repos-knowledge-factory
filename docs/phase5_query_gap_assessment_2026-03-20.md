# Phase 5 Query-Gap Assessment

Date: 2026-03-20
Epic: `github_repos-9fd`
Related: `phase_5_anchor_acceptance_rubric.yaml`, `docs/architecture_refinement_memo_2026-03-20.md`

## 1. Current Surface Summary

The query surface (`query_master.py` v1.2.0, `knowledge.db` schema 1.1.0) provides 9 commands: `stats`, `repo`, `neighbors`, `facts`, `search`, `pattern`, `graph`, `aggregate`.

Corpus: 121 repos, 135 nodes, 152 edges, 6058 deep facts across 8 predicates and 38 categories.

**What the surface does well today:**
- Per-repo fact retrieval by predicate (`facts --id ... --predicate ...`)
- Corpus-level aggregate counts by dimension (`aggregate --group-by predicate/category/...`)
- Full-text search across fact values and notes (`search --term ...`)
- Cross-repo pattern matching by predicate with optional value filter (`pattern --predicate ... --value ...`)
- Graph traversal up to 3 hops with relation and direction filters (`graph --id ... --hops ...`)
- Neighbor lookup with relation filter (`neighbors --id ... --relation ...`)

**What it does not do:**
- No category-filtered queries (cannot say "show me failure modes for agent_cli repos only")
- No cross-predicate correlation (cannot say "repos that have pattern X AND failure mode Y")
- No distribution/frequency output (cannot say "how common is pattern X across repos like mine?")
- No typicality assessment (cannot say "is this pattern typical or unusual for this category?")
- No ranked output (cannot say "which repos are the best references for problem X?")
- No advisory-shaped output (all output is raw facts/edges, not structured recommendations)

## 2. Per-Question Gap Assessment

### Q1: Adjacent-Pattern Discovery

**Question**: "What implementation patterns are most common in repos adjacent to this project for solving `<problem>`?"

**Beads task**: `github_repos-bee`

**What works now**: `pattern --predicate implements_pattern --value "<term>"` returns matching facts across the entire corpus with repo and category metadata. This is the closest existing command to Q1. An agent can assemble a partial answer by running this query and grouping results mentally.

**What is awkward**: The results are flat — a list of individual facts, not grouped by repo or category. There is no frequency count ("12 of 15 agent_cli repos implement streaming"). There is no adjacency filter — the query searches the entire corpus, not repos adjacent to a starting point. The agent must manually cross-reference `neighbors` or `graph` output with `pattern` output to approximate adjacency-scoped patterns.

**What is missing**: A single command that accepts a target repo (or category) and returns pattern distributions across adjacent/similar repos. This is the core Q1 shape.

**Primary blocker**: **Query design**. The facts exist (773 `implements_pattern` facts across the corpus). The missing piece is a query command that joins graph adjacency with pattern aggregation and returns frequency-ranked results.

**Non-inferability**: Strong. Cross-repo pattern distributions are genuinely non-inferable from the target repo alone.

---

### Q2: Likely-Component Discovery

**Question**: "What components should I expect to find, or need to add, when implementing `<feature>` in a repo like this?"

**Beads task**: `github_repos-tny`

**What works now**: `pattern --predicate has_component --value "<term>"` returns component facts across the corpus. `facts --id <repo> --predicate has_component` returns components for a specific repo. `aggregate --group-by category` shows which categories have the most facts. With 2354 component facts, the corpus has significant raw material.

**What is awkward**: Components are not normalized — the same logical component appears under different names in different repos (e.g., "Plugin system", "Plugin extension surface", "Plugin-based extensibility"). There is no way to ask "what components are typical for repos in category X?" without manually querying each repo in that category. The search is substring-based, not semantic — searching for "plugin" returns exact matches but misses "extension system" or "addon framework" that are functionally equivalent.

**What is missing**: A category-scoped component profile ("repos in the agent_cli category typically have these components"). Component normalization or clustering that groups functionally equivalent components. A comparison command ("what components does repo X have that repo Y does not?").

**Primary blocker**: **Query design + ontology shape**. The component facts exist but are not normalized enough to support aggregate "what's typical" queries. A category-scoped query command would be a meaningful improvement even without full normalization.

**Non-inferability**: Moderate. An agent can discover components by reading the target repo, but knowing "adjacent repos typically also have X, Y, Z" is non-inferable. The value is in the comparison, not the raw component list.

---

### Q3: Failure-Mode Preflight

**Question**: "What failure modes or edge cases are common when projects like this implement `<feature>`?"

**Beads task**: `github_repos-4iz`

**What works now**: `pattern --predicate has_failure_mode` returns failure modes across the corpus (296 facts). `search --term "<term>" --field both` can find failure modes by keyword (e.g., "timeout" returns 10 relevant results across multiple categories). Each failure mode fact includes a `note` field with cause and fix information.

**What is awkward**: Failure modes are not scoped by category — the agent cannot ask "what failure modes are common in vector_database repos?" without manual filtering. The 296 failure modes are unevenly distributed (65 in agent_cli, 42 in vector_database, many categories with fewer than 10). The distinction between implementation-time pitfalls and resulting-system failure modes (flagged in the research memo) is not captured in the ontology.

**What is missing**: Category-scoped failure-mode queries. Failure-mode frequency or commonality signals ("this failure mode appears in 8 of 10 vector_database repos" vs. "this failure mode appears in 1 repo"). No way to ask "what failure modes should I expect for `<feature>`?" — only "what failure modes exist that match `<term>`?". The feature-to-failure-mode link is implicit (via keyword search) rather than explicit.

**Primary blocker**: **Query design** is the immediate bottleneck — a category-filtered `pattern` command would unlock most of Q3's value with existing data. Corpus depth is a secondary concern (some categories have very few failure modes).

**Non-inferability**: Very strong. Failure modes from adjacent repos are definitionally non-inferable from the target repo. This is the highest non-inferability question in the set.

---

### Q4: Reference-Repo Selection

**Question**: "Which adjacent repos are the best references for implementing `<feature>`, and why?"

**Beads task**: `github_repos-a20`

**What works now**: `neighbors --id <repo>` returns all edges with relation types and notes. `graph --id <repo> --hops 2 --relation alternative_to` returns alternative repos with traversal. The `alternative_to` relation (41 edges) and `similar_to` (14 edges) are the most relevant relation types. Edge notes contain brief justifications (e.g., "RAGFlow is platform; LangChain is framework").

**What is awkward**: The query returns all neighbors undifferentiated — it cannot rank which neighbor is the *best* reference for a specific feature or problem. The agent must inspect each neighbor's facts separately to determine relevance. There is no way to ask "which neighbor has the most overlap with my implementation problem?" The `alternative_to` and `similar_to` relations capture static similarity, not feature-specific relevance.

**What is missing**: A feature-aware reference-repo ranking command ("for implementing streaming, which of my neighbors has the best coverage?"). A command that combines graph adjacency with fact overlap (e.g., "neighbors that have the most `implements_pattern` facts matching my search term"). Richer justification beyond edge notes.

**Primary blocker**: **Query design**. The graph edges exist and contain useful relation data. The missing piece is a query that combines graph traversal with fact-level relevance scoring. This is a join-and-rank operation the current CLI does not support.

**Non-inferability**: Strong. Knowing which adjacent repos are good references for a specific problem requires cross-repo knowledge.

---

### Q5: Solution-Variant Comparison

**Question**: "What are the main solution variants used across similar repos for `<problem>`, and what tradeoffs do they imply?"

**Beads task**: `github_repos-53l`

**What works now**: `pattern --predicate implements_pattern --value "<term>"` returns all repos implementing a matching pattern. An agent can manually compare the results to identify variants. The `alternative_to` edges (41) implicitly encode solution-variant relationships at the repo level.

**What is awkward**: Pattern values are free-text, not normalized — "Token-Based Auth", "OAuth flow with event-driven progress reporting", and "HTTP auth protocol" are all auth patterns but not linked. There is no tradeoff information in the pattern facts — the ontology captures *what* is implemented but not *why* or *at what cost*. The agent must manually group pattern results, infer which represent distinct solution variants, and reason about tradeoffs from notes alone.

**What is missing**: Solution-variant grouping (clustering functionally equivalent patterns into named variants). Tradeoff annotations ("this approach is simpler but less flexible"). A comparison-shaped output ("3 approaches found: variant A used by 8 repos, variant B used by 3 repos, variant C used by 1 repo; tradeoffs: ...").

**Primary blocker**: **Ontology shape**. The current ontology does not represent solution variants or tradeoffs as first-class concepts. `implements_pattern` captures individual patterns but not the grouping or comparison structure that Q5 requires. Query design is secondary — even with better queries, the underlying data does not capture variant-vs-variant relationships.

**Non-inferability**: Very strong. Solution-variant distributions across repos are definitionally non-inferable.

---

### Q6: Inspection-Priority Guidance

**Question**: "Before I change code, what parts of the target repo should I inspect first based on how similar repos are usually structured?"

**Beads task**: `github_repos-4nk`

**What works now**: `facts --id <repo> --predicate has_component` returns components with some path-level references. Component facts sometimes include `object_kind: path` entries pointing to specific directories or files. `pattern --predicate implements_pattern` facts sometimes include `location:` in notes.

**What is awkward**: Most component facts are concept-level ("Plugin extension surface") rather than path-level ("src/plugins/"). Where paths exist, they are target-repo-specific — useful for understanding that specific repo, but not for cross-repo structural guidance. The query surface has no way to say "based on how 10 similar repos are structured, you should inspect directories matching X pattern."

**What is missing**: A cross-repo structural profile ("agent_cli repos typically have their auth logic in X, their plugin system in Y"). Non-obvious inspection targets — the AGENTS.md research specifically says the value is in what the agent would *not* discover in its first 3 grep calls. A command that translates cross-repo component patterns into target-repo inspection suggestions.

**Primary blocker**: **Ontology shape + corpus quality**. The current ontology does not consistently capture repo structure at a level that supports cross-repo structural comparison. Component facts mix concepts and paths without a clear hierarchy. Even with better queries, the underlying structural data would need enrichment.

**Non-inferability**: Moderate with a nuance. Raw structural guidance ("look at src/auth/") is largely inferable from the target repo. The non-inferable value is "repos like this commonly have a hidden dependency between X and Y that you won't find by grepping" — and the current data rarely captures this kind of structural insight.

---

### Q7: Implementation-Risk Check

**Question**: "Does the implementation direction I'm considering look typical, risky, or unusual compared with adjacent repos?"

**Beads task**: `github_repos-6w4`

**What works now**: `pattern --predicate implements_pattern` can show whether a given pattern appears across the corpus. `graph --id <repo> --relation alternative_to` can show what alternatives exist. `facts --id <repo>` can show what patterns a specific repo uses. An agent could manually assemble a rough typicality judgment by combining these queries.

**What is awkward**: There is no typicality signal in the data — no way to distinguish "90% of repos do this" from "1 repo does this." The query surface returns facts but not distributions or norms. The agent must manually count matches, estimate frequency, and synthesize a risk assessment. There is no atypicality flag or risk signal in the ontology.

**What is missing**: A typicality assessment command ("how common is approach X in repos like mine?"). Distribution data (not just "which repos do X" but "what fraction of similar repos do X"). Atypicality/risk signals as first-class query outputs. A comparison command ("my planned approach uses A+B+C; here is how that compares to the norm for this category").

**Primary blocker**: **Query design + ontology shape**. The query layer needs frequency/distribution output (currently it only returns flat lists). The ontology needs a way to represent pattern frequency or typicality norms — either computed at query time from fact counts or stored as aggregate metadata. This is the highest-gap question.

**Non-inferability**: Very strong. Typicality assessment is the purest form of non-inferable cross-repo knowledge. An agent cannot know whether its approach is unusual without comparing against a corpus.

## 3. Cross-Question Analysis

### Shared blockers

The single most impactful missing capability across all 7 questions is **category-scoped querying with frequency output**. Today, every query searches the entire corpus and returns flat results. Five of seven questions (Q1, Q2, Q3, Q5, Q7) would improve substantially if the query layer could:

1. Filter by category or by graph adjacency
2. Return counts and distributions, not just fact lists
3. Group results by repo or by pattern cluster

This is primarily a query-design problem. The underlying data in `knowledge.db` already supports these operations via SQL joins — but `query_master.py` does not expose them.

### Ontology gaps

Two questions face ontology-level blockers that query improvements alone cannot solve:

- **Q5** needs solution-variant grouping and tradeoff annotations — the ontology captures individual patterns but not variant-vs-variant structure.
- **Q6** needs richer cross-repo structural data — the component ontology mixes concepts and paths without enough consistency to support structural comparison.

### Corpus gaps

No question is primarily blocked by corpus size (121 repos, 6058 facts is adequate for initial advisory use). However:

- Failure modes (296 facts) are thin in some categories — this limits Q3 for underrepresented categories.
- Pattern normalization quality varies — some categories have well-structured pattern facts, others have free-text that resists cross-repo comparison.

These are quality concerns for `github_repos-7yf` (corpus maintenance) but are not gating any question from making progress at the query-design level.

### Follow-on tracks

- **`github_repos-air` (ontology extension)**: Not currently gating. The 32 unmatched repos are a coverage concern but do not block any of the 7 questions from improving. Ontology extension should be scoped by which questions it improves, per the non-inferability constraint.
- **`github_repos-7yf` (corpus maintenance)**: Not currently gating for query-layer improvements. Relevant later for Q3 (failure-mode depth) and Q5 (pattern normalization quality).

## 4. Recommendation: Highest-Value Question to Strengthen First

### Recommended: Q3 (Failure-Mode Preflight)

**Rationale:**

1. **Highest non-inferability.** Failure modes from adjacent repos are the purest form of non-inferable advisory knowledge. An agent inspecting a target repo cannot discover what commonly goes wrong in similar repos.

2. **Lowest improvement cost.** Q3 is primarily blocked by query design, not ontology shape. Adding a category-filtered `pattern` command (or a dedicated `preflight` command) would unlock most of Q3's value with the existing 296 failure mode facts. No schema migration or data enrichment is required.

3. **Strongest research validation.** The coding-agent principles research memo identifies failure-mode awareness as one of the highest-value advisory capabilities (Principles 3 and 5). The CodeRabbit data (1.7x more bugs from AI) and the Amazon incident directly support pre-implementation failure-mode briefing.

4. **Clearest advisory output shape.** Q3 has the most natural advisory format: "Before implementing X in a Y-category repo, be aware of these common failure modes: ..." This is easier to design as a first question-shaped command than Q7's more complex typicality assessment.

5. **Builds toward Q7.** Q3 produces the foundational category-scoped query infrastructure that Q7 (the capstone question) will also need. Solving Q3 first creates reusable query primitives.

**Why not Q7 first?** Q7 is the capstone and most principle-dense question, but it faces both query-design and ontology-shape blockers (typicality signals, distribution output, norm computation). Starting with Q3 builds the query-layer infrastructure Q7 needs while delivering immediate advisory value.

**Why not Q1 first?** Q1 (adjacent-pattern discovery) is important but requires the same category-scoped query infrastructure as Q3, plus graph-adjacency joins. Q3 is a simpler first target that validates the same query primitives.

## 5. Concrete Next Steps

1. **Add a category-filtered query mode to `query_master.py`** — either extend `pattern` with a `--category` flag or add a new `preflight` command that accepts a category and returns failure modes, common patterns, and task expectations for that category. This is the single highest-leverage improvement.

2. **Add frequency/distribution output** — extend query results to include "N of M repos in this category" counts, enabling typicality signals.

3. **Close child tasks** as their findings are recorded in this artifact.

4. **Scope Q7 implementation** once Q3's query infrastructure is in place — Q7 will need the same category-scoped, distribution-aware query primitives plus typicality/norm computation on top.

5. **Defer ontology changes** for Q5 (solution-variant grouping) and Q6 (structural profiles) until query-layer improvements for Q3/Q7 are validated — those questions have higher ontology cost and lower immediate return.
