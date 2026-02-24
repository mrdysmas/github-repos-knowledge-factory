#!/usr/bin/env python3
"""
Knowledge Base Validation Script

Validates structural integrity and consistency of the LLM repos knowledge base.
VALIDATOR_SCOPE: index.yaml, graph.yaml, repos/*.yaml
Full trust-gate coverage (progress/audit/deep) is enforced by tools/trust_gates.py.
Run from the knowledge/ directory or specify path as argument.

Usage:
    python validate.py                    # Run all validations
    python validate.py --fix              # Auto-fix minor issues
    python validate.py --query "ollama"   # Query helper
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from collections import defaultdict
from typing import Any

import yaml


# Valid relation types for graph edges
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


class ValidationResult:
    """Collects validation results."""

    def __init__(self):
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.warnings: list[str] = []

    def add_pass(self, test: str, details: str = ""):
        msg = f"✓ {test}"
        if details:
            msg += f": {details}"
        self.passed.append(msg)

    def add_fail(self, test: str, details: str = ""):
        msg = f"✗ {test}"
        if details:
            msg += f": {details}"
        self.failed.append(msg)

    def add_warning(self, msg: str):
        self.warnings.append(f"⚠ {msg}")

    def summary(self) -> str:
        lines = [
            "\n=== Validation Summary ===",
            f"Passed: {len(self.passed)}",
            f"Failed: {len(self.failed)}",
            f"Warnings: {len(self.warnings)}",
        ]
        if self.failed:
            lines.append("\nFailed tests:")
            lines.extend(f"  {f}" for f in self.failed)
        if self.warnings:
            lines.append("\nWarnings:")
            lines.extend(f"  {w}" for w in self.warnings)
        return "\n".join(lines)

    @property
    def ok(self) -> bool:
        return len(self.failed) == 0


class KnowledgeBase:
    """Loads and provides access to knowledge base data."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.index: dict[str, Any] = {}
        self.graph: dict[str, Any] = {}
        self.repos: dict[str, dict[str, Any]] = {}
        self.repo_name_to_id: dict[str, str] = {}
        self.repo_id_to_name: dict[str, str] = {}

    def load(self) -> None:
        """Load all knowledge base files."""
        self.index = self._load_yaml(self.base_path / "index.yaml")
        self.graph = self._load_yaml(self.base_path / "graph.yaml")
        self._load_repos()

    def _load_yaml(self, path: Path) -> dict:
        """Load a YAML file."""
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _load_repos(self) -> None:
        """Load all repo files."""
        repos_dir = self.base_path / "repos"
        for repo_file in repos_dir.glob("*.yaml"):
            data = self._load_yaml(repo_file)
            if "name" in data:
                self.repos[data["name"]] = data
                node_id = data.get("node_id")
                if isinstance(node_id, str) and node_id:
                    self.repo_name_to_id[data["name"]] = node_id
                    self.repo_id_to_name[node_id] = data["name"]

    def _resolve_repo_id(self, repo_identifier: str) -> str | None:
        """Resolve repo display name or canonical node_id to canonical node_id."""
        if repo_identifier in self.repo_name_to_id:
            return self.repo_name_to_id[repo_identifier]
        if repo_identifier in self.repo_id_to_name:
            return repo_identifier
        return None

    def _display_label(self, node_id: str) -> str:
        """Return human-readable label for node ID."""
        return self.repo_id_to_name.get(node_id, node_id)

    def get_index_repo_names(self) -> set[str]:
        """Get all repo names from index."""
        names = set()
        if "repos_alpha" in self.index:
            for repo in self.index["repos_alpha"]:
                names.add(repo["name"])
        return names

    def get_category_repo_names(self) -> dict[str, set[str]]:
        """Get repos organized by category from index."""
        by_category: dict[str, set[str]] = {}
        for cat_name, cat_data in self.index.get("categories", {}).items():
            by_category[cat_name] = {r["name"] for r in cat_data.get("repos", [])}
        return by_category

    def get_graph_nodes(self) -> set[str]:
        """Get all node IDs referenced in graph edges."""
        nodes = set()
        for edge in self.graph.get("edges", []):
            src_id = edge.get("src_id")
            dst_id = edge.get("dst_id")
            if isinstance(src_id, str):
                nodes.add(src_id)
            if isinstance(dst_id, str):
                nodes.add(dst_id)
        return nodes

    def get_graph_edges(self) -> list[dict]:
        """Get all edges from graph."""
        return self.graph.get("edges", [])

    def get_connections(self, repo_name: str) -> dict[str, list[str]]:
        """Get all connections for a repo (bidirectional)."""
        outgoing: dict[str, list[str]] = defaultdict(list)
        incoming: dict[str, list[str]] = defaultdict(list)
        repo_id = self._resolve_repo_id(repo_name)
        if repo_id is None:
            return {}

        for edge in self.get_graph_edges():
            source = edge.get("src_id")
            target = edge.get("dst_id")
            relation = edge.get("relation")
            if not isinstance(source, str) or not isinstance(target, str) or not isinstance(relation, str):
                continue

            if source == repo_id:
                outgoing[relation].append(self._display_label(target))
            if target == repo_id:
                incoming[relation].append(self._display_label(source))

        # Combine into single view
        all_connections: dict[str, list[str]] = defaultdict(list)
        for rel, targets in outgoing.items():
            all_connections[f"{rel} →"] = targets
        for rel, sources in incoming.items():
            all_connections[f"← {rel}"] = sources

        return dict(all_connections)

    def query_by_relation(self, relation: str, target: str | None = None) -> list[str]:
        """Find repos with given relation to target (or any target if None)."""
        results = set()
        target_id = self._resolve_repo_id(target) if target is not None else None
        if target is not None and target_id is None:
            return []

        for edge in self.get_graph_edges():
            if edge.get("relation") != relation:
                continue
            src_id = edge.get("src_id")
            if not isinstance(src_id, str):
                continue
            if target is None:
                results.add(self._display_label(src_id))
            elif edge.get("dst_id") == target_id:
                results.add(self._display_label(src_id))
        return sorted(results)

    def query_integrations(self, repo: str) -> list[str]:
        """Find all repos that integrate with given repo."""
        return self.query_by_relation("integrates_with", repo)

    def query_alternatives(self, repo: str) -> list[str]:
        """Find alternatives to given repo."""
        results = set()
        repo_id = self._resolve_repo_id(repo)
        if repo_id is None:
            return []

        for edge in self.get_graph_edges():
            if edge.get("relation") != "alternative_to":
                continue
            source = edge.get("src_id")
            target = edge.get("dst_id")
            if not isinstance(source, str) or not isinstance(target, str):
                continue
            if target == repo_id:
                results.add(self._display_label(source))
            if source == repo_id:
                results.add(self._display_label(target))
        return sorted(results)

    def count_connections(self) -> dict[str, int]:
        """Count total connections per repo."""
        counts: dict[str, int] = defaultdict(int)
        for edge in self.get_graph_edges():
            source = edge.get("src_id")
            target = edge.get("dst_id")
            if not isinstance(source, str) or not isinstance(target, str):
                continue
            counts[self._display_label(source)] += 1
            counts[self._display_label(target)] += 1
        return dict(counts)


