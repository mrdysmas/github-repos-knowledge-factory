# Archetype Backfill — Kickoff Prompt (Contract v2.1)

**Session type:** Deep narrative augmentation / archetype backfill
**Branch:** `main`
**Contract:** `contracts/deep_narrative_contract.md` (v2.1, Active)
**Date:** 2026-03-19

---

## What this session does

You will augment deep narrative YAML files for a target list of repos. These files already exist but are missing required evidence family coverage under the new `agent_cli` and `agent_framework` archetypes added in contract v2.1. You are not doing a full re-extraction — you are adding the missing sections to files that already have structural content.

Read `AGENTS.md` at the repo root before doing anything else. Then read `contracts/deep_narrative_contract.md` in full. That contract is the authoritative spec for everything you produce.

---

## What changed (and why it matters)

Contract v2.1 added two new archetypes with required evidence families:

**`agent_cli`** — tools whose primary interface is a terminal command:
- **Tasks** (Required) — `commands`, `cli_commands`, `common_tasks`, `procedures`, `quick_reference`
- **Failures** (Required) — `troubleshooting`

**`agent_framework`** — libraries or platforms for building, orchestrating, or extending agents:
- **Tasks** (Required) — same sections as above
- **Failures** (Recommended) — `troubleshooting`

The soft audit detects coverage by checking whether `supports_task` and `has_failure_mode` facts exist in the knowledge DB for each repo. A `commands:` section only produces `supports_task` facts if it is a **list** of dicts — not a nested dict. See the Format section below.

---

## Critical format rule: list vs. nested dict

The fact extractor produces `supports_task` facts from Tasks sections **only when the section is a list**. A `commands:` section formatted as a nested dict (keys mapping to dicts) produces **zero** `supports_task` facts.

**Correct — list format (produces facts):**
```yaml
commands:
  - name: parlant-server
    description: Start the Parlant server on the default port.
  - name: "parlant agents list"
    description: List all configured agents.
```

**Wrong — nested dict format (produces zero facts):**
```yaml
commands:
  server:
    syntax: parlant-server
    description: Start the Parlant server
  agents_list:
    syntax: parlant agents list
    description: List all agents
```

Some repos in the target list already have a `commands:` or `cli_commands:` section in the wrong (nested dict) format. For those repos, **do not modify the existing section** — add a new `common_tasks:` list-format section instead (same content, correct format). `common_tasks` counts toward the Tasks family.

---

## Target repo list

### Group A — `agent_cli`, missing Failures only

These repos have Tasks coverage already. They only need a `troubleshooting:` section added.

```
anthropics__claude-code    category: agent_cli
openai__codex              category: agent_cli
abhigyanpatwari__gitnexus  category: agent_cli
moonshotai__kimi-cli       category: agent_cli
anomalyco__opencode        category: agent_cli
ralph                      category: agent_cli  (github: snarktank/ralph)
```

The missing family is **Failures** — specifically a `troubleshooting:` section with `symptom` / `cause` / `fix` triples.

CLI tool failure modes to consider: authentication failures (missing API key, expired token, wrong format), rate limiting (429 errors, backoff behavior), missing or invalid config (config file not found, malformed config), network/connectivity errors (endpoint unreachable, SSL errors), and command-level errors (unexpected output format, unknown flags).

---

### Group B — `agent_cli`, missing Tasks + Failures

These repos need both a `commands:` section (list format) and a `troubleshooting:` section added.

```
ccs                  category: agent_cli  (github: kaitranntt/ccs)
claude-code-tips     category: agent_cli  (github: ykdojo/claude-code-tips)
claude-mem           category: agent_cli  (github: thedotmack/claude-mem)
codemoot             category: agent_cli  (github: katarmal-ram/codemoot)
github__copilot-cli  category: agent_cli  (github: github/copilot-cli)
felony               category: agent_cli  (github: henryboldi/felony)
oh-my-opencode       category: agent_cli  (github: code-yeongyu/oh-my-opencode)
ralph-claude-code    category: agent_cli  (github: frankbria/ralph-claude-code)
ralphy               category: agent_cli  (github: michaelshimeles/ralphy)
```

**Note on `github__copilot-cli`:** This file has a `cli_arguments:` section (not in the Tasks family) but no `commands:` or `cli_commands:` list. Add `commands:` as a list.

For repos that appear to be documentation or tips collections (e.g., `claude-code-tips`) rather than executable CLIs: if no meaningful commands exist, add a minimal `commands:` section with the primary invocation patterns described in the README. Do not invent commands — use training knowledge for well-known public repos, flag uncertainty with `sourcing_method: training_knowledge`.

---

### Group C — `agent_framework`, missing Tasks

These repos need a properly-formatted Tasks section added. All five have deep files already.

