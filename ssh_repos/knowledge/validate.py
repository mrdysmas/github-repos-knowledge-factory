#!/usr/bin/env python3
"""
Knowledge Graph Validator

VALIDATOR_SCOPE: index.yaml, graph.yaml, repos/*.yaml
Full trust-gate coverage (progress/audit/deep) is enforced by tools/trust_gates.py.

Validates:
- YAML syntax for index/graph/repo files
- Required fields present in shallow files
- Category consistency across index and repo files
- Graph edge validity (references existing repos)
"""

import subprocess
import sys
import os
from pathlib import Path
from typing import Any

import yaml


KNOWLEDGE_DIR = Path(__file__).parent
REPOS_DIR = KNOWLEDGE_DIR / "repos"
INDEX_FILE = KNOWLEDGE_DIR / "index.yaml"
GRAPH_FILE = KNOWLEDGE_DIR / "graph.yaml"

# Required fields for shallow repo files
REQUIRED_REPO_FIELDS = ["name", "directory", "category", "summary", "core_concepts", "build_run"]
REQUIRED_BUILD_FIELDS = ["language"]

# Categories where 'language' is optional (documentation)
DOCS_CATEGORIES = {"documentation"}
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


def load_yaml(path: Path) -> tuple[dict | None, str | None]:
    """Load YAML file, return (data, error)."""
    try:
        with open(path) as f:
            return yaml.safe_load(f), None
    except yaml.YAMLError as e:
        return None, f"YAML syntax error: {e}"
    except FileNotFoundError:
        return None, f"File not found: {path}"


def validate_repo_file(path: Path) -> list[str]:
    """Validate a single repo YAML file."""
    errors = []
    data, err = load_yaml(path)

    if err:
        return [f"{path.name}: {err}"]

    if not data:
        return [f"{path.name}: Empty file"]

    # Check required fields
    for field in REQUIRED_REPO_FIELDS:
        if field not in data:
            errors.append(f"{path.name}: Missing required field '{field}'")

    # Check build_run has language (except for documentation)
    if "build_run" in data:
        build = data["build_run"]
        if not isinstance(build, dict):
            errors.append(f"{path.name}: 'build_run' must be a dict")
        elif "language" not in build and data.get("category") not in DOCS_CATEGORIES:
            errors.append(f"{path.name}: 'build_run' missing 'language'")

    # Check core_concepts is a list
    if "core_concepts" in data:
        if not isinstance(data["core_concepts"], list):
            errors.append(f"{path.name}: 'core_concepts' must be a list")

    return errors


def validate_categories(index_data: dict, repo_files: list[Path]) -> list[str]:
    """Validate category consistency between index and repo files."""
    errors = []

    # Get categories from index
    index_categories = set()
    if "categories" in index_data:
        index_categories = set(index_data["categories"].keys())

    # Get categories from repo files
    repo_categories = set()
    for path in repo_files:
        data, _ = load_yaml(path)
        if data and "category" in data:
            repo_categories.add(data["category"])

    # Check for categories in repos not in index
    missing_from_index = repo_categories - index_categories
    if missing_from_index and index_categories:
        errors.append(f"Categories in repos but not in index: {missing_from_index}")

    # Check for categories in index with no repos
    unused_categories = index_categories - repo_categories
    if unused_categories and repo_categories:
        errors.append(f"Categories in index with no repos: {unused_categories}")

    return errors


