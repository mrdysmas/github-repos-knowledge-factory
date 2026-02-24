#!/usr/bin/env python3
"""
WS2 identity/provenance backfill and evidence writer.

Deterministic pass over:
- llm_repos/knowledge/repos/*.yaml
- llm_repos/knowledge/deep/*.yaml
- ssh_repos/knowledge/repos/*.yaml
- ssh_repos/knowledge/deep/*.yaml

Applies canonical fields:
- node_id
- github_full_name
- html_url
- source
- provenance.{shard,source_file,as_of}

Writes evidence artifacts:
- reports/ws2_identity/coverage.yaml
- reports/ws2_identity/mismatch_report.yaml
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap


WORKSPACE_ROOT = Path(".")
CONTRACT_VERSION = "1.0.0-ws1"
REQUIRED_FIELDS = ["node_id", "github_full_name", "html_url", "source", "provenance"]
HIGH_CONFIDENCE_SOURCES = {
    "git_origin",
    "go_mod_module",
    "pyproject_meta",
    "package_json_meta",
    "cargo_repository",
    "setup_py_meta",
    "setup_cfg_meta",
    "pom_xml_scm",
    "mkdocs_repo_url",
    "pubspec_meta",
    "goreleaser_meta",
    "llm_manifest",
}
SOURCE_RANK = {
    "git_origin": 10,
    "go_mod_module": 20,
    "pyproject_meta": 30,
    "package_json_meta": 40,
    "cargo_repository": 45,
    "setup_py_meta": 50,
    "setup_cfg_meta": 55,
    "pom_xml_scm": 60,
    "mkdocs_repo_url": 70,
    "pubspec_meta": 75,
    "goreleaser_meta": 80,
    "llm_manifest": 85,
    "readme_self_match": 90,
}
ALLOWED_MASTER_FALLBACK = {"ssh_repos/knowledge/repos/awesome-tunneling.yaml"}


URL_PATTERNS = [
    re.compile(
        r"(?:git\+)?https?://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?(?:[/?#]|$|[\s\"'(),])",
        re.IGNORECASE,
    ),
    re.compile(
        r"git@github\.com:(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?(?:\s|$|[\"])",
        re.IGNORECASE,
    ),
]


@dataclass(frozen=True)
class Candidate:
    full_name: str
    source: str


@dataclass
class Resolution:
    full_name: str
    source: str
    fallback_used: bool


class BackfillError(RuntimeError):
    pass


def norm_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def strip_dir_suffix(value: str) -> str:
    for suffix in ("-main", "-master", "-develop", "-dev"):
        if value.lower().endswith(suffix):
            return value[: -len(suffix)]
    return value


def extract_github_full_names(text: str) -> list[str]:
    out: list[str] = []
    for pattern in URL_PATTERNS:
        for match in pattern.finditer(text):
            owner = match.group("owner").strip().lower()
            repo = match.group("repo").strip().lower().strip("}>,.;:")
            if owner and repo:
                out.append(f"{owner}/{repo}")
    return out


def parse_git_origin(path: Path) -> list[str]:
    if not path.exists():
        return []
    values: list[str] = []
    in_origin = False
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_origin = 'remote "origin"' in stripped
            continue
        if in_origin and stripped.startswith("url ="):
            values.extend(extract_github_full_names(stripped.split("=", 1)[1].strip()))
    return values


def parse_go_mod(path: Path) -> list[str]:
    if not path.exists():
        return []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped.startswith("module "):
            module_path = stripped.split(None, 1)[1].strip()
            if module_path.startswith("github.com/"):
                return extract_github_full_names(f"https://{module_path}")
            return extract_github_full_names(module_path)
    return []


def parse_pyproject(path: Path) -> list[str]:
    if not path.exists():
        return []
    values: list[str] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        payload = tomllib.loads(text)
    except Exception:
        payload = {}

    if isinstance(payload, dict):
        project = payload.get("project")
        if isinstance(project, dict):
            urls = project.get("urls")
            if isinstance(urls, dict):
                for value in urls.values():
                    if isinstance(value, str):
                        values.extend(extract_github_full_names(value))
            for key in ("homepage", "repository"):
                value = project.get(key)
                if isinstance(value, str):
                    values.extend(extract_github_full_names(value))

        tool = payload.get("tool")
        if isinstance(tool, dict):
            poetry = tool.get("poetry")
            if isinstance(poetry, dict):
                for key in ("homepage", "repository"):
                    value = poetry.get(key)
                    if isinstance(value, str):
                        values.extend(extract_github_full_names(value))

    for line in text.splitlines():
        low = line.lower()
        if "=" not in line:
            continue
        if any(key in low for key in ("repository", "homepage", "source", "url")):
            values.extend(extract_github_full_names(line))
    return values


def parse_package_json(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    values: list[str] = []
    repository = payload.get("repository")
    if isinstance(repository, str):
        values.extend(extract_github_full_names(repository))
    elif isinstance(repository, dict):
        url = repository.get("url")
        if isinstance(url, str):
            values.extend(extract_github_full_names(url))

    homepage = payload.get("homepage")
    if isinstance(homepage, str):
        values.extend(extract_github_full_names(homepage))

    bugs = payload.get("bugs")
    if isinstance(bugs, str):
        values.extend(extract_github_full_names(bugs))
    elif isinstance(bugs, dict):
        url = bugs.get("url")
        if isinstance(url, str):
            values.extend(extract_github_full_names(url))

    return values


def parse_cargo_toml(path: Path) -> list[str]:
    if not path.exists():
        return []
    values: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if re.match(r"\s*repository\s*=\s*\"", line):
            values.extend(extract_github_full_names(line))
    return values


def parse_setup_py(path: Path) -> list[str]:
    if not path.exists():
        return []
    values: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        low = line.lower()
        if "github.com/" not in low:
            continue
        if any(
            token in low
            for token in ("url=", "url =", "project_urls", "repository", "source", "homepage", "scm")
        ):
            values.extend(extract_github_full_names(line))
    return values


def parse_setup_cfg(path: Path) -> list[str]:
    if not path.exists():
        return []
    values: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        low = line.lower()
        if "github.com/" not in low:
            continue
        if any(token in low for token in ("home-page", "homepage", "url", "project_urls", "repository", "source")):
            values.extend(extract_github_full_names(line))
    return values


def parse_pom_xml(path: Path) -> list[str]:
    if not path.exists():
        return []
    values: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        low = line.lower()
        if "github.com/" not in low:
            continue
        if any(token in low for token in ("<url>", "<connection>", "<developerconnection>", "<scm>")):
            values.extend(extract_github_full_names(line))
    return values


def parse_mkdocs(path: Path) -> list[str]:
    if not path.exists():
        return []
    values: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip().startswith("repo_url:"):
            values.extend(extract_github_full_names(line))
    return values


def parse_pubspec(path: Path) -> list[str]:
    if not path.exists():
        return []
    values: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped.startswith("repository:") or stripped.startswith("homepage:"):
            values.extend(extract_github_full_names(stripped))
    return values


def parse_goreleaser(path: Path) -> list[str]:
    if not path.exists():
        return []
    values: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "github.com/" in line.lower():
            values.extend(extract_github_full_names(line))
    return values


def parse_readme_self_matches(path: Path, expected_tokens: set[str]) -> list[str]:
    if not path.exists():
        return []
    values: list[str] = []
    for full_name in extract_github_full_names(path.read_text(encoding="utf-8", errors="ignore")):
        repo = full_name.split("/", 1)[1]
        if norm_token(repo) in expected_tokens:
            values.append(full_name)
    return values


def dedupe_preserve(values: list[Candidate]) -> list[Candidate]:
    seen: set[str] = set()
    out: list[Candidate] = []
    for value in values:
        if value.full_name in seen:
            continue
        seen.add(value.full_name)
        out.append(value)
    return out


def collect_local_candidates(repo_dir: Path, expected_tokens: set[str]) -> list[Candidate]:
    candidates: list[Candidate] = []

    def add(full_names: list[str], source: str) -> None:
        for full_name in full_names:
            candidates.append(Candidate(full_name=full_name, source=source))

    add(parse_git_origin(repo_dir / ".git/config"), "git_origin")
    add(parse_go_mod(repo_dir / "go.mod"), "go_mod_module")
    add(parse_pyproject(repo_dir / "pyproject.toml"), "pyproject_meta")
    add(parse_package_json(repo_dir / "package.json"), "package_json_meta")
    add(parse_cargo_toml(repo_dir / "Cargo.toml"), "cargo_repository")
    add(parse_setup_py(repo_dir / "setup.py"), "setup_py_meta")
    add(parse_setup_cfg(repo_dir / "setup.cfg"), "setup_cfg_meta")
    add(parse_pom_xml(repo_dir / "pom.xml"), "pom_xml_scm")
    add(parse_mkdocs(repo_dir / "mkdocs.yml"), "mkdocs_repo_url")
    add(parse_pubspec(repo_dir / "pubspec.yaml"), "pubspec_meta")
    add(parse_goreleaser(repo_dir / ".goreleaser.yml"), "goreleaser_meta")
    add(parse_goreleaser(repo_dir / ".goreleaser.yaml"), "goreleaser_meta")

    # README links are accepted only when they self-match expected tokens.
    add(parse_readme_self_matches(repo_dir / "README.md", expected_tokens), "readme_self_match")
    add(parse_readme_self_matches(repo_dir / "README.MD", expected_tokens), "readme_self_match")
    add(parse_readme_self_matches(repo_dir / "README.rst", expected_tokens), "readme_self_match")
    add(parse_readme_self_matches(repo_dir / "CHANGELOG.md", expected_tokens), "readme_self_match")
    add(parse_readme_self_matches(repo_dir / "CHANGELOG.MD", expected_tokens), "readme_self_match")
    add(parse_readme_self_matches(repo_dir / "CHANGES.rst", expected_tokens), "readme_self_match")

    return dedupe_preserve(candidates)


def choose_from_candidates(
    repo_record_path: Path,
    candidates: list[Candidate],
    expected_tokens: set[str],
) -> Resolution | None:
    def is_self(candidate: Candidate) -> bool:
        repo_part = candidate.full_name.split("/", 1)[1]
        return norm_token(repo_part) in expected_tokens

    self_candidates = [candidate for candidate in candidates if is_self(candidate)]
    if self_candidates:
        by_rank: dict[int, set[str]] = defaultdict(set)
        rank_source: dict[tuple[int, str], str] = {}
        for candidate in self_candidates:
            rank = SOURCE_RANK.get(candidate.source, 999)
            by_rank[rank].add(candidate.full_name)
            rank_source[(rank, candidate.full_name)] = candidate.source

        for rank in sorted(by_rank):
            values = sorted(by_rank[rank])
            if len(values) == 1:
                full_name = values[0]
                source = rank_source[(rank, full_name)]
                return Resolution(full_name=full_name, source=source, fallback_used=False)
            if len(values) > 1:
                raise BackfillError(
                    f"Ambiguous self-match candidates for {repo_record_path}: {values}"
                )

    # No self-match: only high-confidence local candidates can auto-resolve.
    non_self_high_conf = sorted(
        {
            candidate.full_name
            for candidate in candidates
            if candidate.source in HIGH_CONFIDENCE_SOURCES
        }
    )
    if len(non_self_high_conf) == 1:
        full_name = non_self_high_conf[0]
        for candidate in candidates:
            if candidate.full_name == full_name:
                return Resolution(full_name=full_name, source=candidate.source, fallback_used=False)
        raise AssertionError("unreachable")
    if len(non_self_high_conf) > 1:
        raise BackfillError(
            "Ambiguous non-self local candidates for "
            f"{repo_record_path}: {non_self_high_conf}. Stop for escalation."
        )

    return None


def load_master_fallback_map(path: Path) -> dict[str, str]:
    yaml = YAML(typ="safe")
    payload = yaml.load(path.read_text(encoding="utf-8")) or {}
    rows = payload.get("repos", [])
    out: dict[str, str] = {}
    for row in rows:
        local_path = row.get("local_path")
        github_url = row.get("github_url")
        if not isinstance(local_path, str) or not isinstance(github_url, str):
            continue
        values = extract_github_full_names(github_url)
        if not values:
            continue
        out[Path(local_path).name] = values[0]
    return out


def load_llm_manifest_map(path: Path) -> dict[str, str]:
    yaml = YAML(typ="safe")
    payload = yaml.load(path.read_text(encoding="utf-8")) or {}
    rows = payload.get("repos", [])
    out: dict[str, str] = {}
    for row in rows:
        directory = row.get("name")
        github_url = row.get("github_url")
        if not isinstance(directory, str) or not isinstance(github_url, str):
            continue
        values = extract_github_full_names(github_url)
        if not values:
            continue
        out[directory] = values[0]
    return out


def expected_tokens_for_record(repo_name: str, stem: str, directory: str) -> set[str]:
    tokens = {
        norm_token(repo_name),
        norm_token(stem),
        norm_token(strip_dir_suffix(directory)),
    }
    return {token for token in tokens if token}


def relative(path: Path) -> str:
    cwd = Path.cwd().resolve()
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(cwd).as_posix())
    except Exception:
        return str(path.as_posix())


def parse_record_safe(yaml_rt: YAML, path: Path) -> CommentedMap:
    payload = yaml_rt.load(path.read_text(encoding="utf-8"))
    if payload is None:
        payload = CommentedMap()
    if not isinstance(payload, CommentedMap):
        raise BackfillError(f"Expected mapping in {path}, got {type(payload).__name__}")
    return payload


def insert_identity_fields(record: CommentedMap, identity: dict[str, Any]) -> None:
    insert_anchor = None
    for candidate in ("name", "repo", "repo_id", "full_name", "directory"):
        if candidate in record:
            insert_anchor = candidate
            break

    if insert_anchor is None:
        for key, value in identity.items():
            record[key] = value
        return

    # Insert fields right after anchor while preserving existing order/comments.
    keys = list(record.keys())
    anchor_idx = keys.index(insert_anchor)

    # Remove existing identity keys to reinsert in canonical order.
    for key in ("node_id", "github_full_name", "html_url", "source", "provenance"):
        if key in record:
            del record[key]

    for offset, key in enumerate(("node_id", "github_full_name", "html_url", "source", "provenance"), start=1):
        record.insert(anchor_idx + offset, key, identity[key])


def record_missing_fields(record: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in REQUIRED_FIELDS:
        if key not in record:
            missing.append(key)
    return missing


def is_valid_github_full_name(value: Any) -> bool:
    return isinstance(value, str) and re.match(r"^[^/]+/[^/]+$", value) is not None


def is_valid_html_url(value: Any) -> bool:
    return isinstance(value, str) and re.match(r"^https://github\.com/[^/]+/[^/]+$", value) is not None


def audit_identity(path: Path, payload: dict[str, Any], expected_shard: str) -> tuple[list[str], list[str]]:
    malformed: list[str] = []
    provenance_errors: list[str] = []

    full_name = payload.get("github_full_name")
    html_url = payload.get("html_url")
    source = payload.get("source")
    node_id = payload.get("node_id")
    provenance = payload.get("provenance")

    if not is_valid_github_full_name(full_name):
        malformed.append("github_full_name")

    if not is_valid_html_url(html_url):
        malformed.append("html_url")

    if not isinstance(node_id, str) or not node_id.startswith("repo::"):
        malformed.append("node_id")

    if source != expected_shard:
        malformed.append("source")

    if not isinstance(provenance, dict):
        provenance_errors.append("provenance")
    else:
        shard = provenance.get("shard")
        source_file = provenance.get("source_file")
        as_of = provenance.get("as_of")
        if shard not in {"llm_repos", "ssh_repos", "merged"}:
            provenance_errors.append("provenance.shard")
        if shard != expected_shard:
            provenance_errors.append("provenance.shard_mismatch")
        if source_file != relative(path):
            provenance_errors.append("provenance.source_file")
        if not isinstance(as_of, str) or not as_of:
            provenance_errors.append("provenance.as_of")

    return malformed, provenance_errors


def build_resolution_map(
    yaml_safe: YAML,
    shallow_paths: list[Path],
    root: Path,
    llm_manifest_map: dict[str, str],
    fallback_map: dict[str, str],
) -> tuple[dict[str, Resolution], list[dict[str, Any]]]:
    resolution_by_path: dict[str, Resolution] = {}
    fallback_events: list[dict[str, Any]] = []

    fallback_records_used: set[str] = set()

    for path in shallow_paths:
        payload = yaml_safe.load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise BackfillError(f"Expected mapping in {path}")

        shard = path.relative_to(root).parts[0]
        stem = path.stem
        repo_name = str(payload.get("name", stem))
        directory = payload.get("directory")
        if not isinstance(directory, str) or not directory:
            raise BackfillError(f"Missing/invalid directory in shallow record {path}")

        expected_tokens = expected_tokens_for_record(repo_name=repo_name, stem=stem, directory=directory)
        repo_dir = root / shard / directory
        candidates = collect_local_candidates(repo_dir, expected_tokens)

        resolution = choose_from_candidates(path, candidates, expected_tokens)
        if resolution is None:
            if shard == "llm_repos" and directory in llm_manifest_map:
                resolution = Resolution(
                    full_name=llm_manifest_map[directory],
                    source="llm_manifest",
                    fallback_used=False,
                )
        if resolution is None:
            fallback_value = fallback_map.get(directory)
            if fallback_value:
                record_rel = relative(path)
                if record_rel not in ALLOWED_MASTER_FALLBACK:
                    raise BackfillError(
                        "Fallback required for unexpected record "
                        f"{record_rel}; approval only permits {sorted(ALLOWED_MASTER_FALLBACK)}"
                    )
                resolution = Resolution(
                    full_name=fallback_value,
                    source="assistive_master_repo_list",
                    fallback_used=True,
                )
                fallback_records_used.add(record_rel)
                fallback_events.append(
                    {
                        "file": record_rel,
                        "directory": directory,
                        "resolved_github_full_name": resolution.full_name,
                        "source_used": resolution.source,
                        "reason": "no_resolvable_local_self_match",
                    }
                )
            else:
                raise BackfillError(f"Could not resolve identity for {path}")

        resolution_by_path[relative(path)] = resolution

    unexpected_fallbacks = fallback_records_used - ALLOWED_MASTER_FALLBACK
    if unexpected_fallbacks:
        raise BackfillError(f"Unexpected fallback usage: {sorted(unexpected_fallbacks)}")

    return resolution_by_path, fallback_events


def apply_updates(
    yaml_rt: YAML,
    file_path: Path,
    resolution: Resolution,
    shard: str,
    as_of: str,
    conflict_events: list[dict[str, Any]],
) -> None:
    payload = parse_record_safe(yaml_rt, file_path)

    identity = {
        "node_id": f"repo::{resolution.full_name}",
        "github_full_name": resolution.full_name,
        "html_url": f"https://github.com/{resolution.full_name}",
        "source": shard,
        "provenance": {
            "shard": shard,
            "source_file": relative(file_path),
            "as_of": as_of,
        },
    }

    for key in ("node_id", "github_full_name", "html_url", "source"):
        previous = payload.get(key)
        expected = identity[key]
        if previous is not None and previous != expected:
            conflict_events.append(
                {
                    "file": relative(file_path),
                    "field": key,
                    "old_value": previous,
                    "new_value": expected,
                    "source_used": resolution.source,
                    "action": "override",
                }
            )

    previous_prov = payload.get("provenance")
    if previous_prov is not None and previous_prov != identity["provenance"]:
        conflict_events.append(
            {
                "file": relative(file_path),
                "field": "provenance",
                "old_value": previous_prov,
                "new_value": identity["provenance"],
                "source_used": resolution.source,
                "action": "override",
            }
        )

    insert_identity_fields(payload, identity)

    with file_path.open("w", encoding="utf-8") as handle:
        yaml_rt.dump(payload, handle)


def write_yaml(path: Path, payload: dict[str, Any]) -> None:
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)
    with path.open("w", encoding="utf-8") as handle:
        yaml.dump(payload, handle)


def generate_reports(
    yaml_safe: YAML,
    scope_paths: list[Path],
    fallback_events: list[dict[str, Any]],
    conflict_events: list[dict[str, Any]],
    generated_at_utc: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    coverage_by_shard_and_artifact: dict[str, dict[str, Any]] = {
        "llm_repos": {
            "repos": {"scoped_records": 0, "required_field_presence_counts": defaultdict(int), "required_field_coverage_pct": {}},
            "deep": {"scoped_records": 0, "required_field_presence_counts": defaultdict(int), "required_field_coverage_pct": {}},
        },
        "ssh_repos": {
            "repos": {"scoped_records": 0, "required_field_presence_counts": defaultdict(int), "required_field_coverage_pct": {}},
            "deep": {"scoped_records": 0, "required_field_presence_counts": defaultdict(int), "required_field_coverage_pct": {}},
        },
    }

    missing_required_fields: list[dict[str, Any]] = []
    malformed_identity_fields: list[dict[str, Any]] = []
    provenance_errors: list[dict[str, Any]] = []

    node_id_entries: dict[str, list[dict[str, str]]] = defaultdict(list)

    records_with_all_required_fields = 0

    for path in scope_paths:
        shard = path.parts[0]
        artifact_type = path.parts[2]
        payload = yaml_safe.load(path.read_text(encoding="utf-8")) or {}

        cov = coverage_by_shard_and_artifact[shard][artifact_type]
        cov["scoped_records"] += 1

        missing = record_missing_fields(payload)
        if missing:
            missing_required_fields.append(
                {
                    "file": relative(path),
                    "shard": shard,
                    "artifact_type": artifact_type,
                    "missing_fields": missing,
                }
            )
        else:
            records_with_all_required_fields += 1

        for field in REQUIRED_FIELDS:
            if field in payload:
                cov["required_field_presence_counts"][field] += 1

        node_id = payload.get("node_id")
        if isinstance(node_id, str):
            node_id_entries[node_id].append(
                {
                    "file": relative(path),
                    "artifact_type": artifact_type,
                    "shard": shard,
                    "github_full_name": str(payload.get("github_full_name", "")),
                }
            )

        malformed, prov_errors = audit_identity(path, payload, shard)
        if malformed:
            malformed_identity_fields.append(
                {
                    "file": relative(path),
                    "shard": shard,
                    "artifact_type": artifact_type,
                    "malformed_fields": sorted(set(malformed)),
                }
            )
        if prov_errors:
            provenance_errors.append(
                {
                    "file": relative(path),
                    "shard": shard,
                    "artifact_type": artifact_type,
                    "provenance_errors": sorted(set(prov_errors)),
                }
            )

    duplicates: list[dict[str, Any]] = []
    for node_id, entries in sorted(node_id_entries.items()):
        by_artifact = defaultdict(int)
        github_names = set()
        files = []
        for entry in entries:
            by_artifact[entry["artifact_type"]] += 1
            github_names.add(entry["github_full_name"])
            files.append(entry["file"])

        # A valid linked pair is at most one repos + one deep with same github_full_name.
        has_conflict = (
            len(github_names) > 1
            or by_artifact["repos"] > 1
            or by_artifact["deep"] > 1
            or len(entries) > 2
        )
        if has_conflict:
            duplicates.append(
                {
                    "node_id": node_id,
                    "files": sorted(files),
                    "count": len(entries),
                    "distinct_github_full_names": sorted(name for name in github_names if name),
                }
            )

    for shard in coverage_by_shard_and_artifact:
        for artifact in coverage_by_shard_and_artifact[shard]:
            cov = coverage_by_shard_and_artifact[shard][artifact]
            scoped = cov["scoped_records"]
            presence_counts = dict(cov["required_field_presence_counts"])
            cov["required_field_presence_counts"] = presence_counts
            cov["required_field_coverage_pct"] = {
                field: round((presence_counts.get(field, 0) / scoped) * 100, 2) if scoped else 0.0
                for field in REQUIRED_FIELDS
            }

    total_records = len(scope_paths)
    overall_pct = round((records_with_all_required_fields / total_records) * 100, 2) if total_records else 0.0

    gate_summary = {
        "identity_field_coverage_100pct": records_with_all_required_fields == total_records,
        "duplicate_node_id_zero": len(duplicates) == 0,
        "malformed_identity_fields_zero": len(malformed_identity_fields) == 0,
        "provenance_requirements_met": len(provenance_errors) == 0,
        "gate_ready": (
            records_with_all_required_fields == total_records
            and len(duplicates) == 0
            and len(malformed_identity_fields) == 0
            and len(provenance_errors) == 0
        ),
    }

    coverage_report = {
        "artifact_type": "ws2_identity_coverage_report",
        "generated_at_utc": generated_at_utc,
        "contract_version": CONTRACT_VERSION,
        "scope": {
            "definition": (
                "All shard repo and deep YAML records "
                "(llm_repos/knowledge/{repos,deep}, ssh_repos/knowledge/{repos,deep})"
            ),
            "total_records": total_records,
            "shard_record_counts": {
                "llm_repos": {
                    "repos": coverage_by_shard_and_artifact["llm_repos"]["repos"]["scoped_records"],
                    "deep": coverage_by_shard_and_artifact["llm_repos"]["deep"]["scoped_records"],
                },
                "ssh_repos": {
                    "repos": coverage_by_shard_and_artifact["ssh_repos"]["repos"]["scoped_records"],
                    "deep": coverage_by_shard_and_artifact["ssh_repos"]["deep"]["scoped_records"],
                },
            },
        },
        "required_identity_fields": REQUIRED_FIELDS,
        "coverage_by_shard_and_artifact": coverage_by_shard_and_artifact,
        "overall": {
            "records_with_all_required_fields": records_with_all_required_fields,
            "records_with_all_required_fields_pct": overall_pct,
            "duplicate_node_id_count": len(duplicates),
            "malformed_field_count": len(malformed_identity_fields),
            "provenance_error_count": len(provenance_errors),
        },
        "gate_evaluation": gate_summary,
    }

    mismatch_report = {
        "artifact_type": "ws2_identity_mismatch_report",
        "generated_at_utc": generated_at_utc,
        "contract_version": CONTRACT_VERSION,
        "summary": {
            "total_records_scanned": total_records,
            "records_missing_required_fields": len(missing_required_fields),
            "malformed_identity_fields": len(malformed_identity_fields),
            "provenance_errors": len(provenance_errors),
            "duplicate_node_ids": len(duplicates),
            "fallback_mappings_used": len(fallback_events),
            "conflict_overrides": len(conflict_events),
        },
        "missing_required_fields": missing_required_fields,
        "malformed_identity_fields": malformed_identity_fields,
        "provenance_errors": provenance_errors,
        "duplicate_node_ids": duplicates,
        "fallback_mappings": fallback_events,
        "conflict_overrides": conflict_events,
        "gate_ready_summary": gate_summary,
    }

    return coverage_report, mismatch_report


def main() -> int:
    parser = argparse.ArgumentParser(description="WS2 identity backfill")
    parser.add_argument("--workspace-root", default=".", help="workspace root")
    args = parser.parse_args()

    root = Path(args.workspace_root).resolve()
    if not root.exists():
        raise BackfillError(f"Workspace root does not exist: {root}")

    # Keep behavior deterministic with UTC date stamp for this execution day.
    now_utc = dt.datetime.now(dt.timezone.utc)
    generated_at_utc = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    as_of_value = now_utc.strftime("%Y-%m-%d")

    yaml_rt = YAML(typ="rt")
    yaml_rt.preserve_quotes = True
    yaml_rt.width = 4096
    yaml_rt.indent(mapping=2, sequence=4, offset=2)
    yaml_rt.allow_duplicate_keys = True

    yaml_safe = YAML(typ="safe")
    yaml_safe.allow_duplicate_keys = True

    shallow_paths = sorted(
        list(root.glob("llm_repos/knowledge/repos/*.yaml"))
        + list(root.glob("ssh_repos/knowledge/repos/*.yaml"))
    )
    deep_paths = sorted(
        list(root.glob("llm_repos/knowledge/deep/*.yaml"))
        + list(root.glob("ssh_repos/knowledge/deep/*.yaml"))
    )
    scope_paths = shallow_paths + deep_paths

    if len(scope_paths) != 96:
        raise BackfillError(
            f"Expected 96 in-scope records, found {len(scope_paths)}. Stop for escalation."
        )

    fallback_map = load_master_fallback_map(root / "master_repo_list.yaml")
    llm_manifest_map = load_llm_manifest_map(root / "llm_repos/repos.yaml")
    resolution_by_shallow, fallback_events = build_resolution_map(
        yaml_safe,
        shallow_paths,
        root,
        llm_manifest_map,
        fallback_map,
    )

    # Link deep records to shallow records by deterministic normalized stem.
    shallow_by_key: dict[tuple[str, str], str] = {}
    for shallow_path in shallow_paths:
        key = (shallow_path.relative_to(root).parts[0], norm_token(shallow_path.stem))
        rel = relative(shallow_path.relative_to(root))
        shallow_by_key[key] = rel

    deep_to_shallow: dict[str, str] = {}
    for deep_path in deep_paths:
        key = (deep_path.relative_to(root).parts[0], norm_token(deep_path.stem))
        rel_deep = relative(deep_path.relative_to(root))
        linked = shallow_by_key.get(key)
        if not linked:
            raise BackfillError(
                f"Unable to link deep record to shallow record: {rel_deep}. Stop for escalation."
            )
        deep_to_shallow[rel_deep] = linked

    # Precompute canonical node ids and hard-block on duplicates before writing.
    canonical_node_to_files: dict[str, list[str]] = defaultdict(list)
    for shallow_rel, resolution in resolution_by_shallow.items():
        node_id = f"repo::{resolution.full_name}"
        canonical_node_to_files[node_id].append(shallow_rel)

    for deep_rel, shallow_rel in deep_to_shallow.items():
        resolution = resolution_by_shallow[shallow_rel]
        node_id = f"repo::{resolution.full_name}"
        canonical_node_to_files[node_id].append(deep_rel)

    duplicate_candidates = {
        node_id: files
        for node_id, files in canonical_node_to_files.items()
        if len(files) > 2  # one shallow + one deep expected per repo
    }
    if duplicate_candidates:
        raise BackfillError(
            "Duplicate node_id detected after canonicalization: "
            f"{duplicate_candidates}. D4 strict block triggered."
        )

    conflict_events: list[dict[str, Any]] = []

    # Apply updates shallow first.
    for shallow_path in shallow_paths:
        rel = relative(shallow_path.relative_to(root))
        resolution = resolution_by_shallow[rel]
        shard = shallow_path.relative_to(root).parts[0]
        apply_updates(
            yaml_rt=yaml_rt,
            file_path=shallow_path,
            resolution=resolution,
            shard=shard,
            as_of=as_of_value,
            conflict_events=conflict_events,
        )

    # Apply updates deep via linked shallow identity.
    for deep_path in deep_paths:
        rel = relative(deep_path.relative_to(root))
        linked_shallow = deep_to_shallow[rel]
        resolution = resolution_by_shallow[linked_shallow]
        shard = deep_path.relative_to(root).parts[0]
        apply_updates(
            yaml_rt=yaml_rt,
            file_path=deep_path,
            resolution=resolution,
            shard=shard,
            as_of=as_of_value,
            conflict_events=conflict_events,
        )

    # Regenerate reports from written state.
    coverage_report, mismatch_report = generate_reports(
        yaml_safe=yaml_safe,
        scope_paths=[path.relative_to(root) for path in scope_paths],
        fallback_events=fallback_events,
        conflict_events=conflict_events,
        generated_at_utc=generated_at_utc,
    )

    # Re-check duplicate node_id from written data (hard block).
    if mismatch_report["summary"]["duplicate_node_ids"] != 0:
        raise BackfillError("Duplicate node_id detected post-write. D4 strict block triggered.")

    reports_dir = root / "reports/ws2_identity"
    reports_dir.mkdir(parents=True, exist_ok=True)
    write_yaml(reports_dir / "coverage.yaml", coverage_report)
    write_yaml(reports_dir / "mismatch_report.yaml", mismatch_report)

    print("WS2 identity backfill complete")
    print(f"generated_at_utc={generated_at_utc}")
    print(f"as_of={as_of_value}")
    print(f"records={len(scope_paths)}")
    print(f"fallback_mappings={len(fallback_events)}")
    print(f"conflict_overrides={len(conflict_events)}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BackfillError as exc:
        print(f"WS2_BACKFILL_ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
