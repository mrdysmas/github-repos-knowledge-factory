# `query_master.py` Reference

## 1. Overview

`tools/query_master.py` is the read/query CLI for the canonical repo knowledge graph. It reads from `knowledge.db` by default (`--source sqlite`) and can fall back to direct YAML reads (`--source yaml`) for legacy compatibility. In SQLite mode, it performs stale-read protection by comparing `master_index.yaml`, `master_graph.yaml`, and `master_deep_facts.yaml` hashes against `compile_metadata` in `knowledge.db` before running queries. SQLite command responses include a timing trailer (`# query_ms: <ms>`), while `contract` and YAML-mode commands do not.

## 2. Global flags

| Flag | Required | Default | Description |
|---|---|---|---|
| `--workspace-root` | Optional | `.` | Root path used to resolve artifacts. SQLite mode expects `knowledge.db` under this root. |
| `--source` | Optional | `sqlite` | Data source mode: `sqlite` (default, recommended) or `yaml` (legacy). |
| `--master-index` | Optional | `master_index.yaml` | YAML-mode path for index data. Ignored in SQLite mode. |
| `--master-graph` | Optional | `master_graph.yaml` | YAML-mode path for graph data. Ignored in SQLite mode. |
| `--master-deep-facts` | Optional | `master_deep_facts.yaml` | YAML-mode path for deep facts. Ignored in SQLite mode. |

## 3. Commands

## 1. contract

**Purpose:** Print the CLI contract and capability map.

**Usage**

```bash
python3 tools/query_master.py contract
```

**Arguments**

| Argument | Required | Default | Description |
|---|---|---|---|
| None | N/A | N/A | `contract` has no command-specific flags. |

**Output format**

YAML object:
- `artifact_type: master_query_cli_contract`
- `version`
- `commands` map
- `identifier_resolution_order`
- `default_paths`
- `source_options`
- `default_source`

**Examples**

```bash
$ python3 tools/query_master.py contract
artifact_type: master_query_cli_contract
version: 1.2.0
commands:
  contract: Show this CLI contract.
  stats: Show top-level counts from master artifacts.
  repo: Resolve repo by node_id/name/github_full_name and return canonical row.
  neighbors: List inbound/outbound edges for a repo with optional relation filter.
  facts: List deep facts for a repo when master_deep_facts.yaml is present.
  search: Full-text search across fact values and notes (sqlite only).
  pattern: Cross-repo pattern matching by predicate (sqlite only).
  graph: Graph traversal from a starting repo (sqlite only).
  aggregate: Corpus-level statistics by dimension (sqlite only).
identifier_resolution_order:
- node_id
- name
- github_full_name
default_paths:
  master_index: master_index.yaml
  master_graph: master_graph.yaml
  master_deep_facts: master_deep_facts.yaml
source_options:
- sqlite
- yaml
default_source: sqlite
```

```bash
$ python3 tools/query_master.py --source yaml contract
artifact_type: master_query_cli_contract
version: 1.2.0
commands:
  contract: Show this CLI contract.
  stats: Show top-level counts from master artifacts.
  repo: Resolve repo by node_id/name/github_full_name and return canonical row.
  neighbors: List inbound/outbound edges for a repo with optional relation filter.
  facts: List deep facts for a repo when master_deep_facts.yaml is present.
  search: Full-text search across fact values and notes (sqlite only).
  pattern: Cross-repo pattern matching by predicate (sqlite only).
  graph: Graph traversal from a starting repo (sqlite only).
  aggregate: Corpus-level statistics by dimension (sqlite only).
identifier_resolution_order:
- node_id
- name
- github_full_name
default_paths:
  master_index: master_index.yaml
  master_graph: master_graph.yaml
  master_deep_facts: master_deep_facts.yaml
source_options:
- sqlite
- yaml
default_source: sqlite
```

**Notes**

`contract` is source-agnostic and intentionally does not emit `# query_ms`.

## 2. stats

**Purpose:** Return corpus-level counts and source paths.

**Usage**

```bash
python3 tools/query_master.py stats
python3 tools/query_master.py --source yaml stats
```

**Arguments**

| Argument | Required | Default | Description |
|---|---|---|---|
| None | N/A | N/A | Uses only global flags. |

**Output format**

YAML object:
- `artifact_type: master_query_stats`
- `counts` with `repos`, `nodes`, `edges`, `deep_facts`
- `sources` (`knowledge_db` in SQLite mode, YAML file paths in YAML mode)

**Examples**

```bash
$ python3 tools/query_master.py stats
artifact_type: master_query_stats
counts:
  repos: 73
  nodes: 87
  edges: 152
  deep_facts: 2921
sources:
  knowledge_db: /Users/szilaa/scripts/ext_sources/github_repos/knowledge.db
# query_ms: 0
```

