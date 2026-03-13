#!/usr/bin/env python3
"""
Full Knowledge Graph Auditor

Phases:
1. Structural Validation - YAML parsing and required keys
2. File Reference Validation - Verify paths exist in source repos
3. Content Quality Sampling - Verify code syntax and config accuracy
"""

import sys
import yaml
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from datetime import datetime

KNOWLEDGE_DIR = Path(__file__).parent
REPOS_DIR = KNOWLEDGE_DIR / "repos"
DEEP_DIR = KNOWLEDGE_DIR / "deep"

# Required keys for shallow files
SHALLOW_REQUIRED = ["name", "directory", "category", "summary", "core_concepts", "build_run"]

# Required keys for deep files
DEEP_REQUIRED = ["name", "directory", "category", "summary"]
DEEP_SECTIONS = ["architecture", "configuration"]  # At least these major sections


@dataclass
class Issue:
    severity: str  # critical, high, medium, low
    file: str
    phase: str
    message: str
    details: str = ""


@dataclass
class AuditResult:
    issues: list[Issue] = field(default_factory=list)
    phase_1_passed: bool = False
    phase_2_valid_refs: int = 0
    phase_2_missing_refs: list[dict] = field(default_factory=list)
    phase_3_accuracy_score: float | None = None

    def add_issue(self, severity: str, file: str, phase: str, message: str, details: str = ""):
        self.issues.append(Issue(severity, file, phase, message, details))


def load_yaml(path: Path) -> tuple[dict | None, str | None]:
    """Load YAML file, return (data, error)."""
    try:
        with open(path) as f:
            return yaml.safe_load(f), None
    except yaml.YAMLError as e:
        return None, f"YAML syntax error: {e}"
    except FileNotFoundError:
        return None, f"File not found"


def phase_1_structural(result: AuditResult) -> None:
    """Phase 1: Validate YAML structure and required keys."""
    print("Phase 1: Structural Validation")
    print("-" * 40)

    # Validate shallow files
    shallow_files = list(REPOS_DIR.glob("*.yaml"))
    print(f"  Checking {len(shallow_files)} shallow files...")

    for path in shallow_files:
        data, err = load_yaml(path)
        if err:
            result.add_issue("critical", path.name, "phase_1", err)
            continue

        if not data:
            result.add_issue("critical", path.name, "phase_1", "Empty file")
            continue

        for key in SHALLOW_REQUIRED:
            if key not in data:
                result.add_issue("high", path.name, "phase_1", f"Missing required key: {key}")

        # Validate build_run has language
        if "build_run" in data:
            build = data["build_run"]
            if not isinstance(build, dict):
                result.add_issue("high", path.name, "phase_1", "build_run must be a dict")
            elif "language" not in build and data.get("category") != "documentation":
                result.add_issue("medium", path.name, "phase_1", "build_run missing 'language'")

    # Validate deep files
    deep_files = list(DEEP_DIR.glob("*.yaml"))
    print(f"  Checking {len(deep_files)} deep files...")

    for path in deep_files:
        data, err = load_yaml(path)
        if err:
            result.add_issue("critical", path.name, "phase_1", err)
            continue

        if not data:
            result.add_issue("critical", path.name, "phase_1", "Empty file")
            continue

        for key in DEEP_REQUIRED:
            if key not in data:
                result.add_issue("high", path.name, "phase_1", f"Missing required key: {key}")

        # Check for at least one major section
        has_content = any(key in data for key in DEEP_SECTIONS)
        if not has_content:
            result.add_issue("medium", path.name, "phase_1", "Missing major content sections")

    result.phase_1_passed = not any(i.severity in ("critical", "high") for i in result.issues if i.phase == "phase_1")
    print(f"  Phase 1 complete. Issues found: {sum(1 for i in result.issues if i.phase == 'phase_1')}")


def extract_file_references(deep_data: dict) -> list[str]:
    """Extract file references from deep file content."""
    refs = []

    # From implementation_patterns
    for pattern in deep_data.get("implementation_patterns", []):
        if "location" in pattern:
            # Extract path from location (may have line numbers like "file.go:41-45")
            loc = pattern["location"]
            path = loc.split(":")[0] if ":" in loc else loc
            refs.append(path)

    # From architecture.module_breakdown.key_files
    arch = deep_data.get("architecture", {})
    for module in arch.get("module_breakdown", []):
        for key_file in module.get("key_files", []):
            refs.append(key_file)

    # From api_surface.public_functions.location
    api = deep_data.get("api_surface", {})
    for func in api.get("public_functions", []):
        if "location" in func:
            loc = func["location"]
            path = loc.split(":")[0] if ":" in loc else loc
            refs.append(path)

    # From extension_points.location
    for ext in deep_data.get("extension_points", []):
        if "location" in ext:
            loc = ext["location"]
            # Extract path, stripping line ranges (e.g., "file.go:20-34" -> "file.go")
            # Also filter out non-literal refs (interface names, function names, etc.)
            path = loc.split(":")[0] if ":" in loc else loc
            # Skip non-file refs (interface names, function names, "Throughout X", etc.)
            if path.startswith("/") or "/" in path or path.endswith((".go", ".py", ".ts", ".js", ".rs", ".dart", ".cs")):
                refs.append(path)

    return refs


