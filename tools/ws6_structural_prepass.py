#!/usr/bin/env python3
"""Generate narrow, non-canonical WS6 structural pre-pass artifacts.

Reads a WS6 clone manifest, inspects checked-out repos with cheap deterministic
signals, writes per-repo orientation artifacts under reports/, and emits a batch
summary with contract validation results.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 fallback
    tomllib = None


SCHEMA_VERSION = "0.1"
STAGE_NAME = "ws6_structural_prepass"
MODE_NAME = "filesystem_manifest_entrypoint"
DEFAULT_OUTPUT_DIR = "reports/ws6_structural_prepass"
DEFAULT_CLONE_WORKDIR = "workspace/clones"
MAX_SCANNED_SOURCE_FILES = 400
MAX_SOURCE_FILE_BYTES = 128_000

IGNORED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "coverage",
    ".next",
    ".turbo",
    ".cache",
    "target",
    "out",
    "tmp",
    "vendor",
}

MANIFEST_KINDS = {
    "pyproject.toml": "python_manifest",
    "requirements.txt": "python_requirements",
    "requirements-dev.txt": "python_requirements",
    "setup.py": "python_manifest",
    "setup.cfg": "python_manifest",
    "package.json": "node_manifest",
    "pnpm-workspace.yaml": "node_workspace",
    "go.mod": "go_manifest",
    "Cargo.toml": "rust_manifest",
    "Chart.yaml": "helm_chart_manifest",
}

CONFIG_KINDS = {
    "docker-compose.yml": "runtime_config",
    "docker-compose.yaml": "runtime_config",
    "compose.yml": "runtime_config",
    "compose.yaml": "runtime_config",
    ".env.example": "env_example",
    ".env.sample": "env_example",
    ".github/workflows": "ci_config",
    "tsconfig.json": "typescript_config",
    "vite.config.ts": "build_config",
    "vite.config.js": "build_config",
    "next.config.js": "framework_config",
    "next.config.mjs": "framework_config",
    "next.config.ts": "framework_config",
    "pytest.ini": "test_config",
    "tox.ini": "test_config",
    "mkdocs.yml": "docs_config",
    "wrangler.toml": "runtime_config",
    "turbo.json": "build_config",
    "mcp.json": "runtime_config",
}

LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",
}

SOURCE_EXTENSIONS = frozenset(LANGUAGE_EXTENSIONS.keys())

PYTHON_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][\w\.]*)", re.MULTILINE)
JS_IMPORT_RE = re.compile(
    r"""(?:import\s+.+?\s+from\s+|import\s*['"]|require\()\s*['"]([^'"]+)['"]""",
    re.MULTILINE,
)
GO_IMPORT_RE = re.compile(r'"([^"\n]+)"')

NOISE_TOKENS = {
    "bench",
    "benchmark",
    "benchmarks",
    "demo",
    "demos",
    "dist",
    "doc",
    "docs",
    "example",
    "examples",
    "fixture",
    "fixtures",
    "generated",
    "sample",
    "samples",
    "site",
    "storybook",
    "test",
    "tests",
}

SUPPORT_TOKENS = {
    "blog",
    "cookbook",
    "coverage",
    "dev",
    "githooks",
    "helm",
    "hook",
    "hooks",
    "infra",
    "monitoring",
    "ops",
    "public",
    "script",
    "scripts",
    "static",
    "tool",
    "tools",
}

FRONTEND_TOKENS = {
    "console",
    "dashboard",
    "frontend",
    "portal",
    "site",
    "ui",
    "web",
}

GENERIC_GROUP_TOKENS = {
    "app",
    "apps",
    "client",
    "clients",
    "cmd",
    "feature",
    "features",
    "internal",
    "lib",
    "libs",
    "net",
    "package",
    "packages",
    "server",
    "src",
    "type",
    "types",
    "util",
    "utils",
}

RUNTIME_TOKENS = {
    "admin",
    "api",
    "app",
    "cli",
    "cmd",
    "daemon",
    "gateway",
    "mcp",
    "server",
    "service",
    "worker",
}

# File stems that identify Celery/queue worker bootstrap entrypoints.
# These files are typically small re-export modules that launch a separate
# worker process (e.g. `celery -A celery_entrypoint worker`).
WORKER_BOOTSTRAP_STEMS = {
    "celery_entrypoint",
    "worker_entrypoint",
    "queue_worker",
    "worker_app",
}

BOUNDARY_TOKENS = {
    "all",
    "client",
    "clients",
    "control",
    "core",
    "embed",
    "engine",
    "integration",
    "integrations",
    "memory",
    "plane",
    "sdk",
}

DEV_DEPENDENCY_HINTS = (
    "eslint",
    "jest",
    "mypy",
    "prettier",
    "pytest",
    "ruff",
    "storybook",
    "tsup",
    "typescript",
    "vitest",
)

