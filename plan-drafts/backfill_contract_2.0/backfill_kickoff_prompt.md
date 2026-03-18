# Deep Narrative Backfill — Kickoff Prompt (Contract v2.0)

**Session type:** Deep narrative re-extraction / backfill  
**Branch:** `main`  
**Contract:** `contracts/deep_narrative_contract.md` (v2.0, Active)  
**Date:** 2026-03-18

---

## What this session does

You will rewrite or augment deep narrative YAML files for a target list of repos. These files already exist but are missing required behavioral coverage under the new contract (v2.0). You are not doing a full re-extraction from scratch — you are adding the missing sections to files that already have good structural content.

Read `AGENTS.md` at the repo root before doing anything else. Then read `contracts/deep_narrative_contract.md` in full. That contract is the authoritative spec for everything you produce.

---

## What changed (and why it matters)

The contract's Tier 1/2/3 section ranking has been replaced with **evidence families**. Under the old contract, `troubleshooting` was Tier 3 (optional). `supported_protocols` was Tier 3. `commands` / `common_tasks` were Tier 2. Agents following that contract correctly produced files that are almost entirely structural inventory (`has_component`, `has_config_option`).

Under v2.0:
- **Failures family** (`troubleshooting`) is **required** for `vector_database` and `inference_serving` archetypes
- **Protocols & Integrations family** (`supported_protocols` / `vpn_protocols`) is **required** for `tunneling` / `vpn_mesh` / `network_infrastructure` archetypes, and specifically must produce at least one `uses_protocol` fact

Your job is to add the missing families to the target files. Do not remove or rewrite existing sections unless they are incorrect. Append the missing sections.

---

## Target repo list

### Group A — Tunneling / vpn_mesh / network_infrastructure (missing `uses_protocol`)

These repos need a `supported_protocols:` or `vpn_protocols:` section added. Every entry must include a `name` and a `role` describing the repo's function with that protocol. A bare protocol name with no context produces a low-quality fact.

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

**Strong example** (from `repos/knowledge/deep/hiddify-app.yaml` — use as reference):
```yaml
supported_protocols:
  - name: WireGuard
    role: "server-side peer management and key exchange"
  - name: "SOCKS5"
    role: "outbound proxy endpoint exposed to local clients"
  - name: Shadowsocks
    role: "obfuscated proxy transport for censorship circumvention"
```

**Weak (do not write this):**
```yaml
supported_protocols:
  - name: TCP
  - name: HTTP
```

For tunneling tools, the relevant protocols are typically: the transport protocols they tunnel over (TCP, UDP, QUIC, WebSocket, HTTP/2), the proxy protocols they expose (SOCKS5, HTTP CONNECT), any VPN or obfuscation protocols they implement (WireGuard, Shadowsocks, Hysteria), and any authentication protocols they use.

---

### Group B — Vector databases (missing `has_failure_mode`)

These repos need a `troubleshooting:` section added. Every entry must have `symptom`, `cause`, and `fix`. Vague entries ("memory issues / not enough memory / add more memory") are worse than no entries — they produce facts no agent will usefully reach for.

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

**Strong example** (from `repos/knowledge/deep/vllm.yaml` — use as reference for quality):
```yaml
troubleshooting:
  - symptom: KV cache memory exhausted under high concurrency
    cause: "max_num_seqs exceeds available GPU memory for the KV cache allocation"
    fix: "Reduce max_num_seqs, decrease max_model_len, or increase swap_space"
```

For vector databases specifically, the operationally significant failure modes are typically:
- Memory/buffer pool exhaustion during indexing or large queries
- WAL checkpoint pressure under write-heavy workloads
- Index build timeout or failure for large collections
- Read-only mode enforcement when disk is full or WAL limit is reached
- Collection not loaded / not found errors from missing load step
- Dimension mismatch between stored vectors and query vectors
- Connection refused due to service not ready or port conflict

Ground these in the actual repo's architecture. For example, `ladybugdb__ladybug` has a WAL and a buffer pool — failure modes for those are documentable from the source. Don't invent failure modes that have no basis in the repo's design.

---

### Group C — Inference serving (missing `troubleshooting`)

```
lmdeploy              category: inference_serving
nexa_sdk              category: inference_serving
```

Same standard as Group B. Both repos already have `cli_commands` sections (Tasks ✓). They just need `troubleshooting` added. Use `repos/knowledge/deep/vllm.yaml` and `repos/knowledge/deep/ollama.yaml` as reference for what good inference-serving failure mode coverage looks like.

---

## How to work through each file

1. Read the shallow file at `repos/knowledge/repos/{file_stem}.yaml` — confirm `node_id`, `github_full_name`, `category`
2. Read the existing deep file at `repos/knowledge/deep/{file_stem}.yaml` — understand what's already there, don't duplicate it
3. Determine which families are missing based on the target group
4. Source the missing content:
   - Read `README.md` first — operational warnings, known limitations, quick-start commands
   - Read `docs/` if it exists — troubleshooting guides, operational runbooks
   - Read CLI help text or flag documentation for protocol/command coverage
   - Use training knowledge for well-known public repos where live source is unavailable — but be conservative; shorter accurate entries beat longer speculative ones
5. Append the missing section(s) to the existing deep file
6. Set `provenance.sourcing_method` — use `code_verified` if you read live source, `training_knowledge` if not. Update `provenance.as_of` to today's date.

---

## YAML quoting rule (critical)

Always quote string values that contain any of: `` ` `` `@` `[` `]` `{` `}` `:` `#`

Unquoted values containing these characters cause WS6 parse failures. When in doubt, quote the value.

**Wrong:**
```yaml
fix: Reduce max_num_seqs, decrease max_model_len, or increase swap_space
```

**Correct:**
```yaml
fix: "Reduce max_num_seqs, decrease max_model_len, or increase swap_space"
```

---

## What good output looks like

After your changes, each file should:

- Still pass all existing WS6 gates (don't break working sections)
- Have at least one recognized section from the required family for its archetype
- Have behavioral entries that meet the quality standard in the contract:
  - `troubleshooting`: concrete `symptom` / `cause` / `fix` triples, not vague descriptions
  - `supported_protocols`: `name` + `role` for each protocol, not bare names
- Have updated `provenance.as_of` and correct `provenance.sourcing_method`

---

## Reference files

| File | Why |
|---|---|
| `contracts/deep_narrative_contract.md` | Authoritative spec — read in full |
| `repos/knowledge/deep/vllm.yaml` | Best troubleshooting example in corpus |
| `repos/knowledge/deep/hiddify-app.yaml` | Best supported_protocols example in corpus |
| `repos/knowledge/deep/bore.yaml` | Reference small tunneling file (needs protocols added) |
| `repos/knowledge/deep/ladybugdb__ladybug.yaml` | Example vector_database file to augment |
| `AGENTS.md` | Read before any work |

---

## After you finish

Do not run the pipeline. Do not commit. The supervisor will review the files, run `run_batch.py`, verify WS6 gates pass and fact counts increase, then commit.

The key signal the supervisor is checking: `has_failure_mode` count was 78 before this backfill, `uses_protocol` was 47. Both numbers should move meaningfully after re-extraction.
