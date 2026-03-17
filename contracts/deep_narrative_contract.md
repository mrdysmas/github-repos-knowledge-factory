# Deep Narrative Generation Contract

**Version:** 1.1
**Created:** 2026-03-04
**Status:** Active — governs all deep narrative YAML production for WS6 extraction.

This document defines the output contract for deep narrative YAML files. Any agent producing deep narratives must follow this contract. WS6 (`tools/ws6_deep_integrator.py`) consumes these files and extracts structured facts from them. If the narrative doesn't follow this contract, WS6 either skips the content (unmapped section) or fails (parse error).

This is not a style guide. It's an interface specification between narrative generation and fact extraction.

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

Deep narratives live in `{shard}/knowledge/deep/`. The filename must use the `file_stem` from the repo's shallow file with a `.yaml` extension.

```
repos/knowledge/deep/{file_stem}.yaml
```

The `file_stem` follows the pattern `owner__repo` with the GitHub `/` replaced by `__`. Examples:

- `tmux/tmux` → `tmux__tmux.yaml`
- `sharkdp/bat` → `sharkdp__bat.yaml`
- `FlowiseAI/Flowise` → `flowiseai__flowise.yaml`

Match the existing shallow file's stem exactly. Don't guess — read it from the shallow file at `{shard}/knowledge/repos/{file_stem}.yaml`.

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
  as_of: "2026-03-04"
directory: bore-main
category: tunneling
```

### Matching Rules

These rules are non-negotiable. Violating them causes WS4 or WS1 gate failures.

- `node_id` must match the shallow file character-for-character. Copy it, don't retype it.
- `github_full_name` must match the shallow file character-for-character. Case matters (`FlowiseAI/Flowise` ≠ `flowiseai/flowise`).
- `html_url` must match the shallow file character-for-character. Same casing rule.
- `source` must match the shallow file's `source` field. For repos ingested via WS5, this is typically `remote_metadata`, not the shard name. Read it from the shallow file.
- `provenance.shard` is the canonical shard name (`repos`).
- `provenance.source_file` is the path to this deep file relative to the repo root.
- `provenance.as_of` is the current UTC date.
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

## Section Names

WS6 has an extractor for each recognized section name. Any top-level key in the deep narrative that isn't in the identity/ignored lists and isn't in the extractor map becomes an unmapped section in the mismatch report. Unmapped sections don't block the pipeline, but they produce no facts and add noise.

### Identity Keys (skipped by WS6)

These are read for identity matching, not extraction. They're required in the header but produce no facts:

`name`, `node_id`, `github_full_name`, `html_url`, `source`, `provenance`

### Ignored Keys (skipped by WS6)

These are allowed but not extracted. Use them for narrative context if needed:

`sparse`, `directory`, `category`, `summary`, `description`, `notes`, `metadata`

### Recognized Section Names (extracted by WS6)

These are the top-level YAML keys that WS6 knows how to extract facts from. Use only these names. The expected YAML shape for each section is documented below.

**Tier 1 — high fact yield, use whenever the repo has the relevant content:**

- `architecture`
- `code_patterns`
- `implementation_patterns`
- `configuration`
- `cli_arguments`
- `api_surface`
- `key_features`
- `key_files`
- `core_modules`

**Tier 2 — moderate fact yield:**

- `environment` / `environment_variables`
- `tech_stack` / `technology_stack`
- `testing`
- `extension_points`
- `integrations`
- `commands` / `cli_commands`
- `common_tasks`
- `procedures`
- `quick_reference`
- `sdk_usage`

**Tier 3 — lower fact yield, use when applicable:**

- `cross_references`
- `key_sections`
- `content_coverage`
- `supplementary_files`
- `supported_protocols` / `vpn_protocols` / `api_protocols`
- `troubleshooting`
- `ports`
- `related_repos`
- `api_structure`
- `type`
- `primary_language`
- `languages`

---

## Expected Shapes Per Section

Each section has a specific YAML shape that WS6 knows how to parse. If the shape is wrong (e.g., a string where a list of dicts was expected), WS6 silently skips it — no crash, but no facts either.

### architecture

The richest section. Supports three sub-structures, any or all of which can be present.

```yaml
architecture:
  module_breakdown:
    - module: src/client.rs              # module name or path
      responsibility: "Handles client connections"
      key_files: [src/client.rs]         # list of strings
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
    Optional free-text description of how data moves through the system.
    This field is ignored by WS6 (no extractor) but useful for narrative context.
