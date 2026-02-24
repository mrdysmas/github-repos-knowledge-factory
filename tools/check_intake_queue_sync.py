#!/usr/bin/env python3
"""Check whether inputs/intake/intake_queue.yaml is in sync with source files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = THIS_DIR.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from tools.build_intake_queue_from_master_repo_list import build_queue, dump_yaml, load_yaml, write_if_changed


def drop_generated_at(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.pop("generated_at_utc", None)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate intake queue sync against source catalog and master index.")
    parser.add_argument("--workspace-root", default=".", help="Workspace root path.")
    parser.add_argument("--source", default="master_repo_list.yaml", help="Source catalog YAML path.")
    parser.add_argument("--master-index", default="master_index.yaml", help="Master index YAML path.")
    parser.add_argument("--queue", default="inputs/intake/intake_queue.yaml", help="Queue YAML path.")
    parser.add_argument("--fix", action="store_true", help="Rewrite queue file when out of sync.")
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    source_path = (workspace_root / args.source).resolve()
    master_index_path = (workspace_root / args.master_index).resolve()
    queue_path = (workspace_root / args.queue).resolve()

    source_payload = load_yaml(source_path) or {}
    master_index_payload = load_yaml(master_index_path) or {}
    if not isinstance(source_payload, dict) or not isinstance(master_index_payload, dict):
        raise ValueError("Source and master index must be YAML mappings.")

    expected = build_queue(source_payload=source_payload, master_index_payload=master_index_payload)
    if not queue_path.exists():
        if args.fix:
            write_if_changed(queue_path, dump_yaml(expected))
            print("INTAKE_QUEUE_SYNC: FIXED (queue file created)")
            return 0
        print("INTAKE_QUEUE_SYNC: FAIL (queue file missing)")
        return 2

    actual = load_yaml(queue_path) or {}
    if not isinstance(actual, dict):
        if args.fix:
            write_if_changed(queue_path, dump_yaml(expected))
            print("INTAKE_QUEUE_SYNC: FIXED (queue file rewritten from invalid payload)")
            return 0
        print("INTAKE_QUEUE_SYNC: FAIL (queue payload invalid)")
        return 2

    if drop_generated_at(actual) == drop_generated_at(expected):
        print("INTAKE_QUEUE_SYNC: PASS")
        print(f"queued_count: {expected['summary']['queued_count']}")
        print(f"already_canonical_count: {expected['summary']['already_canonical_count']}")
        return 0

    if args.fix:
        write_if_changed(queue_path, dump_yaml(expected))
        print("INTAKE_QUEUE_SYNC: FIXED (queue updated)")
        print(f"queued_count: {expected['summary']['queued_count']}")
        print(f"already_canonical_count: {expected['summary']['already_canonical_count']}")
        return 0

    print("INTAKE_QUEUE_SYNC: FAIL (queue out of sync)")
    print("hint: run with --fix or regenerate using build_intake_queue_from_master_repo_list.py")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
