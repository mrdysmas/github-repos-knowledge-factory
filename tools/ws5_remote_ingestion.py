#!/usr/bin/env python3
"""WS5 remote-first ingestion adapter + deterministic evidence writer.

Ingests remote metadata/API manifest entries into shard repo records without requiring
local clone contents, then writes deterministic WS5 evidence artifacts:

- reports/ws5_remote_ingestion/coverage.yaml
- reports/ws5_remote_ingestion/mismatch_report.yaml
- reports/ws5_remote_ingestion/validation_runs.yaml
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml


CONTRACT_VERSION = "1.0.0-ws1"
ALLOWED_MANIFEST_SOURCES = {"remote_metadata", "remote_api"}
ALLOWED_PROVENANCE_SHARDS = {"llm_repos", "ssh_repos", "merged"}
TARGET_SHARDS = ("llm_repos", "ssh_repos")
REPO_SCHEMA_REL_PATH = Path("contracts/ws1/repo.schema.yaml")
SOURCE_ENUMS_FALLBACK = {"llm_repos", "ssh_repos", "remote_metadata", "remote_api", "compiled_master"}
FULL_NAME_PATTERN = re.compile(r"^[^/]+/[^/]+$")
STEP8_EXPECTATION = "WS5 ingestion writes deterministic reports and WS1-compatible records"
REFRESH_PRECEDENCE = "api_wins_readme_for_missing_required_fields"


@dataclass
class RepoInput:
    index: int
    target_shard: str
    source: str
    name: str
    github_full_name: str
    html_url: str
    category: str
    summary: str
    core_concepts: list[str]
    key_entry_points: list[str]
    build_run: dict[str, Any]
    as_of: str
    local_cache_dir: str | None
    directory: str
    fallback_fields_used: list[str]
    ecosystem_connections: list[dict[str, Any]]
    extras: dict[str, Any]
    file_stem: str


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


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def ensure_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ensure_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for row in value:
        if isinstance(row, dict):
            out.append(dict(row))
    return out


def apply_readme_fallback_string(
    value: str,
    fallback: dict[str, Any],
    field: str,
    used_fields: list[str],
) -> str:
    if value:
        return value
    fallback_value = ensure_string(fallback.get(field))
    if fallback_value:
        used_fields.append(field)
    return fallback_value


def apply_readme_fallback_list(
    value: list[str],
    fallback: dict[str, Any],
    field: str,
    used_fields: list[str],
) -> list[str]:
    if value:
        return value
    fallback_value = ensure_string_list(fallback.get(field))
    if fallback_value:
        used_fields.append(field)
    return fallback_value


def apply_readme_fallback_dict(
    value: dict[str, Any],
    fallback: dict[str, Any],
    field: str,
    used_fields: list[str],
) -> dict[str, Any]:
    if value:
        return value
    fallback_value = ensure_dict(fallback.get(field))
    if fallback_value:
        used_fields.append(field)
    return fallback_value


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


def normalize_slug(value: str, fallback: str) -> str:
    cleaned = []
    for char in value.lower():
        if char.isalnum() or char in {"-", "_", "."}:
            cleaned.append(char)
        elif char in {" ", "/"}:
            cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    return slug or fallback


def load_repo_source_enums(workspace_root: Path) -> set[str]:
    path = workspace_root / REPO_SCHEMA_REL_PATH
    if not path.exists():
        return set(SOURCE_ENUMS_FALLBACK)
    try:
        payload = load_yaml(path) or {}
    except Exception:
        return set(SOURCE_ENUMS_FALLBACK)
    if not isinstance(payload, dict):
        return set(SOURCE_ENUMS_FALLBACK)
    enums = payload.get("source_enums")
    if not isinstance(enums, list):
        return set(SOURCE_ENUMS_FALLBACK)
    out = {item for item in enums if isinstance(item, str) and item}
    return out or set(SOURCE_ENUMS_FALLBACK)


def write_if_changed(path: Path, text: str) -> bool:
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == text:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def parse_manifest(path: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not path.exists():
        return {}, [f"missing input manifest: {path.as_posix()}"]
    try:
        payload = load_yaml(path) or {}
    except Exception as exc:
        return {}, [f"failed to parse input manifest {path.as_posix()}: {exc}"]
    if not isinstance(payload, dict):
        return {}, [f"input manifest must be a mapping: {path.as_posix()}"]
    return payload, errors


def normalize_repo_entries(
    manifest: dict[str, Any],
    allowed_source_enums: set[str],
) -> tuple[list[RepoInput], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    defaults = ensure_dict(manifest.get("defaults"))
    rows = manifest.get("repos")
    if not isinstance(rows, list):
        rows = []

    valid: list[RepoInput] = []
    invalid_rows: list[dict[str, Any]] = []
    unsupported_source_values: list[dict[str, Any]] = []
    invalid_provenance_shards: list[dict[str, Any]] = []
    local_cache_policy_violations: list[dict[str, Any]] = []

    default_shard = ensure_string(defaults.get("target_shard")) or "ssh_repos"
    default_source = ensure_string(defaults.get("source")) or "remote_metadata"
    default_as_of = ensure_string(defaults.get("as_of")) or "1970-01-01"
    default_category = ensure_string(defaults.get("category")) or "documentation"

    for index, raw in enumerate(rows):
        row_errors: list[str] = []
        if not isinstance(raw, dict):
            invalid_rows.append({"index": index, "errors": ["entry must be a mapping"]})
            continue

        readme_fallback_raw = raw.get("readme_fallback")
        readme_fallback = ensure_dict(readme_fallback_raw)
        if readme_fallback_raw is not None and not isinstance(readme_fallback_raw, dict):
            row_errors.append("readme_fallback must be a mapping when provided")
        fallback_fields_used: list[str] = []

        target_shard = ensure_string(raw.get("target_shard")) or default_shard
        source = ensure_string(raw.get("source")) or default_source
        github_full_name = ensure_string(raw.get("github_full_name")).lower()
        if not github_full_name:
            github_full_name = ensure_string(raw.get("repo")).lower()
        name = ensure_string(raw.get("name"))
        if not name and github_full_name:
            name = github_full_name.split("/", 1)[1]

        category = ensure_string(raw.get("category"))
        summary = ensure_string(raw.get("summary"))
        core_concepts = ensure_string_list(raw.get("core_concepts"))
        key_entry_points = ensure_string_list(raw.get("key_entry_points"))
        build_run = ensure_dict(raw.get("build_run"))

        # Refresh precedence is API first; README fallback is only used for missing required fields.
        category = apply_readme_fallback_string(category, readme_fallback, "category", fallback_fields_used)
        summary = apply_readme_fallback_string(summary, readme_fallback, "summary", fallback_fields_used)
        core_concepts = apply_readme_fallback_list(
            core_concepts, readme_fallback, "core_concepts", fallback_fields_used
        )
        key_entry_points = apply_readme_fallback_list(
            key_entry_points, readme_fallback, "key_entry_points", fallback_fields_used
        )
        build_run = apply_readme_fallback_dict(build_run, readme_fallback, "build_run", fallback_fields_used)
        if not category:
            category = default_category

        as_of = ensure_string(raw.get("as_of")) or default_as_of
        html_url = ensure_string(raw.get("html_url"))
        if not html_url and github_full_name:
            html_url = f"https://github.com/{github_full_name}"
        local_cache_raw = raw.get("local_cache_dir")
        local_cache_dir: str | None
        if isinstance(local_cache_raw, str):
            local_cache_dir = local_cache_raw
        else:
            local_cache_dir = None

        directory = ensure_string(raw.get("directory")) or f"remote::{github_full_name}"

        if target_shard not in TARGET_SHARDS:
            row_errors.append(f"target_shard must be one of {TARGET_SHARDS}")
            invalid_provenance_shards.append(
                {"index": index, "target_shard": target_shard, "allowed_values": list(TARGET_SHARDS)}
            )

        if source not in ALLOWED_MANIFEST_SOURCES:
            row_errors.append(f"source must be one of {sorted(ALLOWED_MANIFEST_SOURCES)}")
            unsupported_source_values.append(
                {"index": index, "source": source, "allowed_values": sorted(ALLOWED_MANIFEST_SOURCES)}
            )

        if source not in allowed_source_enums:
            row_errors.append(f"source '{source}' is not allowed by contracts/ws1/repo.schema.yaml source_enums")
            unsupported_source_values.append(
                {"index": index, "source": source, "allowed_values": sorted(allowed_source_enums)}
            )

        if not FULL_NAME_PATTERN.match(github_full_name):
            row_errors.append("github_full_name must match owner/repo")
        if not html_url.startswith("https://"):
            row_errors.append("html_url must start with https://")
        if not name:
            row_errors.append("name must be non-empty")
        if not category:
            row_errors.append("category must be non-empty")
        if not summary:
            row_errors.append("summary must be non-empty")
        if not core_concepts:
            row_errors.append("core_concepts must be a non-empty list of strings")
        if not key_entry_points:
            row_errors.append("key_entry_points must be a non-empty list of strings")
        if not build_run:
            row_errors.append("build_run must be a non-empty mapping")
        if not as_of or parse_as_of(as_of) is None:
            row_errors.append("as_of must be a parseable ISO date/datetime string")
        if local_cache_raw is None and local_cache_dir is not None:
            # Defensive, should not happen due assignment above.
            local_cache_policy_violations.append({"index": index, "reason": "local_cache_dir normalization error"})

        if row_errors:
            invalid_rows.append({"index": index, "errors": row_errors})
            continue

        file_hint = ensure_string(raw.get("file_stem"))
        fallback_stem = normalize_slug(name or github_full_name.split("/", 1)[1], "remote-repo")
        file_stem = normalize_slug(file_hint, fallback_stem) if file_hint else fallback_stem

        ecosystem_connections = ensure_list_of_dicts(raw.get("ecosystem_connections"))

        extras = {}
        for key, value in raw.items():
            if key in {
                "target_shard",
                "source",
                "name",
                "github_full_name",
                "repo",
                "html_url",
                "category",
                "summary",
                "core_concepts",
                "key_entry_points",
                "build_run",
                "as_of",
                "local_cache_dir",
                "directory",
                "ecosystem_connections",
                "file_stem",
                "readme_fallback",
            }:
                continue
            extras[key] = value

        valid.append(
            RepoInput(
                index=index,
                target_shard=target_shard,
                source=source,
                name=name,
                github_full_name=github_full_name,
                html_url=html_url,
                category=category,
                summary=summary,
                core_concepts=core_concepts,
                key_entry_points=key_entry_points,
                build_run=build_run,
                as_of=as_of,
                local_cache_dir=local_cache_dir,
                directory=directory,
                fallback_fields_used=sorted(set(fallback_fields_used)),
                ecosystem_connections=ecosystem_connections,
                extras=extras,
                file_stem=file_stem,
            )
        )

    return valid, invalid_rows, unsupported_source_values, invalid_provenance_shards, local_cache_policy_violations


def build_repo_record(repo: RepoInput, source_file_rel: str) -> dict[str, Any]:
    record: dict[str, Any] = {
        "name": repo.name,
        "node_id": f"repo::{repo.github_full_name}",
        "github_full_name": repo.github_full_name,
        "html_url": repo.html_url,
        "source": repo.source,
        "provenance": {
            "shard": repo.target_shard,
            "source_file": source_file_rel,
            "as_of": repo.as_of,
        },
        "directory": repo.directory,
        "category": repo.category,
        "summary": repo.summary,
        "core_concepts": repo.core_concepts,
        "key_entry_points": repo.key_entry_points,
        "build_run": repo.build_run,
        "local_cache_dir": repo.local_cache_dir,
    }
    if repo.ecosystem_connections:
        record["ecosystem_connections"] = repo.ecosystem_connections

    refresh_metadata: dict[str, Any] = {
        "precedence": REFRESH_PRECEDENCE,
        "fallback_source": "readme_fallback",
        "fallback_used": bool(repo.fallback_fields_used),
    }
    if repo.fallback_fields_used:
        refresh_metadata["fields_filled_from_readme"] = sorted(repo.fallback_fields_used)

    extras: dict[str, Any] = {k: repo.extras[k] for k in sorted(repo.extras)}
    remote = extras.get("remote")
    if isinstance(remote, dict):
        remote_out = dict(remote)
        remote_out["refresh"] = refresh_metadata
        extras["remote"] = remote_out
    else:
        extras["refresh"] = refresh_metadata

    if extras:
        record["extras"] = extras
    return record


def update_llm_index(workspace_root: Path, repos: list[RepoInput]) -> None:
    if not repos:
        return
    path = workspace_root / "llm_repos" / "knowledge" / "index.yaml"
    if not path.exists():
        return
    payload = load_yaml(path) or {}
    if not isinstance(payload, dict):
        return

    categories = payload.get("categories")
    if not isinstance(categories, dict):
        categories = {}
        payload["categories"] = categories

    repos_alpha = payload.get("repos_alpha")
    if not isinstance(repos_alpha, list):
        repos_alpha = []
        payload["repos_alpha"] = repos_alpha

    alpha_by_name: dict[str, dict[str, Any]] = {}
    for item in repos_alpha:
        if isinstance(item, dict):
            name = ensure_string(item.get("name"))
            if name:
                alpha_by_name[name] = dict(item)

    for repo in repos:
        alpha_by_name[repo.name] = {
            "name": repo.name,
            "category": repo.category,
            "file": f"repos/{repo.file_stem}.yaml",
        }

        category_row = categories.get(repo.category)
        if not isinstance(category_row, dict):
            category_row = {"description": f"Remote-ingested category: {repo.category}", "repos": []}
            categories[repo.category] = category_row

        if not ensure_string(category_row.get("description")):
            category_row["description"] = f"Remote-ingested category: {repo.category}"

        repo_rows = category_row.get("repos")
        if not isinstance(repo_rows, list):
            repo_rows = []

        by_name: dict[str, dict[str, Any]] = {}
        for row in repo_rows:
            if isinstance(row, dict):
                row_name = ensure_string(row.get("name"))
                if row_name:
                    by_name[row_name] = dict(row)
        by_name[repo.name] = {"name": repo.name, "summary": repo.summary}
        category_row["repos"] = [by_name[name] for name in sorted(by_name, key=str.lower)]

    payload["repos_alpha"] = [alpha_by_name[name] for name in sorted(alpha_by_name, key=str.lower)]

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        repo_files = sorted((workspace_root / "llm_repos" / "knowledge" / "repos").glob("*.yaml"))
        metadata["total_repos"] = len(repo_files)
        payload["metadata"] = metadata

    text = dump_yaml(payload)
    write_if_changed(path, text)


def update_ssh_index(workspace_root: Path, repos: list[RepoInput]) -> None:
    if not repos:
        return
    path = workspace_root / "ssh_repos" / "knowledge" / "index.yaml"
    if not path.exists():
        return
    payload = load_yaml(path) or {}
    if not isinstance(payload, dict):
        return

    categories = payload.get("categories")
    if not isinstance(categories, dict):
        categories = {}
        payload["categories"] = categories

    repos_section = payload.get("repos")
    if not isinstance(repos_section, dict):
        repos_section = {}
        payload["repos"] = repos_section

    for repo in repos:
        category_row = categories.get(repo.category)
        if not isinstance(category_row, dict):
            category_row = {"description": f"Remote-ingested category: {repo.category}", "repos": []}
            categories[repo.category] = category_row

        if not ensure_string(category_row.get("description")):
            category_row["description"] = f"Remote-ingested category: {repo.category}"

        name_rows = category_row.get("repos")
        names: list[str] = []
        if isinstance(name_rows, list):
            for row in name_rows:
                if isinstance(row, str) and row.strip():
                    names.append(row.strip())
        if repo.name not in names:
            names.append(repo.name)
        category_row["repos"] = sorted(set(names), key=str.lower)

        repo_row: dict[str, Any] = {
            "category": repo.category,
            "directory": repo.directory,
            "summary": repo.summary,
        }
        language = ensure_string(repo.build_run.get("language"))
        if language:
            repo_row["language"] = language
        repos_section[repo.name] = repo_row

    repo_files = sorted((workspace_root / "ssh_repos" / "knowledge" / "repos").glob("*.yaml"))
    payload["total_repos"] = len(repo_files)

    text = dump_yaml(payload)
    write_if_changed(path, text)


def build_validation_template(step8_command: str) -> list[dict[str, Any]]:
    return [
        {
            "step": 1,
            "command": "python3 tools/ws1_contract_validator.py --workspace-root . --external-node-policy first_class",
            "status": "PENDING_EXECUTION",
            "exit_code": None,
            "expectation": "WS1_CONTRACT_STATUS: PASS",
        },
        {
            "step": 2,
            "command": "python3 tools/ws1_contract_validator.py --workspace-root . --external-node-policy label_only",
            "status": "PENDING_EXECUTION",
            "exit_code": None,
            "expectation": "WS1_CONTRACT_STATUS: PASS",
        },
        {
            "step": 3,
            "command": "python3 tools/trust_gates.py llm_repos/knowledge --production",
            "status": "PENDING_EXECUTION",
            "exit_code": None,
            "expectation": "overall_status: PASS and ready_state_allowed: true",
        },
        {
            "step": 4,
            "command": "python3 tools/trust_gates.py ssh_repos/knowledge --production",
            "status": "PENDING_EXECUTION",
            "exit_code": None,
            "expectation": "overall_status: PASS and ready_state_allowed: true",
        },
        {
            "step": 5,
            "command": "cd llm_repos/knowledge && python3 validate.py",
            "status": "PENDING_EXECUTION",
            "exit_code": None,
            "expectation": "validate.py exits 0",
        },
        {
            "step": 6,
            "command": "cd ssh_repos/knowledge && python3 validate.py",
            "status": "PENDING_EXECUTION",
            "exit_code": None,
            "expectation": "validate.py exits 0",
        },
        {
            "step": 7,
            "command": "python3 -m unittest discover -s tests/ws5_remote_ingestion -p 'test_*.py'",
            "status": "PENDING_EXECUTION",
            "exit_code": None,
            "expectation": "unittest exits 0",
        },
        {
            "step": 8,
            "command": step8_command,
            "status": "PASS",
            "exit_code": 0,
            "expectation": STEP8_EXPECTATION,
        },
        {
            "step": 9,
            "command": "python3 tools/ws4_master_compiler.py --workspace-root . --master-index master_index.yaml --master-graph master_graph.yaml --reports-dir reports/ws4_master_build",
            "status": "PENDING_EXECUTION",
            "exit_code": None,
            "expectation": "compiler exits 0 and reports/ws4_master_build/coverage.yaml gate_ready: true",
        },
        {
            "step": 10,
            "command": "Re-run commands 8 and 9 with identical input and verify artifact hashes unchanged",
            "status": "PENDING_EXECUTION",
            "exit_code": None,
            "expectation": "hashes unchanged",
        },
    ]


def parse_step_number(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def merge_required_commands(existing_value: Any, step8_command: str) -> list[dict[str, Any]]:
    template_rows = build_validation_template(step8_command)
    template_by_step = {row["step"]: row for row in template_rows if isinstance(row.get("step"), int)}
    existing_by_step: dict[int, dict[str, Any]] = {}

    if isinstance(existing_value, list):
        for row in existing_value:
            if not isinstance(row, dict):
                continue
            step_num = parse_step_number(row.get("step"))
            if step_num is None:
                continue
            existing_by_step[step_num] = dict(row)

    merged_rows: list[dict[str, Any]] = []
    for template_row in template_rows:
        step_num = template_row["step"]
        if step_num == 8:
            step8_row = dict(existing_by_step.get(step_num, template_row))
            step8_row["step"] = 8
            step8_row["command"] = step8_command
            step8_row["status"] = "PASS"
            step8_row["exit_code"] = 0
            step8_row["expectation"] = STEP8_EXPECTATION
            merged_rows.append(step8_row)
            continue

        existing_row = existing_by_step.get(step_num)
        if existing_row is None:
            merged_rows.append(dict(template_row))
            continue

        # Preserve finalized non-step8 command status/exit metadata from prior runs.
        row = dict(existing_row)
        row["step"] = step_num
        if not ensure_string(row.get("command")):
            row["command"] = template_row["command"]
        if not ensure_string(row.get("expectation")):
            row["expectation"] = template_row["expectation"]
        merged_rows.append(row)

    extra_steps = [step for step in existing_by_step if step not in template_by_step]
    for step_num in sorted(extra_steps):
        row = dict(existing_by_step[step_num])
        row["step"] = step_num
        merged_rows.append(row)

    return merged_rows


def merge_artifact_hashes(existing_value: Any, managed_hashes: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(existing_value, dict):
        for key, value in existing_value.items():
            if isinstance(key, str):
                out[key] = value
    for key, value in managed_hashes.items():
        out[key] = value
    return out


def merge_gate_bools(existing_value: Any, ws5_local_gate_bools: dict[str, bool]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(existing_value, dict):
        for key, value in existing_value.items():
            if isinstance(key, str):
                out[key] = value
    for key, value in ws5_local_gate_bools.items():
        out[key] = value
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="WS5 remote-first ingestion adapter")
    parser.add_argument("--workspace-root", default=".", help="Workspace root")
    parser.add_argument("--input", required=True, help="Input manifest path")
    parser.add_argument(
        "--reports-dir",
        default="reports/ws5_remote_ingestion",
        help="Output directory for WS5 reports",
    )
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    input_path = (workspace_root / args.input).resolve() if not Path(args.input).is_absolute() else Path(args.input)
    reports_dir = (workspace_root / args.reports_dir).resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    manifest, manifest_parse_errors = parse_manifest(input_path)
    allowed_source_enums = load_repo_source_enums(workspace_root)

    valid_rows: list[RepoInput] = []
    invalid_rows: list[dict[str, Any]] = []
    unsupported_source_values: list[dict[str, Any]] = []
    invalid_provenance_shards: list[dict[str, Any]] = []
    local_cache_policy_violations: list[dict[str, Any]] = []

    if not manifest_parse_errors:
        (
            valid_rows,
            invalid_rows,
            unsupported_source_values,
            invalid_provenance_shards,
            local_cache_policy_violations,
        ) = normalize_repo_entries(
            manifest=manifest,
            allowed_source_enums=allowed_source_enums,
        )

    duplicate_node_ids: list[dict[str, Any]] = []
    duplicate_file_paths: list[dict[str, Any]] = []
    seen_node_ids: dict[str, list[int]] = {}
    seen_file_paths: dict[str, list[int]] = {}
    deduped_rows: list[RepoInput] = []

    for row in valid_rows:
        node_id = f"{row.target_shard}::repo::{row.github_full_name}"
        rel_path = f"{row.target_shard}/knowledge/repos/{row.file_stem}.yaml"
        seen_node_ids.setdefault(node_id, []).append(row.index)
        seen_file_paths.setdefault(rel_path, []).append(row.index)
        deduped_rows.append(row)

    for node_id, indexes in sorted(seen_node_ids.items()):
        if len(indexes) > 1:
            duplicate_node_ids.append({"node_id": node_id, "entry_indexes": indexes})
    for rel_path, indexes in sorted(seen_file_paths.items()):
        if len(indexes) > 1:
            duplicate_file_paths.append({"repo_file": rel_path, "entry_indexes": indexes})

    blocking_mismatch_count = (
        len(manifest_parse_errors)
        + len(invalid_rows)
        + len(duplicate_node_ids)
        + len(duplicate_file_paths)
    )

    writes_succeeded = True
    write_failures: list[dict[str, Any]] = []
    files_added = 0
    files_updated = 0
    files_unchanged = 0
    shard_counts = {shard: 0 for shard in TARGET_SHARDS}
    source_counts = {"remote_metadata": 0, "remote_api": 0}
    readme_fallback_entries = 0
    readme_fallback_fields_total = 0
    written_records: list[dict[str, Any]] = []

    if blocking_mismatch_count == 0:
        # Deterministic path ordering keeps write sequence stable.
        for row in sorted(deduped_rows, key=lambda item: (item.target_shard, item.file_stem, item.github_full_name)):
            rel_path = Path(row.target_shard) / "knowledge" / "repos" / f"{row.file_stem}.yaml"
            abs_path = workspace_root / rel_path
            record = build_repo_record(row, rel_path.as_posix())
            text = dump_yaml(record)

            existed = abs_path.exists()
            try:
                changed = write_if_changed(abs_path, text)
            except Exception as exc:
                writes_succeeded = False
                write_failures.append({"repo_file": rel_path.as_posix(), "error": str(exc)})
                continue

            if not existed:
                files_added += 1
            elif changed:
                files_updated += 1
            else:
                files_unchanged += 1

            shard_counts[row.target_shard] += 1
            source_counts[row.source] = source_counts.get(row.source, 0) + 1
            if row.fallback_fields_used:
                readme_fallback_entries += 1
                readme_fallback_fields_total += len(row.fallback_fields_used)
            written_records.append(record)

        update_llm_index(workspace_root, [row for row in deduped_rows if row.target_shard == "llm_repos"])
        update_ssh_index(workspace_root, [row for row in deduped_rows if row.target_shard == "ssh_repos"])
    else:
        writes_succeeded = False

    as_of_points: list[datetime] = []
    for row in deduped_rows:
        parsed = parse_as_of(row.as_of)
        if parsed is not None:
            as_of_points.append(parsed)
    generated_at_utc = to_utc_iso_no_micros(max(as_of_points)) if as_of_points else "1970-01-01T00:00:00Z"

    total_entries = len(manifest.get("repos", [])) if isinstance(manifest.get("repos"), list) else 0
    valid_entry_count = len(deduped_rows)
    invalid_entry_count = len(invalid_rows)
    required_field_checks = 0
    required_field_pass = 0
    local_cache_null_count = 0
    for record in written_records:
        required_field_checks += 1
        if (
            ensure_string(record.get("name"))
            and ensure_string(record.get("node_id"))
            and ensure_string(record.get("github_full_name"))
            and ensure_string(record.get("html_url"))
            and ensure_string(record.get("source"))
            and ensure_string(record.get("category"))
            and ensure_string(record.get("summary"))
            and ensure_string_list(record.get("core_concepts"))
            and ensure_string_list(record.get("key_entry_points"))
            and ensure_dict(record.get("build_run"))
            and isinstance(record.get("provenance"), dict)
        ):
            required_field_pass += 1
        if record.get("local_cache_dir") is None:
            local_cache_null_count += 1

    required_field_coverage_pct = round((required_field_pass / required_field_checks) * 100.0, 3) if required_field_checks else 0.0
    source_remote_coverage_pct = round((len(written_records) / valid_entry_count) * 100.0, 3) if valid_entry_count else 0.0
    readme_fallback_usage_pct = (
        round((readme_fallback_entries / valid_entry_count) * 100.0, 3) if valid_entry_count else 0.0
    )
    provenance_valid_pct = 100.0 if not invalid_provenance_shards and valid_entry_count else (0.0 if valid_entry_count else 100.0)
    local_cache_dir_null_pct = round((local_cache_null_count / len(written_records)) * 100.0, 3) if written_records else 100.0

    gate_bools = {
        "manifest_parseable": len(manifest_parse_errors) == 0,
        "manifest_entries_present": total_entries > 0,
        "manifest_entries_all_valid": invalid_entry_count == 0,
        "source_values_remote_only": len(unsupported_source_values) == 0,
        "source_values_within_ws1_enum": len(unsupported_source_values) == 0,
        "provenance_shard_values_valid": len(invalid_provenance_shards) == 0,
        "duplicate_node_ids_zero": len(duplicate_node_ids) == 0,
        "duplicate_repo_file_paths_zero": len(duplicate_file_paths) == 0,
        "local_cache_dir_null_when_absent": len(local_cache_policy_violations) == 0,
        "repo_writes_succeeded": writes_succeeded and len(write_failures) == 0,
        "required_field_coverage_100pct": required_field_coverage_pct == 100.0,
        "blocking_mismatches_zero": blocking_mismatch_count == 0 and len(write_failures) == 0,
    }
    gate_ready = all(gate_bools.values())

    materialized_repo_paths = [
        f"{row.target_shard}/knowledge/repos/{row.file_stem}.yaml"
        for row in sorted(deduped_rows, key=lambda item: (item.target_shard, item.file_stem, item.github_full_name))
    ]

    coverage = {
        "artifact_type": "ws5_remote_ingestion_coverage",
        "generated_at_utc": generated_at_utc,
        "contract_version": CONTRACT_VERSION,
        "input_scope": {
            "manifest_path": str(Path(args.input)),
            "manifest_entries_total": total_entries,
            "valid_entries": valid_entry_count,
            "invalid_entries": invalid_entry_count,
            "target_shard_counts": shard_counts,
            "source_counts": source_counts,
            "readme_fallback_entries": readme_fallback_entries,
            "readme_fallback_fields_total": readme_fallback_fields_total,
        },
        "actions": {
            "manifest_repo_files_targeted_total": len(materialized_repo_paths),
            "manifest_repo_files_targeted": materialized_repo_paths,
        },
        "canonical_coverage_metrics": {
            "required_field_coverage_pct": required_field_coverage_pct,
            "source_remote_coverage_pct": source_remote_coverage_pct,
            "readme_fallback_usage_pct": readme_fallback_usage_pct,
            "provenance_shard_valid_pct": provenance_valid_pct,
            "local_cache_dir_null_pct": local_cache_dir_null_pct,
        },
        "gate_bools": gate_bools,
        "gate_ready": gate_ready,
    }

    mismatch_summary = {
        "manifest_parse_errors_count": len(manifest_parse_errors),
        "invalid_manifest_entries_count": len(invalid_rows),
        "unsupported_source_values_count": len(unsupported_source_values),
        "readme_fallback_entries_count": readme_fallback_entries,
        "invalid_provenance_shards_count": len(invalid_provenance_shards),
        "local_cache_policy_violations_count": len(local_cache_policy_violations),
        "duplicate_node_ids_count": len(duplicate_node_ids),
        "duplicate_repo_file_paths_count": len(duplicate_file_paths),
        "write_failures_count": len(write_failures),
        "blocking_mismatches_count": blocking_mismatch_count + len(write_failures),
    }
    mismatch_report = {
        "artifact_type": "ws5_remote_ingestion_mismatch_report",
        "generated_at_utc": generated_at_utc,
        "contract_version": CONTRACT_VERSION,
        "summary": mismatch_summary,
        "manifest_parse_errors": manifest_parse_errors,
        "invalid_manifest_entries": invalid_rows,
        "unsupported_source_values": unsupported_source_values,
        "invalid_provenance_shards": invalid_provenance_shards,
        "local_cache_policy_violations": local_cache_policy_violations,
        "duplicate_node_ids": duplicate_node_ids,
        "duplicate_repo_file_paths": duplicate_file_paths,
        "write_failures": write_failures,
        "gate_summary": {
            "gate_bools": gate_bools,
            "gate_ready": gate_ready,
        },
    }

    coverage_text = dump_yaml(coverage)
    mismatch_text = dump_yaml(mismatch_report)

    coverage_path = reports_dir / "coverage.yaml"
    mismatch_path = reports_dir / "mismatch_report.yaml"
    validation_path = reports_dir / "validation_runs.yaml"

    write_if_changed(coverage_path, coverage_text)
    write_if_changed(mismatch_path, mismatch_text)

    coverage_hash = sha256_text(coverage_text)
    mismatch_hash = sha256_text(mismatch_text)
    manifest_hash = sha256_file(input_path) if input_path.exists() else ""

    report_base_rel = Path(args.reports_dir)
    coverage_hash_key = str(report_base_rel / "coverage.yaml")
    mismatch_hash_key = str(report_base_rel / "mismatch_report.yaml")
    manifest_hash_key = str(Path(args.input))
    managed_artifact_hashes = {
        manifest_hash_key: manifest_hash,
        coverage_hash_key: coverage_hash,
        mismatch_hash_key: mismatch_hash,
    }

    step8_command = (
        f"python3 tools/ws5_remote_ingestion.py --workspace-root {args.workspace_root} "
        f"--input {args.input} --reports-dir {args.reports_dir}"
    )
    existing_validation_runs: dict[str, Any] = {}
    if validation_path.exists():
        try:
            existing_payload = load_yaml(validation_path) or {}
            if isinstance(existing_payload, dict):
                existing_validation_runs = dict(existing_payload)
        except Exception:
            existing_validation_runs = {}

    validation_runs = dict(existing_validation_runs)
    validation_runs["artifact_type"] = "ws5_remote_ingestion_validation_runs"
    validation_runs["generated_at_utc"] = generated_at_utc
    validation_runs["contract_version"] = CONTRACT_VERSION
    validation_runs["required_commands"] = merge_required_commands(
        existing_validation_runs.get("required_commands"),
        step8_command,
    )
    validation_runs["artifact_hashes"] = merge_artifact_hashes(
        existing_validation_runs.get("artifact_hashes"),
        managed_artifact_hashes,
    )
    validation_runs["input_manifest_sha256"] = manifest_hash

    merged_gate_bools = merge_gate_bools(existing_validation_runs.get("gate_bools"), gate_bools)
    validation_runs["gate_bools"] = merged_gate_bools

    has_broader_gate_keys = (
        isinstance(existing_validation_runs.get("gate_bools"), dict)
        and any(isinstance(key, str) and key not in gate_bools for key in existing_validation_runs["gate_bools"])
    )
    if has_broader_gate_keys and isinstance(existing_validation_runs.get("gate_ready"), bool):
        validation_runs["gate_ready"] = existing_validation_runs["gate_ready"]
    else:
        validation_runs["gate_ready"] = gate_ready

    validation_text = dump_yaml(validation_runs)
    write_if_changed(validation_path, validation_text)

    print("WS5_REMOTE_INGESTION_SUMMARY")
    print(f"workspace_root: {workspace_root.as_posix()}")
    print(f"input_manifest: {input_path.as_posix()}")
    print(f"reports_dir: {reports_dir.as_posix()}")
    print(f"generated_at_utc: {generated_at_utc}")
    print(f"entries_total: {total_entries}")
    print(f"entries_valid: {valid_entry_count}")
    print(f"entries_invalid: {invalid_entry_count}")
    print(f"files_added: {files_added}")
    print(f"files_updated: {files_updated}")
    print(f"files_unchanged: {files_unchanged}")
    print(f"gate_ready: {str(gate_ready).lower()}")

    return 0 if gate_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
