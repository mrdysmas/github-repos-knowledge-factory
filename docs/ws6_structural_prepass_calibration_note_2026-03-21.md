# WS6 Structural Pre-Pass Calibration Note

Date: 2026-03-21
Issue: `github_repos-tl0`
Batch: `B13_ws6_prepass_calibration`

## Batch Selection Rationale

This calibration used the smallest batch that still exercised two different
orientation shapes:

- `getzep/graphiti`
- `vectorize-io/hindsight`

These were the preferred starting candidates named in the issue and were already
queued in the intake backlog, so they could be tested without inventing a side
workflow.

The pair is useful for calibration because they are complementary:

- `getzep/graphiti` is a moderate-size Python-heavy repo with a recognizable
  core package plus explicit server and MCP surfaces.
- `vectorize-io/hindsight` is a much broader polyglot monorepo with multiple
  packages, runtime surfaces, integrations, clients, docs, and generated/build
  outputs.

That makes the batch small enough for a bounded comparison while still testing
whether the pre-pass stays helpful once repo shape becomes more complex.

## Generated Artifacts

Clone manifest:

- `reports/ws6_clone_prep/B13_ws6_prepass_calibration_clones.yaml`

Pre-pass outputs:

- `reports/ws6_structural_prepass/B13_ws6_prepass_calibration/getzep__graphiti.yaml`
- `reports/ws6_structural_prepass/B13_ws6_prepass_calibration/vectorize-io__hindsight.yaml`
- `reports/ws6_structural_prepass/B13_ws6_prepass_calibration/summary.yaml`

Verification outcome:

- batch generation succeeded for both repos
- summary boundary checks passed
- outputs stayed non-canonical and report-scoped only
- existing regression tests passed via
  `python3 -m unittest discover -s tests/ws6_structural_prepass -p 'test_*.py'`

## Comparison Notes: Usefulness vs Baseline Workflow

Baseline workflow here means the normal manual orientation path before deep
authoring: open the clone, inspect README/top-level tree, and grep for likely
entrypoints or package boundaries.

### `getzep/graphiti`

Usefulness: strong.

The pre-pass helped immediately by surfacing:

- runtime entrypoints at `server/graph_service/main.py` and `mcp_server/main.py`
- the core package boundary under `graphiti_core/`
- supporting structural clusters such as `graphiti_core/driver/` and
  `graphiti_core/cross_encoder/`
- nearby runtime/config surfaces such as `docker-compose.yml` and `.env.example`

This is materially better than tree-only orientation because it turns a repo
with several top-level directories into a short first-read path without making
behavioral claims.

### `vectorize-io/hindsight`

Usefulness: mixed but still directionally positive.

The pre-pass was valuable for quickly showing that the repo is not a single
package but a broad workspace with:

- API/runtime surfaces under `hindsight-api-slim/`
- a Rust CLI under `hindsight-cli/`
- multiple client SDKs under `hindsight-clients/`
- a control-plane app under `hindsight-control-plane/`
- a large integrations area under `hindsight-integrations/`

That is useful orientation signal that would otherwise take several directory
reads and manifest checks to reconstruct.

However, the current heuristics also showed clear noise on this repo:

- `likely_first_read` included
  `hindsight-dev/benchmarks/visualizer/main.py`, which is not a likely primary
  runtime starting point.
- entrypoints included
  `hindsight-clients/typescript/dist/index.js`, which is a built artifact path
  and not a good authoring-first surface.
- `module_groups` emitted duplicate `hindsight_api` naming from different roots.
- dependency output is still broad enough on a polyglot monorepo to feel more
  like inventory than orientation.

So the pre-pass helped answer "what kind of repo is this and where are the main
surfaces?" but it did not yet reliably answer "what should I read first?"
without some human filtering.

## Recommendation

Recommendation: keep the pre-pass experimental and refine it further before any
default adoption for normal batches.

Reasoning:

- The calibration succeeded on the narrow technical question: the artifact is
  cheap, deterministic, non-canonical, and helpful for early repo orientation.
- The calibration did not yet clear the workflow-quality question for broader
  adoption because the monorepo case still introduces enough noise to create
  first-read ambiguity.

Suggested refinement targets before considering soft integration:

- de-prioritize `examples/`, `benchmarks/`, and built-output paths such as
  `dist/` when ranking likely first reads or manifest-derived entrypoints
- merge or normalize duplicate module-group names across related package roots
- trim dependency output to the most orientation-relevant subset for large
  polyglot repos
- score likely runtime surfaces higher than dev/demo/support surfaces in
  monorepo layouts

Bottom line:

The pre-pass is already useful as an optional scaffold for bounded WS6 work, but
this calibration does not support making it a default step yet.
