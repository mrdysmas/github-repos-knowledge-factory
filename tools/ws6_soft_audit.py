#!/usr/bin/env python3
"""WS6 Soft Audit — archetype coverage audit tool.

Reads knowledge.db, checks each repo against its archetype's coverage
requirements, and emits a machine-readable per-repo coverage report.

Read-only diagnostic tool. Does not modify any facts, YAML files, or pipeline state.

Usage:
    python3 tools/ws6_soft_audit.py --workspace-root .
"""

from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# Archetype configuration — add new archetypes here, nowhere else
# ---------------------------------------------------------------------------

FAMILY_PREDICATES: dict[str, list[str]] = {
    "structure":   ["has_component", "has_config_option"],
    "tasks":       ["supports_task"],
    "failures":    ["has_failure_mode"],
    "protocols":   ["uses_protocol", "exposes_api_endpoint", "has_extension_point"],
}

ARCHETYPES: dict[str, dict[str, Any]] = {
    "inference_serving": {
        "categories": ["inference_serving"],
        "required_families": ["structure", "tasks", "failures"],
        "recommended_families": ["protocols"],
        "predicate_checks": {},
    },
    "vector_database": {
        "categories": ["vector_database", "vector_databases"],
        "required_families": ["structure", "failures"],
        "recommended_families": ["tasks", "protocols"],
        "predicate_checks": {},
    },
    "tunneling": {
        "categories": ["tunneling", "vpn_mesh", "network_infrastructure"],
        "required_families": ["structure", "protocols"],
        "recommended_families": ["failures", "tasks"],
        "predicate_checks": {
            # Family presence via has_extension_point alone does not satisfy this archetype.
            # At least one uses_protocol fact is required.
            "protocols": "uses_protocol",
        },
    },
    "agent_framework": {
        "categories": ["agent_framework", "agent_frameworks", "agent_orchestration"],
        "required_families": ["structure", "tasks"],
        "recommended_families": ["failures", "protocols"],
        "predicate_checks": {},
    },
    "agent_cli": {
        "categories": ["agent_cli"],
        "required_families": ["structure", "tasks", "failures"],
        "recommended_families": ["protocols"],
        "predicate_checks": {},
    },
    "rag_frameworks": {
        "categories": ["rag_frameworks"],
        "required_families": ["structure", "tasks", "failures"],
        "recommended_families": ["protocols"],
        "predicate_checks": {},
    },
    "remote_access": {
        "categories": ["remote_access"],
        "required_families": ["structure", "tasks", "protocols"],
        "recommended_families": ["failures"],
        "predicate_checks": {
            # Extension points alone do not satisfy this archetype.
            # At least one uses_protocol fact is required.
            "protocols": "uses_protocol",
        },
    },
    "structured_outputs": {
        "categories": ["structured_outputs"],
        "required_families": ["structure", "tasks", "protocols"],
        "recommended_families": ["failures"],
        "predicate_checks": {},
    },
}

# ---------------------------------------------------------------------------
# Recognized sections (from contracts/deep_narrative_contract.md v2.0)
# Any source_section not in this set is flagged as unmapped.
# ---------------------------------------------------------------------------

RECOGNIZED_SECTIONS: set[str] = {
    # Identity keys (skipped by WS6)
    "name", "node_id", "github_full_name", "html_url", "source", "provenance",
    # Ignored keys (skipped by WS6)
    "sparse", "directory", "category", "summary", "description", "notes", "metadata",
    # Structure family
    "architecture", "configuration", "cli_arguments", "environment",
    "environment_variables", "key_features", "key_files", "core_modules",
    "tech_stack", "technology_stack", "ports", "type", "primary_language", "languages",
    # Tasks family
    "commands", "cli_commands", "common_tasks", "procedures", "quick_reference",
    # Failures family
    "troubleshooting",
    # Protocols & Integrations family
    "supported_protocols", "vpn_protocols", "api_protocols", "api_surface",
    "api_structure", "integrations", "extension_points", "sdk_usage", "cross_references",
    # Cross-cutting
    "code_patterns", "implementation_patterns", "testing",
    # Remaining recognized
    "key_sections", "content_coverage", "supplementary_files", "related_repos",
}

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def connect_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def get_all_repos(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT node_id, name, github_full_name, category FROM repos ORDER BY category, name"
    ).fetchall()


def has_facts_for_predicates(conn: sqlite3.Connection, node_id: str, predicates: list[str]) -> bool:
    placeholders = ",".join("?" * len(predicates))
    row = conn.execute(
        f"SELECT COUNT(*) FROM facts WHERE node_id = ? AND predicate IN ({placeholders})",
        [node_id, *predicates],
    ).fetchone()
    return row[0] > 0


def has_fact_for_predicate(conn: sqlite3.Connection, node_id: str, predicate: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) FROM facts WHERE node_id = ? AND predicate = ?",
        (node_id, predicate),
    ).fetchone()
    return row[0] > 0


