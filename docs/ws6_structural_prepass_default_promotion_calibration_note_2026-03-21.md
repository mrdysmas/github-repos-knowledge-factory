# WS6 Structural Pre-Pass Default-Promotion Calibration Note

Date: 2026-03-21
Issue: `github_repos-zpn`
Batch: `B15_ws6_prepass_default_promotion_calibration`

## Batch Selection Rationale

This calibration was intentionally small and cross-shape, using one fresh repo
for each shape named in the earlier operating-mode decision:

- `airtable/airtable.js` as the easy single-package case that might not need a
  pre-pass at all
- `langchain-ai/deepagents` as the medium multi-surface case where benefit is
  plausible but not guaranteed
- `tailscale/tailscale` as the broad workspace/monorepo-style case where the
  pre-pass should help most if it is ready for default-grade use

These choices broaden the evidence base beyond the earlier `graphiti` and
`hindsight` pair while staying bounded and executable from the normal
`ws6_clone_prep` plus `ws6_structural_prepass` path.

## Generated Artifacts

Input manifest:

- `inputs/ws5/B15_ws6_prepass_default_promotion_calibration_manifest.yaml`

Clone manifest:

- `reports/ws6_clone_prep/B15_ws6_prepass_default_promotion_calibration_clones.yaml`

Pre-pass outputs:

- `reports/ws6_structural_prepass/B15_ws6_prepass_default_promotion_calibration/airtable__airtable.js.yaml`
- `reports/ws6_structural_prepass/B15_ws6_prepass_default_promotion_calibration/langchain-ai__deepagents.yaml`
- `reports/ws6_structural_prepass/B15_ws6_prepass_default_promotion_calibration/tailscale.yaml`
- `reports/ws6_structural_prepass/B15_ws6_prepass_default_promotion_calibration/summary.yaml`

Verification outcome:

- clone prep completed with `repos_failed: 0`
- structural pre-pass completed with `repos_generated: 3`
- summary boundary checks passed
- outputs stayed report-scoped and non-canonical only

## Comparison Notes: Baseline Manual Orientation vs Pre-Pass

Baseline workflow here means the same manual orientation path used in prior
notes: inspect the README, top-level tree, and the main package/build manifests
to answer three questions:

- what kind of repo shape is this
- where should a WS6 author read first
- what are the main runtime or package boundaries

### `airtable/airtable.js`

Repo shape: easy single-package library.

Baseline manual orientation was already fast and sufficient:

- `README.md` immediately identifies the repo as the official JavaScript client
- `package.json` points directly to `main: ./lib/airtable.js`
- the top-level tree is small, with one obvious source boundary under `src/`
  and built output under `lib/`

Pre-pass result:

- correctly identified the single package root and `lib/airtable.js` as the
  likely runtime surface
- added only light extra value beyond what README plus `package.json` already
  told the author

Assessment:

- helpful but low leverage
- does not justify a default extra step for repos of this shape

### `langchain-ai/deepagents`

Repo shape: medium multi-surface Python workspace with a core library, CLI,
ACP/server package, partner integrations, evals, and examples.

Baseline manual orientation was workable but took a few reads to settle:

- `README.md` makes the high-level split visible between the library and the
  CLI
- `libs/cli/pyproject.toml` and `libs/deepagents/pyproject.toml` confirm the
  two primary package roots
- the broader `libs/` tree also shows `acp`, `evals`, and partner packages,
  but those need a little manual sorting to decide what matters first

Pre-pass result:

- clearly surfaced `libs/cli`, `libs/deepagents`, `libs/acp`, `libs/evals`,
  and partner package roots
- correctly highlighted the CLI runtime surface under
  `libs/cli/deepagents_cli/`
- reduced package-boundary ambiguity faster than baseline tree inspection alone

Observed noise or limits:

- `likely_first_read` over-focused on several CLI files and did not elevate the
  core `libs/deepagents/` package as strongly as a WS6 author would likely want
- example `.env.example` files were surfaced as runtime-adjacent, which is
  mildly noisy even if not seriously misleading

Assessment:

- directionally useful
- stronger for package-boundary mapping than for perfect first-read ranking
- good evidence for selective use, not strong evidence for default use

### `tailscale/tailscale`

Repo shape: broad Go monorepo/workspace with many command surfaces, shared
networking packages, daemon/CLI boundaries, packaging areas, and web/UI
subprojects.

Baseline manual orientation required more work than the other two cases but
still surfaced the main boundaries with targeted reading:

- `README.md` identifies the main runtime surfaces as the `tailscaled` daemon
  and the `tailscale` CLI
- `go.mod` confirms the dominant Go module boundary at repo root
- a quick top-level scan shows the major structural areas that matter for WS6
  orientation: `cmd/tailscale`, `cmd/tailscaled`, `wgengine`, `ipn`, `control`,
  `net`, `client`, and supporting packaging/web areas

Pre-pass result:

- correctly detected that this is a broad multi-surface workspace and surfaced
  package roots such as `cmd`, `internal`, `packages`, `client/web`, and
  `cmd/tsconnect`
- helped show that web and packaging surfaces coexist with the main Go module

Observed noise or limits:

- `likely_first_read` was dominated by helper commands such as
  `cmd/addlicense/main.go`, `cmd/containerboot/main.go`, and
  `cmd/get-authkey/main.go`
- the two most important runtime boundaries from the README and tree walk,
  `cmd/tailscaled` and `cmd/tailscale`, were not elevated in the first-read set
- key shared subsystems such as `wgengine`, `ipn`, and `control` were not
  highlighted strongly enough relative to lower-priority helper binaries

Assessment:

- useful for saying "this repo is broad and multi-surface"
- not yet reliable enough on "where should I read first" for a default-grade
  orientation step on large monorepos

## Recommendation

Recommendation: keep the WS6 structural pre-pass policy at **soft-optional**.

Why the new evidence does not support promotion toward default:

- the easy repo confirms the expected low-value case: the pre-pass is fine but
  mostly redundant when README plus one manifest already answer the three
  orientation questions
- the medium repo is a positive selective-use case, but the gain is mostly in
  package-boundary compression rather than in a clearly superior first-read set
- the broad monorepo case still misses the default-promotion bar because
  first-read prioritization is not yet reliable enough; the pre-pass recognizes
  the broad shape, but it still under-ranks the actual primary runtime surfaces

Bottom line:

The evidence now strengthens confidence that selective use is the right
steady-state policy. It does not yet support making the pre-pass a default step
for all applicable WS6 batches.

## Promotion Gap After This Calibration

Before reconsidering default promotion, the pre-pass should show on at least one
more broad repo that it can prioritize:

- the main daemon/service and primary CLI or API surfaces above helper tools
- the main shared subsystem boundaries above packaging or support areas
- first reads that a WS6 author can follow with minimal human re-ranking

The current calibration therefore confirms the policy chosen in
`docs/decisions/ws6_structural_prepass_operating_mode_decision_2026-03-21.md`
rather than replacing it.