def validate_structure(kb: KnowledgeBase) -> ValidationResult:
    """Validate structural integrity of knowledge base."""
    result = ValidationResult()

    # Test 1: YAML parsing (implicitly passes if we got here)
    result.add_pass("YAML parsing", "All files parse correctly")

    # Test 2: Repo count consistency
    index_count = kb.index.get("metadata", {}).get("total_repos", 0)
    actual_count = len(kb.repos)
    index_names = kb.get_index_repo_names()

    if index_count == actual_count:
        result.add_pass("Repo count", f"Index={index_count}, actual={actual_count}")
    else:
        result.add_fail("Repo count", f"Index says {index_count}, found {actual_count}")

    # Test 3: Index/file consistency
    file_names = set(kb.repos.keys())
    missing_files = index_names - file_names
    orphan_files = file_names - index_names

    if not missing_files and not orphan_files:
        result.add_pass("Index/file consistency", "All repos match")
    else:
        if missing_files:
            result.add_fail("Missing repo files", str(missing_files))
        if orphan_files:
            result.add_fail("Orphan repo files", str(orphan_files))

    # Test 4: Category consistency
    category_repos = kb.get_category_repo_names()
    for cat_name, cat_repos in category_repos.items():
        for repo in cat_repos:
            if repo in kb.repos:
                repo_cat = kb.repos[repo].get("category")
                if repo_cat != cat_name:
                    result.add_fail(
                        "Category consistency",
                        f"{repo}: index says {cat_name}, file says {repo_cat}",
                    )
                else:
                    result.add_pass("Category consistency", f"{repo} → {cat_name}")

    # Test 5: Canonical graph edge schema and repo endpoint validity
    required_edge_keys = {"src_id", "dst_id", "dst_kind", "relation", "as_of", "provenance"}
    allowed_dst_kinds = {"repo", "external_tool", "concept"}
    valid_repo_ids = set(kb.repo_id_to_name)
    schema_errors: list[str] = []
    src_missing_repo: set[str] = set()
    repo_dst_missing_repo: set[str] = set()

    for idx, edge in enumerate(kb.get_graph_edges()):
        if not isinstance(edge, dict):
            schema_errors.append(f"edge[{idx}] is not a mapping")
            continue

        missing = sorted(required_edge_keys - set(edge))
        if missing:
            schema_errors.append(f"edge[{idx}] missing keys {missing}")
            continue

        src_id = edge.get("src_id")
        dst_id = edge.get("dst_id")
        dst_kind = edge.get("dst_kind")
        as_of = edge.get("as_of")
        provenance = edge.get("provenance")

        if not isinstance(src_id, str) or not isinstance(dst_id, str):
            schema_errors.append(f"edge[{idx}] src_id/dst_id must be strings")
            continue
        if not isinstance(dst_kind, str) or dst_kind not in allowed_dst_kinds:
            schema_errors.append(f"edge[{idx}] invalid dst_kind '{dst_kind}'")
            continue
        if not isinstance(as_of, str) or not as_of:
            schema_errors.append(f"edge[{idx}] as_of must be a non-empty string")
        if not isinstance(provenance, dict):
            schema_errors.append(f"edge[{idx}] provenance must be a mapping")
        else:
            required_prov = {"shard", "source_file", "source_relation", "source_edge_index"}
            prov_missing = sorted(required_prov - set(provenance))
            if prov_missing:
                schema_errors.append(f"edge[{idx}] provenance missing keys {prov_missing}")

        if src_id not in valid_repo_ids:
            src_missing_repo.add(src_id)

        if dst_kind == "repo" and dst_id not in valid_repo_ids:
            repo_dst_missing_repo.add(dst_id)

    if not schema_errors and not src_missing_repo and not repo_dst_missing_repo:
        result.add_pass("Graph edge schema", "Canonical edge keys/provenance are valid")
    else:
        if schema_errors:
            result.add_fail("Graph edge schema", str(schema_errors[:10]))
        if src_missing_repo:
            result.add_fail("Graph src_id validity", str(sorted(src_missing_repo)))
        if repo_dst_missing_repo:
            result.add_fail("Graph repo dst_id validity", str(sorted(repo_dst_missing_repo)))

    # Test 6: Valid relation types
    invalid_relations = set()
    for edge in kb.get_graph_edges():
        rel = edge.get("relation")
        if rel not in VALID_RELATIONS:
            invalid_relations.add(rel)
    if not invalid_relations:
        result.add_pass("Relation types", "All use valid relation types")
    else:
        result.add_fail("Invalid relations", str(invalid_relations))

    # Test 7: No self-references
    self_refs = []
    for edge in kb.get_graph_edges():
        if edge.get("src_id") == edge.get("dst_id"):
            self_refs.append(edge.get("src_id"))
    if not self_refs:
        result.add_pass("Self-references", "None found")
    else:
        result.add_fail("Self-references", str(self_refs))

    return result


