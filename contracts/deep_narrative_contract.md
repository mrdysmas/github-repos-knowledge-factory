# Deep Narrative Generation Contract

**Version:** 2.1
**Created:** 2026-03-18
**Status:** Active — governs all deep narrative YAML production for WS6 extraction.

This document defines the output contract for deep narrative YAML files. Any agent producing deep narratives must follow this contract. WS6 (`tools/ws6_deep_integrator.py`) consumes these files and extracts structured facts from them. If the narrative doesn't follow this contract, WS6 either skips the content (unmapped section) or fails (parse error).

This is not a style guide. It is an interface specification between narrative generation and fact extraction. It also defines what the post-generation soft audit checks.

### What changed from v1.2

The Tier 1/2/3 section ranking is replaced entirely. That system ranked sections by extraction ease, which caused structural inventory (`has_component`, `has_config_option`) to dominate the corpus at the expense of operationally useful facts (`has_failure_mode`, `supports_task`, `uses_protocol`). v2.0 replaces tiers with two things:

1. **Evidence families** — four named families that group sections by the kind of knowledge they produce. Every deep narrative is evaluated against families, not a tier ranking.
2. **Archetype requirements** — five repo archetypes (`inference_serving`, `vector_database`, `tunneling`, `agent_framework`, `agent_cli`) each have required evidence families. A compliant file for those archetypes must cover those families. All other repos follow global defaults.

The header fields, YAML quoting rules, section shapes, and sourcing requirements are unchanged from v1.2.

---

## Pipeline Context

The deep narrative is the bridge between raw source code and structured facts:

```
Source code (local clone) → [agent reads code] → deep narrative YAML → WS6 extraction → canonical facts
```

WS5 and WS4 handle shallow ingestion and compilation. They don't depend on deep narratives. Deep narratives are consumed exclusively by WS6.

Deep narrative generation is an LLM task — it requires reading and understanding source code. It cannot be fully automated. This contract defines the output shape so the extraction step is deterministic.

---

## File Location and Naming

Deep narratives live in `repos/knowledge/deep/`. The filename must use the `file_stem` from the repo's shallow file with a `.yaml` extension.

```
repos/knowledge/deep/{file_stem}.yaml
```

The `file_stem` follows the pattern `owner__repo` with the GitHub `/` replaced by `__`. Examples:

- `tmux/tmux` → `tmux__tmux.yaml`
- `sharkdp/bat` → `sharkdp__bat.yaml`
- `FlowiseAI/Flowise` → `flowiseai__flowise.yaml`

Match the existing shallow file's stem exactly. Don't guess — read it from the shallow file at `repos/knowledge/repos/{file_stem}.yaml`.

---

## Required Header Fields

Every deep narrative must start with these identity fields. They tie the deep file to its shallow counterpart and tell WS6 which repo this narrative describes.

```yaml
name: bore
node_id: "repo::ekzhang/bore"
github_full_name: ekzhang/bore
html_url: https://github.com/ekzhang/bore
source: remote_metadata
provenance:
  shard: repos
  source_file: repos/knowledge/deep/bore.yaml
  as_of: "2026-03-18"
  sourcing_method: code_verified        # or training_knowledge
  extraction_model: claude-opus-4-6    # optional
  extraction_agent: codex              # optional
directory: bore-main
category: tunneling
```

### Matching Rules

These rules are non-negotiable. Violating them causes WS4 or WS1 gate failures.

- `node_id` must match the shallow file character-for-character. Copy it, don't retype it.
- `github_full_name` must match the shallow file character-for-character. Case matters (`FlowiseAI/Flowise` ≠ `flowiseai/flowise`).
- `html_url` must match the shallow file character-for-character. Same casing rule.
- `source` must match the shallow file's `source` field. For repos ingested via WS5, this is typically `remote_metadata`. Read it from the shallow file.
- `provenance.shard` is the canonical shard name (`repos`).
- `provenance.source_file` is the path to this deep file relative to the repo root.
- `provenance.as_of` is the current UTC date.
- `provenance.sourcing_method` records whether the narrative was generated from verified code or training knowledge.
- `provenance.extraction_model` is optional. Records the model identifier (e.g. `claude-opus-4-6`). Omit if unknown.
- `provenance.extraction_agent` is optional. Records the invoking agent or tool (e.g. `codex`). Omit if unknown.
- `directory` should match the shallow file's `directory` field.
- `category` should match the shallow file's `category` field.

