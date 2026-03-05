#!/usr/bin/env python3
"""Contract-driven loader for tools/query_master.py.

This module is built for agent workflows:
- Loads docs/query_master_reference.machine.yaml as the command contract.
- Validates command/source/arguments before invoking query_master.py.
- Normalizes sqlite timing trailer (# query_ms: N) for robust YAML parsing.
- Maps known CLI error signatures to stable error kinds.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class QueryMasterRunResult:
    ok: bool
    exit_code: int
    command: str
    source: str
    argv: list[str]
    parsed: Any | None
    query_ms: int | None
    error_kind: str | None
    recommended_fix: str | None
    stdout: str
    stderr: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "exit_code": self.exit_code,
            "command": self.command,
            "source": self.source,
            "argv": self.argv,
            "query_ms": self.query_ms,
            "error_kind": self.error_kind,
            "recommended_fix": self.recommended_fix,
            "parsed": self.parsed,
            "stdout": self.stdout,
            "stderr": self.stderr,
        }


class QueryMasterLoaderError(RuntimeError):
    """Raised for local validation/setup issues prior to command execution."""


class QueryMasterLoader:
    def __init__(
        self,
        workspace_root: str | Path = ".",
        machine_reference_path: str | Path = "docs/query_master_reference.machine.yaml",
        query_script_path: str | Path = "tools/query_master.py",
        python_executable: str = "python3",
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.machine_reference_path = (self.workspace_root / machine_reference_path).resolve()
        self.query_script_path = (self.workspace_root / query_script_path).resolve()
        self.python_executable = python_executable
        self._spec = self._load_spec()

    def _load_spec(self) -> dict[str, Any]:
        if not self.machine_reference_path.exists():
            raise QueryMasterLoaderError(f"Machine reference not found: {self.machine_reference_path}")
        loaded = yaml.safe_load(self.machine_reference_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise QueryMasterLoaderError(f"Machine reference is not a YAML mapping: {self.machine_reference_path}")
        if loaded.get("artifact_type") != "query_master_reference_machine":
            raise QueryMasterLoaderError(
                f"Unexpected artifact_type in machine reference: {loaded.get('artifact_type')!r}"
            )
        if not isinstance(loaded.get("commands"), dict):
            raise QueryMasterLoaderError("Machine reference missing 'commands' mapping.")
        return loaded

    @property
    def spec(self) -> dict[str, Any]:
        return self._spec

    def _command_spec(self, command: str) -> dict[str, Any]:
        commands = self._spec.get("commands", {})
        spec = commands.get(command)
        if not isinstance(spec, dict):
            known = ", ".join(sorted(commands.keys()))
            raise QueryMasterLoaderError(f"Unknown command: {command!r}. Known commands: {known}")
        return spec

    @staticmethod
    def _canonical_arg_key(flag_name: str) -> str:
        # --workspace-root -> workspace_root
        return flag_name.lstrip("-").replace("-", "_")

    def _validate_inputs(self, command: str, source: str, args: dict[str, Any]) -> dict[str, Any]:
        spec = self._command_spec(command)
        supported_sources = spec.get("supported_sources", [])
        if source not in supported_sources:
            raise QueryMasterLoaderError(
                f"Command {command!r} does not support source {source!r}. "
                f"Supported: {', '.join(map(str, supported_sources))}"
            )

        arg_specs = spec.get("arguments", [])
        normalized: dict[str, Any] = {}
        known_keys: set[str] = set()

        for arg_spec in arg_specs:
            if not isinstance(arg_spec, dict):
                continue
            name = str(arg_spec.get("name") or "")
            if not name.startswith("--"):
                continue
            canonical = self._canonical_arg_key(name)
            known_keys.add(canonical)
            required = bool(arg_spec.get("required"))
            default = arg_spec.get("default")

            if canonical in args:
                value = args[canonical]
            else:
                value = default

            if required and (value is None or value == ""):
                raise QueryMasterLoaderError(f"Missing required argument for {command!r}: {name}")

            if value is not None:
                normalized[canonical] = value

        unknown = sorted(set(args.keys()) - known_keys)
        if unknown:
            raise QueryMasterLoaderError(
                f"Unknown argument(s) for {command!r}: {', '.join(unknown)}. "
                f"Known: {', '.join(sorted(known_keys)) or '(none)'}"
            )

        # Enum and integer checks (subset of machine reference schema used here)
        for arg_spec in arg_specs:
            if not isinstance(arg_spec, dict):
                continue
            name = str(arg_spec.get("name") or "")
            if not name.startswith("--"):
                continue
            canonical = self._canonical_arg_key(name)
            if canonical not in normalized:
                continue
            value = normalized[canonical]
            arg_type = str(arg_spec.get("type") or "")
            choices = arg_spec.get("choices")
            min_value = arg_spec.get("min")

            if arg_type == "enum":
                if value not in choices:
                    raise QueryMasterLoaderError(
                        f"Invalid value for {name}: {value!r}. Allowed: {choices}"
                    )
            elif arg_type == "integer":
                if not isinstance(value, int):
                    raise QueryMasterLoaderError(f"Expected integer for {name}, got {type(value).__name__}")
                if isinstance(min_value, int) and value < min_value:
                    raise QueryMasterLoaderError(f"Invalid value for {name}: {value} < min {min_value}")

        return normalized

    def _build_argv(self, command: str, source: str, args: dict[str, Any]) -> list[str]:
        spec = self._command_spec(command)
        argv: list[str] = [
            self.python_executable,
            self.query_script_path.as_posix(),
            "--workspace-root",
            self.workspace_root.as_posix(),
            "--source",
            source,
            command,
        ]
        for arg_spec in spec.get("arguments", []):
            if not isinstance(arg_spec, dict):
                continue
            name = str(arg_spec.get("name") or "")
            if not name.startswith("--"):
                continue
            canonical = self._canonical_arg_key(name)
            if canonical not in args:
                continue
            value = args[canonical]
            if value is None:
                continue
            argv.append(name)
            argv.append(str(value))
        return argv

    @staticmethod
    def _extract_query_ms(stdout: str) -> tuple[str, int | None]:
        lines = stdout.splitlines()
        if not lines:
            return stdout, None
        last = lines[-1].strip()
        match = re.match(r"^# query_ms:\s+(\d+)$", last)
        if not match:
            return stdout, None
        query_ms = int(match.group(1))
        body = "\n".join(lines[:-1]).rstrip("\n")
        return body, query_ms

    def _detect_error_signature(self, full_text: str, exit_code: int) -> tuple[str | None, str | None]:
        signatures = self._spec.get("error_signatures", [])
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        for signature in signatures:
            if not isinstance(signature, dict):
                continue
            declared_exit = signature.get("exit_code")
            if isinstance(declared_exit, int) and declared_exit != exit_code:
                continue

            starts_with = signature.get("starts_with")
            pattern = signature.get("pattern")

            matched = False
            if isinstance(starts_with, str) and starts_with:
                matched = any(line.startswith(starts_with) for line in lines)
            elif isinstance(pattern, str) and pattern:
                try:
                    regex = re.compile(pattern)
                except re.error:
                    regex = None
                if regex is not None:
                    matched = any(regex.search(line) for line in lines)

            if matched:
                return signature.get("key"), signature.get("recommended_fix")
        return None, None

    def run(self, command: str, source: str | None = None, **kwargs: Any) -> QueryMasterRunResult:
        chosen_source = source or str(self._spec.get("global", {}).get("default_source") or "sqlite")
        normalized_args = self._validate_inputs(command=command, source=chosen_source, args=kwargs)
        argv = self._build_argv(command=command, source=chosen_source, args=normalized_args)

        completed = subprocess.run(
            argv,
            cwd=self.workspace_root.as_posix(),
            capture_output=True,
            text=True,
            check=False,
        )

        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        stripped_stdout, query_ms = self._extract_query_ms(stdout)

        parsed: Any | None = None
        if stripped_stdout.strip():
            try:
                parsed = yaml.safe_load(stripped_stdout)
            except yaml.YAMLError:
                parsed = None

        full_text = "\n".join([text for text in [stdout, stderr] if text.strip()])
        error_kind, recommended_fix = self._detect_error_signature(full_text=full_text, exit_code=completed.returncode)

        return QueryMasterRunResult(
            ok=completed.returncode == 0,
            exit_code=completed.returncode,
            command=command,
            source=chosen_source,
            argv=argv,
            parsed=parsed,
            query_ms=query_ms,
            error_kind=error_kind,
            recommended_fix=recommended_fix,
            stdout=stdout,
            stderr=stderr,
        )


def parse_key_value_pairs(entries: list[str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for entry in entries:
        if "=" not in entry:
            raise QueryMasterLoaderError(f"Invalid --arg value {entry!r}; expected KEY=VALUE")
        key, raw_value = entry.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key:
            raise QueryMasterLoaderError(f"Invalid --arg value {entry!r}; empty KEY")

        # Lightweight coercion: int and bool when obvious; else string.
        lowered = raw_value.lower()
        if lowered == "true":
            value: Any = True
        elif lowered == "false":
            value = False
        elif re.match(r"^-?\d+$", raw_value):
            value = int(raw_value)
        else:
            value = raw_value
        parsed[key] = value
    return parsed


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Contract-driven loader for tools/query_master.py")
    parser.add_argument("--workspace-root", default=".", help="Workspace root path.")
    parser.add_argument(
        "--machine-reference",
        default="docs/query_master_reference.machine.yaml",
        help="Path to machine-readable query_master reference YAML.",
    )
    parser.add_argument(
        "--query-script",
        default="tools/query_master.py",
        help="Path to query_master.py script.",
    )
    parser.add_argument("--python-bin", default="python3", help="Python executable for query invocation.")
    parser.add_argument("--command", required=True, help="query_master command name.")
    parser.add_argument("--source", default=None, choices=["sqlite", "yaml"], help="Optional data source override.")
    parser.add_argument(
        "--arg",
        action="append",
        default=[],
        help="Command argument in KEY=VALUE form (use snake_case; e.g. id=maxkb or limit=5).",
    )
    parser.add_argument(
        "--json-indent",
        type=int,
        default=2,
        help="Indentation used when printing JSON result.",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        cmd_args = parse_key_value_pairs(args.arg)
        loader = QueryMasterLoader(
            workspace_root=args.workspace_root,
            machine_reference_path=args.machine_reference,
            query_script_path=args.query_script,
            python_executable=args.python_bin,
        )
        result = loader.run(command=args.command, source=args.source, **cmd_args)
        print(json.dumps(result.as_dict(), indent=args.json_indent, sort_keys=False))
        return 0 if result.ok else result.exit_code
    except QueryMasterLoaderError as exc:
        payload = {
            "ok": False,
            "error_type": "loader_validation_error",
            "error": str(exc),
        }
        print(json.dumps(payload, indent=args.json_indent, sort_keys=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
