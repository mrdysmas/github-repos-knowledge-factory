#!/usr/bin/env python3
"""WS0 trust-gates preflight for knowledge artifacts.

This script enforces three gates before downstream validation/merge work:
- G1 Parse Integrity
- G2 Status Semantic Integrity
- G3 Spec/Validator Contract Integrity
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from typing import Any

import yaml


STATUS_COMPLETE_VALUES = {"complete", "completed"}
READY_VERDICTS = {"READY_FOR_PRODUCTION", "VERIFIED_DEEP"}
REQUIRED_SCOPE_TOKENS = {
    "index.yaml",
    "graph.yaml",
    "progress.yaml",
    "audit-progress.yaml",
    "repos/*.yaml",
    "deep/*.yaml",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_status(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _is_complete_status(value: Any) -> bool:
    return _normalize_status(value) in STATUS_COMPLETE_VALUES


def _is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    return True


def _as_rel_path(path: Path, base: Path) -> str:
    return path.relative_to(base).as_posix()


def _parse_yaml(path: Path) -> tuple[Any, str | None]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f), None
    except FileNotFoundError:
        return None, "file is missing"
    except yaml.YAMLError as exc:
        return None, str(exc).strip()


def _collect_tracked_files(knowledge_dir: Path) -> tuple[list[Path], list[dict[str, str]]]:
    files: list[Path] = []
    parse_errors: list[dict[str, str]] = []

    for filename in ("index.yaml", "graph.yaml", "progress.yaml"):
        path = knowledge_dir / filename
        if path.exists() and path.is_file():
            files.append(path)
        else:
            parse_errors.append({"file": filename, "error": "required file is missing"})

    audit_path = knowledge_dir / "audit-progress.yaml"
    if audit_path.exists() and audit_path.is_file():
        files.append(audit_path)

    for dirname in ("repos", "deep"):
        folder = knowledge_dir / dirname
        if not folder.exists():
            parse_errors.append({"file": f"{dirname}/", "error": "required directory is missing"})
            continue
        if not folder.is_dir():
            parse_errors.append({"file": f"{dirname}/", "error": "required path is not a directory"})
            continue

        for yaml_file in sorted(folder.glob("*.yaml"), key=lambda p: p.name):
            files.append(yaml_file)

    return files, parse_errors


def _evaluate_g1_parse_integrity(knowledge_dir: Path) -> tuple[dict[str, Any], dict[str, Any], set[str]]:
    tracked_files, parse_errors = _collect_tracked_files(knowledge_dir)
    parsed_docs: dict[str, Any] = {}
    parse_failed_files: set[str] = set()

    for yaml_file in tracked_files:
        rel_path = _as_rel_path(yaml_file, knowledge_dir)
        data, error = _parse_yaml(yaml_file)
        if error is not None:
            parse_errors.append({"file": rel_path, "error": error})
            parse_failed_files.add(rel_path)
            continue

        parsed_docs[rel_path] = data if data is not None else {}

    parse_errors.sort(key=lambda item: (item["file"], item["error"]))
    status = "PASS" if not parse_errors else "FAIL"

    return (
        {
            "status": status,
            "parse_errors": parse_errors,
        },
        parsed_docs,
        parse_failed_files,
    )


def _collect_issue_items(audit_doc: dict[str, Any], level: str) -> list[Any]:
    issues = audit_doc.get("issues_found")
    if not isinstance(issues, dict):
        return []

    value = issues.get(level)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.items())
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [value]


def _add_violation(
    violations: list[dict[str, Any]],
    rule: str,
    message: str,
    file: str | None = None,
) -> None:
    violation: dict[str, Any] = {"rule": rule, "message": message}
    if file:
        violation["file"] = file
    violations.append(violation)


def _evaluate_g2_status_semantics(
    parsed_docs: dict[str, Any],
    parse_failed_files: set[str],
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []

    progress_rel = "progress.yaml"
    progress_doc = parsed_docs.get(progress_rel)

    if progress_rel in parse_failed_files:
        _add_violation(
            violations,
            "progress.parse",
            "progress.yaml is not parseable; status semantics cannot be trusted",
            file=progress_rel,
        )
    elif progress_doc is None:
        _add_violation(
            violations,
            "progress.missing",
            "progress.yaml is missing; status semantics cannot be validated",
            file=progress_rel,
        )
    elif not isinstance(progress_doc, dict):
        _add_violation(
            violations,
            "progress.shape",
            "progress.yaml must contain a top-level mapping",
            file=progress_rel,
        )
    else:
        top_status = progress_doc.get("status")
        phases = progress_doc.get("phases")

        if _is_complete_status(top_status):
            if not isinstance(phases, dict):
                _add_violation(
                    violations,
                    "progress.complete_requires_phases",
                    "Top-level status is complete/completed but phases is missing or invalid",
                    file=progress_rel,
                )
            else:
                for phase_name in sorted(phases):
                    phase_data = phases.get(phase_name)
                    phase_status = phase_data.get("status") if isinstance(phase_data, dict) else None
                    if not _is_complete_status(phase_status):
                        _add_violation(
                            violations,
                            "progress.complete_requires_all_phases_complete",
                            (
                                f"Top-level status is complete/completed but phase '{phase_name}' "
                                f"has status '{phase_status}'"
                            ),
                            file=progress_rel,
                        )

        if isinstance(phases, dict):
            deepening = phases.get("deepening")
            if isinstance(deepening, dict) and _is_complete_status(deepening.get("status")):
                pending = deepening.get("pending", [])
                if _is_non_empty(pending):
                    _add_violation(
                        violations,
                        "progress.deepening_pending_must_be_empty",
                        "phases.deepening.status is complete/completed but pending is non-empty",
                        file=progress_rel,
                    )

                current_batch = deepening.get("current_batch", [])
                if _is_non_empty(current_batch):
                    _add_violation(
                        violations,
                        "progress.deepening_current_batch_must_be_empty",
                        "phases.deepening.status is complete/completed but current_batch is non-empty",
                        file=progress_rel,
                    )

            audit_phase = phases.get("audit")
            if isinstance(audit_phase, dict) and _is_complete_status(audit_phase.get("status")):
                if "audit-progress.yaml" in parse_failed_files:
                    _add_violation(
                        violations,
                        "progress.audit_requires_parseable_audit_report",
                        "phases.audit.status is complete/completed but audit-progress.yaml is not parseable",
                        file="audit-progress.yaml",
                    )
                elif "audit-progress.yaml" not in parsed_docs:
                    _add_violation(
                        violations,
                        "progress.audit_requires_audit_report",
                        "phases.audit.status is complete/completed but audit-progress.yaml is missing",
                        file="audit-progress.yaml",
                    )

    audit_rel = "audit-progress.yaml"
    audit_doc = parsed_docs.get(audit_rel)
    if isinstance(audit_doc, dict):
        verdict = audit_doc.get("overall_verdict")
        if verdict in READY_VERDICTS:
            critical_issues = _collect_issue_items(audit_doc, "critical")
            high_issues = _collect_issue_items(audit_doc, "high")

            if critical_issues:
                _add_violation(
                    violations,
                    "audit.ready_verdict_forbidden_with_critical_issues",
                    (
                        f"overall_verdict '{verdict}' is forbidden while "
                        f"issues_found.critical is non-empty"
                    ),
                    file=audit_rel,
                )
            if high_issues:
                _add_violation(
                    violations,
                    "audit.ready_verdict_forbidden_with_high_issues",
                    (
                        f"overall_verdict '{verdict}' is forbidden while "
                        f"issues_found.high is non-empty"
                    ),
                    file=audit_rel,
                )

    violations.sort(key=lambda item: (item.get("rule", ""), item.get("file", ""), item.get("message", "")))
    status = "PASS" if not violations else "FAIL"

    return {
        "status": status,
        "violations": violations,
    }


def _normalize_scope_token(token: str) -> str | None:
    normalized = token.strip().lower()
    if not normalized:
        return None

    mapping = {
        "index": "index.yaml",
        "index.yaml": "index.yaml",
        "graph": "graph.yaml",
        "graph.yaml": "graph.yaml",
        "progress": "progress.yaml",
        "progress.yaml": "progress.yaml",
        "audit-progress": "audit-progress.yaml",
        "audit-progress.yaml": "audit-progress.yaml",
        "repos": "repos/*.yaml",
        "repos/*.yaml": "repos/*.yaml",
        "repos/*.yml": "repos/*.yaml",
        "deep": "deep/*.yaml",
        "deep/*.yaml": "deep/*.yaml",
        "deep/*.yml": "deep/*.yaml",
    }
    return mapping.get(normalized, token.strip())


def _parse_declared_scope(validate_text: str) -> set[str] | None:
    for line in validate_text.splitlines():
        if "VALIDATOR_SCOPE:" not in line:
            continue
        _, value = line.split("VALIDATOR_SCOPE:", 1)
        tokens = []
        for raw in value.split(","):
            token = _normalize_scope_token(raw)
            if token:
                tokens.append(token)
        return set(tokens)
    return None


def _detect_implemented_scope(validate_text: str) -> set[str]:
    scope: set[str] = set()
    text = validate_text

    if "index.yaml" in text:
        scope.add("index.yaml")
    if "graph.yaml" in text:
        scope.add("graph.yaml")
    if "progress.yaml" in text:
        scope.add("progress.yaml")
    if "audit-progress.yaml" in text:
        scope.add("audit-progress.yaml")

    has_glob_yaml = bool(re.search(r"glob\(\s*[\"']\*\.ya?ml[\"']\s*\)", text))
    has_repos_dir_ref = bool(
        re.search(r"[/=]\s*[\"']repos[\"']", text)
        or re.search(r"\bREPOS_DIR\b", text)
    )
    if has_glob_yaml and has_repos_dir_ref:
        scope.add("repos/*.yaml")

    # Detect deep coverage only when code references a quoted \"deep\" path token.
    has_deep_dir_ref = bool(
        re.search(r"[/=]\s*[\"']deep[\"']", text)
        or re.search(r"\bDEEP_DIR\b", text)
    )
    if has_glob_yaml and has_deep_dir_ref:
        scope.add("deep/*.yaml")

    return scope


def _has_all_files_claim(validate_text: str) -> bool:
    return bool(
        re.search(
            r"all\s+files|all\s+knowledge\s+artifacts|yaml\s+syntax\s+for\s+all\s+files",
            validate_text,
            flags=re.IGNORECASE,
        )
    )


def _contract_severity(production: bool) -> str:
    return "FAIL" if production else "WARN"


def _evaluate_g3_contract_integrity(knowledge_dir: Path, production: bool) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    validate_path = knowledge_dir / "validate.py"

    if not validate_path.exists() or not validate_path.is_file():
        findings.append(
            {
                "id": "VALIDATOR_MISSING",
                "severity": _contract_severity(production),
                "file": "validate.py",
                "message": "validate.py is missing; cannot verify spec/validator contract",
            }
        )
    else:
        validate_text = validate_path.read_text(encoding="utf-8")
        declared_scope = _parse_declared_scope(validate_text)
        implemented_scope = _detect_implemented_scope(validate_text)

        if declared_scope is not None:
            if declared_scope != implemented_scope:
                findings.append(
                    {
                        "id": "SCOPE_DECLARED_IMPLEMENTED_MISMATCH",
                        "severity": _contract_severity(production),
                        "file": "validate.py",
                        "message": "Declared validation scope does not match implemented scope",
                        "declared_scope": sorted(declared_scope),
                        "implemented_scope": sorted(implemented_scope),
                    }
                )
        elif _has_all_files_claim(validate_text) and implemented_scope != REQUIRED_SCOPE_TOKENS:
            findings.append(
                {
                    "id": "SCOPE_ALL_FILES_CLAIM_MISMATCH",
                    "severity": _contract_severity(production),
                    "file": "validate.py",
                    "message": "Validator claims all-files coverage but implementation scope is narrower",
                    "implemented_scope": sorted(implemented_scope),
                    "expected_scope": sorted(REQUIRED_SCOPE_TOKENS),
                }
            )
        elif implemented_scope != REQUIRED_SCOPE_TOKENS:
            findings.append(
                {
                    "id": "SCOPE_UNDECLARED_SUBSET",
                    "severity": _contract_severity(production),
                    "file": "validate.py",
                    "message": (
                        "Validator implements subset scope without explicit declaration. "
                        "Add VALIDATOR_SCOPE annotation to keep contract explicit."
                    ),
                    "implemented_scope": sorted(implemented_scope),
                }
            )

    findings.sort(key=lambda item: (item.get("severity", ""), item.get("id", ""), item.get("file", "")))

    if any(item.get("severity") == "FAIL" for item in findings):
        status = "FAIL"
    elif findings:
        status = "WARN"
    else:
        status = "PASS"

    return {
        "status": status,
        "findings": findings,
    }


def _determine_overall_status(
    g1_status: str,
    g2_status: str,
    g3_status: str,
) -> str:
    if g1_status == "FAIL" or g2_status == "FAIL":
        return "BLOCKED"
    if g3_status == "FAIL":
        return "FAIL"
    if g3_status == "WARN":
        return "WARN"
    return "PASS"


def run_trust_gates(
    knowledge_dir: Path,
    *,
    production: bool = False,
    output_path: Path | None = None,
) -> tuple[dict[str, Any], Path]:
    knowledge_dir = knowledge_dir.resolve()

    g1_result, parsed_docs, parse_failed_files = _evaluate_g1_parse_integrity(knowledge_dir)
    g2_result = _evaluate_g2_status_semantics(parsed_docs, parse_failed_files)
    g3_result = _evaluate_g3_contract_integrity(knowledge_dir, production=production)

    overall_status = _determine_overall_status(
        g1_status=g1_result["status"],
        g2_status=g2_result["status"],
        g3_status=g3_result["status"],
    )

    ready_state_allowed = overall_status == "PASS" or (overall_status == "WARN" and not production)

    report = {
        "metadata": {
            "run_at": _utc_now_iso(),
            "knowledge_dir": str(knowledge_dir),
            "production_run": production,
        },
        "gates": {
            "g1_parse_integrity": g1_result,
            "g2_status_semantics": g2_result,
            "g3_spec_validator_contract": g3_result,
        },
        "overall_status": overall_status,
        "ready_state_allowed": ready_state_allowed,
    }

    target_report_path = output_path or (knowledge_dir / "trust-gates-report.yaml")
    target_report_path.parent.mkdir(parents=True, exist_ok=True)
    with target_report_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(report, f, sort_keys=False, default_flow_style=False)

    return report, target_report_path


def main() -> int:
    parser = argparse.ArgumentParser(description="WS0 trust gates preflight")
    parser.add_argument(
        "knowledge_dir",
        nargs="?",
        default=".",
        help="Path to knowledge directory (default: current directory)",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="Treat run as production (G3 mismatches escalate to FAIL)",
    )
    parser.add_argument(
        "--output",
        help="Optional report output path (default: <knowledge_dir>/trust-gates-report.yaml)",
    )

    args = parser.parse_args()

    knowledge_dir = Path(args.knowledge_dir)
    if not knowledge_dir.exists() or not knowledge_dir.is_dir():
        print(f"Error: knowledge directory not found: {knowledge_dir}")
        return 1

    output_path = Path(args.output).resolve() if args.output else None

    report, written_path = run_trust_gates(
        knowledge_dir=knowledge_dir,
        production=args.production,
        output_path=output_path,
    )

    g1 = report["gates"]["g1_parse_integrity"]
    g2 = report["gates"]["g2_status_semantics"]
    g3 = report["gates"]["g3_spec_validator_contract"]

    print(f"Knowledge dir: {report['metadata']['knowledge_dir']}")
    print(f"Report: {written_path}")
    print(f"G1 Parse Integrity: {g1['status']} ({len(g1['parse_errors'])} errors)")
    print(f"G2 Status Semantics: {g2['status']} ({len(g2['violations'])} violations)")
    print(f"G3 Spec/Validator Contract: {g3['status']} ({len(g3['findings'])} findings)")
    print(f"Overall: {report['overall_status']}")
    print(f"ready_state_allowed: {str(report['ready_state_allowed']).lower()}")

    if report["overall_status"] in {"FAIL", "BLOCKED"}:
        return 1
    if report["overall_status"] == "WARN" and args.production:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
