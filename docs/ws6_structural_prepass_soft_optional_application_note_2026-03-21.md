# WS6 Structural Pre-Pass Soft-Optional Application Note

Date: 2026-03-21
Issues: `github_repos-ckh`, `github_repos-an9`
Batch: `B14_graphiti_prepass_intake`
Repo: `getzep/graphiti`

## Execution Path

This application used the normal corpus-expansion path, not the earlier
calibration-only path:

1. `inputs/ws5/B14_graphiti_prepass_intake_manifest.yaml`
2. `python3 tools/ws5_remote_ingestion.py --workspace-root . --input inputs/ws5/B14_graphiti_prepass_intake_manifest.yaml`
3. `python3 tools/ws4_master_compiler.py --workspace-root .`
4. `python3 tools/ws6_clone_prep.py --workspace-root . --manifest inputs/ws5/B14_graphiti_prepass_intake_manifest.yaml --clone-workdir /home/abe/scripts/ext_sources/github_repos/workspace/clones --size-limit-mb 500 --batch-id B14_graphiti_prepass_intake`
5. `python3 tools/ws6_structural_prepass.py --workspace-root . --clone-manifest reports/ws6_clone_prep/B14_graphiti_prepass_intake_clones.yaml --input-manifest inputs/ws5/B14_graphiti_prepass_intake_manifest.yaml`
6. Deep authoring for `repos/knowledge/deep/getzep__graphiti.yaml`
7. `python3 tools/run_batch.py --spec /tmp/B14_graphiti_prepass_intake_batch_spec.yaml --workspace-root .`

Verification outcome:

- `reports/ws6_structural_prepass/B14_graphiti_prepass_intake/summary.yaml` passed
  boundary checks and stayed report-scoped only
- `reports/run_batch/B14_graphiti_prepass_intake_verdict.yaml` finished `result: ok`
- WS6 and WS7 gates both passed
- `query_master stats` now reports `repos: 122` and `deep_facts: 6123`
- `repos/knowledge/deep_facts/getzep__graphiti.yaml` emitted 75 facts with
  task, failure-mode, API, extension-point, and protocol coverage

## Usefulness vs Manual Orientation

Usefulness on this real corpus application was strong.

The pre-pass immediately clarified the three surfaces that mattered for first
read selection:

- `graphiti_core/` as the reusable temporal graph library
- `server/graph_service/main.py` plus its routers as the REST runtime surface
- `mcp_server/main.py` and `mcp_server/src/graphiti_mcp_server.py` as the MCP
  runtime surface

That reduced orientation thrash in two ways:

- it answered the package/runtime-boundary question before deeper file reading,
  so authoring did not spend time treating examples or docs as likely primary
  entrypoints
- it narrowed the first-read set to the exact files that ended up shaping the
  deep narrative: core client, REST startup and routers, MCP startup/config, and
  quickstart docs

Time savings were moderate rather than dramatic because `getzep/graphiti` is not
an extremely broad monorepo, but the boundary clarity was still materially
useful and justified the soft-optional step.

## Follow-Up Assessment

No new soft-optional policy failure mode surfaced strongly enough here to justify
opening a follow-up Beads issue.

The only minor noise observed was that the pre-pass still surfaced both
`mcp_server/` and `mcp_server/src` as related package roots. In this repo that
was easy to filter mentally and did not create first-read confusion, so it is
better treated as acceptable heuristic redundancy than as a new blocker.
