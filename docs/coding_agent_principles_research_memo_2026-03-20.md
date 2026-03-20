# Coding-Agent Problem-Solving Principles: Research Memo

Date: 2026-03-20
Related issue: `github_repos-th0`
Related documents:
- `docs/coding_session_enhancement_positioning_memo_2026-03-19.md`
- `docs/architecture_refinement_memo_2026-03-20.md`

## 1. Purpose

This memo identifies the most important problem-solving principles that effective coding agents use during real software development, then evaluates how those principles support, validate, or refine this project's 7 coding-session anchor questions.

The research draws on peer-reviewed papers, vendor publications, practitioner reports, benchmark analyses, and community discussions. Each finding is classified by evidence quality.

## 2. Research Scope

Sources consulted:

- **Peer-reviewed research**: SWE-bench variants, SWE-Search (ICLR 2025), CodeTree (NAACL 2025), LocAgent (ACL 2025), SWE-PRM (NeurIPS 2025), PALADIN, CodePRM, ACE/Agentic Context Engineering (Stanford/SambaNova 2025), RACG survey, AGENTS.md evaluation (ETH Zurich/ICML 2026)
- **Vendor publications**: Anthropic (context engineering, tool design, agent harnesses), OpenAI (agent guide), Microsoft (Code Researcher), NVIDIA (risk vectors)
- **Industry data**: CodeRabbit State of AI vs. Human Code report (470 repos), Apiiro security analysis, Amazon incident reports
- **Practitioner sources**: Stoneforge blog (hill-climbing analysis), Pragmatic Engineer newsletter, Stack Overflow blog, Hacker News discussions, Reddit (r/ClaudeAI, r/LocalLLaMA, r/cursor), Medium/Substack analyses
- **OSS documentation**: Aider repo map, SWE-agent ACI design, Devin workflow guides

## 3. Six Execution Principles

### Principle 1: Plan Before You Build

**Evidence (strong, multi-source)**

Planning significantly improves agent outcomes across multiple evaluation frameworks:

- SWE-Search (ICLR 2025): integrating Monte Carlo Tree Search yields 23% relative improvement across 5 models, with performance scaling via deeper search without larger models.
- CodeTree (NAACL 2025): breadth-first strategy exploration outperforms depth-first; separating strategy generation (Thinker) from code generation (Solver) achieves 95.1% pass@1 on HumanEval.
- AIDE: framing problem-solving as tree search in solution space wins 4x more medals than linear agents on MLE-Bench (75 Kaggle competitions).
- Practitioners consistently report that planning consumes 30-40% of tokens but produces more productive total sessions, and that output quality is determined by planning clarity, not tool choice.

**Counterpoint**: an OpenReview paper found that traditional "reason first, then code" chain-of-thought may not help as expected for code generation — the planning mechanism needs to be more structured than simple CoT. This validates the idea that planning should produce structured implementation strategy, not just free-form reasoning.

**Project implication**: the knowledge base's value is highest when consumed during planning phase, before code inspection begins.

### Principle 2: Minimize Orientation Cost

**Evidence (strong, multi-source)**

Agents waste 20-40% of their context window on codebase orientation before writing any code. This is the "hill-climbing" problem: each grep/read/glob is a step up the hill, consuming tokens at the start of the context window when reasoning is sharpest.

Key findings:

- Stoneforge analysis: 15-20 tool calls and thousands of tokens consumed before a single line of code exists; structured documentation reduces this to 1-3 tool calls.
- "Lost in the Middle" (Liu et al.): models reason most effectively at the beginning of their context window; attention degrades as context fills.
- LoCoBench-Agent: two operational modes exist — "focused executors" (10-13 turns) and "exploratory reasoners" (14-20 turns); the former is more efficient, the latter only marginally more comprehending.
- SWE-Agent ACI design: deliberately constraining the agent to 100 lines at a time improves performance by preventing context overload.

**Critical nuance from AGENTS.md evaluation (ETH Zurich, ICML 2026)**:

Context files that repeat inferable information (README content, test configuration, documentation the agent could find) actually *reduce* task success rates by 3% and increase cost by 20%+. Developer-written context files only marginally improve performance (+4%). The study recommends omitting LLM-generated context files entirely and limiting instructions to non-inferable details (specific tooling, custom build commands).

