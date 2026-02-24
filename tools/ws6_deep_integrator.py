#!/usr/bin/env python3
"""WS6 deep integration spec (contract-first, no mutation).

This file is intentionally a SPEC EMITTER, not the final implementation.
It provides a single authoritative WS6 execution contract for fresh agents.

Planned WS6 role:
- Normalize shard deep artifacts into canonical deep facts.
- Enforce deep fact schema + relation mapping + evidence rules.
- Generate deterministic WS6 reports.
- Feed WS4 compiler with canonical deep-fact artifacts.

Current status:
- Spec-only. Running this script does NOT modify repository knowledge files.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


SPEC_VERSION = "1.0.0-ws6-spec"


def build_spec() -> dict[str, Any]:
    return {
        "artifact_type": "ws6_deep_integration_spec",
        "spec_version": SPEC_VERSION,
        "status": "SPEC_ONLY_NO_MUTATION",
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
            "Join deep artifacts to shallow repos by node_id.",
            "Require identity parity with shallow repo fields.",
            "Map observed deep predicates to canonical predicates.",
            "Drop or fail unknown predicates based on strict mode.",
            "Require at least one evidence row per fact.",
            "Require confidence in [0.0, 1.0] for each fact.",
        ],
        "outputs": {
            "canonical_shard_outputs": [
                "llm_repos/knowledge/deep_facts/*.yaml",
                "ssh_repos/knowledge/deep_facts/*.yaml",
            ],
            "master_output_for_ws4": "master_deep_facts.yaml",
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
            "ws6_hash_stable",
        ],
        "required_commands": [
            "python3 tools/ws1_contract_validator.py --workspace-root . --external-node-policy first_class",
            "python3 tools/trust_gates.py llm_repos/knowledge --production",
            "python3 tools/trust_gates.py ssh_repos/knowledge --production",
            "python3 tools/ws6_deep_integrator.py --workspace-root . --reports-dir reports/ws6_deep_integration --materialize-spec reports/ws6_deep_integration/spec.yaml",
            "python3 tools/ws4_master_compiler.py --workspace-root . --master-index master_index.yaml --master-graph master_graph.yaml --reports-dir reports/ws4_master_build",
        ],
        "implementation_backlog": [
            "Implement deep narrative -> fact extraction adapters.",
            "Implement canonical deep fact serializer with stable ordering.",
            "Implement mismatch report with blocking/non-blocking severity.",
            "Add ws6 unit tests under tests/ws6_deep_integration/.",
            "Extend WS4 compiler input set to ingest deep_facts/*.yaml and emit master_deep_facts.yaml.",
        ],
    }


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit WS6 deep integration execution spec.")
    parser.add_argument("--workspace-root", default=".", help="Workspace root path.")
    parser.add_argument(
        "--reports-dir",
        default="reports/ws6_deep_integration",
        help="Reserved for future WS6 report materialization path.",
    )
    parser.add_argument(
        "--materialize-spec",
        default="",
        help="Optional file path (relative to workspace root) to write spec YAML.",
    )
    parser.add_argument(
        "--print-spec",
        action="store_true",
        help="Print spec YAML to stdout (default true when --materialize-spec not set).",
    )
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    spec = build_spec()
    text = dump_yaml(spec)

    should_print = args.print_spec or not args.materialize_spec
    if should_print:
        print(text.rstrip())

    if args.materialize_spec:
        target = (workspace_root / args.materialize_spec).resolve()
        changed = write_if_changed(target, text)
        status = "written" if changed else "unchanged"
        print(f"spec_file: {target.as_posix()} ({status})")

    print(f"reports_dir: {args.reports_dir}")
    print("status: SPEC_ONLY_NO_MUTATION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
