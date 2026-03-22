# AI Code Review with Claude: Research Report

**Date:** 2026-03-22 (Round 1), updated 2026-03-22 (Round 2)
**Purpose:** Reference for building a code review skill for agent-generated code — orchestration scripts, modules, APIs, and any code agents churn on during personal project work. Intended to run after each agent pass on critical work.
**Sources (Round 1):** O'Reilly, official Claude docs, practitioner blogs, HackerNews threads, Reddit (r/linux, r/ClaudeAI, r/SoftwareEngineering, r/ExperiencedDevs).
**Sources (Round 2):** Reddit (r/ExperiencedDevs, r/ClaudeAI, r/selfhosted, r/LocalLLaMA) — broader scope, real-world bug taxonomies, iterative workflow patterns.

---

## 1. Executive Summary

AI-assisted code review is most effective when treated as a **pointer, not a judge**: the model finds issues, humans decide what to act on. The research consistently shows that diff-only input, exhaustive checklists, and self-review (same context window that wrote the code) are the three primary failure modes. For agent orchestration scripts specifically, the additional challenge is that the model has no architectural context — what the script does, what calls it, what its known failure modes are — and will produce low-signal findings without it.

The skill gap this research identifies: **no existing guide covers code review tuned for long autonomous-agent scripts**. Existing material targets PR diffs in team workflows. The patterns below extend those to single-file, high-complexity orchestration code reviewed by a fresh subagent.

---

## 2. Sources Consulted

| Source | Type | Key Contribution |
|--------|------|-----------------|
| O'Reilly: *Auto-Reviewing Claude's Code* | Deep article | Context window intoxication, semantic check taxonomy |
| Claude Code Docs: *Code Review* | Official | Canonical REVIEW.md structure, always/skip patterns |
| josecasanova.com: *Claude Code Review Prompt* | Practitioner blog | Minimal severity-tagged prompt template |
| eesel.ai: *Claude Code Best Practices* | Blog | Role + domain context pattern |
| HN thread 45310529 | Discussion | Full file vs. diff debate, severity threshold advice |
| HN thread 46346391 | Discussion | "10 seconds" workflow, parallel reviewer instances |
| r/linux: Sashiko thread | Reddit | Real-world validation from Linux kernel AI review |
| r/ClaudeAI: Vibe-coded projects fail | Reddit | Context-constraint problem for long scripts |
| r/SoftwareEngineering: Code quality thread | Reddit | Team enforcement patterns, bite-size scoping |

---

## 3. Primary Failure Modes to Avoid

### 3.1 Self-Review (Context Window Intoxication)

The O'Reilly piece is the most important finding: **do not ask the same agent that wrote the code to review it**. As the context window fills with accumulated task work, the model increasingly ignores its own system prompt and becomes "intoxicated" by its prior decisions. It will validate its own work even when wrong.

**Remedy:** Always use a separate subagent in a fresh context window for review. Pass only: the file(s) + a review prompt + domain context. Nothing else.

### 3.2 Diff-Only Input

HN consensus (multiple top-voted comments): reviewing only the diff is the worst possible input. The model confuses unchanged context with new code, misses interactions between changed and unchanged sections, and cannot evaluate whether changed logic is correct relative to surrounding code.

**Remedy:** Always pass the **full file(s)** touched by the change, with the diff optionally annotated separately. For long scripts, the full file is the unit.

### 3.3 Exhaustive Checklists

Verbose review prompts that ask the model to check everything produce a 1-in-20 useful finding rate (HN, multiple commenters). The model pads to fill the checklist.

**Remedy:** Ask for top 3–5 findings only, severity-tagged, skipping what linters and formatters already catch.

### 3.4 Architecture-Level Asks

The model will not reliably find "this whole design is wrong." It is best at line-level and function-level correctness. Asking it to evaluate architecture produces confident-sounding but unreliable output.

**Remedy:** Constrain the scope explicitly. Architecture review requires human judgment or a specialized structured approach (not a single-pass review prompt).

---

## 4. Prompt Design

### 4.1 Minimal, Severity-Focused Prompt (baseline)

