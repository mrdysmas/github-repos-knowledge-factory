---
name: bdcapture
description: Capture the actionable conclusions from the recent conversation into 1-3 well-scoped Beads. Use when discussion has produced clear next steps and the user wants those next steps crystallized into issues for future agents.
---

# bdcapture

Capture recent agreed conclusions into a small set of actionable Beads.

Keep the workflow lightweight. Prefer 1-3 issues that preserve decision-quality context for future agents.

## Use When

Invoke when the conversation has already produced one or more of these:

- a clear decision with actionable follow-up
- an implied next-step sequence that should be made explicit
- a split between execution work and calibration or policy work
- a recommendation that should become claimable Beads instead of staying in prose

Do not invoke for generic backlog generation or brainstorming-only conversations.

## Core Outcome

Create Beads that carry forward:

- why the work exists now
- what question or execution target the issue is meant to answer
- what concrete deliverables are required
- what failure mode should invalidate a vague or drifting implementation
- which earlier issue or decision this work was discovered from

## Decision Logic

IF the conversation points to one concrete next action:
→ Create one execution issue.

IF the conversation separates immediate work from a later decision:
→ Create one execution issue and one decision issue.

IF the conversation distinguishes real-world use from evidence-gathering:
→ Split into execution and calibration issues.

IF the user explicitly wants policy captured:
→ Create a decision issue with repo-shape cues, acceptance target, and promotion criteria.

IF there is no clear actionable conclusion yet:
→ Do not create issues. Briefly say the discussion has not crossed the capture threshold.

## Workflow

1. Re-read the most recent discussion window.
2. Extract only conclusions the user has effectively agreed to.
3. Group the work into at most three tracks:
   - execution
   - decision
   - calibration
4. Name each issue by its actual job, not by generic follow-up language.
5. Write descriptions that are specific enough for a future agent to claim and execute without re-deriving the context.
6. Create each issue with `bd create ... --json`.
7. Link each new issue with `--deps discovered-from:<prior-id>` when a source issue exists.
8. Push Beads state with `bd dolt push` after creation.

## Writing Rules

- Keep titles short and operational.
- State the starting posture when it matters.
- Make acceptance targets explicit rather than implied.
- Separate "use this in real work" from "gather more calibration evidence."
- Prefer concrete repo-shape or workflow-shape cues over abstract criteria.
- Cap default fanout at 3 issues unless the user asks for more.

## Anti-Bloat Rules

- Do not create speculative backlog trees.
- Do not create a calibration issue if the user only wants execution.
- Do not create both optional-use and default-promotion issues unless those are genuinely different tasks.
- Do not use vague phrases like "follow up on this" without deliverables and a failure mode.

## Output Pattern

Before creating issues, summarize the proposed split in one short paragraph or a flat list.

For each issue description, include:

- why now
- required inputs or evidence base
- decision criteria or execution target
- deliverables
- failure mode

After creation, report:

- created issue IDs and titles
- why the split was chosen
- whether Beads push succeeded

## Quick Reference

```bash
bd create "<title>" --type task --priority 2 --description "<text>" --deps discovered-from:<id> --json
bd show <id> --json
bd dolt push
```

## Notes

- Treat this as a crystallization step, not ideation.
- Preserve the user's wording when it sharpens scope or posture.
- If the user gives a preferred command form such as `/bdcapture`, interpret that as permission to perform the capture workflow directly.