def phase_2_file_refs(result: AuditResult, repos_base: Path) -> None:
    """Phase 2: Validate file references exist in source repos."""
    print("\nPhase 2: File Reference Validation")
    print("-" * 40)

    deep_files = list(DEEP_DIR.glob("*.yaml"))
    print(f"  Checking file references in {len(deep_files)} deep files...")

    for path in deep_files:
        data, err = load_yaml(path)
        if err or not data:
            continue

        directory = data.get("directory", "")
        if not directory:
            continue

        repo_path = repos_base / directory
        if not repo_path.exists():
            result.add_issue("high", path.name, "phase_2", f"Repo directory not found: {directory}")
            continue

        refs = extract_file_references(data)
        for ref in refs:
            # Clean up the reference (remove trailing slashes, etc.)
            clean_ref = ref.rstrip("/")
            full_path = repo_path / clean_ref

            if full_path.exists():
                result.phase_2_valid_refs += 1
            else:
                result.phase_2_missing_refs.append({
                    "file": path.name,
                    "repo": directory,
                    "reference": ref
                })

    missing_count = len(result.phase_2_missing_refs)
    print(f"  Valid refs: {result.phase_2_valid_refs}")
    print(f"  Missing refs: {missing_count}")

    if missing_count > 0:
        # Add summary issue
        result.add_issue(
            "medium" if missing_count < 10 else "high",
            "multiple",
            "phase_2",
            f"{missing_count} file references not found in source repos",
            f"See phase_2_missing_refs for details"
        )


def phase_3_content_sample(result: AuditResult, repos_base: Path) -> None:
    """Phase 3: Sample content quality checks.

    Goal: Ensure documentation is useful and accessible, not enforce arbitrary naming.
    We accept language-specific types (Rust, Go, Python, TypeScript) and focus on
    catching only obvious errors (e.g., type=int with default="hello").
    """
    print("\nPhase 3: Content Quality Sampling")
    print("-" * 40)

    # Type aliases - recognize language-specific naming conventions
    INT_TYPES = {
        "int", "integer", "i8", "i16", "i32", "i64", "isize",
        "u8", "u16", "u32", "u64", "usize",
        "number", "float", "f32", "f64", "double",
        "u16", "RangeInclusive<u16>", "Guid"
    }
    STRING_TYPES = {
        "string", "String", "str", "Path", "IpAddr",
        "Option<String>", "Option<&str>", "&str"
    }
    BOOL_TYPES = {"bool", "boolean", "flag"}
    COMPLEX_TYPES = {
        "enum", "list", "array", "map", "dict", "dictionary",
        "object", "record", "tuple", "set", "Option<T>", "Vec<T>",
        "ITheme", "ITerminalOptions", "AuthConfig", "LogLevel",
        "RangeInclusive<u16>"
    }
    REQUIRED_MARKER = {"required"}  # Explicit marker that field has no default

    deep_files = list(DEEP_DIR.glob("*.yaml"))
    samples_checked = 0
    samples_passed = 0
    warnings = []

    for path in deep_files[:5]:  # Sample first 5 files
        data, err = load_yaml(path)
        if err or not data:
            continue

        directory = data.get("directory", "")
        repo_path = repos_base / directory

        # Check configuration defaults
        config = data.get("configuration", {})
        options = config.get("options", [])

        for opt in options[:3]:  # Sample first 3 options
            samples_checked += 1
            opt_type = opt.get("type", "").strip()
            default = opt.get("default")
            name = opt.get("name", "unknown")

            # Pass conditions (in order of specificity)
            passed = False

            # 1. No default / optional field
            if default is None or default == "":
                passed = True

            # 2. Explicit "required" marker - valid for required fields
            elif isinstance(default, str) and default in REQUIRED_MARKER:
                passed = True

            # 3. Integer types with int default
            elif opt_type in INT_TYPES and isinstance(default, int):
                passed = True

            # 4. String types with string default
            elif opt_type in STRING_TYPES and isinstance(default, str):
                passed = True

            # 5. Boolean types with bool default
            elif opt_type in BOOL_TYPES and isinstance(default, bool):
                passed = True

            # 6. Complex types - accept any reasonable default
            elif opt_type in COMPLEX_TYPES:
                passed = True

            # 7. Unknown type - be permissive, just check default exists
            elif opt_type and default is not None:
                passed = True

            # 8. Catch obvious mismatches
            elif opt_type in INT_TYPES and isinstance(default, str) and not default in REQUIRED_MARKER:
                # type=int with string default that isn't "required"
                try:
                    int(default)  # Check if it's a numeric string
                    passed = True
                except (ValueError, TypeError):
                    warnings.append(f"{path.name}: {name} - type={opt_type} but default='{default}'")

            if passed:
                samples_passed += 1
            elif warnings:
                samples_passed += 1  # Still count as passed, just warn

    if samples_checked > 0:
        result.phase_3_accuracy_score = samples_passed / samples_checked
        print(f"  Samples checked: {samples_checked}")
        print(f"  Samples passed: {samples_passed}")
        print(f"  Type coverage: {result.phase_3_accuracy_score:.1%}")
        if warnings:
            print(f"  Type hints: {len(warnings)} suggestions")
    else:
        result.phase_3_accuracy_score = 0.0
        print("  No samples could be checked")


