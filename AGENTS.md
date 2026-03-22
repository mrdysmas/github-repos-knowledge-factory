## Execution Environment

- **Primary dev machine**: gbabe (Linux Mint 22.3 / Ubuntu 24.04, hostname `gbabe`, Tailscale-connected)
- **Mac role**: control node only — iTerm + Claude Code CLI direct, SSH/Paseo client
- **Remote orchestration**: Paseo daemon running on gbabe as a systemd service; connect via `app.paseo.sh` → direct TCP at `gbabe.tailca7be8.ts.net:443`
- **bd Dolt server**: runs as `beads-dolt.service` on gbabe; no manual start needed. If `bd` commands fail with a Dolt bind/start error, check `sudo systemctl status beads-dolt` on gbabe.
- **Shared Dolt remote**: gbabe exports `~/.beads-remote` via NFS; Mac mounts it at the same path. Both machines use `file://` remotes — no URL change needed.
- **Switching machines**: run `bd dolt pull` before starting work to pick up the other machine's pushes. Failure to pull before push will result in a non-fast-forward rejection (non-destructive — just pull and retry).

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
- Design decisions index: `docs/decisions/` — consult before writing deep files for new shapes or changing archetype/intake routing behavior.

## Corpus Maintenance Rules

- Archetype definitions live in `tools/ws6_soft_audit.py` (`ARCHETYPES` dict). Do not add new archetypes without first reading `docs/decisions/archetype_definition_process_decision_2026-03-22.md`.
- Pre-pass manifests use provisional categories (e.g. `infra_ops`). Deep files must set specific categories that match the intended archetype — two repos cannot share a broad category if they will map to different archetypes. Category collision produces a silent audit failure where one repo is misclassified.
- For repos with no existing deep files, define the archetype shape first, then write the deep file targeting those families. Do not reverse this order.
- **Pipeline input directories**: `repos/knowledge/deep_facts/` is WS6 output — writing there is silently ignored. To add a new repo, create (1) a shallow entry in `repos/knowledge/repos/` and (2) a narrative file in `repos/knowledge/deep/`. WS6 reads those two and produces `deep_facts/` as output.

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
- Dolt remote is configured for this repo; use `bd dolt push` to publish Beads history.
- Local Dolt history remains available even when remote sync is deferred.

### Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Always use `--json` flag for programmatic use
- ✅ Link discovered work with `discovered-from` dependencies
- ✅ Check `bd ready` before asking "what should I work on?"
- ✅ Treat `bd create` and `bd dolt push` as non-retryable until state is checked
- ✅ If `bd create` returns an uncertain result, verify first with `bd search "<distinctive title phrase>" --status all --json` or `bd show <id> --json` before retrying
- ✅ If `bd dolt push` fails with `checksum error`, `non-fast-forward`, or `nothing to commit`, inspect local state (`.beads/push-state.json`, `.beads/dolt-server.log`, and the affected issue IDs) before any retry
- ✅ Prefer the actual installed bd CLI shape over memory:
  - use `--type`, not `--issue-type`
  - use `bd duplicate <id> --of <canonical>`
  - use `bd dep <blocker> --blocks <blocked>` to add blocking dependencies
- ✅ When passing long `bd` descriptions through the shell, avoid backticks and other command-substitution syntax inside quoted text
- ✅ If sandboxed `bd` commands fail because Dolt cannot auto-start or bind a port, rerun with escalation instead of treating it as a normal bd error
- ✅ After changing dependencies or deferrals, verify with `bd show <id> --json`, `bd dep list <id> --json`, and `bd ready --json` rather than assuming the queue changed as intended
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
   ./tools/guarded_closeout.sh
   ```
   The wrapper is the primary path. It serializes `bd dolt push`, `git pull --rebase`, `git push`, and a fresh `git status` under a single repo lock.
   Beads note: do not blind-retry `bd dolt push`. If the result is uncertain or fails with a remote/backend error, verify state first and then do at most one deliberate retry.
   Execution note: do not bypass the wrapper by launching `bd dolt push`, `git pull --rebase`, `git push`, or `git status` separately or in parallel. If the wrapper reports a stale lock, inspect `.git/guarded-closeout.lock/metadata` and then use `./tools/guarded_closeout.sh --force-clear-stale-lock` only after confirming the recorded PID is gone.
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If `git push` fails, resolve and retry until it succeeds
- If `bd dolt push` fails, do not loop retries. Verify whether the Beads mutation already landed, classify the error, and only then retry once if the failure looks retryable.
- If `bd dolt push` is still blocked after a verified retry, surface the blocker with the exact error and the local Beads state you confirmed.

<!-- END BEADS INTEGRATION -->