**Before writing a deep narrative, always read the corresponding shallow file and copy these fields exactly.**

---

## YAML Quoting Rules

YAML is sensitive to special characters in unquoted (plain scalar) values. The following characters break parsing if they appear in unquoted strings.

**Always wrap string values in double quotes if they contain any of:**

| Character | Why it breaks |
|-----------|--------------|
| `` ` `` (backtick) | Common in code references, can confuse some parsers |
| `@` | YAML tag indicator |
| `[` or `]` | YAML flow sequence |
| `{` or `}` | YAML flow mapping |
| `:` | YAML key-value separator |
| `#` | YAML comment |

Example — wrong:

```yaml
description: Uses @Injectable decorator and [optional] params
```

Example — correct:

```yaml
description: "Uses @Injectable decorator and [optional] params"
```

When in doubt, quote the value. Quoting a value that doesn't need it is harmless. Not quoting a value that needs it causes a parse failure and blocks the pipeline.

---

## Evidence Families

Every recognized section belongs to one of four evidence families. The families define what kind of knowledge a deep narrative is expected to produce, and they are the unit used in archetype requirements and the soft audit.

### Family 1 — Structure

**What it covers:** What the repo is made of and how it is configured.

**Predicates produced:** `has_component`, `has_config_option`

**Sections:** `architecture`, `configuration`, `cli_arguments`, `environment` / `environment_variables`, `key_features`, `key_files`, `core_modules`, `tech_stack` / `technology_stack`, `ports`, `primary_language`, `languages`, `type`

Structure is the easiest family to populate and is expected in every deep narrative. It should not crowd out the other families. Write it efficiently — a few well-chosen components and configuration options are more useful than an exhaustive inventory.

---

### Family 2 — Tasks

**What it covers:** What the repo can be directed to do. Discrete operations, workflows, and CLI interactions.

**Predicates produced:** `supports_task`

**Sections:** `commands` / `cli_commands`, `common_tasks`, `procedures`, `quick_reference`

Tasks are the primary interface between a repo and an agent that wants to use it. Every repo that has a CLI, a meaningful workflow, or documented operational patterns should have Tasks coverage. A debugging agent asking "what can this tool do?" is querying this family.

`quick_reference` counts toward Tasks family coverage, but only when entries describe actionable operations — serving commands, workflow steps, common invocations. A `quick_reference` limited to lookup values ("Default port: 8080", "Config path: ~/.config/...") does not satisfy Tasks intent. When using `quick_reference` as the primary Tasks section, ensure it contains command-oriented entries with enough description to be agent-discoverable.

---

### Family 3 — Failures

**What it covers:** What can go wrong, why, and how to recover.

**Predicates produced:** `has_failure_mode`

**Sections:** `troubleshooting`

Failures are the highest-value family for planning and debugging use cases. They are also the most under-represented in the current corpus. A `troubleshooting` section with five concrete symptom/cause/fix entries produces five `has_failure_mode` facts that a debugging agent can directly surface. Treat this section as first-class, not optional.

---

### Family 4 — Protocols & Integrations

**What it covers:** How the repo speaks to other systems — protocols it implements, APIs it exposes, extension points it defines, and external systems it integrates with.

**Predicates produced:** `uses_protocol`, `exposes_api_endpoint`, `has_extension_point`

**Sections:** `supported_protocols` / `vpn_protocols` / `api_protocols`, `api_surface`, `api_structure`, `integrations`, `extension_points`, `sdk_usage`, `cross_references`

This family is mandatory for any repo whose primary function involves network communication, data exchange, or pluggable architecture. For network tools, this family is as important as Structure.

---

### Cross-cutting sections

Some sections span families or produce `implements_pattern`, which doesn't map cleanly to a single family:

- `code_patterns` / `implementation_patterns` → `implements_pattern`
- `testing` → `implements_pattern` (test structure), `supports_task` (test commands)

These sections are valuable and should be included when the repo has substantive content for them. They are not assigned to a family requirement but count toward overall predicate coverage.

---

## Archetype Requirements

Three repo archetypes have required evidence families. A deep narrative for a repo in one of these archetypes is considered behaviorally thin if it is missing a required family. The soft audit flags thin files — it does not block ingestion.