```
Analyze this code for critical issues only:
- Potential bugs and incorrect logic
- Silent failures (defaults assigned instead of raising errors)
- Security issues (shell injection, untrusted input, hardcoded secrets)
- Edge cases likely to break in production

List findings as short bullets tagged [CRITICAL] / [WARN] / [NIT].
Skip formatting, style, and test coverage unless asked.
Approve with ✅ if nothing critical found.
```

This is the minimum viable prompt. It works. Everything else is tuning.

### 4.2 Role + Domain Context Header

Prepend a role statement tuned to the script's domain:

```
You are a senior Python developer reviewing an orchestration script.
Pay particular attention to: async logic, error propagation, silent
swallowing of exceptions, and incorrect default assignments.
```

For agent-specific scripts, extend this:
```
This script coordinates autonomous agents that write and run code.
Failure modes include: partial completion being treated as success,
missing retry logic, and exceptions silently continuing the loop.
```

### 4.3 Architectural Context Block (critical for long scripts)

The vibe-coded projects Reddit thread surfaced a key problem: reviewing a "chapter in an existing series" requires immense context that the model won't infer from the code alone. You must provide it.

Prepend a structured context block:

```
## Script Context
- Purpose: [what this script does in one sentence]
- Called by: [what invokes it — CLI, scheduler, parent agent]
- Calls out to: [external systems, APIs, subprocesses it touches]
- Known failure modes: [what has broken before or is at risk]
- What "success" means: [how the script signals completion]
```

This is the single highest-leverage addition over generic review prompts for orchestration scripts.

### 4.4 Severity Threshold

Ask for a bounded output:
```
Return the top 5 findings maximum. If fewer than 5 real issues exist, return fewer.
Do not pad.
```

---

## 5. What to Flag: Semantic Checks for Agent Scripts

These are the categories linters won't catch. Ordered by value for orchestration scripts:

| Category | What to look for |
|----------|-----------------|
| **Silent defaults** | `None`, `[]`, `{}`, or fallback values assigned instead of raising on missing config/data |
| **Missing error propagation** | `except` blocks that log but don't re-raise — causes silent partial failure in a multi-step pipeline |
| **Wrong failure signal** | Script exits `0` or returns without indicating partial failure; caller treats it as success |
| **Logic in wrong layer** | Orchestration script making decisions that belong in a downstream component |
| **Shell injection surface** | `subprocess` with `shell=True` and any variable input; `os.system()` with constructed strings |
| **Domain name leakage** | `helper`, `utils`, `manager`, `process_data` — names that obscure what the code actually does |
| **Swallowed retries** | Retry loops that catch exceptions and continue without limit or alerting |
| **State mutation without guard** | Shared mutable state modified across async calls without locks or atomic operations |

The top four are the highest-value catches for Claude/Codex-generated orchestration code specifically. The O'Reilly piece identifies silent defaults and missing error propagation as the most common AI-generated bugs that survive linting.

---

## 6. Reviewer Architecture for a Skill

### 6.1 Pattern

```
Main agent writes/modifies script
        ↓
Skill triggers dedicated reviewer subagent:
  - Input: full file(s) + review prompt + domain context block
  - Fresh context window (no inherited task state)
        ↓
Reviewer returns tagged findings
        ↓
Main agent decides which to address
```

### 6.2 Why Fresh Context is Non-Negotiable

Two independent sources converge on this:
1. O'Reilly: context intoxication from accumulated task work.
2. r/SoftwareEngineering: a reviewer inheriting disorganized context produces degraded output because messy context trashes the model's working memory.

The skill must spawn a subagent, not ask the current agent to self-review.

### 6.3 Parallel Reviewer Instances (high-stakes option)

For critical scripts, run 2–3 reviewer subagents with the same prompt in parallel (different random seeds surface different issues). Merge findings in a fresh context. This is the "belt and suspenders" variant — overkill for routine review, appropriate for pre-deployment checks on complex scripts.

---

## 7. What to Put in the Skill's System Prompt / REVIEW.md

Based on the official Claude docs pattern and practitioner usage:

