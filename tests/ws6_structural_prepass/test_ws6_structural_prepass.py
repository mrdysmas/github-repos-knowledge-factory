#!/usr/bin/env python3
"""WS6 structural pre-pass regression tests."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "ws6_structural_prepass.py"


class WS6StructuralPrepassTests(unittest.TestCase):
    def _write_yaml(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def _make_python_workspace(self, tmp_path: Path) -> Path:
        (tmp_path / "inputs" / "ws5").mkdir(parents=True, exist_ok=True)
        (tmp_path / "reports" / "ws6_clone_prep").mkdir(parents=True, exist_ok=True)
        repo_root = tmp_path / "workspace" / "clones" / "ExampleOrg__demo-app"
        (repo_root / "demo_app").mkdir(parents=True, exist_ok=True)
        (repo_root / "server").mkdir(parents=True, exist_ok=True)
        (repo_root / ".github" / "workflows").mkdir(parents=True, exist_ok=True)

        (repo_root / "pyproject.toml").write_text(
            "\n".join(
                [
                    "[project]",
                    'name = "demo-app"',
                    'version = "0.1.0"',
                    'dependencies = ["fastapi>=0.110", "uvicorn>=0.29"]',
                ]
            ),
            encoding="utf-8",
        )
        (repo_root / "requirements.txt").write_text("httpx>=0.27\n", encoding="utf-8")
        (repo_root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
        (repo_root / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
        (repo_root / "demo_app" / "__init__.py").write_text("", encoding="utf-8")
        (repo_root / "demo_app" / "service.py").write_text(
            "\n".join(
                [
                    "from fastapi import FastAPI",
                    "",
                    "app = FastAPI()",
                ]
            ),
            encoding="utf-8",
        )
        (repo_root / "server" / "main.py").write_text(
            "\n".join(
                [
                    "from demo_app.service import app",
                    "",
                    "if __name__ == '__main__':",
                    "    print(app)",
                ]
            ),
            encoding="utf-8",
        )
        (repo_root / "cli.py").write_text("from demo_app.service import app\n", encoding="utf-8")

        input_manifest = {
            "artifact_type": "ws5_remote_ingestion_input_manifest",
            "contract_version": "1.0.0-ws1",
            "repos": [
                {
                    "github_full_name": "ExampleOrg/demo-app",
                    "file_stem": "exampleorg__demo-app",
                }
            ],
        }
        self._write_yaml(tmp_path / "inputs" / "ws5" / "B_demo_manifest.yaml", input_manifest)

        clone_manifest = {
            "batch_id": "B_demo",
            "generated_at_utc": "2026-03-21T00:00:00Z",
            "clone_workdir": "/Users/old-machine/scripts/ext_sources/github_repos/workspace/clones",
            "repos": [
                {
                    "github_full_name": "ExampleOrg/demo-app",
                    "local_path": "/Users/old-machine/scripts/ext_sources/github_repos/workspace/clones/ExampleOrg__demo-app",
                    "cloned": False,
                    "skip_reason": "already_cloned",
                }
            ],
        }
        self._write_yaml(tmp_path / "reports" / "ws6_clone_prep" / "B_demo_clones.yaml", clone_manifest)
        return tmp_path

    def _make_node_workspace(self, tmp_path: Path) -> Path:
        (tmp_path / "inputs" / "ws5").mkdir(parents=True, exist_ok=True)
        (tmp_path / "reports" / "ws6_clone_prep").mkdir(parents=True, exist_ok=True)
        repo_root = tmp_path / "workspace" / "clones" / "acme__web-demo"
        (repo_root / "src").mkdir(parents=True, exist_ok=True)
        (repo_root / "bin").mkdir(parents=True, exist_ok=True)

        (repo_root / "package.json").write_text(
            json.dumps(
                {
                    "name": "web-demo",
                    "main": "src/index.ts",
                    "bin": {"web-demo": "bin/cli.ts"},
                    "dependencies": {"express": "^4.0.0"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (repo_root / "src" / "index.ts").write_text(
            "import express from 'express';\nexport const app = express();\n",
            encoding="utf-8",
        )
        (repo_root / "bin" / "cli.ts").write_text("import { app } from '../src/index';\n", encoding="utf-8")

        input_manifest = {
            "artifact_type": "ws5_remote_ingestion_input_manifest",
            "contract_version": "1.0.0-ws1",
            "repos": [
                {
                    "github_full_name": "acme/web-demo",
                    "file_stem": "acme__web-demo",
                },
                {
                    "github_full_name": "acme/skip-me",
                    "file_stem": "acme__skip-me",
                },
            ],
        }
        self._write_yaml(tmp_path / "inputs" / "ws5" / "B_web_manifest.yaml", input_manifest)

        clone_manifest = {
            "batch_id": "B_web",
            "generated_at_utc": "2026-03-21T00:00:00Z",
            "clone_workdir": "workspace/clones",
            "repos": [
                {
                    "github_full_name": "acme/web-demo",
                    "local_path": str(repo_root),
                    "cloned": True,
                    "skip_reason": None,
                },
                {
                    "github_full_name": "acme/skip-me",
                    "local_path": str(tmp_path / "workspace" / "clones" / "acme__skip-me"),
                    "cloned": False,
                    "skip_reason": "missing",
                },
            ],
        }
        self._write_yaml(tmp_path / "reports" / "ws6_clone_prep" / "B_web_clones.yaml", clone_manifest)
        return tmp_path

    def _make_monorepo_workspace(self, tmp_path: Path) -> Path:
        (tmp_path / "inputs" / "ws5").mkdir(parents=True, exist_ok=True)
        (tmp_path / "reports" / "ws6_clone_prep").mkdir(parents=True, exist_ok=True)
        repo_root = tmp_path / "workspace" / "clones" / "acme__memory-monorepo"

        (repo_root / "runtime-api" / "runtime_api" / "worker").mkdir(parents=True, exist_ok=True)
        (repo_root / "runtime-api-slim" / "runtime_api" / "worker").mkdir(parents=True, exist_ok=True)
        (repo_root / "runtime-api-slim" / "runtime_api" / "engine").mkdir(parents=True, exist_ok=True)
        (repo_root / "runtime-api-slim" / "tests").mkdir(parents=True, exist_ok=True)
        (repo_root / "clients" / "typescript" / "src").mkdir(parents=True, exist_ok=True)
        (repo_root / "control-plane" / "bin").mkdir(parents=True, exist_ok=True)
        (repo_root / "dev" / "benchmarks" / "visualizer").mkdir(parents=True, exist_ok=True)
        (repo_root / "docs").mkdir(parents=True, exist_ok=True)

        (repo_root / "runtime-api" / "pyproject.toml").write_text(
            "\n".join(
                [
                    "[project]",
                    'name = "runtime-api"',
                    'dependencies = ["fastapi>=0.110", "uvicorn>=0.29", "pytest>=8.0"]',
                    "",
                    "[project.scripts]",
                    'runtime-api = "runtime_api.main:main"',
                    'runtime-worker = "runtime_api.worker.main:main"',
                ]
            ),
            encoding="utf-8",
        )
        (repo_root / "runtime-api" / "runtime_api" / "__init__.py").write_text("", encoding="utf-8")
        (repo_root / "runtime-api" / "runtime_api" / "main.py").write_text("def main():\n    return None\n", encoding="utf-8")
        (repo_root / "runtime-api" / "runtime_api" / "worker" / "__init__.py").write_text("", encoding="utf-8")
        (repo_root / "runtime-api" / "runtime_api" / "worker" / "main.py").write_text(
            "def main():\n    return None\n",
            encoding="utf-8",
        )
        (repo_root / "runtime-api-slim" / "pyproject.toml").write_text(
            "\n".join(
                [
                    "[project]",
                    'name = "runtime-api-slim"',
                    'dependencies = ["httpx>=0.27", "sqlalchemy>=2.0"]',
                ]
            ),
            encoding="utf-8",
        )
        (repo_root / "runtime-api-slim" / "runtime_api" / "__init__.py").write_text("", encoding="utf-8")
        (repo_root / "runtime-api-slim" / "runtime_api" / "main.py").write_text(
            "from runtime_api.engine.router import app\n",
            encoding="utf-8",
        )
        (repo_root / "runtime-api-slim" / "runtime_api" / "server.py").write_text(
            "from runtime_api.engine.router import app\n",
            encoding="utf-8",
        )
        (repo_root / "runtime-api-slim" / "runtime_api" / "worker" / "__init__.py").write_text("", encoding="utf-8")
        (repo_root / "runtime-api-slim" / "runtime_api" / "worker" / "main.py").write_text(
            "from runtime_api.engine.jobs import run\n",
            encoding="utf-8",
        )
        (repo_root / "runtime-api-slim" / "runtime_api" / "engine" / "__init__.py").write_text("", encoding="utf-8")
        (repo_root / "runtime-api-slim" / "runtime_api" / "engine" / "router.py").write_text(
            "from runtime_api.engine.jobs import run\n",
            encoding="utf-8",
        )
        (repo_root / "runtime-api-slim" / "runtime_api" / "engine" / "jobs.py").write_text(
            "from runtime_api.engine.router import app\n",
            encoding="utf-8",
        )
        (repo_root / "runtime-api-slim" / "tests" / "__init__.py").write_text("", encoding="utf-8")

        (repo_root / "clients" / "typescript" / "package.json").write_text(
            json.dumps(
                {
                    "name": "@acme/runtime-client",
                    "main": "./dist/index.js",
                    "dependencies": {"axios": "^1.0.0"},
                    "devDependencies": {"typescript": "^5.0.0"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (repo_root / "clients" / "typescript" / "src" / "index.ts").write_text(
            "export const client = 'ok';\n",
            encoding="utf-8",
        )

        (repo_root / "control-plane" / "package.json").write_text(
            json.dumps(
                {
                    "name": "@acme/control-plane",
                    "bin": {"control-plane": "./bin/cli.js"},
                    "dependencies": {"next": "^16.0.0", "react": "^19.0.0"},
                    "devDependencies": {"eslint": "^9.0.0"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (repo_root / "control-plane" / "bin" / "cli.js").write_text("console.log('cli');\n", encoding="utf-8")

        (repo_root / "dev" / "benchmarks" / "visualizer" / "main.py").write_text("print('benchmark')\n", encoding="utf-8")
        (repo_root / "docs" / "package.json").write_text(json.dumps({"name": "docs"}, indent=2) + "\n", encoding="utf-8")

        input_manifest = {
            "artifact_type": "ws5_remote_ingestion_input_manifest",
            "contract_version": "1.0.0-ws1",
            "repos": [
                {
                    "github_full_name": "acme/memory-monorepo",
                    "file_stem": "acme__memory-monorepo",
                }
            ],
        }
        self._write_yaml(tmp_path / "inputs" / "ws5" / "B_mono_manifest.yaml", input_manifest)

        clone_manifest = {
            "batch_id": "B_mono",
            "generated_at_utc": "2026-03-21T00:00:00Z",
            "clone_workdir": "workspace/clones",
            "repos": [
                {
                    "github_full_name": "acme/memory-monorepo",
                    "local_path": str(repo_root),
                    "cloned": True,
                    "skip_reason": None,
                }
            ],
        }
        self._write_yaml(tmp_path / "reports" / "ws6_clone_prep" / "B_mono_clones.yaml", clone_manifest)
        return tmp_path

    def test_cli_generates_contract_conforming_artifact_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_python_workspace(Path(tmp_dir))
            cmd = [
                sys.executable,
                str(SCRIPT),
                "--workspace-root",
                str(workspace),
                "--clone-manifest",
                "reports/ws6_clone_prep/B_demo_clones.yaml",
                "--input-manifest",
                "inputs/ws5/B_demo_manifest.yaml",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

            artifact_path = workspace / "reports" / "ws6_structural_prepass" / "B_demo" / "exampleorg__demo-app.yaml"
            summary_path = workspace / "reports" / "ws6_structural_prepass" / "B_demo" / "summary.yaml"
            self.assertTrue(artifact_path.exists())
            self.assertTrue(summary_path.exists())

            artifact = yaml.safe_load(artifact_path.read_text(encoding="utf-8"))
            summary = yaml.safe_load(summary_path.read_text(encoding="utf-8"))

            self.assertEqual(artifact["schema_version"], "0.1")
            self.assertEqual(artifact["repo"]["github_full_name"], "ExampleOrg/demo-app")
            self.assertEqual(artifact["repo"]["file_stem"], "exampleorg__demo-app")
            self.assertEqual(artifact["artifact"]["stage"], "ws6_structural_prepass")
            self.assertEqual(
                artifact["artifact"]["output_file"],
                "reports/ws6_structural_prepass/B_demo/exampleorg__demo-app.yaml",
            )
            self.assertIn("server/main.py", artifact["orientation_hints"]["likely_first_read"])
            self.assertTrue(any(item["path"] == "server/main.py" for item in artifact["entrypoints"]))
            self.assertTrue(any(item["path"] == "pyproject.toml" for item in artifact["filesystem_signals"]["manifests"]))
            self.assertIn("imports", artifact["signals_used"])
            self.assertIn("dependency_signals", artifact)
            self.assertIn("demo_app.service", artifact["dependency_signals"]["internal_modules"])
            self.assertIn("fastapi", artifact["dependency_signals"]["external_packages"])
            self.assertTrue(all(item.get("evidence") for item in artifact["package_roots"]))
            self.assertTrue(all(item.get("evidence") for item in artifact["entrypoints"]))
            self.assertTrue(all(item.get("evidence") for item in artifact["module_groups"]))
            self.assertNotIn("common_tasks", artifact)
            self.assertNotIn("failure_modes", artifact)

            self.assertTrue(summary["summary"]["gate_ready"])
            self.assertTrue(summary["boundary_checks"]["non_canonical_output_only"])
            self.assertEqual(summary["boundary_checks"]["canonical_files_written"], [])
            self.assertEqual(summary["repos"][0]["status"], "ok")
            self.assertTrue(summary["repos"][0]["validation"]["valid"])

    def test_cli_repo_filter_processes_only_selected_repo_and_detects_package_json_entrypoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_node_workspace(Path(tmp_dir))
            cmd = [
                sys.executable,
                str(SCRIPT),
                "--workspace-root",
                str(workspace),
                "--clone-manifest",
                "reports/ws6_clone_prep/B_web_clones.yaml",
                "--input-manifest",
                "inputs/ws5/B_web_manifest.yaml",
                "--repo",
                "acme/web-demo",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

            selected_artifact = workspace / "reports" / "ws6_structural_prepass" / "B_web" / "acme__web-demo.yaml"
            skipped_artifact = workspace / "reports" / "ws6_structural_prepass" / "B_web" / "acme__skip-me.yaml"
            summary_path = workspace / "reports" / "ws6_structural_prepass" / "B_web" / "summary.yaml"
            self.assertTrue(selected_artifact.exists())
            self.assertFalse(skipped_artifact.exists())

            artifact = yaml.safe_load(selected_artifact.read_text(encoding="utf-8"))
            summary = yaml.safe_load(summary_path.read_text(encoding="utf-8"))

            entrypoint_paths = {item["path"] for item in artifact["entrypoints"]}
            self.assertIn("src/index.ts", entrypoint_paths)
            self.assertIn("bin/cli.ts", entrypoint_paths)
            self.assertEqual(summary["summary"]["repos_selected"], 1)
            self.assertEqual(summary["summary"]["repos_generated"], 1)
            self.assertEqual(len(summary["repos"]), 1)

    def test_monorepo_ranking_prefers_runtime_surfaces_and_merges_duplicate_module_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_monorepo_workspace(Path(tmp_dir))
            cmd = [
                sys.executable,
                str(SCRIPT),
                "--workspace-root",
                str(workspace),
                "--clone-manifest",
                "reports/ws6_clone_prep/B_mono_clones.yaml",
                "--input-manifest",
                "inputs/ws5/B_mono_manifest.yaml",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

            artifact_path = workspace / "reports" / "ws6_structural_prepass" / "B_mono" / "acme__memory-monorepo.yaml"
            artifact = yaml.safe_load(artifact_path.read_text(encoding="utf-8"))

            entrypoint_paths = {item["path"] for item in artifact["entrypoints"]}
            self.assertIn("runtime-api-slim/runtime_api/main.py", entrypoint_paths)
            self.assertIn("clients/typescript/src/index.ts", entrypoint_paths)
            self.assertNotIn("clients/typescript/dist/index.js", entrypoint_paths)
            self.assertNotIn("dev/benchmarks/visualizer/main.py", entrypoint_paths)

            likely_first_read = artifact["orientation_hints"]["likely_first_read"]
            self.assertTrue(
                any(path.startswith("runtime-api-slim/runtime_api/") for path in likely_first_read),
                likely_first_read,
            )
            self.assertNotIn("dev/benchmarks/visualizer/main.py", likely_first_read)

            runtime_api_groups = [group for group in artifact["module_groups"] if group["name"] == "runtime_api"]
            self.assertEqual(len(runtime_api_groups), 1)
            self.assertIn("runtime-api", runtime_api_groups[0]["paths"])
            self.assertIn("runtime-api-slim/runtime_api", runtime_api_groups[0]["paths"])

            self.assertIn("runtime_api.engine", artifact["dependency_signals"]["internal_modules"])
            self.assertNotIn("pytest", artifact["dependency_signals"]["external_packages"])
            self.assertNotIn("typescript", artifact["dependency_signals"]["external_packages"])


if __name__ == "__main__":
    unittest.main()
