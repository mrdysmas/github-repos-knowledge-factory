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

    def _make_broad_go_workspace(self, tmp_path: Path) -> Path:
        (tmp_path / "inputs" / "ws5").mkdir(parents=True, exist_ok=True)
        (tmp_path / "reports" / "ws6_clone_prep").mkdir(parents=True, exist_ok=True)
        repo_root = tmp_path / "workspace" / "clones" / "acme__mesh-broad"

        for directory in (
            repo_root / "cmd" / "tailscale",
            repo_root / "cmd" / "tailscaled",
            repo_root / "cmd" / "addlicense",
            repo_root / "cmd" / "containerboot",
            repo_root / "cmd" / "get-authkey",
            repo_root / "wgengine",
            repo_root / "ipn",
            repo_root / "control",
            repo_root / "client" / "web",
        ):
            directory.mkdir(parents=True, exist_ok=True)

        (repo_root / "go.mod").write_text("module example.com/mesh-broad\n", encoding="utf-8")
        (repo_root / "cmd" / "tailscale" / "tailscale.go").write_text(
            "\n".join(
                [
                    "package main",
                    "",
                    'import "example.com/mesh-broad/wgengine"',
                    "",
                    "func main() {",
                    "    _ = wgengine.Engine{}",
                    "}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (repo_root / "cmd" / "tailscale" / "up.go").write_text("package main\n", encoding="utf-8")
        (repo_root / "cmd" / "tailscale" / "status.go").write_text("package main\n", encoding="utf-8")
        (repo_root / "cmd" / "tailscale" / "debug.go").write_text("package main\n", encoding="utf-8")

        (repo_root / "cmd" / "tailscaled" / "tailscaled.go").write_text(
            "\n".join(
                [
                    "package main",
                    "",
                    'import "example.com/mesh-broad/ipn"',
                    "",
                    "func main() {",
                    "    _ = ipn.Server{}",
                    "}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (repo_root / "cmd" / "tailscaled" / "netstack.go").write_text("package main\n", encoding="utf-8")
        (repo_root / "cmd" / "tailscaled" / "proxy.go").write_text("package main\n", encoding="utf-8")
        (repo_root / "cmd" / "tailscaled" / "debug.go").write_text("package main\n", encoding="utf-8")

        (repo_root / "cmd" / "addlicense" / "main.go").write_text("package main\n", encoding="utf-8")
        (repo_root / "cmd" / "containerboot" / "main.go").write_text("package main\n", encoding="utf-8")
        (repo_root / "cmd" / "containerboot" / "serve.go").write_text("package main\n", encoding="utf-8")
        (repo_root / "cmd" / "get-authkey" / "main.go").write_text("package main\n", encoding="utf-8")

        (repo_root / "wgengine" / "wgengine.go").write_text("package wgengine\n\ntype Engine struct{}\n", encoding="utf-8")
        (repo_root / "wgengine" / "router.go").write_text("package wgengine\n", encoding="utf-8")
        (repo_root / "ipn" / "server.go").write_text("package ipn\n\ntype Server struct{}\n", encoding="utf-8")
        (repo_root / "ipn" / "localapi.go").write_text("package ipn\n", encoding="utf-8")
        (repo_root / "control" / "client.go").write_text("package control\n", encoding="utf-8")
        (repo_root / "control" / "map.go").write_text("package control\n", encoding="utf-8")

        (repo_root / "client" / "web" / "package.json").write_text(
            json.dumps({"name": "@acme/web", "dependencies": {"react": "^19.0.0"}}, indent=2) + "\n",
            encoding="utf-8",
        )

        input_manifest = {
            "artifact_type": "ws5_remote_ingestion_input_manifest",
            "contract_version": "1.0.0-ws1",
            "repos": [
                {
                    "github_full_name": "acme/mesh-broad",
                    "file_stem": "acme__mesh-broad",
                }
            ],
        }
        self._write_yaml(tmp_path / "inputs" / "ws5" / "B_broad_manifest.yaml", input_manifest)

        clone_manifest = {
            "batch_id": "B_broad",
            "generated_at_utc": "2026-03-21T00:00:00Z",
            "clone_workdir": "workspace/clones",
            "repos": [
                {
                    "github_full_name": "acme/mesh-broad",
                    "local_path": str(repo_root),
                    "cloned": True,
                    "skip_reason": None,
                }
            ],
        }
        self._write_yaml(tmp_path / "reports" / "ws6_clone_prep" / "B_broad_clones.yaml", clone_manifest)
        return tmp_path

    def _make_broad_frontend_workspace(self, tmp_path: Path) -> Path:
        (tmp_path / "inputs" / "ws5").mkdir(parents=True, exist_ok=True)
        (tmp_path / "reports" / "ws6_clone_prep").mkdir(parents=True, exist_ok=True)
        repo_root = tmp_path / "workspace" / "clones" / "acme__product-suite"

        for directory in (
            repo_root / "api" / "controllers" / "console" / "app",
            repo_root / "api" / "controllers" / "service_api" / "app",
            repo_root / "api" / "core",
            repo_root / "api" / "commands",
            repo_root / "api" / "configs",
            repo_root / "web" / "app",
            repo_root / "web" / "app" / "components",
            repo_root / "web" / "app" / "dashboard",
            repo_root / "web" / "app" / "settings",
            repo_root / "sdks" / "nodejs-client",
        ):
            directory.mkdir(parents=True, exist_ok=True)

        (repo_root / "api" / "pyproject.toml").write_text(
            "\n".join(
                [
                    "[project]",
                    'name = "product-suite-api"',
                    'dependencies = ["fastapi>=0.110", "uvicorn>=0.29"]',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        for package_dir in ("core", "commands", "configs"):
            (repo_root / "api" / package_dir / "__init__.py").write_text("", encoding="utf-8")
        (repo_root / "api" / "app.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
        (repo_root / "api" / "controllers" / "console" / "app" / "app.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n",
            encoding="utf-8",
        )
        (repo_root / "api" / "controllers" / "service_api" / "app" / "app.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n",
            encoding="utf-8",
        )

        (repo_root / "web" / "package.json").write_text(
            json.dumps(
                {
                    "name": "@acme/product-web",
                    "dependencies": {"next": "^16.0.0", "react": "^19.0.0"},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (repo_root / "web" / "next.config.ts").write_text("export default {}\n", encoding="utf-8")
        (repo_root / "web" / "tsconfig.json").write_text('{"compilerOptions": {"jsx": "preserve"}}\n', encoding="utf-8")
        (repo_root / "web" / "app" / "layout.tsx").write_text("export default function Layout() { return null }\n", encoding="utf-8")
        (repo_root / "web" / "app" / "page.tsx").write_text("export default function Page() { return null }\n", encoding="utf-8")
        for index in range(12):
            (repo_root / "web" / "app" / "components" / f"widget_{index}.tsx").write_text(
                "export const Widget = () => null\n",
                encoding="utf-8",
            )
        for index in range(4):
            (repo_root / "web" / "app" / "dashboard" / f"page_{index}.tsx").write_text(
                "export default function DashboardPage() { return null }\n",
                encoding="utf-8",
            )
            (repo_root / "web" / "app" / "settings" / f"panel_{index}.tsx").write_text(
                "export const SettingsPanel = () => null\n",
                encoding="utf-8",
            )

        (repo_root / "sdks" / "nodejs-client" / "package.json").write_text(
            json.dumps({"name": "@acme/node-sdk", "dependencies": {"axios": "^1.0.0"}}, indent=2) + "\n",
            encoding="utf-8",
        )

        input_manifest = {
            "artifact_type": "ws5_remote_ingestion_input_manifest",
            "contract_version": "1.0.0-ws1",
            "repos": [
                {
                    "github_full_name": "acme/product-suite",
                    "file_stem": "acme__product-suite",
                }
            ],
        }
        self._write_yaml(tmp_path / "inputs" / "ws5" / "B_frontend_manifest.yaml", input_manifest)

        clone_manifest = {
            "batch_id": "B_frontend",
            "generated_at_utc": "2026-03-21T00:00:00Z",
            "clone_workdir": "workspace/clones",
            "repos": [
                {
                    "github_full_name": "acme/product-suite",
                    "local_path": str(repo_root),
                    "cloned": True,
                    "skip_reason": None,
                }
            ],
        }
        self._write_yaml(tmp_path / "reports" / "ws6_clone_prep" / "B_frontend_clones.yaml", clone_manifest)
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

    def test_broad_repo_ranking_prefers_primary_runtime_surfaces_over_helper_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_broad_go_workspace(Path(tmp_dir))
            cmd = [
                sys.executable,
                str(SCRIPT),
                "--workspace-root",
                str(workspace),
                "--clone-manifest",
                "reports/ws6_clone_prep/B_broad_clones.yaml",
                "--input-manifest",
                "inputs/ws5/B_broad_manifest.yaml",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

            artifact_path = workspace / "reports" / "ws6_structural_prepass" / "B_broad" / "acme__mesh-broad.yaml"
            artifact = yaml.safe_load(artifact_path.read_text(encoding="utf-8"))

            entrypoints = artifact["entrypoints"]
            entrypoint_paths = [item["path"] for item in entrypoints]
            self.assertIn("cmd/tailscale/tailscale.go", entrypoint_paths)
            self.assertIn("cmd/tailscaled/tailscaled.go", entrypoint_paths)
            self.assertIn("cmd/addlicense/main.go", entrypoint_paths)

            self.assertLess(
                entrypoint_paths.index("cmd/tailscale/tailscale.go"),
                entrypoint_paths.index("cmd/addlicense/main.go"),
                entrypoint_paths,
            )
            self.assertLess(
                entrypoint_paths.index("cmd/tailscaled/tailscaled.go"),
                entrypoint_paths.index("cmd/get-authkey/main.go"),
                entrypoint_paths,
            )

            likely_first_read = artifact["orientation_hints"]["likely_first_read"]
            self.assertEqual(likely_first_read[0], "cmd/tailscale/tailscale.go", likely_first_read)
            self.assertEqual(likely_first_read[1], "cmd/tailscaled/tailscaled.go", likely_first_read)
            self.assertNotIn("cmd/addlicense/main.go", likely_first_read[:2], likely_first_read)
            self.assertIn("control", likely_first_read, likely_first_read)
            self.assertIn("ipn", likely_first_read, likely_first_read)

    def test_broad_repo_surfaces_major_frontend_boundary_without_displacing_primary_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_broad_frontend_workspace(Path(tmp_dir))
            cmd = [
                sys.executable,
                str(SCRIPT),
                "--workspace-root",
                str(workspace),
                "--clone-manifest",
                "reports/ws6_clone_prep/B_frontend_clones.yaml",
                "--input-manifest",
                "inputs/ws5/B_frontend_manifest.yaml",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

            artifact_path = workspace / "reports" / "ws6_structural_prepass" / "B_frontend" / "acme__product-suite.yaml"
            artifact = yaml.safe_load(artifact_path.read_text(encoding="utf-8"))

            module_groups = artifact["module_groups"]
            self.assertEqual(module_groups[0]["paths"], ["web"])
            self.assertIn(["api"], [group["paths"] for group in module_groups[:4]])

            likely_first_read = artifact["orientation_hints"]["likely_first_read"]
            self.assertTrue(likely_first_read[0].startswith("api/"), likely_first_read)
            self.assertTrue(likely_first_read[1].startswith("api/"), likely_first_read)
            self.assertIn("web", likely_first_read[:5], likely_first_read)
            if "api/commands" in likely_first_read:
                self.assertLess(likely_first_read.index("web"), likely_first_read.index("api/commands"), likely_first_read)
            if "api/configs" in likely_first_read:
                self.assertLess(likely_first_read.index("web"), likely_first_read.index("api/configs"), likely_first_read)


if __name__ == "__main__":
    unittest.main()
