#!/usr/bin/env python3
"""Add a new repo candidate to master_repo_list.yaml and refresh intake queue."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

THIS_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = THIS_DIR.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from tools.build_intake_queue_from_master_repo_list import build_queue, dump_yaml, load_yaml, write_if_changed


GITHUB_URL_PATTERN = re.compile(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$")
FULL_NAME_PATTERN = re.compile(r"^[^/]+/[^/]+$")


def utc_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def normalize_full_name(value: str) -> str:
    return value.strip().lower()


def parse_full_name_from_url(url: str) -> tuple[str, str]:
    match = GITHUB_URL_PATTERN.match(url.strip())
    if not match:
        raise ValueError(f"Invalid GitHub URL: {url}")
    owner, repo = match.group(1), match.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    full_name = f"{owner}/{repo}"
    if not FULL_NAME_PATTERN.match(full_name):
        raise ValueError(f"Could not parse owner/repo from URL: {url}")
    return owner, repo


def extract_existing_full_names(rows: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        author = row.get("author")
        repo_name = row.get("repo_name")
        if isinstance(author, str) and author.strip() and isinstance(repo_name, str) and repo_name.strip():
            out.add(normalize_full_name(f"{author.strip()}/{repo_name.strip()}"))
            continue

        github_url = row.get("github_url")
        if isinstance(github_url, str) and github_url.strip():
            try:
                owner, repo = parse_full_name_from_url(github_url.strip())
                out.add(normalize_full_name(f"{owner}/{repo}"))
            except ValueError:
                continue
    return out


def recalc_metadata(payload: dict[str, Any]) -> None:
    rows = payload.get("repos")
    if not isinstance(rows, list):
        payload["repos"] = []
        rows = payload["repos"]

    identified = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        github_url = row.get("github_url")
        author = row.get("author")
        repo_name = row.get("repo_name")
        if (
            isinstance(github_url, str)
            and github_url.strip()
            and isinstance(author, str)
            and author.strip()
            and isinstance(repo_name, str)
            and repo_name.strip()
        ):
            identified += 1

    total = len(rows)
    unidentified = total - identified

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        payload["metadata"] = metadata

    metadata["generated"] = utc_date()
    metadata["total_repos"] = total
    metadata["identified"] = identified
    metadata["unidentified"] = unidentified
    if "notes" not in metadata:
        metadata["notes"] = "Updated by tools/add_repo_candidate.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Add new repo candidate and refresh intake queue.")
    parser.add_argument("--workspace-root", default=".", help="Workspace root path.")
    parser.add_argument("--github-url", required=True, help="GitHub repo URL.")
    parser.add_argument("--category", default="uncat_repos", help="Candidate category label.")
    parser.add_argument("--local-path", default="", help="Optional local path if already cloned.")
    parser.add_argument("--detection-method", default="manual", help="Detection method tag.")
    parser.add_argument("--needs-review", action="store_true", help="Mark candidate as needs_review=true.")
    parser.add_argument("--notes", default="", help="Optional notes field.")
    parser.add_argument("--source", default="master_repo_list.yaml", help="Source catalog path.")
    parser.add_argument("--master-index", default="master_index.yaml", help="Master index path.")
    parser.add_argument("--queue-output", default="inputs/intake/intake_queue.yaml", help="Intake queue output path.")
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    source_path = (workspace_root / args.source).resolve()
    master_index_path = (workspace_root / args.master_index).resolve()
    queue_path = (workspace_root / args.queue_output).resolve()

    owner, repo = parse_full_name_from_url(args.github_url)
    full_name_norm = normalize_full_name(f"{owner}/{repo}")

    source_payload = load_yaml(source_path) or {}
    if not isinstance(source_payload, dict):
        raise ValueError(f"Source payload is not mapping: {source_path.as_posix()}")
    repos = source_payload.get("repos")
    if not isinstance(repos, list):
        raise ValueError("master_repo_list.yaml missing top-level repos list")

    existing = extract_existing_full_names(repos)
    if full_name_norm in existing:
        print(f"candidate_exists: {owner}/{repo}")
        print(f"source_file: {source_path.as_posix()}")
        return 2

    row: dict[str, Any] = {
        "local_path": args.local_path.strip() or None,
        "github_url": args.github_url.strip(),
        "author": owner,
        "repo_name": repo,
        "category": args.category.strip() or "uncat_repos",
        "needs_review": bool(args.needs_review),
        "detection_method": args.detection_method.strip() or "manual",
    }
    if args.notes.strip():
        row["notes"] = args.notes.strip()

    repos.append(row)
    recalc_metadata(source_payload)

    source_text = dump_yaml(source_payload)
    write_if_changed(source_path, source_text)

    master_index_payload = load_yaml(master_index_path) or {}
    if not isinstance(master_index_payload, dict):
        raise ValueError(f"Master index payload is not mapping: {master_index_path.as_posix()}")
    queue_payload = build_queue(source_payload=source_payload, master_index_payload=master_index_payload)
    queue_text = dump_yaml(queue_payload)
    write_if_changed(queue_path, queue_text)

    print(f"added_candidate: {owner}/{repo}")
    print(f"catalog_file: {source_path.as_posix()}")
    print(f"queue_file: {queue_path.as_posix()}")
    print(f"queued_count: {queue_payload['summary']['queued_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