```markdown
## Always flag
- `except:` or `except Exception:` without re-raise
- Any subprocess call with shell=True and variable input
- Return/exit 0 without indicating partial failure
- Assignment of None/[]/fallback where raise would be correct
- TODO/FIXME in non-obvious code paths

## Domain context for these scripts
- Scripts coordinate autonomous agents
- Partial completion must be surfaced as failure, not success
- Check that all exception paths either raise or return a failure signal

## Skip
- Docstring completeness
- Type annotation coverage
- Formatting (handled by linter)
- Style consistency (handled by formatter)
- Test coverage

## Output format
- Short bullets, tagged [CRITICAL] / [WARN] / [NIT]
- Max 5 findings
- ✅ if nothing critical found
- No preamble, no summary
```

---

## 8. Scope Constraints

### 8.1 Per-File, Not Per-Script-as-Monolith

From r/SoftwareEngineering (KOM_Unchained):
> Enforce bite-size updates: 1-2 files at a time. No yolo across 10 files.

For long scripts: if the script is a single file, that's the unit. If the script imports shared utilities that are relevant to the issues, include those too, but be explicit about which is primary. Don't dump an entire codebase.

### 8.2 File Size Limits

No hard number in the research, but HN commenters noted that beyond ~500–800 lines, the model's attention on specific sections degrades. For scripts longer than this, consider a two-pass approach:
1. First pass: structure and control flow review (skip implementation details).
2. Second pass: targeted review of specific functions flagged by the first pass.

---

## 9. Security Note: Prompt Injection in GH Actions

A r/programming post (PromptPwnd) documented a real vulnerability class: when AI review is integrated into GitHub Actions and reviews PR content that includes user-controlled text (issue descriptions, PR body, commit messages), that content can inject into the review prompt.

**If the skill ever operates on PRs:** sanitize all user-controlled input before it enters the review prompt. Do not pass raw PR description or issue text to the reviewer without stripping or quoting it.

For the current use case (reviewing agent-generated scripts, not user PRs), this is lower risk — but worth noting for future expansion.

---

## 10. Validation from Production Use

Two real-world deployments corroborate the approach:

**Google Sashiko (Linux kernel, 2026):** Google engineers deployed an agentic AI code review system for the Linux kernel. Community reception was positive — the framing "point me to it, I'll fix it" is exactly how kernel maintainers described using it. A similar AI review bot had been running on the `net-next` mailing list for months before this announcement, also with positive contributor feedback.

**AI self-learning loop (r/ArtificialInteligence):** A practitioner ran a coding agent in a self-improving loop for 4 hours, 119 commits, 14k lines of Python→TypeScript translation with zero build errors. The key was extracting "skills" between runs — not review per se, but the same principle: fresh context + structured criteria per iteration.

---

## 11. The Gap This Skill Should Fill

Existing guides target:
- PR diff review in team workflows
- Catching style/formatting issues (already handled by linters)
- General correctness for web/app code

**No existing guide covers:**
- Full-file review of long orchestration scripts
- Agent-generated code with agent-specific failure modes (silent partial completion, swallowed retries, wrong error signals)
- Structured architectural context injection to compensate for the model's lack of repo knowledge
- Subagent-based review to avoid self-review bias in an agentic workflow

The skill should own this niche.

---

## 12. Recommended Skill Design (sketch)

The skill should:

1. **Accept:** path to script file(s) + optional domain context override
2. **Read** the full file(s) into a structured prompt
3. **Inject** a standard architectural context block (with defaults the user can override)
4. **Spawn** a fresh reviewer subagent (not self-review)
5. **Return** tagged findings — [CRITICAL] / [WARN] / [NIT] — with no preamble
6. **Cap** output at 5 findings unless `--verbose` flag is passed

Optional extensions:
- `--parallel N`: run N reviewers in parallel, merge findings
- `--focus <category>`: restrict to one check category (e.g., `error-propagation`, `security`, `silent-defaults`)
- `--context <file>`: load architectural context from a separate YAML/MD file rather than prompting

The skill should **not** attempt to fix issues — it finds and tags. Fixing is a separate step the calling agent can invoke if needed.

---

## 13. Reference Prompt Templates

### Minimal (copy-paste ready)

