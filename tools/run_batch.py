#!/usr/bin/env python3
"""Batch pipeline orchestrator: chains WS5 → WS4 → WS6 → WS7 from a single command.

Reads a batch_spec.yaml, runs each pipeline step as a subprocess,
evaluates gate reports between steps, and emits a machine-readable verdict.
"""

from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


STEPS = [
    {
        "name": "ws5",
        "label": "WS5 remote ingestion",
        "tool": "tools/ws5_remote_ingestion.py",
        "args_fn": lambda spec, ws_root: [
            "--workspace-root", ws_root,
            "--input", spec["manifest"],
        ],
    },
    {
        "name": "ws4",
        "label": "WS4 master compiler",
        "tool": "tools/ws4_master_compiler.py",
        "args_fn": lambda spec, ws_root: [
            "--workspace-root", ws_root,
        ],
    },
    {
        "name": "ws6_clone_prep",
        "label": "WS6 clone prep",
        "tool": "tools/ws6_clone_prep.py",
        "args_fn": lambda spec, ws_root: [
            "--workspace-root", ws_root,
            "--manifest", spec["manifest"],
            "--clone-workdir", str(Path(ws_root) / spec.get("clone_workdir", "workspace/clones")),
            "--size-limit-mb", str(spec.get("clone_size_limit_mb", 500)),
            "--batch-id", spec["batch_id"],
        ] + (["--cleanup"] if spec.get("clone_cleanup", False) else []),
    },
    {
        "name": "ws6",
        "label": "WS6 deep integrator",
        "tool": "tools/ws6_deep_integrator.py",
        "args_fn": lambda spec, ws_root: [
            "--workspace-root", ws_root,
            "--run-validation-suite",
        ],
    },
    {
        "name": "ws6_gate",
        "label": "WS6 gate evaluation",
        "gate": True,
    },
    {
        "name": "ws7",
        "label": "WS7 read model compiler",
        "tool": "tools/ws7_read_model_compiler.py",
        "args_fn": lambda spec, ws_root: [
            "--workspace-root", ws_root,
            "--force",
        ],
    },
    {
        "name": "ws7_gate",
        "label": "WS7 gate evaluation",
        "gate": True,
    },
]


