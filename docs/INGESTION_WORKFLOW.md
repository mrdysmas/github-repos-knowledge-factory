# Ingestion Workflow

**Version:** 1.0
**Created:** 2026-03-17
**Status:** Active

This document describes the end-to-end process for adding a new GitHub repo to
the knowledge base — from "here is a URL" to "facts are queryable." It is
written for agents and supervisors who need to execute or oversee an ingestion
without relying on prior session context.

Read `AGENTS.md` at the repo root before executing any steps.

---

## Overview

Every repo in the knowledge base passes through two phases:

1. **Shallow ingestion** — repo metadata, category, and core concepts are
   written to a canonical YAML file. This is handled by WS5 and WS4.
2. **Deep generation** — structured facts are extracted from the repo's source
   code and written to a deep YAML file. This is handled by WS6.

Both phases must complete before the read model reflects the repo. A repo that
has only completed shallow ingestion exists in the knowledge base but
contributes zero queryable facts.

The pipeline that executes both phases is:

```
WS5 → WS4 → clone prep → WS6 → WS7
```

`tools/run_batch.py` chains these stages from a single command and
enforces gate checks between stages. Use it for all ingestion runs.

---

## Step 1 — Register the repo

Run `add_repo_candidate.py` to register the new repo in `master_repo_list.yaml`
and refresh the intake queue:

```bash
python3 tools/add_repo_candidate.py \
  --workspace-root . \
  --github-url https://github.com/<owner>/<repo> \
  --category <category>
```

`--category` should match one of the existing category labels in the corpus.
Run `python3 tools/query_master.py --workspace-root . aggregate --group-by category`
to see the current category vocabulary.

This step writes to `master_repo_list.yaml` and regenerates
`inputs/intake/intake_queue.yaml`. It does not write to the WS5 manifest.

---

## Step 2 — Build the WS5 manifest entry

WS5 reads the manifest specified by the batch spec. The normal current pattern
is a batch-local manifest such as `inputs/ws5/<batch_id>_manifest.yaml`.
`inputs/ws5/ws5_input_manifest.yaml` remains the default/legacy path.

Create or update the manifest file manually or via an agent. Each manifest uses
the standard WS5 wrapper and a `repos:` list:

```yaml
artifact_type: ws5_remote_ingestion_input_manifest
contract_version: 1.0.0-ws1
defaults:
  target_shard: repos
  as_of: <current UTC date>
  source: remote_metadata
repos:
  - name: <short_name>
    github_full_name: <owner>/<repo>
    html_url: https://github.com/<owner>/<repo>
    target_shard: repos
    source: remote_metadata
    category: <category>
    summary: <one or two sentence description>
    core_concepts:
      - <concept 1>
      - <concept 2>
    key_entry_points:
      - README.md
      - <primary source directory>
    build_run:
      language: <primary language>
      build: See upstream README for project build steps.
      test: See upstream README for project test steps.
    as_of: <current UTC date>
    local_cache_dir: null
```

`local_cache_dir: null` keeps clone prep in remote-clone mode instead of
pointing at a pre-existing local cache. This is the standard mode for remote
ingestion.

Run the queue sync gate to confirm the manifest is coherent before proceeding:

```bash
python3 tools/check_intake_queue_sync.py --workspace-root .
```

This must pass before executing the pipeline.

---

## Step 3 — Clone the repos

`ws6_clone_prep.py` acquires source code for each repo in the manifest selected
by the batch spec before WS6 runs. In the normal path it is called
automatically by `run_batch.py`.

If any repo exceeds the `clone_size_limit_mb` threshold in `batch_spec.yaml`
(default: 500 MB), the tool halts with exit code 2 before cloning anything and
prints the offending repo and its size.

`tools/run_batch.py` does not expose `--force-large` on its documented main
path. For supervisor-approved oversized repos, use this exception path:

1. Run `tools/ws6_clone_prep.py` manually with `--force-large` against the same
   manifest you will use for the batch.
2. Then run `tools/run_batch.py` with `clone_size_limit_mb` set high enough for
   the run-batch clone-prep step to hit the already-cloned path instead of
   halting on size.

Example:

```bash
python3 tools/ws6_clone_prep.py \
  --workspace-root . \
  --manifest inputs/ws5/<batch_id>_manifest.yaml \
  --clone-workdir workspace/clones \
  --size-limit-mb <approved_limit_mb> \
  --batch-id <batch_id> \
  --force-large
```

The clone manifest is written to:

    reports/ws6_clone_prep/<batch_id>_clones.yaml

