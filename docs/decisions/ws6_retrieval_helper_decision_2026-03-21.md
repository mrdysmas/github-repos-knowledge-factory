# WS6 Retrieval Helper Decision (`github_repos-5n8`)

Decision date (UTC): 2026-03-21T06:00:00Z

## Decision

Do not adopt a Kodit-style retrieval/indexing helper as a standard WS6 dependency now.

Recommend **prototype later**, after the first narrow WS6 structural pre-pass direction is fixed.

For current planning, treat a Kodit-style tool as:

- an optional retrieval helper for orientation and evidence-finding
- non-canonical
- outside the required `WS5 -> WS4 -> WS6 -> WS7` path

Do not treat it as:

- the source of truth
- the first implementation of `ws6_structural_prepass`
- a replacement for direct source/document review
- a reason to widen the ontology around parser-shaped or graph-shaped facts

## Intended Role

If used later, the helper's role should stay narrow:

- speed up finding relevant files, manifests, entrypoints, and code snippets in a checked-out repo
- help agents retrieve concrete evidence paths faster during WS6 deep authoring
- optionally support targeted structural orientation in larger or more modular repos

It should not:

- emit canonical facts directly
- define the artifact schema for the pre-pass
- become a required runtime service for normal batch execution

This keeps the trust boundary intact: canonical facts still come from WS6 with explicit provenance.

## Why

The current repo direction already says the first useful pre-pass slice should be cheap, deterministic, and reversible:

- read clone paths from the existing clone manifest
- scan filesystem shape and language manifests
- identify package roots and entrypoints
- emit a narrow non-canonical orientation artifact

That target is smaller than Kodit's natural operating model.

As of 2026-03-21, Kodit's official docs and GitHub README position it as a code-indexing MCP server with:

- repository indexing for local and remote repos
- keyword and semantic search
- Tree-sitter-based code slicing
- dependency tracking and call-graph generation
- periodic sync and assistant integrations

Those are real strengths, but they also imply an extra indexing/search subsystem with its own setup, sync, and trust-shaping behavior.

For this project, the main risks are:

1. **System complexity too early**
   The first WS6 structural pre-pass question is still about the artifact contract and the signal ladder, not about search infrastructure.

2. **False confidence**
   A strong snippet-retrieval layer can make a repo feel "understood" before behavioral evidence is actually gathered.

3. **Ontology drift**
   If the helper is adopted before the contract is narrow and explicit, there is pressure to mirror the tool's AST/call-graph view in canonical facts.

4. **Workflow coupling**
   `run_batch.py` and the current pipeline assume local scripts over repo artifacts, not a continuously available indexing service.

The result is: Kodit looks plausible as a later complement, but it is not the right first move for WS6 stabilization.

## Concrete Pain Point To Benchmark

The benchmark target should be:

- reducing time spent locating repo entrypoints, module roots, routing/config surfaces, and likely runtime boundaries before deep authoring starts

This is the right pain point because it tests orientation and evidence-finding, not generic "search feels better" impressions.

## Small Evaluation Design

Run one bounded comparison on a larger modular repo already processed through clone prep.

### Baseline

Use current workflow only:

- clone manifest
- local filesystem inspection
- `rg`
- targeted file reads

### Treatment

Repeat the same orientation task with a Kodit-style helper available, but keep the usage narrow:

- file/manifests/entrypoint discovery
- targeted snippet retrieval
- no direct canonical fact generation
- no graph-native escalation unless the simple helper clearly fails

### Task

For the same repo, produce an orientation packet containing:

- package roots
- likely entrypoints
- likely runtime surfaces
- likely module groups
- evidence paths for each claim

### Compare

Measure:

1. time to produce the packet
2. number of correct claims with usable evidence paths
3. number of noisy or misleading structural claims
4. whether the helper reduces orientation effort enough to leave more attention for behavioral evidence

### Success Threshold

Prototype adoption is justified only if the helper:

- materially reduces orientation time
- does not increase noisy structural overproduction
- does not pressure the workflow toward tool-shaped canonical facts
- works as an optional aid rather than a required subsystem

If those conditions are not met, prefer a repo-local pre-pass script over external indexing.

## Recommendation For `github_repos-kfk`

The pre-pass artifact contract should proceed on the assumption that:

- the artifact can be generated without Kodit
- helper-tool support is optional and additive
- fields should be grounded first in filesystem, manifests, entrypoints, config/routing, and imports
- AST- or graph-derived enrichment remains conditional

That keeps `github_repos-kfk` unblocked by infrastructure choices while still leaving room for later helper-assisted evidence retrieval.

## Sources

- Local design note: `docs/ws6_structural_prepass_sketch_2026-03-20.md`
- Local architecture note: `docs/ground_up_architecture_proposal_2026-03-19.md`
- Kodit docs: https://docs.helix.ml/kodit/getting-started/quick-start/
- Kodit GitHub README: https://github.com/helixml/kodit
