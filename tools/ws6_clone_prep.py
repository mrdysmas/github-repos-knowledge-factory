#!/usr/bin/env python3
"""WS6 clone prep: acquire repo source code before deep file generation.

Reads the WS5 input manifest, checks repo sizes via the GitHub API,
clones qualifying repos into a working directory, and writes a clone
manifest that WS6 deep file generation agents use to locate source code.

Reports:
- reports/ws6_clone_prep/<batch_id>_clones.yaml
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
    import json as _json
except ImportError:
    pass  # stdlib — always available


def load_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    if not manifest_path.exists():
        print(f"ERROR: manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)
    with manifest_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "repos" not in data:
        print(f"ERROR: manifest missing 'repos' key: {manifest_path}", file=sys.stderr)
        sys.exit(1)
    return data["repos"]


def github_repo_size_kb(
    full_name: str,
    token: str | None = None,
) -> int | None:
    """Return repo size in KB from the GitHub API, or None on failure."""
    url = f"https://api.github.com/repos/{full_name}"
    req = Request(url)
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "ws6-clone-prep")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urlopen(req, timeout=15) as resp:
            body = _json.loads(resp.read().decode("utf-8"))
            return body.get("size")
    except (HTTPError, URLError, OSError, ValueError) as exc:
        print(f"  WARNING: GitHub API failed for {full_name}: {exc}")
        return None


def clone_repo(full_name: str, dest: Path) -> bool:
    """Shallow-clone a repo. Returns True on success."""
    url = f"https://github.com/{full_name}"
    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            capture_output=True,
            text=True,
            check=False,
            timeout=300,
        )
        if result.returncode != 0:
            print(f"  ERROR: git clone failed for {full_name}: {result.stderr.strip()}")
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"  ERROR: git clone timed out for {full_name}")
        return False


def is_valid_git_repo(path: Path) -> bool:
    return (path / ".git").is_dir()


def run(
    workspace_root: str,
    manifest_path: str,
    clone_workdir: str,
    size_limit_mb: int,
    batch_id: str,
    cleanup: bool,
    force_large: bool,
    github_token: str | None,
) -> int:
    ws_root = Path(workspace_root).resolve()
    manifest_arg = Path(manifest_path)
    manifest = manifest_arg if manifest_arg.is_absolute() else (ws_root / manifest_arg).resolve()
    workdir_arg = Path(clone_workdir)
    workdir = workdir_arg if workdir_arg.is_absolute() else (ws_root / workdir_arg).resolve()
    report_dir = ws_root / "reports" / "ws6_clone_prep"

    repos = load_manifest(manifest)
    workdir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    clone_entries: list[dict[str, Any]] = []
    repos_cloned = 0
    repos_skipped = 0
    repos_failed = 0

    # Phase 1: size check — halt before any cloning if oversized
    for entry in repos:
        full_name = entry.get("github_full_name", "")
        local_cache = entry.get("local_cache_dir")
        if local_cache is not None:
            continue  # will be skipped, no size concern

        size_kb = github_repo_size_kb(full_name, token=github_token)
        if size_kb is not None:
            size_mb = size_kb / 1024
            if size_mb > size_limit_mb and not force_large:
                print(
                    f"\nSIZE LIMIT EXCEEDED: {full_name} is {size_mb:.0f} MB "
                    f"(limit: {size_limit_mb} MB).\n"
                    f"To proceed, re-run with --force-large or remove the repo "
                    f"from the manifest."
                )
                return 2

    # Phase 2: clone
    for entry in repos:
        full_name = entry.get("github_full_name", "")
        local_cache = entry.get("local_cache_dir")
        owner_repo = full_name.replace("/", "__")
        dest = workdir / owner_repo

        if local_cache is not None:
            print(f"  SKIP {full_name}: local_cache_dir already set")
            clone_entries.append({
                "github_full_name": full_name,
                "local_path": str(dest),
                "size_kb": None,
                "cloned": False,
                "skip_reason": "local_cache_dir_set",
            })
            repos_skipped += 1
            continue

        size_kb = github_repo_size_kb(full_name, token=github_token)

        if dest.exists() and is_valid_git_repo(dest):
            print(f"  SKIP {full_name}: already cloned at {dest}")
            clone_entries.append({
                "github_full_name": full_name,
                "local_path": str(dest),
                "size_kb": size_kb,
                "cloned": False,
                "skip_reason": "already_cloned",
            })
            repos_skipped += 1
            continue

        print(f"  CLONE {full_name} → {dest}")
        ok = clone_repo(full_name, dest)
        if ok:
            clone_entries.append({
                "github_full_name": full_name,
                "local_path": str(dest),
                "size_kb": size_kb,
                "cloned": True,
                "skip_reason": None,
            })
            repos_cloned += 1
        else:
            clone_entries.append({
                "github_full_name": full_name,
                "local_path": str(dest),
                "size_kb": size_kb,
                "cloned": False,
                "skip_reason": "clone_failed",
            })
            repos_failed += 1

    # Write clone manifest
    clone_manifest = {
        "batch_id": batch_id,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "clone_workdir": str(workdir),
        "repos": clone_entries,
    }
    report_path = report_dir / f"{batch_id}_clones.yaml"
    with report_path.open("w", encoding="utf-8") as f:
        yaml.dump(clone_manifest, f, default_flow_style=False, sort_keys=False)

    # Cleanup if requested
    if cleanup:
        import shutil
        for entry in clone_entries:
            if entry["cloned"]:
                p = Path(entry["local_path"])
                if p.exists():
                    shutil.rmtree(p)
                    print(f"  CLEANUP: removed {p}")

    gate_ready = repos_failed == 0

    # Summary block
    print(f"""
WS6_CLONE_PREP_SUMMARY
  batch_id: {batch_id}
  manifest: {manifest}
  clone_workdir: {workdir}
  repos_total: {len(repos)}
  repos_cloned: {repos_cloned}
  repos_skipped: {repos_skipped}
  repos_failed: {repos_failed}
  size_limit_mb: {size_limit_mb}
  report: {report_path}
  gate_ready: {str(gate_ready).lower()}""")

    return 1 if repos_failed > 0 else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="WS6 clone prep: acquire repo source code before deep file generation.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--workspace-root", default=".", help="Repo root directory")
    parser.add_argument(
        "--manifest",
        default="inputs/ws5/ws5_input_manifest.yaml",
        help="Path to WS5 input manifest (relative to workspace root)",
    )
    parser.add_argument(
        "--clone-workdir",
        default="workspace/clones",
        help="Directory for cloned repos",
    )
    parser.add_argument(
        "--size-limit-mb",
        type=int,
        default=500,
        help="Halt before cloning repos larger than this (MB)",
    )
    parser.add_argument("--batch-id", required=True, help="Batch identifier for output report")
    parser.add_argument("--cleanup", action="store_true", help="Remove clones after writing manifest")
    parser.add_argument("--force-large", action="store_true", help="Skip size confirmation for oversized repos")
    parser.add_argument(
        "--github-token",
        default=None,
        help="GitHub personal access token for API requests (avoids 60 req/hr rate limit)",
    )
    args = parser.parse_args()

    token = args.github_token or os.environ.get("GITHUB_TOKEN")

    return run(
        workspace_root=args.workspace_root,
        manifest_path=args.manifest,
        clone_workdir=args.clone_workdir,
        size_limit_mb=args.size_limit_mb,
        batch_id=args.batch_id,
        cleanup=args.cleanup,
        force_large=args.force_large,
        github_token=token,
    )


if __name__ == "__main__":
    raise SystemExit(main())
