## Execution Clarity

- When the user says they are confused or says "assume nothing," lead with exactly one concrete next action and one verification check before offering alternatives.
- Before giving operational guidance in any ambiguous context, disambiguate the target using a unique identifier and current state signal (for example: absolute path, active branch, commit SHA, environment name, or file hash).

## Scope Control

Default mode is execution and supervision, not exploration.

- Do not perform exploratory analysis unless explicitly requested.
- If context is sufficient to execute, execute.
- If blocked, report blocker and 2-3 options with tradeoffs.
- Keep responses concise and decision-oriented.
- Re-audit or broad re-scans require explicit user request.
- Treat unsolicited exploration as scope creep.
- Ask for confirmation before any broad discovery step.

## Status Routing

- Current status source of truth: `project_status.yaml`.
- Historical phase tracker and evidence narrative: `master_graph_merge_progress.yaml`.
- Phase 5 work-selection rubric: `phase_5_anchor_acceptance_rubric.yaml` (use this for core Phase 5 architecture/query/ontology/interface work; lightweight mode or exemption is allowed for exploratory or tiny tasks).
- Canonical generated artifacts: `master_index.yaml` and `master_graph.yaml`.
- Canonical update path: `inputs/ws5/ws5_input_manifest.yaml` -> `tools/ws5_remote_ingestion.py` -> WS1/trust/validate gates on `repos/knowledge` -> `tools/ws4_master_compiler.py` -> `tools/ws7_read_model_compiler.py`.
- Deep narrative output contract: `contracts/deep_narrative_contract.md` (governs all WS6-compatible deep YAML production).
- Read model materializer: `tools/ws7_read_model_compiler.py` (WS7 — compiles canonical YAML into `knowledge.db`; non-negotiable gate after every WS4/WS6 run).
- Read model output: `knowledge.db` (SQLite, gitignored — derived artifact rebuilt on every compile).
- Query CLI: `tools/query_master.py` (reads `knowledge.db` by default; `--source yaml` for legacy fallback; 9 commands including search/pattern/graph/aggregate).
- `kgraph-repos` is non-canonical (draft/raw discovery only) and must be mapped through WS1/WS5 pipeline before master compile.

## Intake Enforcement

- Intake source catalog: `master_repo_list.yaml` (intake backlog only; not canonical).
- Intake queue artifact: `inputs/intake/intake_queue.yaml` (generated).
- Queue generator: `tools/build_intake_queue_from_master_repo_list.py`.
- Queue sync gate: `tools/check_intake_queue_sync.py` (must pass before intake execution).
- Add new candidates using `tools/add_repo_candidate.py`; do not hand-edit queue files.

Required preflight before intake work:
- `python3 tools/check_intake_queue_sync.py --workspace-root .`

Required command to add a new candidate:
- `python3 tools/add_repo_candidate.py --workspace-root . --github-url https://github.com/<owner>/<repo>`

## Runbook Command Policy

- Any `required_commands` or `first_commands` entries in status/runbook artifacts must be directly executable from repo root.
- Do not use pseudo-command aliases (example: `spec.yaml --run-validation-suite`); use canonical interpreter-prefixed commands (example: `python3 tools/ws6_deep_integrator.py ...`).

## Phase 5 Acceptance Rubric

- For core Phase 5 work that changes ontology, extraction, query behavior, interface semantics, or planning guidance, consult `phase_5_anchor_acceptance_rubric.yaml`.
- Treat the rubric as a decision-quality filter, not universal bureaucracy.
- Use lightweight mode or explicit exemption for exploratory tasks or very small tasks where a full pass would be overhead.

<!-- BEGIN BEADS INTEGRATION v:1 profile:full hash:d4f96305 -->
## Issue Tracking with bd (beads)

**IMPORTANT**: This project uses **bd (beads)** for ALL issue tracking. Do NOT use markdown TODOs, task lists, or other tracking methods.

### Why bd?

- Dependency-aware: Track blockers and relationships between issues
- Git-friendly: Dolt-powered version control with native sync
- Agent-optimized: JSON output, ready work detection, discovered-from links
- Prevents duplicate tracking systems and confusion

### Quick Start

**Check for ready work:**

```bash
bd ready --json
```

**Create new issues:**

```bash
bd create "Issue title" --description="Detailed context" -t bug|feature|task -p 0-4 --json
bd create "Issue title" --description="What this issue is about" -p 1 --deps discovered-from:bd-123 --json
```

**Claim and update:**

```bash
bd update <id> --claim --json
bd update bd-42 --priority 1 --json
```

**Complete work:**

```bash
bd close bd-42 --reason "Completed" --json
```

### Issue Types

- `bug` - Something broken
- `feature` - New functionality
- `task` - Work item (tests, docs, refactoring)
- `epic` - Large feature with subtasks
- `chore` - Maintenance (dependencies, tooling)

### Priorities

- `0` - Critical (security, data loss, broken builds)
- `1` - High (major features, important bugs)
- `2` - Medium (default, nice-to-have)
- `3` - Low (polish, optimization)
- `4` - Backlog (future ideas)

### Workflow for AI Agents

1. **Check ready work**: `bd ready` shows unblocked issues
2. **Claim your task atomically**: `bd update <id> --claim`
3. **Work on it**: Implement, test, document
4. **Discover new work?** Create linked issue:
   - `bd create "Found bug" --description="Details about what was found" -p 1 --deps discovered-from:<parent-id>`
5. **Complete**: `bd close <id> --reason "Done"`

### Auto-Sync

bd automatically syncs via Dolt:

- Each write auto-commits to Dolt history
- **Dolt remote is NOT configured** — `bd dolt push` will fail with "remote 'origin' not found". Skip it.
- Local Dolt history is preserved; remote sync is not available until a remote is added.

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ❌ Do NOT create markdown TODO lists
- ❌ Do NOT use external issue trackers
- ❌ Do NOT duplicate tracking systems

For more details, see README.md and docs/QUICKSTART.md.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   git push
   git status  # MUST show "up to date with origin"
   ```
   Note: `bd dolt push` is NOT available — Dolt remote is not configured. Skip it.
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

<!-- END BEADS INTEGRATION -->