FRONTEND_FRAMEWORK_CONFIG_NAMES = {
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "nuxt.config.js",
    "nuxt.config.ts",
    "remix.config.js",
    "remix.config.ts",
    "svelte.config.js",
    "svelte.config.ts",
    "vite.config.js",
    "vite.config.ts",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def dump_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def ensure_repo_relative(path: Path) -> str:
    text = path.as_posix()
    return text if text else "."


def path_tokens(path: Path) -> list[str]:
    tokens: list[str] = []
    for part in path.parts:
        for token in re.split(r"[^a-z0-9]+", part.lower()):
            if token:
                tokens.append(token)
    return tokens


def path_part_labels(path: Path) -> list[str]:
    labels: list[str] = []
    for part in path.parts:
        label = re.sub(r"[^a-z0-9]+", "_", part.lower()).strip("_")
        if label:
            labels.append(label)
    return labels


def path_depth(path: Path) -> int:
    return max(len(path.parts) - 1, 0)


def path_has_noise(path: Path) -> bool:
    return any(label in NOISE_TOKENS for label in path_part_labels(path))


def build_source_dir_counts(paths: list[Path]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for path in paths:
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        current = path.parent
        while current != Path(".") and current.parts:
            counts[ensure_repo_relative(current)] += 1
            current = current.parent
    return counts


def orientation_score(path: Path, *, prefer_runtime: bool) -> int:
    tokens = path_tokens(path)
    labels = path_part_labels(path)
    score = 0
    if prefer_runtime:
        score += sum(4 for token in tokens if token in RUNTIME_TOKENS)
        score += sum(2 for token in tokens if token in BOUNDARY_TOKENS)
    else:
        score += sum(3 for token in tokens if token in RUNTIME_TOKENS)
        score += sum(3 for token in tokens if token in BOUNDARY_TOKENS)

    if any(label in NOISE_TOKENS for label in labels):
        score -= sum(6 for label in labels if label in NOISE_TOKENS)
    if any(label in SUPPORT_TOKENS for label in labels):
        score -= sum(3 for label in labels if label in SUPPORT_TOKENS)

    if len(path.parts) <= 2:
        score += 3
    elif len(path.parts) == 3:
        score += 1
    else:
        score -= min(path_depth(path), 4)

    if path.name.lower().startswith("readme"):
        score += 2
    return score


def frontend_surface_boost(
    path: Path,
    *,
    manifests: list[dict[str, str]],
    config_files: list[dict[str, str]],
    source_dir_counts: Counter[str],
    paths: list[Path],
) -> int:
    labels = path_part_labels(path)
    if not any(label in FRONTEND_TOKENS for label in labels):
        return 0
    if is_noise_root(path):
        return 0

    rel = ensure_repo_relative(path)
    source_count = source_dir_counts.get(rel, 0)
    if source_count < 8:
        return 0

    has_node_manifest = any(
        Path(item["path"]).parent == path and item["kind"] in {"node_manifest", "node_workspace"}
        for item in manifests
    )
    has_framework_config = any(
        item["path"].startswith(f"{rel}/") and Path(item["path"]).name in FRONTEND_FRAMEWORK_CONFIG_NAMES
        for item in config_files
    )
    has_frontend_routes = any(
        len(candidate.parts) >= len(path.parts) + 2
        and candidate.parts[: len(path.parts)] == path.parts
        and candidate.parts[len(path.parts)] in {"app", "pages", "routes", "src"}
        and candidate.suffix.lower() in {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}
        for candidate in paths
    )
    if not (has_node_manifest or has_framework_config or has_frontend_routes):
        return 0

    boost = 4
    if has_node_manifest:
        boost += 2
    if has_framework_config:
        boost += 4
    if has_frontend_routes:
        boost += 3
    if len(path.parts) == 1:
        boost += 2
    if source_count >= 100:
        boost += 4
    elif source_count >= 30:
        boost += 2
    return boost


def is_noise_root(path: Path) -> bool:
    labels = path_part_labels(path)
    return any(label in NOISE_TOKENS or label in SUPPORT_TOKENS for label in labels)


def dedupe_evidence(entries: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, str]] = []
    for entry in entries:
        key = (
            entry.get("kind", ""),
            entry.get("path", ""),
            entry.get("detail", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def normalized_group_name(path: Path) -> str:
    return path.name.replace("-", "_").replace(".", "_")


def prefer_source_equivalent_path(repo_root: Path, rel_path: Path) -> Path | None:
    parts = list(rel_path.parts)
    if not any(part in {"dist", "build", "out"} for part in parts):
        return None

    candidate_bases: list[Path] = []
    for replacement in ("src", "app", "server"):
        swapped = [replacement if part in {"dist", "build", "out"} else part for part in parts]
        candidate_bases.append(Path(*swapped))

    stem = rel_path.stem
    for base in candidate_bases:
        for suffix in (".ts", ".tsx", ".js", ".jsx", ".py"):
            candidate = base.with_suffix(suffix)
            if (repo_root / candidate).exists():
                return candidate
        if stem == "index":
            for suffix in (".ts", ".tsx", ".js", ".jsx", ".py"):
                candidate = base.parent / f"index{suffix}"
                if (repo_root / candidate).exists():
                    return candidate
    return None


def is_dependency_noise(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in DEV_DEPENDENCY_HINTS)


def normalize_file_stem(github_full_name: str) -> str:
    owner, repo = github_full_name.split("/", 1)
    return f"{owner.lower()}__{repo.lower()}"


def load_input_manifest_lookup(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    payload = load_yaml(path) or {}
    repos = payload.get("repos", []) if isinstance(payload, dict) else []
    lookup: dict[str, dict[str, Any]] = {}
    for entry in repos:
        if isinstance(entry, dict) and entry.get("github_full_name"):
            lookup[str(entry["github_full_name"])] = entry
    return lookup


def load_canonical_repo_lookup(workspace_root: Path) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    base = workspace_root / "repos" / "knowledge" / "repos"
    if not base.exists():
        return lookup
    for repo_file in sorted(base.glob("*.yaml")):
        try:
            payload = load_yaml(repo_file) or {}
        except yaml.YAMLError:
            continue
        github_full_name = payload.get("github_full_name")
        node_id = payload.get("node_id")
        if isinstance(github_full_name, str) and github_full_name:
            lookup[github_full_name] = {
                "file_stem": repo_file.stem,
                "node_id": node_id if isinstance(node_id, str) and node_id else f"repo::{github_full_name}",
            }
    return lookup


def find_case_insensitive_path(root: Path, target_name: str) -> Path | None:
    if not root.exists():
        return None
    lower_target = target_name.lower()
    for child in root.iterdir():
        if child.name.lower() == lower_target:
            return child
    return None


def resolve_repo_root(
    workspace_root: Path,
    clone_manifest: dict[str, Any],
    clone_entry: dict[str, Any],
    clone_workdir_override: Path | None,
) -> Path | None:
    local_path_raw = clone_entry.get("local_path")
    if isinstance(local_path_raw, str) and local_path_raw:
        local_path = Path(local_path_raw)
        if local_path.exists():
            return local_path

    full_name = str(clone_entry["github_full_name"])
    default_slug = full_name.replace("/", "__")
    candidates: list[Path] = []

    if clone_workdir_override is not None:
        candidates.append(clone_workdir_override / default_slug)

    manifest_workdir = clone_manifest.get("clone_workdir")
    if isinstance(manifest_workdir, str) and manifest_workdir:
        manifest_path = Path(manifest_workdir)
        if manifest_path.is_absolute():
            candidates.append(workspace_root / DEFAULT_CLONE_WORKDIR / default_slug)
        else:
            candidates.append((workspace_root / manifest_path) / default_slug)

    candidates.append(workspace_root / DEFAULT_CLONE_WORKDIR / default_slug)

    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists():
            return resolved
        parent = resolved.parent
        matched = find_case_insensitive_path(parent, resolved.name)
        if matched is not None and matched.exists():
            return matched.resolve()
    return None


def iter_repo_files(repo_root: Path) -> list[Path]:
    rel_paths: list[Path] = []
    for current_root, dirs, files in os.walk(repo_root, topdown=True):
        dirs[:] = sorted(
            directory
            for directory in dirs
            if directory not in IGNORED_DIRS and not directory.startswith(".terraform")
        )
        current_path = Path(current_root)
        for name in sorted(files):
            rel_path = (current_path / name).relative_to(repo_root)
            rel_paths.append(rel_path)
    return rel_paths


def classify_manifest(path: Path) -> str | None:
    if path.name in MANIFEST_KINDS:
        return MANIFEST_KINDS[path.name]
    if path.name.startswith("requirements") and path.suffix == ".txt":
        return "python_requirements"
    return None


def classify_config_path(path: Path) -> str | None:
    text = ensure_repo_relative(path)
    if text in CONFIG_KINDS:
        return CONFIG_KINDS[text]
    if path.name in CONFIG_KINDS:
        return CONFIG_KINDS[path.name]
    if text.startswith(".github/workflows/"):
        return "ci_workflow"
    if text.endswith(".env.example") or text.endswith(".env.sample"):
        return "env_example"
    return None


def detect_languages(paths: list[Path], manifest_paths: list[dict[str, str]]) -> list[str]:
    counter: Counter[str] = Counter()
    for path in paths:
        language = LANGUAGE_EXTENSIONS.get(path.suffix.lower())
        if language:
            counter[language] += 1
    manifest_kinds = {item["kind"] for item in manifest_paths}
    if "python_manifest" in manifest_kinds or "python_requirements" in manifest_kinds:
        counter["python"] += 1
    if "node_manifest" in manifest_kinds or "node_workspace" in manifest_kinds:
        counter["typescript"] += 1
    if "go_manifest" in manifest_kinds:
        counter["go"] += 1
    if "rust_manifest" in manifest_kinds:
        counter["rust"] += 1
    return [language for language, _count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))]


def file_evidence(kind: str, path: Path, detail: str | None = None) -> dict[str, str]:
    payload = {"kind": kind, "path": ensure_repo_relative(path)}
    if detail:
        payload["detail"] = detail
    return payload


def collect_manifest_signals(paths: list[Path]) -> list[dict[str, str]]:
    manifests: list[dict[str, str]] = []
    for path in paths:
        kind = classify_manifest(path)
        if kind:
            manifests.append({"path": ensure_repo_relative(path), "kind": kind})
    return manifests


def collect_config_signals(paths: list[Path]) -> list[dict[str, str]]:
    configs: list[dict[str, str]] = []
    for path in paths:
        kind = classify_config_path(path)
        if kind:
            configs.append({"path": ensure_repo_relative(path), "kind": kind})
    return configs


def choose_package_roots(
    repo_root: Path,
    paths: list[Path],
    manifests: list[dict[str, str]],
    config_files: list[dict[str, str]],
) -> list[dict[str, Any]]:
    roots: dict[str, dict[str, Any]] = {}
    manifest_paths = {Path(item["path"]): item["kind"] for item in manifests}
    manifest_roots = {manifest_path.parent for manifest_path in manifest_paths}
    source_dir_counts = build_source_dir_counts(paths)

    def register_candidate(path: Path, evidence: dict[str, str], source: str) -> None:
        rel = ensure_repo_relative(path)
        if rel == ".":
            item = roots.setdefault(rel, {"path": rel, "evidence": [], "sources": set(), "_score": 18})
        else:
            score = orientation_score(path, prefer_runtime=False)
            if source == "manifest":
                score += 12
            elif source == "init":
                score += 8
            elif source == "structural":
                score += 6
            elif source == "workspace_child":
                score += 7
            score += frontend_surface_boost(
                path,
                manifests=manifests,
                config_files=config_files,
                source_dir_counts=source_dir_counts,
                paths=paths,
            )
            if is_noise_root(path):
                score -= 8
            item = roots.setdefault(rel, {"path": rel, "evidence": [], "sources": set(), "_score": score})
            item["_score"] = max(item["_score"], score)
        item["evidence"].append(evidence)
        item["sources"].add(source)

    for manifest_path, kind in manifest_paths.items():
        register_candidate(manifest_path.parent, file_evidence("manifest", manifest_path, kind), "manifest")

    init_dirs = sorted({path.parent for path in paths if path.name == "__init__.py"})
    for init_dir in init_dirs:
        if is_noise_root(init_dir):
            continue
        if len(init_dir.parts) == 1 or init_dir.parent in manifest_roots:
            register_candidate(init_dir, file_evidence("filepath", init_dir / "__init__.py"), "init")

    structural_dirs = ("src", "app", "server", "cmd", "pkg", "internal", "packages", "libs")
    present_dirs = {path.parts[0] for path in paths if path.parts}
    for directory in structural_dirs:
        if directory in present_dirs:
            rel_path = Path(directory)
            if not is_noise_root(rel_path):
                register_candidate(rel_path, file_evidence("directory", rel_path), "structural")

    package_children = ("packages", "libs")
    for parent in package_children:
        for path in paths:
            if len(path.parts) >= 2 and path.parts[0] == parent:
                if Path(path.parts[1]).suffix:
                    continue
                child = Path(path.parts[0]) / path.parts[1]
                if not is_noise_root(child):
                    register_candidate(child, file_evidence("directory", child), "workspace_child")

    selected = sorted(roots.values(), key=lambda item: (-item["_score"], item["path"]))
    if selected:
        return [
            {
                "path": item["path"],
                "evidence": dedupe_evidence(item["evidence"]),
            }
            for item in selected[:8]
        ]
    return [{"path": ".", "evidence": [file_evidence("directory", Path("."), "repo root fallback")]}]


def score_entrypoint(path: Path, source_dir_counts: Counter[str]) -> tuple[int, str, str]:
    text = ensure_repo_relative(path)
    parts = path.parts
    name = path.name.lower()
    suffix = path.suffix.lower()
    if name == "__init__.py":
        return 0, "app_entry", "package init is not a runtime entrypoint"
    base_score = 0
    kind = "app_entry"
    note = "filename heuristic"

    if name in {"main.py", "main.ts", "main.js", "main.go", "main.rs"}:
        base_score += 5
    if name in {"app.py", "server.py", "manage.py", "cli.py", "wsgi.py", "asgi.py", "index.ts", "index.js"}:
        base_score += 4
    if name == "cli.py":
        kind = "cli_entry"
    if "main.go" == name and "cmd" in parts:
        base_score += 5
        kind = "cli_entry"
        note = "cmd main convention"
    if len(parts) >= 2 and suffix in SOURCE_EXTENSIONS and path.parent.name.lower() == path.stem.lower():
        base_score += 6
        note = "directory-matched runtime file"
        if "cmd" in parts:
            kind = "cli_entry"
    if name.startswith("main.") and suffix in SOURCE_EXTENSIONS:
        base_score += 2
    if name.startswith("server.") and suffix in SOURCE_EXTENSIONS:
        base_score += 2
        kind = "server_entry"
    if text.startswith("src/main."):
        base_score += 2
    if text == "manage.py":
        kind = "management_entry"
        note = "framework manage convention"
    if name in {"wsgi.py", "asgi.py"}:
        kind = "server_entry"
        note = "framework entry convention"
    if path.stem.lower() in WORKER_BOOTSTRAP_STEMS:
        base_score += 5
        kind = "worker_entry"
        note = "celery/queue worker bootstrap stem"
    if "worker" in path_tokens(path):
        base_score += 2
    if base_score == 0:
        return 0, kind, note
    score = base_score + orientation_score(path, prefer_runtime=True)
    subtree_source_count = source_dir_counts.get(ensure_repo_relative(path.parent), 0)
    if subtree_source_count >= 3:
        score += min(subtree_source_count, 18) // 2
    if kind == "worker_entry" and path_depth(path) <= 2:
        score += 3
    if len(parts) >= 3 and parts[0] == "cmd" and name == f"{parts[1].lower()}{suffix}":
        score += 6
    if len(parts) >= 3 and parts[0] == "cmd" and name == "main.go" and subtree_source_count <= 2:
        score -= 4
    if "admin" in path_tokens(path):
        score -= 3
    return score, kind, note


def parse_package_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def parse_toml(path: Path) -> dict[str, Any]:
    if tomllib is None:
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def pyproject_script_entrypoints(repo_root: Path, rel_path: Path) -> list[dict[str, Any]]:
    payload = parse_toml(repo_root / rel_path)
    entrypoints: list[dict[str, Any]] = []
    project = payload.get("project", {}) if isinstance(payload, dict) else {}
    script_sections: list[tuple[str, Any]] = [("project.scripts", project.get("scripts"))]

    tool_section = payload.get("tool", {}) if isinstance(payload, dict) else {}
    poetry = tool_section.get("poetry", {}) if isinstance(tool_section, dict) else {}
    script_sections.append(("tool.poetry.scripts", poetry.get("scripts")))

    for section_name, scripts in script_sections:
        if not isinstance(scripts, dict):
            continue
        for command_name, target in sorted(scripts.items()):
            if not isinstance(target, str) or ":" not in target:
                continue
            module_name = target.split(":", 1)[0].strip()
            if not module_name:
                continue
            module_path = rel_path.parent / Path(*module_name.split("."))
            file_path = module_path.with_suffix(".py")
            if not (repo_root / file_path).exists():
                init_path = module_path / "__init__.py"
                if not (repo_root / init_path).exists():
                    continue
                file_path = init_path
            entrypoints.append({
                "path": ensure_repo_relative(file_path),
                "kind": "cli_entry" if "cli" in command_name or "admin" in command_name else "app_entry",
                "confidence": "medium",
                "evidence": [
                    file_evidence("manifest", rel_path, f"{section_name}:{command_name}"),
                    file_evidence("filepath", file_path),
                ],
            })
    return entrypoints


def package_json_entrypoints(repo_root: Path, rel_path: Path) -> list[dict[str, Any]]:
    payload = parse_package_json(repo_root / rel_path)
    entrypoints: list[dict[str, Any]] = []
    main_value = payload.get("main")
    if isinstance(main_value, str) and main_value:
        main_path = rel_path.parent / Path(main_value)
        preferred_path = prefer_source_equivalent_path(repo_root, main_path) or main_path
        detail = "package.json main"
        if preferred_path != main_path:
            detail = "package.json main mapped to authored source"
        entrypoints.append({
            "path": ensure_repo_relative(preferred_path),
            "kind": "app_entry",
            "confidence": "medium",
            "evidence": [
                file_evidence("manifest", rel_path, detail),
                file_evidence("filepath", preferred_path),
            ],
        })
    bin_value = payload.get("bin")
    if isinstance(bin_value, str) and bin_value:
        bin_path = rel_path.parent / Path(bin_value)
        entrypoints.append({
            "path": ensure_repo_relative(bin_path),
            "kind": "cli_entry",
            "confidence": "medium",
            "evidence": [
                file_evidence("manifest", rel_path, "package.json bin"),
                file_evidence("filepath", bin_path),
            ],
        })
    elif isinstance(bin_value, dict):
        for command_name, command_path in sorted(bin_value.items()):
            if not isinstance(command_path, str) or not command_path:
                continue
            rel_bin = rel_path.parent / Path(command_path)
            entrypoints.append({
                "path": ensure_repo_relative(rel_bin),
                "kind": "cli_entry",
                "confidence": "medium",
                "evidence": [
                    file_evidence("manifest", rel_path, f"package.json bin:{command_name}"),
                    file_evidence("filepath", rel_bin),
                ],
            })
    return entrypoints


def choose_entrypoints(repo_root: Path, paths: list[Path], manifests: list[dict[str, str]]) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    source_dir_counts = build_source_dir_counts(paths)
    for path in paths:
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        score, kind, note = score_entrypoint(path, source_dir_counts)
        if score >= 4:
            candidates[ensure_repo_relative(path)] = {
                "path": ensure_repo_relative(path),
                "kind": kind,
                "confidence": "high" if score >= 6 else "medium",
                "evidence": [file_evidence("filepath", path, note)],
                "_score": score,
            }

    for manifest in manifests:
        manifest_path = Path(manifest["path"])
        if manifest_path.name == "package.json":
            for entry in package_json_entrypoints(repo_root, manifest_path):
                entry_path = Path(entry["path"])
                existing = candidates.get(entry["path"])
                entry["_score"] = 5 + orientation_score(entry_path, prefer_runtime=True)
                if existing is None or existing["_score"] < entry["_score"]:
                    candidates[entry["path"]] = entry
        elif manifest_path.name == "pyproject.toml":
            for entry in pyproject_script_entrypoints(repo_root, manifest_path):
                entry_path = Path(entry["path"])
                existing = candidates.get(entry["path"])
                penalty = 0
                entry_tokens = path_tokens(entry_path)
                if "admin" in entry_tokens:
                    penalty += 3
                if "local" in entry_tokens:
                    penalty += 1
                entry["_score"] = 4 + orientation_score(entry_path, prefer_runtime=True) - penalty
                if existing is None or existing["_score"] < entry["_score"]:
                    candidates[entry["path"]] = entry

    selected = sorted(candidates.values(), key=lambda item: (-item["_score"], item["path"]))[:8]
    for item in selected:
        item.pop("_score", None)
    return selected


def choose_module_groups(
    paths: list[Path],
    package_roots: list[dict[str, Any]],
    manifests: list[dict[str, str]],
    config_files: list[dict[str, str]],
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    source_dir_counts: Counter[str] = Counter()
    for path in paths:
        if path.suffix.lower() in SOURCE_EXTENSIONS and path.parts:
            if len(path.parts) >= 2 and path.parts[0] in {"src", "app", "server", "cmd", "pkg", "internal"}:
                source_dir_counts[f"{path.parts[0]}/{path.parts[1]}"] += 1
            else:
                source_dir_counts[path.parts[0]] += 1

    def add_group(name: str, candidate_path: str, rationale: str, evidence: list[dict[str, str]], score: int) -> None:
        item = groups.setdefault(
            name,
            {
                "name": name,
                "paths": [],
                "rationale": rationale,
                "confidence": "medium",
                "evidence": [],
                "_score": score,
            },
        )
        item["_score"] = max(item["_score"], score)
        if candidate_path not in item["paths"]:
            item["paths"].append(candidate_path)
        item["evidence"].extend(evidence)
        if len(item["paths"]) > 1:
            item["confidence"] = "high"
            item["rationale"] = "merged related package roots with the same module label"

    for package_root in package_roots:
        root_path = Path(package_root["path"])
        if package_root["path"] == ".":
            continue
        if is_noise_root(root_path):
            continue
        add_group(
            normalized_group_name(root_path),
            package_root["path"],
            "package root or workspace module boundary",
            package_root["evidence"],
            10
            + orientation_score(root_path, prefer_runtime=False)
            + frontend_surface_boost(
                root_path,
                manifests=manifests,
                config_files=config_files,
                source_dir_counts=source_dir_counts,
                paths=paths,
            ),
        )

    for directory, count in sorted(source_dir_counts.items(), key=lambda item: (-item[1], item[0])):
        rel_path = Path(directory)
        if count < 2 or is_noise_root(rel_path):
            continue
        add_group(
            normalized_group_name(rel_path),
            directory,
            "directory grouping with repeated source files",
            [file_evidence("directory", rel_path)],
            count + orientation_score(rel_path, prefer_runtime=False),
        )

    selected = sorted(groups.values(), key=lambda item: (-item["_score"], item["name"]))
    if selected:
        trimmed: list[dict[str, Any]] = []
        for item in selected[:8]:
            trimmed.append({
                "name": item["name"],
                "paths": sorted(item["paths"]),
                "rationale": item["rationale"],
                "confidence": item["confidence"],
                "evidence": dedupe_evidence(item["evidence"]),
            })
        return trimmed

    fallback_path = package_roots[0]["path"]
    return [{
        "name": Path(fallback_path).name or "repo_root",
        "paths": [fallback_path],
        "rationale": "fallback structural grouping from package root",
        "confidence": "medium",
        "evidence": package_roots[0]["evidence"],
    }]


def parse_requirements(text: str) -> list[str]:
    packages: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        package = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip()
        if package:
            packages.append(package)
    return packages


def parse_go_mod(text: str) -> list[str]:
    packages: list[str] = []
    in_require_block = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("require ("):
            in_require_block = True
            continue
        if in_require_block and line == ")":
            in_require_block = False
            continue
        if in_require_block and line:
            packages.append(line.split()[0])
        elif line.startswith("require "):
            rest = line[len("require "):].strip()
            if rest:
                packages.append(rest.split()[0])
    return packages


def collapse_internal_module(match: str, language: str) -> str:
    if language == "python":
        parts = [part for part in match.split(".") if part]
        if len(parts) >= 2:
            return ".".join(parts[:2])
        return match
    if language == "javascript":
        parts = [part for part in match.split("/") if part]
        if len(parts) >= 2:
            return "/".join(parts[:2])
    if language == "go":
        parts = [part for part in match.split("/") if part]
        if len(parts) >= 2:
            return "/".join(parts[-2:])
    return match


def collect_dependency_signals(
    repo_root: Path,
    manifests: list[dict[str, str]],
    paths: list[Path],
    package_roots: list[dict[str, Any]],
    entrypoints: list[dict[str, Any]],
    module_groups: list[dict[str, Any]],
    languages: list[str],
) -> dict[str, list[str]] | None:
    external_packages: Counter[str] = Counter()
    internal_modules: Counter[str] = Counter()
    package_prefixes = {Path(item["path"]).name.replace("-", "_") for item in package_roots if item["path"] != "."}
    entrypoint_root_counts: Counter[str] = Counter()
    for item in entrypoints:
        entry_path = Path(item["path"])
        if entry_path.parts:
            entrypoint_root_counts[entry_path.parts[0]] += 1
    group_root_counts: Counter[str] = Counter()
    for group in module_groups[:4]:
        for group_path in group["paths"]:
            group_root = Path(group_path)
            if group_root.parts:
                group_root_counts[group_root.parts[0]] += 1

    complex_repo = len(languages) >= 3 or len(manifests) >= 10 or len(package_roots) >= 6
    manifest_budget = 4 if complex_repo else 8
    external_budget = 12 if complex_repo else 20
    internal_budget = 10 if complex_repo else 16

    prioritized_manifests = sorted(
        manifests,
        key=lambda item: (
            -(
                12
                + orientation_score(Path(item["path"]).parent, prefer_runtime=False)
                + (
                    5 * entrypoint_root_counts.get(Path(item["path"]).parent.parts[0], 0)
                    if Path(item["path"]).parent.parts
                    else 0
                )
                + (
                    2 * group_root_counts.get(Path(item["path"]).parent.parts[0], 0)
                    if Path(item["path"]).parent.parts
                    else 0
                )
                + (2 if item["kind"] in {"python_manifest", "node_manifest", "go_manifest", "rust_manifest"} else 0)
            ),
            item["path"],
        ),
    )[:manifest_budget]

    for manifest_index, manifest in enumerate(prioritized_manifests):
        rel_path = Path(manifest["path"])
        abs_path = repo_root / rel_path
        manifest_weight = max(manifest_budget - manifest_index, 1)
        if rel_path.name == "package.json":
            payload = parse_package_json(abs_path)
            for key in ("dependencies", "peerDependencies"):
                deps = payload.get(key)
                if isinstance(deps, dict):
                    for name in deps.keys():
                        if not is_dependency_noise(str(name)):
                            external_packages[str(name)] += manifest_weight
        elif rel_path.name == "pyproject.toml":
            payload = parse_toml(abs_path)
            project = payload.get("project", {}) if isinstance(payload, dict) else {}
            dependencies = project.get("dependencies", [])
            if isinstance(dependencies, list):
                for name in parse_requirements("\n".join(str(item) for item in dependencies)):
                    if not is_dependency_noise(name):
                        external_packages[name] += manifest_weight
            poetry = payload.get("tool", {}).get("poetry", {}) if isinstance(payload, dict) else {}
            poetry_dependencies = poetry.get("dependencies", {})
            if isinstance(poetry_dependencies, dict):
                for name in poetry_dependencies.keys():
                    name_text = str(name)
                    if name_text != "python" and not is_dependency_noise(name_text):
                        external_packages[name_text] += manifest_weight
        elif rel_path.name.startswith("requirements"):
            try:
                for name in parse_requirements(abs_path.read_text(encoding="utf-8")):
                    if not is_dependency_noise(name):
                        external_packages[name] += manifest_weight
            except OSError:
                continue
        elif rel_path.name == "go.mod":
            try:
                for name in parse_go_mod(abs_path.read_text(encoding="utf-8")):
                    if not is_dependency_noise(name):
                        external_packages[name] += manifest_weight
            except OSError:
                continue
        elif rel_path.name == "Cargo.toml":
            payload = parse_toml(abs_path)
            dependencies = payload.get("dependencies", {}) if isinstance(payload, dict) else {}
            if isinstance(dependencies, dict):
                for name in dependencies.keys():
                    name_text = str(name)
                    if not is_dependency_noise(name_text):
                        external_packages[name_text] += manifest_weight

    scanned_files = 0
    for path in paths:
        if scanned_files >= MAX_SCANNED_SOURCE_FILES:
            break
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        abs_path = repo_root / path
        try:
            if abs_path.stat().st_size > MAX_SOURCE_FILE_BYTES:
                continue
            text = abs_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scanned_files += 1

        if path.suffix.lower() == ".py":
            for match in PYTHON_IMPORT_RE.findall(text):
                prefix = match.split(".")[0]
                if prefix in package_prefixes:
                    internal_modules[collapse_internal_module(match, "python")] += 1
        elif path.suffix.lower() in {".js", ".jsx", ".ts", ".tsx"}:
            for match in JS_IMPORT_RE.findall(text):
                if match.startswith(("./", "../")):
                    continue
                prefix = match.split("/")[0].replace("@", "")
                if prefix in package_prefixes:
                    internal_modules[collapse_internal_module(match, "javascript")] += 1
        elif path.suffix.lower() == ".go":
            if "import" not in text:
                continue
            for match in GO_IMPORT_RE.findall(text):
                prefix = match.split("/")[-1]
                if prefix in package_prefixes:
                    internal_modules[collapse_internal_module(match, "go")] += 1

    if not external_packages and not internal_modules:
        return None

    payload: dict[str, list[str]] = {}
    if internal_modules:
        payload["internal_modules"] = [
            name
            for name, _count in sorted(internal_modules.items(), key=lambda item: (-item[1], item[0]))[:internal_budget]
        ]
    if external_packages:
        payload["external_packages"] = [
            name
            for name, _count in sorted(external_packages.items(), key=lambda item: (-item[1], item[0]))[:external_budget]
        ]
    return payload


def build_orientation_hints(
    entrypoints: list[dict[str, Any]],
    module_groups: list[dict[str, Any]],
    config_files: list[dict[str, str]],
    manifests: list[dict[str, str]],
    paths: list[Path],
) -> dict[str, list[str]]:
    likely_first_read: list[str] = []
    broad_repo = len(entrypoints) >= 6 and len(module_groups) >= 5
    source_dir_counts = build_source_dir_counts(paths)

    first_read_entry_budget = 2 if broad_repo else 3
    first_read_group_budget = 3 if broad_repo else 3

    def group_first_read_score(group: dict[str, Any]) -> tuple[int, str]:
        primary_path = Path(group["paths"][0])
        labels = path_part_labels(primary_path)
        score = orientation_score(primary_path, prefer_runtime=False)
        score += frontend_surface_boost(
            primary_path,
            manifests=manifests,
            config_files=config_files,
            source_dir_counts=source_dir_counts,
            paths=paths,
        )
        if len(primary_path.parts) >= 2:
            score += 4
        if not any(label in GENERIC_GROUP_TOKENS for label in labels):
            score += 5
        score -= sum(4 for label in labels if label in GENERIC_GROUP_TOKENS)
        if group.get("confidence") == "high":
            score += 1
        return score, group["paths"][0]

    prioritized_groups = (
        sorted(module_groups, key=lambda group: (-group_first_read_score(group)[0], group_first_read_score(group)[1]))
        if broad_repo
        else module_groups
    )

    for entrypoint in entrypoints[:first_read_entry_budget]:
        if entrypoint["path"] not in likely_first_read:
            likely_first_read.append(entrypoint["path"])
    for group in prioritized_groups[:first_read_group_budget]:
        for path in group["paths"]:
            if path not in likely_first_read:
                likely_first_read.append(path)
                if broad_repo and len(likely_first_read) >= 5:
                    break
        if broad_repo and len(likely_first_read) >= 5:
            break
    if broad_repo:
        for entrypoint in entrypoints[first_read_entry_budget:]:
            if entrypoint["path"] not in likely_first_read:
                likely_first_read.append(entrypoint["path"])
            if len(likely_first_read) >= 6:
                break
    else:
        for group in prioritized_groups[first_read_group_budget:3]:
            for path in group["paths"]:
                if path not in likely_first_read:
                    likely_first_read.append(path)

    likely_runtime_surfaces: list[str] = []
    for entrypoint in entrypoints[:4]:
        if entrypoint["path"] not in likely_runtime_surfaces:
            likely_runtime_surfaces.append(entrypoint["path"])
    is_helm_repo = any(item["kind"] == "helm_chart_manifest" for item in manifests)
    if not entrypoints and is_helm_repo:
        # Helm chart repos: no process entrypoints; chart roots are the deployment surfaces
        for group in module_groups[:6]:
            for path in group["paths"]:
                if path not in likely_runtime_surfaces:
                    likely_runtime_surfaces.append(path)
    else:
        preferred_config_kinds = {"runtime_config", "framework_config", "env_example", "typescript_config"}
        prioritized_configs = sorted(
            [item for item in config_files if item["kind"] in preferred_config_kinds],
            key=lambda item: (-orientation_score(Path(item["path"]), prefer_runtime=True), item["path"]),
        )
        non_ci_configs = [item for item in config_files if item["kind"] != "ci_workflow"]
        fallback_configs = prioritized_configs if prioritized_configs else non_ci_configs
        for config in fallback_configs[:4]:
            if config["path"] not in likely_runtime_surfaces:
                likely_runtime_surfaces.append(config["path"])

    return {
        "likely_first_read": likely_first_read[:6],
        "likely_runtime_surfaces": likely_runtime_surfaces[:6],
    }


def build_limitations(
    entrypoints: list[dict[str, Any]],
    module_groups: list[dict[str, Any]],
    dependency_signals: dict[str, list[str]] | None,
    scanned_file_count: int,
) -> list[str]:
    limitations = [
        "module groups are heuristic directory-level clusters",
        "no behavioral, failure-mode, or cross-repo claims are emitted",
    ]
    if any(item["confidence"] == "medium" for item in entrypoints):
        limitations.append("some entrypoints come from filename or manifest heuristics")
    if dependency_signals is None:
        limitations.append("dependency and import hints were omitted where cheap signals were weak")
    if scanned_file_count >= MAX_SCANNED_SOURCE_FILES:
        limitations.append("import scanning was capped to keep the pre-pass cheap and deterministic")
    return limitations


def analyze_repo(
    workspace_root: Path,
    repo_root: Path,
    batch_id: str,
    clone_manifest_rel: str,
    github_full_name: str,
    file_stem: str,
    node_id: str,
    output_rel: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    rel_paths = iter_repo_files(repo_root)
    manifests = collect_manifest_signals(rel_paths)
    config_files = collect_config_signals(rel_paths)
    languages = detect_languages(rel_paths, manifests)
    package_roots = choose_package_roots(repo_root, rel_paths, manifests, config_files)
    entrypoints = choose_entrypoints(repo_root, rel_paths, manifests)
    module_groups = choose_module_groups(rel_paths, package_roots, manifests, config_files)
    dependency_signals = collect_dependency_signals(
        repo_root,
        manifests,
        rel_paths,
        package_roots,
        entrypoints,
        module_groups,
        languages,
    )
    signals_used = ["filesystem", "manifest", "entrypoint", "config_routing"]
    if dependency_signals is not None:
        signals_used.append("imports")

    source_files_scanned = sum(1 for path in rel_paths if path.suffix.lower() in SOURCE_EXTENSIONS)

    artifact: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "repo": {
            "github_full_name": github_full_name,
            "node_id": node_id,
            "file_stem": file_stem,
        },
        "artifact": {
            "generated_at_utc": utc_now(),
            "stage": STAGE_NAME,
            "mode": MODE_NAME,
            "output_file": output_rel,
        },
        "batch": {
            "batch_id": batch_id,
            "clone_manifest": clone_manifest_rel,
        },
        "source": {
            "repo_root": str(repo_root.resolve()),
            "languages": languages,
        },
        "signals_used": signals_used,
        "package_roots": package_roots,
        "entrypoints": entrypoints,
        "module_groups": module_groups,
        "filesystem_signals": {
            "manifests": manifests,
            "config_files": config_files,
        },
        "orientation_hints": build_orientation_hints(entrypoints, module_groups, config_files, manifests, rel_paths),
        "limitations": build_limitations(entrypoints, module_groups, dependency_signals, source_files_scanned),
    }
    if dependency_signals is not None:
        artifact["dependency_signals"] = dependency_signals

    validation = validate_artifact(artifact)
    metadata = {
        "repo_root": str(repo_root),
        "total_files_seen": len(rel_paths),
        "source_files_seen": source_files_scanned,
        "validation": validation,
    }
    return artifact, metadata


def validate_claim_entries(items: list[dict[str, Any]], required_fields: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    for index, item in enumerate(items):
        for field in required_fields:
            if not item.get(field):
                errors.append(f"entry[{index}] missing {field}")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"entry[{index}] missing evidence")
    return errors


def validate_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    forbidden_sections = [
        "troubleshooting",
        "failure_modes",
        "implementation_patterns",
        "common_tasks",
        "risk_assessment",
    ]
    required_top_level = [
        "schema_version",
        "repo",
        "artifact",
        "batch",
        "source",
        "signals_used",
        "package_roots",
        "entrypoints",
        "module_groups",
        "filesystem_signals",
        "orientation_hints",
        "limitations",
    ]
    for field in required_top_level:
        if field not in artifact:
            errors.append(f"missing top-level field: {field}")

    if artifact.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version mismatch")
    if artifact.get("artifact", {}).get("stage") != STAGE_NAME:
        errors.append("artifact.stage mismatch")

    output_file = artifact.get("artifact", {}).get("output_file", "")
    if not isinstance(output_file, str) or not output_file.startswith(f"{DEFAULT_OUTPUT_DIR}/"):
        errors.append("artifact.output_file outside reports/ws6_structural_prepass")

    if not isinstance(artifact.get("signals_used"), list) or not artifact["signals_used"]:
        errors.append("signals_used must be a non-empty list")

    package_roots = artifact.get("package_roots", [])
    entrypoints = artifact.get("entrypoints", [])
    module_groups = artifact.get("module_groups", [])
    if not isinstance(package_roots, list) or not package_roots:
        errors.append("package_roots must be non-empty")
    else:
        errors.extend(validate_claim_entries(package_roots, ("path",)))
    if not isinstance(entrypoints, list):
        errors.append("entrypoints must be a list")
    else:
        errors.extend(validate_claim_entries(entrypoints, ("path", "kind", "confidence")))
    if not isinstance(module_groups, list) or not module_groups:
        errors.append("module_groups must be non-empty")
    else:
        errors.extend(validate_claim_entries(module_groups, ("name", "paths", "confidence")))

    filesystem_signals = artifact.get("filesystem_signals", {})
    if "manifests" not in filesystem_signals or "config_files" not in filesystem_signals:
        errors.append("filesystem_signals missing manifests or config_files")

    orientation_hints = artifact.get("orientation_hints", {})
    if "likely_first_read" not in orientation_hints or "likely_runtime_surfaces" not in orientation_hints:
        errors.append("orientation_hints missing required lists")

    limitations = artifact.get("limitations", [])
    if not isinstance(limitations, list) or not limitations:
        errors.append("limitations must be non-empty")

    forbidden_present = [field for field in forbidden_sections if field in artifact]
    if forbidden_present:
        errors.append(f"forbidden sections present: {', '.join(forbidden_present)}")

    return {
        "valid": not errors,
        "errors": errors,
        "forbidden_sections_present": forbidden_present,
        "consumption_boundary": {
            "non_canonical_output_only": True,
            "writes_canonical_files": False,
            "ws6_canonical_emitter_unchanged": True,
        },
    }


def select_repos(repos: list[dict[str, Any]], repo_filters: list[str]) -> list[dict[str, Any]]:
    if not repo_filters:
        return repos
    wanted = set(repo_filters)
    return [entry for entry in repos if entry.get("github_full_name") in wanted]


def run(
    workspace_root: str,
    clone_manifest_path: str,
    output_dir: str,
    input_manifest_path: str | None,
    clone_workdir_override: str | None,
    repo_filters: list[str],
) -> int:
    ws_root = Path(workspace_root).resolve()
    clone_manifest_arg = Path(clone_manifest_path)
    clone_manifest_abs = clone_manifest_arg if clone_manifest_arg.is_absolute() else (ws_root / clone_manifest_arg).resolve()
    if not clone_manifest_abs.exists():
        print(f"ERROR: clone manifest not found: {clone_manifest_abs}", file=sys.stderr)
        return 2

    clone_manifest = load_yaml(clone_manifest_abs) or {}
    repos = clone_manifest.get("repos", [])
    if not isinstance(repos, list):
        print("ERROR: clone manifest missing repos list", file=sys.stderr)
        return 2

    batch_id = clone_manifest.get("batch_id")
    if not isinstance(batch_id, str) or not batch_id:
        print("ERROR: clone manifest missing batch_id", file=sys.stderr)
        return 2

    selected_repos = select_repos(repos, repo_filters)
    if not selected_repos:
        print("ERROR: no repos selected from clone manifest", file=sys.stderr)
        return 2

    input_manifest_abs: Path | None = None
    if input_manifest_path:
        candidate = Path(input_manifest_path)
        input_manifest_abs = candidate if candidate.is_absolute() else (ws_root / candidate).resolve()
    input_lookup = load_input_manifest_lookup(input_manifest_abs)
    canonical_lookup = load_canonical_repo_lookup(ws_root)
    output_root = ws_root / output_dir / batch_id
    clone_workdir_path = None
    if clone_workdir_override:
        candidate = Path(clone_workdir_override)
        clone_workdir_path = candidate if candidate.is_absolute() else (ws_root / candidate).resolve()

    clone_manifest_rel = ensure_repo_relative(clone_manifest_abs.relative_to(ws_root))
    repo_results: list[dict[str, Any]] = []
    generated_count = 0
    failed_count = 0
    validation_failed = 0

    for entry in selected_repos:
        github_full_name = entry.get("github_full_name")
        if not isinstance(github_full_name, str) or "/" not in github_full_name:
            repo_results.append({
                "github_full_name": github_full_name,
                "status": "failed",
                "reason": "invalid_github_full_name",
            })
            failed_count += 1
            continue

        repo_root = resolve_repo_root(ws_root, clone_manifest, entry, clone_workdir_path)
        if repo_root is None:
            repo_results.append({
                "github_full_name": github_full_name,
                "status": "failed",
                "reason": "repo_root_not_found",
            })
            failed_count += 1
            continue

        input_entry = input_lookup.get(github_full_name, {})
        canonical_entry = canonical_lookup.get(github_full_name, {})
        file_stem = (
            str(input_entry.get("file_stem") or "")
            or str(canonical_entry.get("file_stem") or "")
            or normalize_file_stem(github_full_name)
        )
        node_id = (
            str(canonical_entry.get("node_id") or "")
            or f"repo::{github_full_name}"
        )
        output_rel = f"{output_dir}/{batch_id}/{file_stem}.yaml"

        artifact, metadata = analyze_repo(
            workspace_root=ws_root,
            repo_root=repo_root,
            batch_id=batch_id,
            clone_manifest_rel=clone_manifest_rel,
            github_full_name=github_full_name,
            file_stem=file_stem,
            node_id=node_id,
            output_rel=output_rel,
        )
        output_path = ws_root / output_rel
        dump_yaml(output_path, artifact)
        generated_count += 1
        if not metadata["validation"]["valid"]:
            validation_failed += 1

        repo_results.append({
            "github_full_name": github_full_name,
            "file_stem": file_stem,
            "status": "ok" if metadata["validation"]["valid"] else "invalid",
            "output_file": output_rel,
            "repo_root": metadata["repo_root"],
            "source_files_seen": metadata["source_files_seen"],
            "total_files_seen": metadata["total_files_seen"],
            "validation": metadata["validation"],
        })

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "batch_id": batch_id,
        "stage": STAGE_NAME,
        "clone_manifest": clone_manifest_rel,
        "input_manifest": ensure_repo_relative(input_manifest_abs.relative_to(ws_root)) if input_manifest_abs and input_manifest_abs.exists() else None,
        "output_dir": f"{output_dir}/{batch_id}",
        "repo_filters": repo_filters or None,
        "summary": {
            "repos_selected": len(selected_repos),
            "repos_generated": generated_count,
            "repos_failed": failed_count,
            "repos_invalid": validation_failed,
            "gate_ready": failed_count == 0 and validation_failed == 0 and generated_count > 0,
        },
        "boundary_checks": {
            "non_canonical_output_only": True,
            "writes_outside_reports": False,
            "canonical_files_written": [],
        },
        "repos": repo_results,
    }
    summary_path = output_root / "summary.yaml"
    dump_yaml(summary_path, summary)

    print(
        "\n".join(
            [
                "WS6_STRUCTURAL_PREPASS_SUMMARY",
                f"  batch_id: {batch_id}",
                f"  clone_manifest: {clone_manifest_rel}",
                f"  repos_selected: {len(selected_repos)}",
                f"  repos_generated: {generated_count}",
                f"  repos_failed: {failed_count}",
                f"  repos_invalid: {validation_failed}",
                f"  output_dir: {output_dir}/{batch_id}",
                f"  summary_file: {ensure_repo_relative(summary_path.relative_to(ws_root))}",
                f"  gate_ready: {str(summary['summary']['gate_ready']).lower()}",
            ]
        )
    )

    return 0 if summary["summary"]["gate_ready"] else 1


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate narrow WS6 structural pre-pass artifacts.")
    parser.add_argument("--workspace-root", default=".", help="Repo root directory")
    parser.add_argument("--clone-manifest", required=True, help="Path to WS6 clone manifest")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Report directory for structural pre-pass artifacts",
    )
    parser.add_argument(
        "--input-manifest",
        default=None,
        help="Optional WS5 input manifest for explicit file_stem lookup",
    )
    parser.add_argument(
        "--clone-workdir",
        default=None,
        help="Optional override for locating local clones when manifest paths are stale",
    )
    parser.add_argument(
        "--repo",
        action="append",
        default=[],
        help="Limit processing to a specific github_full_name; may be repeated",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()
    return run(
        workspace_root=args.workspace_root,
        clone_manifest_path=args.clone_manifest,
        output_dir=args.output_dir,
        input_manifest_path=args.input_manifest,
        clone_workdir_override=args.clone_workdir,
        repo_filters=args.repo,
    )


if __name__ == "__main__":
    raise SystemExit(main())
