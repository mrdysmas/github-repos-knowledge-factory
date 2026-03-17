#!/usr/bin/env python3
"""Skill-facing adapter for query_master loader.

This is a compact facade intended for skills/agents:
- Query mode: run one query_master command with compact output.
- Recipe mode: run multi-step workflows from workflow_recipes in the machine spec.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
from typing import Any

from query_master_loader import (
    QueryMasterLoader,
    QueryMasterLoaderError,
    QueryMasterRunResult,
    parse_key_value_pairs,
)


def _coerce_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


class QueryMasterSkillAdapter:
    def __init__(self, loader: QueryMasterLoader) -> None:
        self.loader = loader

    @staticmethod
    def _agent_state(run: QueryMasterRunResult) -> str:
        if run.ok:
            return "ok"
        if run.error_kind in {"knowledge_db_missing", "knowledge_db_stale"}:
            return "setup_needed"
        if run.error_kind is None:
            return "recovery_recommended"
        return "query_error"

    @staticmethod
    def _is_empty_success_data(data: Any) -> bool:
        if data == [] or data == {}:
            return True
        if not isinstance(data, dict):
            return False

        list_values = [value for value in data.values() if isinstance(value, list)]
        if not list_values:
            return False
        if any(value for value in list_values):
            return False

        nested_dict_values = [value for value in data.values() if isinstance(value, dict)]
        if any(value for value in nested_dict_values):
            return False

        return True

    @staticmethod
    def _compact_result(run: QueryMasterRunResult) -> dict[str, Any]:
        parsed = run.parsed if isinstance(run.parsed, (dict, list)) else None
        error_message: str | None = None
        if not run.ok:
            if isinstance(run.parsed, dict):
                maybe_error = run.parsed.get("error")
                if isinstance(maybe_error, str):
                    error_message = maybe_error
            if error_message is None and run.stdout.strip():
                lines = [line.strip() for line in run.stdout.splitlines() if line.strip()]
                error_message = lines[0] if lines else None

        agent_state = QueryMasterSkillAdapter._agent_state(run)
        hint = None
        if run.ok and QueryMasterSkillAdapter._is_empty_success_data(parsed):
            hint = (
                "No results. Try broader search terms, a different predicate, or "
                "search --term <keyword> to find candidates first."
            )

        return {
            "ok": run.ok,
            "agent_state": agent_state,
            "data": parsed if run.ok else None,
            "error_kind": run.error_kind,
            "error": error_message,
            "fix": run.recommended_fix,
            "hint": hint,
            "meta": {
                "command": run.command,
                "source": run.source,
                "exit_code": run.exit_code,
                "query_ms": run.query_ms,
            },
        }

    def run_query(self, command: str, source: str | None = None, **kwargs: Any) -> dict[str, Any]:
        run = self.loader.run(command=command, source=source, **kwargs)
        return self._compact_result(run)

    def list_recipes(self) -> list[dict[str, Any]]:
        recipes = self.loader.spec.get("workflow_recipes", [])
        out: list[dict[str, Any]] = []
        if not isinstance(recipes, list):
            return out
        for row in recipes:
            if not isinstance(row, dict):
                continue
            steps = row.get("steps")
            out.append(
                {
                    "name": row.get("name"),
                    "intent": row.get("intent"),
                    "recommended_when": row.get("recommended_when"),
                    "step_count": len(steps) if isinstance(steps, list) else 0,
                    "steps": steps if isinstance(steps, list) else [],
                }
            )
        return out

    @staticmethod
    def _fill_placeholders(template: str, variables: dict[str, Any]) -> str:
        pattern = re.compile(r"<([A-Za-z_][A-Za-z0-9_]*)>")

        def _replace(match: re.Match[str]) -> str:
            key = match.group(1)
            if key not in variables:
                raise QueryMasterLoaderError(
                    f"Missing recipe variable <{key}>. Supply it via --var {key}=VALUE."
                )
            return str(variables[key])

        return pattern.sub(_replace, template)

    def _parse_recipe_step(self, step_command: str, variables: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
        resolved_step = self._fill_placeholders(step_command, variables)
        tokens = shlex.split(resolved_step)
        if not tokens:
            raise QueryMasterLoaderError("Empty recipe step command.")

        known_commands = set(self.loader.spec.get("commands", {}).keys())
        command_index: int | None = None
        for idx, token in enumerate(tokens):
            if token in known_commands:
                command_index = idx
                break

        if command_index is None:
            raise QueryMasterLoaderError(
                f"Could not locate query_master command in recipe step: {resolved_step!r}"
            )

        command = tokens[command_index]
        tail = tokens[command_index + 1 :]
        args: dict[str, Any] = {}

        idx = 0
        while idx < len(tail):
            token = tail[idx]
            if not token.startswith("--"):
                raise QueryMasterLoaderError(
                    f"Unexpected token in recipe step after command {command!r}: {token!r}"
                )
            if idx + 1 >= len(tail):
                raise QueryMasterLoaderError(
                    f"Missing value for flag {token!r} in recipe step {resolved_step!r}"
                )
            value_token = tail[idx + 1]
            if value_token.startswith("--"):
                raise QueryMasterLoaderError(
                    f"Missing value for flag {token!r} in recipe step {resolved_step!r}"
                )

            key = token.lstrip("-").replace("-", "_")
            args[key] = _coerce_scalar(value_token)
            idx += 2

        return command, args, resolved_step

    def run_recipe(
        self,
        recipe_name: str,
        recipe_vars: dict[str, Any] | None = None,
        source: str | None = None,
        stop_on_error: bool = True,
    ) -> dict[str, Any]:
        rows = self.loader.spec.get("workflow_recipes", [])
        if not isinstance(rows, list):
            raise QueryMasterLoaderError("Machine reference has no workflow_recipes list.")

        recipe: dict[str, Any] | None = None
        for row in rows:
            if isinstance(row, dict) and row.get("name") == recipe_name:
                recipe = row
                break
        if recipe is None:
            known = [row.get("name") for row in rows if isinstance(row, dict)]
            raise QueryMasterLoaderError(
                f"Unknown recipe {recipe_name!r}. Known recipes: {', '.join(map(str, known))}"
            )

        steps = recipe.get("steps")
        if not isinstance(steps, list):
            raise QueryMasterLoaderError(f"Recipe {recipe_name!r} has invalid/missing steps.")

        variables = recipe_vars or {}
        step_results: list[dict[str, Any]] = []
        overall_ok = True
        overall_agent_state = "ok"

        for step in steps:
            if not isinstance(step, str):
                continue
            command, kwargs, resolved_step = self._parse_recipe_step(step, variables)
            run = self.loader.run(command=command, source=source, **kwargs)
            compact = self._compact_result(run)
            compact["step"] = resolved_step
            compact["args"] = kwargs
            step_results.append(compact)

            if not run.ok:
                overall_ok = False
                overall_agent_state = str(compact.get("agent_state") or "recovery_recommended")
                if stop_on_error:
                    break

        return {
            "ok": overall_ok,
            "agent_state": overall_agent_state,
            "recipe": recipe_name,
            "intent": recipe.get("intent"),
            "source": source or self.loader.spec.get("global", {}).get("default_source"),
            "stop_on_error": stop_on_error,
            "steps_total": len(steps),
            "steps_completed": len(step_results),
            "steps": step_results,
        }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Skill-facing adapter for query_master workflows.")
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
    parser.add_argument("--source", default=None, choices=["sqlite", "yaml"], help="Optional data source override.")

    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--command", help="Run one query_master command in compact adapter mode.")
    mode_group.add_argument("--recipe", help="Run a named workflow recipe from machine reference.")
    mode_group.add_argument("--list-recipes", action="store_true", help="List available workflow recipes.")

    parser.add_argument(
        "--arg",
        action="append",
        default=[],
        help="Command arg KEY=VALUE for --command mode (snake_case keys; e.g. id=maxkb).",
    )
    parser.add_argument(
        "--var",
        action="append",
        default=[],
        help="Recipe placeholder KEY=VALUE for --recipe mode (for example repo=maxkb).",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="In --recipe mode, continue executing subsequent steps after failures.",
    )
    parser.add_argument("--json-indent", type=int, default=2, help="Indentation for JSON output.")
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        loader = QueryMasterLoader(
            workspace_root=args.workspace_root,
            machine_reference_path=args.machine_reference,
            query_script_path=args.query_script,
            python_executable=args.python_bin,
        )
        adapter = QueryMasterSkillAdapter(loader=loader)

        if args.list_recipes:
            payload = {"ok": True, "recipes": adapter.list_recipes()}
            print(json.dumps(payload, indent=args.json_indent, sort_keys=False))
            return 0

        if args.command:
            cmd_args = parse_key_value_pairs(args.arg)
            result = adapter.run_query(command=args.command, source=args.source, **cmd_args)
            print(json.dumps(result, indent=args.json_indent, sort_keys=False))
            return 0 if result.get("ok") else int(result.get("meta", {}).get("exit_code") or 1)

        if args.recipe:
            recipe_vars = parse_key_value_pairs(args.var)
            result = adapter.run_recipe(
                recipe_name=args.recipe,
                recipe_vars=recipe_vars,
                source=args.source,
                stop_on_error=not args.continue_on_error,
            )
            print(json.dumps(result, indent=args.json_indent, sort_keys=False))
            if result.get("ok"):
                return 0
            steps = result.get("steps", [])
            if isinstance(steps, list) and steps:
                last = steps[-1]
                if isinstance(last, dict):
                    meta = last.get("meta")
                    if isinstance(meta, dict):
                        return int(meta.get("exit_code") or 1)
            return 1

        return 2

    except QueryMasterLoaderError as exc:
        payload = {
            "ok": False,
            "agent_state": "query_error",
            "data": None,
            "error_kind": None,
            "error_type": "adapter_validation_error",
            "error": str(exc),
            "fix": None,
            "hint": None,
            "meta": None,
        }
        print(json.dumps(payload, indent=args.json_indent, sort_keys=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
