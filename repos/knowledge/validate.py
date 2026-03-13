#!/usr/bin/env python3
"""Validator for the unified repos/knowledge shard."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


BASE_DIR = Path(__file__).resolve().parent
REPOS_DIR = BASE_DIR / "repos"
INDEX_FILE = BASE_DIR / "index.yaml"
GRAPH_FILE = BASE_DIR / "graph.yaml"

REQUIRED_REPO_FIELDS = ("name", "category", "summary")
VALID_DST_KINDS = {"repo", "external_tool", "concept"}
VALID_RELATIONS = {
    "alternative_to",
    "integrates_with",
    "extends",
    "depends_on",
    "related_to",
    "similar_to",
    "built_on",
    "deploys",
    "references",
    "replaces",
    "supports",
    "used_by",
    "wrapper_for",
}


def load_yaml(path: Path) -> tuple[Any, str | None]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle), None
    except yaml.YAMLError as exc:
        return None, f"YAML syntax error: {exc}"
    except FileNotFoundError:
        return None, f"File not found: {path.as_posix()}"


def run_trust_gates_preflight() -> None:
    repo_root = BASE_DIR.parents[1]
    trust_gates_script = repo_root / "tools" / "trust_gates.py"
    result = subprocess.run(
        [sys.executable, str(trust_gates_script), str(BASE_DIR), "--production"],
        check=False,
    )
    if result.returncode != 0:
        print("\nTrust gates preflight failed. Validation halted.")
        sys.exit(result.returncode)


def run_ws1_contract_preflight() -> None:
    repo_root = BASE_DIR.parents[1]
    ws1_validator = repo_root / "tools" / "ws1_contract_validator.py"
    result = subprocess.run(
        [
            sys.executable,
            str(ws1_validator),
            "--workspace-root",
            str(repo_root),
            "--external-node-policy",
            "first_class",
        ],
        check=False,
    )
    if result.returncode != 0:
        print("\nWS1 contract preflight failed. Validation halted.")
        sys.exit(result.returncode)


def validate_repo_file(path: Path) -> tuple[list[str], str | None]:
    errors: list[str] = []
    payload, err = load_yaml(path)
    if err:
        return [f"{path.name}: {err}"], None
    if not isinstance(payload, dict):
        return [f"{path.name}: repo file must be a mapping"], None

    for field in REQUIRED_REPO_FIELDS:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{path.name}: missing required field '{field}'")

    node_id = payload.get("node_id")
    if not isinstance(node_id, str) or not node_id.strip():
        errors.append(f"{path.name}: missing required canonical identity field 'node_id'")
        node_id = None

    return errors, node_id


def validate_graph(graph_data: Any, valid_repo_ids: set[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(graph_data, dict):
        return ["graph.yaml: graph file must be a mapping"]

    edges = graph_data.get("edges")
    if not isinstance(edges, list):
        return ["graph.yaml: missing 'edges' list"]

    required_edge_fields = {"src_id", "dst_id", "dst_kind", "relation", "as_of", "provenance"}
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"graph.yaml: edge[{index}] must be a mapping")
            continue

        missing = sorted(required_edge_fields - set(edge))
        if missing:
            errors.append(f"graph.yaml: edge[{index}] missing fields {missing}")
            continue

        src_id = edge.get("src_id")
        dst_id = edge.get("dst_id")
        dst_kind = edge.get("dst_kind")
        relation = edge.get("relation")
        as_of = edge.get("as_of")
        provenance = edge.get("provenance")

        if not isinstance(src_id, str) or src_id not in valid_repo_ids:
            errors.append(f"graph.yaml: edge[{index}] src_id references unknown repo '{src_id}'")
        if not isinstance(dst_kind, str) or dst_kind not in VALID_DST_KINDS:
            errors.append(f"graph.yaml: edge[{index}] invalid dst_kind '{dst_kind}'")
            continue
        if dst_kind == "repo" and (not isinstance(dst_id, str) or dst_id not in valid_repo_ids):
            errors.append(f"graph.yaml: edge[{index}] dst_id references unknown repo '{dst_id}'")
        if relation not in VALID_RELATIONS:
            errors.append(f"graph.yaml: edge[{index}] invalid relation '{relation}'")
        if not isinstance(as_of, str) or not as_of.strip():
            errors.append(f"graph.yaml: edge[{index}] as_of must be non-empty")
        if not isinstance(provenance, dict):
            errors.append(f"graph.yaml: edge[{index}] provenance must be a mapping")

    return errors


def main() -> int:
    run_trust_gates_preflight()
    run_ws1_contract_preflight()

    errors: list[str] = []
    valid_repo_ids: set[str] = set()

    index_payload, index_error = load_yaml(INDEX_FILE)
    if index_error:
        errors.append(f"index.yaml: {index_error}")
    elif not isinstance(index_payload, dict):
        errors.append("index.yaml: file must be a mapping")

    repo_files = sorted(REPOS_DIR.glob("*.yaml"), key=lambda path: path.name)
    for path in repo_files:
        repo_errors, node_id = validate_repo_file(path)
        errors.extend(repo_errors)
        if node_id:
            valid_repo_ids.add(node_id)

    graph_payload, graph_error = load_yaml(GRAPH_FILE)
    if graph_error:
        errors.append(f"graph.yaml: {graph_error}")
    else:
        errors.extend(validate_graph(graph_payload, valid_repo_ids))

    print("=== repos/knowledge validation ===")
    print(f"repo_files: {len(repo_files)}")
    print(f"repo_ids: {len(valid_repo_ids)}")
    print(f"errors: {len(errors)}")

    if errors:
        print("VALIDATION_STATUS: FAIL")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("VALIDATION_STATUS: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