For archetypes not listed here, the global default applies: Family 1 (Structure) is expected; all other families are optional but encouraged.

---

### Archetype: `inference_serving`

Categories: `inference_serving`

| Family | Requirement |
|---|---|
| Structure | Required |
| Tasks | Required |
| Failures | Required |
| Protocols & Integrations | Recommended |

**Rationale:** Inference servers have discrete serving commands, known operational failure modes (memory pressure, CUDA errors, concurrency limits), and expose APIs. A file lacking Tasks or Failures for this archetype is missing its highest-value content. `inference_serving` is currently the only category with meaningful `has_failure_mode` coverage — use those files as positive examples.

**Reference files:**
- `repos/knowledge/deep/vllm.yaml` — strong Failures coverage via `troubleshooting:`
- `repos/knowledge/deep/ollama.yaml` — good Tasks coverage

---

### Archetype: `vector_database`

Categories: `vector_database`, `vector_databases`

> **Note:** Both category strings are active in the corpus. `vector_databases` (plural) is a legacy inconsistency affecting at least `milvus-io/milvus`. Both are treated identically by the soft audit.

| Family | Requirement |
|---|---|
| Structure | Required |
| Failures | Required |
| Tasks | Recommended |
| Protocols & Integrations | Recommended |

**Rationale:** Databases have operationally significant failure modes — buffer pool sizing, WAL checkpoint pressure, transaction gate enforcement, read-only path behavior. These are the facts that distinguish a database entry in the knowledge base from a generic component inventory. Currently zero `vector_database` repos have `has_failure_mode` coverage. Every vector database file should include a `troubleshooting:` section grounded in the database's known operational constraints.

**Reference files:**
- `repos/knowledge/deep/ladybugdb__ladybug.yaml` — example of what to improve: good Structure, zero Failures
- `repos/knowledge/deep/milvus.yaml` — has some failure coverage to learn from

---

### Archetype: `tunneling`

Categories: `tunneling`, `vpn_mesh`, `network_infrastructure`

| Family | Requirement |
|---|---|
| Structure | Required |
| Protocols & Integrations | Required |
| Failures | Recommended |
| Tasks | Recommended |

**Rationale:** Tunneling and network tools implement protocols by definition. Currently nine tunneling repos have zero `uses_protocol` facts — the worst coverage gap in the corpus by category. A tunneling deep file that doesn't name the protocols the tool speaks is not useful for cross-repo protocol discovery. Every network tool should have a `supported_protocols:` or `vpn_protocols:` section naming each protocol and the repo's role in it.

**Audit enforcement note:** The Protocols & Integrations family includes sections like `extension_points` and `cross_references` that produce `has_extension_point`, not `uses_protocol`. For the tunneling archetype specifically, the soft audit must check for at least one `uses_protocol` fact — family presence alone is not sufficient. A tunneling repo that satisfies the family requirement through extension point entries only is still flagged as `behavioral_coverage: thin`.

**Reference files:**
- `repos/knowledge/deep/bore.yaml` — small, balanced, good reference shape
- `repos/knowledge/deep/hiddify-app.yaml` — strong `supported_protocols:` coverage

---

### Archetype: `agent_framework`

Categories: `agent_framework`, `agent_frameworks`, `agent_orchestration`

> **Note:** `agent_frameworks` (plural) and `agent_orchestration` are legacy label variants. All three are treated identically by the soft audit. Use `agent_framework` for new repos.

| Family | Requirement |
|---|---|
| Structure | Required |
| Tasks | Required |
| Failures | Recommended |
| Protocols & Integrations | Recommended |

**Rationale:** Agent frameworks are used by building on top of them. A file that inventories components without describing how to configure, invoke, or extend the framework answers the wrong question. Tasks coverage — how do you run an agent, what are the key invocation patterns, what configuration surfaces the important behaviors — is the primary interface for an agent trying to use this framework. Failures are recommended because framework-level error behaviors vary significantly across repos; document them when they are concrete and observable.

**Reference files:**
- `repos/knowledge/deep/pydantic__pydantic-ai.yaml` — strongest Tasks coverage in group (14 facts)
- `repos/knowledge/deep/ruvnet__claude-flow.yaml` — broad section coverage
- For Failures format: `repos/knowledge/deep/vllm.yaml` — `troubleshooting:` with concrete symptom/cause/fix entries

---

### Archetype: `agent_cli`

Categories: `agent_cli`

