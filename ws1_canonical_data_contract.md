# WS1 Canonical Data Contract

Date: 2026-02-22
Status: Proposed-Implemented (WS1 boundary)
Contract version: `1.0.0-ws1`

## Purpose

Freeze a canonical WS1 contract for repo records, graph nodes, graph edges, relation ontology mapping,
and validator boundary checks so WS2+ can proceed without schema churn.

## Scope

In scope:
- Canonical repo/node/edge contracts
- Canonical relation ontology with mapping from shard labels
- External node policy proposal with configurable validator behavior
- WS1 validator boundary contract
- WS1 contract regression fixtures/tests

Out of scope:
- WS2 identity backfill execution
- WS3 edge migration execution
- WS4 compiler implementation
- WS5 remote ingestion implementation

## Contract Artifacts

- `contracts/ws1/repo.schema.yaml`
- `contracts/ws1/node.schema.yaml`
- `contracts/ws1/edge.schema.yaml`
- `contracts/ws1/relation_mapping.yaml`
- `contracts/ws1/external_node_policy.yaml`
- `contracts/ws1/validator_contract.yaml`

All WS1 artifacts must carry `contract_version: 1.0.0-ws1`.

## Canonical Entity Contracts

### Repo Record

Required fields:
- `node_id` (string, unique)
- `github_full_name` (string, `owner/repo`)
- `html_url` (string, `https://` URL)
- `source` (enum: `llm_repos`, `ssh_repos`, `remote_metadata`, `remote_api`, `compiled_master`)
- `name` (string)
- `category` (string)
- `summary` (string)
- `core_concepts` (array of strings, min 1)
- `key_entry_points` (array of strings, min 1)
- `build_run` (object)
- `provenance` (object with `shard`, `source_file`, `as_of`)

Optional fields:
- `local_cache_dir` (string or null)
- `ecosystem_connections` (array of `{target, relation, note?}`)
- `extras` (object for domain-specific extension)

### Graph Node

Required fields:
- `node_id` (string, unique)
- `kind` (enum: `repo`, `external_tool`, `concept`)
- `label` (string)
- `source` (enum: `llm_repos`, `ssh_repos`, `remote_metadata`, `remote_api`, `compiled_master`)
- `provenance` (object with `as_of`, `source_refs`)

Conditional fields:
- `repo_ref` required when `kind=repo`
- `external_ref` required when `kind=external_tool`

Optional fields:
- `aliases` (array of strings)

### Graph Edge

Required fields:
- `src_id` (string)
- `dst_id` (string)
- `dst_kind` (enum: `repo`, `external_tool`, `concept`)
- `relation` (enum from canonical ontology)
- `as_of` (ISO date or datetime)
- `provenance` (object with `shard`, `source_file`, `source_relation`, `source_edge_index`)

Optional fields:
- `confidence` (number 0..1)
- `evidence` (array of strings)
- `note` (string)

## Confidence Rubric

The `confidence` field (used in graph edges, `has_failure_mode` facts, and troubleshooting entries) encodes verification chain depth. Values are not arbitrary — each tier corresponds to a specific evidence type.

| Tier | Range | Verification basis |
|------|-------|--------------------|
| `training_knowledge` | ~0.74 | Derived from model training data; no source-level confirmation |
| `error_constant_confirmed` | ~0.80 | Error code or constant confirmed present in source |
| `mechanism_confirmed` | 0.85–0.88 | Full failure mechanism confirmed in source (code path, docs, or commit) |
| `programmatic_extraction` | 0.90–0.92 | Extracted via automated analysis (AST, static analysis, log parsing) |
| `programmatic_and_human` | ~0.95 | Programmatic extraction + human review |
| `corroborated` | ~0.99 | Programmatic + human + independent corroboration (second source, issue tracker, CVE, etc.) |

**Assignment rules:**

- Default to `training_knowledge` (~0.74) when no source-level evidence is available.
- Do not inflate confidence without a concrete verification step to justify the tier.
- When `augmentation_provenance` is present, the `method` field should be consistent with the confidence tier (e.g., `error_code_search` → `error_constant_confirmed` range).
- Confidence ceilings apply per entry — a single weak link in the verification chain caps the value at that tier.

## Canonical Relation Ontology

Canonical set (WS1):
- `alternative_to`
- `integrates_with`
- `extends`
- `depends_on`
- `related_to`
- `similar_to`
- `built_on`
- `deploys`
- `references`
- `replaces`
- `supports`
- `used_by`
- `wrapper_for`

Mapping coverage rules:
- 100% unique observed labels must map to canonical relation labels, or be explicitly unsupported with rationale.
- Mapping artifact reports both:
  - unique canonical coverage (for example, `12/12`)
  - per-shard observed label rows (for example, `14` rows)

## External Node Policy (D3 remains OPEN)

Policy is runtime-configurable at validator boundary:
- `first_class`: external targets must exist as explicit non-repo nodes.
- `label_only`: external labels may appear in edges without explicit node records.

WS1 keeps D3 open by requiring explicit runtime mode selection.
No architecture finalization is implied by WS1.

## Validator Boundary Contract

Canonical WS1 command:

```bash
python3 tools/ws1_contract_validator.py --workspace-root <repo_root> --external-node-policy <first_class|label_only>
```

Mandatory enforcement path:
- Called from `llm_repos/knowledge/validate.py` preflight.
- Called from `ssh_repos/knowledge/validate.py` preflight.

WS1 validator enforces:
- Versioned WS1 artifact presence and version consistency
- Relation mapping coverage and row integrity against current shard graphs
- External node policy mode validity
- Edge/node consistency rule: `dst_kind` integrity check against node kinds

## Open Decisions (intentionally preserved)

- `D1` persistence model remains OPEN.
- `D2` ontology strategy remains OPEN.
- `D3` external-node modeling remains OPEN.

WS1 includes recommendations and executable boundary checks only.
No D1/D2/D3 finalization occurs in this milestone.