```

Each entry in `module_breakdown` needs at least `module` or `key_files`. Each entry in `key_abstractions` needs `name`. Each entry in `components` needs `name`.

### code_patterns / implementation_patterns

Both use the same extractor. List of pattern entries.

```yaml
code_patterns:
  - pattern: Factory Pattern            # or name: or title:
    description: "Creates provider instances based on config"
    location: src/factory.py:45         # or file_reference:
  - pattern: Observer Pattern
    description: "Event-driven plugin notification"
    location: src/events.py:120
```

Each entry needs at least `pattern` (or `name` or `title`).

### configuration

Flexible shape — supports flat lists, nested groups, and dict-shaped options.

```yaml
# Flat list (simplest)
configuration:
  - key: max_connections              # or name:
    type: integer
    default: "100"
    description: "Maximum concurrent connections"
  - key: log_level
    default: "info"
    description: "Logging verbosity"

# Grouped (also works)
configuration:
  server:
    options:
      - key: bind_address
        default: "0.0.0.0"
        description: "Address to bind"
  client:
    options:
      - key: timeout
        default: "30"
        description: "Connection timeout in seconds"
```

Each option needs at least `key` (or `name`).

### cli_arguments

List of CLI flags/arguments.

```yaml
cli_arguments:
  - flag: "--verbose"                  # or name:
    description: "Enable verbose output"
    default: "false"
  - flag: "--output"
    description: "Output file path"
  - flag: "--format"
    description: "Output format"
    default: "json"
```

Each entry needs at least `flag` (or `name`).

### api_surface

Supports `public_functions` and endpoint sub-keys.

```yaml
api_surface:
  public_functions:
    - name: "Client.connect"
      purpose: "Establish connection to server"
      signature: "pub async fn connect(addr: &str) -> Result<Self>"
      location: src/client.rs
    - name: "Server.listen"
      purpose: "Start listening for connections"

  endpoints:
    - path: /api/v1/users
      method: GET
      description: "List all users"
    - path: /api/v1/users/:id
      method: DELETE
      description: "Delete a user"
```

**Quality rule:** Only list genuinely public/exported symbols in `public_functions`. Do not include private/internal functions. This was a confirmed quality issue in the Phase 2B spot-check audit — misclassifying private symbols as public API was the primary hallucination pattern.

### key_features

Simple list. Can be plain strings or dicts.

```yaml
# Plain strings (works)
key_features:
  - "Syntax highlighting for 100+ languages"
  - "Git integration shows file modifications"
  - "Automatic paging"

# Dicts (also works)
key_features:
  - feature: "Syntax highlighting"
    description: "Supports 100+ languages via syntect"
  - feature: "Git integration"
    description: "Shows file modifications in the gutter"
```

### key_files

List of important files with purposes.

```yaml
key_files:
  - path: src/main.rs
    purpose: "CLI entry point"
  - path: Cargo.toml
    purpose: "Workspace and dependency configuration"
```

Each entry needs at least `path` (or `name` or `file`).

### core_modules

Dict or list describing major modules.

```yaml
core_modules:
  modules:
    - name: parser
      path: src/parser/
      purpose: "Markdown parsing and AST generation"
    - name: renderer
      path: src/renderer/
      purpose: "HTML output generation"
```

### environment / environment_variables

Environment variables with descriptions.

```yaml
environment:
  required:
    - key: DATABASE_URL
      description: "PostgreSQL connection string"
  optional:
    - key: LOG_LEVEL
      default: "info"
      description: "Logging verbosity"
```

Also works as a flat list:

```yaml
environment_variables:
  - key: API_KEY
    description: "Authentication key"
  - key: PORT
    default: "8080"
    description: "Server port"
```

### tech_stack / technology_stack

List of technologies.

```yaml
tech_stack:
  - name: Rust
    role: "Primary language"
  - name: Tokio
    role: "Async runtime"
  - name: Clap
    role: "CLI argument parsing"
```

### testing

Test infrastructure description.

```yaml
testing:
  framework: pytest
  patterns:
    - name: "Integration tests"
      location: tests/integration/
      description: "End-to-end API tests"
    - name: "Unit tests"
      location: tests/unit/
      description: "Per-module unit tests"
  key_files:
    - tests/conftest.py
    - tests/integration/test_api.py
