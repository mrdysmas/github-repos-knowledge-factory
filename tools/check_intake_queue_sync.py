#!/usr/bin/env python3
"""Check intake preflight invariants.

Current strict checks:
- Queue sync: inputs/intake/intake_queue.yaml must match generated queue.
- Domain hint validation: pilot_batch domain_hint values must be in the
  suggested_values allowlist from intake_manifest classification strategy.
- Domain hint aliases: alias_map values are accepted only when canonicalized;
  `--fix` rewrites alias values to canonical values in pilot_batch.
"""

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


def _validate_domain_hints(
    workspace_root: Path,
    intake_manifest_rel: str,
    pilot_batch_rel: str,
) -> tuple[bool, list[str], int, int, int]:
    errors: list[str] = []
    manifest_path = (workspace_root / intake_manifest_rel).resolve()
    pilot_path = (workspace_root / pilot_batch_rel).resolve()

    if not manifest_path.exists():
        return False, [f"missing intake manifest: {manifest_path}"], 0, 0, 0
    if not pilot_path.exists():
        return False, [f"missing pilot batch file: {pilot_path}"], 0, 0, 0

    manifest_payload = load_yaml(manifest_path) or {}
    pilot_payload = load_yaml(pilot_path) or {}

    if not isinstance(manifest_payload, dict):
        return False, [f"intake manifest must be a YAML mapping: {manifest_path}"], 0, 0, 0
    if not isinstance(pilot_payload, dict):
        return False, [f"pilot batch must be a YAML mapping: {pilot_path}"], 0, 0, 0

    classification = manifest_payload.get("classification_strategy")
    if not isinstance(classification, dict):
        return False, ["classification_strategy missing in intake manifest"], 0, 0, 0

    domain_hint = classification.get("domain_hint")
    if not isinstance(domain_hint, dict):
        return False, ["classification_strategy.domain_hint missing in intake manifest"], 0, 0, 0

    suggested_values = domain_hint.get("suggested_values")
    if not isinstance(suggested_values, list):
        return False, ["classification_strategy.domain_hint.suggested_values must be a list"], 0, 0, 0

    allowed_values: list[str] = []
    seen: set[str] = set()
    for idx, value in enumerate(suggested_values):
        if not isinstance(value, str) or not value.strip():
            errors.append(f"suggested_values[{idx}] must be a non-empty string")
            continue
        normalized = value.strip()
        if normalized in seen:
            errors.append(f"duplicate suggested_values entry: {normalized}")
            continue
        seen.add(normalized)
        allowed_values.append(normalized)

    if not allowed_values:
        errors.append("domain_hint suggested_values allowlist is empty")
        return False, errors, 0, 0, 0

    records = pilot_payload.get("records")
    if not isinstance(records, list):
        errors.append("pilot batch records must be a list")
        return False, errors, len(allowed_values), 0, 0

    checked_records = 0
    rewrites = 0
    allowed_set = set(allowed_values)
    alias_map_raw = domain_hint.get("alias_map")
    alias_map: dict[str, str] = {}
    if alias_map_raw is None:
        alias_map_raw = {}
    if not isinstance(alias_map_raw, dict):
        errors.append("classification_strategy.domain_hint.alias_map must be a mapping when provided")
        return False, errors, len(allowed_values), checked_records, rewrites
    for raw_alias, raw_target in sorted(alias_map_raw.items(), key=lambda item: str(item[0])):
        alias = raw_alias.strip() if isinstance(raw_alias, str) else ""
        target = raw_target.strip() if isinstance(raw_target, str) else ""
        if not alias:
            errors.append(f"domain_hint.alias_map has invalid alias key: {raw_alias!r}")
            continue
        if not target:
            errors.append(f"domain_hint.alias_map[{alias!r}] has empty target")
            continue
        if target not in allowed_set:
            errors.append(
                f"domain_hint.alias_map[{alias!r}] target '{target}' is not in suggested_values allowlist"
            )
            continue
        if alias in allowed_set:
            errors.append(
                f"domain_hint.alias_map[{alias!r}] duplicates canonical value; remove this alias entry"
            )
            continue
        alias_map[alias] = target

    if errors:
        return False, errors, len(allowed_values), checked_records, rewrites

    alias_hits: list[tuple[int, str, str, str]] = []
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"records[{idx}] must be a mapping")
            continue

        checked_records += 1
        repo_label = ""
        for key in ("github_full_name", "repo_id", "queue_id"):
            value = record.get(key)
            if isinstance(value, str) and value.strip():
                repo_label = value.strip()
                break
        if not repo_label:
            repo_label = f"records[{idx}]"

        value = record.get("domain_hint")
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{repo_label}: missing domain_hint")
            continue
        normalized = value.strip()
        if normalized in allowed_set:
            continue
        if normalized in alias_map:
            alias_hits.append((idx, repo_label, normalized, alias_map[normalized]))
            continue
        errors.append(
            f"{repo_label}: invalid domain_hint '{normalized}' "
            f"(allowed: {sorted(allowed_set)})"
        )

    for _, repo_label, alias_value, canonical_value in alias_hits:
        errors.append(
            f"{repo_label}: domain_hint alias '{alias_value}' "
            f"must be canonicalized to '{canonical_value}' (run with --fix)"
        )

    if errors:
        return False, errors, len(allowed_values), checked_records, rewrites

    return len(errors) == 0, errors, len(allowed_values), checked_records, rewrites