```bash
$ python3 tools/query_master.py --source yaml stats
artifact_type: master_query_stats
counts:
  repos: 73
  nodes: 87
  edges: 152
  deep_facts: 2921
sources:
  master_index: /Users/szilaa/scripts/ext_sources/github_repos/master_index.yaml
  master_graph: /Users/szilaa/scripts/ext_sources/github_repos/master_graph.yaml
  master_deep_facts: /Users/szilaa/scripts/ext_sources/github_repos/master_deep_facts.yaml
```

**Notes**

SQLite mode includes timing; YAML mode does not.

## 3. repo

**Purpose:** Resolve an identifier and return the full canonical repo row.

**Usage**

```bash
python3 tools/query_master.py repo --id <identifier>
```

**Arguments**

| Argument | Required | Default | Description |
|---|---|---|---|
| `--id` | Required | None | Repo identifier (`node_id`, short `name`, or `github_full_name`). |

**Output format**

YAML object:
- `artifact_type: master_query_repo`
- `node_id` (resolved canonical ID)
- `repo` (full repo record from canonical artifacts)

**Examples**

```bash
$ python3 tools/query_master.py repo --id maxkb
artifact_type: master_query_repo
node_id: repo::1panel-dev/maxkb
repo:
  node_id: repo::1panel-dev/maxkb
  github_full_name: 1panel-dev/maxkb
  html_url: https://github.com/1panel-dev/maxkb
  source: compiled_master
  name: maxkb
  category: ui_tools
  summary: 'Open-source enterprise-grade agent platform (Max Knowledge Brain). Combines
    RAG pipelines,
    ...'
  core_concepts:
  - Application Builder
  - Knowledge Management
  - Workflow Engine
  - Model Providers
  - MCP Tools
  key_entry_points:
  - apps/
  - apps/application/
  - apps/knowledge/
  - ui/
  ...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py repo --id "repo::fatedier/frp"
artifact_type: master_query_repo
node_id: repo::fatedier/frp
repo:
  node_id: repo::fatedier/frp
  github_full_name: fatedier/frp
  html_url: https://github.com/fatedier/frp
  source: compiled_master
  name: frp
  category: tunneling
  summary: 'A fast reverse proxy for NAT/firewall traversal...'
  key_entry_points:
  - cmd/frpc/main.go:23
  - cmd/frps/main.go:23
  - cmd/frpc/sub/root.go:122
  - cmd/frps/root.go:111
  - client/service.go:144
  - server/service.go:135
  ...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py repo --id "1panel-dev/maxkb"
artifact_type: master_query_repo
node_id: repo::1panel-dev/maxkb
repo:
  node_id: repo::1panel-dev/maxkb
  github_full_name: 1panel-dev/maxkb
  name: maxkb
  category: ui_tools
  ...
# query_ms: 0

$ python3 tools/query_master.py repo --id nonexistent_thing
error: 'Repo identifier not found: nonexistent_thing'
# query_ms: 0
```

**Notes**

Misses return exit code `2` with an `error` object.

## 4. neighbors

**Purpose:** List graph edges touching a repo, with direction and relation filters.

**Usage**

```bash
python3 tools/query_master.py neighbors --id <identifier> [--direction in|out|both] [--relation <relation>]
```

**Arguments**

| Argument | Required | Default | Description |
|---|---|---|---|
| `--id` | Required | None | Repo identifier (`node_id`, `name`, or `github_full_name`). |
| `--direction` | Optional | `both` | Edge direction filter: `in`, `out`, `both`. |
| `--relation` | Optional | empty string | Exact relation match (for example `alternative_to`, `integrates_with`). |

**Output format**

YAML object:
- `artifact_type: master_query_neighbors`
- `node_id` (resolved)
- `direction`
- `relation_filter` (`null` if unset)
- `edges` list sorted by `(src_id, dst_kind, dst_id, relation)`

**Examples**