def validate_graph(graph_data: dict, valid_repo_ids: set[str]) -> list[str]:
    """Validate graph edges.

    Canonical edge schema:
    src_id, dst_id, dst_kind, relation, as_of, provenance
    """
    errors = []

    if not graph_data:
        return ["graph.yaml: Empty or missing"]

    if "edges" not in graph_data:
        return ["graph.yaml: Missing 'edges' field"]

    required_edge_fields = {"src_id", "dst_id", "dst_kind", "relation", "as_of", "provenance"}
    for idx, edge in enumerate(graph_data.get("edges", [])):
        if not isinstance(edge, dict):
            errors.append(f"graph.yaml: Edge[{idx}] must be a mapping")
            continue

        missing = sorted(required_edge_fields - set(edge))
        if missing:
            errors.append(f"graph.yaml: Edge[{idx}] missing required fields {missing}")
            continue

        src_id = edge.get("src_id")
        dst_id = edge.get("dst_id")
        dst_kind = edge.get("dst_kind")
        relation = edge.get("relation")
        as_of = edge.get("as_of")
        provenance = edge.get("provenance")

        if not isinstance(src_id, str) or not isinstance(dst_id, str):
            errors.append(f"graph.yaml: Edge[{idx}] src_id/dst_id must be strings")
            continue

        if src_id not in valid_repo_ids:
            errors.append(f"graph.yaml: Edge[{idx}] src_id references unknown repo node_id '{src_id}'")

        if not isinstance(dst_kind, str) or dst_kind not in VALID_DST_KINDS:
            errors.append(f"graph.yaml: Edge[{idx}] invalid dst_kind '{dst_kind}'")
            continue

        if dst_kind == "repo" and dst_id not in valid_repo_ids:
            errors.append(f"graph.yaml: Edge[{idx}] dst_kind=repo references unknown repo node_id '{dst_id}'")

        if relation not in VALID_RELATIONS:
            errors.append(f"graph.yaml: Edge[{idx}] invalid relation '{relation}'")

        if not isinstance(as_of, str) or not as_of:
            errors.append(f"graph.yaml: Edge[{idx}] as_of must be non-empty string")

        if not isinstance(provenance, dict):
            errors.append(f"graph.yaml: Edge[{idx}] provenance must be a mapping")
            continue

        required_prov_fields = {"shard", "source_file", "source_relation", "source_edge_index"}
        prov_missing = sorted(required_prov_fields - set(provenance))
        if prov_missing:
            errors.append(f"graph.yaml: Edge[{idx}] provenance missing fields {prov_missing}")

    return errors


def run_trust_gates_preflight() -> None:
    """Run WS0 trust gates before validator checks."""
    repo_root = Path(__file__).resolve().parents[2]
    trust_gates_script = repo_root / "tools" / "trust_gates.py"

    if not trust_gates_script.exists():
        print(f"Error: missing trust gates preflight script at {trust_gates_script}")
        sys.exit(1)

    result = subprocess.run(
        [sys.executable, str(trust_gates_script), str(KNOWLEDGE_DIR), "--production"],
        check=False,
    )
    if result.returncode != 0:
        print("\nTrust gates preflight failed. Validation halted.")
        sys.exit(result.returncode)


def run_ws1_contract_preflight() -> None:
    """Run WS1 canonical contract validation preflight."""
    repo_root = Path(__file__).resolve().parents[2]
    ws1_validator = repo_root / "tools" / "ws1_contract_validator.py"

    if not ws1_validator.exists():
        print(f"Error: missing WS1 contract validator at {ws1_validator}")
        sys.exit(1)

    external_policy = os.environ.get("WS1_EXTERNAL_NODE_POLICY", "first_class")
    result = subprocess.run(
        [
            sys.executable,
            str(ws1_validator),
            "--workspace-root",
            str(repo_root),
            "--external-node-policy",
            external_policy,
        ],
        check=False,
    )
    if result.returncode != 0:
        print("\nWS1 contract preflight failed. Validation halted.")
        sys.exit(result.returncode)


def main() -> int:
    """Run all validations, return exit code."""
    all_errors = []

    run_trust_gates_preflight()
    run_ws1_contract_preflight()

    # Collect repo files
    repo_files = list(REPOS_DIR.glob("*.yaml")) if REPOS_DIR.exists() else []
    valid_repo_names = set()
    valid_repo_ids = set()

    print(f"Found {len(repo_files)} repo files")

    # Validate each repo file
    for path in repo_files:
        errors = validate_repo_file(path)
        all_errors.extend(errors)

        data, _ = load_yaml(path)
        if data and "name" in data:
            valid_repo_names.add(data["name"])
        if data and isinstance(data.get("node_id"), str) and data["node_id"]:
            valid_repo_ids.add(data["node_id"])
        else:
            all_errors.append(f"{path.name}: Missing required canonical identity field 'node_id'")

    # Validate index.yaml
    if INDEX_FILE.exists():
        index_data, err = load_yaml(INDEX_FILE)
        if err:
            all_errors.append(f"index.yaml: {err}")
        else:
            all_errors.extend(validate_categories(index_data, repo_files))
    else:
        all_errors.append("index.yaml: File not found")

    # Validate graph.yaml
    if GRAPH_FILE.exists():
        graph_data, err = load_yaml(GRAPH_FILE)
        if err:
            all_errors.append(f"graph.yaml: {err}")
        else:
            all_errors.extend(validate_graph(graph_data, valid_repo_ids))
    else:
        # Graph file not created yet - warn but don't fail
        print("Warning: graph.yaml not found (will be created)")

    # Report results
    if all_errors:
        print("\nValidation errors:")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print("\nValidation passed!")
    print(f"  - {len(repo_files)} repo files")
    print(f"  - {len(valid_repo_names)} unique repos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