| Family | Requirement |
|---|---|
| Structure | Required |
| Tasks | Required |
| Failures | Required |
| Protocols & Integrations | Recommended |

**Rationale:** CLI tools are invoked, not extended. A file that inventories components without documenting commands, flags, and error behaviors is nearly useless for an agent that needs to know how to run the tool. Tasks coverage (`commands`, `cli_commands`, `cli_arguments`) is mandatory. Failures are equally required: CLI tools have concrete, agent-discoverable error modes — authentication failures, missing config, rate limiting, connectivity issues — that planning and debugging agents directly query for. A CLI file without Failures coverage is missing its second most valuable content.

**Reference files:**
- `repos/knowledge/deep/abhigyanpatwari__gitnexus.yaml` — strongest Tasks coverage in group (23 facts)
- `repos/knowledge/deep/anthropics__claude-code.yaml` — broad section coverage
- For Failures format: `repos/knowledge/deep/vllm.yaml` — `troubleshooting:` with concrete symptom/cause/fix entries

---

## Behavioral Entry Standards

Structural sections (Family 1) are relatively forgiving — a list of modules or config keys is useful even without much context. Behavioral sections (Families 2, 3, 4) are not. A weak behavioral entry produces a fact that no agent will usefully reach for. A strong one produces a fact that directly answers a planning or debugging query.

These standards apply to all behavioral sections.

### troubleshooting — Failures family

Each entry must name a concrete failure mode, not a vague pain point.

**Required fields:** `symptom`, `cause`, `fix`

**Strong entry:**
```yaml
troubleshooting:
  - symptom: KV cache memory exhausted under high concurrency
    cause: "max_num_seqs exceeds available GPU memory for the KV cache allocation"
    fix: "Reduce max_num_seqs, decrease max_model_len, or increase swap_space"
```

**Weak entry (do not write this):**
```yaml
troubleshooting:
  - symptom: Memory issues
    cause: Not enough memory
    fix: Add more memory
```

The symptom should be the error condition an operator would actually observe. The cause should name the specific mechanism. The fix should be actionable — a flag, a config key, a specific mitigation.

If a repo has a troubleshooting doc, read it. If it has known operational constraints documented in its README or issue tracker, those are valid sources. Don't invent failure modes that aren't documented — but don't leave `troubleshooting:` empty because the source code doesn't have a dedicated troubleshooting file. README warnings, known limitations sections, and operational notes all count.

---

### commands / common_tasks / procedures — Tasks family

Each entry must name the task and its operational purpose, not just the command string.

**Required fields:** `name`, `description`

**Strong entry:**
```yaml
commands:
  - name: "vllm serve"
    description: "Launch an OpenAI-compatible inference server for a local or HuggingFace model"
    usage: "vllm serve <model-name> --host 0.0.0.0 --port 8000"
  - name: "borg create"
    description: "Create a deduplicated, compressed backup archive from a source path"
    usage: "borg create /path/to/repo::archive-name /source/path"
```

**Weak entry (do not write this):**
```yaml
commands:
  - name: run
    description: Runs the application
```

The description should tell an agent why it would invoke this command, not just confirm it exists. Think of it as answering: "if an agent is trying to accomplish X, would this entry help it find the right command?"

---

### supported_protocols / vpn_protocols / api_protocols — Protocols & Integrations family

Each entry must name the protocol and the repo's role in it.

**Required fields:** `name` (minimum); `role` or `context` strongly recommended

**Strong entry:**
```yaml
supported_protocols:
  - name: WireGuard
    role: server-side peer management and key exchange
  - name: "SOCKS5"
    role: outbound proxy endpoint exposed to local clients
  - name: "gRPC"
    role: primary inter-service communication protocol
```

**Weak entry (do not write this):**
```yaml
supported_protocols:
  - name: WireGuard
  - name: HTTP
```

A bare protocol name without context is nearly useless for cross-repo discovery. "This repo uses HTTP" describes almost everything. "This repo exposes an HTTP/REST API for model inference with OpenAI-compatible endpoints" is a fact worth storing.

---

## Source Selection Strategy

Behavioral sections require reading different sources than structural sections. Before writing any behavioral content, prioritize these sources in order:

1. **README** — operational warnings, known limitations, quick-start commands
2. **docs/** — troubleshooting guides, operational runbooks, deployment notes
3. **CLI help text** (`--help` output or documented flags) — task and command coverage
4. **Test files** — integration tests often reveal how the system is actually operated
5. **Known limitations and documented issues** — README warnings, "known issues" sections, and operational notes checked into the repo often encode real failure modes. This means content committed to the repo itself, not live issue tracker browsing.
6. **Config files and examples** — protocol names, integration endpoints, environment requirements
7. **Source code** — for structural sections; less reliable for behavioral sections unless the code has inline documentation

Do not default to reading source code first for behavioral sections. Source code is the right starting point for component inventory. For tasks, failures, and protocols, the documentation layer is more reliable and more directly useful.

---

## Section Reference

All sections recognized by WS6. Any top-level key not in the identity/ignored lists and not in this reference becomes an unmapped section — it produces no facts and adds noise to the mismatch report.

### Identity Keys (skipped by WS6)

Required in the header but produce no facts:

`name`, `node_id`, `github_full_name`, `html_url`, `source`, `provenance`

### Ignored Keys (skipped by WS6)

Allowed but not extracted:

`sparse`, `directory`, `category`, `summary`, `description`, `notes`, `metadata`

### Recognized Sections by Family

**Structure family:**
`architecture`, `configuration`, `cli_arguments`, `environment` / `environment_variables`, `key_features`, `key_files`, `core_modules`, `tech_stack` / `technology_stack`, `ports`, `type`, `primary_language`, `languages`

**Tasks family:**
`commands` / `cli_commands`, `common_tasks`, `procedures`, `quick_reference`

**Failures family:**
`troubleshooting`

**Protocols & Integrations family:**
`supported_protocols` / `vpn_protocols` / `api_protocols`, `api_surface`, `api_structure`, `integrations`, `extension_points`, `sdk_usage`, `cross_references`

**Cross-cutting (implements_pattern):**
`code_patterns` / `implementation_patterns`, `testing`

**Remaining recognized sections:**
`key_sections`, `content_coverage`, `supplementary_files`, `related_repos`

---

## Expected Shapes Per Section

Each section has a specific YAML shape that WS6 knows how to parse. If the shape is wrong, WS6 silently skips it — no crash, but no facts either.

### architecture

Supports three sub-structures, any or all of which can be present.

```yaml
architecture:
  module_breakdown:
    - module: src/client.rs
      responsibility: "Handles client connections"
      key_files: [src/client.rs]
    - module: src/server.rs
      responsibility: "Manages server state"
      key_files: [src/server.rs]

  key_abstractions:
    - name: ConnectionPool
      purpose: "Manages reusable TCP connections"
    - name: MessageCodec
      purpose: "Encodes/decodes wire protocol messages"

  components:
    - name: API Server
      description: "Express HTTP server handling REST endpoints"
    - name: Worker Pool
      description: "Background job processing with Redis queue"

  data_flow: |
    Optional free-text. Ignored by WS6 but useful for narrative context.
```

Each entry in `module_breakdown` needs at least `module` or `key_files`. Each entry in `key_abstractions` needs `name`. Each entry in `components` needs `name`.

### code_patterns / implementation_patterns

Both use the same extractor.

```yaml
code_patterns:
  - pattern: Factory Pattern
    description: "Creates provider instances based on config"
    location: src/factory.py:45
  - pattern: Observer Pattern
    description: "Event-driven plugin notification"
    location: src/events.py:120
```

Each entry needs at least `pattern` (or `name` or `title`).

### configuration

Supports flat lists, nested groups, and dict-shaped options.

```yaml
# Flat list
configuration:
  - key: max_connections
    type: integer
    default: "100"
    description: "Maximum concurrent connections"

# Grouped
configuration:
  server:
    options:
      - key: bind_address
        default: "0.0.0.0"
        description: "Address to bind"
```

Each option needs at least `key` (or `name`).

### cli_arguments

```yaml
cli_arguments:
  - flag: "--verbose"
    description: "Enable verbose output"
    default: "false"
  - flag: "--output"
    description: "Output file path"
```

Each entry needs at least `flag` (or `name`).

### api_surface

```yaml
api_surface:
  public_functions:
    - name: "Client.connect"
      purpose: "Establish connection to server"
      signature: "pub async fn connect(addr: &str) -> Result<Self>"
      location: src/client.rs

  endpoints:
    - path: /api/v1/users
      method: GET
      description: "List all users"
```

**Quality rule:** Only list genuinely public/exported symbols in `public_functions`. Do not include private/internal functions.

### key_features

```yaml
key_features:
  - "Syntax highlighting for 100+ languages"
  - "Git integration shows file modifications"

# Or as dicts:
key_features:
  - feature: "Syntax highlighting"
    description: "Supports 100+ languages via syntect"
```

### key_files

```yaml
key_files:
  - path: src/main.rs
    purpose: "CLI entry point"
  - path: Cargo.toml
    purpose: "Workspace and dependency configuration"
```

Each entry needs at least `path` (or `name` or `file`).

### core_modules

```yaml
core_modules:
  modules:
    - name: parser
      path: src/parser/
      purpose: "Markdown parsing and AST generation"
```

### environment / environment_variables

```yaml
environment:
  required:
    - key: DATABASE_URL
      description: "PostgreSQL connection string"
  optional:
    - key: LOG_LEVEL
      default: "info"
      description: "Logging verbosity"

# Or flat list:
environment_variables:
  - key: API_KEY
    description: "Authentication key"
```

### tech_stack / technology_stack

```yaml
tech_stack:
  - name: Rust
    role: "Primary language"
  - name: Tokio
    role: "Async runtime"
```

### testing

```yaml
testing:
  framework: pytest
  patterns:
    - name: "Integration tests"
      location: tests/integration/
      description: "End-to-end API tests"
  key_files:
    - tests/conftest.py
```

### extension_points

```yaml
extension_points:
  - name: "Plugin interface"
    location: src/plugins/mod.rs
    hook: "trait Plugin"
    example: "impl Plugin for MyPlugin"
```

### commands / cli_commands / common_tasks / procedures

All use the same extractor. See Behavioral Entry Standards above for quality guidance.

```yaml
commands:
  - name: "borg create"
    description: "Create a deduplicated backup archive from a source path"
    usage: "borg create /path/to/repo::archive-name /source/path"
```

### quick_reference

```yaml
quick_reference:
  - name: "Default port"
    value: "8080"
  - name: "Config file location"
    value: "~/.config/app/config.toml"
```

### troubleshooting

See Behavioral Entry Standards above for quality guidance. The `symptom` / `cause` / `fix` shape is required.

```yaml
troubleshooting:
  - symptom: OutOfMemoryError during model loading
    cause: "Model too large for GPU memory given current gpu_memory_utilization setting"
    fix: "Reduce gpu_memory_utilization, use quantization, or increase tensor_parallel_size"
```

### supported_protocols / vpn_protocols / api_protocols

See Behavioral Entry Standards above for quality guidance.

```yaml
supported_protocols:
  - name: WireGuard
    role: "server-side peer management and key exchange"
  - name: "SOCKS5"
    role: "outbound proxy endpoint exposed to local clients"
```

### Remaining Sections

`cross_references`, `key_sections`, `content_coverage`, `supplementary_files`, `integrations`, `sdk_usage`, `ports`, `related_repos`, `api_structure`, `type`, `primary_language`, `languages` — follow similar list-of-dicts or simple-value patterns. If unsure of the shape, look at the corresponding `extract_*` function in `tools/ws6_deep_integrator.py`.

---

## Quality Guidelines

### Ground everything in source code

Every claim in a deep narrative must be verifiable against the repo's actual source code or documentation. Do not:

- Invent file paths that don't exist in the repo
- Describe functions or methods that aren't in the source
- Attribute behavior to the project that you haven't confirmed

If you're unsure whether something exists, leave it out. A shorter, accurate narrative produces fewer but trustworthy facts.

### Don't pad small repos

Some repos are genuinely small or simple. A <500 LOC CLI tool might produce a 50-line narrative. That's correct. Don't inflate the narrative with speculative content just to satisfy family coverage — if a small tool has no meaningful failure modes documented, leave `troubleshooting:` out rather than invent entries.

### Size guidance

- Large repos (wezterm, hugo, vllm): 150–300 lines
- Medium repos (tmux, capistrano, borg): 100–200 lines
- Small repos (bore, pgvector, annoy): 80–150 lines
- Tiny repos (glm, 1loc): 30–80 lines

These are guidelines, not targets.

### Sourcing requirements

Deep file content must be grounded in actual source code. The standard method is to read from the local clone provided by the `ws6_clone_prep` step. The clone path for each repo is available in the batch's clone manifest at `reports/ws6_clone_prep/<batch_id>_clones.yaml`.

**Training knowledge as fallback**

Training knowledge may be used only when all of the following are true:

1. No local clone is available (the repo is absent from the clone manifest or `cloned: false`)
2. The repo is a well-known, widely-documented public library with stable APIs
3. The batch supervisor has explicitly opted in by setting `sourcing_fallback: training_knowledge_permitted` in the batch spec

When training knowledge is used:

```yaml
provenance:
  sourcing_method: training_knowledge
```

When code-verified:

```yaml
provenance:
  sourcing_method: code_verified
```

Files without a `sourcing_method` field are assumed unverified. Do not omit it in new files.

---

## Soft Audit

After WS6 extraction, a post-generation audit checks behavioral coverage for each repo. The audit does not block ingestion — it produces a coverage report.

The audit is not yet implemented as a standalone tool. When it is built, it should check the following:

### What the audit checks

**For all repos:**
- No unmapped sections (all top-level keys are recognized or identity/ignored)
- All behavioral entries in `troubleshooting`, `commands`/`common_tasks`, and `supported_protocols` have at least the minimum required fields (`symptom`/`cause`/`fix`; `name`/`description`; `name` respectively)

**For archetype-matched repos** (`inference_serving`, `vector_database`/`vector_databases`, `tunneling`/`vpn_mesh`/`network_infrastructure`, `agent_framework`/`agent_frameworks`/`agent_orchestration`, `agent_cli`):
- Required families are present (at least one section from each required family produced at least one fact)
- For the `tunneling`/`vpn_mesh`/`network_infrastructure` archetypes specifically: at least one `uses_protocol` fact must be present, not just any Protocols & Integrations family fact. Family presence via `has_extension_point` alone does not satisfy this check.
- Flagged as `behavioral_coverage: thin` if a required family is absent or if the archetype-specific predicate check fails

### What the audit does not check

- Whether entries are accurate — that requires a ground-truth audit against source code
- Whether fact count meets a minimum threshold — thin is flagged, not blocked
- Repos in categories without archetype definitions — they are audited for unmapped sections only

### Audit output shape

The audit produces a per-repo coverage record. Proposed shape:

```yaml
- repo: ladybugdb/ladybug
  archetype: vector_database
  families_present: [structure]
  families_missing: [failures, tasks]
  behavioral_coverage: thin
  flags:
    - "required family 'failures' absent — no troubleshooting section"
    - "recommended family 'tasks' absent — no commands or common_tasks section"
```

---

## Reference Files

- **Extractor source:** `tools/ws6_deep_integrator.py` (search for `extractor_map` near line 2513)
- **Strong Failures example:** `repos/knowledge/deep/vllm.yaml` — `troubleshooting:` with 5 concrete entries
- **Strong Tasks example:** `repos/knowledge/deep/openai__codex.yaml` — `commands:` section
- **Strong Protocols example:** `repos/knowledge/deep/hiddify-app.yaml` — `supported_protocols:`
- **Balanced small file:** `repos/knowledge/deep/bore.yaml`
- **Example of thin file to improve:** `repos/knowledge/deep/ladybugdb__ladybug.yaml`
- **WS1 schema contracts:** `contracts/ws1/` (read-only — do not modify)
- **Unmapped section debt:** `reports/ws6_deep_integration/mismatch_report.yaml`

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-03-04 | Initial contract. Header matching, YAML quoting, recognized sections, expected shapes, quality guidelines. |
| 1.1 | 2026-03-17 | Sourcing requirements. Training-knowledge opt-in. `sourcing_method` provenance field. |
| 1.2 | 2026-03-17 | Optional `extraction_model` and `extraction_agent` provenance fields. |
| 2.0 | 2026-03-18 | Replace Tier 1/2/3 ranking with evidence families and archetype requirements. Add behavioral entry standards. Add source selection strategy. Add soft audit spec. Archetypes defined: `inference_serving`, `vector_database`, `tunneling`/`vpn_mesh`/`network_infrastructure`. |
| 2.1 | 2026-03-19 | Add `agent_framework` and `agent_cli` archetypes. `agent_framework` canonicalizes `agent_frameworks`/`agent_orchestration` label variants. Both require Structure + Tasks; `agent_cli` additionally requires Failures. |