```bash
$ python3 tools/query_master.py neighbors --id maxkb
artifact_type: master_query_neighbors
node_id: repo::1panel-dev/maxkb
direction: both
relation_filter: null
edges:
- src_id: repo::1panel-dev/maxkb
  dst_id: repo::infiniflow/ragflow
  dst_kind: repo
  relation: alternative_to
  note: Both full-stack RAG platforms with visual UI
- src_id: repo::1panel-dev/maxkb
  dst_id: repo::langchain-ai/langchain
  dst_kind: repo
  relation: extends
  note: MaxKB built on LangChain framework
- src_id: repo::1panel-dev/maxkb
  dst_id: repo::milvus-io/milvus
  dst_kind: repo
  relation: integrates_with
  note: MaxKB could use Milvus for vector storage
- src_id: repo::1panel-dev/maxkb
  dst_id: repo::open-webui/open-webui
  dst_kind: repo
  relation: alternative_to
  note: MaxKB has stronger workflow engine; Open WebUI more popular
- src_id: repo::jeecgboot/jeecgboot
  dst_id: repo::1panel-dev/maxkb
  dst_kind: repo
  relation: related_to
  note: Both enterprise platforms with AI capabilities
...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py neighbors --id maxkb --direction out
artifact_type: master_query_neighbors
node_id: repo::1panel-dev/maxkb
direction: out
relation_filter: null
edges:
- src_id: repo::1panel-dev/maxkb
  dst_id: repo::infiniflow/ragflow
  relation: alternative_to
- src_id: repo::1panel-dev/maxkb
  dst_id: repo::langchain-ai/langchain
  relation: extends
- src_id: repo::1panel-dev/maxkb
  dst_id: repo::milvus-io/milvus
  relation: integrates_with
- src_id: repo::1panel-dev/maxkb
  dst_id: repo::open-webui/open-webui
  relation: alternative_to
# query_ms: 0
```

```bash
$ python3 tools/query_master.py neighbors --id maxkb --relation alternative_to
artifact_type: master_query_neighbors
node_id: repo::1panel-dev/maxkb
direction: both
relation_filter: alternative_to
edges:
- src_id: repo::1panel-dev/maxkb
  dst_id: repo::infiniflow/ragflow
  relation: alternative_to
- src_id: repo::1panel-dev/maxkb
  dst_id: repo::open-webui/open-webui
  relation: alternative_to
# query_ms: 0
```

```bash
$ python3 tools/query_master.py neighbors --id ollama --direction in --relation integrates_with
artifact_type: master_query_neighbors
node_id: repo::ollama/ollama
direction: in
relation_filter: integrates_with
edges:
- src_id: repo::infiniflow/ragflow
  dst_id: repo::ollama/ollama
  relation: integrates_with
- src_id: repo::jeecgboot/jeecgboot
  dst_id: repo::ollama/ollama
  relation: integrates_with
- src_id: repo::khoj-ai/khoj
  dst_id: repo::ollama/ollama
  relation: integrates_with
- src_id: repo::langchain-ai/langchain
  dst_id: repo::ollama/ollama
  relation: integrates_with
- src_id: repo::mintplex-labs/anything-llm
  dst_id: repo::ollama/ollama
  relation: integrates_with
...
# query_ms: 0
```

**Notes**

Filtering is exact-match on relation, not substring or regex.

## 5. facts

**Purpose:** Return deep facts for a repo, optionally narrowed to one predicate.

**Usage**

```bash
python3 tools/query_master.py facts --id <identifier> [--predicate <predicate>]
```

**Arguments**

| Argument | Required | Default | Description |
|---|---|---|---|
| `--id` | Required | None | Repo identifier (`node_id`, `name`, or `github_full_name`). |
| `--predicate` | Optional | empty string | Exact predicate filter (for example `has_component`, `exposes_api_endpoint`). |

**Output format**

YAML object:
- `artifact_type: master_query_facts`
- `node_id`
- `predicate_filter` (`null` if unset)
- `facts` list sorted by `(predicate, fact_id)`

Each fact includes `fact_id`, `fact_type`, `predicate`, `object_kind`, `object_value`, `confidence`, `provenance`, and optional `note`/`evidence`.

**Examples**

```bash
$ python3 tools/query_master.py facts --id maxkb
artifact_type: master_query_facts
node_id: repo::1panel-dev/maxkb
predicate_filter: null
facts:
- node_id: repo::1panel-dev/maxkb
  fact_type: api_endpoint
  predicate: exposes_api_endpoint
  object_kind: api_route
  object_value: GET /api/v1/knowledge/{id}
  fact_id: fact::1f3a8c4042d69aca8acd6b7c
- node_id: repo::1panel-dev/maxkb
  fact_type: api_endpoint
  predicate: exposes_api_endpoint
  object_kind: api_route
  object_value: POST /api/v1/provider/{id}/model
  fact_id: fact::34a0d583f9b9ae45617859fd
- node_id: repo::1panel-dev/maxkb
  fact_type: component
  predicate: has_component
  object_kind: path
  object_value: apps/tools/
  note: Custom tools and integrations
  fact_id: fact::00e744b3a313d8d5be4bdee7
- node_id: repo::1panel-dev/maxkb
  fact_type: config_option
  predicate: has_config_option
  object_kind: config_key
  object_value: DATABASE_URL
  fact_id: fact::e53b8f8eab2609b2c736018c
...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py facts --id maxkb --predicate exposes_api_endpoint
artifact_type: master_query_facts
node_id: repo::1panel-dev/maxkb
predicate_filter: exposes_api_endpoint
facts:
- object_value: GET /api/v1/knowledge/{id}
  fact_id: fact::1f3a8c4042d69aca8acd6b7c
- object_value: POST /api/v1/provider/{id}/model
  fact_id: fact::34a0d583f9b9ae45617859fd
- object_value: POST /api/v1/application
  fact_id: fact::3d7ee95284db23f7293468a4
- object_value: GET /api/v1/application/{id}
  fact_id: fact::528ec3bcdcd77fd5a52eed4e
...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py facts --id frp --predicate implements_pattern
artifact_type: master_query_facts
node_id: repo::fatedier/frp
predicate_filter: implements_pattern
facts:
- object_value: Message Type Dispatch
  note: 'description: Single-byte type identifiers for protocol message routing; location: pkg/msg/msg.go:22-41'
  fact_id: fact::0ee1d1531c7a559fd46ae18b
- object_value: test/e2e/ with framework/, basic/, features/, plugin/
  note: 'testing metadata: structure'
  fact_id: fact::16811e8600c9325b277441ca
- object_value: Factory Registration
  note: 'description: Proxy types registered via RegisterProxyFactory() at init time; location: client/proxy/proxy.go:41-45'
  fact_id: fact::af82379807586a4882babf4b
# query_ms: 0
```

