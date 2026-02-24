#!/usr/bin/env python3
"""Minimal canonical query CLI contract for master artifacts.

Contract scope:
- Query master_index.yaml and master_graph.yaml.
- Optionally query master_deep_facts.yaml when present.
- Keep output deterministic and machine-readable.

This is a thin read layer for operator workflows. It is not a replacement for a
future generated SQLite/DuckDB read-model.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def dump_yaml(payload: Any) -> str:
    return yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    )


def ensure_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for row in value:
        if isinstance(row, dict):
            out.append(row)
    return out


def build_repo_lookup(repos: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str], dict[str, str]]:
    by_node_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, str] = {}
    by_full_name: dict[str, str] = {}

    for repo in repos:
        node_id = str(repo.get("node_id") or "").strip()
        name = str(repo.get("name") or "").strip()
        full_name = str(repo.get("github_full_name") or "").strip()
        if not node_id:
            continue
        by_node_id[node_id] = repo
        if name:
            by_name[name] = node_id
        if full_name:
            by_full_name[full_name] = node_id

    return by_node_id, by_name, by_full_name


def resolve_repo_node_id(identifier: str, by_node_id: dict[str, dict[str, Any]], by_name: dict[str, str], by_full_name: dict[str, str]) -> str | None:
    if identifier in by_node_id:
        return identifier
    if identifier in by_name:
        return by_name[identifier]
    if identifier in by_full_name:
        return by_full_name[identifier]
    return None


def load_master_artifacts(workspace_root: Path, master_index_path: str, master_graph_path: str, master_deep_path: str) -> dict[str, Any]:
    index_path = (workspace_root / master_index_path).resolve()
    graph_path = (workspace_root / master_graph_path).resolve()
    deep_path = (workspace_root / master_deep_path).resolve()

    index_payload = load_yaml(index_path) or {}
    graph_payload = load_yaml(graph_path) or {}
    deep_payload: dict[str, Any] = {}
    if deep_path.exists():
        loaded = load_yaml(deep_path) or {}
        if isinstance(loaded, dict):
            deep_payload = loaded

    repos = ensure_list_of_dicts(index_payload.get("repos"))
    nodes = ensure_list_of_dicts(graph_payload.get("nodes"))
    edges = ensure_list_of_dicts(graph_payload.get("edges"))
    deep_facts = ensure_list_of_dicts(deep_payload.get("facts"))

    by_node_id, by_name, by_full_name = build_repo_lookup(repos)
    return {
        "index_path": index_path.as_posix(),
        "graph_path": graph_path.as_posix(),
        "deep_path": deep_path.as_posix(),
        "repos": repos,
        "nodes": nodes,
        "edges": edges,
        "deep_facts": deep_facts,
        "repo_lookup": {
            "by_node_id": by_node_id,
            "by_name": by_name,
            "by_full_name": by_full_name,
        },
    }


def command_contract() -> dict[str, Any]:
    return {
        "artifact_type": "master_query_cli_contract",
        "version": "1.0.0",
        "commands": {
            "contract": "Show this CLI contract.",
            "stats": "Show top-level counts from master artifacts.",
            "repo": "Resolve repo by node_id/name/github_full_name and return canonical row.",
            "neighbors": "List inbound/outbound edges for a repo with optional relation filter.",
            "facts": "List deep facts for a repo when master_deep_facts.yaml is present.",
        },
        "identifier_resolution_order": ["node_id", "name", "github_full_name"],
        "default_paths": {
            "master_index": "master_index.yaml",
            "master_graph": "master_graph.yaml",
            "master_deep_facts": "master_deep_facts.yaml",
        },
    }


def command_stats(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "master_query_stats",
        "counts": {
            "repos": len(payload["repos"]),
            "nodes": len(payload["nodes"]),
            "edges": len(payload["edges"]),
            "deep_facts": len(payload["deep_facts"]),
        },
        "sources": {
            "master_index": payload["index_path"],
            "master_graph": payload["graph_path"],
            "master_deep_facts": payload["deep_path"],
        },
    }


def command_repo(payload: dict[str, Any], identifier: str) -> tuple[int, dict[str, Any]]:
    lookup = payload["repo_lookup"]
    node_id = resolve_repo_node_id(
        identifier,
        lookup["by_node_id"],
        lookup["by_name"],
        lookup["by_full_name"],
    )
    if node_id is None:
        return 2, {"error": f"Repo identifier not found: {identifier}"}
    repo = lookup["by_node_id"][node_id]
    return 0, {"artifact_type": "master_query_repo", "node_id": node_id, "repo": repo}


def command_neighbors(
    payload: dict[str, Any],
    identifier: str,
    direction: str,
    relation: str,
) -> tuple[int, dict[str, Any]]:
    lookup = payload["repo_lookup"]
    node_id = resolve_repo_node_id(
        identifier,
        lookup["by_node_id"],
        lookup["by_name"],
        lookup["by_full_name"],
    )
    if node_id is None:
        return 2, {"error": f"Repo identifier not found: {identifier}"}

    filtered: list[dict[str, Any]] = []
    for edge in payload["edges"]:
        edge_relation = str(edge.get("relation") or "").strip()
        if relation and edge_relation != relation:
            continue
        src_id = str(edge.get("src_id") or "").strip()
        dst_id = str(edge.get("dst_id") or "").strip()

        include = False
        if direction in {"out", "both"} and src_id == node_id:
            include = True
        if direction in {"in", "both"} and dst_id == node_id:
            include = True

        if include:
            filtered.append(edge)

    filtered.sort(
        key=lambda row: (
            str(row.get("src_id") or ""),
            str(row.get("dst_kind") or ""),
            str(row.get("dst_id") or ""),
            str(row.get("relation") or ""),
        )
    )
    return 0, {
        "artifact_type": "master_query_neighbors",
        "node_id": node_id,
        "direction": direction,
        "relation_filter": relation or None,
        "edges": filtered,
    }


def command_facts(payload: dict[str, Any], identifier: str, predicate: str) -> tuple[int, dict[str, Any]]:
    lookup = payload["repo_lookup"]
    node_id = resolve_repo_node_id(
        identifier,
        lookup["by_node_id"],
        lookup["by_name"],
        lookup["by_full_name"],
    )
    if node_id is None:
        return 2, {"error": f"Repo identifier not found: {identifier}"}

    facts = payload["deep_facts"]
    if not facts:
        return 2, {
            "error": "No deep facts found. Expected master_deep_facts.yaml with top-level 'facts' list.",
            "hint": "Generate WS6 deep facts first.",
        }

    out: list[dict[str, Any]] = []
    for row in facts:
        row_node_id = str(row.get("node_id") or "").strip()
        row_predicate = str(row.get("predicate") or "").strip()
        if row_node_id != node_id:
            continue
        if predicate and row_predicate != predicate:
            continue
        out.append(row)

    out.sort(key=lambda row: (str(row.get("predicate") or ""), str(row.get("fact_id") or "")))
    return 0, {
        "artifact_type": "master_query_facts",
        "node_id": node_id,
        "predicate_filter": predicate or None,
        "facts": out,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal query CLI for canonical master artifacts.")
    parser.add_argument("--workspace-root", default=".", help="Workspace root path.")
    parser.add_argument("--master-index", default="master_index.yaml", help="Path to master index YAML.")
    parser.add_argument("--master-graph", default="master_graph.yaml", help="Path to master graph YAML.")
    parser.add_argument(
        "--master-deep-facts",
        default="master_deep_facts.yaml",
        help="Path to master deep facts YAML.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("contract", help="Print CLI contract.")
    subparsers.add_parser("stats", help="Print top-level counts.")

    repo_parser = subparsers.add_parser("repo", help="Resolve and print canonical repo row.")
    repo_parser.add_argument("--id", required=True, help="Repo identifier: node_id, name, or github_full_name.")

    neighbors_parser = subparsers.add_parser("neighbors", help="Show repo neighbors from master graph edges.")
    neighbors_parser.add_argument("--id", required=True, help="Repo identifier: node_id, name, or github_full_name.")
    neighbors_parser.add_argument(
        "--direction",
        default="both",
        choices=["in", "out", "both"],
        help="Edge direction filter.",
    )
    neighbors_parser.add_argument(
        "--relation",
        default="",
        help="Optional exact relation filter (e.g., alternative_to).",
    )

    facts_parser = subparsers.add_parser("facts", help="Show deep facts for a repo when available.")
    facts_parser.add_argument("--id", required=True, help="Repo identifier: node_id, name, or github_full_name.")
    facts_parser.add_argument("--predicate", default="", help="Optional exact predicate filter.")

    args = parser.parse_args()

    if args.command == "contract":
        print(dump_yaml(command_contract()).rstrip())
        return 0

    workspace_root = Path(args.workspace_root).resolve()
    payload = load_master_artifacts(
        workspace_root=workspace_root,
        master_index_path=args.master_index,
        master_graph_path=args.master_graph,
        master_deep_path=args.master_deep_facts,
    )

    if args.command == "stats":
        print(dump_yaml(command_stats(payload)).rstrip())
        return 0

    if args.command == "repo":
        code, body = command_repo(payload, args.id)
        print(dump_yaml(body).rstrip())
        return code

    if args.command == "neighbors":
        code, body = command_neighbors(
            payload=payload,
            identifier=args.id,
            direction=args.direction,
            relation=args.relation.strip(),
        )
        print(dump_yaml(body).rstrip())
        return code

    if args.command == "facts":
        code, body = command_facts(
            payload=payload,
            identifier=args.id,
            predicate=args.predicate.strip(),
        )
        print(dump_yaml(body).rstrip())
        return code

    print(dump_yaml({"error": f"Unhandled command: {args.command}"}).rstrip())
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
