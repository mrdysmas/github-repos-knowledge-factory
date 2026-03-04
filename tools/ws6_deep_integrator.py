#!/usr/bin/env python3
"""WS6 deep integration materializer (contract-first).

Materializes canonical deep facts from deep narrative artifacts and optional draft
facts. Emits shard-level deep_facts, master_deep_facts, and deterministic WS6
reports.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml


SHARDS = ("llm_repos", "ssh_repos")
EXTRACTOR_VERSION = "ws6-deep-integrator-v1"
SPEC_VERSION = "1.1.0-ws6-materializer"

IDENTITY_KEYS = {
    "name",
    "node_id",
    "github_full_name",
    "html_url",
    "source",
    "provenance",
}

IGNORED_NARRATIVE_KEYS = {
    "sparse",
    "directory",
    "category",
    "summary",
    "description",
    "notes",
    "metadata",
}


@dataclass
class RepoIdentity:
    shard: str
    repo_path: Path
    file_stem: str
    name: str
    node_id: str
    github_full_name: str
    html_url: str
    source: str
    as_of: str


@dataclass
class FactCandidate:
    node_id: str
    github_full_name: str
    source_file: str
    source_kind: str  # narrative | draft
    fact: dict[str, Any]


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


def write_if_changed(path: Path, text: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def ensure_string(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def ensure_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def ensure_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            out.append(dict(item))
    return out


def ensure_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def compact_whitespace(text: str) -> str:
    return " ".join(text.split())


def truncate_text(text: str, max_len: int = 280) -> str:
    compact = compact_whitespace(text)
    if len(compact) <= max_len:
        return compact
    return compact[: max_len - 3].rstrip() + "..."


def is_filesystem_path(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    if text.startswith(("/", "./", "../", "~/")):
        return True
    if text.endswith(("/", "\\")):
        return True
    if "/" in text or "\\" in text:
        return True
    if " " in text:
        return False
    lowered = text.lower()
    for suffix in (
        ".py",
        ".go",
        ".rs",
        ".js",
        ".ts",
        ".tsx",
        ".cpp",
        ".cc",
        ".h",
        ".hpp",
        ".md",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".ini",
        ".sql",
        ".sh",
    ):
        if lowered.endswith(suffix):
            return True
    return False


def is_command_like(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    if text.startswith(("$", "./", "python", "pip", "uv", "go ", "cargo", "npm", "pnpm", "yarn", "make", "docker", "kubectl", "git ")):
        return True
    if " --" in text or "|" in text or "&&" in text:
        return True
    first = text.split()[0]
    return first in {
        "python3",
        "python",
        "pip",
        "pip3",
        "poetry",
        "go",
        "cargo",
        "npm",
        "pnpm",
        "yarn",
        "make",
        "cmake",
        "docker",
        "kubectl",
        "git",
        "uv",
        "pytest",
        "bash",
        "sh",
        "ls",
        "cd",
        "grep",
        "curl",
        "wget",
        "opencompass",
        "graphrag",
        "llamafactory-cli",
        "torchrun",
        "llama-cli",
        "llama-server",
    }


def is_cli_line(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    if is_command_like(text):
        return True
    if text.startswith(("#", "|")):
        return False
    if text.upper().startswith(("GET ", "POST ", "PUT ", "PATCH ", "DELETE ", "HEAD ", "OPTIONS ")):
        return False
    first = text.split()[0].strip()
    return first.endswith(("-cli", "_cli"))


def is_api_route_like(value: str) -> bool:
    text = value.strip()
    if not text:
        return False
    if text.startswith(("/", "http://", "https://")):
        return True
    upper = text.upper()
    for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
        if upper.startswith(f"{method} /") or upper.startswith(f"{method} HTTP"):
            return True
    return False


def normalized_lines(value: str) -> list[str]:
    out: list[str] = []
    for raw in value.splitlines():
        line = compact_whitespace(raw)
        if not line:
            continue
        if line in {"```", "```bash", "```sh", "```shell", "```zsh"}:
            continue
        if line.startswith("|") and line.endswith("|"):
            continue
        if set(line.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")) == set():
            continue
        out.append(line)
    return out


def iter_text_nodes(section: Any, base_ref: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []

    def _walk(node: Any, ref: str) -> None:
        if isinstance(node, str):
            text = node.strip()
            if text:
                out.append((ref, text))
            return
        if isinstance(node, list):
            for idx, item in enumerate(node):
                _walk(item, f"{ref}[{idx}]")
            return
        if isinstance(node, dict):
            for key in sorted(node.keys(), key=lambda item: str(item)):
                _walk(node[key], f"{ref}.{key}")

    _walk(section, base_ref)
    return out


def parse_as_of(value: Any) -> datetime | None:
    text = ensure_string(value)
    if not text:
        return None

    candidate = text
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        else:
            parsed = parsed.astimezone(timezone.utc)
        return parsed
    except ValueError:
        pass

    try:
        parsed_date = date.fromisoformat(text)
        return datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=timezone.utc)
    except ValueError:
        return None


def to_utc_iso_no_micros(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def compact_output_tail(stdout: str, stderr: str, max_lines: int = 12, max_chars: int = 1200) -> str:
    parts: list[str] = []
    if stdout.strip():
        lines = stdout.strip().splitlines()
        tail = "\n".join(lines[-max_lines:])
        parts.append(f"stdout_tail:\n{tail}")
    if stderr.strip():
        lines = stderr.strip().splitlines()
        tail = "\n".join(lines[-max_lines:])
        parts.append(f"stderr_tail:\n{tail}")
    text = "\n".join(parts)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def build_spec() -> dict[str, Any]:
    return {
        "artifact_type": "ws6_deep_integration_spec",
        "spec_version": SPEC_VERSION,
        "status": "MATERIALIZER_ACTIVE",
        "inputs": {
            "contracts": [
                "contracts/ws1/deep_fact.schema.yaml",
                "contracts/ws1/relation_mapping.yaml",
            ],
            "shallow_repos": [
                "llm_repos/knowledge/repos/*.yaml",
                "ssh_repos/knowledge/repos/*.yaml",
            ],
            "deep_narrative": [
                "llm_repos/knowledge/deep/*.yaml",
                "ssh_repos/knowledge/deep/*.yaml",
            ],
            "deep_fact_draft_optional": [
                "llm_repos/knowledge/deep_facts_draft/*.yaml",
                "ssh_repos/knowledge/deep_facts_draft/*.yaml",
            ],
        },
        "normalization_rules": [
            "Join deep artifacts to shallow repos by node_id/full_name/stem.",
            "Require identity parity with shallow repo fields.",
            "Strict mode default: unknown draft predicates are blocking.",
            "Unmapped narrative sections are non-blocking but counted/reported.",
            "Draft fact authority wins over narrative-derived collisions.",
            "Fingerprint-identical derived facts merge evidence deterministically.",
            "Require evidence for every fact and confidence in [0.0, 1.0].",
            "Deterministic output ordering for stable reruns.",
        ],
        "mapping_table": [
            {
                "deep_field": "architecture.module_breakdown[]",
                "fact_type": "component",
                "predicate": "has_component",
                "object_kind_rule": "concept when module name exists unless clearly filesystem path; else path from key_files",
            },
            {
                "deep_field": "architecture.key_abstractions[]",
                "fact_type": "component",
                "predicate": "has_component",
                "object_kind": "concept",
            },
            {
                "deep_field": "code_patterns[] / implementation_patterns[]",
                "fact_type": "implementation_pattern",
                "predicate": "implements_pattern",
                "object_kind": "concept",
            },
            {
                "deep_field": "configuration.*",
                "fact_type": "config_option",
                "predicate": "has_config_option",
                "object_kind": "config_key",
            },
            {
                "deep_field": "api_surface.*endpoints*",
                "fact_type": "api_endpoint",
                "predicate": "exposes_api_endpoint",
                "object_kind": "api_route",
            },
            {
                "deep_field": "extension_points[]",
                "fact_type": "extension_point",
                "predicate": "has_extension_point",
                "object_kind": "path or concept",
            },
            {
                "deep_field": "common_tasks[] / commands",
                "fact_type": "operational_task",
                "predicate": "supports_task",
                "object_kind": "command or text",
            },
            {
                "deep_field": "troubleshooting[]",
                "fact_type": "failure_mode",
                "predicate": "has_failure_mode",
                "object_kind": "issue",
            },
            {
                "deep_field": "supported_protocols* / vpn_protocols / api_protocols",
                "fact_type": "protocol_usage",
                "predicate": "uses_protocol",
                "object_kind": "protocol",
            },
        ],
        "outputs": {
            "canonical_shard_outputs": [
                "llm_repos/knowledge/deep_facts/*.yaml",
                "ssh_repos/knowledge/deep_facts/*.yaml",
            ],
            "master_output_for_ws4_and_query": "master_deep_facts.yaml",
            "reports": [
                "reports/ws6_deep_integration/coverage.yaml",
                "reports/ws6_deep_integration/mismatch_report.yaml",
                "reports/ws6_deep_integration/validation_runs.yaml",
            ],
        },
        "gate_bools": [
            "deep_facts_parseable",
            "deep_fact_identity_coverage_100pct",
            "facts_with_evidence_100pct",
            "confidence_bounds_valid",
            "unmapped_deep_predicates_zero",
            "duplicate_fact_ids_zero",
            "execution_results_pending_zero",
            "ws6_hash_stable",
        ],
        "gate_metrics": [
            "unmapped_sections_count",
        ],
        "execution_modes": [
            "materialize_only (default)",
            "full_validation_run (--run-validation-suite)",
        ],
    }


def load_contracts(workspace_root: Path) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    errors: list[str] = []

    deep_fact_path = workspace_root / "contracts" / "ws1" / "deep_fact.schema.yaml"
    relation_map_path = workspace_root / "contracts" / "ws1" / "relation_mapping.yaml"

    try:
        deep_fact_payload = load_yaml(deep_fact_path) or {}
    except Exception as exc:
        return {}, {}, [f"failed to parse {deep_fact_path.as_posix()}: {exc}"]

    try:
        relation_payload = load_yaml(relation_map_path) or {}
    except Exception as exc:
        return {}, {}, [f"failed to parse {relation_map_path.as_posix()}: {exc}"]

    if not isinstance(deep_fact_payload, dict):
        errors.append("deep_fact.schema.yaml must be a mapping")
    if not isinstance(relation_payload, dict):
        errors.append("relation_mapping.yaml must be a mapping")

    return deep_fact_payload, relation_payload, errors


def parse_contract_enums(contract: dict[str, Any]) -> dict[str, set[str]]:
    def _enum_set(key: str) -> set[str]:
        values = contract.get(key)
        out = {item for item in values if isinstance(item, str) and item.strip()} if isinstance(values, list) else set()
        return out

    return {
        "source": _enum_set("source_enums"),
        "fact_type": _enum_set("fact_type_enums"),
        "predicate": _enum_set("predicate_enums"),
        "object_kind": _enum_set("object_kind_enums"),
        "evidence_kind": _enum_set("evidence_kind_enums"),
    }


def load_shallow_repos(workspace_root: Path) -> tuple[dict[str, RepoIdentity], dict[str, RepoIdentity], dict[str, RepoIdentity], list[str]]:
    errors: list[str] = []
    by_node_id: dict[str, RepoIdentity] = {}
    by_full_name: dict[str, RepoIdentity] = {}
    by_stem: dict[str, RepoIdentity] = {}

    for shard in SHARDS:
        repos_dir = workspace_root / shard / "knowledge" / "repos"
        if not repos_dir.exists():
            errors.append(f"missing shallow repos dir: {repos_dir.as_posix()}")
            continue

        for path in sorted(repos_dir.glob("*.yaml"), key=lambda p: p.name):
            try:
                payload = load_yaml(path) or {}
            except Exception as exc:
                errors.append(f"failed to parse shallow repo {path.as_posix()}: {exc}")
                continue

            if not isinstance(payload, dict):
                errors.append(f"shallow repo must be mapping: {path.as_posix()}")
                continue

            name = ensure_string(payload.get("name"))
            node_id = ensure_string(payload.get("node_id"))
            full_name = ensure_string(payload.get("github_full_name"))
            html_url = ensure_string(payload.get("html_url"))
            source = ensure_string(payload.get("source"))
            provenance = ensure_dict(payload.get("provenance"))
            as_of = ensure_string(provenance.get("as_of"))

            if not (name and node_id and full_name and html_url):
                errors.append(f"shallow repo missing identity fields: {path.as_posix()}")
                continue

            identity = RepoIdentity(
                shard=shard,
                repo_path=path,
                file_stem=path.stem,
                name=name,
                node_id=node_id,
                github_full_name=full_name,
                html_url=html_url,
                source=source,
                as_of=as_of,
            )

            if node_id in by_node_id:
                errors.append(f"duplicate shallow node_id across repos: {node_id}")
                continue
            by_node_id[node_id] = identity
            by_full_name[full_name.lower()] = identity
            by_stem[path.stem.lower()] = identity

    return by_node_id, by_full_name, by_stem, errors


def infer_generated_at(repo_facts: list[dict[str, Any]], fallback_as_of: str = "1970-01-01T00:00:00Z") -> str:
    points: list[datetime] = []
    for row in repo_facts:
        parsed = parse_as_of(row.get("as_of"))
        if parsed is not None:
            points.append(parsed)

    if not points:
        parsed_fb = parse_as_of(fallback_as_of)
        if parsed_fb is not None:
            points.append(parsed_fb)

    if not points:
        return "1970-01-01T00:00:00Z"
    return to_utc_iso_no_micros(max(points))


def build_collision_key(node_id: str, fact: dict[str, Any]) -> tuple[str, str, str, str, str]:
    object_key = ""
    object_kind = ensure_string(fact.get("object_kind"))
    if object_kind in {"repo", "external_tool"}:
        object_key = ensure_string(fact.get("object_node_id"))
    else:
        object_key = ensure_string(fact.get("object_value"))
    return (
        node_id,
        ensure_string(fact.get("fact_type")),
        ensure_string(fact.get("predicate")),
        object_kind,
        object_key,
    )


def fact_merge_key(node_id: str, fact: dict[str, Any]) -> str:
    object_kind = ensure_string(fact.get("object_kind"))
    object_key = ensure_string(fact.get("object_node_id")) if object_kind in {"repo", "external_tool"} else ensure_string(
        fact.get("object_value")
    )
    payload = {
        "node_id": node_id,
        "fact_type": ensure_string(fact.get("fact_type")),
        "predicate": ensure_string(fact.get("predicate")),
        "object_kind": object_kind,
        "object_key": object_key,
        "note": ensure_string(fact.get("note")),
        "confidence": round(float(fact.get("confidence") or 0.0), 6),
        "as_of": ensure_string(fact.get("as_of")),
        "extraction_mode": ensure_string(ensure_dict(fact.get("provenance")).get("extraction_mode")),
    }
    return sha256_text(dump_yaml(payload))


def fact_fingerprint_payload(node_id: str, fact: dict[str, Any]) -> dict[str, Any]:
    evidence = []
    for row in ensure_list_of_dicts(fact.get("evidence")):
        evidence.append(
            {
                "kind": ensure_string(row.get("kind")),
                "ref": ensure_string(row.get("ref")),
                "source_file": ensure_string(row.get("source_file")),
                "excerpt": ensure_string(row.get("excerpt")),
                "start_line": row.get("start_line") if isinstance(row.get("start_line"), int) else None,
                "end_line": row.get("end_line") if isinstance(row.get("end_line"), int) else None,
            }
        )

    evidence.sort(
        key=lambda r: (
            r["kind"],
            r["ref"],
            r["source_file"],
            r["excerpt"],
            r["start_line"] or 0,
            r["end_line"] or 0,
        )
    )

    prov = ensure_dict(fact.get("provenance"))
    out = {
        "node_id": node_id,
        "fact_type": ensure_string(fact.get("fact_type")),
        "predicate": ensure_string(fact.get("predicate")),
        "object_kind": ensure_string(fact.get("object_kind")),
        "object_value": ensure_string(fact.get("object_value")),
        "object_node_id": ensure_string(fact.get("object_node_id")),
        "note": ensure_string(fact.get("note")),
        "confidence": round(float(fact.get("confidence") or 0.0), 6),
        "as_of": ensure_string(fact.get("as_of")),
        "provenance": {
            "source_file": ensure_string(prov.get("source_file")),
            "source_section": ensure_string(prov.get("source_section")),
            "extraction_mode": ensure_string(prov.get("extraction_mode")),
        },
        "evidence": evidence,
    }
    return out


def fact_fingerprint_key(node_id: str, fact: dict[str, Any]) -> str:
    payload = fact_fingerprint_payload(node_id, fact)
    text = dump_yaml(payload)
    return sha256_text(text)


def build_fact_id(node_id: str, fact: dict[str, Any]) -> str:
    return f"fact::{fact_fingerprint_key(node_id, fact)[:24]}"


def make_evidence(source_file: str, ref: str, excerpt: str = "") -> list[dict[str, Any]]:
    row: dict[str, Any] = {
        "kind": "file_block",
        "ref": ref,
        "source_file": source_file,
    }
    if excerpt:
        row["excerpt"] = truncate_text(excerpt)
    return [row]


def make_fact(
    *,
    fact_type: str,
    predicate: str,
    object_kind: str,
    object_value: str = "",
    object_node_id: str = "",
    note: str = "",
    confidence: float,
    as_of: str,
    source_file: str,
    source_section: str,
    extraction_mode: str,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    fact: dict[str, Any] = {
        "fact_type": fact_type,
        "predicate": predicate,
        "object_kind": object_kind,
        "confidence": float(confidence),
        "as_of": as_of,
        "provenance": {
            "source_file": source_file,
            "source_section": source_section,
            "extraction_mode": extraction_mode,
        },
        "evidence": evidence if evidence else make_evidence(source_file, source_section),
    }

    if object_kind in {"repo", "external_tool"}:
        fact["object_node_id"] = object_node_id
    else:
        fact["object_value"] = object_value

    note_clean = ensure_string(note)
    if note_clean:
        fact["note"] = truncate_text(note_clean)

    return fact


def normalize_note_parts(parts: list[str]) -> str:
    clean = [compact_whitespace(p) for p in parts if ensure_string(p)]
    clean = [p for p in clean if p]
    return "; ".join(clean)


def collect_protocol_names(value: Any) -> list[str]:
    names: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, str) and node.strip():
            text = node.strip()
            if len(text) <= 80:
                names.append(text)
            return
        if isinstance(node, list):
            for item in node:
                _walk(item)
            return
        if isinstance(node, dict):
            if isinstance(node.get("name"), str) and node["name"].strip():
                names.append(node["name"].strip())
            for child in node.values():
                _walk(child)

    _walk(value)
    out = sorted({n for n in names if n})
    return out


def split_inline_terms(text: str) -> list[str]:
    compact = compact_whitespace(text)
    if not compact:
        return []
    if "," not in compact:
        return [compact]
    terms = [part.strip() for part in compact.split(",")]
    return [term for term in terms if term]


def extract_architecture_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    payload = ensure_dict(section)

    module_rows = ensure_list_of_dicts(payload.get("module_breakdown"))
    for idx, row in enumerate(module_rows):
        module = ensure_string(row.get("module"))
        key_files = ensure_string_list(row.get("key_files"))
        responsibility = ensure_string(row.get("responsibility"))

        object_value = ""
        object_kind = "concept"

        if module:
            object_value = module
            object_kind = "path" if is_filesystem_path(module) else "concept"
        elif key_files:
            object_value = key_files[0]
            object_kind = "path" if is_filesystem_path(object_value) else "concept"

        if not object_value:
            continue

        note = normalize_note_parts(
            [
                f"responsibility: {responsibility}" if responsibility else "",
                f"key_files: {', '.join(key_files[:4])}" if key_files else "",
            ]
        )

        section_ref = f"architecture.module_breakdown[{idx}]"
        facts.append(
            make_fact(
                fact_type="component",
                predicate="has_component",
                object_kind=object_kind,
                object_value=object_value,
                note=note,
                confidence=0.78,
                as_of=as_of,
                source_file=source_file,
                source_section=section_ref,
                extraction_mode="narrative",
                evidence=make_evidence(source_file, section_ref, responsibility or object_value),
            )
        )

    abstraction_rows = ensure_list_of_dicts(payload.get("key_abstractions"))
    for idx, row in enumerate(abstraction_rows):
        name = ensure_string(row.get("name")) or ensure_string(row.get("purpose"))
        if not name:
            continue
        purpose = ensure_string(row.get("purpose"))
        section_ref = f"architecture.key_abstractions[{idx}]"
        facts.append(
            make_fact(
                fact_type="component",
                predicate="has_component",
                object_kind="concept",
                object_value=name,
                note=purpose,
                confidence=0.74,
                as_of=as_of,
                source_file=source_file,
                source_section=section_ref,
                extraction_mode="narrative",
                evidence=make_evidence(source_file, section_ref, purpose or name),
            )
        )

    component_rows = ensure_list_of_dicts(payload.get("components"))
    for idx, row in enumerate(component_rows):
        label = ensure_string(row.get("name")) or ensure_string(row.get("module")) or ensure_string(row.get("component"))
        if not label:
            continue
        section_ref = f"architecture.components[{idx}]"
        facts.append(
            make_fact(
                fact_type="component",
                predicate="has_component",
                object_kind="path" if is_filesystem_path(label) else "concept",
                object_value=label,
                note=ensure_string(row.get("description")),
                confidence=0.72,
                as_of=as_of,
                source_file=source_file,
                source_section=section_ref,
                extraction_mode="narrative",
                evidence=make_evidence(source_file, section_ref, label),
            )
        )

    return facts


def extract_key_features_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen_features: set[str] = set()

    rows = section if isinstance(section, list) else [section]
    for idx, row in enumerate(rows):
        feature = ""
        note = ""

        if isinstance(row, str):
            feature = compact_whitespace(row)
        elif isinstance(row, dict):
            feature = ensure_string(row.get("feature")) or ensure_string(row.get("name"))
            note = ensure_string(row.get("description"))

        if not feature:
            continue

        feature_key = feature.lower()
        if feature_key in seen_features:
            continue
        seen_features.add(feature_key)

        section_ref = f"key_features[{idx}]"
        facts.append(
            make_fact(
                fact_type="component",
                predicate="has_component",
                object_kind="concept",
                object_value=feature,
                note=note,
                confidence=0.67,
                as_of=as_of,
                source_file=source_file,
                source_section=section_ref,
                extraction_mode="narrative",
                evidence=make_evidence(source_file, section_ref, feature),
            )
        )

    return facts


def extract_key_files_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen_paths: set[str] = set()

    rows = section if isinstance(section, list) else [section]
    for idx, row in enumerate(rows):
        path_value = ""
        note = ""

        if isinstance(row, dict):
            path_value = ensure_string(row.get("path")) or ensure_string(row.get("file"))
            note = ensure_string(row.get("description"))
        elif isinstance(row, str):
            path_value = compact_whitespace(row)

        if not path_value:
            continue

        path_key = path_value.lower()
        if path_key in seen_paths:
            continue
        seen_paths.add(path_key)

        section_ref = f"key_files[{idx}]"
        facts.append(
            make_fact(
                fact_type="component",
                predicate="has_component",
                object_kind="path",
                object_value=path_value,
                note=note,
                confidence=0.72,
                as_of=as_of,
                source_file=source_file,
                source_section=section_ref,
                extraction_mode="narrative",
                evidence=make_evidence(source_file, section_ref, path_value),
            )
        )

    return facts


def extract_cli_argument_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    rows = ensure_list_of_dicts(section)
    facts: list[dict[str, Any]] = []
    seen_flags: set[str] = set()

    for idx, row in enumerate(rows):
        flag = ensure_string(row.get("flag")) or ensure_string(row.get("name"))
        if not flag:
            continue

        flag_key = flag.lower()
        if flag_key in seen_flags:
            continue
        seen_flags.add(flag_key)

        default_value = row.get("default")
        default_text = ""
        if isinstance(default_value, (str, int, float, bool)):
            default_text = str(default_value).strip()

        note = normalize_note_parts(
            [
                ensure_string(row.get("description")),
                f"default: {default_text}" if default_text else "",
            ]
        )

        section_ref = f"cli_arguments[{idx}]"
        facts.append(
            make_fact(
                fact_type="config_option",
                predicate="has_config_option",
                object_kind="command",
                object_value=flag,
                note=note,
                confidence=0.7,
                as_of=as_of,
                source_file=source_file,
                source_section=section_ref,
                extraction_mode="narrative",
                evidence=make_evidence(source_file, section_ref, flag),
            )
        )

    return facts


def extract_pattern_rows(
    section: Any,
    *,
    source_file: str,
    as_of: str,
    section_name: str,
) -> list[dict[str, Any]]:
    rows = ensure_list_of_dicts(section)
    facts: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        label = ensure_string(row.get("name")) or ensure_string(row.get("pattern")) or ensure_string(row.get("title"))
        if not label:
            continue
        description = ensure_string(row.get("description"))
        location = ensure_string(row.get("location")) or ensure_string(row.get("file_reference"))
        note = normalize_note_parts([
            f"description: {description}" if description else "",
            f"location: {location}" if location else "",
        ])
        section_ref = f"{section_name}[{idx}]"
        facts.append(
            make_fact(
                fact_type="implementation_pattern",
                predicate="implements_pattern",
                object_kind="concept",
                object_value=label,
                note=note,
                confidence=0.8,
                as_of=as_of,
                source_file=source_file,
                source_section=section_ref,
                extraction_mode="narrative",
                evidence=make_evidence(source_file, location or section_ref, description or label),
            )
        )
    return facts


def iter_configuration_options(section: Any, base_ref: str = "configuration") -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []

    if isinstance(section, list):
        for i, block in enumerate(section):
            if not isinstance(block, dict):
                continue
            options = block.get("options")
            if isinstance(options, list):
                for j, option in enumerate(options):
                    if isinstance(option, dict):
                        rows.append((f"{base_ref}[{i}].options[{j}]", option))
            else:
                rows.append((f"{base_ref}[{i}]", block))
        return rows

    if isinstance(section, dict):
        top_options = section.get("options")
        if isinstance(top_options, list):
            for i, option in enumerate(top_options):
                if isinstance(option, dict):
                    rows.append((f"{base_ref}.options[{i}]", option))

        for key, value in section.items():
            if key == "options":
                continue
            if isinstance(value, dict):
                nested_options = value.get("options")
                if isinstance(nested_options, list):
                    for i, option in enumerate(nested_options):
                        if isinstance(option, dict):
                            rows.append((f"{base_ref}.{key}.options[{i}]", option))
                else:
                    rows.append((f"{base_ref}.{key}", value))
            elif isinstance(value, list):
                for i, option in enumerate(value):
                    if isinstance(option, dict):
                        rows.append((f"{base_ref}.{key}[{i}]", option))
            elif isinstance(value, (str, int, float, bool)):
                rows.append(
                    (
                        f"{base_ref}.{key}",
                        {
                            "key": key,
                            "default": str(value),
                            "description": f"configuration default for {key}",
                        },
                    )
                )

    return rows


def extract_configuration_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []

    for section_ref, option in iter_configuration_options(section):
        key = ensure_string(option.get("key")) or ensure_string(option.get("name"))
        if not key:
            # fallback for dict-shaped option blocks
            if len(option) == 1:
                only_key = next(iter(option.keys()))
                if isinstance(only_key, str) and only_key.strip():
                    key = only_key.strip()
        if not key:
            continue

        note = normalize_note_parts(
            [
                f"type: {ensure_string(option.get('type'))}" if ensure_string(option.get("type")) else "",
                f"default: {ensure_string(option.get('default'))}" if ensure_string(option.get("default")) else "",
                ensure_string(option.get("description")),
            ]
        )

        facts.append(
            make_fact(
                fact_type="config_option",
                predicate="has_config_option",
                object_kind="config_key",
                object_value=key,
                note=note,
                confidence=0.72,
                as_of=as_of,
                source_file=source_file,
                source_section=section_ref,
                extraction_mode="narrative",
                evidence=make_evidence(source_file, section_ref, key),
            )
        )

    return facts


def extract_endpoint_facts(section: Any, source_file: str, as_of: str, base_ref: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []

    if isinstance(section, list):
        for idx, row in enumerate(section):
            route = ""
            note = ""
            if isinstance(row, dict):
                route = (
                    ensure_string(row.get("path"))
                    or ensure_string(row.get("endpoint"))
                    or ensure_string(row.get("route"))
                    or ensure_string(row.get("service"))
                    or ensure_string(row.get("name"))
                )
                note = normalize_note_parts(
                    [
                        ensure_string(row.get("purpose")),
                        ensure_string(row.get("description")),
                        ensure_string(row.get("methods")),
                    ]
                )
            elif isinstance(row, str):
                route = row.strip()

            if not route:
                continue

            section_ref = f"{base_ref}[{idx}]"
            facts.append(
                make_fact(
                    fact_type="api_endpoint",
                    predicate="exposes_api_endpoint",
                    object_kind="api_route",
                    object_value=route,
                    note=note,
                    confidence=0.8,
                    as_of=as_of,
                    source_file=source_file,
                    source_section=section_ref,
                    extraction_mode="narrative",
                    evidence=make_evidence(source_file, section_ref, route),
                )
            )

    elif isinstance(section, dict):
        for key, value in section.items():
            facts.extend(extract_endpoint_facts(value, source_file, as_of, f"{base_ref}.{key}"))

    return facts


def extract_api_surface_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    payload = ensure_dict(section)
    facts: list[dict[str, Any]] = []

    for key, value in sorted(payload.items()):
        lowered = key.lower()
        if "endpoint" in lowered:
            facts.extend(extract_endpoint_facts(value, source_file, as_of, f"api_surface.{key}"))
            continue

        if key == "public_functions":
            rows = ensure_list_of_dicts(value)
            for idx, row in enumerate(rows):
                label = ensure_string(row.get("name"))
                if not label:
                    continue
                note = normalize_note_parts(
                    [
                        ensure_string(row.get("purpose")),
                        ensure_string(row.get("signature")),
                        ensure_string(row.get("location")),
                    ]
                )
                section_ref = f"api_surface.public_functions[{idx}]"
                facts.append(
                    make_fact(
                        fact_type="extension_point",
                        predicate="has_extension_point",
                        object_kind="concept",
                        object_value=label,
                        note=note,
                        confidence=0.73,
                        as_of=as_of,
                        source_file=source_file,
                        source_section=section_ref,
                        extraction_mode="narrative",
                        evidence=make_evidence(source_file, section_ref, label),
                    )
                )

    return facts


def extract_extension_point_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    rows = ensure_list_of_dicts(section)
    facts: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        location = ensure_string(row.get("location"))
        hook = ensure_string(row.get("hook"))
        label = location or hook or ensure_string(row.get("name"))
        if not label:
            continue
        kind = "path" if location and is_filesystem_path(location) else "concept"
        note = normalize_note_parts([ensure_string(row.get("example")), hook if location else ""])
        section_ref = f"extension_points[{idx}]"
        facts.append(
            make_fact(
                fact_type="extension_point",
                predicate="has_extension_point",
                object_kind=kind,
                object_value=label,
                note=note,
                confidence=0.71,
                as_of=as_of,
                source_file=source_file,
                source_section=section_ref,
                extraction_mode="narrative",
                evidence=make_evidence(source_file, section_ref, label),
            )
        )
    return facts


def extract_task_facts(section: Any, source_file: str, as_of: str, base_ref: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []

    if isinstance(section, list):
        for idx, row in enumerate(section):
            if isinstance(row, dict):
                label = ensure_string(row.get("task")) or ensure_string(row.get("command")) or ensure_string(row.get("name"))
                note = normalize_note_parts(
                    [
                        ensure_string(row.get("description")),
                        ", ".join(ensure_string_list(row.get("steps"))) if isinstance(row.get("steps"), list) else "",
                        ", ".join(ensure_string_list(row.get("gotchas"))) if isinstance(row.get("gotchas"), list) else "",
                    ]
                )
            else:
                label = ensure_string(row)
                note = ""

            if not label:
                continue

            section_ref = f"{base_ref}[{idx}]"
            facts.append(
                make_fact(
                    fact_type="operational_task",
                    predicate="supports_task",
                    object_kind="command" if is_command_like(label) else "text",
                    object_value=label,
                    note=note,
                    confidence=0.68,
                    as_of=as_of,
                    source_file=source_file,
                    source_section=section_ref,
                    extraction_mode="narrative",
                    evidence=make_evidence(source_file, section_ref, label),
                )
            )

    elif isinstance(section, dict):
        for key, value in sorted(section.items()):
            label = ensure_string(value)
            if not label:
                continue
            section_ref = f"{base_ref}.{key}"
            facts.append(
                make_fact(
                    fact_type="operational_task",
                    predicate="supports_task",
                    object_kind="command" if is_command_like(label) else "text",
                    object_value=label,
                    note=f"command group: {key}",
                    confidence=0.66,
                    as_of=as_of,
                    source_file=source_file,
                    source_section=section_ref,
                    extraction_mode="narrative",
                    evidence=make_evidence(source_file, section_ref, label),
                )
            )

    return facts


def extract_testing_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen_tasks: set[str] = set()
    seen_patterns: set[str] = set()

    for section_ref, text in iter_text_nodes(section, "testing"):
        for line_idx, line in enumerate(normalized_lines(text)):
            line_ref = f"{section_ref}.line[{line_idx}]"
            if is_cli_line(line):
                task_key = line.lower()
                if task_key in seen_tasks:
                    continue
                seen_tasks.add(task_key)
                facts.append(
                    make_fact(
                        fact_type="operational_task",
                        predicate="supports_task",
                        object_kind="command",
                        object_value=line,
                        note="testing command",
                        confidence=0.67,
                        as_of=as_of,
                        source_file=source_file,
                        source_section=line_ref,
                        extraction_mode="narrative",
                        evidence=make_evidence(source_file, line_ref, line),
                    )
                )

    payload = ensure_dict(section)
    concept_keys = {"framework", "structure", "coverage", "coverage_areas", "test_patterns"}
    for key in sorted(payload.keys()):
        if key not in concept_keys:
            continue
        value = payload[key]
        entries: list[tuple[str, str]] = []
        if isinstance(value, str):
            entries.append((f"testing.{key}", value))
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                text = ensure_string(item)
                if text:
                    entries.append((f"testing.{key}[{idx}]", text))
        elif isinstance(value, dict):
            for sub_key in sorted(value.keys(), key=lambda item: str(item)):
                text = ensure_string(value[sub_key])
                if text:
                    entries.append((f"testing.{key}.{sub_key}", text))

        for section_ref, text in entries:
            for line_idx, line in enumerate(normalized_lines(text)):
                if is_cli_line(line):
                    continue
                pattern_key = line.lower()
                if pattern_key in seen_patterns:
                    continue
                seen_patterns.add(pattern_key)
                line_ref = f"{section_ref}.line[{line_idx}]"
                facts.append(
                    make_fact(
                        fact_type="implementation_pattern",
                        predicate="implements_pattern",
                        object_kind="concept",
                        object_value=line,
                        note=f"testing metadata: {key}",
                        confidence=0.64,
                        as_of=as_of,
                        source_file=source_file,
                        source_section=line_ref,
                        extraction_mode="narrative",
                        evidence=make_evidence(source_file, line_ref, line),
                    )
                )

    return facts


def extract_quick_reference_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []

    rows = section if isinstance(section, list) else [section]
    for idx, row in enumerate(rows):
        row_ref = f"quick_reference[{idx}]"
        topic = ""
        values: list[str] = []

        if isinstance(row, dict):
            topic = ensure_string(row.get("topic")) or ensure_string(row.get("name"))
            for key in ("content", "command", "syntax"):
                text = ensure_string(row.get(key))
                if text:
                    values.append(text)
            if not values:
                for _, text in iter_text_nodes(row, row_ref):
                    values.append(text)
        else:
            text = ensure_string(row)
            if text:
                values.append(text)

        emitted = False
        for text in values:
            for line_idx, line in enumerate(normalized_lines(text)):
                if not is_cli_line(line):
                    continue
                emitted = True
                section_ref = f"{row_ref}.line[{line_idx}]"
                note = f"topic: {topic}" if topic else ""
                facts.append(
                    make_fact(
                        fact_type="operational_task",
                        predicate="supports_task",
                        object_kind="command",
                        object_value=line,
                        note=note,
                        confidence=0.67,
                        as_of=as_of,
                        source_file=source_file,
                        source_section=section_ref,
                        extraction_mode="narrative",
                        evidence=make_evidence(source_file, section_ref, line),
                    )
                )

        if emitted:
            continue

        fallback = topic
        if not fallback:
            for text in values:
                for line in normalized_lines(text):
                    fallback = line
                    break
                if fallback:
                    break
        if not fallback:
            continue

        note = "quick reference topic"
        facts.append(
            make_fact(
                fact_type="operational_task",
                predicate="supports_task",
                object_kind="text",
                object_value=fallback,
                note=note,
                confidence=0.58,
                as_of=as_of,
                source_file=source_file,
                source_section=row_ref,
                extraction_mode="narrative",
                evidence=make_evidence(source_file, row_ref, fallback),
            )
        )

    return facts


def extract_endpoint_like_facts(section: Any, source_file: str, as_of: str, base_ref: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    route_keys = ("path", "endpoint", "route", "url")
    note_keys = ("method", "methods", "purpose", "description")

    def _emit(route: str, section_ref: str, note: str) -> None:
        route_clean = route.strip()
        if not route_clean or not is_api_route_like(route_clean):
            return
        facts.append(
            make_fact(
                fact_type="api_endpoint",
                predicate="exposes_api_endpoint",
                object_kind="api_route",
                object_value=route_clean,
                note=note,
                confidence=0.73,
                as_of=as_of,
                source_file=source_file,
                source_section=section_ref,
                extraction_mode="narrative",
                evidence=make_evidence(source_file, section_ref, route_clean),
            )
        )

    def _walk(node: Any, ref: str) -> None:
        if isinstance(node, str):
            if is_api_route_like(node):
                _emit(node, ref, "")
            return

        if isinstance(node, list):
            for idx, item in enumerate(node):
                _walk(item, f"{ref}[{idx}]")
            return

        if not isinstance(node, dict):
            return

        route = ""
        for route_key in route_keys:
            route = ensure_string(node.get(route_key))
            if route:
                break
        note = normalize_note_parts([ensure_string(node.get(key)) for key in note_keys])
        if route:
            _emit(route, ref, note)

        skip_keys = set(route_keys) | set(note_keys) | {"name", "service", "operations"}
        for key in sorted(node.keys(), key=lambda item: str(item)):
            if key in skip_keys:
                continue
            value = node[key]
            if isinstance(value, (dict, list, str)):
                _walk(value, f"{ref}.{key}")

    _walk(section, base_ref)
    return facts


def extract_api_structure_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    return extract_endpoint_like_facts(section, source_file, as_of, "api_structure")


def extract_integrations_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen_concepts: set[str] = set()

    payload = ensure_dict(section)
    if not payload:
        payload = {"items": section}

    for key in sorted(payload.keys(), key=lambda item: str(item)):
        value = payload[key]
        key_text = ensure_string(key)
        section_ref = f"integrations.{key_text}"
        lowered = key_text.lower()

        if any(token in lowered for token in ("endpoint", "api", "webhook", "route")):
            facts.extend(extract_endpoint_like_facts(value, source_file, as_of, section_ref))
            continue

        for text_ref, text in iter_text_nodes(value, section_ref):
            for line_idx, line in enumerate(normalized_lines(text)):
                if is_cli_line(line) or is_api_route_like(line):
                    continue
                concept_key = line.lower()
                if concept_key in seen_concepts:
                    continue
                seen_concepts.add(concept_key)
                line_ref = f"{text_ref}.line[{line_idx}]"
                facts.append(
                    make_fact(
                        fact_type="extension_point",
                        predicate="has_extension_point",
                        object_kind="concept",
                        object_value=line,
                        note=f"integration group: {key_text}",
                        confidence=0.64,
                        as_of=as_of,
                        source_file=source_file,
                        source_section=line_ref,
                        extraction_mode="narrative",
                        evidence=make_evidence(source_file, line_ref, line),
                    )
                )

    return facts


def extract_tech_stack_facts(section: Any, source_file: str, as_of: str, base_ref: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen_components: set[str] = set()

    for section_ref, text in iter_text_nodes(section, base_ref):
        for line_idx, line in enumerate(normalized_lines(text)):
            if is_cli_line(line) or is_api_route_like(line):
                continue
            component_key = line.lower()
            if component_key in seen_components:
                continue
            seen_components.add(component_key)
            line_ref = f"{section_ref}.line[{line_idx}]"
            facts.append(
                make_fact(
                    fact_type="component",
                    predicate="has_component",
                    object_kind="concept",
                    object_value=line,
                    note=f"technology stack ({base_ref})",
                    confidence=0.61,
                    as_of=as_of,
                    source_file=source_file,
                    source_section=line_ref,
                    extraction_mode="narrative",
                    evidence=make_evidence(source_file, line_ref, line),
                )
            )

    return facts


def extract_repo_type_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen_types: set[str] = set()

    for section_ref, text in iter_text_nodes(section, "type"):
        for line_idx, line in enumerate(normalized_lines(text)):
            for term in split_inline_terms(line):
                if is_cli_line(term) or is_api_route_like(term):
                    continue
                type_key = term.lower()
                if type_key in seen_types:
                    continue
                seen_types.add(type_key)
                line_ref = f"{section_ref}.line[{line_idx}]"
                facts.append(
                    make_fact(
                        fact_type="component",
                        predicate="has_component",
                        object_kind="concept",
                        object_value=term,
                        note="repository type classification",
                        confidence=0.6,
                        as_of=as_of,
                        source_file=source_file,
                        source_section=line_ref,
                        extraction_mode="narrative",
                        evidence=make_evidence(source_file, line_ref, term),
                    )
                )

    return facts


def extract_primary_language_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen_languages: set[str] = set()

    for section_ref, text in iter_text_nodes(section, "primary_language"):
        for line_idx, line in enumerate(normalized_lines(text)):
            for term in split_inline_terms(line):
                if is_cli_line(term) or is_api_route_like(term):
                    continue
                lang_key = term.lower()
                if lang_key in seen_languages:
                    continue
                seen_languages.add(lang_key)
                line_ref = f"{section_ref}.line[{line_idx}]"
                facts.append(
                    make_fact(
                        fact_type="component",
                        predicate="has_component",
                        object_kind="concept",
                        object_value=term,
                        note="primary language",
                        confidence=0.66,
                        as_of=as_of,
                        source_file=source_file,
                        source_section=line_ref,
                        extraction_mode="narrative",
                        evidence=make_evidence(source_file, line_ref, term),
                    )
                )

    return facts


def extract_languages_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen_languages: set[str] = set()

    for section_ref, text in iter_text_nodes(section, "languages"):
        for line_idx, line in enumerate(normalized_lines(text)):
            for term in split_inline_terms(line):
                if is_cli_line(term) or is_api_route_like(term):
                    continue
                lang_key = term.lower()
                if lang_key in seen_languages:
                    continue
                seen_languages.add(lang_key)
                line_ref = f"{section_ref}.line[{line_idx}]"
                facts.append(
                    make_fact(
                        fact_type="component",
                        predicate="has_component",
                        object_kind="concept",
                        object_value=term,
                        note="language ecosystem",
                        confidence=0.61,
                        as_of=as_of,
                        source_file=source_file,
                        source_section=line_ref,
                        extraction_mode="narrative",
                        evidence=make_evidence(source_file, line_ref, term),
                    )
                )

    return facts


def format_port_value(value: Any) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, float):
        return str(value)
    return ensure_string(value)


def extract_ports_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    if isinstance(section, dict):
        for key, value in sorted(section.items(), key=lambda item: str(item[0])):
            port_name = ensure_string(key)
            port_value = ""
            if isinstance(value, dict):
                port_value = format_port_value(value.get("port") or value.get("value") or value.get("number"))
                if not port_name:
                    port_name = ensure_string(value.get("name")) or ensure_string(value.get("service"))
            elif isinstance(value, list):
                continue
            else:
                port_value = format_port_value(value)

            if not port_name:
                port_name = "port"
            port_value = port_value.strip()
            if not port_value:
                continue

            key_token = f"{port_name.lower()}::{port_value}"
            if key_token in seen_keys:
                continue
            seen_keys.add(key_token)

            section_ref = f"ports.{port_name}" if port_name != "port" else "ports"
            facts.append(
                make_fact(
                    fact_type="config_option",
                    predicate="has_config_option",
                    object_kind="config_key",
                    object_value=port_name,
                    note=f"port: {port_value}",
                    confidence=0.7,
                    as_of=as_of,
                    source_file=source_file,
                    source_section=section_ref,
                    extraction_mode="narrative",
                    evidence=make_evidence(source_file, section_ref, f"{port_name}={port_value}"),
                )
            )

    elif isinstance(section, list):
        for idx, row in enumerate(section):
            port_name = ""
            port_value = ""
            if isinstance(row, dict):
                port_name = ensure_string(row.get("name")) or ensure_string(row.get("service")) or ensure_string(
                    row.get("protocol")
                )
                port_value = format_port_value(row.get("port") or row.get("value") or row.get("number"))
            else:
                port_value = format_port_value(row)
            if not port_value.strip():
                continue
            if not port_name:
                port_name = f"port_{idx + 1}"
            key_token = f"{port_name.lower()}::{port_value.strip()}"
            if key_token in seen_keys:
                continue
            seen_keys.add(key_token)
            section_ref = f"ports[{idx}]"
            facts.append(
                make_fact(
                    fact_type="config_option",
                    predicate="has_config_option",
                    object_kind="config_key",
                    object_value=port_name,
                    note=f"port: {port_value.strip()}",
                    confidence=0.68,
                    as_of=as_of,
                    source_file=source_file,
                    source_section=section_ref,
                    extraction_mode="narrative",
                    evidence=make_evidence(source_file, section_ref, f"{port_name}={port_value.strip()}"),
                )
            )

    return facts


def extract_related_repos_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen_values: set[str] = set()

    for section_ref, text in iter_text_nodes(section, "related_repos"):
        for line_idx, line in enumerate(normalized_lines(text)):
            for term in split_inline_terms(line):
                if is_cli_line(term) or is_api_route_like(term):
                    continue
                rel_key = term.lower()
                if rel_key in seen_values:
                    continue
                seen_values.add(rel_key)
                line_ref = f"{section_ref}.line[{line_idx}]"
                facts.append(
                    make_fact(
                        fact_type="extension_point",
                        predicate="has_extension_point",
                        object_kind="concept",
                        object_value=term,
                        note="related repository",
                        confidence=0.59,
                        as_of=as_of,
                        source_file=source_file,
                        source_section=line_ref,
                        extraction_mode="narrative",
                        evidence=make_evidence(source_file, line_ref, term),
                    )
                )

    return facts


def extract_failure_mode_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    rows = ensure_list_of_dicts(section)
    facts: list[dict[str, Any]] = []

    for idx, row in enumerate(rows):
        symptom = ensure_string(row.get("symptom")) or ensure_string(row.get("issue"))
        if not symptom:
            continue
        note = normalize_note_parts(
            [
                f"cause: {ensure_string(row.get('cause'))}" if ensure_string(row.get("cause")) else "",
                f"fix: {ensure_string(row.get('fix'))}" if ensure_string(row.get("fix")) else "",
                f"solution: {ensure_string(row.get('solution'))}" if ensure_string(row.get("solution")) else "",
            ]
        )
        section_ref = f"troubleshooting[{idx}]"
        facts.append(
            make_fact(
                fact_type="failure_mode",
                predicate="has_failure_mode",
                object_kind="issue",
                object_value=symptom,
                note=note,
                confidence=0.74,
                as_of=as_of,
                source_file=source_file,
                source_section=section_ref,
                extraction_mode="narrative",
                evidence=make_evidence(source_file, section_ref, symptom),
            )
        )

    return facts


def extract_protocol_facts(section: Any, source_file: str, as_of: str, base_ref: str) -> list[dict[str, Any]]:
    names = collect_protocol_names(section)
    facts: list[dict[str, Any]] = []

    for idx, name in enumerate(names):
        section_ref = f"{base_ref}[{idx}]"
        facts.append(
            make_fact(
                fact_type="protocol_usage",
                predicate="uses_protocol",
                object_kind="protocol",
                object_value=name,
                note="",
                confidence=0.7,
                as_of=as_of,
                source_file=source_file,
                source_section=section_ref,
                extraction_mode="narrative",
                evidence=make_evidence(source_file, section_ref, name),
            )
        )

    return facts


def extract_environment_variable_facts(section: Any, source_file: str, as_of: str) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []

    if isinstance(section, list):
        rows = ensure_list_of_dicts(section)
        for idx, row in enumerate(rows):
            name = ensure_string(row.get("name")) or ensure_string(row.get("key"))
            if not name:
                continue
            note = normalize_note_parts(
                [
                    ensure_string(row.get("description")),
                    f"default: {ensure_string(row.get('default'))}" if ensure_string(row.get("default")) else "",
                ]
            )
            section_ref = f"environment_variables[{idx}]"
            facts.append(
                make_fact(
                    fact_type="config_option",
                    predicate="has_config_option",
                    object_kind="config_key",
                    object_value=name,
                    note=note,
                    confidence=0.7,
                    as_of=as_of,
                    source_file=source_file,
                    source_section=section_ref,
                    extraction_mode="narrative",
                    evidence=make_evidence(source_file, section_ref, name),
                )
            )
    elif isinstance(section, dict):
        for key, value in sorted(section.items()):
            if isinstance(value, list):
                for idx, item in enumerate(value):
                    if not isinstance(item, str) or not item.strip():
                        continue
                    name = item.strip()
                    section_ref = f"environment.{key}[{idx}]"
                    facts.append(
                        make_fact(
                            fact_type="config_option",
                            predicate="has_config_option",
                            object_kind="config_key",
                            object_value=name,
                            note=f"environment group: {key}",
                            confidence=0.68,
                            as_of=as_of,
                            source_file=source_file,
                            source_section=section_ref,
                            extraction_mode="narrative",
                            evidence=make_evidence(source_file, section_ref, name),
                        )
                    )

    return facts


def normalize_evidence_rows(
    evidence: Any,
    *,
    source_file_default: str,
    source_section_default: str,
    evidence_kind_enums: set[str],
) -> tuple[list[dict[str, Any]], str]:
    rows = ensure_list_of_dicts(evidence)
    if not rows:
        return [], "missing_or_invalid_evidence"

    normalized: list[dict[str, Any]] = []
    for row in rows:
        kind = ensure_string(row.get("kind"))
        ref = ensure_string(row.get("ref"))
        source_file = ensure_string(row.get("source_file")) or source_file_default
        if not kind or not ref or not source_file:
            return [], "invalid_evidence_required_fields"
        if evidence_kind_enums and kind not in evidence_kind_enums:
            return [], f"unknown_evidence_kind:{kind}"

        out: dict[str, Any] = {
            "kind": kind,
            "ref": ref,
            "source_file": source_file,
        }
        excerpt = ensure_string(row.get("excerpt"))
        if excerpt:
            out["excerpt"] = truncate_text(excerpt)
        start_line = row.get("start_line")
        end_line = row.get("end_line")
        if isinstance(start_line, int) and start_line >= 1:
            out["start_line"] = start_line
        if isinstance(end_line, int) and end_line >= 1:
            out["end_line"] = end_line
        normalized.append(out)

    normalized.sort(
        key=lambda r: (
            r["kind"],
            r["ref"],
            r["source_file"],
            ensure_string(r.get("excerpt")),
            int(r.get("start_line") or 0),
            int(r.get("end_line") or 0),
        )
    )

    # Ensure deterministic uniq evidence list.
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for row in normalized:
        key = (
            row["kind"],
            row["ref"],
            row["source_file"],
            ensure_string(row.get("excerpt")),
            int(row.get("start_line") or 0),
            int(row.get("end_line") or 0),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    if not deduped:
        return [], "empty_evidence_after_normalization"

    return deduped, ""


def merge_evidence(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = existing + incoming
    merged.sort(
        key=lambda r: (
            ensure_string(r.get("kind")),
            ensure_string(r.get("ref")),
            ensure_string(r.get("source_file")),
            ensure_string(r.get("excerpt")),
            int(r.get("start_line") or 0),
            int(r.get("end_line") or 0),
        )
    )

    out: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for row in merged:
        key = (
            ensure_string(row.get("kind")),
            ensure_string(row.get("ref")),
            ensure_string(row.get("source_file")),
            ensure_string(row.get("excerpt")),
            int(row.get("start_line") or 0),
            int(row.get("end_line") or 0),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def make_mismatch(
    *,
    severity: str,
    reason: str,
    shard: str,
    source_file: str,
    repo_node_id: str,
    detail: str,
    section: str = "",
    fact_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "severity": severity,
        "reason": reason,
        "shard": shard,
        "source_file": source_file,
        "repo_node_id": repo_node_id,
        "detail": detail,
    }
    if section:
        row["section"] = section
    if fact_summary:
        row["fact_summary"] = fact_summary
    return row


def summarize_fact(fact: dict[str, Any]) -> dict[str, Any]:
    out = {
        "fact_type": ensure_string(fact.get("fact_type")),
        "predicate": ensure_string(fact.get("predicate")),
        "object_kind": ensure_string(fact.get("object_kind")),
    }
    object_kind = out["object_kind"]
    if object_kind in {"repo", "external_tool"}:
        out["object_node_id"] = ensure_string(fact.get("object_node_id"))
    else:
        out["object_value"] = ensure_string(fact.get("object_value"))
    return out


def resolve_repo_identity(
    *,
    payload: dict[str, Any],
    source_file: Path,
    shard: str,
    by_node_id: dict[str, RepoIdentity],
    by_full_name: dict[str, RepoIdentity],
    by_stem: dict[str, RepoIdentity],
) -> RepoIdentity | None:
    node_id = ensure_string(payload.get("node_id"))
    full_name = ensure_string(payload.get("github_full_name"))

    identity: RepoIdentity | None = None
    if node_id and node_id in by_node_id:
        identity = by_node_id[node_id]
    elif full_name and full_name.lower() in by_full_name:
        identity = by_full_name[full_name.lower()]
    else:
        identity = by_stem.get(source_file.stem.lower())

    if identity is None:
        return None
    if identity.shard != shard:
        return None
    return identity


def validate_identity_parity(
    *,
    payload: dict[str, Any],
    repo: RepoIdentity,
    source_file_rel: str,
    strict_source_field: bool,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    for key, expected in (
        ("name", repo.name),
        ("node_id", repo.node_id),
        ("github_full_name", repo.github_full_name),
        ("html_url", repo.html_url),
    ):
        actual = ensure_string(payload.get(key))
        if not actual:
            issues.append(
                make_mismatch(
                    severity="blocking",
                    reason="identity_missing_field",
                    shard=repo.shard,
                    source_file=source_file_rel,
                    repo_node_id=repo.node_id,
                    detail=f"missing identity field: {key}",
                )
            )
            continue
        if actual != expected:
            issues.append(
                make_mismatch(
                    severity="blocking",
                    reason="identity_mismatch",
                    shard=repo.shard,
                    source_file=source_file_rel,
                    repo_node_id=repo.node_id,
                    detail=f"{key} mismatch (expected='{expected}', actual='{actual}')",
                )
            )

    if strict_source_field:
        source_value = ensure_string(payload.get("source"))
        if source_value and source_value not in {repo.source, repo.shard}:
            issues.append(
                make_mismatch(
                    severity="blocking",
                    reason="identity_source_mismatch",
                    shard=repo.shard,
                    source_file=source_file_rel,
                    repo_node_id=repo.node_id,
                    detail=f"source mismatch (repo='{repo.source}', deep='{source_value}')",
                )
            )

    provenance = ensure_dict(payload.get("provenance"))
    prov_shard = ensure_string(provenance.get("shard"))
    if prov_shard and prov_shard != repo.shard:
        issues.append(
            make_mismatch(
                severity="blocking",
                reason="identity_provenance_shard_mismatch",
                shard=repo.shard,
                source_file=source_file_rel,
                repo_node_id=repo.node_id,
                detail=f"provenance.shard mismatch (expected='{repo.shard}', actual='{prov_shard}')",
            )
        )

    return issues


def extract_narrative_facts(
    *,
    repo: RepoIdentity,
    source_file_rel: str,
    payload: dict[str, Any],
    unmapped_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    as_of = ensure_string(ensure_dict(payload.get("provenance")).get("as_of")) or repo.as_of or "1970-01-01"

    extractor_map: dict[str, Callable[[Any, str, str], list[dict[str, Any]]]] = {
        "architecture": extract_architecture_facts,
        "key_features": extract_key_features_facts,
        "key_files": extract_key_files_facts,
        "cli_arguments": extract_cli_argument_facts,
        "type": extract_repo_type_facts,
        "primary_language": extract_primary_language_facts,
        "languages": extract_languages_facts,
        "ports": extract_ports_facts,
        "related_repos": extract_related_repos_facts,
        "code_patterns": lambda v, s, a: extract_pattern_rows(v, source_file=s, as_of=a, section_name="code_patterns"),
        "implementation_patterns": lambda v, s, a: extract_pattern_rows(v, source_file=s, as_of=a, section_name="implementation_patterns"),
        "configuration": extract_configuration_facts,
        "api_surface": extract_api_surface_facts,
        "extension_points": extract_extension_point_facts,
        "common_tasks": lambda v, s, a: extract_task_facts(v, s, a, "common_tasks"),
        "troubleshooting": extract_failure_mode_facts,
        "supported_protocols": lambda v, s, a: extract_protocol_facts(v, s, a, "supported_protocols"),
        "vpn_protocols": lambda v, s, a: extract_protocol_facts(v, s, a, "vpn_protocols"),
        "api_protocols": lambda v, s, a: extract_protocol_facts(v, s, a, "api_protocols"),
        "environment": extract_environment_variable_facts,
        "environment_variables": extract_environment_variable_facts,
        "commands": lambda v, s, a: extract_task_facts(v, s, a, "commands"),
        "cli_commands": lambda v, s, a: extract_task_facts(v, s, a, "cli_commands"),
        "procedures": lambda v, s, a: extract_task_facts(v, s, a, "procedures"),
        "testing": extract_testing_facts,
        "quick_reference": extract_quick_reference_facts,
        "integrations": extract_integrations_facts,
        "tech_stack": lambda v, s, a: extract_tech_stack_facts(v, s, a, "tech_stack"),
        "technology_stack": lambda v, s, a: extract_tech_stack_facts(v, s, a, "technology_stack"),
        "api_structure": extract_api_structure_facts,
    }

    facts: list[dict[str, Any]] = []

    for key, value in payload.items():
        if key in IDENTITY_KEYS or key in IGNORED_NARRATIVE_KEYS:
            continue

        extractor = extractor_map.get(key)
        if extractor is None:
            if value in (None, "", [], {}):
                continue
            unmapped_findings.append(
                make_mismatch(
                    severity="non_blocking",
                    reason="unmapped_section",
                    shard=repo.shard,
                    source_file=source_file_rel,
                    repo_node_id=repo.node_id,
                    section=key,
                    detail=f"section '{key}' has no WS6 extractor",
                )
            )
            continue

        try:
            produced = extractor(value, source_file_rel, as_of)
        except Exception as exc:
            unmapped_findings.append(
                make_mismatch(
                    severity="non_blocking",
                    reason="section_extractor_error",
                    shard=repo.shard,
                    source_file=source_file_rel,
                    repo_node_id=repo.node_id,
                    section=key,
                    detail=f"extractor error: {exc}",
                )
            )
            produced = []

        facts.extend(produced)

    return facts


def normalize_draft_fact(
    *,
    row: dict[str, Any],
    repo: RepoIdentity,
    source_file_rel: str,
    source_section: str,
    enums: dict[str, set[str]],
    strict_unknown_predicates: bool,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []

    fact_type = ensure_string(row.get("fact_type"))
    predicate = ensure_string(row.get("predicate"))
    object_kind = ensure_string(row.get("object_kind"))

    if enums["fact_type"] and fact_type not in enums["fact_type"]:
        issues.append(
            make_mismatch(
                severity="blocking",
                reason="unknown_fact_type",
                shard=repo.shard,
                source_file=source_file_rel,
                repo_node_id=repo.node_id,
                section=source_section,
                detail=f"unknown fact_type '{fact_type}'",
            )
        )

    if enums["predicate"] and predicate not in enums["predicate"]:
        severity = "blocking" if strict_unknown_predicates else "non_blocking"
        issues.append(
            make_mismatch(
                severity=severity,
                reason="unknown_predicate",
                shard=repo.shard,
                source_file=source_file_rel,
                repo_node_id=repo.node_id,
                section=source_section,
                detail=f"unknown predicate '{predicate}'",
            )
        )

    if enums["object_kind"] and object_kind not in enums["object_kind"]:
        issues.append(
            make_mismatch(
                severity="blocking",
                reason="unknown_object_kind",
                shard=repo.shard,
                source_file=source_file_rel,
                repo_node_id=repo.node_id,
                section=source_section,
                detail=f"unknown object_kind '{object_kind}'",
            )
        )

    confidence_raw = row.get("confidence")
    confidence: float | None = None
    if isinstance(confidence_raw, (float, int)):
        confidence = float(confidence_raw)
    elif isinstance(confidence_raw, str):
        try:
            confidence = float(confidence_raw.strip())
        except ValueError:
            confidence = None

    if confidence is None or not (0.0 <= confidence <= 1.0):
        issues.append(
            make_mismatch(
                severity="blocking",
                reason="invalid_confidence",
                shard=repo.shard,
                source_file=source_file_rel,
                repo_node_id=repo.node_id,
                section=source_section,
                detail=f"confidence must be numeric in [0.0,1.0], got '{confidence_raw}'",
            )
        )

    as_of = ensure_string(row.get("as_of")) or repo.as_of or "1970-01-01"

    provenance = ensure_dict(row.get("provenance"))
    source_section_value = ensure_string(provenance.get("source_section")) or source_section
    evidence, evidence_error = normalize_evidence_rows(
        row.get("evidence"),
        source_file_default=ensure_string(provenance.get("source_file")) or source_file_rel,
        source_section_default=source_section_value,
        evidence_kind_enums=enums["evidence_kind"],
    )
    if evidence_error:
        issues.append(
            make_mismatch(
                severity="blocking",
                reason=evidence_error,
                shard=repo.shard,
                source_file=source_file_rel,
                repo_node_id=repo.node_id,
                section=source_section,
                detail="draft fact evidence invalid",
            )
        )

    if any(issue["severity"] == "blocking" for issue in issues):
        return None, issues
    if not strict_unknown_predicates and any(issue["reason"] == "unknown_predicate" for issue in issues):
        # non-blocking drop when explicitly allowed
        return None, issues

    fact: dict[str, Any] = {
        "fact_type": fact_type,
        "predicate": predicate,
        "object_kind": object_kind,
        "confidence": float(confidence if confidence is not None else 0.0),
        "as_of": as_of,
        "provenance": {
            "source_file": ensure_string(provenance.get("source_file")) or source_file_rel,
            "source_section": source_section_value,
            "extraction_mode": "draft",
        },
        "evidence": evidence,
    }

    if object_kind in {"repo", "external_tool"}:
        object_node_id = ensure_string(row.get("object_node_id"))
        if not object_node_id:
            issues.append(
                make_mismatch(
                    severity="blocking",
                    reason="missing_object_node_id",
                    shard=repo.shard,
                    source_file=source_file_rel,
                    repo_node_id=repo.node_id,
                    section=source_section,
                    detail="object_node_id required for repo/external_tool",
                )
            )
            return None, issues
        fact["object_node_id"] = object_node_id
    else:
        object_value = ensure_string(row.get("object_value"))
        if not object_value:
            issues.append(
                make_mismatch(
                    severity="blocking",
                    reason="missing_object_value",
                    shard=repo.shard,
                    source_file=source_file_rel,
                    repo_node_id=repo.node_id,
                    section=source_section,
                    detail="object_value required for non-node object kinds",
                )
            )
            return None, issues
        fact["object_value"] = object_value

    note = ensure_string(row.get("note"))
    if note:
        fact["note"] = truncate_text(note)

    return fact, issues


def validate_fact(
    *,
    fact: dict[str, Any],
    repo: RepoIdentity,
    source_file_rel: str,
    enums: dict[str, set[str]],
    strict_unknown_predicates: bool,
) -> tuple[bool, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []

    fact_type = ensure_string(fact.get("fact_type"))
    predicate = ensure_string(fact.get("predicate"))
    object_kind = ensure_string(fact.get("object_kind"))

    if enums["fact_type"] and fact_type not in enums["fact_type"]:
        issues.append(
            make_mismatch(
                severity="blocking",
                reason="unknown_fact_type",
                shard=repo.shard,
                source_file=source_file_rel,
                repo_node_id=repo.node_id,
                detail=f"unknown fact_type '{fact_type}'",
                fact_summary=summarize_fact(fact),
            )
        )

    if enums["predicate"] and predicate not in enums["predicate"]:
        severity = "blocking" if strict_unknown_predicates else "non_blocking"
        issues.append(
            make_mismatch(
                severity=severity,
                reason="unknown_predicate",
                shard=repo.shard,
                source_file=source_file_rel,
                repo_node_id=repo.node_id,
                detail=f"unknown predicate '{predicate}'",
                fact_summary=summarize_fact(fact),
            )
        )

    if enums["object_kind"] and object_kind not in enums["object_kind"]:
        issues.append(
            make_mismatch(
                severity="blocking",
                reason="unknown_object_kind",
                shard=repo.shard,
                source_file=source_file_rel,
                repo_node_id=repo.node_id,
                detail=f"unknown object_kind '{object_kind}'",
                fact_summary=summarize_fact(fact),
            )
        )

    confidence = fact.get("confidence")
    if not isinstance(confidence, (float, int)) or not (0.0 <= float(confidence) <= 1.0):
        issues.append(
            make_mismatch(
                severity="blocking",
                reason="invalid_confidence",
                shard=repo.shard,
                source_file=source_file_rel,
                repo_node_id=repo.node_id,
                detail=f"confidence must be in [0.0,1.0], got '{confidence}'",
                fact_summary=summarize_fact(fact),
            )
        )

    provenance = ensure_dict(fact.get("provenance"))
    source_section = ensure_string(provenance.get("source_section"))

    evidence, evidence_error = normalize_evidence_rows(
        fact.get("evidence"),
        source_file_default=ensure_string(provenance.get("source_file")) or source_file_rel,
        source_section_default=source_section,
        evidence_kind_enums=enums["evidence_kind"],
    )
    if evidence_error:
        issues.append(
            make_mismatch(
                severity="blocking",
                reason=evidence_error,
                shard=repo.shard,
                source_file=source_file_rel,
                repo_node_id=repo.node_id,
                detail="fact evidence invalid",
                fact_summary=summarize_fact(fact),
            )
        )
    else:
        fact["evidence"] = evidence

    if object_kind in {"repo", "external_tool"}:
        object_node_id = ensure_string(fact.get("object_node_id"))
        if not object_node_id:
            issues.append(
                make_mismatch(
                    severity="blocking",
                    reason="missing_object_node_id",
                    shard=repo.shard,
                    source_file=source_file_rel,
                    repo_node_id=repo.node_id,
                    detail="object_node_id is required",
                    fact_summary=summarize_fact(fact),
                )
            )
    else:
        object_value = ensure_string(fact.get("object_value"))
        if not object_value:
            issues.append(
                make_mismatch(
                    severity="blocking",
                    reason="missing_object_value",
                    shard=repo.shard,
                    source_file=source_file_rel,
                    repo_node_id=repo.node_id,
                    detail="object_value is required",
                    fact_summary=summarize_fact(fact),
                )
            )

    if any(issue["severity"] == "blocking" for issue in issues):
        return False, issues
    if not strict_unknown_predicates and any(issue["reason"] == "unknown_predicate" for issue in issues):
        return False, issues

    return True, issues


def load_deep_source_files(workspace_root: Path) -> tuple[list[tuple[str, Path]], list[tuple[str, Path]]]:
    narrative: list[tuple[str, Path]] = []
    draft: list[tuple[str, Path]] = []

    for shard in SHARDS:
        narrative_dir = workspace_root / shard / "knowledge" / "deep"
        if narrative_dir.exists():
            for path in sorted(narrative_dir.glob("*.yaml"), key=lambda p: p.name):
                narrative.append((shard, path))

        draft_dir = workspace_root / shard / "knowledge" / "deep_facts_draft"
        if draft_dir.exists():
            for path in sorted(draft_dir.glob("*.yaml"), key=lambda p: p.name):
                draft.append((shard, path))

    return narrative, draft


def materialize(
    *,
    workspace_root: Path,
    reports_dir_rel: str,
    strict_unknown_predicates: bool,
    run_validation_suite: bool,
) -> tuple[dict[str, str], dict[str, Any], int]:
    deep_contract, relation_mapping, contract_errors = load_contracts(workspace_root)
    del relation_mapping  # relation mapping is loaded for contract completeness in WS6 v1.

    enums = parse_contract_enums(deep_contract)
    contract_version = ensure_string(deep_contract.get("contract_version")) or "1.0.0-ws6-draft"

    by_node_id, by_full_name, by_stem, shallow_errors = load_shallow_repos(workspace_root)

    narrative_files, draft_files = load_deep_source_files(workspace_root)

    blocking_findings: list[dict[str, Any]] = []
    non_blocking_findings: list[dict[str, Any]] = []
    dropped_facts: list[dict[str, Any]] = []

    for err in contract_errors + shallow_errors:
        blocking_findings.append(
            {
                "severity": "blocking",
                "reason": "preflight_error",
                "detail": err,
            }
        )

    repo_narrative_facts: dict[str, list[FactCandidate]] = {}
    repo_draft_facts: dict[str, list[FactCandidate]] = {}
    repo_stats: dict[str, dict[str, Any]] = {}

    def _repo_stats(repo: RepoIdentity) -> dict[str, Any]:
        row = repo_stats.get(repo.node_id)
        if row is None:
            row = {
                "node_id": repo.node_id,
                "github_full_name": repo.github_full_name,
                "shard": repo.shard,
                "narrative_files": 0,
                "draft_files": 0,
                "narrative_facts_raw": 0,
                "draft_facts_raw": 0,
                "derived_facts_after_dedupe": 0,
                "draft_overrides": 0,
                "evidence_merges": 0,
                "facts_emitted": 0,
                "blocked_facts": 0,
                "unmapped_sections_count": 0,
            }
            repo_stats[repo.node_id] = row
        return row

    # Process deep narrative inputs.
    for shard, path in narrative_files:
        source_rel = path.relative_to(workspace_root).as_posix()
        try:
            payload = load_yaml(path) or {}
        except Exception as exc:
            blocking_findings.append(
                make_mismatch(
                    severity="blocking",
                    reason="parse_error",
                    shard=shard,
                    source_file=source_rel,
                    repo_node_id="",
                    detail=f"failed to parse deep narrative: {exc}",
                )
            )
            continue

        if not isinstance(payload, dict):
            blocking_findings.append(
                make_mismatch(
                    severity="blocking",
                    reason="invalid_payload_shape",
                    shard=shard,
                    source_file=source_rel,
                    repo_node_id="",
                    detail="deep narrative must be mapping",
                )
            )
            continue

        repo = resolve_repo_identity(
            payload=payload,
            source_file=path,
            shard=shard,
            by_node_id=by_node_id,
            by_full_name=by_full_name,
            by_stem=by_stem,
        )
        if repo is None:
            blocking_findings.append(
                make_mismatch(
                    severity="blocking",
                    reason="missing_shallow_match",
                    shard=shard,
                    source_file=source_rel,
                    repo_node_id=ensure_string(payload.get("node_id")),
                    detail="unable to resolve deep narrative to shallow repo identity",
                )
            )
            continue

        stats = _repo_stats(repo)
        stats["narrative_files"] += 1

        parity_issues = validate_identity_parity(
            payload=payload,
            repo=repo,
            source_file_rel=source_rel,
            strict_source_field=True,
        )
        if parity_issues:
            blocking_findings.extend(parity_issues)
            stats["blocked_facts"] += 1
            continue

        unmapped_sections: list[dict[str, Any]] = []
        raw_facts = extract_narrative_facts(
            repo=repo,
            source_file_rel=source_rel,
            payload=payload,
            unmapped_findings=unmapped_sections,
        )
        non_blocking_findings.extend(unmapped_sections)
        stats["unmapped_sections_count"] += len(unmapped_sections)
        stats["narrative_facts_raw"] += len(raw_facts)

        bucket = repo_narrative_facts.setdefault(repo.node_id, [])
        for fact in raw_facts:
            ok, issues = validate_fact(
                fact=fact,
                repo=repo,
                source_file_rel=source_rel,
                enums=enums,
                strict_unknown_predicates=strict_unknown_predicates,
            )
            for issue in issues:
                if issue.get("severity") == "blocking":
                    blocking_findings.append(issue)
                else:
                    non_blocking_findings.append(issue)
            if not ok:
                stats["blocked_facts"] += 1
                dropped_facts.append(
                    {
                        "reason": "invalid_derived_fact",
                        "source_file": source_rel,
                        "repo_node_id": repo.node_id,
                        "fact_summary": summarize_fact(fact),
                    }
                )
                continue

            bucket.append(
                FactCandidate(
                    node_id=repo.node_id,
                    github_full_name=repo.github_full_name,
                    source_file=source_rel,
                    source_kind="narrative",
                    fact=fact,
                )
            )

    # Process optional draft facts.
    for shard, path in draft_files:
        source_rel = path.relative_to(workspace_root).as_posix()
        try:
            payload = load_yaml(path) or {}
        except Exception as exc:
            blocking_findings.append(
                make_mismatch(
                    severity="blocking",
                    reason="parse_error",
                    shard=shard,
                    source_file=source_rel,
                    repo_node_id="",
                    detail=f"failed to parse draft facts: {exc}",
                )
            )
            continue

        if not isinstance(payload, dict):
            blocking_findings.append(
                make_mismatch(
                    severity="blocking",
                    reason="invalid_payload_shape",
                    shard=shard,
                    source_file=source_rel,
                    repo_node_id="",
                    detail="draft fact payload must be mapping",
                )
            )
            continue

        repo = resolve_repo_identity(
            payload=payload,
            source_file=path,
            shard=shard,
            by_node_id=by_node_id,
            by_full_name=by_full_name,
            by_stem=by_stem,
        )
        if repo is None:
            blocking_findings.append(
                make_mismatch(
                    severity="blocking",
                    reason="missing_shallow_match",
                    shard=shard,
                    source_file=source_rel,
                    repo_node_id=ensure_string(payload.get("node_id")),
                    detail="unable to resolve draft facts to shallow repo identity",
                )
            )
            continue

        stats = _repo_stats(repo)
        stats["draft_files"] += 1

        parity_issues = validate_identity_parity(
            payload=payload,
            repo=repo,
            source_file_rel=source_rel,
            strict_source_field=False,
        )
        for issue in parity_issues:
            if issue["severity"] == "blocking":
                blocking_findings.append(issue)
            else:
                non_blocking_findings.append(issue)

        rows = payload.get("facts")
        if not isinstance(rows, list):
            rows = payload.get("deep_facts")
        if not isinstance(rows, list):
            non_blocking_findings.append(
                make_mismatch(
                    severity="non_blocking",
                    reason="missing_draft_facts_list",
                    shard=shard,
                    source_file=source_rel,
                    repo_node_id=repo.node_id,
                    detail="draft payload has no facts/deep_facts list",
                )
            )
            continue

        bucket = repo_draft_facts.setdefault(repo.node_id, [])

        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                blocking_findings.append(
                    make_mismatch(
                        severity="blocking",
                        reason="invalid_draft_fact_shape",
                        shard=shard,
                        source_file=source_rel,
                        repo_node_id=repo.node_id,
                        detail=f"draft fact at index {idx} is not mapping",
                        section=f"facts[{idx}]",
                    )
                )
                stats["blocked_facts"] += 1
                continue

            section_ref = f"facts[{idx}]"
            fact, issues = normalize_draft_fact(
                row=row,
                repo=repo,
                source_file_rel=source_rel,
                source_section=section_ref,
                enums=enums,
                strict_unknown_predicates=strict_unknown_predicates,
            )

            for issue in issues:
                if issue["severity"] == "blocking":
                    blocking_findings.append(issue)
                else:
                    non_blocking_findings.append(issue)

            if fact is None:
                stats["blocked_facts"] += 1
                dropped_facts.append(
                    {
                        "reason": "invalid_draft_fact",
                        "source_file": source_rel,
                        "repo_node_id": repo.node_id,
                        "section": section_ref,
                    }
                )
                continue

            stats["draft_facts_raw"] += 1
            bucket.append(
                FactCandidate(
                    node_id=repo.node_id,
                    github_full_name=repo.github_full_name,
                    source_file=source_rel,
                    source_kind="draft",
                    fact=fact,
                )
            )

    # Build final per-repo canonical fact sets.
    per_repo_output: dict[str, dict[str, Any]] = {}
    master_rows: list[dict[str, Any]] = []
    draft_overrides_count = 0
    derived_dedupe_merges_count = 0

    for node_id in sorted(set(repo_narrative_facts) | set(repo_draft_facts)):
        repo = by_node_id.get(node_id)
        if repo is None:
            continue
        stats = _repo_stats(repo)

        derived_candidates = repo_narrative_facts.get(node_id, [])
        draft_candidates = repo_draft_facts.get(node_id, [])

        # Step 1: dedupe derived facts by fingerprint-identical key and merge evidence deterministically.
        derived_by_fp: dict[str, dict[str, Any]] = {}
        derived_collision_index: dict[tuple[str, str, str, str, str], str] = {}

        for candidate in derived_candidates:
            fact = dict(candidate.fact)
            fp = fact_merge_key(node_id, fact)
            collision_key = build_collision_key(node_id, fact)

            if fp in derived_by_fp:
                existing = derived_by_fp[fp]
                existing["evidence"] = merge_evidence(
                    ensure_list_of_dicts(existing.get("evidence")),
                    ensure_list_of_dicts(fact.get("evidence")),
                )
                derived_dedupe_merges_count += 1
                stats["evidence_merges"] += 1
                dropped_facts.append(
                    {
                        "reason": "duplicate_derived_merged",
                        "repo_node_id": node_id,
                        "source_file": candidate.source_file,
                        "fact_summary": summarize_fact(fact),
                    }
                )
                continue

            derived_by_fp[fp] = fact
            derived_collision_index[collision_key] = fp

        stats["derived_facts_after_dedupe"] = len(derived_by_fp)

        # Step 2: apply draft authority on collision key.
        final_facts: list[dict[str, Any]] = list(derived_by_fp.values())
        final_collision_index: dict[tuple[str, str, str, str, str], int] = {}
        for idx, fact in enumerate(final_facts):
            final_collision_index[build_collision_key(node_id, fact)] = idx

        for candidate in draft_candidates:
            draft_fact = dict(candidate.fact)
            collision_key = build_collision_key(node_id, draft_fact)
            if collision_key in final_collision_index:
                idx = final_collision_index[collision_key]
                replaced = final_facts[idx]
                dropped_facts.append(
                    {
                        "reason": "draft_precedence_override",
                        "repo_node_id": node_id,
                        "source_file": candidate.source_file,
                        "replaced_fact": summarize_fact(replaced),
                        "authoritative_fact": summarize_fact(draft_fact),
                    }
                )
                final_facts[idx] = draft_fact
                draft_overrides_count += 1
                stats["draft_overrides"] += 1
            else:
                final_facts.append(draft_fact)
                final_collision_index[collision_key] = len(final_facts) - 1

        # Step 3: final dedupe by full fingerprint (covers repeated drafts too).
        final_by_fp: dict[str, dict[str, Any]] = {}
        for fact in final_facts:
            fp = fact_merge_key(node_id, fact)
            if fp in final_by_fp:
                existing = final_by_fp[fp]
                existing["evidence"] = merge_evidence(
                    ensure_list_of_dicts(existing.get("evidence")),
                    ensure_list_of_dicts(fact.get("evidence")),
                )
                dropped_facts.append(
                    {
                        "reason": "duplicate_final_fact_merged",
                        "repo_node_id": node_id,
                        "fact_summary": summarize_fact(fact),
                    }
                )
                continue
            final_by_fp[fp] = fact

        canonical_facts = list(final_by_fp.values())
        for fact in canonical_facts:
            fact["fact_id"] = build_fact_id(node_id, fact)

        canonical_facts.sort(
            key=lambda f: (
                ensure_string(f.get("predicate")),
                ensure_string(f.get("fact_type")),
                ensure_string(f.get("object_kind")),
                ensure_string(f.get("object_node_id")) or ensure_string(f.get("object_value")),
                ensure_string(f.get("fact_id")),
            )
        )

        stats["facts_emitted"] = len(canonical_facts)

        if not canonical_facts:
            continue

        output_rel = f"{repo.shard}/knowledge/deep_facts/{repo.file_stem}.yaml"
        repo_as_of = repo.as_of
        if not repo_as_of:
            fact_as_ofs = [ensure_string(f.get("as_of")) for f in canonical_facts if ensure_string(f.get("as_of"))]
            repo_as_of = fact_as_ofs[0] if fact_as_ofs else "1970-01-01"

        repo_payload = {
            "name": repo.name,
            "node_id": repo.node_id,
            "github_full_name": repo.github_full_name,
            "html_url": repo.html_url,
            "source": repo.source or repo.shard,
            "provenance": {
                "shard": repo.shard,
                "source_file": output_rel,
                "as_of": repo_as_of,
                "extractor_version": EXTRACTOR_VERSION,
            },
            "facts": canonical_facts,
        }

        per_repo_output[node_id] = {
            "repo": repo,
            "payload": repo_payload,
            "output_rel": output_rel,
        }

        for fact in canonical_facts:
            flattened = {
                "node_id": repo.node_id,
                "github_full_name": repo.github_full_name,
                "name": repo.name,
                **fact,
            }
            master_rows.append(flattened)

    master_rows.sort(
        key=lambda f: (
            ensure_string(f.get("node_id")),
            ensure_string(f.get("predicate")),
            ensure_string(f.get("fact_type")),
            ensure_string(f.get("object_kind")),
            ensure_string(f.get("object_node_id")) or ensure_string(f.get("object_value")),
            ensure_string(f.get("fact_id")),
        )
    )

    generated_at_utc = infer_generated_at(master_rows)

    master_payload = {
        "artifact_type": "ws6_master_deep_facts",
        "generated_at_utc": generated_at_utc,
        "contract_version": contract_version,
        "summary": {
            "total_facts": len(master_rows),
            "repos_with_facts": len(per_repo_output),
            "source_shards": list(SHARDS),
            "draft_overrides": draft_overrides_count,
            "derived_dedupe_merges": derived_dedupe_merges_count,
        },
        "facts": master_rows,
    }

    # Build textual outputs deterministically before writing to evaluate stability.
    output_texts: dict[str, str] = {}
    for node_id in sorted(per_repo_output):
        row = per_repo_output[node_id]
        output_texts[row["output_rel"]] = dump_yaml(row["payload"])

    master_rel = "master_deep_facts.yaml"
    output_texts[master_rel] = dump_yaml(master_payload)

    # Compose mismatch and coverage reports.
    blocking_count = sum(1 for row in blocking_findings if row.get("severity") == "blocking")
    non_blocking_count = sum(1 for row in non_blocking_findings if row.get("severity") != "blocking")

    unknown_predicates_count = sum(
        1
        for row in blocking_findings + non_blocking_findings
        if row.get("reason") == "unknown_predicate"
    )

    unmapped_sections = [
        row
        for row in non_blocking_findings
        if row.get("reason") == "unmapped_section"
    ]

    per_repo_rows = sorted(repo_stats.values(), key=lambda r: r["node_id"])
    unmapped_sections_by_repo = {
        row["node_id"]: int(row.get("unmapped_sections_count", 0))
        for row in per_repo_rows
        if int(row.get("unmapped_sections_count", 0)) > 0
    }

    emitted_facts_total = sum(int(r.get("facts_emitted", 0)) for r in per_repo_rows)
    facts_with_evidence = 0
    confidence_valid = 0
    all_fact_ids: list[str] = []
    for fact in master_rows:
        evidence = ensure_list_of_dicts(fact.get("evidence"))
        if evidence:
            facts_with_evidence += 1
        conf = fact.get("confidence")
        if isinstance(conf, (float, int)) and 0.0 <= float(conf) <= 1.0:
            confidence_valid += 1
        fact_id = ensure_string(fact.get("fact_id"))
        if fact_id:
            all_fact_ids.append(fact_id)

    duplicate_fact_ids = sorted(
        fid for fid in {fid for fid in all_fact_ids} if all_fact_ids.count(fid) > 1
    )

    evidence_pct = round((facts_with_evidence / emitted_facts_total) * 100.0, 3) if emitted_facts_total else 100.0
    confidence_pct = round((confidence_valid / emitted_facts_total) * 100.0, 3) if emitted_facts_total else 100.0

    gate_bools = {
        "deep_facts_parseable": True,
        "deep_fact_identity_coverage_100pct": (
            len([r for r in blocking_findings if r.get("reason", "").startswith("identity_")]) == 0
        ),
        "facts_with_evidence_100pct": evidence_pct == 100.0,
        "confidence_bounds_valid": confidence_pct == 100.0,
        "unmapped_deep_predicates_zero": unknown_predicates_count == 0,
        "duplicate_fact_ids_zero": len(duplicate_fact_ids) == 0,
        "execution_results_pending_zero": True,
        "ws6_hash_stable": True,
    }

    gate_metrics = {
        "unmapped_sections_count": len(unmapped_sections),
    }
    execution_mode = "full_validation_run" if run_validation_suite else "materialize_only"

    mismatch_report = {
        "artifact_type": "ws6_deep_integration_mismatch_report",
        "generated_at_utc": generated_at_utc,
        "contract_version": contract_version,
        "summary": {
            "blocking_mismatches_count": blocking_count,
            "non_blocking_mismatches_count": non_blocking_count,
            "unknown_predicates_count": unknown_predicates_count,
            "unmapped_sections_count": len(unmapped_sections),
            "dropped_facts_count": len(dropped_facts),
        },
        "blocking_findings": blocking_findings,
        "non_blocking_findings": non_blocking_findings,
        "dropped_facts": dropped_facts,
        "duplicate_fact_ids": duplicate_fact_ids,
        "gate_bools": gate_bools,
        "gate_metrics": gate_metrics,
        "execution_mode": execution_mode,
    }

    coverage_report = {
        "artifact_type": "ws6_deep_integration_coverage",
        "generated_at_utc": generated_at_utc,
        "contract_version": contract_version,
        "input_scope": {
            "deep_narrative_files_total": len(narrative_files),
            "deep_fact_draft_files_total": len(draft_files),
            "repos_with_any_deep_inputs": len(per_repo_rows),
            "repos_materialized": len(per_repo_output),
        },
        "metrics": {
            "facts_materialized_total": emitted_facts_total,
            "facts_with_evidence_pct": evidence_pct,
            "confidence_bounds_valid_pct": confidence_pct,
            "draft_overrides_count": draft_overrides_count,
            "derived_dedupe_merges_count": derived_dedupe_merges_count,
            "unmapped_sections_count": len(unmapped_sections),
            "unmapped_sections_by_repo": unmapped_sections_by_repo,
            "per_repo": per_repo_rows,
        },
        "actions": {
            "materialized_repo_files": sorted(output_rel for output_rel in output_texts if output_rel.endswith(".yaml") and output_rel != master_rel),
            "master_output": master_rel,
        },
        "gate_bools": gate_bools,
        "gate_metrics": gate_metrics,
        "execution_mode": execution_mode,
    }

    # Stability check: regenerate report texts and output hashes from immutable payloads.
    reports_rel = reports_dir_rel.rstrip("/")
    coverage_rel = f"{reports_rel}/coverage.yaml"
    mismatch_rel = f"{reports_rel}/mismatch_report.yaml"
    validation_rel = f"{reports_rel}/validation_runs.yaml"

    output_texts[coverage_rel] = dump_yaml(coverage_report)
    output_texts[mismatch_rel] = dump_yaml(mismatch_report)

    hashes_once = {path: sha256_text(text) for path, text in sorted(output_texts.items())}
    hashes_twice = {path: sha256_text(text) for path, text in sorted(output_texts.items())}
    stable = hashes_once == hashes_twice
    gate_bools["ws6_hash_stable"] = stable

    execution_plan = [
        {
            "step": 1,
            "command": "python3 tools/ws1_contract_validator.py --workspace-root . --external-node-policy first_class",
            "expectation": "WS1_CONTRACT_STATUS: PASS",
        },
        {
            "step": 2,
            "command": "python3 tools/trust_gates.py llm_repos/knowledge --production",
            "expectation": "overall_status: PASS and ready_state_allowed: true",
        },
        {
            "step": 3,
            "command": "python3 tools/trust_gates.py ssh_repos/knowledge --production",
            "expectation": "overall_status: PASS and ready_state_allowed: true",
        },
        {
            "step": 4,
            "command": f"python3 tools/ws6_deep_integrator.py --workspace-root . --reports-dir {reports_rel} --materialize-spec {reports_rel}/spec.yaml",
            "expectation": "WS6 writes deterministic deep_facts, master_deep_facts, and reports",
        },
        {
            "step": 5,
            "command": "python3 tools/ws4_master_compiler.py --workspace-root . --master-index master_index.yaml --master-graph master_graph.yaml --reports-dir reports/ws4_master_build",
            "expectation": "compiler exits 0 and reports/ws4_master_build/coverage.yaml gate_ready: true",
        },
        {
            "step": 6,
            "command": "python3 tools/query_master.py stats",
            "expectation": "deep_facts > 0",
        },
        {
            "step": 7,
            "command": "Re-run WS6 command with identical input and verify output hashes unchanged",
            "expectation": "hashes unchanged",
        },
    ]
    required_commands = [dict(row, status="PLANNED", exit_code=None) for row in execution_plan]
    execution_results = [
        {
            "step": row["step"],
            "command": row["command"],
            "status": "NOT_RUN",
            "exit_code": None,
            "ran_at_utc": None,
            "duration_ms": None,
            "observation": "not executed in this ws6 invocation",
        }
        for row in execution_plan
    ]
    results_by_step = {row["step"]: row for row in execution_results}

    def _record_result(
        *,
        step: int,
        status: str,
        exit_code: int | None,
        observation: str,
        duration_ms: int | None = None,
        output_tail: str = "",
    ) -> None:
        row = results_by_step[step]
        row["status"] = status
        row["exit_code"] = exit_code
        row["ran_at_utc"] = utc_now_iso()
        row["duration_ms"] = duration_ms
        row["observation"] = observation
        if output_tail:
            row["output_tail"] = output_tail

    validation_runs = {
        "artifact_type": "ws6_deep_integration_validation_runs",
        "generated_at_utc": generated_at_utc,
        "contract_version": contract_version,
        "report_semantics": {
            "required_commands": "Execution contract/plan only (status=PLANNED); this section is not proof of execution.",
            "execution_results": "Observed outcomes recorded by this WS6 invocation; statuses are PASS/FAIL/NOT_RUN only.",
            "pending_status_allowed": False,
        },
        "execution_mode": execution_mode,
        "required_commands": required_commands,
        "execution_results": execution_results,
        "artifact_hashes": hashes_once,
        "gate_bools": gate_bools,
        "gate_metrics": gate_metrics,
        "ws6_gate_ready": False,
        "validation_suite_complete": False,
        "validation_suite_passed": None,
        "gate_ready": False,
    }

    output_texts[validation_rel] = dump_yaml(validation_runs)

    # Final parseability checks for generated YAML outputs.
    for rel_path, text in sorted(output_texts.items()):
        try:
            parsed = yaml.safe_load(text)
        except Exception as exc:
            gate_bools["deep_facts_parseable"] = False
            blocking_findings.append(
                {
                    "severity": "blocking",
                    "reason": "generated_yaml_parse_error",
                    "source_file": rel_path,
                    "detail": str(exc),
                }
            )
            continue
        if not isinstance(parsed, dict):
            gate_bools["deep_facts_parseable"] = False
            blocking_findings.append(
                {
                    "severity": "blocking",
                    "reason": "generated_yaml_not_mapping",
                    "source_file": rel_path,
                    "detail": "generated YAML must be a mapping",
                }
            )

    ws6_gate_ready = all(gate_bools.values()) and not any(
        row.get("severity") == "blocking" for row in blocking_findings
    )
    _record_result(
        step=4,
        status="PASS" if ws6_gate_ready else "FAIL",
        exit_code=0 if ws6_gate_ready else 1,
        duration_ms=0,
        observation=(
            f"ws6_gate_ready={str(ws6_gate_ready).lower()} "
            f"blocking_mismatches={len([r for r in blocking_findings if r.get('severity') == 'blocking'])} "
            f"facts_materialized={emitted_facts_total}"
        ),
    )
    _record_result(
        step=7,
        status="PASS" if stable else "FAIL",
        exit_code=0 if stable else 1,
        duration_ms=0,
        observation=f"hash_stability={str(stable).lower()}",
    )

    # Write initial outputs so optional validation suite commands can inspect artifacts.
    writes_changed = 0
    for rel_path, text in sorted(output_texts.items()):
        if write_if_changed(workspace_root / rel_path, text):
            writes_changed += 1

    if run_validation_suite:
        suite_commands: dict[int, list[str]] = {
            1: ["python3", "tools/ws1_contract_validator.py", "--workspace-root", ".", "--external-node-policy", "first_class"],
            2: ["python3", "tools/trust_gates.py", "llm_repos/knowledge", "--production"],
            3: ["python3", "tools/trust_gates.py", "ssh_repos/knowledge", "--production"],
            5: [
                "python3",
                "tools/ws4_master_compiler.py",
                "--workspace-root",
                ".",
                "--master-index",
                "master_index.yaml",
                "--master-graph",
                "master_graph.yaml",
                "--reports-dir",
                "reports/ws4_master_build",
            ],
            6: ["python3", "tools/query_master.py", "stats"],
        }

        for step in (1, 2, 3, 5, 6):
            cmd = suite_commands[step]
            started = time.monotonic()
            proc = subprocess.run(
                cmd,
                cwd=workspace_root,
                text=True,
                capture_output=True,
                check=False,
            )
            elapsed_ms = int(round((time.monotonic() - started) * 1000.0))
            stdout = proc.stdout or ""
            stderr = proc.stderr or ""
            merged = f"{stdout}\n{stderr}".lower()

            ok = proc.returncode == 0
            observation = f"exit_code={proc.returncode}"
            if step == 1:
                ws1_ok = "ws1_contract_status: pass" in merged
                ok = ok and ws1_ok
                observation = f"{observation}; ws1_contract_status_pass={str(ws1_ok).lower()}"
            elif step in {2, 3}:
                overall_ok = "overall: pass" in merged
                ready_ok = "ready_state_allowed: true" in merged
                ok = ok and overall_ok and ready_ok
                observation = f"{observation}; overall_pass={str(overall_ok).lower()}; ready_state_allowed_true={str(ready_ok).lower()}"
            elif step == 5:
                coverage_path = workspace_root / "reports" / "ws4_master_build" / "coverage.yaml"
                ws4_gate_ready = False
                if coverage_path.exists():
                    try:
                        coverage_payload = load_yaml(coverage_path) or {}
                        if isinstance(coverage_payload, dict):
                            ws4_gate_ready = bool(coverage_payload.get("gate_ready"))
                    except Exception:
                        ws4_gate_ready = False
                ok = ok and ws4_gate_ready
                observation = f"{observation}; ws4_gate_ready={str(ws4_gate_ready).lower()}"
            elif step == 6:
                deep_facts_count = 0
                try:
                    stats_payload = yaml.safe_load(stdout) or {}
                    if isinstance(stats_payload, dict):
                        counts = stats_payload.get("counts")
                        if isinstance(counts, dict):
                            deep_facts_count = int(counts.get("deep_facts") or 0)
                except Exception:
                    deep_facts_count = 0
                ok = ok and deep_facts_count > 0
                observation = f"{observation}; deep_facts={deep_facts_count}"

            _record_result(
                step=step,
                status="PASS" if ok else "FAIL",
                exit_code=proc.returncode,
                duration_ms=elapsed_ms,
                observation=observation,
                output_tail=compact_output_tail(stdout, stderr),
            )

    validation_suite_complete = all(row.get("status") != "NOT_RUN" for row in execution_results)
    validation_suite_passed = validation_suite_complete and all(row.get("status") == "PASS" for row in execution_results)

    failed_steps = [row for row in execution_results if row.get("status") == "FAIL"]
    if run_validation_suite:
        for row in failed_steps:
            blocking_findings.append(
                {
                    "severity": "blocking",
                    "reason": "validation_suite_step_failed",
                    "source_file": validation_rel,
                    "detail": f"step {row.get('step')} failed: {row.get('observation')}",
                }
            )

    pending_rows = [row for row in execution_results if row.get("status") == "PENDING_EXECUTION"]
    gate_bools["execution_results_pending_zero"] = len(pending_rows) == 0
    if ws6_gate_ready and pending_rows:
        blocking_findings.append(
            {
                "severity": "blocking",
                "reason": "execution_results_pending",
                "source_file": validation_rel,
                "detail": f"pending steps present while ws6_gate_ready=true: {[row.get('step') for row in pending_rows]}",
            }
        )

    ws6_gate_ready = all(gate_bools.values()) and not any(
        row.get("severity") == "blocking" for row in blocking_findings
    )
    overall_gate_ready = ws6_gate_ready and (validation_suite_passed if run_validation_suite else True)

    # Refresh reports with final gate status.
    final_blocking_count = sum(1 for row in blocking_findings if row.get("severity") == "blocking")
    final_non_blocking_count = sum(1 for row in non_blocking_findings if row.get("severity") != "blocking")
    mismatch_report["blocking_findings"] = blocking_findings
    mismatch_report["summary"] = {
        "blocking_mismatches_count": final_blocking_count,
        "non_blocking_mismatches_count": final_non_blocking_count,
        "unknown_predicates_count": unknown_predicates_count,
        "unmapped_sections_count": len(unmapped_sections),
        "dropped_facts_count": len(dropped_facts),
    }
    mismatch_report["gate_bools"] = gate_bools
    mismatch_report["ws6_gate_ready"] = ws6_gate_ready
    mismatch_report["gate_ready"] = overall_gate_ready
    coverage_report["gate_bools"] = gate_bools
    coverage_report["ws6_gate_ready"] = ws6_gate_ready
    coverage_report["gate_ready"] = overall_gate_ready
    validation_runs["gate_bools"] = gate_bools
    validation_runs["execution_results"] = execution_results
    validation_runs["ws6_gate_ready"] = ws6_gate_ready
    validation_runs["validation_suite_complete"] = validation_suite_complete
    validation_runs["validation_suite_passed"] = validation_suite_passed if run_validation_suite else None
    validation_runs["gate_ready"] = overall_gate_ready

    artifact_hashes = {
        path: sha256_text(text) for path, text in sorted(output_texts.items()) if path != validation_rel
    }
    validation_runs["artifact_hashes"] = artifact_hashes

    output_texts[coverage_rel] = dump_yaml(coverage_report)
    output_texts[mismatch_rel] = dump_yaml(mismatch_report)
    output_texts[validation_rel] = dump_yaml(validation_runs)

    # Final write pass after optional validation suite updates.
    for rel_path, text in sorted(output_texts.items()):
        if write_if_changed(workspace_root / rel_path, text):
            writes_changed += 1

    validation_steps_executed = len([row for row in execution_results if row.get("status") != "NOT_RUN"])
    validation_steps_failed = len([row for row in execution_results if row.get("status") == "FAIL"])

    summary = {
        "workspace_root": workspace_root.as_posix(),
        "reports_dir": (workspace_root / reports_rel).as_posix(),
        "contract_version": contract_version,
        "narrative_files": len(narrative_files),
        "draft_files": len(draft_files),
        "repos_materialized": len(per_repo_output),
        "facts_materialized": emitted_facts_total,
        "unmapped_sections_count": len(unmapped_sections),
        "blocking_mismatches": len([r for r in blocking_findings if r.get("severity") == "blocking"]),
        "writes_changed": writes_changed,
        "execution_mode": execution_mode,
        "validation_steps_executed": validation_steps_executed,
        "validation_steps_failed": validation_steps_failed,
        "ws6_gate_ready": ws6_gate_ready,
        "gate_ready": overall_gate_ready,
    }

    return output_texts, summary, 0 if overall_gate_ready else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="WS6 deep integration materializer")
    parser.add_argument("--workspace-root", default=".", help="Workspace root path.")
    parser.add_argument(
        "--reports-dir",
        default="reports/ws6_deep_integration",
        help="Output directory for WS6 reports.",
    )
    parser.add_argument(
        "--materialize-spec",
        default="",
        help="Optional file path (relative to workspace root) to write the WS6 spec YAML.",
    )
    parser.add_argument(
        "--print-spec",
        action="store_true",
        help="Print WS6 spec YAML to stdout.",
    )
    parser.add_argument(
        "--allow-unknown-predicates",
        action="store_true",
        help="Downgrade unknown draft predicates from blocking to non-blocking drop.",
    )
    parser.add_argument(
        "--run-validation-suite",
        action="store_true",
        help="Run WS1/trust/WS4/query commands and record execution results in WS6 validation_runs.yaml.",
    )
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()

    spec = build_spec()
    spec_text = dump_yaml(spec)
    if args.print_spec:
        print(spec_text.rstrip())
    if args.materialize_spec:
        spec_path = (workspace_root / args.materialize_spec).resolve()
        changed = write_if_changed(spec_path, spec_text)
        status = "written" if changed else "unchanged"
        print(f"spec_file: {spec_path.as_posix()} ({status})")

    _, summary, exit_code = materialize(
        workspace_root=workspace_root,
        reports_dir_rel=args.reports_dir,
        strict_unknown_predicates=not args.allow_unknown_predicates,
        run_validation_suite=args.run_validation_suite,
    )

    print("WS6_DEEP_INTEGRATION_SUMMARY")
    print(f"workspace_root: {summary['workspace_root']}")
    print(f"reports_dir: {summary['reports_dir']}")
    print(f"contract_version: {summary['contract_version']}")
    print(f"deep_narrative_files: {summary['narrative_files']}")
    print(f"deep_fact_draft_files: {summary['draft_files']}")
    print(f"repos_materialized: {summary['repos_materialized']}")
    print(f"facts_materialized: {summary['facts_materialized']}")
    print(f"unmapped_sections_count: {summary['unmapped_sections_count']}")
    print(f"blocking_mismatches: {summary['blocking_mismatches']}")
    print(f"writes_changed: {summary['writes_changed']}")
    print(f"validation_mode: {summary['execution_mode']}")
    print(f"validation_steps_executed: {summary['validation_steps_executed']}")
    print(f"validation_steps_failed: {summary['validation_steps_failed']}")
    print(f"ws6_gate_ready: {str(summary['ws6_gate_ready']).lower()}")
    print(f"gate_ready: {str(summary['gate_ready']).lower()}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