```
You are a senior Python developer reviewing an orchestration script.

## Script context
- Purpose: {PURPOSE}
- Called by: {CALLER}
- External systems: {EXTERNAL}
- Known failure risks: {RISKS}

## Review criteria
Flag only:
- Silent defaults where raise is correct
- Exception handling that swallows failures without re-raising
- Shell injection surfaces
- Wrong success signal (exits 0 on partial failure)
- Logic clearly in the wrong layer

Output: bullets tagged [CRITICAL] / [WARN] / [NIT]. Max 5 findings.
✅ if nothing critical. No preamble.

## Script
{FULL_FILE_CONTENTS}
```

### Parallel merge prompt (for fresh merge-context subagent)

```
You are merging findings from {N} independent reviewers of the same script.

De-duplicate findings that are substantively identical.
For conflicting severity ratings, use the higher severity.
Return the merged list, still tagged [CRITICAL] / [WARN] / [NIT], max 7 findings.
No preamble.

## Reviewer outputs
{REVIEWER_1_OUTPUT}
---
{REVIEWER_2_OUTPUT}
```

---

## 14. Round 2 Findings: Broader Scope (Personal Agent Workflows)

*These findings extend the scope from orchestration scripts specifically to any code agents generate during personal project work. The use case: running the review skill after each agent pass on critical files.*

### 14.1 Concrete AI Code Anti-Patterns (From Practitioners)

The r/ExperiencedDevs "AI slop cleanup" thread (4,250 upvotes, 8 years freelance SE doing AI-code remediation) and r/softwaredevelopment surfaced a recurring taxonomy of what goes wrong. These go beyond what linters catch:

| Anti-pattern | Description | Catch signal |
|---|---|---|
| **Timing hacks** | `setTimeout` / `sleep` used to "fix" race conditions instead of proper synchronization | Any `setTimeout` with a magic delay, any `sleep()` in async code |
| **Dead file bloat** | AI adds files, imports, helpers that end up unused — one case: 90+ files removed out of 100 | Unused imports, unreachable functions, files not referenced anywhere |
| **MVP-quality error handling** | Works under normal load, fails silently or catastrophically at scale or edge cases | `except: pass`, bare `try/except`, missing error return paths |
| **Over-commenting** | AI generates verbose comments that either state the obvious or drift out of sync with the code | Comments longer than the code they describe; comments that contradict the code |
| **Average-quality defaults** | AI is trained on the average of public code, which is bad-to-mediocre — it will produce average patterns unless steered | Generic variable names (`data`, `result`, `temp`), copy-paste patterns, boilerplate that should be refactored |
| **Missing tests** | AI rarely proactively adds tests; code without them becomes unmaintainable as agents continue modifying it | No test file, no assertions, untested edge cases in core logic |
| **Auth as afterthought** | AI adds features first, security second (or never) — auth endpoints unprotected, credentials accessible without login | Unauthenticated endpoints, credentials in response payloads, missing auth middleware |
| **Feature velocity smell** | Rapid AI-driven feature addition without hardening = accumulating risk. Rate of new files/features is a quality signal itself | Sudden large additions that don't include corresponding guard code or tests |

The `setTimeout` pattern deserves special emphasis (370 upvotes on that specific comment):
> "The number of times ChatGPT has suggested `setTimeout` unironically to fix a legitimate issue makes me terrified of what I'm going to find in codebases over the coming years."

This is an **AI-specific tell** — a human developer would rarely reach for a timing hack; the AI does it because it's common in training data.

### 14.2 Security: What Vibe-Coded Projects Actually Get Wrong

The Huntarr case (r/selfhosted, 9,469 upvotes) is the most detailed real-world security audit of a vibe-coded project available. Specific vulnerabilities found in v9.4.2:

- **Authentication bypass**: sensitive endpoints had zero authentication
- **Credential exposure**: API keys for connected apps (Sonarr, Radarr, Prowlarr) returned without auth
- **No input validation at API boundaries**: user-controlled input passed directly to internal logic
- **Scope creep without hardening**: AI kept adding features, each increasing attack surface without adding guards

The pattern: AI builds happy-path functionality confidently. It doesn't model "what happens if an unauthenticated user calls this?" because that requires adversarial thinking, not pattern completion.

