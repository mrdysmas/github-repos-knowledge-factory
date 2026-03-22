#!/usr/bin/env python3
"""Deduplicate (predicate, object_value) pairs in deep_facts YAML files.

Keeps the fact with highest confidence; breaks ties by preserving existing order
(first occurrence wins). Rewrites files in-place.
"""

import argparse
import sys
from pathlib import Path

import yaml


def dedup_facts(facts: list) -> tuple[list, int]:
    """Return (deduped_facts, num_removed)."""
    seen: dict[tuple, int] = {}  # (predicate, object_value) -> index of kept fact
    kept = []
    removed = 0

    for fact in facts:
        predicate = fact.get("predicate")
        object_value = fact.get("object_value")
        if predicate is None or object_value is None:
            kept.append(fact)
            continue

        key = (predicate, object_value)
        if key not in seen:
            seen[key] = len(kept)
            kept.append(fact)
        else:
            existing_idx = seen[key]
            existing_conf = kept[existing_idx].get("confidence", 0) or 0
            new_conf = fact.get("confidence", 0) or 0
            if new_conf > existing_conf:
                kept[existing_idx] = fact
            removed += 1

    return kept, removed


def process_file(path: Path, dry_run: bool = False) -> tuple[int, int]:
    """Process one YAML file. Returns (facts_before, facts_after)."""
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)

    facts = data.get("facts")
    if not isinstance(facts, list):
        return 0, 0

    before = len(facts)
    deduped, removed = dedup_facts(facts)
    after = len(deduped)

    if removed == 0:
        return before, after

    if not dry_run:
        data["facts"] = deduped
        new_text = yaml.dump(
            data,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=120,
        )
        path.write_text(new_text, encoding="utf-8")

    return before, after


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace-root",
        default=".",
        help="Repo root (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes without writing files",
    )
    args = parser.parse_args()

    deep_facts_dir = Path(args.workspace_root) / "repos/knowledge/deep_facts"
    if not deep_facts_dir.exists():
        print(f"ERROR: {deep_facts_dir} not found", file=sys.stderr)
        sys.exit(1)

    yaml_files = sorted(deep_facts_dir.glob("*.yaml"))
    total_before = 0
    total_after = 0
    changed_files = 0

    for path in yaml_files:
        before, after = process_file(path, dry_run=args.dry_run)
        total_before += before
        total_after += after
        if before != after:
            removed = before - after
            changed_files += 1
            tag = "[DRY RUN] " if args.dry_run else ""
            print(f"{tag}{path.name}: {before} → {after} facts (-{removed})")

    total_removed = total_before - total_after
    mode = "DRY RUN" if args.dry_run else "DONE"
    print(
        f"\n{mode}: {len(yaml_files)} files scanned, "
        f"{changed_files} modified, "
        f"{total_before} → {total_after} facts (-{total_removed})"
    )


if __name__ == "__main__":
    main()