```bash
$ python3 tools/query_master.py facts --id wezterm --predicate has_component
artifact_type: master_query_facts
node_id: repo::wez/wezterm
predicate_filter: has_component
facts:
- object_value: rust
  object_kind: concept
  note: primary language
  fact_id: fact::0920a7f58be0b18d29482066
- object_value: markdown
  object_kind: concept
  note: language ecosystem
  fact_id: fact::1f93c499442318ca4baf8c8c
- object_value: lua
  object_kind: concept
  note: language ecosystem
  fact_id: fact::322f75633d5c4e6eae8697e7
- object_value: wezterm-gui/src/main.rs
  object_kind: path
  note: GUI event loop and terminal windows.
  fact_id: fact::f9b8add5e66dce772a3479c9
...
# query_ms: 0
```

**Notes**

If deep facts are absent, the command fails with:

```text
error: No deep facts found. Expected master_deep_facts.yaml with top-level 'facts' list.
hint: Generate WS6 deep facts first.
```

## 6. search

**Purpose:** Full-text search across deep facts (`object_value`, `note`, or both).

**Usage**

```bash
python3 tools/query_master.py search --term <substring> [--field object_value|note|both] [--limit <n>]
```

**Arguments**

| Argument | Required | Default | Description |
|---|---|---|---|
| `--term` | Required | None | Substring to search (case-insensitive). |
| `--field` | Optional | `both` | Search target column(s): `object_value`, `note`, `both`. |
| `--limit` | Optional | `50` | Max result rows. |

**Output format**

YAML object:
- `artifact_type: master_query_search`
- `term`, `field`, `limit`, `result_count`
- `results` list with `fact_id`, `node_id`, `predicate`, `object_kind`, `object_value`, `note`

**Examples**

```bash
$ python3 tools/query_master.py search --term "Factory"
artifact_type: master_query_search
term: Factory
field: both
limit: 50
result_count: 17
results:
- fact_id: fact::05db1a94b8f1ed35db884845
  node_id: repo::datawhalechina/self-llm
  predicate: has_extension_point
  object_value: LLaMA-Factory
  note: 'integration group: frameworks'
- fact_id: fact::88ba3d0f91477086f37f4105
  node_id: repo::fatedier/frp
  predicate: has_extension_point
  object_value: client/proxy/proxy.go
  note: Register custom proxy type with factory function; RegisterProxyFactory
- fact_id: fact::af82379807586a4882babf4b
  node_id: repo::fatedier/frp
  predicate: implements_pattern
  object_value: Factory Registration
  note: 'description: Proxy types registered via RegisterProxyFactory() at init time; location: client/proxy/proxy.go:41-45'
- fact_id: fact::275ab82471df021293e7a8be
  node_id: repo::mintplex-labs/anything-llm
  predicate: implements_pattern
  object_value: Provider Factory
  note: 'description: Factory pattern using environment variables to select providers...'
...
# query_ms: 1
```

```bash
$ python3 tools/query_master.py search --term "DATABASE" --field object_value --limit 10
artifact_type: master_query_search
term: DATABASE
field: object_value
limit: 10
result_count: 9
results:
- node_id: repo::1panel-dev/maxkb
  predicate: has_config_option
  object_value: DATABASE_URL
- node_id: repo::jeecgboot/jeecgboot
  predicate: has_config_option
  object_value: jeecg.ai-rag.embed-store.database
- node_id: repo::juanfont/headscale
  predicate: has_config_option
  object_value: database.type
- node_id: repo::open-webui/open-webui
  predicate: has_config_option
  object_value: DATABASE_URL
...
# query_ms: 1
```

