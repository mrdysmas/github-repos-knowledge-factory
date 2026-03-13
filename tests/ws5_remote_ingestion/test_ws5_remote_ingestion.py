#!/usr/bin/env python3
"""WS5 remote ingestion regression tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "ws5_remote_ingestion.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WS5RemoteIngestionTests(unittest.TestCase):
    def _make_workspace(self, tmp_path: Path) -> Path:
        (tmp_path / "contracts" / "ws1").mkdir(parents=True, exist_ok=True)
        (tmp_path / "repos" / "knowledge" / "repos").mkdir(parents=True, exist_ok=True)
        (tmp_path / "inputs" / "ws5").mkdir(parents=True, exist_ok=True)

        repo_schema = {
            "contract_version": "1.0.0-ws1",
            "artifact_type": "ws1_repo_schema",
            "source_enums": ["repos", "remote_metadata", "remote_api", "compiled_master"],
        }
        (tmp_path / "contracts" / "ws1" / "repo.schema.yaml").write_text(
            yaml.safe_dump(repo_schema, sort_keys=False),
            encoding="utf-8",
        )

        index_payload = {
            "version": "1.0",
            "generated": "2026-02-23",
            "total_repos": 0,
            "categories": {
                "network_infrastructure": {"description": "infra", "repos": []},
                "vpn_mesh": {"description": "vpn", "repos": []},
            },
            "repos": {},
        }
        (tmp_path / "repos" / "knowledge" / "index.yaml").write_text(
            yaml.safe_dump(index_payload, sort_keys=False),
            encoding="utf-8",
        )

        manifest_payload = {
            "artifact_type": "ws5_remote_ingestion_input_manifest",
            "contract_version": "1.0.0-ws1",
            "defaults": {"target_shard": "repos", "as_of": "2026-02-23"},
            "repos": [
                {
                    "name": "cloudflared",
                    "github_full_name": "cloudflare/cloudflared",
                    "source": "remote_metadata",
                    "category": "network_infrastructure",
                    "summary": "Cloudflare Tunnel client",
                    "core_concepts": ["Tunnel client", "Zero trust edge"],
                    "key_entry_points": ["cmd/cloudflared", "README.md"],
                    "build_run": {"language": "go", "build": "go build ./cmd/cloudflared"},
                },
                {
                    "name": "tailscale",
                    "github_full_name": "tailscale/tailscale",
                    "source": "remote_api",
                    "category": "vpn_mesh",
                    "summary": "WireGuard mesh network",
                    "core_concepts": ["Mesh VPN", "Identity-aware access"],
                    "key_entry_points": ["cmd/tailscale", "cmd/tailscaled"],
                    "build_run": {"language": "go", "build": "go build ./cmd/tailscale"},
                },
            ],
        }
        (tmp_path / "inputs" / "ws5" / "ws5_input_manifest.yaml").write_text(
            yaml.safe_dump(manifest_payload, sort_keys=False),
            encoding="utf-8",
        )
        return tmp_path

    def test_cli_ingests_remote_records_and_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(Path(tmp_dir))
            cmd = [
                sys.executable,
                str(SCRIPT),
                "--workspace-root",
                str(workspace),
                "--input",
                "inputs/ws5/ws5_input_manifest.yaml",
                "--reports-dir",
                "reports/ws5_remote_ingestion",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

            cloudflared_repo = workspace / "repos" / "knowledge" / "repos" / "cloudflared.yaml"
            tailscale_repo = workspace / "repos" / "knowledge" / "repos" / "tailscale.yaml"
            self.assertTrue(cloudflared_repo.exists())
            self.assertTrue(tailscale_repo.exists())

            cloud_payload = yaml.safe_load(cloudflared_repo.read_text(encoding="utf-8"))
            tail_payload = yaml.safe_load(tailscale_repo.read_text(encoding="utf-8"))
            self.assertEqual(cloud_payload["source"], "remote_metadata")
            self.assertEqual(tail_payload["source"], "remote_api")
            self.assertEqual(cloud_payload["provenance"]["shard"], "repos")
            self.assertIsNone(cloud_payload["local_cache_dir"])
            self.assertIsNone(tail_payload["local_cache_dir"])

            coverage = yaml.safe_load((workspace / "reports" / "ws5_remote_ingestion" / "coverage.yaml").read_text(encoding="utf-8"))
            mismatch = yaml.safe_load((workspace / "reports" / "ws5_remote_ingestion" / "mismatch_report.yaml").read_text(encoding="utf-8"))
            runs = yaml.safe_load((workspace / "reports" / "ws5_remote_ingestion" / "validation_runs.yaml").read_text(encoding="utf-8"))
            self.assertTrue(coverage["gate_ready"])
            self.assertEqual(mismatch["summary"]["blocking_mismatches_count"], 0)
            self.assertIn("inputs/ws5/ws5_input_manifest.yaml", runs["artifact_hashes"])
            self.assertEqual(runs["artifact_hashes"]["inputs/ws5/ws5_input_manifest.yaml"], runs["input_manifest_sha256"])

    def test_cli_uses_readme_fallback_only_for_missing_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(Path(tmp_dir))
            manifest_path = workspace / "inputs" / "ws5" / "ws5_input_manifest.yaml"
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            repos = manifest["repos"]

            repos[0]["summary"] = ""
            repos[0]["core_concepts"] = []
            repos[0]["key_entry_points"] = []
            repos[0]["build_run"] = {}
            repos[0]["readme_fallback"] = {
                "summary": "Fallback summary from README",
                "core_concepts": ["README concept"],
                "key_entry_points": ["README.md"],
                "build_run": {"language": "go", "build": "go build ./cmd/cloudflared"},
            }

            repos[1]["readme_fallback"] = {
                "summary": "README should not override API summary",
                "core_concepts": ["README should not override API concepts"],
                "key_entry_points": ["README should not override API entry points"],
                "build_run": {"language": "go", "build": "echo should-not-override"},
            }

            manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")

            cmd = [
                sys.executable,
                str(SCRIPT),
                "--workspace-root",
                str(workspace),
                "--input",
                "inputs/ws5/ws5_input_manifest.yaml",
                "--reports-dir",
                "reports/ws5_remote_ingestion",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

            cloud_payload = yaml.safe_load(
                (workspace / "repos" / "knowledge" / "repos" / "cloudflared.yaml").read_text(encoding="utf-8")
            )
            tailscale_payload = yaml.safe_load(
                (workspace / "repos" / "knowledge" / "repos" / "tailscale.yaml").read_text(encoding="utf-8")
            )

            self.assertEqual(cloud_payload["summary"], "Fallback summary from README")
            self.assertEqual(cloud_payload["core_concepts"], ["README concept"])
            self.assertEqual(cloud_payload["key_entry_points"], ["README.md"])
            self.assertEqual(cloud_payload["build_run"]["build"], "go build ./cmd/cloudflared")

            self.assertEqual(tailscale_payload["summary"], "WireGuard mesh network")
            self.assertEqual(tailscale_payload["core_concepts"], ["Mesh VPN", "Identity-aware access"])
            self.assertEqual(tailscale_payload["key_entry_points"], ["cmd/tailscale", "cmd/tailscaled"])
            self.assertEqual(tailscale_payload["build_run"]["build"], "go build ./cmd/tailscale")

            cloud_refresh = cloud_payload["extras"]["refresh"]
            self.assertEqual(
                cloud_refresh["precedence"],
                "api_wins_readme_for_missing_required_fields",
            )
            self.assertTrue(cloud_refresh["fallback_used"])
            self.assertEqual(
                cloud_refresh["fields_filled_from_readme"],
                ["build_run", "core_concepts", "key_entry_points", "summary"],
            )

            tailscale_refresh = tailscale_payload["extras"]["refresh"]
            self.assertFalse(tailscale_refresh["fallback_used"])

            coverage = yaml.safe_load(
                (workspace / "reports" / "ws5_remote_ingestion" / "coverage.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(coverage["input_scope"]["readme_fallback_entries"], 1)
            self.assertEqual(coverage["input_scope"]["readme_fallback_fields_total"], 4)
            self.assertEqual(coverage["canonical_coverage_metrics"]["readme_fallback_usage_pct"], 50.0)

    def test_cli_is_deterministic_for_identical_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(Path(tmp_dir))
            cmd = [
                sys.executable,
                str(SCRIPT),
                "--workspace-root",
                str(workspace),
                "--input",
                "inputs/ws5/ws5_input_manifest.yaml",
                "--reports-dir",
                "reports/ws5_remote_ingestion",
            ]

            first = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, msg=first.stdout + "\n" + first.stderr)

            first_hashes = {
                "coverage": _sha256(workspace / "reports" / "ws5_remote_ingestion" / "coverage.yaml"),
                "mismatch": _sha256(workspace / "reports" / "ws5_remote_ingestion" / "mismatch_report.yaml"),
                "validation_runs": _sha256(workspace / "reports" / "ws5_remote_ingestion" / "validation_runs.yaml"),
                "cloudflared": _sha256(workspace / "repos" / "knowledge" / "repos" / "cloudflared.yaml"),
                "tailscale": _sha256(workspace / "repos" / "knowledge" / "repos" / "tailscale.yaml"),
            }

            second = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(second.returncode, 0, msg=second.stdout + "\n" + second.stderr)

            second_hashes = {
                "coverage": _sha256(workspace / "reports" / "ws5_remote_ingestion" / "coverage.yaml"),
                "mismatch": _sha256(workspace / "reports" / "ws5_remote_ingestion" / "mismatch_report.yaml"),
                "validation_runs": _sha256(workspace / "reports" / "ws5_remote_ingestion" / "validation_runs.yaml"),
                "cloudflared": _sha256(workspace / "repos" / "knowledge" / "repos" / "cloudflared.yaml"),
                "tailscale": _sha256(workspace / "repos" / "knowledge" / "repos" / "tailscale.yaml"),
            }
            self.assertEqual(first_hashes, second_hashes)

    def test_cli_preserves_finalized_validation_runs_on_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(Path(tmp_dir))
            reports_dir = workspace / "reports" / "ws5_remote_ingestion"
            reports_dir.mkdir(parents=True, exist_ok=True)

            validation_path = reports_dir / "validation_runs.yaml"
            seeded_validation_runs = {
                "artifact_type": "ws5_remote_ingestion_validation_runs",
                "generated_at_utc": "2026-02-22T00:00:00Z",
                "contract_version": "1.0.0-ws1",
                "required_commands": [
                    {
                        "step": 1,
                        "command": "python3 tools/ws1_contract_validator.py --workspace-root . --external-node-policy first_class",
                        "status": "PASS",
                        "exit_code": 0,
                        "expectation": "WS1_CONTRACT_STATUS: PASS",
                    },
                    {
                        "step": 2,
                        "command": "python3 tools/ws1_contract_validator.py --workspace-root . --external-node-policy label_only",
                        "status": "PASS",
                        "exit_code": 0,
                        "expectation": "WS1_CONTRACT_STATUS: PASS",
                    },
                    {
                        "step": 3,
                        "command": "python3 tools/trust_gates.py repos/knowledge --production",
                        "status": "PASS",
                        "exit_code": 0,
                        "expectation": "overall_status: PASS and ready_state_allowed: true",
                    },
                    {
                        "step": 4,
                        "command": "cd repos/knowledge && python3 validate.py",
                        "status": "PASS",
                        "exit_code": 0,
                        "expectation": "validate.py exits 0",
                    },
                    {
                        "step": 5,
                        "command": "python3 -m unittest discover -s tests/ws5_remote_ingestion -p 'test_*.py'",
                        "status": "PASS",
                        "exit_code": 0,
                        "expectation": "unittest exits 0",
                    },
                    {
                        "step": 6,
                        "command": "python3 tools/ws5_remote_ingestion.py --workspace-root . --input inputs/ws5/ws5_input_manifest.yaml --reports-dir reports/ws5_remote_ingestion",
                        "status": "FAIL",
                        "exit_code": 1,
                        "expectation": "WS5 ingestion writes deterministic reports and WS1-compatible records",
                    },
                    {
                        "step": 7,
                        "command": "python3 tools/ws4_master_compiler.py --workspace-root . --master-index master_index.yaml --master-graph master_graph.yaml --reports-dir reports/ws4_master_build",
                        "status": "PASS",
                        "exit_code": 0,
                        "expectation": "compiler exits 0 and reports/ws4_master_build/coverage.yaml gate_ready: true",
                    },
                    {
                        "step": 8,
                        "command": "Re-run commands 6 and 7 with identical input and verify artifact hashes unchanged",
                        "status": "PASS",
                        "exit_code": 0,
                        "expectation": "hashes unchanged",
                    },
                ],
                "artifact_hashes": {
                    "inputs/ws5/ws5_input_manifest.yaml": "legacy-manifest-hash",
                    "reports/ws5_remote_ingestion/coverage.yaml": "legacy-coverage-hash",
                    "reports/ws5_remote_ingestion/mismatch_report.yaml": "legacy-mismatch-hash",
                    "master_graph.yaml": "keep-this-extra-hash",
                },
                "input_manifest_sha256": "legacy-manifest-hash",
                "gate_bools": {
                    "manifest_parseable": False,
                    "manifest_entries_present": True,
                    "ws1_contract_first_class_pass": True,
                    "all_required_commands_exit_zero": True,
                },
                "gate_ready": True,
                "deterministic_rerun_hash_check": {
                    "status": "PASS",
                    "artifacts": {
                        "reports/ws5_remote_ingestion/validation_runs.yaml": "existing-finalized-hash",
                    },
                },
            }
            validation_path.write_text(yaml.safe_dump(seeded_validation_runs, sort_keys=False), encoding="utf-8")

            cmd = [
                sys.executable,
                str(SCRIPT),
                "--workspace-root",
                str(workspace),
                "--input",
                "inputs/ws5/ws5_input_manifest.yaml",
                "--reports-dir",
                "reports/ws5_remote_ingestion",
            ]

            first = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(first.returncode, 0, msg=first.stdout + "\n" + first.stderr)

            first_runs = yaml.safe_load(validation_path.read_text(encoding="utf-8"))
            self.assertEqual(
                first_runs["deterministic_rerun_hash_check"],
                seeded_validation_runs["deterministic_rerun_hash_check"],
            )
            self.assertEqual(first_runs["artifact_hashes"]["master_graph.yaml"], "keep-this-extra-hash")
            self.assertTrue(first_runs["gate_bools"]["ws1_contract_first_class_pass"])
            self.assertTrue(first_runs["gate_bools"]["all_required_commands_exit_zero"])
            self.assertTrue(first_runs["gate_bools"]["manifest_parseable"])

            commands_by_step = {row["step"]: row for row in first_runs["required_commands"]}
            seeded_commands = {row["step"]: row for row in seeded_validation_runs["required_commands"]}
            for step in (1, 2, 3, 4, 5, 7, 8):
                self.assertEqual(commands_by_step[step]["status"], seeded_commands[step]["status"])
                self.assertEqual(commands_by_step[step]["exit_code"], seeded_commands[step]["exit_code"])

            self.assertEqual(commands_by_step[6]["status"], "PASS")
            self.assertEqual(commands_by_step[6]["exit_code"], 0)
            self.assertEqual(first_runs["gate_ready"], True)

            first_hash = _sha256(validation_path)
            second = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(second.returncode, 0, msg=second.stdout + "\n" + second.stderr)
            second_hash = _sha256(validation_path)
            self.assertEqual(first_hash, second_hash)


if __name__ == "__main__":
    unittest.main()