**Review implication**: For any file that exposes an endpoint, handles a credential, or accepts external input — add an explicit security pass. The general review prompt won't reliably catch these; they need a dedicated security-focused reviewer invocation.

One comment that captures the systemic risk:
> "The features getting added and the rate they are going in makes this obviously an AI project so it's extremely risky."

And the darkly funny coda:
> "The GitHub is gone now... They probably asked the LLM to fix all security issues and it deleted the whole thing."

### 14.3 Iterative Review: Per-Pass Workflow

From the "100% AI-generated code — 12 lessons" post (r/ClaudeAI, 2,293 upvotes) and its comment thread, the patterns that survived real project completion:

**Lesson 4 (original post):** Break down complex problems — one problem at a time. Claude is "almost bulletproof" at small, focused code; it degrades on multi-concern blobs.

**Review implication:** When an agent pass touches multiple concerns (adds a feature *and* refactors a helper *and* updates config), split the review. A single prompt reviewing all three changes will pad. Issue one review per coherent change.

**Comment (100 upvotes, djc0):**
> "Create a handover doc template and have the AI fill it out at the end of each session so it can pick up the next task in a new chat with all the info it needs."

This is the session-boundary equivalent of the architectural context block. For the review skill: if there's a handover doc or AGENTS.md-style context file in the project, pass it to the reviewer as the "Script Context" block. It already contains the purpose, failure modes, and what's in progress.

**Comment (independent):**
> "Have a 2nd AI/eyes look at your code and analyze for exploits and inconsistency."

This is independent confirmation of the fresh-subagent pattern — practitioners are arriving at it naturally even without knowing the O'Reilly framing.

**Comment (hei8ht):**
> "My greatest regret is not writing tests. Now whenever I change something or cursor changes something, something always breaks and the project has become too big for manual testing."