**What this means for this project**: the knowledge base should provide *non-inferable, cross-repo* knowledge — implementation priors, failure modes, pattern comparisons — not repeat what the agent can discover by reading the target repo. This is exactly the project's positioning, and the AGENTS.md paper provides strong empirical support for it.

### Principle 3: Recognize When You're Stuck

**Evidence (moderate-to-strong)**

Agents lack meta-awareness of being stuck and will persist on failing approaches indefinitely:

- SWE-PRM (IBM, NeurIPS 2025): taxonomy of trajectory inefficiencies (action looping, redundant backtracking, goal drift); training a process reward model to detect these improves resolution from 40.0% to 50.6%. Critical finding: telling the agent *what category of mistake* it is making is more effective than telling it *what specific action to take*.
- Practitioner report (Medium): documented an agent spending 47 iterations on variations of the same ALTER TABLE command — $30 in tokens on a $0.50 problem.
- Practitioner consensus (Reddit, r/ClaudeAI, 2k+ upvotes): experienced developers describe agents as "brilliant but occasionally doing something completely unhinged" — going in circles for hours before a fresh start works immediately.
- PALADIN: compositional recovery strategies (retries → tool switch → graceful termination) generalize across failure scenarios, retaining 95.2% recovery performance.

**What this means for this project**: failure-mode knowledge is among the highest-value advisory content. An agent that knows "projects like this commonly fail on X" before starting has a structural advantage in recognizing when it is hitting that failure mode during execution.

### Principle 4: Match the Prior to the Problem

**Evidence (strong, multi-source)**

LLMs have strong implementation priors — memorized patterns of how code is typically written for given problem types. These priors are the main source of both agent competence and agent failure:

- "Memorize or Generalize?" research: LLMs memorize prompt-solution pairs; their answers on variants resemble memorized solutions and fail to generalize. Mitigating memorization degrades performance on standard tasks — a direct tradeoff.
- "Beyond Code Generation" research: LLMs produce a "point solution" that hides the design space, creating anchoring bias. The implementation prior actively constrains the solution space the agent considers.
- Design pattern studies: LLMs have pattern-specific biases, performing well on training-data-common patterns and poorly on rare ones.
- Practitioner consensus: when the prior matches (standard web app, common framework patterns), agents excel; when it mismatches (unusual architectures, legacy systems, domain-specific constraints), agents confidently produce plausible-looking but wrong solutions.

**What this means for this project**: Q5 (solution-variant comparison) and Q7 (implementation-risk check) directly address this. The knowledge base can surface when the target repo's architecture is *unusual* compared to adjacent repos — exactly the situation where the agent's built-in prior is most dangerous. This is a high-value advisory capability that no other tool provides.

### Principle 5: Assess Blast Radius Before Acting

**Evidence (moderate, emerging)**

Risk assessment is the largest gap in current agent architectures. No major coding agent implements pre-change risk scoring:

- Amazon incident: AI agent deleted a production environment to "fix" a config error — 6-hour outage, 6.3M lost orders — leading to a 90-day code safety reset.
- CodeRabbit data (470 repos): AI creates 1.7x more bugs than humans, 75% more logic/correctness errors, 1.5-2x more security issues, 8x more excessive I/O.
- Apiiro: AI accelerates creation but concentrates change, overloading code review and expanding blast radius per merge.
- NVIDIA: every permission granted is a ceiling on potential blast radius; the autonomy-functionality tradeoff is fundamental.

**What this means for this project**: Q3 (failure-mode preflight) and Q7 (implementation-risk check) address the advisory side of this gap. The knowledge base cannot enforce runtime guardrails, but it can prime the agent with "repos like this commonly experience X when changing Y" — a pre-implementation risk brief.

### Principle 6: Prefer Structured, Non-Inferable Knowledge Over Volume

**Evidence (strong, multi-source, directly relevant)**

The quality of context matters more than quantity, and structured context outperforms raw retrieval for advisory tasks — but only when it provides information the agent cannot derive itself:

