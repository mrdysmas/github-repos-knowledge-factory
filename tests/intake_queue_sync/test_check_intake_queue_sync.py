#!/usr/bin/env python3
"""Regression tests for intake queue sync gate behavior."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "check_intake_queue_sync.py"


class IntakeQueueSyncTests(unittest.TestCase):
    def _write_yaml(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def _make_workspace(self, tmp_path: Path) -> Path:
        self._write_yaml(
            tmp_path / "master_repo_list.yaml",
            {
                "artifact_type": "master_repo_catalog",
                "repos": [
                    {
                        "github_url": "https://github.com/example/demo-repo",
                        "author": "example",
                        "repo_name": "demo-repo",
                        "category": "llm_repos",
                        "local_path": "intake_repos/example__demo-repo",
                        "needs_review": False,
                    }
                ],
            },
        )
        self._write_yaml(
            tmp_path / "master_index.yaml",
            {
                "artifact_type": "master_index",
                "repos": [],
            },
        )
        self._write_yaml(
            tmp_path / "inputs" / "intake" / "intake_manifest.yaml",
            {
                "classification_strategy": {
                    "domain_hint": {
                        "suggested_values": ["agent_cli"],
                        "alias_map": {"agent-cli": "agent_cli"},
                    }
                }
            },
        )
        self._write_yaml(
            tmp_path / "inputs" / "intake" / "pilot_batch.yaml",
            {
                "records": [
                    {
                        "github_full_name": "example/demo-repo",
                        "domain_hint": "agent-cli",
                    }
                ]
            },
        )
        return tmp_path

    def test_fix_alias_does_not_emit_fail_after_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(Path(tmp_dir))
            cmd = [
                sys.executable,
                str(SCRIPT),
                "--workspace-root",
                str(workspace),
                "--fix",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            self.assertIn("DOMAIN_HINT_NORMALIZATION: FIXED", result.stdout)
            self.assertIn("DOMAIN_HINT_VALIDATION: PASS", result.stdout)
            self.assertNotIn("DOMAIN_HINT_VALIDATION: FAIL", result.stdout)

            pilot_payload = yaml.safe_load((workspace / "inputs" / "intake" / "pilot_batch.yaml").read_text(encoding="utf-8"))
            self.assertEqual(pilot_payload["records"][0]["domain_hint"], "agent_cli")


if __name__ == "__main__":
    unittest.main()