```

### extension_points

List of extensibility hooks.

```yaml
extension_points:
  - name: "Plugin interface"
    location: src/plugins/mod.rs
    hook: "trait Plugin"
    example: "impl Plugin for MyPlugin"
```

### commands / cli_commands / common_tasks / procedures

All use the same extractor shape — list of task-like entries.

```yaml
commands:
  - name: "borg create"
    description: "Create a new backup archive"
    usage: "borg create /path/to/repo::archive-name /path/to/source"
  - name: "borg extract"
    description: "Extract archive contents"
```

### quick_reference

Quick lookup entries.

```yaml
quick_reference:
  - name: "Default port"
    value: "8080"
  - name: "Config file location"
    value: "~/.config/app/config.toml"
```

### Remaining Sections

`cross_references`, `key_sections`, `content_coverage`, `supplementary_files`, `integrations`, `sdk_usage`, `supported_protocols`, `troubleshooting`, `ports`, `related_repos`, `type`, `primary_language`, `languages` — these all follow similar list-of-dicts or simple-value patterns. If unsure of the shape, look at the corresponding `extract_*` function in `tools/ws6_deep_integrator.py`.

---

## Quality Guidelines

### Ground everything in source code

Every claim in a deep narrative must be verifiable against the repo's actual source code. Do not:

- Invent file paths that don't exist in the repo
- Describe functions or methods that aren't in the source
- Attribute behavior to the project that you haven't confirmed by reading the code

If you're unsure whether something exists, leave it out. A shorter, accurate narrative produces fewer but trustworthy facts. A longer narrative with fabricated content produces facts that fail ground-truth audits.

### Don't pad small repos

Some repos are genuinely small or simple. A <500 LOC CLI tool might produce a 50-line narrative. That's correct. Don't inflate the narrative with speculative content just to hit a line count. The pipeline handles zero or low fact counts gracefully — they're valid findings, not failures.

### Size guidance

- Large repos (wezterm, hugo, puppeteer): 150–300 lines
- Medium repos (tmux, capistrano, borg): 100–200 lines
- Small repos (bore, pgvector, annoy): 80–150 lines
- Tiny repos (glm, 1loc): 30–80 lines

These are guidelines, not targets. The narrative should be as long as the source code justifies and no longer.

### Sourcing requirements

Deep file content must be grounded in actual source code. The standard method is to read from the local clone provided by the `ws6_clone_prep` step. The clone path for each repo is available in the batch's clone manifest at `reports/ws6_clone_prep/<batch_id>_clones.yaml`.

**Training knowledge as fallback**

Training knowledge may be used only when all of the following are true:

1. No local clone is available (the repo is absent from the clone manifest or `cloned: false`)
2. The repo is a well-known, widely-documented public library with stable APIs (examples: pydantic, qdrant, instructor, numpy)
3. The batch supervisor has explicitly opted in by setting `sourcing_fallback: training_knowledge_permitted` in the batch spec

When training knowledge is used, the deep file must declare this in its provenance block:

```yaml
provenance:
  shard: repos
  source_file: repos/knowledge/deep/<file_stem>.yaml
  as_of: "<current UTC date>"
  sourcing_method: training_knowledge
```

Code-verified files should declare:

```yaml
  sourcing_method: code_verified
```

Files without a `sourcing_method` field are assumed to be unverified. Do not
omit it in new files.

---

## Reference Files

- **Extractor source:** `tools/ws6_deep_integrator.py` (search for `extractor_map` near line 2513)
- **Example small deep file:** `repos/knowledge/deep/bore.yaml` (~174 lines, Rust CLI)
- **Example large deep file:** `repos/knowledge/deep/anything_llm.yaml` (Node.js monorepo)
- **WS1 schema contracts:** `contracts/ws1/` (read-only — do not modify)
- **Unmapped section debt:** `reports/ws6_deep_integration/mismatch_report.yaml`

---

## Version History

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-03-04 | Initial contract. Covers header matching, YAML quoting, recognized sections, expected shapes, quality guidelines. Derived from Phase 2B SB1–SB3 kickoff prompts and spot-check audit findings. |
| 1.1 | 2026-03-17 | Add sourcing requirements section. Narrow training-knowledge permission to explicit opt-in. Add sourcing_method provenance field. |