**Review implication:** Include a test-coverage check as an optional pass. Not "are tests comprehensive?" (that's slow and noisy) but "does this function/module have *any* test?" Zero tests on core logic is a `[WARN]`, zero tests on anything that touches external state is a `[CRITICAL]`.

### 14.4 Comments as an AI-Generated Code Signal

From r/ExperiencedDevs (pavlik_enemy, 147 upvotes):
> "Given that very few people comment the code, if there are comments at all it's AI generated."

This is a subtle but useful heuristic. AI over-comments. The review skill can use this as a secondary signal: if a section is heavily commented but the comments are generic or restate the obvious, that's where AI-generated logic is likely to be lurking — and where the model was probably uncertain about what it was writing.

A comment that explains *what* the code does (not *why*) is a smell. A comment that says `# Initialize the connection` above `conn = db.connect()` added nothing and signals the author wasn't reasoning about the code.

**Review check:** Flag comments that restate the code literally without adding intent or context.

### 14.5 What Experienced Devs Look For When Auditing AI Code

Synthesized from the slop cleanup thread — what the freelancers doing remediation actually check first:

1. **Does it work under non-happy-path conditions?** Test with missing data, unexpected types, high load.
2. **Is there unnecessary code?** AI adds bloat. Unused imports, dead branches, files that are never called.
3. **Is there a real error strategy or just logging?** `console.log(err)` / `logger.error(e)` without re-raise or user feedback is not error handling.
4. **Is anything hardcoded that should be configurable?** URLs, timeouts, limits.
5. **Are there timing assumptions?** Sequential code that assumes a previous async operation has completed.
6. **What happens when an external service is unavailable?** If the answer is "the whole thing crashes," that's unhandled.

### 14.6 Revised Scope for the Skill

Based on Round 2 findings, the skill should handle **four distinct review modes**, selectable by the user:

| Mode | Focus | Prompt variant |
|---|---|---|
| `general` | Bugs, silent failures, logic errors, dead code | Base prompt from Section 4.1 |
| `security` | Auth, credential exposure, injection surfaces, input validation | Security-specific reviewer with adversarial framing |
| `agent-output` | Patterns specific to AI-generated code: timing hacks, bloat, over-commenting, missing tests | Extended semantic checks from Section 14.1 |
| `iterative` | Lightweight pass for each agent turn on a file in active development | Stripped-down prompt, max 3 findings, focus on regressions only |

The `iterative` mode is the key addition for the personal project use case. When an agent is churning on a file across multiple passes, you don't want a full audit each time — you want a quick regression check: "did this pass introduce anything that wasn't there before?" That means the prompt should be oriented around *change detection*, not comprehensive review.

**Iterative mode prompt sketch:**
```
You are reviewing code after a single agent edit pass.
Focus only on: new bugs, new silent failures, new timing assumptions.
Do NOT re-flag issues that existed before this change.
If nothing new was introduced, respond: ✅ No regressions detected.
Max 3 findings. [CRITICAL] / [WARN] only — no NITs.

## What changed this pass
{DESCRIPTION_OF_WHAT_AGENT_DID}

## Current file
{FULL_FILE_CONTENTS}
```

Note: for iterative mode to work well, the skill needs to know *what the agent just did* — a one-line description. The calling agent should pass this in.

### 14.7 The "AI Trains on Average Code" Problem

From r/ExperiencedDevs (F0tNMC, 30 years experience):
> "AI is trained on all the publicly available code. Get the average and that's what AI uses to generate code. Most code is bad to mediocre, less than 10% is good. It's absolutely no surprise that AI produces almost all bad to mediocre code in large volumes."

This is the foundational reason why review is necessary — not because the AI makes random mistakes, but because it *reliably produces the median* of what it was trained on, which is not good code. Review is the mechanism for pulling the output above median.

The implication for prompt design: **don't ask the reviewer to evaluate against an implicit standard**. State the standard explicitly in the system prompt. "Prefer explicit error types over generic fallbacks" is more useful than "check code quality."

---

## 15. Updated Semantic Check List (Combined Rounds 1 + 2)

Full taxonomy for the skill's reviewer prompt, ordered by catch-value for agent-generated personal project code:

| Priority | Category | What to look for |
|---|---|---|
| 1 | **Silent defaults** | `None`/`[]`/`{}`/fallback assigned where `raise` is correct |
| 2 | **Missing error propagation** | `except` blocks that log but don't re-raise |
| 3 | **Auth missing** | Endpoints or functions that should require auth but don't |
| 4 | **Timing hacks** | `setTimeout`/`sleep` used to work around async issues |
| 5 | **Wrong success signal** | Returns/exits 0 on partial failure |
| 6 | **Credential exposure** | Secrets, tokens, API keys in responses or logs |
| 7 | **Shell injection** | `subprocess(shell=True)` with variable input, `os.system()` with constructed strings |
| 8 | **Dead code / bloat** | Unused imports, unreferenced files, dead branches |
| 9 | **Hardcoded values** | URLs, timeouts, limits that should be config |
| 10 | **No test coverage** | Core logic or external-state functions with zero tests |
| 11 | **Misleading comments** | Comments that restate code literally, contradict code, or are clearly AI-generated filler |
| 12 | **Logic in wrong layer** | Orchestration making decisions that belong downstream |

Items 1–7 are `[CRITICAL]` territory. Items 8–12 are `[WARN]` or `[NIT]` depending on context.

---

---

## 16. Round 3 Findings: Workflow Design, Hooks, and Official Tooling

*Sources: Boris's full Claude Code setup Q&A, 6-month hardcore use tips post, 28+ official plugins thread, MorroHsu CLI agents Part 2, $417 word game post.*

### 16.1 Don't Auto-Trigger Review on Every File Write

From the 6-month tips post, commenter lucianw (high upvotes):
> "I disagree about running the formatter as a PostToolUse hook. Every time it changes a file on disk, Claude gets a `<system-reminder>` on its next UserPrompt listing all lines changed. These are useless tokens. Remember every token in context costs you — both in price and attention."

This is a direct implementation constraint for the review skill. **Do not wire it as a PostToolUse hook that fires on every file write.** The cost — both token and attention — is too high for routine use.

**Correct trigger pattern:** Explicit invocation by the calling agent or user, not automatic. The agent should call the skill after completing a meaningful unit of work, not after every individual file edit.

Corollary from the Boris Q&A (DCOperator, 229 upvotes):
> "Load up Claude Code, do nothing but type /context and you see you only have 137k tokens before the dreaded auto-compact. If you stuff everything into CLAUDE.md, you have zero tokens right after loading."

The review skill's system prompt and context injection must be **lean**. A bloated reviewer prompt eats from the same budget as the work being reviewed. The architectural context block should be the file contents + a tight prompt, not an elaborate knowledge dump.

### 16.2 Official Code Review Plugins Exist — Know the Difference

From the plugins thread, commenter wewerecreaturres:
> "`pr-review-toolkit` seems to be better than `code-review` at catching things in my experience."

There are already two official Claude Code plugins for review: `code-review` and `pr-review-toolkit`. They're accessible via `/plugins` inside Claude Code. 53 plugins total as of early 2026.

**What they don't cover:** Both are oriented toward PR-style review — diffs, changed lines, team workflow. They don't address:
- Iterative pass-level regression checks
- Agent-generated code anti-patterns (timing hacks, bloat, silent defaults)
- Architectural context injection for scripts without a PR context
- A fresh subagent as the reviewer (they run in the same session)

Our skill fills that gap. But worth knowing the plugins exist — a user who just wants general code review should reach for `code-review` or `pr-review-toolkit` first. The skill is for the agent-iteration use case specifically.

### 16.3 Cross-Model Review: Use a Different Model to Avoid Same-Model Bias

From the $417 Claude Code post, commenter olavla (well-received):
> "My secret trick: use `git2text` on the codebase. Put everything in Google AI Studio (Gemini 2.5 Pro), let it comment on the code, and have it generate specific to-do lists that I paste back into Claude Code."

This is an independently-discovered, stronger version of the fresh-subagent pattern. The insight: **using a different model to review eliminates model-specific blind spots**, not just context intoxication. Claude reviewing Claude's code may share systematic biases (same training, same tendencies toward certain patterns). A different model has different failure modes.

For the skill design: document this as an optional variant. The default is a fresh Claude subagent (accessible, cheap, works in-session). For high-stakes code, the nuclear option is passing the file to a different model via API — Gemini 2.5 or o3 — and having it return findings that Claude then acts on.

### 16.4 Feature Creep as a Reviewable Pattern

From the $417 post, OP's own comment (120 upvotes):
> "I would often ask Claude for a relatively simple addition, but it would take it upon itself to add 5 different things. Sometimes they were actually good ideas, but often they weren't and I'd waste time and money telling it to change things back."

This is a concrete, nameable AI anti-pattern: **scope inflation**. The agent adds more than was asked. The review skill should detect this when running in iterative mode:

> "Did this pass add functionality beyond what the task description requested? Flag any additions that weren't explicitly asked for as [WARN: scope inflation]."

Scope inflation is insidious because the added code often works — it just wasn't requested, may not be tested, and adds maintenance surface.

### 16.5 CLAUDE.md Instruction Drift

From the Boris post, commenter WePwnTheSky:
> "Claude chronically ignores instructions in CLAUDE.md. I implement a new feature requiring a new permission, it never implements the permission and RLS correctly despite CLAUDE.md documenting the pattern and prior pitfalls."

And from kwabaj_ (8 months daily Claude Code use, 29 upvotes):
> "Skills, an overly extensive CLAUDE.md file, pre-configured subagents — all of that stuff is just pollution. Claude already has a sophisticated well-engineered system prompt. Adding all sorts of skills is doing more harm than good. Just talk to it."

Two complementary data points:
1. CLAUDE.md instructions don't reliably propagate — agents don't re-read it mid-task.
2. Over-engineering with skills and subagents has diminishing returns.

**Review skill implication:** The review prompt must be **self-contained**. Don't rely on CLAUDE.md or project-level context files being loaded or respected. Every invocation of the skill must carry all the criteria it needs in its own prompt. No implicit references to "the rules in CLAUDE.md."

### 16.6 Test-Writing as a Verification Step

Two independent sources converged on this:

From the $417 post, commenter kkingsbe:
> "Have Claude write tests to verify its changes."

From the 100% AI project post (Round 2), commenter hei8ht:
> "My greatest regret is not writing tests. Now whenever I change something, something always breaks."

**Design implication:** The skill should include an optional `--with-tests` flag or a `verify` mode that, after issuing review findings, asks the reviewer to also generate a minimal test for the highest-risk finding. Not a full test suite — just enough to make the critical finding executable and verifiable.

This turns the review from passive (list of issues) to active (here's a test that will fail if this bug exists). For iterative agent use, that's the difference between "the agent knows there's a problem" and "the agent can confirm it fixed the problem."

### 16.7 Cost Discipline in Iterative Review

From MorroHsu Part 2, commenter mrtrly:
> "I have watched agent swarms burn through $50 in tokens on tasks that should have cost $2. Each tool call has a price tag. Most agent builders focus on capabilities and forget cost observability."

The iterative review mode needs to be cheap per invocation. Design principles:
- Max 3 findings in iterative mode (vs. 5 in general mode)
- No preamble, no explanation of what was checked — findings only
- Skip NITs entirely in iterative mode
- The reviewer subagent should use the cheapest capable model (Haiku 4.5 for iterative, Sonnet for general/security passes)

### 16.8 Progressive Tool Discovery (from MorroHsu)

From the CLI agents post, the "Tips Thinking" pattern:
> "Return a hint on how to fix a command instead of just a raw error code. Massive token saver in long-context loops."

Applied to the review skill: when findings are returned, each finding should include one actionable directive, not just a description of the problem. "Silent default on line 47 — raise ValueError instead of assigning None" is twice as useful as "Line 47 has a silent default assignment."

The finding format should be: **[SEVERITY] Location — problem — one-line fix hint**.

### 16.9 Boris's Actual Workflow (What the Creator Does)

The full picture from his Q&A, stripped of the "unlimited tokens" caveat:

1. **5 parallel sessions** across separate git checkouts (not worktrees — avoids checkout conflicts)
2. **System notifications** to know when a session needs input — he doesn't watch them continuously
3. **Hands off work between sessions** using `--teleport` or manual context passing
4. **Deliberately vanilla** — no elaborate CLAUDE.md, no custom skill stacks, no pre-configured subagents

The review-relevant insight: Boris uses **separate checkouts** to keep parallel work isolated. For the review skill in a personal agent workflow, this suggests: the reviewer should operate on the files as they exist at review time, not during active editing. Trigger review at natural pause points (end of a task phase, before committing), not mid-edit.

---

## 17. Final Consolidated Skill Design

Drawing all three rounds together:

### Architecture
```
Caller (main agent or user)
    ↓  explicit invocation (not hook-triggered)
Review Skill
    ↓  reads file(s) + optional context (handover doc, AGENTS.md excerpt)
Fresh Reviewer Subagent
    ↓  self-contained prompt (no CLAUDE.md dependency)
    ↓  model: Haiku for iterative, Sonnet for general/security
Tagged Findings → returned to caller
```

### Four Modes

| Mode | Trigger | Model | Max findings | Scope |
|---|---|---|---|---|
| `iterative` | After each agent pass on a file | Haiku | 3 | Regressions only, no NITs |
| `general` | End of task phase | Sonnet | 5 | Full semantic check list |
| `security` | Before any external exposure | Sonnet | 5 | Auth, credentials, injection |
| `agent-output` | New file or major addition | Sonnet | 5 | AI-specific anti-patterns |

### Finding Format (all modes)
```
[SEVERITY] file.py:line — problem description — fix hint
```
Example:
```
[CRITICAL] ws6_prepass.py:142 — bare except swallows KeyError silently — raise or catch specifically
[WARN] ingest.py:89 — scope inflation: added retry logic not in task spec — confirm intentional
[WARN] pipeline.py:203 — setTimeout(fn, 500) masks race condition — use proper async coordination
```

### What the Prompt Must Always Include
1. Mode declaration (iterative/general/security/agent-output)
2. File contents (full, not diff)
3. For iterative mode: one-line description of what the agent just did
4. Severity cap and finding limit
5. The full check list appropriate to the mode (self-contained — no CLAUDE.md references)

---

*End of report (all rounds). This document is the complete reference for building the skill. Start with `iterative` mode — it's the most-used path and the most constrained design.*
