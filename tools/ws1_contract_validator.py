#!/usr/bin/env python3
"""WS1 canonical contract validator.

This validator enforces the WS1 boundary contract:
- Contract artifact existence + contract_version alignment
- Source enum alignment across repo/node schemas (including remote-first enums)
- Relation mapping coverage integrity (unique coverage + per-shard observed rows)
- Edge/node consistency with explicit dst_kind checks under configurable external-node policy
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


REQUIRED_ARTIFACTS = [
    "repo.schema.yaml",
    "node.schema.yaml",
    "edge.schema.yaml",
    "relation_mapping.yaml",
    "external_node_policy.yaml",
    "validator_contract.yaml",
]

REQUIRED_REMOTE_SOURCES = {"remote_metadata", "remote_api", "compiled_master"}
SHARDS = ("llm_repos", "ssh_repos")
IDENTITY_REQUIRED_FIELDS = ("name", "node_id", "github_full_name", "html_url", "source", "provenance")
DEEP_LEGACY_ALIAS_KEYS = {"repo_id", "repo", "full_name"}


@dataclass
class CheckResult:
    passed: list[str]
    failed: list[str]

    def add_pass(self, message: str) -> None:
        self.passed.append(message)

    def add_fail(self, message: str) -> None:
        self.failed.append(message)

    @property
    def ok(self) -> bool:
        return not self.failed


def load_yaml(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def normalize_contract_version(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def validate_artifacts(contracts_dir: Path, result: CheckResult) -> dict[str, Any]:
    loaded: dict[str, Any] = {}

    for rel_path in REQUIRED_ARTIFACTS:
        full_path = contracts_dir / rel_path
        if not full_path.exists():
            result.add_fail(f"Missing required artifact: {full_path}")
            continue
        try:
            loaded[rel_path] = load_yaml(full_path)
        except Exception as exc:  # pragma: no cover - defensive path
            result.add_fail(f"Failed to parse artifact {full_path}: {exc}")

    if result.failed:
        return loaded

    versions: dict[str, str] = {}
    for rel_path, data in loaded.items():
        if not isinstance(data, dict):
            result.add_fail(f"Artifact {contracts_dir / rel_path} must be a YAML mapping")
            continue
        versions[rel_path] = normalize_contract_version(data.get("contract_version"))
        if not versions[rel_path]:
            result.add_fail(f"Artifact {contracts_dir / rel_path} missing contract_version")

    if result.failed:
        return loaded

    unique_versions = set(versions.values())
    if len(unique_versions) != 1:
        result.add_fail(f"Contract version mismatch across artifacts: {versions}")
    else:
        version = next(iter(unique_versions))
        result.add_pass(f"Contract version aligned across WS1 artifacts: {version}")

    return loaded


def validate_source_enum_alignment(loaded: dict[str, Any], result: CheckResult) -> None:
    repo_sources = loaded.get("repo.schema.yaml", {}).get("source_enums")
    node_sources = loaded.get("node.schema.yaml", {}).get("source_enums")

    if not isinstance(repo_sources, list) or not isinstance(node_sources, list):
        result.add_fail("repo.schema.yaml and node.schema.yaml must both define source_enums lists")
        return

    repo_set = set(repo_sources)
    node_set = set(node_sources)
    if repo_set != node_set:
        result.add_fail(
            "Source enum mismatch between repo/node schemas: "
            f"repo={sorted(repo_set)} node={sorted(node_set)}"
        )
        return

    missing_remote = REQUIRED_REMOTE_SOURCES - repo_set
    if missing_remote:
        result.add_fail(
            "Source enums must include remote-first values "
            f"{sorted(REQUIRED_REMOTE_SOURCES)}; missing={sorted(missing_remote)}"
        )
        return

    result.add_pass(f"Source enums aligned and remote-first ready: {sorted(repo_set)}")


def _load_yaml_files(folder: Path) -> list[tuple[Path, Any]]:
    rows: list[tuple[Path, Any]] = []
    for file_path in sorted(folder.glob("*.yaml"), key=lambda p: p.name):
        rows.append((file_path, load_yaml(file_path)))
    return rows


def _required_identity_missing(payload: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in IDENTITY_REQUIRED_FIELDS:
        value = payload.get(key)
        if key == "provenance":
            if not isinstance(value, dict):
                missing.append(key)
            continue
        if not isinstance(value, str) or not value.strip():
            missing.append(key)
    return missing


def validate_shallow_and_deep_identity(workspace_root: Path, result: CheckResult) -> None:
    for shard in SHARDS:
        shallow_dir = workspace_root / shard / "knowledge" / "repos"
        deep_dir = workspace_root / shard / "knowledge" / "deep"

        if not shallow_dir.exists() or not shallow_dir.is_dir():
            result.add_fail(f"Missing shallow directory for {shard}: {shallow_dir}")
            continue
        if not deep_dir.exists() or not deep_dir.is_dir():
            result.add_fail(f"Missing deep directory for {shard}: {deep_dir}")
            continue

        shallow_by_node: dict[str, dict[str, str]] = {}
        local_shallow_node_ids: set[str] = set()

        try:
            shallow_rows = _load_yaml_files(shallow_dir)
        except Exception as exc:
            result.add_fail(f"Failed loading shallow files for {shard}: {exc}")
            continue

        for file_path, payload in shallow_rows:
            if not isinstance(payload, dict):
                result.add_fail(f"Shallow file must be a mapping: {file_path}")
                continue

            missing = _required_identity_missing(payload)
            if missing:
                result.add_fail(f"Shallow identity missing required fields in {file_path}: {missing}")
                continue

            provenance = payload.get("provenance")
            prov_shard = provenance.get("shard") if isinstance(provenance, dict) else None
            if prov_shard != shard:
                result.add_fail(
                    f"Shallow provenance shard mismatch in {file_path}: expected={shard} actual={prov_shard}"
                )
                continue

            node_id = str(payload.get("node_id")).strip()
            source = str(payload.get("source")).strip()
            if source == shard:
                local_shallow_node_ids.add(node_id)

            existing = shallow_by_node.get(node_id)
            canonical = {
                "name": str(payload.get("name")).strip(),
                "node_id": node_id,
                "github_full_name": str(payload.get("github_full_name")).strip(),
                "html_url": str(payload.get("html_url")).strip(),
                "source": source,
            }
            if existing and existing != canonical:
                result.add_fail(
                    f"Shallow node identity conflict for node_id '{node_id}' in shard {shard}: "
                    f"existing={existing} incoming={canonical}"
                )
                continue
            shallow_by_node[node_id] = canonical

        local_deep_node_ids: set[str] = set()

        try:
            deep_rows = _load_yaml_files(deep_dir)
        except Exception as exc:
            result.add_fail(f"Failed loading deep files for {shard}: {exc}")
            continue

        for file_path, payload in deep_rows:
            if not isinstance(payload, dict):
                result.add_fail(f"Deep file must be a mapping: {file_path}")
                continue

            legacy_keys = sorted(key for key in DEEP_LEGACY_ALIAS_KEYS if key in payload)
            if legacy_keys:
                result.add_fail(f"Deep file contains legacy alias keys in {file_path}: {legacy_keys}")

            missing = _required_identity_missing(payload)
            if missing:
                result.add_fail(f"Deep identity missing required fields in {file_path}: {missing}")
                continue

            provenance = payload.get("provenance")
            prov_shard = provenance.get("shard") if isinstance(provenance, dict) else None
            if prov_shard != shard:
                result.add_fail(
                    f"Deep provenance shard mismatch in {file_path}: expected={shard} actual={prov_shard}"
                )
                continue

            node_id = str(payload.get("node_id")).strip()
            source = str(payload.get("source")).strip()
            if source == shard:
                local_deep_node_ids.add(node_id)

            shallow_identity = shallow_by_node.get(node_id)
            if shallow_identity is None:
                result.add_fail(
                    f"Deep node_id '{node_id}' in {file_path} is missing matching shallow repo record"
                )
                continue

            if str(payload.get("name")).strip() != shallow_identity["name"]:
                result.add_fail(
                    f"Deep/shallow name mismatch for node_id '{node_id}': "
                    f"deep='{payload.get('name')}' shallow='{shallow_identity['name']}'"
                )
            if str(payload.get("github_full_name")).strip() != shallow_identity["github_full_name"]:
                result.add_fail(
                    f"Deep/shallow github_full_name mismatch for node_id '{node_id}'"
                )
            if str(payload.get("html_url")).strip() != shallow_identity["html_url"]:
                result.add_fail(
                    f"Deep/shallow html_url mismatch for node_id '{node_id}'"
                )
            if source != shallow_identity["source"]:
                result.add_fail(
                    f"Deep/shallow source mismatch for node_id '{node_id}': "
                    f"deep='{source}' shallow='{shallow_identity['source']}'"
                )

        missing_local_deep = sorted(local_shallow_node_ids - local_deep_node_ids)
        if missing_local_deep:
            result.add_fail(
                f"Missing deep files for local-source shallow records in {shard}: {missing_local_deep}"
            )
        else:
            result.add_pass(
                "Shallow/deep identity contract OK for "
                f"{shard}: shallow={len(shallow_rows)} deep={len(deep_rows)} local_deep_coverage=100%"
            )


def collect_observed_relations(graph_path: Path, keys: list[str] | tuple[str, ...] | str) -> set[str]:
    data = load_yaml(graph_path) or {}
    edges = data.get("edges", [])
    observed: set[str] = set()
    if isinstance(keys, str):
        key_order = [keys]
    else:
        key_order = list(keys)
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        for key in key_order:
            label = edge.get(key)
            if isinstance(label, str) and label:
                observed.add(label)
                break
    return observed


def validate_relation_mapping(
    loaded: dict[str, Any],
    llm_graph: Path,
    ssh_graph: Path,
    result: CheckResult,
) -> None:
    mapping = loaded.get("relation_mapping.yaml")
    edge_schema = loaded.get("edge.schema.yaml")

    if not isinstance(mapping, dict):
        result.add_fail("relation_mapping.yaml must be a mapping")
        return

    canonical_relations = mapping.get("canonical_relations")
    if not isinstance(canonical_relations, list) or not canonical_relations:
        result.add_fail("relation_mapping.yaml canonical_relations must be a non-empty list")
        return

    edge_canonical = edge_schema.get("canonical_relations") if isinstance(edge_schema, dict) else None
    if not isinstance(edge_canonical, list):
        result.add_fail("edge.schema.yaml canonical_relations must be a list")
        return

    if set(canonical_relations) != set(edge_canonical):
        result.add_fail(
            "Canonical relation set mismatch between relation_mapping.yaml and edge.schema.yaml"
        )
        return

    observed_by_shard = {
        "llm_repos": collect_observed_relations(llm_graph, ["relation"]),
        "ssh_repos": collect_observed_relations(ssh_graph, ["relation", "type"]),
    }

    mapping_rows = mapping.get("mappings")
    if not isinstance(mapping_rows, list):
        result.add_fail("relation_mapping.yaml mappings must be a list")
        return

    seen_pairs: set[tuple[str, str]] = set()
    mapped_unique_observed: set[str] = set()

    for row in mapping_rows:
        if not isinstance(row, dict):
            result.add_fail("relation_mapping.yaml contains non-mapping mapping row")
            continue

        shard = row.get("shard")
        observed = row.get("observed_label")
        canonical = row.get("canonical_relation")
        status = row.get("status")

        if shard not in observed_by_shard:
            result.add_fail(f"Invalid shard in mapping row: {row}")
            continue
        if not isinstance(observed, str) or not observed:
            result.add_fail(f"Invalid observed_label in mapping row: {row}")
            continue
        if not isinstance(canonical, str) or canonical not in canonical_relations:
            result.add_fail(f"Invalid canonical_relation in mapping row: {row}")
            continue
        if status != "mapped":
            result.add_fail(f"Unsupported mapping status (expected 'mapped'): {row}")
            continue

        seen_pairs.add((shard, observed))
        mapped_unique_observed.add(observed)

    if result.failed:
        return

    expected_pairs = {
        (shard, label)
        for shard, labels in observed_by_shard.items()
        for label in labels
    }
    missing_pairs = expected_pairs - seen_pairs
    extra_pairs = seen_pairs - expected_pairs

    if missing_pairs:
        result.add_fail(f"Mapping coverage missing observed shard-label rows: {sorted(missing_pairs)}")
    if extra_pairs:
        result.add_fail(f"Mapping contains rows not observed in shard graphs: {sorted(extra_pairs)}")

    unsupported = mapping.get("unsupported", [])
    if unsupported is None:
        unsupported = []
    if not isinstance(unsupported, list):
        result.add_fail("relation_mapping.yaml unsupported must be a list")
        return

    coverage = mapping.get("coverage")
    if not isinstance(coverage, dict):
        result.add_fail("relation_mapping.yaml coverage must be a mapping")
        return

    unique_observed = len(observed_by_shard["llm_repos"] | observed_by_shard["ssh_repos"])
    unique_mapped = len(mapped_unique_observed)
    observed_rows = len(expected_pairs)
    mapped_rows = len(seen_pairs)

    expected_coverage = {
        "unique_observed_labels": unique_observed,
        "unique_mapped_labels": unique_mapped,
        "unique_canonical_coverage": f"{unique_mapped}/{unique_observed}",
        "per_shard_observed_rows": observed_rows,
        "per_shard_mapped_rows": mapped_rows,
        "unsupported_rows": len(unsupported),
    }

    for key, expected_value in expected_coverage.items():
        actual_value = coverage.get(key)
        if actual_value != expected_value:
            result.add_fail(
                f"Coverage mismatch for {key}: expected={expected_value} actual={actual_value}"
            )

    if not result.failed:
        result.add_pass(
            "Relation mapping coverage OK: "
            f"unique={expected_coverage['unique_canonical_coverage']} "
            f"rows={expected_coverage['per_shard_mapped_rows']}/{expected_coverage['per_shard_observed_rows']}"
        )


def validate_policy_configuration(
    loaded: dict[str, Any],
    external_policy: str,
    result: CheckResult,
) -> None:
    policy = loaded.get("external_node_policy.yaml")
    if not isinstance(policy, dict):
        result.add_fail("external_node_policy.yaml must be a mapping")
        return

    runtime = policy.get("runtime_enforcement")
    if not isinstance(runtime, dict):
        result.add_fail("external_node_policy.yaml runtime_enforcement must be a mapping")
        return

    allowed = runtime.get("allowed_values")
    if not isinstance(allowed, list) or not allowed:
        result.add_fail("external_node_policy.yaml runtime_enforcement.allowed_values must be a list")
        return

    if runtime.get("required_runtime_selection") is not True:
        result.add_fail("external_node_policy.yaml must require explicit runtime policy selection")
        return

    if external_policy not in allowed:
        result.add_fail(
            f"Requested external node policy '{external_policy}' is not allowed: {allowed}"
        )
        return

    result.add_pass(f"External node policy mode selected: {external_policy}")


def validate_edge_node_consistency(
    fixture_path: Path,
    external_policy: str,
    loaded: dict[str, Any],
    result: CheckResult,
) -> None:
    if not fixture_path.exists():
        result.add_fail(f"Missing edge/node consistency fixture: {fixture_path}")
        return

    data = load_yaml(fixture_path) or {}
    if not isinstance(data, dict):
        result.add_fail(f"Consistency fixture must be a mapping: {fixture_path}")
        return

    nodes = data.get("nodes")
    edges = data.get("edges")
    if not isinstance(nodes, list) or not isinstance(edges, list):
        result.add_fail(f"Consistency fixture must define list fields nodes and edges: {fixture_path}")
        return

    node_kinds: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, dict):
            result.add_fail(f"Invalid node entry in fixture {fixture_path}: {node}")
            continue
        node_id = node.get("node_id")
        kind = node.get("kind")
        if not isinstance(node_id, str) or not isinstance(kind, str):
            result.add_fail(f"Fixture node must include node_id/kind strings: {node}")
            continue
        node_kinds[node_id] = kind

    canonical_relations = set(loaded.get("relation_mapping.yaml", {}).get("canonical_relations", []))

    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            result.add_fail(f"Invalid edge entry at index {index} in fixture {fixture_path}: {edge}")
            continue

        src_id = edge.get("src_id")
        dst_id = edge.get("dst_id")
        dst_kind = edge.get("dst_kind")
        relation = edge.get("relation")

        prefix = f"fixture edge[{index}]"
        if not isinstance(src_id, str) or not isinstance(dst_id, str) or not isinstance(dst_kind, str):
            result.add_fail(f"{prefix}: src_id/dst_id/dst_kind must be strings")
            continue

        if src_id not in node_kinds:
            result.add_fail(f"{prefix}: src_id '{src_id}' missing from nodes")

        if relation not in canonical_relations:
            result.add_fail(f"{prefix}: relation '{relation}' not in canonical relations")

        if dst_kind == "repo":
            if dst_id not in node_kinds:
                result.add_fail(f"{prefix}: dst_kind=repo requires dst_id '{dst_id}' node")
            elif node_kinds[dst_id] != "repo":
                result.add_fail(
                    f"{prefix}: dst_kind=repo but destination node kind is '{node_kinds[dst_id]}'"
                )
            continue

        if external_policy == "first_class":
            if dst_id not in node_kinds:
                result.add_fail(
                    f"{prefix}: policy first_class requires explicit destination node '{dst_id}'"
                )
            elif node_kinds[dst_id] != dst_kind:
                result.add_fail(
                    f"{prefix}: dst_kind '{dst_kind}' does not match destination node kind "
                    f"'{node_kinds[dst_id]}'"
                )
            continue

        # label_only mode
        if dst_id in node_kinds and node_kinds[dst_id] != dst_kind:
            result.add_fail(
                f"{prefix}: label_only still requires dst_kind match when node exists "
                f"('{dst_kind}' vs '{node_kinds[dst_id]}')"
            )

    if not result.failed:
        result.add_pass(
            f"Edge/node consistency OK for policy '{external_policy}' (dst_kind integrity enforced)"
        )


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    workspace_default = script_dir.parent

    parser = argparse.ArgumentParser(description="Validate WS1 canonical contract boundary")
    parser.add_argument(
        "--workspace-root",
        default=str(workspace_default),
        help="Repository workspace root",
    )
    parser.add_argument(
        "--contracts-dir",
        default=None,
        help="Override contracts directory (default: <workspace-root>/contracts/ws1)",
    )
    parser.add_argument(
        "--llm-graph",
        default=None,
        help="Override llm graph path (default: <workspace-root>/llm_repos/knowledge/graph.yaml)",
    )
    parser.add_argument(
        "--ssh-graph",
        default=None,
        help="Override ssh graph path (default: <workspace-root>/ssh_repos/knowledge/graph.yaml)",
    )
    parser.add_argument(
        "--consistency-fixture",
        default=None,
        help=(
            "Path to edge/node consistency fixture "
            "(default: <workspace-root>/tests/ws1_contract/fixtures/edge_node_consistency_valid.yaml)"
        ),
    )
    parser.add_argument(
        "--external-node-policy",
        required=True,
        choices=["first_class", "label_only"],
        help="External node policy mode for WS1 boundary enforcement",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    contracts_dir = (
        Path(args.contracts_dir).resolve()
        if args.contracts_dir
        else workspace_root / "contracts" / "ws1"
    )
    llm_graph = Path(args.llm_graph).resolve() if args.llm_graph else workspace_root / "llm_repos" / "knowledge" / "graph.yaml"
    ssh_graph = Path(args.ssh_graph).resolve() if args.ssh_graph else workspace_root / "ssh_repos" / "knowledge" / "graph.yaml"
    consistency_fixture = (
        Path(args.consistency_fixture).resolve()
        if args.consistency_fixture
        else workspace_root / "tests" / "ws1_contract" / "fixtures" / "edge_node_consistency_valid.yaml"
    )

    result = CheckResult(passed=[], failed=[])

    loaded = validate_artifacts(contracts_dir, result)

    if not llm_graph.exists():
        result.add_fail(f"Missing llm graph file: {llm_graph}")
    if not ssh_graph.exists():
        result.add_fail(f"Missing ssh graph file: {ssh_graph}")

    if result.ok:
        validate_source_enum_alignment(loaded, result)
        validate_shallow_and_deep_identity(workspace_root, result)
        validate_relation_mapping(loaded, llm_graph, ssh_graph, result)
        validate_policy_configuration(loaded, args.external_node_policy, result)
        validate_edge_node_consistency(consistency_fixture, args.external_node_policy, loaded, result)

    print("\n=== WS1 Contract Validator ===")
    print(f"workspace_root: {workspace_root}")
    print(f"contracts_dir: {contracts_dir}")
    print(f"external_node_policy: {args.external_node_policy}")

    if result.passed:
        print("\nPASS checks:")
        for line in result.passed:
            print(f"  - {line}")

    if result.failed:
        print("\nFAIL checks:")
        for line in result.failed:
            print(f"  - {line}")

    if result.ok:
        print("\nWS1_CONTRACT_STATUS: PASS")
        return 0

    print("\nWS1_CONTRACT_STATUS: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