def validate_consistency(kb: KnowledgeBase) -> ValidationResult:
    """Validate cross-file consistency."""
    result = ValidationResult()

    # Check ecosystem_connections in repo files vs graph.yaml
    for repo_name, repo_data in kb.repos.items():
        connections = repo_data.get("ecosystem_connections", [])
        if not connections:
            continue

        # Get graph edges involving this repo
        graph_targets = set()
        repo_id = kb.repo_name_to_id.get(repo_name)
        if repo_id is None:
            continue

        for edge in kb.get_graph_edges():
            if edge.get("src_id") != repo_id:
                continue
            if edge.get("dst_kind") != "repo":
                continue
            dst_id = edge.get("dst_id")
            if not isinstance(dst_id, str):
                continue
            target_name = kb.repo_id_to_name.get(dst_id)
            if target_name:
                graph_targets.add(target_name)

        # Get ecosystem_targets (normalizing dashes to underscores)
        eco_targets = set()
        for conn in connections:
            target = conn.get("target", "").replace("-", "_")
            eco_targets.add(target)

        # Note: Not a hard fail since repo files can have connections not in graph
        # (bidirectional documentation vs directional graph)
        missing_in_graph = eco_targets - graph_targets - {n.replace("_", "-") for n in graph_targets}
        if missing_in_graph:
            result.add_warning(
                f"{repo_name}: ecosystem_connections has targets not in graph: {missing_in_graph}"
            )

    result.add_pass("Ecosystem consistency check", "Completed (see warnings if any)")

    return result