- ACE (Stanford, 2025): treating contexts as evolving playbooks that accumulate strategies produces +10.6% on agent benchmarks; brevity bias and context collapse are real problems in naive approaches.
- AGENTS.md evaluation (ETH Zurich): inferable context files reduce performance; only non-inferable details help. This is the single most important empirical finding for this project.
- Aider's repo map: PageRank-based structural summaries that surface the most-referenced identifiers help agents respect existing abstractions — structured knowledge outperforming raw file access.
- LocAgent (ACL 2025): graph-based code representation dramatically outperforms flat search (92.7% file-level accuracy with an 86% cost reduction).
- Practitioner consensus: "the implementation prior helps more than it hurts for standard tasks" (minimaxir, Feb 2026) but agents need to know when their default pattern doesn't apply.

**What this means for this project**: the project's core architecture — canonical YAML, normalized facts, compiled SQLite read model, deterministic query layer — is the right shape for this principle. The knowledge base provides what individual repo inspection cannot: cross-repo patterns, failure-mode norms, solution-variant distributions, and typicality assessments. These are genuinely non-inferable from the target codebase alone.

## 4. Principle-to-Question Mapping

| Principle | Q1 Patterns | Q2 Components | Q3 Failures | Q4 References | Q5 Variants | Q6 Inspection | Q7 Risk |
|-----------|:-----------:|:-------------:|:-----------:|:-------------:|:-----------:|:-------------:|:-------:|
| 1. Plan Before You Build | **●** | ○ | ○ | ○ | **●** | ○ | **●** |
| 2. Minimize Orientation Cost | ○ | **●** | ○ | **●** | ○ | **●** | ○ |
| 3. Recognize When Stuck | ○ | ○ | **●** | ○ | ○ | ○ | **●** |
| 4. Match Prior to Problem | **●** | ○ | ○ | ○ | **●** | ○ | **●** |
| 5. Assess Blast Radius | ○ | ○ | **●** | ○ | ○ | ○ | **●** |
| 6. Structured Non-Inferable Knowledge | **●** | **●** | **●** | **●** | **●** | **●** | **●** |

**● = primary support; ○ = secondary or indirect**

### Reading the map

- **Q7 (Implementation-Risk Check)** is the most principle-dense question, supported by 5 of 6 principles. This validates its position as the most decision-support-oriented question in the set.
- **Q1 (Adjacent-Pattern Discovery)** and **Q5 (Solution-Variant Comparison)** are tightly coupled through Principles 1 and 4 — both address the prior-matching problem from different angles.
- **Q3 (Failure-Mode Preflight)** bridges Principles 3 and 5 — it is the pre-implementation complement to runtime error detection.
- **Q6 (Inspection-Priority Guidance)** and **Q2 (Likely-Component Discovery)** are most supported by Principle 2 (orientation cost) — they directly reduce the hill-climbing problem.
- **Q4 (Reference-Repo Selection)** has the narrowest principle support but high practical value — it is the search-space reduction mechanism.
- **Principle 6** (structured non-inferable knowledge) underpins all 7 questions. It is the meta-principle for the entire project.

## 5. Recommendation on the 7 Questions

### Verdict: Tighten, do not expand.

The research validates the 7 questions as well-chosen. They cover the space that matters, and their gaps are deliberate (intentionally excluding memory, code retrieval, and codebase summarization).

**Tightening recommendations:**

1. **Q7 should be emphasized as the capstone question.** It is the most principle-dense, the most decision-support-oriented, and the most unique to this project. It should be the question the system answers *best*, not just one of seven.

2. **Q1 and Q5 should be explicitly linked.** They address the same underlying need (prior calibration) from different angles. In query design, Q1 results should inform Q5 answers and vice versa.

3. **Q3 should distinguish between failure modes the agent can encounter during *implementation* vs. failure modes in the *resulting system*.** The research shows both are valuable but serve different advisory moments. The current phrasing ("when projects like this implement `<feature>`") already handles this well — tightening means ensuring the underlying data captures both categories distinctly.

4. **Q6 should incorporate the AGENTS.md finding.** Inspection guidance should explicitly focus on *non-obvious* inspection targets — the files and patterns that an agent would *not* discover in its first 3 grep calls. This sharpens Q6 from "what to inspect" to "what to inspect that you wouldn't find on your own."

**What should NOT be added:**

