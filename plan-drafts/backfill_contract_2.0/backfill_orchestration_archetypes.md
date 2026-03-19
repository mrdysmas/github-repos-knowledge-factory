# Archetype Backfill Orchestration — Supplementary Context

**Read this before reading `backfill_kickoff_archetypes.md`.**
**Companion to:** `backfill_kickoff_archetypes.md`
**Date:** 2026-03-19

---

## Your role in this session

You are the orchestrator. You do not write deep narrative files yourself. You spawn subagents to do that work, review their output, and stop if something goes wrong.

The actual extraction work is defined in `backfill_kickoff_archetypes.md`. Every subagent you spawn receives that prompt plus a scoped target list. Nothing else needs to change between subagents — the prompt is self-contained.

---

## Subagent sequence

Run three subagents, sequentially. Do not start the next subagent until the previous one completes and you have verified its output (see Verification below).

### Subagent 1 — Group A (agent_cli, missing Failures only)

Pass the full contents of `backfill_kickoff_archetypes.md` with this target list scoped to Group A only:

```
anthropics__claude-code    category: agent_cli  (github: anthropics/claude-code)
openai__codex              category: agent_cli  (github: openai/codex)
abhigyanpatwari__gitnexus  category: agent_cli  (github: abhigyanpatwari/gitnexus)
moonshotai__kimi-cli       category: agent_cli  (github: moonshotai/kimi-cli)
anomalyco__opencode        category: agent_cli  (github: anomalyco/opencode)
ralph                      category: agent_cli  (github: snarktank/ralph)
```

The missing family for all of these is **Failures** — add `troubleshooting:` with `symptom`/`cause`/`fix` triples. Do not touch the existing Tasks sections.

### Subagent 2 — Group B (agent_cli, missing Tasks + Failures)

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

Missing families: **Tasks** and **Failures**. Add both `commands:` (list format) and `troubleshooting:`.

### Subagent 3 — Group C (agent_framework, missing Tasks)

```
composiohq__awesome-claude-skills  category: agent_framework  (github: composiohq/awesome-claude-skills)
anthropics__skills                 category: agent_framework  (github: anthropics/skills)
superpowers                        category: agent_framework  (github: obra/superpowers)
khoj                               category: agent_framework  (github: khoj-ai/khoj)
parlant                            category: agent_framework  (github: emcie-co/parlant)
```

Missing family: **Tasks**. Critical: `khoj` and `parlant` already have commands sections in nested-dict format that produce zero facts — the subagent must add `common_tasks:` as a list instead (see kickoff prompt for details).

---

## What to pass each subagent

1. The full text of `backfill_kickoff_archetypes.md` — unmodified except the target list
2. The scoped target list for their group (above)
3. This instruction: **"Make no changes to existing sections. Only append new top-level sections to each file. Do not run `run_batch.py`. Do not commit."**

That third point is critical. The existing sections in these files pass WS6 gates. A subagent that reformats or reorganizes existing YAML while appending can introduce parse errors that break previously clean files.

---

## Verification between subagents

After each subagent completes, before spawning the next one, run this check:

```bash
# Confirm files were modified
git diff --name-only repos/knowledge/deep/

# For Groups A and B, confirm troubleshooting sections are present
grep -l "troubleshooting:" repos/knowledge/deep/*.yaml

# For Group C, confirm common_tasks or commands were added
grep -l "common_tasks:\|commands:" repos/knowledge/deep/khoj.yaml repos/knowledge/deep/parlant.yaml

# Quick YAML parse check — catches malformed output before it hits WS6
python3 -c "
import yaml, glob, sys
errors = []
for f in glob.glob('repos/knowledge/deep/*.yaml'):
    try:
        yaml.safe_load(open(f))
    except yaml.YAMLError as e:
        errors.append(f'{f}: {e}')
if errors:
    print('PARSE ERRORS:')
    for e in errors: print(e)
    sys.exit(1)
else:
    print('All deep files parse cleanly.')
"
```

If the YAML parse check fails, stop. Do not proceed to the next subagent. Identify which file is malformed, fix it, re-run the parse check, then continue.

**Known format pitfall to check after Group C:** For `khoj` and `parlant`, confirm the newly added section is a list (not a dict) and that it uses `name`/`description` fields. Run:
```bash
python3 -c "
import yaml
for fn in ['repos/knowledge/deep/khoj.yaml', 'repos/knowledge/deep/parlant.yaml']:
    f = yaml.safe_load(open(fn))
    ct = f.get('common_tasks', f.get('procedures'))
    if ct is None:
        print(f'{fn}: WARNING — no common_tasks or procedures section found')
    elif not isinstance(ct, list):
        print(f'{fn}: WARNING — section is not a list (type: {type(ct).__name__})')
    elif not ct[0].get('name') and not ct[0].get('task') and not ct[0].get('command'):
        print(f'{fn}: WARNING — first entry has no name/task/command field')
    else:
        print(f'{fn}: OK ({len(ct)} entries)')
"
```

---

## After all three subagents complete

Stop. Do not run the pipeline. Do not commit. Report back to the supervisor with:

1. Which files were modified (from `git diff --name-only`)
2. Whether the YAML parse check passed for all groups
3. Any files that were skipped or produced errors
4. For `khoj` and `parlant`: confirm whether `common_tasks:` was added as a list
5. Any judgment calls the subagents made that you want the supervisor to review

The supervisor will run `run_batch.py`, verify WS6 gates, check that `supports_task` and `has_failure_mode` counts increased for `agent_cli` and `agent_framework` repos, then commit.

---

## What success looks like

- All 20 files modified (6 Group A + 9 Group B + 5 Group C)
- All files parse cleanly
- No existing sections touched
- Each Group A file has `troubleshooting:` with at least 3 `symptom`/`cause`/`fix` entries
- Each Group B file has `commands:` (list) with at least 3 entries AND `troubleshooting:` with at least 3 entries
- Each Group C file has a list-format Tasks section (`commands:`, `common_tasks:`, or `quick_reference:`) with at least 2 entries
- `khoj` and `parlant` have `common_tasks:` (list) added, not modifications to existing sections
- `provenance.as_of` updated in each modified file