def load_spec(spec_path: str) -> dict[str, Any]:
    path = Path(spec_path)
    if not path.exists():
        print(f"ERROR: spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(2)
    with open(path, encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    if not isinstance(spec, dict):
        print(f"ERROR: spec file is not a YAML mapping: {spec_path}", file=sys.stderr)
        sys.exit(2)
    for key in ("batch_id", "manifest"):
        if key not in spec:
            print(f"ERROR: spec missing required key: {key}", file=sys.stderr)
            sys.exit(2)
    return spec


def validate_manifest(spec: dict[str, Any], workspace_root: str) -> None:
    manifest_path = Path(workspace_root) / spec["manifest"]
    if not manifest_path.exists():
        print(f"ERROR: manifest not found: {manifest_path}", file=sys.stderr)
        sys.exit(2)


def run_tool(tool: str, args: list[str], workspace_root: str) -> subprocess.CompletedProcess:
    tool_path = str(Path(workspace_root) / tool)
    argv = ["python3", tool_path] + args
    return subprocess.run(
        argv,
        cwd=workspace_root,
        capture_output=True,
        text=True,
        check=False,
    )


def evaluate_ws6_gate(spec: dict[str, Any], workspace_root: str) -> dict[str, bool]:
    report_path = Path(workspace_root) / "reports" / "ws6_deep_integration" / "validation_runs.yaml"
    if not report_path.exists():
        print(f"ERROR: WS6 validation report not found: {report_path}", file=sys.stderr)
        return {}
    with open(report_path, encoding="utf-8") as f:
        report = yaml.safe_load(f)
    return report.get("gate_bools", {})


def evaluate_ws7_gate(spec: dict[str, Any], workspace_root: str) -> dict[str, str]:
    report_path = Path(workspace_root) / "reports" / "ws7_read_model" / "compile_log.yaml"
    if not report_path.exists():
        print(f"ERROR: WS7 compile log not found: {report_path}", file=sys.stderr)
        return {}
    with open(report_path, encoding="utf-8") as f:
        report = yaml.safe_load(f)
    gates = report.get("gates", {})
    return {name: gate.get("status", "unknown") for name, gate in gates.items()}


def build_verdict(
    batch_id: str,
    result: str,
    halted_at: str | None,
    ws6_gate_bools: dict[str, bool],
    ws7_gate_summary: dict[str, str],
    exit_code: int,
    step_logs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "batch_id": batch_id,
        "result": result,
        "halted_at": halted_at,
        "ws6_gate_bools": ws6_gate_bools,
        "ws7_gate_summary": ws7_gate_summary,
        "exit_code": exit_code,
        "step_logs": step_logs,
    }


def write_verdict(verdict: dict[str, Any], workspace_root: str) -> str:
    out_dir = Path(workspace_root) / "reports" / "run_batch"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{verdict['batch_id']}_verdict.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(verdict, f, default_flow_style=False, sort_keys=False)
    return str(out_path)


def truncate(text: str, max_lines: int = 30) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[-max_lines:]) + f"\n... (truncated, showing last {max_lines} of {len(lines)} lines)"


def run_batch(spec_path: str, workspace_root: str, dry_run: bool) -> int:
    spec = load_spec(spec_path)
    ws_root = str(Path(workspace_root).resolve())
    batch_id = spec["batch_id"]
    gates_config = spec.get("gates", {})

    validate_manifest(spec, ws_root)

    if dry_run:
        print(f"=== DRY RUN: batch {batch_id} ===")
        print(f"Workspace root: {ws_root}")
        print(f"Manifest: {spec['manifest']}")
        print(f"Gates config: {gates_config}")
        print()
        for step in STEPS:
            if step.get("gate"):
                print(f"  [{step['name']}] {step['label']}")
            else:
                args = step["args_fn"](spec, ws_root)
                print(f"  [{step['name']}] python3 {step['tool']} {' '.join(args)}")
        print()
        print("No tools executed (dry run).")
        return 0

    step_logs: list[dict[str, Any]] = []
    ws6_gate_bools: dict[str, bool] = {}
    ws7_gate_summary: dict[str, str] = {}

    for step in STEPS:
        name = step["name"]
        label = step["label"]

        # Gate evaluation steps
        if step.get("gate"):
            if name == "ws6_gate":
                print(f"--- {label} ---")
                ws6_gate_bools = evaluate_ws6_gate(spec, ws_root)
                fail_on_any_false = gates_config.get("ws6_fail_on_any_false", True)
                false_gates = [k for k, v in ws6_gate_bools.items() if v is False]
                step_log = {
                    "step": name,
                    "gate_bools": ws6_gate_bools,
                    "false_gates": false_gates,
                }
                step_logs.append(step_log)
                if false_gates:
                    print(f"  WS6 gate failures: {false_gates}")
                    if fail_on_any_false:
                        print("  HALTING: ws6_fail_on_any_false is true")
                        verdict = build_verdict(batch_id, "failed", "ws6_gate", ws6_gate_bools, ws7_gate_summary, 1, step_logs)
                        path = write_verdict(verdict, ws_root)
                        print(f"Verdict written to {path}")
                        print(yaml.dump(verdict, default_flow_style=False, sort_keys=False))
                        return 1
                    else:
                        print("  WARNING: WS6 gate failures present but ws6_fail_on_any_false is false, continuing")
                else:
                    print("  All WS6 gates passed")

            elif name == "ws7_gate":
                print(f"--- {label} ---")
                ws7_gate_summary = evaluate_ws7_gate(spec, ws_root)
                fail_on_any_non_pass = gates_config.get("ws7_fail_on_any_non_pass", False)
                fail_gates = [k for k, v in ws7_gate_summary.items() if v == "fail"]
                warn_gates = [k for k, v in ws7_gate_summary.items() if v == "warn"]
                step_log = {
                    "step": name,
                    "gate_summary": ws7_gate_summary,
                    "fail_gates": fail_gates,
                    "warn_gates": warn_gates,
                }
                step_logs.append(step_log)
                if warn_gates:
                    print(f"  WS7 warn gates (non-blocking): {warn_gates}")
                if fail_gates:
                    print(f"  WS7 fail gates: {fail_gates}")
                    # fail gates always block
                    print("  HALTING: WS7 gate failure detected")
                    verdict = build_verdict(batch_id, "failed", "ws7_gate", ws6_gate_bools, ws7_gate_summary, 1, step_logs)
                    path = write_verdict(verdict, ws_root)
                    print(f"Verdict written to {path}")
                    print(yaml.dump(verdict, default_flow_style=False, sort_keys=False))
                    return 1
                elif fail_on_any_non_pass and warn_gates:
                    print("  HALTING: ws7_fail_on_any_non_pass is true and warn gates present")
                    verdict = build_verdict(batch_id, "failed", "ws7_gate", ws6_gate_bools, ws7_gate_summary, 1, step_logs)
                    path = write_verdict(verdict, ws_root)
                    print(f"Verdict written to {path}")
                    print(yaml.dump(verdict, default_flow_style=False, sort_keys=False))
                    return 1
                else:
                    print("  All WS7 gates passed (warns are non-blocking)")
            continue

        # Tool execution steps
        print(f"--- {label} ---")
        args = step["args_fn"](spec, ws_root)
        argv_display = f"python3 {step['tool']} {' '.join(args)}"
        print(f"  Running: {argv_display}")

        proc = run_tool(step["tool"], args, ws_root)
        step_log: dict[str, Any] = {
            "step": name,
            "command": argv_display,
            "exit_code": proc.returncode,
            "stdout_tail": truncate(proc.stdout),
            "stderr_tail": truncate(proc.stderr),
        }
        step_logs.append(step_log)

        if proc.returncode != 0:
            print(f"  TOOL ERROR: exit code {proc.returncode}")
            if proc.stderr.strip():
                print(f"  stderr: {truncate(proc.stderr, 10)}")
            verdict = build_verdict(batch_id, "halted", name, ws6_gate_bools, ws7_gate_summary, 2, step_logs)
            path = write_verdict(verdict, ws_root)
            print(f"Verdict written to {path}")
            print(yaml.dump(verdict, default_flow_style=False, sort_keys=False))
            return 2
        else:
            print(f"  OK (exit 0)")

    # All steps passed
    verdict = build_verdict(batch_id, "ok", None, ws6_gate_bools, ws7_gate_summary, 0, step_logs)
    path = write_verdict(verdict, ws_root)
    print(f"\n=== BATCH {batch_id} COMPLETE ===")
    print(f"Verdict written to {path}")
    print(yaml.dump(verdict, default_flow_style=False, sort_keys=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch pipeline orchestrator: chains WS5 → WS4 → WS6 → WS7 from a single command.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Example spec (batch_spec.yaml):
  batch_id: B7
  manifest: inputs/ws5/ws5_input_manifest.yaml
  gates:
    ws6_fail_on_any_false: true
    ws7_fail_on_any_non_pass: false

Steps executed:
  1. WS5 remote ingestion (ws5_remote_ingestion.py --input <manifest>)
  2. WS4 master compiler (ws4_master_compiler.py)
  3. WS6 deep integrator (ws6_deep_integrator.py --run-validation-suite)
  4. WS6 gate evaluation (reads validation_runs.yaml gate_bools)
  5. WS7 read model compiler (ws7_read_model_compiler.py --force)
  6. WS7 gate evaluation (reads compile_log.yaml gates)

Exit codes:
  0 = all steps passed
  1 = gate failure
  2 = tool error or bad spec
""",
    )
    parser.add_argument("--spec", required=True, help="Path to batch_spec.yaml")
    parser.add_argument("--workspace-root", default=".", help="Workspace root directory")
    parser.add_argument("--dry-run", action="store_true", help="Print planned steps without executing")
    args = parser.parse_args()
    return run_batch(args.spec, args.workspace_root, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