- A "summarize this codebase" question — still the domain of other tools.
- A "remember what happened" question — still memory-system territory.
- A "what operational tasks come with this" question — the research does not elevate this above the current seven. It could be folded into Q3 if needed, but the seven are already at the right granularity.
- A "what follow-on changes are likely" question — this requires code-specific impact analysis that the current data supports only indirectly. Adding it would create a question the system cannot answer well, violating the "optimize for advisory usefulness" principle.

## 6. Concrete Phase 5 Implications

### 6.1 Query-layer design should be question-shaped, not table-shaped

The research strongly supports the architecture refinement memo's recommendation: the query layer is the product surface. Question-shaped query commands (not raw SQL or table browsing) should be the primary agent interface.

Specifically:
- Each of the 7 questions should map to one or more query commands
- Query output should be advisory (structured recommendations with confidence) not raw (tables of facts)
- The AGENTS.md evaluation shows that less is more — query results should be concise, non-inferable, and targeted

### 6.2 Ontology changes should serve prior calibration

The most important ontology capability is supporting Principle 4 (match prior to problem):
- The system needs enough pattern data to distinguish *typical* from *atypical* implementations
- Failure-mode data must be rich enough to support pre-implementation risk briefs
- Solution-variant data must capture enough alternatives to prevent anchoring on one approach

This means ontology growth should prioritize:
- Diversity of solution approaches per problem type (supports Q5)
- Failure-mode coverage per archetype (supports Q3, Q7)
- Explicit typicality/atypicality markers (supports Q7)

### 6.3 The non-inferability criterion is now an architectural constraint

The AGENTS.md evaluation provides direct empirical support for a design constraint:

> The knowledge base must provide information that cannot be derived from inspecting the target repository alone.

This means:
- Cross-repo pattern distributions (how many repos use approach X) — **non-inferable** ✓
- Common failure modes for this category of project — **non-inferable** ✓
- Which adjacent repos best illustrate an approach — **non-inferable** ✓
- The target repo's file structure and naming — **inferable, do not include** ✗
- Standard build/test commands — **inferable, do not include** ✗

This constraint should be stated explicitly in the Phase 5 acceptance criteria and used to evaluate proposed schema or query changes.

### 6.4 Small-model value proposition is validated

The research confirms that structured context is disproportionately valuable for smaller models:
- KV cache quantization causes local models to degrade at 30k+ tokens (Reddit, r/LocalLLaMA, 235 upvotes, confirmed by multiple practitioners)
- Smaller models struggle specifically with codebase exploration and tool use (SWE-bench Pro analysis)
- Minimizing orientation cost (Principle 2) is more critical for models with limited context and weaker search strategies
- The implementation prior (Principle 4) is narrower in smaller models, making external pattern knowledge more valuable

This validates the positioning memo's claim that the project's value increases as the target model gets smaller.

### 6.5 Advisory output format matters

The research suggests the system should produce:
- **Ranked alternatives, not single answers** (Principle 4, Q5): "Here are 3 approaches used by adjacent repos, with tradeoffs" rather than "Use approach X"
- **Typicality assessments, not just patterns** (Principle 4, Q7): "Your planned approach is unusual — 80% of adjacent repos use Y instead" rather than "Adjacent repos use Y"
- **Non-obvious inspection targets** (Principle 2, Q6): "You would not find this by grepping — inspect Z because adjacent repos commonly have a hidden dependency there"
- **Risk signals, not risk scores** (Principle 5, Q3/Q7): "Projects like this commonly fail on X when implementing Y — check for Z before proceeding"

## 7. Evidence Quality Summary

| Category | Count | Confidence |
|----------|-------|------------|
| Peer-reviewed papers (ICLR, NAACL, NeurIPS, ACL, ICML, ACM) | 14 | High |
| Vendor publications (Anthropic, OpenAI, Microsoft, NVIDIA) | 6 | High (potential bias noted) |
| Industry data reports (CodeRabbit, Apiiro) | 2 | Moderate-High |
| Practitioner reports with evidence (blogs, newsletters) | 8 | Moderate |
| Community consensus (Reddit, HN, high-engagement threads) | 6 | Moderate (signal in aggregate) |
| Practitioner opinion/speculation | 5 | Low-Moderate |

The strongest findings — planning improves outcomes, orientation cost is real, inferable context hurts, agents lack risk models — are supported by multiple independent sources at high confidence. The weakest finding is the specific blast-radius data (Amazon incident sourcing not independently verified).

## 8. What This Memo Does Not Cover

