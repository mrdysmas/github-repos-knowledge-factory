# AI Code Review with Claude: Research Report

**Date:** 2026-03-22
**Purpose:** Reference for building a code review skill targeting long, complex agent orchestration scripts.
**Sources:** O'Reilly, official Claude docs, practitioner blogs, HackerNews threads, Reddit (r/linux, r/ClaudeAI, r/SoftwareEngineering, r/ExperiencedDevs).

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

*End of report. Next step: build the skill in a fresh session, using this document as the reference.*
