# WS6 Structural Pre-pass Broad-Repo Application Note

Date: 2026-03-21
Issue: `github_repos-tja`
Batch: `B16_dify_broad_prepass_backfill`
Repo: `langgenius/dify`

## Why This Repo Qualified

`langgenius/dify` clearly met the broad-repo trigger before authoring:

- multiple major runtime/package boundaries: `api/`, `web/`, `docker/`, `sdks/`
- polyglot implementation surface: Python, TypeScript, JavaScript, and PHP files
- mixed top-level tree with product code, deployment stack, docs, SDKs, and helper scripts
- more than one primary runtime surface: Flask API, Celery worker/beat, Next.js web app

That made the structural pre-pass required for this task rather than optional.

## Execution Path

This used the normal corpus-maintenance batch workflow:

1. `inputs/ws5/B16_dify_broad_prepass_backfill_manifest.yaml`
2. `python3 tools/ws5_remote_ingestion.py --workspace-root . --input inputs/ws5/B16_dify_broad_prepass_backfill_manifest.yaml`
3. `python3 tools/ws4_master_compiler.py --workspace-root .`
4. `python3 tools/ws6_clone_prep.py --workspace-root . --manifest inputs/ws5/B16_dify_broad_prepass_backfill_manifest.yaml --clone-workdir workspace/clones --size-limit-mb 1000 --batch-id B16_dify_broad_prepass_backfill`
5. `python3 tools/ws6_structural_prepass.py --workspace-root . --clone-manifest reports/ws6_clone_prep/B16_dify_broad_prepass_backfill_clones.yaml --input-manifest inputs/ws5/B16_dify_broad_prepass_backfill_manifest.yaml`
6. Deep-authoring refresh for `repos/knowledge/deep/langgenius__dify.yaml`
7. `python3 tools/run_batch.py --spec /tmp/B16_dify_broad_prepass_backfill_batch_spec.yaml --workspace-root .`

## Outcome

Artifacts and resulting corpus outcome:

- pre-pass artifact: `reports/ws6_structural_prepass/B16_dify_broad_prepass_backfill/langgenius__dify.yaml`
- pre-pass summary: `reports/ws6_structural_prepass/B16_dify_broad_prepass_backfill/summary.yaml`
- completed batch verdict: `reports/run_batch/B16_dify_broad_prepass_backfill_verdict.yaml`
- refreshed deep narrative: `repos/knowledge/deep/langgenius__dify.yaml`
- resulting deep facts: `repos/knowledge/deep_facts/langgenius__dify.yaml`

Verification outcome:

- pre-pass summary reported `gate_ready: true` and no writes outside `reports/`
- batch verdict finished `result: ok`
- all WS6 gates passed
- all WS7 gates passed
- repo-specific WS6 coverage now shows `facts_emitted: 102` and `unmapped_sections_count: 0` for `repo::langgenius/dify`
- global `query_master stats` after the run reports `repos: 122` and `deep_facts: 6186`

## Did The Broad-Repo Ranking Refinement Hold Up?

Mostly yes, with one useful caveat.

What held up:

- `likely_first_read` started with the main backend runtime surfaces:
  `api/controllers/service_api/app/app.py`,
  `api/controllers/console/app/app.py`,
  `api/core`,
  `api/commands`,
  `api/configs`,
  `api/app.py`
- helper/admin-secondary areas such as `docs/`, `sdks/`, and `docker/` did not outrank the primary API subsystem
- the package-root detection correctly surfaced `api`, `web`, and `sdks/nodejs-client`, which made the repo shape obvious quickly

Residual weakness:

- `web/` is a real primary subsystem boundary in Dify, but it did not make the `likely_first_read` list even though it appeared in `package_roots` and the repo clearly has a separate frontend runtime
- the ranking therefore favored the backend surfaces correctly, but it still under-emphasized one major co-equal surface of the product

Practical assessment:

The refinement still helped in real work because it pushed the right backend surfaces above noisy secondary areas and made the repo shape legible early. On this repo, the remaining gap is not helper/admin clutter outranking the core system anymore; it is better balancing between two real primary surfaces, especially `api/` versus `web/`.