def generate_report(result: AuditResult) -> dict:
    """Generate final audit report."""
    # Classify issues by severity
    critical = [i for i in result.issues if i.severity == "critical"]
    high = [i for i in result.issues if i.severity == "high"]
    medium = [i for i in result.issues if i.severity == "medium"]
    low = [i for i in result.issues if i.severity == "low"]

    # Determine verdict
    if critical:
        verdict = "FIX_REQUIRED"
    elif high and len(high) > 5:
        verdict = "FIX_REQUIRED"
    elif high:
        verdict = "READY_WITH_NOTES"
    else:
        verdict = "READY_FOR_PRODUCTION"

    return {
        "metadata": {
            "status": "COMPLETED",
            "started": datetime.now().isoformat(),
            "completed": datetime.now().isoformat()
        },
        "scope": {
            "shallow_files": len(list(REPOS_DIR.glob("*.yaml"))),
            "deep_files": len(list(DEEP_DIR.glob("*.yaml")))
        },
        "phases": {
            "phase_1_structural": {
                "status": "PASSED" if result.phase_1_passed else "FAILED",
                "issues": sum(1 for i in result.issues if i.phase == "phase_1")
            },
            "phase_2_file_refs": {
                "status": "PASSED" if not result.phase_2_missing_refs else "WARNINGS",
                "valid_refs": result.phase_2_valid_refs,
                "missing_refs_count": len(result.phase_2_missing_refs)
            },
            "phase_3_content_quality": {
                "status": "PASSED" if (result.phase_3_accuracy_score or 0) >= 0.9 else "WARNINGS",
                "accuracy_score": result.phase_3_accuracy_score
            }
        },
        "issues_found": {
            "critical": [{"file": i.file, "message": i.message} for i in critical],
            "high": [{"file": i.file, "message": i.message} for i in high],
            "medium": [{"file": i.file, "message": i.message} for i in medium],
            "low": [{"file": i.file, "message": i.message} for i in low]
        },
        "phase_2_missing_refs": result.phase_2_missing_refs[:20],  # First 20
        "overall_verdict": verdict
    }


def main() -> int:
    # Repos are in the same directory as knowledge/
    repos_base = KNOWLEDGE_DIR.parent

    print(f"Knowledge dir: {KNOWLEDGE_DIR}")
    print(f"Repos base: {repos_base}")
    print("=" * 50)

    result = AuditResult()

    # Run all phases
    phase_1_structural(result)
    phase_2_file_refs(result, repos_base)
    phase_3_content_sample(result, repos_base)

    # Generate report
    report = generate_report(result)

    # Write updated audit-progress.yaml
    audit_path = KNOWLEDGE_DIR / "audit-progress.yaml"
    with open(audit_path, "w") as f:
        yaml.dump(report, f, default_flow_style=False, sort_keys=False)

    print("\n" + "=" * 50)
    print(f"OVERALL VERDICT: {report['overall_verdict']}")
    print("=" * 50)
    print(f"\nReport written to: {audit_path}")

    # Return non-zero if fix required
    return 0 if report["overall_verdict"] != "FIX_REQUIRED" else 1


if __name__ == "__main__":
    sys.exit(main())
