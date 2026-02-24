#!/usr/bin/env python3
"""Build a deterministic intake queue from master_repo_list.yaml.

Goal:
- Treat master_repo_list.yaml as the source backlog.
- Avoid keeping all clones locally.
- Mark entries as queued/already_canonical against master_index.yaml.
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


FULL_NAME_PATTERN = re.compile(r"^[^/]+/[^/]+$")
GITHUB_URL_PATTERN = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


def parse_full_name_from_url(url: str) -> str:
    match = GITHUB_URL_PATTERN.match(url.strip())
    if not match:
        return ""
    owner, repo = match.group(1), match.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    full_name = f"{owner}/{repo}"
    return full_name if FULL_NAME_PATTERN.match(full_name) else ""


def infer_target_shard_hint(categories: set[str]) -> str:
    if "llm_repos" in categories:
        return "llm_repos"
    if "ssh_repos" in categories or "go_repos" in categories:
        return "ssh_repos"
    return "undecided"


def normalize_full_name(value: str) -> str:
    return value.strip().lower()


def build_queue(
    source_payload: dict[str, Any],
    master_index_payload: dict[str, Any],
) -> dict[str, Any]:
    source_rows = source_payload.get("repos")
    if not isinstance(source_rows, list):
        raise ValueError("master_repo_list.yaml missing top-level repos list")

    canonical_repos = master_index_payload.get("repos")
    canonical_set: set[str] = set()
    canonical_name_by_norm: dict[str, str] = {}
    if isinstance(canonical_repos, list):
        for row in canonical_repos:
            if not isinstance(row, dict):
                continue
            full_name = ensure_string(row.get("github_full_name"))
            if FULL_NAME_PATTERN.match(full_name):
                norm = normalize_full_name(full_name)
                canonical_set.add(norm)
                canonical_name_by_norm[norm] = full_name

    aggregate: dict[str, dict[str, Any]] = {}
    missing_url_rows = 0
    invalid_full_name_rows = 0

    for idx, row in enumerate(source_rows):
        if not isinstance(row, dict):
            continue
        github_url = ensure_string(row.get("github_url"))
        if not github_url:
            missing_url_rows += 1
            continue

        author = ensure_string(row.get("author"))
        repo_name = ensure_string(row.get("repo_name"))
        full_name = f"{author}/{repo_name}" if author and repo_name else parse_full_name_from_url(github_url)
        if not FULL_NAME_PATTERN.match(full_name):
            full_name = parse_full_name_from_url(github_url)

        if not FULL_NAME_PATTERN.match(full_name):
            invalid_full_name_rows += 1
            continue

        norm_full_name = normalize_full_name(full_name)
        item = aggregate.get(norm_full_name)
        if item is None:
            item = {
                "github_full_name": full_name,
                "html_url": github_url,
                "source_categories": set(),
                "source_local_paths": [],
                "needs_review_count": 0,
                "source_row_indexes": [],
                "normalized_full_name": norm_full_name,
            }
            aggregate[norm_full_name] = item

        category = ensure_string(row.get("category"))
        if category:
            item["source_categories"].add(category)
        local_path = ensure_string(row.get("local_path"))
        if local_path and local_path not in item["source_local_paths"]:
            item["source_local_paths"].append(local_path)
        if bool(row.get("needs_review")):
            item["needs_review_count"] += 1
        item["source_row_indexes"].append(idx)

    entries: list[dict[str, Any]] = []
    queued_count = 0
    canonical_count = 0

    for norm_full_name in sorted(aggregate):
        row = aggregate[norm_full_name]
        full_name = canonical_name_by_norm.get(norm_full_name, row["github_full_name"])
        categories = sorted(row["source_categories"])
        local_paths = sorted(row["source_local_paths"])
        canonical_status = "already_canonical" if norm_full_name in canonical_set else "queued"
        if canonical_status == "queued":
            queued_count += 1
        else:
            canonical_count += 1

        intake_status = "pending" if canonical_status == "queued" else "hold"
        recommended_action = "candidate_shallow_scan" if canonical_status == "queued" else "skip_existing_canonical"

        entries.append(
            {
                "queue_id": f"intake::{full_name}",
                "github_full_name": full_name,
                "html_url": row["html_url"],
                "canonical_status": canonical_status,
                "intake_status": intake_status,
                "recommended_action": recommended_action,
                "target_shard_hint": infer_target_shard_hint(set(categories)),
                "source_categories": categories,
                "source_local_paths": local_paths,
                "needs_review_count": int(row["needs_review_count"]),
                "source_row_indexes": sorted(row["source_row_indexes"]),
            }
        )

    return {
        "artifact_type": "intake_repo_queue",
        "contract_version": "1.0.0-intake",
        "generated_at_utc": utc_now_iso(),
        "source": {
            "catalog_file": "master_repo_list.yaml",
            "master_index_file": "master_index.yaml",
            "notes": "Queue entries are deduplicated by github_full_name.",
        },
        "summary": {
            "source_rows_total": len(source_rows),
            "source_rows_missing_github_url": missing_url_rows,
            "source_rows_invalid_full_name": invalid_full_name_rows,
            "deduped_entries_total": len(entries),
            "already_canonical_count": canonical_count,
            "queued_count": queued_count,
        },
        "policies": {
            "scan_mode_default": "shallow_first",
            "clone_strategy": "clone_on_demand",
            "deep_strategy": "priority_based",
        },
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build intake queue from master_repo_list.yaml.")
    parser.add_argument("--workspace-root", default=".", help="Workspace root path.")
    parser.add_argument("--source", default="master_repo_list.yaml", help="Source catalog YAML path.")
    parser.add_argument("--master-index", default="master_index.yaml", help="Master index YAML path.")
    parser.add_argument("--output", default="inputs/intake/intake_queue.yaml", help="Queue output YAML path.")
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    source_path = (workspace_root / args.source).resolve()
    master_index_path = (workspace_root / args.master_index).resolve()
    output_path = (workspace_root / args.output).resolve()

    source_payload = load_yaml(source_path) or {}
    if not isinstance(source_payload, dict):
        raise ValueError(f"Source payload is not mapping: {source_path.as_posix()}")

    master_index_payload = load_yaml(master_index_path) or {}
    if not isinstance(master_index_payload, dict):
        raise ValueError(f"Master index payload is not mapping: {master_index_path.as_posix()}")

    queue = build_queue(source_payload=source_payload, master_index_payload=master_index_payload)
    text = dump_yaml(queue)
    changed = write_if_changed(output_path, text)
    status = "written" if changed else "unchanged"
    print(f"queue_file: {output_path.as_posix()} ({status})")
    print(f"queued_count: {queue['summary']['queued_count']}")
    print(f"already_canonical_count: {queue['summary']['already_canonical_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
