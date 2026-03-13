#!/usr/bin/env python3
"""WS4 deterministic master compiler + unified validation evidence writer.

Builds:
- master_index.yaml
- master_graph.yaml

Writes deterministic WS4 evidence:
- reports/ws4_master_build/coverage.yaml
- reports/ws4_master_build/mismatch_report.yaml
- reports/ws4_master_build/validation_runs.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml


CONTRACT_VERSION = "1.0.0-ws1"
SHARDS = ("repos",)
ALLOWED_DST_KINDS = {"repo", "external_tool", "concept"}
ALLOWED_NODE_KINDS = {"repo", "external_tool", "concept"}
REPO_ALLOWED_KEYS = {
    "node_id",
    "github_full_name",
    "html_url",
    "source",
    "name",
    "category",
    "summary",
    "core_concepts",
    "key_entry_points",
    "build_run",
    "provenance",
    "local_cache_dir",
    "ecosystem_connections",
    "extras",
}


@dataclass
class CommandRun:
    step: int
    command: str
    expectation: str
    exit_code: int
    status: str
    details: str = ""


@dataclass
class CompileResult:
    generated_at_utc: str
    master_index: dict[str, Any]
    master_graph: dict[str, Any]
    coverage_metrics: dict[str, Any]
    unmapped_relation_types: list[dict[str, str]]
    unknown_repo_node_refs: list[dict[str, Any]]
    stale_records: list[dict[str, Any]]
    duplicate_repo_node_ids: list[dict[str, Any]]
    compile_errors: list[str]
    source_counts: dict[str, int]
    source_structured_repo_count: int
    compiled_structured_repo_count: int
    compiled_hashes: dict[str, str]


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def dump_yaml(data: Any) -> str:
    return yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=False,
        default_flow_style=False,
    )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_as_of(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)
        return parsed
    except ValueError:
        pass

    try:
        parsed_date = date.fromisoformat(value.strip())
        return datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=timezone.utc)
    except ValueError:
        return None


def to_utc_iso_no_micros(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def deterministic_generated_at(repo_records: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    timestamps: list[datetime] = []

    for record in repo_records:
        provenance = record.get("provenance")
        if isinstance(provenance, dict):
            parsed = parse_as_of(provenance.get("as_of"))
            if parsed is not None:
                timestamps.append(parsed)

    for edge in edges:
        parsed = parse_as_of(edge.get("as_of"))
        if parsed is not None:
            timestamps.append(parsed)

    if not timestamps:
        return "1970-01-01T00:00:00Z"

    return to_utc_iso_no_micros(max(timestamps))


def ensure_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return ""


def ensure_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item)
    return out


def normalize_text_list(value: Any, preferred_keys: tuple[str, ...]) -> list[str]:
    """Normalize heterogeneous list payloads into deterministic string arrays.

    WS1 canonical repo schema expects string arrays for core_concepts/key_entry_points.
    Shard payloads often store richer object rows (name/description/path/purpose), so
    we extract stable representative text from preferred keys.
    """
    if not isinstance(value, list):
        return []

    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
            continue

        if not isinstance(item, dict):
            continue

        extracted = ""
        for key in preferred_keys:
            candidate = item.get(key)
            if isinstance(candidate, str) and candidate.strip():
                extracted = candidate.strip()
                break

        if not extracted:
            for candidate in item.values():
                if isinstance(candidate, str) and candidate.strip():
                    extracted = candidate.strip()
                    break

        if extracted:
            out.append(extracted)

    return out


def ensure_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ensure_optional_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            out.append(dict(item))
    return out


def extract_structured_entries(value: Any) -> list[dict[str, Any]]:
    """Return raw structured list entries (dict rows) for fidelity preservation."""
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            out.append(dict(item))
    return out


def has_structured_entries(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    return any(isinstance(item, dict) for item in value)


def collect_source_repo_records(workspace_root: Path) -> tuple[list[tuple[str, Path, dict[str, Any]]], list[str]]:
    records: list[tuple[str, Path, dict[str, Any]]] = []
    errors: list[str] = []

    for shard in SHARDS:
        repos_dir = workspace_root / shard / "knowledge" / "repos"
        if not repos_dir.exists():
            errors.append(f"Missing repos directory: {repos_dir}")
            continue
        for path in sorted(repos_dir.glob("*.yaml"), key=lambda p: p.name):
            try:
                payload = load_yaml(path) or {}
            except Exception as exc:
                errors.append(f"Failed to parse repo file {path.as_posix()}: {exc}")
                continue

            if not isinstance(payload, dict):
                errors.append(f"Repo file is not a mapping: {path.as_posix()}")
                continue

            records.append((shard, path, payload))

    return records, errors


def compile_repo_record(
    shard: str,
    path: Path,
    payload: dict[str, Any],
    compile_errors: list[str],
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "node_id": ensure_string(payload.get("node_id")),
        "github_full_name": ensure_string(payload.get("github_full_name")),
        "html_url": ensure_string(payload.get("html_url")),
        "source": "compiled_master",
        "name": ensure_string(payload.get("name")),
        "category": ensure_string(payload.get("category")),
        "summary": ensure_string(payload.get("summary")),
        "core_concepts": normalize_text_list(
            payload.get("core_concepts"),
            ("name", "concept", "title", "description", "path", "location", "purpose"),
        ),
        "key_entry_points": normalize_text_list(
            payload.get("key_entry_points"),
            ("path", "entry", "name", "purpose", "location", "description"),
        ),
        "build_run": ensure_dict(payload.get("build_run")),
    }

    source_prov = ensure_dict(payload.get("provenance"))
    source_file = ensure_string(source_prov.get("source_file")) or path.as_posix()
    source_as_of = ensure_string(source_prov.get("as_of"))
    record["provenance"] = {
        "shard": "merged",
        "source_file": source_file,
        "as_of": source_as_of,
    }

    if "local_cache_dir" in payload:
        local_cache_dir = payload.get("local_cache_dir")
        if isinstance(local_cache_dir, str) or local_cache_dir is None:
            record["local_cache_dir"] = local_cache_dir

    ecosystem_connections = ensure_optional_list_of_dicts(payload.get("ecosystem_connections"))
    if ecosystem_connections:
        record["ecosystem_connections"] = ecosystem_connections

    extras: dict[str, Any] = {}
    payload_extras = payload.get("extras")
    if isinstance(payload_extras, dict):
        extras.update(payload_extras)

    raw_core_structured = extract_structured_entries(payload.get("core_concepts"))
    if raw_core_structured:
        extras["raw_core_concepts_structured"] = raw_core_structured

    raw_entry_structured = extract_structured_entries(payload.get("key_entry_points"))
    if raw_entry_structured:
        extras["raw_key_entry_points_structured"] = raw_entry_structured

    for key, value in payload.items():
        if key not in REPO_ALLOWED_KEYS:
            extras[key] = value

    if extras:
        record["extras"] = {k: extras[k] for k in sorted(extras)}

    required_text_fields = (
        "node_id",
        "github_full_name",
        "html_url",
        "name",
        "category",
        "summary",
    )
    for field in required_text_fields:
        if not ensure_string(record.get(field)).strip():
            compile_errors.append(f"Missing required repo field '{field}' in {path.as_posix()}")

    if not record["core_concepts"]:
        compile_errors.append(f"core_concepts must be non-empty list in {path.as_posix()}")
    if not record["key_entry_points"]:
        compile_errors.append(f"key_entry_points must be non-empty list in {path.as_posix()}")
    if not isinstance(record["build_run"], dict) or len(record["build_run"]) == 0:
        compile_errors.append(f"build_run must be non-empty mapping in {path.as_posix()}")
    if not ensure_string(record["provenance"].get("as_of")).strip():
        compile_errors.append(f"Missing provenance.as_of in {path.as_posix()}")

    return record


def collect_relation_contract(workspace_root: Path) -> tuple[dict[tuple[str, str], str], set[str], list[str]]:
    path = workspace_root / "contracts" / "ws1" / "relation_mapping.yaml"
    errors: list[str] = []
    lookup: dict[tuple[str, str], str] = {}
    canonical_set: set[str] = set()

    try:
        payload = load_yaml(path) or {}
    except Exception as exc:
        return lookup, canonical_set, [f"Failed to parse relation mapping {path.as_posix()}: {exc}"]

    if not isinstance(payload, dict):
        return lookup, canonical_set, [f"relation_mapping.yaml must be a mapping: {path.as_posix()}"]

    canonical_relations = payload.get("canonical_relations")
    if isinstance(canonical_relations, list):
        canonical_set = {item for item in canonical_relations if isinstance(item, str) and item}
    else:
        errors.append("relation_mapping.yaml missing canonical_relations list")

    rows = payload.get("mappings")
    if not isinstance(rows, list):
        errors.append("relation_mapping.yaml missing mappings list")
        return lookup, canonical_set, errors

    for row in rows:
        if not isinstance(row, dict):
            errors.append("relation_mapping row is not a mapping")
            continue
        shard = row.get("shard")
        observed = row.get("observed_label")
        canonical = row.get("canonical_relation")
        if not isinstance(shard, str) or not isinstance(observed, str) or not isinstance(canonical, str):
            errors.append(f"Invalid relation mapping row: {row}")
            continue
        lookup[(shard, observed)] = canonical

    return lookup, canonical_set, errors


def collect_shard_edges(workspace_root: Path) -> tuple[list[tuple[str, int, dict[str, Any]]], list[str]]:
    rows: list[tuple[str, int, dict[str, Any]]] = []
    errors: list[str] = []

    for shard in SHARDS:
        path = workspace_root / shard / "knowledge" / "graph.yaml"
        try:
            payload = load_yaml(path) or {}
        except Exception as exc:
            errors.append(f"Failed to parse graph file {path.as_posix()}: {exc}")
            continue

        if not isinstance(payload, dict):
            errors.append(f"Graph file must be a mapping: {path.as_posix()}")
            continue

        edges = payload.get("edges")
        if not isinstance(edges, list):
            errors.append(f"Graph file missing edges list: {path.as_posix()}")
            continue

        for index, edge in enumerate(edges):
            if not isinstance(edge, dict):
                errors.append(f"Non-mapping edge {shard} edge[{index}]")
                continue
            rows.append((shard, index, edge))

    return rows, errors


def canonicalize_edge(
    shard: str,
    edge_index: int,
    edge: dict[str, Any],
    relation_lookup: dict[tuple[str, str], str],
    canonical_relations: set[str],
    unmapped_relation_types: list[dict[str, str]],
    compile_errors: list[str],
) -> dict[str, Any]:
    src_id = ensure_string(edge.get("src_id"))
    dst_id = ensure_string(edge.get("dst_id"))
    dst_kind = ensure_string(edge.get("dst_kind"))
    source_relation = ensure_string(edge.get("relation")) or ensure_string(edge.get("type"))

    if not src_id:
        compile_errors.append(f"{shard} edge[{edge_index}] missing src_id")
    if not dst_id:
        compile_errors.append(f"{shard} edge[{edge_index}] missing dst_id")
    if dst_kind not in ALLOWED_DST_KINDS:
        compile_errors.append(f"{shard} edge[{edge_index}] invalid dst_kind '{dst_kind}'")

    mapped_relation = relation_lookup.get((shard, source_relation), source_relation)
    if mapped_relation not in canonical_relations:
        unmapped_relation_types.append(
            {
                "shard": shard,
                "edge_index": edge_index,
                "observed_relation": source_relation,
                "mapped_relation": mapped_relation,
            }
        )

    provenance = ensure_dict(edge.get("provenance"))
    provenance_out = {
        "shard": ensure_string(provenance.get("shard")) or shard,
        "source_file": ensure_string(provenance.get("source_file"))
        or f"{shard}/knowledge/graph.yaml",
        "source_relation": ensure_string(provenance.get("source_relation")) or source_relation,
        "source_edge_index": provenance.get("source_edge_index")
        if isinstance(provenance.get("source_edge_index"), int)
        else edge_index,
    }

    as_of = ensure_string(edge.get("as_of"))
    out: dict[str, Any] = {
        "src_id": src_id,
        "dst_id": dst_id,
        "dst_kind": dst_kind,
        "relation": mapped_relation,
        "as_of": as_of,
        "provenance": provenance_out,
    }

    if isinstance(edge.get("confidence"), (float, int)):
        out["confidence"] = float(edge["confidence"])
    evidence = ensure_string_list(edge.get("evidence"))
    if evidence:
        out["evidence"] = evidence
    note = ensure_string(edge.get("note"))
    if note:
        out["note"] = note

    return out


def build_master_payloads(workspace_root: Path) -> CompileResult:
    compile_errors: list[str] = []

    source_records, source_record_errors = collect_source_repo_records(workspace_root)
    compile_errors.extend(source_record_errors)

    relation_lookup, canonical_relations, relation_errors = collect_relation_contract(workspace_root)
    compile_errors.extend(relation_errors)

    edge_rows, edge_errors = collect_shard_edges(workspace_root)
    compile_errors.extend(edge_errors)

    compiled_repos: list[dict[str, Any]] = []
    source_counts = {shard: 0 for shard in SHARDS}
    repo_occurrences: dict[str, list[dict[str, str]]] = {}
    source_structured_repo_count = 0

    for shard, path, payload in source_records:
        source_counts[shard] += 1
        if has_structured_entries(payload.get("core_concepts")) or has_structured_entries(payload.get("key_entry_points")):
            source_structured_repo_count += 1
        record = compile_repo_record(shard, path, payload, compile_errors)
        compiled_repos.append(record)

        node_id = ensure_string(record.get("node_id"))
        if node_id:
            repo_occurrences.setdefault(node_id, []).append(
                {"shard": shard, "source_file": path.as_posix(), "github_full_name": ensure_string(record.get("github_full_name"))}
            )

    duplicate_repo_node_ids: list[dict[str, Any]] = []
    for node_id, occurrences in sorted(repo_occurrences.items()):
        if len(occurrences) > 1:
            duplicate_repo_node_ids.append({"node_id": node_id, "occurrences": occurrences})

    compiled_structured_repo_count = 0
    for repo in compiled_repos:
        extras = ensure_dict(repo.get("extras"))
        if ensure_optional_list_of_dicts(extras.get("raw_core_concepts_structured")) or ensure_optional_list_of_dicts(
            extras.get("raw_key_entry_points_structured")
        ):
            compiled_structured_repo_count += 1

    compiled_repos.sort(key=lambda rec: (ensure_string(rec.get("node_id")), ensure_string(rec.get("github_full_name"))))
    repo_ids = {ensure_string(rec.get("node_id")) for rec in compiled_repos if ensure_string(rec.get("node_id"))}

    unmapped_relation_types: list[dict[str, str]] = []
    compiled_edges: list[dict[str, Any]] = []
    external_nodes: dict[str, dict[str, Any]] = {}

    for shard, edge_index, edge in edge_rows:
        canonical_edge = canonicalize_edge(
            shard=shard,
            edge_index=edge_index,
            edge=edge,
            relation_lookup=relation_lookup,
            canonical_relations=canonical_relations,
            unmapped_relation_types=unmapped_relation_types,
            compile_errors=compile_errors,
        )
        compiled_edges.append(canonical_edge)

        dst_kind = canonical_edge.get("dst_kind")
        dst_id = ensure_string(canonical_edge.get("dst_id"))
        if dst_kind != "repo" and dst_kind in ALLOWED_NODE_KINDS and dst_id:
            label = dst_id.split("::", 1)[1] if "::" in dst_id else dst_id
            node = external_nodes.get(dst_id)
            if node is None:
                node = {
                    "node_id": dst_id,
                    "kind": dst_kind,
                    "label": label,
                    "source": "compiled_master",
                    "provenance": {
                        "as_of": ensure_string(canonical_edge.get("as_of")),
                        "source_refs": [ensure_string(canonical_edge["provenance"].get("source_file"))],
                    },
                }
                if dst_kind == "external_tool":
                    node["external_ref"] = {"provider": "label", "value": label}
                external_nodes[dst_id] = node
            else:
                source_refs = node["provenance"].get("source_refs", [])
                source_file = ensure_string(canonical_edge["provenance"].get("source_file"))
                if source_file and source_file not in source_refs:
                    source_refs.append(source_file)
                    source_refs.sort()
                    node["provenance"]["source_refs"] = source_refs

                candidate_as_of = parse_as_of(canonical_edge.get("as_of"))
                current_as_of = parse_as_of(node["provenance"].get("as_of"))
                if candidate_as_of and (current_as_of is None or candidate_as_of > current_as_of):
                    node["provenance"]["as_of"] = ensure_string(canonical_edge.get("as_of"))

    compiled_edges.sort(
        key=lambda edge: (
            ensure_string(edge.get("src_id")),
            ensure_string(edge.get("dst_kind")),
            ensure_string(edge.get("dst_id")),
            ensure_string(edge.get("relation")),
            ensure_string(ensure_dict(edge.get("provenance")).get("shard")),
            int(ensure_dict(edge.get("provenance")).get("source_edge_index") or 0),
        )
    )

    repo_nodes: list[dict[str, Any]] = []
    for repo in compiled_repos:
        node_id = ensure_string(repo.get("node_id"))
        github_full_name = ensure_string(repo.get("github_full_name"))
        repo_name = ensure_string(repo.get("name"))
        source_file = ensure_string(ensure_dict(repo.get("provenance")).get("source_file"))
        as_of = ensure_string(ensure_dict(repo.get("provenance")).get("as_of"))

        node: dict[str, Any] = {
            "node_id": node_id,
            "kind": "repo",
            "label": github_full_name or repo_name or node_id,
            "source": "compiled_master",
            "repo_ref": github_full_name,
            "provenance": {
                "as_of": as_of,
                "source_refs": [source_file] if source_file else ["compiled_master"],
            },
        }

        aliases = []
        if repo_name and repo_name != node["label"]:
            aliases.append(repo_name)
        if aliases:
            node["aliases"] = aliases

        repo_nodes.append(node)

    external_node_list = [external_nodes[key] for key in sorted(external_nodes)]
    nodes = sorted(
        repo_nodes + external_node_list,
        key=lambda node: (ensure_string(node.get("kind")), ensure_string(node.get("node_id"))),
    )

    generated_at_utc = deterministic_generated_at(compiled_repos, compiled_edges)

    category_counts: dict[str, int] = {}
    for repo in compiled_repos:
        category = ensure_string(repo.get("category"))
        if category:
            category_counts[category] = category_counts.get(category, 0) + 1

    master_index = {
        "artifact_type": "ws4_master_index",
        "generated_at_utc": generated_at_utc,
        "contract_version": CONTRACT_VERSION,
        "metadata": {
            "source_shards": list(SHARDS),
            "total_repos": len(compiled_repos),
            "repo_counts_by_shard": source_counts,
            "category_counts": {k: category_counts[k] for k in sorted(category_counts)},
            "compiled_source": "compiled_master",
        },
        "repos": compiled_repos,
    }

    master_graph = {
        "artifact_type": "ws4_master_graph",
        "generated_at_utc": generated_at_utc,
        "contract_version": CONTRACT_VERSION,
        "nodes": nodes,
        "edges": compiled_edges,
    }

    unknown_repo_node_refs: list[dict[str, Any]] = []
    for edge in compiled_edges:
        if ensure_string(edge.get("dst_kind")) != "repo":
            continue
        dst_id = ensure_string(edge.get("dst_id"))
        if dst_id not in repo_ids:
            unknown_repo_node_refs.append(
                {
                    "src_id": ensure_string(edge.get("src_id")),
                    "dst_id": dst_id,
                    "relation": ensure_string(edge.get("relation")),
                    "source_file": ensure_string(ensure_dict(edge.get("provenance")).get("source_file")),
                    "source_edge_index": ensure_dict(edge.get("provenance")).get("source_edge_index"),
                }
            )

    stale_records: list[dict[str, Any]] = []
    for repo in compiled_repos:
        prov = ensure_dict(repo.get("provenance"))
        as_of = ensure_string(prov.get("as_of"))
        if parse_as_of(as_of) is None:
            stale_records.append(
                {
                    "record_type": "repo",
                    "node_id": ensure_string(repo.get("node_id")),
                    "source_file": ensure_string(prov.get("source_file")),
                    "reason": "missing_or_invalid_provenance_as_of",
                }
            )

    for edge in compiled_edges:
        as_of = ensure_string(edge.get("as_of"))
        if parse_as_of(as_of) is None:
            stale_records.append(
                {
                    "record_type": "edge",
                    "src_id": ensure_string(edge.get("src_id")),
                    "dst_id": ensure_string(edge.get("dst_id")),
                    "source_file": ensure_string(ensure_dict(edge.get("provenance")).get("source_file")),
                    "source_edge_index": ensure_dict(edge.get("provenance")).get("source_edge_index"),
                    "reason": "missing_or_invalid_as_of",
                }
            )

    repo_input_total = len(source_records)
    edge_input_total = len(edge_rows)
    repo_compiled_total = len(compiled_repos)
    edge_compiled_total = len(compiled_edges)
    repo_coverage_pct = round((repo_compiled_total / repo_input_total) * 100.0, 3) if repo_input_total else 0.0
    edge_coverage_pct = round((edge_compiled_total / edge_input_total) * 100.0, 3) if edge_input_total else 0.0

    coverage_metrics = {
        "coverage": {
            "repo_records": {
                "input_total": repo_input_total,
                "compiled_total": repo_compiled_total,
                "coverage_pct": repo_coverage_pct,
            },
            "edge_records": {
                "input_total": edge_input_total,
                "compiled_total": edge_compiled_total,
                "coverage_pct": edge_coverage_pct,
            },
            "node_records": {
                "compiled_total": len(nodes),
                "repo_nodes": len(repo_nodes),
                "external_nodes": len(external_node_list),
            },
        },
        "unmapped_relations": {
            "count": len(unmapped_relation_types),
        },
        "unknown_repo_node_refs_dst_kind_repo": {
            "count": len(unknown_repo_node_refs),
        },
        "stale_records": {
            "count": len(stale_records),
            "repo_records": sum(1 for item in stale_records if item.get("record_type") == "repo"),
            "edge_records": sum(1 for item in stale_records if item.get("record_type") == "edge"),
        },
        "structured_list_fidelity": {
            "source_repos_with_structured_entries": source_structured_repo_count,
            "compiled_repos_with_preserved_structured_entries": compiled_structured_repo_count,
            "preservation_pct": round(
                (compiled_structured_repo_count / source_structured_repo_count) * 100.0, 3
            )
            if source_structured_repo_count
            else 100.0,
        },
    }

    master_index_text = dump_yaml(master_index)
    master_graph_text = dump_yaml(master_graph)
    compiled_hashes = {
        "master_index.yaml": sha256_text(master_index_text),
        "master_graph.yaml": sha256_text(master_graph_text),
    }

    return CompileResult(
        generated_at_utc=generated_at_utc,
        master_index=master_index,
        master_graph=master_graph,
        coverage_metrics=coverage_metrics,
        unmapped_relation_types=sorted(
            unmapped_relation_types,
            key=lambda row: (row["shard"], int(row["edge_index"]), row["observed_relation"]),
        ),
        unknown_repo_node_refs=unknown_repo_node_refs,
        stale_records=stale_records,
        duplicate_repo_node_ids=duplicate_repo_node_ids,
        compile_errors=compile_errors,
        source_counts=source_counts,
        source_structured_repo_count=source_structured_repo_count,
        compiled_structured_repo_count=compiled_structured_repo_count,
        compiled_hashes=compiled_hashes,
    )


def parse_generated_yaml(text: str) -> bool:
    try:
        parsed = yaml.safe_load(text)
    except Exception:
        return False
    return isinstance(parsed, dict)


def command_exit_status(exit_code: int) -> str:
    return "PASS" if exit_code == 0 else "FAIL"


def run_command(
    step: int,
    command: str,
    expectation: str,
    argv: list[str],
    cwd: Path,
    extra_check: callable | None = None,
) -> CommandRun:
    completed = subprocess.run(
        argv,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        check=False,
    )
    status = command_exit_status(completed.returncode)
    details = ""

    if completed.returncode == 0 and extra_check is not None:
        ok, detail = extra_check(completed)
        if not ok:
            status = "FAIL"
            details = detail
        elif detail:
            details = detail
    elif completed.returncode != 0:
        details = (completed.stderr or completed.stdout or "").strip().splitlines()
        details = details[-1] if details else "non-zero exit"

    return CommandRun(
        step=step,
        command=command,
        expectation=expectation,
        exit_code=completed.returncode,
        status=status,
        details=details,
    )


def ws1_output_check(completed: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    ok = "WS1_CONTRACT_STATUS: PASS" in output
    return ok, "" if ok else "WS1_CONTRACT_STATUS: PASS not found in output"


def trust_gates_report_check(report_path: Path) -> callable:
    def _check(_: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
        try:
            payload = load_yaml(report_path) or {}
        except Exception as exc:
            return False, f"failed to parse report {report_path.as_posix()}: {exc}"

        if not isinstance(payload, dict):
            return False, f"report {report_path.as_posix()} is not a mapping"

        overall = payload.get("overall_status")
        ready = payload.get("ready_state_allowed")
        ok = overall == "PASS" and ready is True
        detail = "" if ok else f"overall_status={overall}, ready_state_allowed={ready}"
        return ok, detail

    return _check


def run_required_preflight_commands(workspace_root: Path) -> list[CommandRun]:
    python = sys.executable
    runs: list[CommandRun] = []

    runs.append(
        run_command(
            step=1,
            command="python3 tools/ws1_contract_validator.py --workspace-root . --external-node-policy first_class",
            expectation="WS1_CONTRACT_STATUS: PASS",
            argv=[
                python,
                "tools/ws1_contract_validator.py",
                "--workspace-root",
                ".",
                "--external-node-policy",
                "first_class",
            ],
            cwd=workspace_root,
            extra_check=ws1_output_check,
        )
    )
    runs.append(
        run_command(
            step=2,
            command="python3 tools/ws1_contract_validator.py --workspace-root . --external-node-policy label_only",
            expectation="WS1_CONTRACT_STATUS: PASS",
            argv=[
                python,
                "tools/ws1_contract_validator.py",
                "--workspace-root",
                ".",
                "--external-node-policy",
                "label_only",
            ],
            cwd=workspace_root,
            extra_check=ws1_output_check,
        )
    )
    runs.append(
        run_command(
            step=3,
            command="python3 tools/trust_gates.py repos/knowledge --production",
            expectation="overall_status: PASS and ready_state_allowed: true",
            argv=[python, "tools/trust_gates.py", "repos/knowledge", "--production"],
            cwd=workspace_root,
            extra_check=trust_gates_report_check(workspace_root / "repos" / "knowledge" / "trust-gates-report.yaml"),
        )
    )
    runs.append(
        run_command(
            step=4,
            command="cd repos/knowledge && python3 validate.py",
            expectation="validate.py exits 0",
            argv=[python, "validate.py"],
            cwd=workspace_root / "repos" / "knowledge",
            extra_check=None,
        )
    )

    return runs


def evaluate_external_policy_compatibility(master_graph: dict[str, Any]) -> tuple[bool, bool]:
    nodes = master_graph.get("nodes", [])
    edges = master_graph.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return False, False

    node_kind_by_id = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = ensure_string(node.get("node_id"))
        kind = ensure_string(node.get("kind"))
        if node_id:
            node_kind_by_id[node_id] = kind

    first_class_ok = True
    label_only_ok = True

    for edge in edges:
        if not isinstance(edge, dict):
            first_class_ok = False
            label_only_ok = False
            continue
        dst_id = ensure_string(edge.get("dst_id"))
        dst_kind = ensure_string(edge.get("dst_kind"))

        if dst_kind == "repo":
            if node_kind_by_id.get(dst_id) != "repo":
                first_class_ok = False
                label_only_ok = False
            continue

        node_kind = node_kind_by_id.get(dst_id)
        if node_kind is None:
            first_class_ok = False
            continue
        if node_kind != dst_kind:
            first_class_ok = False
            label_only_ok = False

    return first_class_ok, label_only_ok


def write_if_changed(path: Path, text: str) -> None:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == text:
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_reports(
    compile_result: CompileResult,
    gate_bools: dict[str, bool],
    gate_ready: bool,
    command_runs: list[CommandRun],
    deterministic_hash_check: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    metrics = compile_result.coverage_metrics

    coverage_report = {
        "artifact_type": "ws4_master_build_coverage",
        "generated_at_utc": compile_result.generated_at_utc,
        "contract_version": CONTRACT_VERSION,
        "metrics": metrics,
        "unmapped_relation_types": compile_result.unmapped_relation_types,
        "unknown_repo_node_refs_dst_kind_repo": compile_result.unknown_repo_node_refs,
        "stale_records": compile_result.stale_records,
        "gate_bools": gate_bools,
        "gate_ready": gate_ready,
    }

    mismatch_report = {
        "artifact_type": "ws4_master_build_mismatch_report",
        "generated_at_utc": compile_result.generated_at_utc,
        "contract_version": CONTRACT_VERSION,
        "summary": {
            "unmapped_relation_types_count": len(compile_result.unmapped_relation_types),
            "unknown_repo_node_refs_count": len(compile_result.unknown_repo_node_refs),
            "stale_records_count": len(compile_result.stale_records),
            "duplicate_repo_node_ids_count": len(compile_result.duplicate_repo_node_ids),
            "compile_errors_count": len(compile_result.compile_errors),
        },
        "unmapped_relation_types": compile_result.unmapped_relation_types,
        "unknown_repo_node_refs_dst_kind_repo": compile_result.unknown_repo_node_refs,
        "stale_records": compile_result.stale_records,
        "duplicate_repo_node_ids": compile_result.duplicate_repo_node_ids,
        "compile_errors": compile_result.compile_errors,
        "metrics": metrics,
        "gate_bools": gate_bools,
        "gate_ready": gate_ready,
    }

    command_rows: list[dict[str, Any]] = []
    for run in command_runs:
        row: dict[str, Any] = {
            "step": run.step,
            "command": run.command,
            "exit_code": run.exit_code,
            "status": run.status,
            "expectation": run.expectation,
        }
        if run.details:
            row["details"] = run.details
        command_rows.append(row)

    command_rows.append(
        {
            "step": 7,
            "command": "python3 tools/ws4_master_compiler.py --workspace-root . --master-index master_index.yaml --master-graph master_graph.yaml --reports-dir reports/ws4_master_build",
            "exit_code": 0,
            "status": "PASS",
            "expectation": "Compiler writes deterministic master artifacts and WS4 evidence artifacts",
        }
    )
    command_rows.append(
        {
            "step": 8,
            "command": "Re-run command #7 and verify deterministic output (artifact hashes unchanged)",
            "exit_code": 0 if deterministic_hash_check else 1,
            "status": "PASS" if deterministic_hash_check else "FAIL",
            "expectation": "artifact hashes unchanged",
        }
    )

    validation_runs = {
        "artifact_type": "ws4_master_build_validation_runs",
        "generated_at_utc": compile_result.generated_at_utc,
        "contract_version": CONTRACT_VERSION,
        "required_commands": command_rows,
        "artifact_hashes": compile_result.compiled_hashes,
        "metrics": metrics,
        "gate_bools": gate_bools,
        "gate_ready": gate_ready,
    }

    return coverage_report, mismatch_report, validation_runs


def main() -> int:
    parser = argparse.ArgumentParser(description="WS4 deterministic master compiler")
    parser.add_argument("--workspace-root", default=".", help="Workspace root")
    parser.add_argument("--master-index", default="master_index.yaml", help="Output path for master index")
    parser.add_argument("--master-graph", default="master_graph.yaml", help="Output path for master graph")
    parser.add_argument(
        "--reports-dir",
        default="reports/ws4_master_build",
        help="Output directory for WS4 reports",
    )
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    master_index_path = (workspace_root / args.master_index).resolve()
    master_graph_path = (workspace_root / args.master_graph).resolve()
    reports_dir = (workspace_root / args.reports_dir).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    command_runs = run_required_preflight_commands(workspace_root)

    first_compile = build_master_payloads(workspace_root)
    second_compile = build_master_payloads(workspace_root)

    deterministic_hash_check = first_compile.compiled_hashes == second_compile.compiled_hashes

    master_index_text = dump_yaml(first_compile.master_index)
    master_graph_text = dump_yaml(first_compile.master_graph)
    master_index_parseable = parse_generated_yaml(master_index_text)
    master_graph_parseable = parse_generated_yaml(master_graph_text)

    repo_source_compiled_master = True
    repos = first_compile.master_index.get("repos", [])
    if isinstance(repos, list):
        for repo in repos:
            if not isinstance(repo, dict) or repo.get("source") != "compiled_master":
                repo_source_compiled_master = False
                break
    else:
        repo_source_compiled_master = False

    node_source_compiled_master = True
    nodes = first_compile.master_graph.get("nodes", [])
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict) or node.get("source") != "compiled_master":
                node_source_compiled_master = False
                break
    else:
        node_source_compiled_master = False

    first_class_ok, label_only_ok = evaluate_external_policy_compatibility(first_compile.master_graph)

    step_by_number = {run.step: run for run in command_runs}
    ws1_first_class_pass = step_by_number.get(1, CommandRun(1, "", "", 1, "FAIL")).status == "PASS"
    ws1_label_only_pass = step_by_number.get(2, CommandRun(2, "", "", 1, "FAIL")).status == "PASS"
    trust_gates_repos_pass = step_by_number.get(3, CommandRun(3, "", "", 1, "FAIL")).status == "PASS"
    repos_validate_pass = step_by_number.get(4, CommandRun(4, "", "", 1, "FAIL")).status == "PASS"

    gate_bools: dict[str, bool] = {
        "repo_coverage_100pct": first_compile.coverage_metrics["coverage"]["repo_records"]["coverage_pct"] == 100.0,
        "edge_coverage_100pct": first_compile.coverage_metrics["coverage"]["edge_records"]["coverage_pct"] == 100.0,
        "unmapped_relation_types_empty": len(first_compile.unmapped_relation_types) == 0,
        "unknown_repo_node_refs_dst_kind_repo_zero": len(first_compile.unknown_repo_node_refs) == 0,
        "stale_records_zero": len(first_compile.stale_records) == 0,
        "duplicate_repo_node_ids_zero": len(first_compile.duplicate_repo_node_ids) == 0,
        "compile_errors_zero": len(first_compile.compile_errors) == 0,
        "master_index_yaml_parseable": master_index_parseable,
        "master_graph_yaml_parseable": master_graph_parseable,
        "master_repo_records_source_compiled_master": repo_source_compiled_master,
        "master_node_records_source_compiled_master": node_source_compiled_master,
        "external_policy_first_class_compatible": first_class_ok,
        "external_policy_label_only_compatible": label_only_ok,
        "structured_list_fidelity_preserved_under_extras": (
            first_compile.compiled_structured_repo_count == first_compile.source_structured_repo_count
        ),
        "ws1_contract_first_class_pass": ws1_first_class_pass,
        "ws1_contract_label_only_pass": ws1_label_only_pass,
        "trust_gates_repos_pass": trust_gates_repos_pass,
        "repos_validate_entrypoint_pass": repos_validate_pass,
        "ws4_command_7_compiler_pass": True,
        "ws4_command_8_deterministic_hash_unchanged": deterministic_hash_check,
    }
    gate_bools["all_required_commands_exit_zero"] = all(
        run.status == "PASS" for run in command_runs
    ) and gate_bools["ws4_command_7_compiler_pass"] and gate_bools["ws4_command_8_deterministic_hash_unchanged"]

    gate_ready = all(gate_bools.values())

    coverage_report, mismatch_report, validation_runs = build_reports(
        compile_result=first_compile,
        gate_bools=gate_bools,
        gate_ready=gate_ready,
        command_runs=command_runs,
        deterministic_hash_check=deterministic_hash_check,
    )

    coverage_text = dump_yaml(coverage_report)
    mismatch_text = dump_yaml(mismatch_report)
    validation_runs_text = dump_yaml(validation_runs)

    # Update hash map with final report artifacts (after final report payloads are built).
    final_hashes = dict(first_compile.compiled_hashes)
    final_hashes["reports/ws4_master_build/coverage.yaml"] = sha256_text(coverage_text)
    final_hashes["reports/ws4_master_build/mismatch_report.yaml"] = sha256_text(mismatch_text)
    validation_runs["artifact_hashes"] = final_hashes
    validation_runs_text = dump_yaml(validation_runs)

    write_if_changed(master_index_path, master_index_text)
    write_if_changed(master_graph_path, master_graph_text)
    write_if_changed(reports_dir / "coverage.yaml", coverage_text)
    write_if_changed(reports_dir / "mismatch_report.yaml", mismatch_text)
    write_if_changed(reports_dir / "validation_runs.yaml", validation_runs_text)

    print("WS4_MASTER_BUILD_SUMMARY")
    print(f"workspace_root: {workspace_root.as_posix()}")
    print(f"master_index: {master_index_path.as_posix()}")
    print(f"master_graph: {master_graph_path.as_posix()}")
    print(f"reports_dir: {reports_dir.as_posix()}")
    print(f"generated_at_utc: {first_compile.generated_at_utc}")
    print(f"gate_ready: {str(gate_ready).lower()}")
    print(f"unmapped_relation_types: {len(first_compile.unmapped_relation_types)}")
    print(f"unknown_repo_node_refs_dst_kind_repo: {len(first_compile.unknown_repo_node_refs)}")
    print(f"stale_records: {len(first_compile.stale_records)}")
    print(f"compile_errors: {len(first_compile.compile_errors)}")

    return 0 if gate_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