```
composiohq__awesome-claude-skills  category: agent_framework  (github: composiohq/awesome-claude-skills)
anthropics__skills                 category: agent_framework  (github: anthropics/skills)
superpowers                        category: agent_framework  (github: obra/superpowers)
khoj                               category: agent_framework  (github: khoj-ai/khoj)
parlant                            category: agent_framework  (github: emcie-co/parlant)
```

**Critical for `khoj`:** This file has `commands:` formatted as a nested dict (keys `installation`, `running`, `database` mapping to sub-dicts). This format produces zero `supports_task` facts. Do not modify the existing section. Add a `common_tasks:` list using the same command information:
```yaml
common_tasks:
  - name: "pip install -e '.[dev]'"
    description: "Install with development dependencies."
  - name: python -m khoj.main
    description: "Start the Khoj server with default settings."
  - name: python manage.py migrate
    description: "Run Django database migrations."
```

**Critical for `parlant`:** Same issue — `cli_commands:` is formatted as a nested dict. Add `common_tasks:` as a list instead.

For `composiohq/awesome-claude-skills` and `anthropics/skills`: these are skill/resource collection repos, not CLIs. Add `commands:` or `quick_reference:` entries describing how to use or install skills (e.g., copy instructions, Claude CLI invocation patterns). If minimal, a 2–3 entry `quick_reference:` is sufficient.

For `superpowers`: a framework/platform — add `commands:` describing how to install, start, and configure the platform.

---

## How to work through each file

1. Read the shallow file at `repos/knowledge/repos/{file_stem}.yaml` — confirm `node_id`, `github_full_name`, `category`
2. Read the existing deep file at `repos/knowledge/deep/{file_stem}.yaml` — understand what's already there, don't duplicate it
3. Determine which families are missing based on the target group
4. Check for existing sections in the wrong format (see `khoj`, `parlant` above)
5. Source the missing content:
   - Read `README.md` first — commands, known issues, warnings, quick-start
   - Read `docs/` if it exists — troubleshooting guides, operational runbooks
   - Use training knowledge for well-known public repos where live source is unavailable — be conservative
6. Append the missing section(s) to the existing deep file
7. Set `provenance.sourcing_method` — use `code_verified` if you read live source, `training_knowledge` if not. Update `provenance.as_of` to today's date.

---

## YAML quoting rule (critical)

Always quote string values that contain any of: `` ` `` `@` `[` `]` `{` `}` `:` `#`

**Wrong:**
```yaml
fix: Reduce max_num_seqs, decrease max_model_len, or increase swap_space
```

**Correct:**
```yaml
fix: "Reduce max_num_seqs, decrease max_model_len, or increase swap_space"
```

---

## What good output looks like

**Tasks section (list format — required):**
```yaml
commands:
  - name: gitnexus setup
    description: "Configure editor MCP integration and install Claude skills/hooks where supported."
  - name: "gitnexus analyze [path]"
    description: "Index a Git repository into .gitnexus/lbug."
```

**Failures section:**
```yaml
troubleshooting:
  - symptom: "Authentication fails with 401 on first run"
    cause: "API key not set or set with wrong environment variable name"
    fix: "Set the correct environment variable (e.g., ANTHROPIC_API_KEY) and retry."
  - symptom: "Rate limit error (429) during long sessions"
    cause: "Exceeded per-minute token limit for the model tier"
    fix: "Add retry logic with exponential backoff, or reduce request frequency."
```

Note: use `symptom`/`cause`/`fix` — **not** `issue`/`solution`. Any existing sections using the wrong field names do not produce `has_failure_mode` facts and should not be used as models.

After your changes, each file should:
- Still pass all existing WS6 gates (don't break working sections)
- Have at least one recognized Tasks section as a list with `name`/`description` entries
- For Groups A and B: have a `troubleshooting:` section with `symptom`/`cause`/`fix` triples
- Have updated `provenance.as_of` and correct `provenance.sourcing_method`

---

## Reference files

| File | Why |
|---|---|
| `contracts/deep_narrative_contract.md` | Authoritative spec — read in full |
| `repos/knowledge/deep/abhigyanpatwari__gitnexus.yaml` | Strongest Tasks example for agent_cli (13 commands, list format) |
| `repos/knowledge/deep/vllm.yaml` | Strongest Failures example (troubleshooting with symptom/cause/fix) |
| `repos/knowledge/deep/openai__codex.yaml` | Good Tasks example for agent_cli |
| `repos/knowledge/deep/pydantic__pydantic-ai.yaml` | Tasks example for agent_framework (quick_reference format) |
| `AGENTS.md` | Read before any work |

---

## After you finish

Do not run the pipeline. Do not commit. The supervisor will review the files, run `run_batch.py`, verify WS6 gates pass and fact counts increase, then commit.

The key signal the supervisor is checking:
- `supports_task` count for `agent_framework` and `agent_cli` repos should increase
- `has_failure_mode` count for `agent_cli` repos should increase (currently 0 for all 15)
