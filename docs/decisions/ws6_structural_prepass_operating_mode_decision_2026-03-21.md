# WS6 Structural Pre-Pass Operating Mode Decision (`github_repos-8e8`)

Date: 2026-03-21

## Decision

Recommendation: **soft-optional**

The WS6 structural pre-pass should be a recommended orientation step for
certain repo shapes, not a default step for all WS6 batches and not a
manual-only experiment.

## Evidence Reviewed

Inputs reviewed:

- `github_repos-9yt` prototype outcome in
  `docs/ws6_structural_prepass_prototype_note_2026-03-21.md`
- `github_repos-tl0` calibration outcome in
  `docs/ws6_structural_prepass_calibration_note_2026-03-21.md`
- `github_repos-sm6` refinement changes in commit `dda324c`
- B13 artifacts before and after refinement for:
  - `reports/ws6_structural_prepass/B13_ws6_prepass_calibration/getzep__graphiti.yaml`
  - `reports/ws6_structural_prepass/B13_ws6_prepass_calibration/vectorize-io__hindsight.yaml`

What the sequence shows:

- The prototype cleared the technical bar: cheap, deterministic, report-scoped,
  and non-canonical.
- Initial B13 calibration showed clear orientation value on `getzep/graphiti`
  and mixed-but-positive value on `vectorize-io/hindsight`.
- The refinement pass materially improved `hindsight` by removing obvious false
  first reads and inventory noise:
  - dropped `hindsight-dev/benchmarks/visualizer/main.py` from entrypoint and
    first-read output
  - stopped surfacing built output like
    `hindsight-clients/typescript/dist/index.js`
  - merged duplicate `hindsight_api` labeling into clearer module-group output
  - trimmed dependency output toward orientation-focused packages/modules

## Mode Evaluation

### 1. Default for all applicable WS6 batches

Do not adopt yet.

Why not:

- The evidence base is still only one refined two-repo calibration batch.
- The strongest value is on the broader repo shape, not on every repo shape.
- Small or single-package repos may not gain enough orientation value to justify
  another step and another report artifact.
- Default adoption would imply workflow expectations that are stronger than the
  current calibration supports.

### 2. Soft-optional for certain repo shapes

Adopt this now.

Why this clears the bar:

- The refined B13 output is now good enough to answer the three target
  questions on complex repos with lower manual orientation cost:
  - what kind of repo shape is this?
  - where should I read first?
  - what are the main runtime or package boundaries?
- The benefit is strongest exactly where manual orientation cost is highest:
  monorepos, multi-package workspaces, and repos with several runtime surfaces.
- Keeping it optional avoids forcing extra workflow and artifact overhead onto
  repos that are already easy to orient manually.

### 3. Experimental/manual only

Do not keep it here.

Why not:

- That would understate the current evidence.
- After `github_repos-sm6`, the pre-pass is past “interesting prototype only”
  status for complex repo shapes.
- Treating it as manual-only would slow useful adoption in the cases where it
  now clearly helps.

## Repo-Shape Cues

Operational wording future agents should follow:

- make a lightweight initial repo-shape judgment
- run the WS6 structural pre-pass if the repo appears broad, multi-surface,
  polyglot, workspace-like, or noisy at the top level in ways that are likely
  to make manual orientation slow
- skip it when the repo is small, structurally obvious, or easy to orient
  manually

Run the WS6 structural pre-pass when one or more of these cues are present:

- the repo is a multi-package or workspace-style layout with sibling manifests
  or package roots across multiple top-level directories
- the repo is polyglot or mixes several build ecosystems, for example Python
  plus TypeScript, Go, or Rust
- the top-level tree suggests multiple product/runtime surfaces such as API,
  worker, CLI, MCP server, control plane, SDKs, or integrations
- the repo mixes product code with large side areas like clients,
  integrations, docs, dev tooling, benchmarks, or generated/build outputs, so
  manual first-read selection is likely to be noisy

Leave it optional or skip it when the repo is easy to orient manually, such as:

- a small or medium single-package repo with one obvious runtime surface
- a repo where README plus one clear package root already answers the three
  orientation questions quickly

## Calibration Plan For Promotion To Default

Before promoting `soft-optional` to `default`, gather evidence from at least one
additional bounded calibration set that includes all of these shapes:

- easy single-package repos
- medium repos with 2-3 runtime surfaces
- broad monorepos or polyglot workspaces

Promotion criteria:

- the pre-pass consistently improves first-read selection, not just repo-shape
  labeling
- noisy first-read paths, build outputs, and support/dev surfaces remain rare
  across the sample
- authors report lower orientation effort without confusion about whether the
  artifact is canonical
- maintenance remains low: no frequent per-repo overrides and no pressure to
  widen scope beyond structural orientation

If those conditions are not met, keep the policy at `soft-optional`.

## Runbook Impact

Runbook update required and applied:

- `docs/INGESTION_WORKFLOW.md` now records the current policy:
  the structural pre-pass sits after clone prep as a soft-optional step for
  complex repo shapes and is not part of the default `run_batch.py` path.
