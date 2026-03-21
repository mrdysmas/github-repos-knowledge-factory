# Probe: Infra/Ops Surfaces — Helm Chart Monorepo
**Date:** 2026-03-21
**Parent bead:** github_repos-wma
**This bead:** github_repos-wm7

---

## Probe Target

**Class (2) infra/ops surfaces** — repos where the artifact is declarative config (Helm charts, Terraform, Ansible, k8s manifests), not executable code. The orientation concern: no process entrypoints → fallback paths dominate and may produce misleading output.

---

## Exemplar Repo

**`grafana/helm-charts`** (B17 output: `reports/ws6_structural_prepass/B17_grafana_helm_charts_prepass/grafana__helm-charts.yaml`)

**Structure:**
- `charts/` — 20+ Helm chart subdirectories, each with `Chart.yaml`, `values.yaml`, `templates/`
- `charts/grafana/`, `charts/loki/` — stub dirs (README.md only; actual chart content elsewhere or removed)
- `scripts/` — release automation scripts
- `.github/workflows/` — 8 CI workflows (lint, test, release, sync)
- No application source code; `languages: []` correct

---

## Pre-pass Output Assessment

**Verdict: MISLEADING / INSUFFICIENT**

| Probe question | Expected | Actual | Pass? |
|---|---|---|---|
| `likely_first_read` → chart dirs | `charts/` or `charts/grafana/` etc. | `.` (fallback) | FAIL |
| `likely_runtime_surfaces` → graceful no-entrypoint | empty or chart roots | CI workflow files | FAIL |
| `module_groups` → chart-level grouping | one group per chart root | single fallback `repo_root: .` | FAIL |
| `entrypoints` → correctly empty | `[]` | `[]` | PASS |
| `languages` → correctly empty | `[]` | `[]` | PASS |

**Root cause:** The pre-pass has no Helm-aware signal path. `Chart.yaml` files are not recognized as manifest-type signals. The fallback path:
1. Finds no package manifests (`package.json`, `pyproject.toml`, etc.)
2. Falls back to `repo_root: .` for module grouping
3. Promotes CI workflow files into `likely_runtime_surfaces` (wrong — these are build tooling, not runtime surfaces for a chart consumer)
4. Sets `likely_first_read` to `.` rather than `charts/`

---

## Refinement Requirements

Spawn a refinement bead targeting `ws6_structural_prepass.py`:

1. **Helm chart detection** — recognize `Chart.yaml` as a manifest signal; each `charts/*/Chart.yaml` → one module group (chart root)
2. **`likely_first_read` for chart repos** — when chart roots are detected, surface `charts/` and top chart subdirs, not repo root
3. **`likely_runtime_surfaces` for declarative repos** — when no process entrypoints exist and the repo is chart/config-only, emit chart roots (or empty) instead of CI workflows
4. **No-entrypoint graceful handling** — `entrypoints: []` is correct; the issue is what fills the orientation gaps. For Helm repos, chart roots are the "surfaces" a consumer cares about.

**Signal cost:** `Chart.yaml` detection is cheap (glob `charts/*/Chart.yaml`). No parsing required — presence alone is sufficient to identify chart roots.

---

## Disposition

**Refinement bead spawned** (see dependency link). Close this probe as sufficient for establishing the failure mode — the pre-pass cannot orient a Helm chart monorepo without Helm-aware signals.