def print_query_results(kb: KnowledgeBase, query: str) -> None:
    """Print query results for a repo."""
    if query not in kb.repos:
        print(f"Repo '{query}' not found. Available: {sorted(kb.repos.keys())}")
        return

    repo = kb.repos[query]
    print(f"\n{'='*50}")
    print(f"Repo: {query}")
    print(f"Category: {repo.get('category')}")
    print(f"{'='*50}")

    # Summary
    summary = repo.get("summary", "").strip()
    if summary:
        print(f"\nSummary:\n{summary[:200]}...")

    # Connections
    connections = kb.get_connections(query)
    if connections:
        print(f"\nConnections:")
        for rel, targets in sorted(connections.items()):
            print(f"  {rel}: {', '.join(targets)}")

    # Connection count
    counts = kb.count_connections()
    if query in counts:
        print(f"\nTotal connections: {counts[query]}")

    # Alternatives
    alts = kb.query_alternatives(query)
    if alts:
        print(f"\nAlternatives: {', '.join(alts)}")


def print_stats(kb: KnowledgeBase) -> None:
    """Print knowledge base statistics."""
    print("\n=== Knowledge Base Statistics ===")
    print(f"Total repos: {len(kb.repos)}")
    print(f"Total edges: {len(kb.get_graph_edges())}")
    print(f"Categories: {len(kb.index.get('categories', {}))}")

    # Most connected repos
    counts = kb.count_connections()
    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    print("\nMost connected repos:")
    for repo, count in sorted_counts[:5]:
        print(f"  {repo}: {count} connections")

    # By category
    print("\nRepos by category:")
    for cat, repos in kb.get_category_repo_names().items():
        print(f"  {cat}: {len(repos)} repos")


def run_trust_gates_preflight(base_path: Path) -> None:
    """Run WS0 trust gates before validator checks."""
    repo_root = Path(__file__).resolve().parents[2]
    trust_gates_script = repo_root / "tools" / "trust_gates.py"

    if not trust_gates_script.exists():
        print(f"Error: missing trust gates preflight script at {trust_gates_script}")
        sys.exit(1)

    result = subprocess.run(
        [sys.executable, str(trust_gates_script), str(base_path), "--production"],
        check=False,
    )
    if result.returncode != 0:
        print("\n✗ Trust gates preflight failed. Validation halted.")
        sys.exit(result.returncode)


def run_ws1_contract_preflight(base_path: Path) -> None:
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
        print("\n✗ WS1 contract preflight failed. Validation halted.")
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description="Validate LLM repos knowledge base")
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to knowledge directory (default: current)",
    )
    parser.add_argument("--query", "-q", help="Query a specific repo")
    parser.add_argument("--stats", "-s", action="store_true", help="Show statistics")
    parser.add_argument(
        "--integrations",
        metavar="REPO",
        help="Show repos that integrate with REPO",
    )
    parser.add_argument(
        "--alternatives",
        metavar="REPO",
        help="Show alternatives to REPO",
    )

    args = parser.parse_args()

    base_path = Path(args.path).resolve()
    if not (base_path / "index.yaml").exists():
        print(f"Error: {base_path} does not contain index.yaml")
        sys.exit(1)

    kb = KnowledgeBase(base_path)
    try:
        kb.load()
    except Exception as e:
        print(f"Error loading knowledge base: {e}")
        sys.exit(1)

    # Handle query modes
    if args.query:
        print_query_results(kb, args.query)
        sys.exit(0)

    if args.stats:
        print_stats(kb)
        sys.exit(0)

    if args.integrations:
        results = kb.query_integrations(args.integrations)
        print(f"\nRepos integrating with {args.integrations}:")
        for r in results:
            print(f"  - {r}")
        sys.exit(0)

    if args.alternatives:
        results = kb.query_alternatives(args.alternatives)
        print(f"\nAlternatives to {args.alternatives}:")
        for r in results:
            print(f"  - {r}")
        sys.exit(0)

    run_trust_gates_preflight(base_path)
    run_ws1_contract_preflight(base_path)

    # Run validations
    print("Validating knowledge base...")
    print(f"Path: {base_path}")

    structure_result = validate_structure(kb)
    consistency_result = validate_consistency(kb)

    # Print results
    for msg in structure_result.passed:
        print(msg)
    for msg in consistency_result.passed:
        print(msg)

    all_warnings = structure_result.warnings + consistency_result.warnings
    for msg in all_warnings:
        print(msg)

    # Summary
    print(structure_result.summary())

    if consistency_result.warnings:
        print(f"\nConsistency warnings: {len(consistency_result.warnings)}")

    # Exit code
    if structure_result.ok:
        print("\n✓ All validations passed!")
        sys.exit(0)
    else:
        print("\n✗ Validation failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