```bash
$ python3 tools/query_master.py search --term "proxy" --field note --limit 5
artifact_type: master_query_search
term: proxy
field: note
limit: 5
result_count: 5
results:
- node_id: repo::apernet/hysteria
  predicate: has_component
  object_value: app/internal/
  note: 'responsibility: App utilities - socks5, http, forwarding, tproxy, tun implementations; ...'
- node_id: repo::apernet/hysteria
  predicate: has_component
  object_value: core/internal/protocol/
  note: 'responsibility: Wire protocol - HTTP auth, proxy frames, UDP fragmentation; ...'
- node_id: repo::apernet/hysteria
  predicate: has_config_option
  object_value: http.listen
  note: 'type: string; HTTP proxy listen address'
- node_id: repo::fatedier/frp
  predicate: has_component
  object_value: Visitor
  note: Reverse proxy connections from server to client for secure access
# query_ms: 0
```

```bash
$ python3 tools/query_master.py search --term "redis"
artifact_type: master_query_search
term: redis
field: both
limit: 50
result_count: 4
results:
- node_id: repo::1panel-dev/maxkb
  predicate: has_config_option
  object_value: REDIS_URL
- node_id: repo::infiniflow/ragflow
  predicate: has_config_option
  object_value: redis.host
- node_id: repo::langgenius/dify
  predicate: has_component
  object_value: Redis
- node_id: repo::open-webui/open-webui
  predicate: has_config_option
  object_value: REDIS_URL
# query_ms: 1
```

**Notes**

`search` uses SQLite `LIKE ... COLLATE NOCASE`, so matching is case-insensitive substring search, not tokenized full-text indexing.

## 7. pattern

**Purpose:** Find cross-repo matches for one exact predicate, with optional `object_value` substring filter.

**Usage**

```bash
python3 tools/query_master.py pattern --predicate <predicate> [--value <substring>] [--limit <n>]
```

**Arguments**

| Argument | Required | Default | Description |
|---|---|---|---|
| `--predicate` | Required | None | Exact predicate to match. |
| `--value` | Optional | empty string | Substring filter on `object_value` (case-insensitive). |
| `--limit` | Optional | `50` | Max results. |

**Output format**

YAML object:
- `artifact_type: master_query_pattern`
- `predicate`, `value_filter`, `limit`, `result_count`
- `results` list with `node_id`, `name`, `category`, `object_value`, `object_kind`

**Examples**

```bash
$ python3 tools/query_master.py pattern --predicate implements_pattern --limit 15
artifact_type: master_query_pattern
predicate: implements_pattern
value_filter: null
limit: 15
result_count: 15
results:
- node_id: repo::phuocng/1loc
  name: 1loc
  category: snippet_collection
  object_value: Filename-as-index
  object_kind: concept
- node_id: repo::flowiseai/flowise
  name: Flowise
  category: workflow_builder
  object_value: monorepo modules for server, ui, components, and agentflow packages
  object_kind: concept
- node_id: repo::jeecgboot/jeecgboot
  name: JeecgBoot
  category: ui_tools
  object_value: RESTful API with Pagination
  object_kind: concept
...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py pattern --predicate has_config_option --value "DATABASE"
artifact_type: master_query_pattern
predicate: has_config_option
value_filter: DATABASE
limit: 50
result_count: 6
results:
- node_id: repo::jeecgboot/jeecgboot
  name: JeecgBoot
  category: ui_tools
  object_value: jeecg.ai-rag.embed-store.database
  object_kind: config_key
- node_id: repo::juanfont/headscale
  name: headscale
  category: vpn_mesh
  object_value: database.postgres.host
  object_kind: config_key
- node_id: repo::1panel-dev/maxkb
  name: maxkb
  category: ui_tools
  object_value: DATABASE_URL
  object_kind: config_key
- node_id: repo::open-webui/open-webui
  name: open_webui
  category: ui_tools
  object_value: DATABASE_URL
  object_kind: config_key
...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py pattern --predicate uses_protocol
artifact_type: master_query_pattern
predicate: uses_protocol
value_filter: null
limit: 50
result_count: 47
results:
- node_id: repo::hiddify/hiddify-app
  name: hiddify-app
  category: documentation
  object_value: HTTP, SOCKS, Naive
  object_kind: protocol
- node_id: repo::mindsdb/mindsdb
  name: mindsdb
  category: data_pipelines
  object_value: MCP (Model Context Protocol)
  object_kind: protocol
- node_id: repo::streisandeffect/streisand
  name: streisand
  category: vpn_mesh
  object_value: OpenVPN
  object_kind: protocol
- node_id: repo::streisandeffect/streisand
  name: streisand
  category: vpn_mesh
  object_value: WireGuard
  object_kind: protocol
...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py pattern --predicate has_failure_mode --limit 10
artifact_type: master_query_pattern
predicate: has_failure_mode
value_filter: null
limit: 10
result_count: 10
results:
- node_id: repo::jeecgboot/jeecgboot
  name: JeecgBoot
  category: ui_tools
  object_value: AI chat returns 404
  object_kind: issue
- node_id: repo::jeecgboot/jeecgboot
  name: JeecgBoot
  category: ui_tools
  object_value: MCP connection fails
  object_kind: issue
- node_id: repo::dair-ai/prompt-engineering-guide
  name: Prompt-Engineering-Guide
  category: educational
  object_value: Jupyter notebooks fail to run
  object_kind: issue
- node_id: repo::mintplex-labs/anything-llm
  name: anything_llm
  category: ui_tools
  object_value: 401 errors on requests
  object_kind: issue
# query_ms: 0
```

