# WS6 Structural Pre-pass Broad-Repo Ranking Refinement Note

Date: 2026-03-21

## Scope

This refinement stayed within the current `tools/ws6_structural_prepass.py`
tool. It did not introduce a separate broad-repo mode or companion tool.

Changes made:

- entrypoint scoring now recognizes directory-matched runtime files such as
  `cmd/tailscale/tailscale.go` and `cmd/tailscaled/tailscaled.go`
- entrypoint scoring now uses source-subtree density so broad repos prefer
  richer runtime surfaces over thin helper commands
- broad-repo `likely_first_read` selection now favors specific subsystem
  boundaries over generic buckets
- module-group selection now scores the full candidate set before trimming,
  instead of stopping early on the first eight groups encountered

## Required Broad-Repo Rerun

Target rerun: `tailscale/tailscale` from the B15 calibration set.

Direct comparison:

- `entrypoints` before:
  `cmd/addlicense/main.go`, `cmd/containerboot/main.go`,
  `cmd/get-authkey/main.go`, `cmd/k8s-nameserver/main.go`, ...
- `entrypoints` after:
  `cmd/tailscale/tailscale.go`, `cmd/tailscaled/tailscaled.go`,
  `cmd/tsconnect/tsconnect.go`, `cmd/proxy-test-server/proxy-test-server.go`, ...

- `orientation_hints.likely_first_read` before:
  `cmd/addlicense/main.go`, `cmd/containerboot/main.go`,
  `cmd/get-authkey/main.go`, `net`, `util`, `cmd`
- `orientation_hints.likely_first_read` after:
  `cmd/tailscale/tailscale.go`, `cmd/tailscaled/tailscaled.go`,
  `ipn`, `wgengine`, `cmd/tailscale`, `cmd/tsconnect/tsconnect.go`

- `orientation_hints.likely_runtime_surfaces` before:
  `cmd/addlicense/main.go`, `cmd/containerboot/main.go`,
  `cmd/get-authkey/main.go`, `cmd/k8s-nameserver/main.go`,
  `cmd/tsconnect/tsconfig.json`, `client/web/tsconfig.json`
- `orientation_hints.likely_runtime_surfaces` after:
  `cmd/tailscale/tailscale.go`, `cmd/tailscaled/tailscaled.go`,
  `cmd/tsconnect/tsconnect.go`, `cmd/proxy-test-server/proxy-test-server.go`,
  `cmd/tsconnect/tsconfig.json`, `client/web/tsconfig.json`

Boundary-cue improvement:

- the first-read list now starts with the primary CLI and daemon runtime files
- shared subsystem/package cues `ipn` and `wgengine` now appear in the
  first-read set
- helper/admin-style commands no longer outrank the primary runtime boundaries

Residual limit:

- broad repos can still surface some secondary runtime commands such as
  `cmd/tsconnect` or `cmd/proxy-test-server` in the runtime-surfaces list
  when those directories are structurally strong

## Regression Coverage

Regression checks used:

- unit regression suite:
  `python3 -m unittest tests.ws6_structural_prepass.test_ws6_structural_prepass`
- B15 rerun spot checks on:
  `airtable/airtable.js`
  `langchain-ai/deepagents`

Observed regression status:

- `airtable/airtable.js`: `likely_first_read` unchanged; `likely_runtime_surfaces`
  unchanged
- `langchain-ai/deepagents`: `likely_first_read` unchanged; runtime surfaces
  improved slightly by elevating `libs/acp/deepagents_acp/server.py` above
  `__init__.py`

## Conclusion

The current structural pre-pass still looks sufficient for this problem with
repo-shape-sensitive ranking refinements.

Why:

- the broad target improved on the exact weakness that blocked stronger
  confidence: primary runtime boundaries now outrank helper/admin surfaces
- easy and medium coverage did not show a first-read regression
- the remaining noise is now at the level of secondary runtime ordering inside
  a broad repo, not at the level of failing to identify where to read first

Based on this evidence, a separate broad-repo mode or companion pre-pass is not
yet justified. The current tool can handle the broad-repo case more cleanly
with targeted ranking refinements.
