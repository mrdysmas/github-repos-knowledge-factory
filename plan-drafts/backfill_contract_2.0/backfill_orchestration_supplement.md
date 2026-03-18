# Backfill Orchestration — Supplementary Context

**Read this before reading `backfill_kickoff_prompt.md`.**  
**Companion to:** `backfill_kickoff_prompt.md`  
**Date:** 2026-03-18

---

## Your role in this session

You are the orchestrator. You do not write deep narrative files yourself. You spawn subagents to do that work, review their output, and stop if something goes wrong.

The actual extraction work is defined in `backfill_kickoff_prompt.md`. Every subagent you spawn receives that prompt plus a scoped target list. Nothing else needs to change between subagents — the prompt is self-contained.

---

## Subagent sequence

Run three subagents, sequentially. Do not start the next subagent until the previous one completes and you have verified its output (see Verification below).

### Subagent 1 — Group A (tunneling / vpn_mesh / network_infrastructure)

Pass the full contents of `backfill_kickoff_prompt.md` with this target list substituted for the one in the prompt:

```
awesome-tunneling     category: tunneling
bore                  category: tunneling
cloudflared           category: network_infrastructure
frp                   category: tunneling
gost                  category: tunneling
headscale             category: vpn_mesh
hsync                 category: tunneling
hysteria              category: tunneling
mmar                  category: tunneling
nebula                category: vpn_mesh
pangolin              category: tunneling
rathole               category: tunneling
tailscale             category: vpn_mesh
tunnelite             category: tunneling
vgrok                 category: tunneling
ytunnel               category: tunneling
```

The missing family for all of these is **Protocols & Integrations** — specifically a `supported_protocols:` or `vpn_protocols:` section with `name` + `role` per entry.

### Subagent 2 — Group B (vector databases)

```
infinity              category: vector_database
ladybugdb__ladybug    category: vector_database
lancedb__lancedb      category: vector_database
ngt                   category: vector_database
qdrant__qdrant        category: vector_database
spotify__voyager      category: vector_database
unum-cloud__usearch   category: vector_database
weaviate__weaviate    category: vector_database
zilliztech__vectordbbench  category: vector_database
```

The missing family for all of these is **Failures** — specifically a `troubleshooting:` section with `symptom` / `cause` / `fix` triples.

### Subagent 3 — Group C (inference serving)

```
lmdeploy              category: inference_serving
nexa_sdk              category: inference_serving
```

Same missing family as Group B: **Failures** / `troubleshooting:`. Both files already have `cli_commands` sections — Tasks family is covered.

---

## What to pass each subagent

1. The full text of `backfill_kickoff_prompt.md` — unmodified except the target list
2. The scoped target list for their group (above)
3. This instruction: **"Make no changes to existing sections. Only append new top-level sections to each file. Do not run `run_batch.py`. Do not commit."**

That third point is critical. The existing sections in these files pass WS6 gates. A subagent that reformats or reorganizes existing YAML while appending can introduce parse errors that break previously clean files.

---

## Verification between subagents

After each subagent completes, before spawning the next one, run this check:

```bash
# Confirm files were modified (not left untouched)
git diff --name-only repos/knowledge/deep/

# Spot-check one file from the group — confirm the new section is present
# For Group A, look for supported_protocols: or vpn_protocols:
grep -l "supported_protocols:\|vpn_protocols:" repos/knowledge/deep/*.yaml

# For Groups B and C, look for troubleshooting:
grep -l "troubleshooting:" repos/knowledge/deep/*.yaml

# Quick YAML parse check — catches malformed output before it hits WS6
python3 -c "
import yaml, glob, sys
errors = []
for f in glob.glob('repos/knowledge/deep/*.yaml'):
    try:
        yaml.safe_load(open(f))
    except yaml.YAMLError as e:
        errors.append(f'{f}: {e}')
if errors:
    print('PARSE ERRORS:')
    for e in errors: print(e)
    sys.exit(1)
else:
    print('All deep files parse cleanly.')
"
```

If the YAML parse check fails, stop. Do not proceed to the next subagent. Identify which file is malformed, fix it, re-run the parse check, then continue.

If a file from the target list was not modified (missing from `git diff`), note it — the supervisor will review whether the subagent skipped it or determined it already had coverage.

---

## After all three subagents complete

Stop. Do not run the pipeline. Do not commit. Report back to the supervisor with:

1. Which files were modified (from `git diff --name-only`)
2. Whether the YAML parse check passed for all groups
3. Any files that were skipped or that produced errors
4. Any judgment calls the subagents made that you want the supervisor to review

The supervisor will run `run_batch.py`, verify WS6 gates, check that `has_failure_mode` and `uses_protocol` counts increased from their baselines (78 and 47 respectively), and then commit.

---

## What success looks like

- All 27 files modified
- All files parse cleanly
- No existing sections touched
- Each Group A file has at least one `supported_protocols:` or `vpn_protocols:` entry with `name` and `role`
- Each Group B/C file has at least one `troubleshooting:` entry with `symptom`, `cause`, and `fix`
- `provenance.as_of` updated to today's date in each modified file