**Notes**

`pattern` uses `SELECT DISTINCT` and can return multiple rows per repo when multiple matching values exist.

## 8. graph

**Purpose:** Traverse repo relationships outward/inward across 1–3 hops.

**Usage**

```bash
python3 tools/query_master.py graph --id <identifier> [--hops 1|2|3] [--relation <relation>] [--direction in|out|both]
```

**Arguments**

| Argument | Required | Default | Description |
|---|---|---|---|
| `--id` | Required | None | Starting repo identifier. |
| `--hops` | Optional | `1` | Traversal depth; allowed values `1`, `2`, `3`. |
| `--relation` | Optional | empty string | Optional exact relation filter. |
| `--direction` | Optional | `both` | Traverse `in`, `out`, or `both` edge directions. |

**Output format**

YAML object:
- `artifact_type: master_query_graph`
- `start_id`, `hops`, `direction`, `relation_filter`
- `nodes_reached`, `edges_traversed`
- `traversal_layers` (`hop`, `edges_found`, `new_nodes`)
- `nodes` (`node_id`, `kind`, `label`)
- `edges` (`src_id`, `dst_id`, `relation`, `note`, `hop`)

**Examples**

```bash
$ python3 tools/query_master.py graph --id maxkb
artifact_type: master_query_graph
start_id: repo::1panel-dev/maxkb
hops: 1
direction: both
relation_filter: null
nodes_reached: 6
edges_traversed: 6
traversal_layers:
- hop: 1
  edges_found: 6
  new_nodes: 6
nodes:
- node_id: repo::infiniflow/ragflow
  kind: repo
  label: infiniflow/ragflow
- node_id: repo::langchain-ai/langchain
  kind: repo
  label: langchain-ai/langchain
- node_id: repo::milvus-io/milvus
  kind: repo
  label: milvus-io/milvus
...
edges:
- src_id: repo::1panel-dev/maxkb
  dst_id: repo::infiniflow/ragflow
  relation: alternative_to
  hop: 1
- src_id: repo::1panel-dev/maxkb
  dst_id: repo::langchain-ai/langchain
  relation: extends
  hop: 1
- src_id: repo::jeecgboot/jeecgboot
  dst_id: repo::1panel-dev/maxkb
  relation: related_to
  hop: 1
...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py graph --id maxkb --hops 2
artifact_type: master_query_graph
start_id: repo::1panel-dev/maxkb
hops: 2
direction: both
relation_filter: null
nodes_reached: 21
edges_traversed: 72
traversal_layers:
- hop: 1
  edges_found: 6
  new_nodes: 6
- hop: 2
  edges_found: 66
  new_nodes: 15
nodes:
- node_id: repo::dair-ai/prompt-engineering-guide
  kind: repo
  label: dair-ai/prompt-engineering-guide
- node_id: repo::infiniflow/ragflow
  kind: repo
  label: infiniflow/ragflow
- node_id: repo::ollama/ollama
  kind: repo
  label: ollama/ollama
...
edges:
- src_id: repo::1panel-dev/maxkb
  dst_id: repo::infiniflow/ragflow
  relation: alternative_to
  hop: 1
- src_id: repo::infiniflow/ragflow
  dst_id: repo::ollama/ollama
  relation: integrates_with
  hop: 2
- src_id: repo::langchain-ai/langchain
  dst_id: repo::milvus-io/milvus
  relation: integrates_with
  hop: 2
...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py graph --id maxkb --hops 3
artifact_type: master_query_graph
start_id: repo::1panel-dev/maxkb
hops: 3
direction: both
relation_filter: null
nodes_reached: 25
edges_traversed: 162
traversal_layers:
- hop: 1
  edges_found: 6
  new_nodes: 6
- hop: 2
  edges_found: 66
  new_nodes: 15
- hop: 3
  edges_found: 90
  new_nodes: 4
nodes:
- node_id: repo::ggml-org/llama.cpp
  kind: repo
  label: ggml-org/llama.cpp
- node_id: repo::hiyouga/llama-factory
  kind: repo
  label: hiyouga/llama-factory
- node_id: repo::open-compass/opencompass
  kind: repo
  label: open-compass/opencompass
...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py graph --id ollama --relation integrates_with
artifact_type: master_query_graph
start_id: repo::ollama/ollama
hops: 1
direction: both
relation_filter: integrates_with
nodes_reached: 10
edges_traversed: 15
traversal_layers:
- hop: 1
  edges_found: 15
  new_nodes: 10
nodes:
- node_id: repo::infiniflow/ragflow
  kind: repo
  label: infiniflow/ragflow
- node_id: repo::open-webui/open-webui
  kind: repo
  label: open-webui/open-webui
- node_id: repo::run-llama/llama_index
  kind: repo
  label: run-llama/llama_index
...
edges:
- src_id: repo::infiniflow/ragflow
  dst_id: repo::ollama/ollama
  relation: integrates_with
  hop: 1
- src_id: repo::ollama/ollama
  dst_id: repo::open-webui/open-webui
  relation: integrates_with
  hop: 1
...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py graph --id frp --hops 2 --direction out
artifact_type: master_query_graph
start_id: repo::fatedier/frp
hops: 2
direction: out
relation_filter: null
nodes_reached: 1
edges_traversed: 1
traversal_layers:
- hop: 1
  edges_found: 1
  new_nodes: 1
- hop: 2
  edges_found: 0
  new_nodes: 0
nodes:
- node_id: external_tool::ngrok
  kind: external_tool
  label: ngrok
edges:
- src_id: repo::fatedier/frp
  dst_id: external_tool::ngrok
  relation: alternative_to
  note: Self-hosted vs SaaS
  hop: 1
# query_ms: 0
```