def _normalize_domain_hint_aliases(
    workspace_root: Path,
    intake_manifest_rel: str,
    pilot_batch_rel: str,
) -> tuple[bool, list[str], int]:
    errors: list[str] = []
    rewrites = 0
    manifest_path = (workspace_root / intake_manifest_rel).resolve()
    pilot_path = (workspace_root / pilot_batch_rel).resolve()

    manifest_payload = load_yaml(manifest_path) or {}
    pilot_payload = load_yaml(pilot_path) or {}
    if not isinstance(manifest_payload, dict) or not isinstance(pilot_payload, dict):
        return False, ["unable to normalize: manifest/pilot payload invalid"], rewrites

    classification = manifest_payload.get("classification_strategy")
    domain_hint = classification.get("domain_hint") if isinstance(classification, dict) else None
    alias_map_raw = domain_hint.get("alias_map") if isinstance(domain_hint, dict) else None
    alias_map = alias_map_raw if isinstance(alias_map_raw, dict) else {}
    if not alias_map:
        return True, errors, rewrites

    records = pilot_payload.get("records")
    if not isinstance(records, list):
        return False, ["unable to normalize: pilot records must be a list"], rewrites

    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            errors.append(f"unable to normalize: records[{idx}] must be a mapping")
            continue
        value = record.get("domain_hint")
        if not isinstance(value, str):
            continue
        normalized = value.strip()
        replacement = alias_map.get(normalized)
        if isinstance(replacement, str) and replacement.strip():
            replacement_norm = replacement.strip()
            if normalized != replacement_norm:
                record["domain_hint"] = replacement_norm
                rewrites += 1

    if errors:
        return False, errors, rewrites

    if rewrites > 0:
        write_if_changed(pilot_path, dump_yaml(pilot_payload))

    return True, errors, rewrites


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate intake queue sync + strict domain_hint allowlist compliance."
    )
    parser.add_argument("--workspace-root", default=".", help="Workspace root path.")
    parser.add_argument("--source", default="master_repo_list.yaml", help="Source catalog YAML path.")
    parser.add_argument("--master-index", default="master_index.yaml", help="Master index YAML path.")
    parser.add_argument("--queue", default="inputs/intake/intake_queue.yaml", help="Queue YAML path.")
    parser.add_argument(
        "--intake-manifest",
        default="inputs/intake/intake_manifest.yaml",
        help="Intake manifest path for domain_hint allowlist.",
    )
    parser.add_argument(
        "--pilot-batch",
        default="inputs/intake/pilot_batch.yaml",
        help="Pilot batch path containing records/domain_hint values.",
    )
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
    queue_ok = False
    queue_fixed = False

    if not queue_path.exists():
        if args.fix:
            write_if_changed(queue_path, dump_yaml(expected))
            queue_ok = True
            queue_fixed = True
        else:
            print("INTAKE_QUEUE_SYNC: FAIL (queue file missing)")
    else:
        actual = load_yaml(queue_path) or {}
        if not isinstance(actual, dict):
            if args.fix:
                write_if_changed(queue_path, dump_yaml(expected))
                queue_ok = True
                queue_fixed = True
            else:
                print("INTAKE_QUEUE_SYNC: FAIL (queue payload invalid)")
        elif drop_generated_at(actual) == drop_generated_at(expected):
            queue_ok = True
        elif args.fix:
            write_if_changed(queue_path, dump_yaml(expected))
            queue_ok = True
            queue_fixed = True
        else:
            print("INTAKE_QUEUE_SYNC: FAIL (queue out of sync)")
            print("hint: run with --fix or regenerate using build_intake_queue_from_master_repo_list.py")

    if queue_ok:
        if queue_fixed:
            print("INTAKE_QUEUE_SYNC: FIXED (queue updated)")
        else:
            print("INTAKE_QUEUE_SYNC: PASS")
        print(f"queued_count: {expected['summary']['queued_count']}")
        print(f"already_canonical_count: {expected['summary']['already_canonical_count']}")

    hints_ok, hint_errors, allowed_count, checked_records, _ = _validate_domain_hints(
        workspace_root=workspace_root,
        intake_manifest_rel=args.intake_manifest,
        pilot_batch_rel=args.pilot_batch,
    )

    if hints_ok:
        print("DOMAIN_HINT_VALIDATION: PASS")
        print(f"domain_hint_allowed_values: {allowed_count}")
        print(f"domain_hint_records_checked: {checked_records}")
    else:
        alias_fix_ok = False
        alias_fix_errors: list[str] = []
        alias_fix_rewrites = 0
        if args.fix:
            alias_fix_ok, alias_fix_errors, alias_fix_rewrites = _normalize_domain_hint_aliases(
                workspace_root=workspace_root,
                intake_manifest_rel=args.intake_manifest,
                pilot_batch_rel=args.pilot_batch,
            )
            if alias_fix_ok and alias_fix_rewrites > 0:
                # Re-run validation after canonical rewrite.
                hints_ok, hint_errors, allowed_count, checked_records, _ = _validate_domain_hints(
                    workspace_root=workspace_root,
                    intake_manifest_rel=args.intake_manifest,
                    pilot_batch_rel=args.pilot_batch,
                )
                if hints_ok:
                    print("DOMAIN_HINT_NORMALIZATION: FIXED")
                    print(f"domain_hint_rewrites: {alias_fix_rewrites}")
                    print("DOMAIN_HINT_VALIDATION: PASS")
                    print(f"domain_hint_allowed_values: {allowed_count}")
                    print(f"domain_hint_records_checked: {checked_records}")
                    return 0 if queue_ok else 2

        print("DOMAIN_HINT_VALIDATION: FAIL")
        for error in hint_errors:
            print(f"- {error}")
        if args.fix and alias_fix_errors:
            for error in alias_fix_errors:
                print(f"- {error}")

    return 0 if (queue_ok and hints_ok) else 2


if __name__ == "__main__":
    raise SystemExit(main())