def get_total_facts(conn: sqlite3.Connection, node_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM facts WHERE node_id = ?",
        (node_id,),
    ).fetchone()
    return row[0]


def get_source_sections(conn: sqlite3.Connection, node_id: str) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT source_section FROM facts WHERE node_id = ? AND source_section IS NOT NULL",
        (node_id,),
    ).fetchall()
    return [row[0] for row in rows]


# ---------------------------------------------------------------------------
# Archetype matching
# ---------------------------------------------------------------------------


def match_archetype(category: str | None) -> tuple[str | None, dict[str, Any] | None]:
    """Return (archetype_name, archetype_config) or (None, None) if unmatched."""
    if not category:
        return None, None
    category = category.strip()
    for name, config in ARCHETYPES.items():
        if category in config["categories"]:
            return name, config
    return None, None


# ---------------------------------------------------------------------------
# Per-repo audit
# ---------------------------------------------------------------------------


def audit_repo(
    conn: sqlite3.Connection,
    node_id: str,
    github_full_name: str,
    category: str | None,
    archetype_filter: str | None,
) -> dict[str, Any]:
    archetype_name, archetype_config = match_archetype(category)

    # If filtering by archetype, skip non-matching repos but still emit an unmatched record
    if archetype_filter and archetype_name != archetype_filter:
        return {
            "repo": github_full_name,
            "node_id": node_id,
            "category": category,
            "archetype": archetype_name,
            "families_present": [],
            "families_missing": [],
            "predicate_check_failures": [],
            "behavioral_coverage": "unmatched",
            "flags": [],
            "_skip": True,
        }

    total_facts = get_total_facts(conn, node_id)
    flags: list[str] = []

    # Unmapped section check (all repos)
    unmapped: list[str] = []
    for section in get_source_sections(conn, node_id):
        if section not in RECOGNIZED_SECTIONS:
            unmapped.append(section)
    if unmapped:
        for sec in sorted(unmapped):
            flags.append(f"unmapped source_section '{sec}' — produced facts but section not in contract")

    if archetype_name is None:
        if total_facts == 0:
            flags.append("no facts extracted — deep file may be missing or empty")
        return {
            "repo": github_full_name,
            "node_id": node_id,
            "category": category,
            "archetype": None,
            "families_present": [],
            "families_missing": [],
            "predicate_check_failures": [],
            "behavioral_coverage": "unmatched",
            "flags": flags,
        }

    if total_facts == 0:
        flags.append("no facts extracted — deep file may be missing or empty")

    # Family coverage check
    families_present: list[str] = []
    families_missing: list[str] = []
    predicate_check_failures: list[str] = []

    required_families: list[str] = archetype_config["required_families"]
    predicate_checks: dict[str, str] = archetype_config.get("predicate_checks", {})

    # Check all families for presence (required ones drive coverage classification)
    for family, predicates in FAMILY_PREDICATES.items():
        if has_facts_for_predicates(conn, node_id, predicates):
            families_present.append(family)
        elif family in required_families:
            families_missing.append(family)
            flags.append(
                f"required family '{family}' absent — no {'/'.join(predicates)} facts"
            )

    # Predicate-level checks (beyond family presence)
    for family, required_predicate in predicate_checks.items():
        if family in families_present:
            if not has_fact_for_predicate(conn, node_id, required_predicate):
                predicate_check_failures.append(required_predicate)
                flags.append(
                    f"predicate check failed — family '{family}' present but no '{required_predicate}' facts"
                    f" (archetype '{archetype_name}' requires at least one)"
                )

    # Classify
    is_thin = bool(families_missing) or bool(predicate_check_failures)
    behavioral_coverage = "thin" if is_thin else "full"

    return {
        "repo": github_full_name,
        "node_id": node_id,
        "category": category,
        "archetype": archetype_name,
        "families_present": families_present,
        "families_missing": families_missing,
        "predicate_check_failures": predicate_check_failures,
        "behavioral_coverage": behavioral_coverage,
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# Report assembly
# ---------------------------------------------------------------------------


def build_report(
    records: list[dict[str, Any]],
    archetype_filter: str | None,
    include_full: bool,
    generated_at: str,
) -> dict[str, Any]:
    total_repos = len(records)

    archetypes_checked = list(ARCHETYPES.keys()) if not archetype_filter else [archetype_filter]

    repos_matched = sum(1 for r in records if r["archetype"] is not None)
    repos_unmatched = sum(1 for r in records if r["behavioral_coverage"] == "unmatched")
    repos_thin = sum(1 for r in records if r["behavioral_coverage"] == "thin")
    repos_full = sum(1 for r in records if r["behavioral_coverage"] == "full")

    # Summary by archetype
    summary_by_archetype: dict[str, Any] = {}
    for arch_name in archetypes_checked:
        arch_records = [r for r in records if r["archetype"] == arch_name]
        thin_repos = [r["repo"] for r in arch_records if r["behavioral_coverage"] == "thin"]
        summary_by_archetype[arch_name] = {
            "total": len(arch_records),
            "full": sum(1 for r in arch_records if r["behavioral_coverage"] == "full"),
            "thin": len(thin_repos),
            "thin_repos": thin_repos,
        }

    # Coverage records (thin + unmatched by default; full only with --include-full)
    coverage_records = [
        {k: v for k, v in r.items() if not k.startswith("_")}
        for r in records
        if r["behavioral_coverage"] in ("thin", "unmatched") or include_full
    ]

    return {
        "audit_metadata": {
            "generated_at": generated_at,
            "total_repos": total_repos,
            "archetypes_checked": archetypes_checked,
            "repos_matched": repos_matched,
            "repos_unmatched": repos_unmatched,
            "repos_thin": repos_thin,
            "repos_full": repos_full,
        },
        "summary_by_archetype": summary_by_archetype,
        "coverage_records": coverage_records,
    }


# ---------------------------------------------------------------------------
# stdout summary
# ---------------------------------------------------------------------------


def print_summary(
    records: list[dict[str, Any]],
    report_path: Path,
    archetype_filter: str | None,
) -> None:
    total = len(records)
    print(f"\nSoft audit complete — {total} repos checked.")
    print()
    print("Archetype coverage:")

    archetypes_checked = list(ARCHETYPES.keys()) if not archetype_filter else [archetype_filter]
    for arch_name in archetypes_checked:
        arch_records = [r for r in records if r["archetype"] == arch_name]
        full_count = sum(1 for r in arch_records if r["behavioral_coverage"] == "full")
        thin_count = sum(1 for r in arch_records if r["behavioral_coverage"] == "thin")
        total_arch = len(arch_records)
        thin_note = f"  ({thin_count} thin)" if thin_count else ""
        print(f"  {arch_name:<20} {full_count}/{total_arch} full{thin_note}")

    unmatched_count = sum(1 for r in records if r["behavioral_coverage"] == "unmatched")
    print(f"  {'unmatched':<20} {unmatched_count} repos (no archetype defined)")

    thin_records = [r for r in records if r["behavioral_coverage"] == "thin"]
    if thin_records:
        print()
        print("Thin repos:")
        by_arch: dict[str, list[dict[str, Any]]] = {}
        for r in thin_records:
            by_arch.setdefault(r["archetype"] or "unknown", []).append(r)
        for arch_name, arch_thin in by_arch.items():
            print(f"  {arch_name}:")
            for r in arch_thin:
                missing = ", ".join(r["families_missing"]) if r["families_missing"] else "(none — predicate check failed)"
                print(f"    {r['repo']} — missing: {missing}")

    print()
    print(f"Report written to: {report_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="WS6 Soft Audit — archetype coverage audit for knowledge.db repos."
    )
    parser.add_argument("--workspace-root", default=".", help="Workspace root path.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for report (default: <workspace-root>/reports/ws6_soft_audit/).",
    )
    parser.add_argument(
        "--db",
        default=None,
        help="Path to knowledge.db (default: <workspace-root>/knowledge.db).",
    )
    parser.add_argument(
        "--archetype",
        default=None,
        choices=list(ARCHETYPES.keys()),
        help="Audit only one archetype (default: all).",
    )
    parser.add_argument(
        "--include-full",
        action="store_true",
        help="Include full-coverage repos in coverage_records (default: thin/unmatched only).",
    )
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()

    db_path = Path(args.db).resolve() if args.db else workspace_root / "knowledge.db"
    if not db_path.exists():
        print(
            f"ERROR: knowledge.db not found at {db_path}. "
            "Run ws7_read_model_compiler.py first."
        )
        return 1

    output_dir = (
        Path(args.output_dir).resolve()
        if args.output_dir
        else workspace_root / "reports" / "ws6_soft_audit"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    generated_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    conn = connect_db(db_path)
    try:
        repos = get_all_repos(conn)

        records: list[dict[str, Any]] = []
        for repo in repos:
            node_id = repo["node_id"]
            github_full_name = repo["github_full_name"] or repo["name"] or node_id
            category = repo["category"]

            record = audit_repo(
                conn=conn,
                node_id=node_id,
                github_full_name=github_full_name,
                category=category,
                archetype_filter=args.archetype,
            )

            # If filtering by archetype, skip records that don't belong
            if record.get("_skip"):
                continue

            records.append(record)

    finally:
        conn.close()

    report = build_report(
        records=records,
        archetype_filter=args.archetype,
        include_full=args.include_full,
        generated_at=generated_at,
    )

    report_filename = f"{timestamp}_audit.yaml"
    report_path = output_dir / report_filename
    latest_path = output_dir / "latest_audit.yaml"

    with report_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(report, fh, sort_keys=False, allow_unicode=True, default_flow_style=False)

    # Write latest_audit.yaml as a copy (avoids symlink portability issues)
    shutil.copy2(report_path, latest_path)

    print_summary(records, report_path, args.archetype)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