**Notes**

Per-hop edge deduplication uses `(src_id, dst_id, relation)` keys; the same relationship can still appear again at later hops if reached through a different frontier node.

## 9. aggregate

**Purpose:** Return top-N aggregate counts by selected dimension.

**Usage**

```bash
python3 tools/query_master.py aggregate --group-by predicate|fact_type|object_kind|category|relation [--top <n>]
```

**Arguments**

| Argument | Required | Default | Description |
|---|---|---|---|
| `--group-by` | Required | None | Grouping dimension: `predicate`, `fact_type`, `object_kind`, `category`, `relation`. |
| `--top` | Optional | `20` | Number of groups to return. |

**Output format**

YAML object:
- `artifact_type: master_query_aggregate`
- `group_by`, `top`, `total_groups`
- `groups` list (for `category`, each row includes `count` and `fact_count`; other modes return `count`)

**Examples**

```bash
$ python3 tools/query_master.py aggregate --group-by predicate
artifact_type: master_query_aggregate
group_by: predicate
top: 20
total_groups: 8
groups:
- key: has_component
  count: 893
- key: has_config_option
  count: 722
- key: implements_pattern
  count: 454
- key: has_extension_point
  count: 362
- key: supports_task
  count: 282
...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py aggregate --group-by object_kind
artifact_type: master_query_aggregate
group_by: object_kind
top: 20
total_groups: 9
groups:
- key: concept
  count: 1213
- key: config_key
  count: 650
- key: path
  count: 474
- key: text
  count: 185
- key: command
  count: 169
...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py aggregate --group-by category
artifact_type: master_query_aggregate
group_by: category
top: 20
total_groups: 35
groups:
- key: tunneling
  count: 9
  fact_count: 390
- key: inference_serving
  count: 6
  fact_count: 206
- key: rag_frameworks
  count: 6
  fact_count: 208
- key: vpn_mesh
  count: 5
  fact_count: 212
- key: documentation
  count: 4
  fact_count: 119
...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py aggregate --group-by relation
artifact_type: master_query_aggregate
group_by: relation
top: 20
total_groups: 12
groups:
- key: integrates_with
  count: 56
- key: alternative_to
  count: 41
- key: related_to
  count: 23
- key: similar_to
  count: 14
- key: references
  count: 6
...
# query_ms: 0
```

```bash
$ python3 tools/query_master.py aggregate --group-by category --top 5
artifact_type: master_query_aggregate
group_by: category
top: 5
total_groups: 35
groups:
- key: tunneling
  count: 9
  fact_count: 390
- key: inference_serving
  count: 6
  fact_count: 206
- key: rag_frameworks
  count: 6
  fact_count: 208
- key: vpn_mesh
  count: 5
  fact_count: 212
- key: documentation
  count: 4
  fact_count: 119
# query_ms: 0
```

**Notes**

`category` aggregation joins `repos` + `facts`; counts are returned as `repo` count plus `fact_count` per category.

## 4. Identifier resolution

`--id` accepts three forms:
- Full node ID: `repo::owner/name` (example: `repo::fatedier/frp`)
- Short repo name: `name` (example: `maxkb`)
- GitHub full name: `owner/name` (example: `1panel-dev/maxkb`)

