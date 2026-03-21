# Probe: Worker/Job/Agent Subsystem Class
**Date:** 2026-03-21
**Parent bead:** github_repos-wma
**This bead:** github_repos-w8t

---

## Probe Target

**Class:** Worker / job / queue / agent subsystem surfaces — separate background-process entrypoints that are co-equal runtime components alongside an API server, but reside in dedicated module files or directories (e.g., Celery workers, job queues, scheduler processes).

**Why this class first:** Most immediately testable using dify, which is already cloned and has B16 pre-pass output. The class is common in production web apps (Flask/Django + Celery, FastAPI + worker, etc.).

---

## Exemplar Repo

**`langgenius/dify`** (B16 output: `reports/ws6_structural_prepass/B16_dify_broad_prepass_backfill/langgenius__dify.yaml`)

**Rationale:** Dify runs as two distinct processes:
1. API server: `celery -A celery_entrypoint worker` → entry module `api/celery_entrypoint.py`
2. Web frontend: `web/` (already handled by frontend boost, B16 confirmed correct)

The Celery worker process is co-equal with the API server. Any reader consuming `likely_runtime_surfaces` would not know the worker exists from the current output.

---

## Probe Findings

### Gap 1: `api/celery_entrypoint.py` not detected as entrypoint

- File path: `api/celery_entrypoint.py`
- Content: re-exports `app` and `celery` from `app.py` for Celery CLI launch
- **Why missed:** path tokens are "api", "celery", "entrypoint" — none map to `RUNTIME_TOKENS`. File has no `if __name__ == "__main__"` guard, so Python entrypoint heuristics don't fire.
- **Expected behavior:** Should appear as `app_entry` entrypoint, then promote to `likely_runtime_surfaces`

### Gap 2: `api/dify_graph/graph_engine/worker.py` detected but wrong kind

- **Currently detected** as `app_entry` via filename heuristic ("worker" ∈ `RUNTIME_TOKENS`)
- **Actual role:** Internal graph execution worker pool module — runs inside the API process, not a separate process entrypoint
- **Effect:** Occupies the one "worker" slot in entrypoints but represents the wrong level; true Celery entrypoint is invisible

### Gap 3: `api/tasks/` (51 files) not surfaced

- Large, dedicated Celery task directory not represented in orientation hints
- `api/tasks/` is effectively the implementation surface of the worker process

---

## Current Output vs Expected

| Surface | Current `likely_runtime_surfaces` | Expected |
|---|---|---|
| API server | api/app.py ✓ | ✓ correct |
| API controllers | api/controllers/... ✓ | ✓ correct |
| Celery worker entrypoint | ❌ absent | Should appear as process surface |
| tasks/ directory | ❌ absent | Should appear or be mentioned in hints |

---

## Generalizability

**Pattern:** `{module_root}/celery_entrypoint.py` (or `worker_entrypoint.py`, `queue_app.py`, etc.) is the conventional Celery worker bootstrap. This pattern is widespread:
- Flask + Celery, FastAPI + Celery, Django + Celery are all common
- The entrypoint file is typically small (re-exports app + celery object) but semantically significant

**Not specific to dify.** Any repo with this architecture will have the same blind spot.

---

## Spawn Decision: YES — create child refinement bead

**Trigger conditions met:**
1. Worker entrypoint is structurally important (separate process, not a helper)
2. Systematically absent from output (not a ranking tie — simply not detected)
3. Pattern generalizes broadly to common Python webapp architecture

**Refinement scope (narrow):**
1. Add file-stem patterns for Celery/queue worker bootstrap to entrypoint detection: `celery_entrypoint`, `worker_entrypoint`, `queue_worker`, `worker_app`
2. Promote detected celery/queue-process entrypoints in `likely_runtime_surfaces` when they sit at module-root depth (shallow relative to enclosing module)
3. Guard: re-run B16 dify + B15 airtable.js + B13 graphiti to confirm no regressions on non-worker repos

---

## Criteria for Future Probes (General)

**Spawn refinement bead if:**
- A semantically important subsystem surface is **absent** from `likely_runtime_surfaces` (not merely deprioritized)
- The absence stems from a detectable structural signal that the tool currently ignores
- The pattern generalizes to ≥2 common repo shapes (not a one-off quirk)

**Close as sufficient if:**
- The subsystem appears in `likely_runtime_surfaces` or `likely_first_read` at a reasonable rank
- The subsystem is subordinate (helper, not co-equal process)
- The only fix would be name-based token matching with no structural backing evidence