- Specific query_master.py command mappings (that is the follow-on task from the positioning memo)
- Schema/ontology changes needed (that is Phase 5 implementation work)
- MCP/skill packaging design (deferred per architecture refinement memo)
- Detailed benchmark methodology or reproduction steps
- Agent memory systems, session continuity, or chat-transcript management (out of scope per guardrails)

## 9. Supplementary Findings (Background Research Agents)

Four parallel research agents produced extended findings that reinforce and deepen the memo's core conclusions. Key supplementary material:

### 9.1 Competitive landscape confirms the gap

A survey of every major knowledge-augmented coding agent system (Aider, Cursor, Cody, Continue, Codex CLI) reveals that **no system provides cross-repo implementation-prior knowledge**. All focus exclusively on understanding the current repo's structure and content.

The closest systems:
- **Moderne/Moddy**: genuine multi-repo work at scale using Lossless Semantic Trees + LLM-generated knowledge graphs, but focused on migration/modernization rather than advisory
- **LogicLens** (Jan 2026): semantic multi-repo code graph enabling natural-language queries across repos — architecturally relevant but not advisory-oriented
- **Augment Code**: claims 400K-file cross-repo indexing with "architectural maps," but focused on call-graph tracing, not pattern comparison

Assessment from the research: *"'Repos like yours' pattern knowledge: Nonexistent as a product — Complete gap — nobody is doing this."* This is the strongest external validation of the project's positioning.

### 9.2 Benchmark inflation and the feature gap

SWE-bench scores are 36-54% inflated due to data leakage from training corpora (5 independent studies). More critically, FeatureBench (ICLR 2026) shows Claude 4.5 Opus drops from 74.4% on bug-fix tasks to 11.0% on feature-level tasks — revealing a gap between narrow bug-fix capability and broader implementation judgment. The project's component-discovery and pattern-comparison questions (Q1, Q2, Q5) directly address this gap.

### 9.3 The 80% Problem and perception gap

Addy Osmani's widely-cited analysis describes the central practitioner experience: agents rapidly produce 80% of code, but the remaining 20% (production readiness, edge cases, architectural coherence) requires exponentially more effort. The METR study found experienced developers were 19% *slower* with AI tools while estimating they were 20% *faster* — a 39-point perception gap. This validates the project's emphasis on advisory front-loading: structured priors before implementation reduce the cost of the last 20%.

### 9.4 Cross-project knowledge demand is implicit

Practitioner communities show the *thinnest signal* for explicit cross-project knowledge requests — practitioners want it but don't articulate it that way. When they complain about agents not following conventions, reinventing patterns, or failing to use existing libraries, they are expressing demand for implementation priors. The project fills a need that users cannot yet name.

### 9.5 Structured context evidence strengthens

SWE-ContextBench (Feb 2026) found that correctly selected summarized experience improves resolution accuracy and reduces cost, *especially on harder tasks* — but unfiltered or incorrectly selected experience provides limited or negative benefit. This directly supports the non-inferability criterion: the system must be selective about what it surfaces.

A codified-context infrastructure study found a 108K-line C# system required 25K lines of specifications, prompts, and rules — a 24.2% knowledge-to-code ratio. Three tiers emerged: always-loaded constitution, specialist agents invoked per task, and cold-memory knowledge base queried on demand via MCP. This architecture maps closely to the project's canonical YAML → compiled SQLite → query-layer design.

## 10. Bottom Line

The 7 coding-session anchor questions are well-validated by the research. They cover the space that matters and exclude the space that doesn't. No competing system occupies this niche.

The strongest insight from this research is the **non-inferability criterion**: the system's value comes precisely from providing knowledge that cannot be obtained by inspecting the target repository. Cross-repo patterns, failure-mode distributions, solution-variant comparisons, and typicality assessments are non-inferable. Repository structure, README content, and standard tooling are inferable and should not be the system's concern.

The six execution principles distilled here — plan before building, minimize orientation cost, recognize when stuck, match prior to problem, assess blast radius, prefer structured non-inferable knowledge — provide a principled framework for evaluating whether future changes improve the system's advisory value.

Phase 5 should treat Q7 (implementation-risk check) as the capstone question, the non-inferability criterion as an architectural constraint, and the advisory output format as a product design concern.