Deep file generation agents should read this file to locate source code. Do not
hardcode clone paths — always resolve them from the clone manifest.

Clones are retained by default after the pipeline completes. Set
`clone_cleanup: true` in `batch_spec.yaml` to remove them automatically.

### Optional: WS6 structural pre-pass

Current policy: the WS6 structural pre-pass is a `soft-optional` orientation
step, not a default batch step.

Decision rule: make a lightweight repo-shape judgment after clone prep. Run the
pre-pass after clone prep and before deep authoring when the repo looks broad,
multi-surface, polyglot, workspace-like, or otherwise noisy enough at the top
level that manual orientation is likely to cost extra reads. Skip it when the
repo is small, structurally obvious, or already easy to orient manually.

In practice, that usually means running it when one or more of these cues are
present:

- multiple sibling package roots or workspace manifests
- polyglot layout across multiple ecosystems
- several runtime surfaces such as API, worker, CLI, MCP, control plane, SDKs,
  or integrations
- large side areas like clients, docs, dev tooling, benchmarks, or built output
  that make first-read selection noisy

Command:

```bash
python3 tools/ws6_structural_prepass.py \
  --workspace-root . \
  --clone-manifest reports/ws6_clone_prep/<batch_id>_clones.yaml \
  --input-manifest inputs/ws5/<batch_id>_manifest.yaml
```

Outputs:

- `reports/ws6_structural_prepass/<batch_id>/<file_stem>.yaml`
- `reports/ws6_structural_prepass/<batch_id>/summary.yaml`

Do not treat the artifact as canonical. It is an orientation scaffold for WS6
authoring. For small or clearly single-package repos, skip this step unless a
supervisor explicitly wants the extra scaffold.

---

## Step 4 — Generate the deep YAML file

This is the most substantive step. Read `contracts/deep_narrative_contract.md`
in full before writing any content. That contract is the authoritative spec —
this section is a summary only.

**File location and naming:**

Deep files live in `repos/knowledge/deep/`. The filename stem uses `__` in
place of `/` in the GitHub full name:

```
owner/repo  →  repos/knowledge/deep/owner__repo.yaml
```

Read the shallow file at `repos/knowledge/repos/` to confirm the exact stem —
do not guess.

**Required header:**

Copy these fields exactly from the shallow file. Case matters.

```yaml
name: <name>
node_id: "repo::<github_full_name>"
github_full_name: <github_full_name>
html_url: <html_url>
source: remote_metadata
provenance:
  shard: repos
  source_file: repos/knowledge/deep/<file_stem>.yaml
  as_of: "<current UTC date>"
category: <category>
```

**Content:**

Use only recognized section names from the contract. The highest-yield
sections are: `architecture`, `configuration`, `implementation_patterns`,
`api_surface`, `key_features`, `key_files`, `core_modules`.

Ground every claim in actual source code. Do not invent file paths, function
names, or configuration keys. If a claim cannot be verified, leave it out — a
shorter accurate file produces better facts than a longer speculative one.

Quote any string value containing: `` ` `` `@` `[` `]` `{` `}` `:` `#`

Size guidance:
- Large repos (dify, qdrant, weaviate): 150–300 lines
- Medium repos (instructor, code-server): 100–200 lines
- Small repos (pgvector, voyager): 80–150 lines
- Tiny repos: 30–80 lines

Reference examples:
- Small: `repos/knowledge/deep/bore.yaml`
- Large: `repos/knowledge/deep/anything_llm.yaml`

**Sourcing:**

Deep file content must be grounded in source code from the local clone (see
Step 3). Sourcing requirements and training-knowledge fallback rules are defined
in `contracts/deep_narrative_contract.md` § Sourcing requirements.

---

## Step 5 — Run the pipeline

Create a `batch_spec.yaml` at the repo root (this file is gitignored; a
reference copy lives at `tools/batch_spec.example.yaml`):

```yaml
batch_id: <batch_id>
manifest: inputs/ws5/<batch_id>_manifest.yaml
clone_size_limit_mb: 500
gates:
  ws6_fail_on_any_false: true
  ws7_fail_on_any_non_pass: false
dry_run: false
```

Choose a batch ID that is unique and descriptive (e.g. `B9_myrepo`).

Batch-local manifests are the normal current pattern. Use
`inputs/ws5/ws5_input_manifest.yaml` only when you intentionally want the
default/legacy manifest path.

Run the pipeline:

```bash
python3 tools/run_batch.py --spec batch_spec.yaml --workspace-root .
```

Use `--dry-run` first to confirm the planned steps before executing:

```bash
python3 tools/run_batch.py --spec batch_spec.yaml --workspace-root . --dry-run
```

---

## Step 6 — Verify

Check the verdict file at `reports/run_batch/<batch_id>_verdict.yaml`. A
successful run looks like:

```yaml
result: ok
halted_at: null
ws6_gate_bools:
  deep_facts_parseable: true
  deep_fact_identity_coverage_100pct: true
  facts_with_evidence_100pct: true
  confidence_bounds_valid: true
  unmapped_deep_predicates_zero: true
  duplicate_fact_ids_zero: true
  execution_results_pending_zero: true
  ws6_hash_stable: true
ws7_gate_summary:
  snapshot_consistency: warn   # non-blocking — expected
  row_count_parity: pass
  orphan_edge_detection: pass
  query_parity: pass
  deterministic_rebuild: pass
exit_code: 0
```

`snapshot_consistency: warn` is expected and non-blocking (governed by D4).
Any `ws6_gate_bools` value of `false` is a blocking failure and must be
resolved before committing.

Confirm the fact count increased:

```bash
python3 tools/query_master.py --workspace-root . stats
```

The `deep_facts` count must be higher than the pre-run baseline.

---

## Step 7 — Commit

Commit the new files in two separate commits, following the established
batch commit pattern:

1. **Execution artifacts** — the new shallow file, deep file, deep_facts file,
   and any updated master artifacts (`master_index.yaml`, `master_graph.yaml`,
   `master_deep_facts.yaml`)
2. **Control-plane updates** — `project_status.yaml`,
   `phase_4_progress_tracker.yaml`, and any governance notes

Do not mix execution artifacts and control-plane updates in the same commit.

---

## Batch ingestion (multiple repos)

For batches of more than one repo, the process is the same but the manifest
entry and deep file generation steps are repeated per repo before running the
pipeline once. The orchestrator handles all repos in the manifest in a single
pass — there is no need to run the pipeline once per repo.

For large batches, sub-batch by tier to keep each run reviewable:
- T1: High-yield, architecturally rich repos
- T2: Moderate yield
- T3: Thin or documentation-only repos

Deep file generation for a large batch can be parallelized across agents
before any pipeline run — each deep file is independent.

---

## Reference

| Artifact | Purpose |
|---|---|
| `AGENTS.md` | Agent instruction file — read before any work |
| `contracts/deep_narrative_contract.md` | Deep YAML output contract — authoritative spec |
| `tools/add_repo_candidate.py` | Register new repo in master_repo_list |
| `tools/check_intake_queue_sync.py` | Preflight gate — run before pipeline |
| `inputs/ws5/<batch_id>_manifest.yaml` | WS5 input — normal current pattern; `inputs/ws5/ws5_input_manifest.yaml` is the default/legacy path |
| `tools/run_batch.py` | Pipeline orchestrator — single command for WS5→WS7 |
| `tools/batch_spec.example.yaml` | Reference batch spec |
| `tools/query_master.py` | Query the knowledge base (9 commands) |
| `tools/ws6_clone_prep.py` | Clones repos before WS6; writes clone manifest |
| `reports/ws6_clone_prep/` | Clone manifests from each batch run |
| `reports/run_batch/` | Verdict files from orchestrator runs |
| `project_status.yaml` | Current project state |

---

## Antipatterns

These are known failure modes from past batches. Treat them as hard stops,
not judgment calls.

**Do not add a manifest entry for a repo that already has a canonical shallow
file without reading that file first.**
WS5 will unconditionally overwrite an existing shallow file with
manifest-derived output. If the existing file has richer content (structured
core_concepts, named key_entry_points, ecosystem_connections, etc.), adding a
manifest entry will degrade it. Check: read the shallow file at
repos/knowledge/repos/<stem>.yaml before writing any manifest entry. If the
file is richer than the manifest entry you are about to write, the repo is
already ingested — skip the manifest step and proceed directly to writing the
deep file.

**Do not modify pipeline config thresholds during a run.**
clone_size_limit_mb, gate settings, and batch spec fields are set by the
supervisor before the run starts. If the clone step halts due to a size limit,
stop and report it — do not raise the threshold to unblock. The halt is
intentional. Escalate to the supervisor with the repo name and size, and wait
for explicit instruction.

**Do not resolve gate failures by modifying the artifacts being gated.**
If WS6 or WS7 report a mismatch between a deep file and its corresponding
shallow file, the correct response is to investigate why they diverged — not
to update one to match the other. A source mismatch between a deep file and a
shallow file usually means the shallow file was overwritten. Check git history
before modifying anything.