Declared resolution priority is:
1. `node_id`
2. `name`
3. `github_full_name`

In YAML mode this order is explicit in code. In SQLite mode, one SQL lookup checks all three columns and relies on uniqueness in the corpus (which holds in current data).

## 5. Data source modes

`query_master.py` supports two modes:

| Mode | What it reads | Available commands |
|---|---|---|
| `--source sqlite` (default) | `knowledge.db` | All 9 commands (`contract`, `stats`, `repo`, `neighbors`, `facts`, `search`, `pattern`, `graph`, `aggregate`) |
| `--source yaml` | `master_index.yaml`, `master_graph.yaml`, optional `master_deep_facts.yaml` | `contract`, `stats`, `repo`, `neighbors`, `facts` |

SQLite mode protections:
- If DB is missing, command fails:

```text
ERROR: knowledge.db not found. Run: python3 tools/ws7_read_model_compiler.py --workspace-root .
```

- If DB is stale vs master YAML hashes, command fails:

```text
ERROR: knowledge.db is stale — master_graph.yaml has changed since last compile.
Run: python3 tools/ws7_read_model_compiler.py --workspace-root .
```

- For SQLite-only commands run in YAML mode:

```bash
$ python3 tools/query_master.py --source yaml search --term "test"
ERROR: 'search' requires --source sqlite. These commands need the SQLite read model.
Run: python3 tools/ws7_read_model_compiler.py --workspace-root .
```

Timing trailer behavior:
- SQLite mode appends `# query_ms: <ms>` for every command except `contract`.
- YAML mode does not append `query_ms`.

## 6. Common workflows

### Understand what one repo is and how it connects

```bash
python3 tools/query_master.py repo --id maxkb
python3 tools/query_master.py neighbors --id maxkb
python3 tools/query_master.py facts --id maxkb --predicate exposes_api_endpoint
```

Representative outcomes from this run:
- `repo` resolved `maxkb` -> `repo::1panel-dev/maxkb`
- `neighbors` showed direct links to `ragflow`, `langchain`, `milvus`, `open-webui`
- `facts` returned endpoints like `POST /api/v1/application/{id}/chat`

### Find repos that use a protocol or config family

```bash
python3 tools/query_master.py pattern --predicate uses_protocol
python3 tools/query_master.py pattern --predicate has_config_option --value "DATABASE"
python3 tools/query_master.py search --term "redis"
```

Representative outcomes from this run:
- `uses_protocol` returned 47 matches (for example `OpenVPN`, `WireGuard`, `MCP`)
- `DATABASE` config filter returned 6 matches (including `maxkb` and `open-webui`)
- `redis` search returned 4 hits (`maxkb`, `ragflow`, `dify`, `open-webui`)

### Explore local graph neighborhood with increasing depth

```bash
python3 tools/query_master.py graph --id maxkb
python3 tools/query_master.py graph --id maxkb --hops 2
python3 tools/query_master.py graph --id maxkb --hops 3
```

Representative outcomes from this run:
- 1 hop: `nodes_reached: 6`
- 2 hops: `nodes_reached: 21`
- 3 hops: `nodes_reached: 25`

### Get high-level corpus shape quickly

```bash
python3 tools/query_master.py stats
python3 tools/query_master.py aggregate --group-by category --top 5
python3 tools/query_master.py aggregate --group-by predicate
```

Representative outcomes from this run:
- corpus counts: `repos: 73`, `edges: 152`, `deep_facts: 2921`
- top categories included `tunneling`, `inference_serving`, `rag_frameworks`
- top predicate was `has_component` (893 facts)

### Find alternatives and integration neighborhoods around one tool

```bash
python3 tools/query_master.py neighbors --id maxkb --relation alternative_to
python3 tools/query_master.py graph --id ollama --relation integrates_with
python3 tools/query_master.py graph --id frp --hops 2 --direction out
```

Representative outcomes from this run:
- `maxkb` alternatives included `ragflow` and `open-webui`
- `ollama` integration neighborhood reached 10 nodes with 15 integrates_with edges
- outbound `frp` graph showed direct `alternative_to` edge to `external_tool::ngrok`

## 7. Pipeline context

`query_master.py` is a read-layer CLI that sits after WS7 materialization. The prerequisite for reliable SQLite queries is:

```bash
python3 tools/ws7_read_model_compiler.py --workspace-root . --force
```

This compiles canonical YAML artifacts into `knowledge.db` (a gitignored derived artifact). Operationally, the canonical update path remains:
`inputs/ws5/ws5_input_manifest.yaml` -> `tools/ws5_remote_ingestion.py` -> WS1/trust/shard gates -> `tools/ws4_master_compiler.py` -> `tools/ws7_read_model_compiler.py` -> `tools/query_master.py`.
