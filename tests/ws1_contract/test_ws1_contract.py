#!/usr/bin/env python3
"""WS1 canonical contract regression tests."""

from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = ROOT / "tools" / "ws1_contract_validator.py"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


class WS1ContractRegressionTests(unittest.TestCase):
    def _run_validator(
        self,
        *,
        external_policy: str,
        fixture_name: str,
        contracts_dir: Path | None = None,
        workspace_root: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        root = workspace_root if workspace_root is not None else ROOT
        cmd = [
            sys.executable,
            str(VALIDATOR_PATH),
            "--workspace-root",
            str(root),
            "--external-node-policy",
            external_policy,
            "--consistency-fixture",
            str(FIXTURES_DIR / fixture_name),
        ]
        if contracts_dir is not None:
            cmd.extend(["--contracts-dir", str(contracts_dir)])

        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def test_ws1_validator_passes_first_class_mode(self) -> None:
        result = self._run_validator(
            external_policy="first_class",
            fixture_name="edge_node_consistency_valid.yaml",
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
        self.assertIn("WS1_CONTRACT_STATUS: PASS", result.stdout)

    def test_ws1_validator_passes_label_only_mode(self) -> None:
        result = self._run_validator(
            external_policy="label_only",
            fixture_name="edge_node_consistency_label_only_valid.yaml",
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
        self.assertIn("WS1_CONTRACT_STATUS: PASS", result.stdout)

    def test_ws1_validator_fails_on_dst_kind_mismatch(self) -> None:
        result = self._run_validator(
            external_policy="first_class",
            fixture_name="edge_node_consistency_invalid_mismatch.yaml",
        )
        self.assertNotEqual(result.returncode, 0, msg="expected failure")
        self.assertIn("WS1_CONTRACT_STATUS: FAIL", result.stdout)
        self.assertIn("dst_kind", result.stdout)

    def test_ws1_validator_fails_on_coverage_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            contracts_copy = Path(tmp_dir) / "contracts_ws1"
            shutil.copytree(ROOT / "contracts" / "ws1", contracts_copy)

            relation_mapping_path = contracts_copy / "relation_mapping.yaml"
            relation_mapping = yaml.safe_load(relation_mapping_path.read_text(encoding="utf-8"))
            relation_mapping["coverage"]["unique_observed_labels"] = 999
            relation_mapping_path.write_text(
                yaml.safe_dump(relation_mapping, sort_keys=False),
                encoding="utf-8",
            )

            result = self._run_validator(
                external_policy="first_class",
                fixture_name="edge_node_consistency_valid.yaml",
                contracts_dir=contracts_copy,
            )

            self.assertNotEqual(result.returncode, 0, msg="expected coverage failure")
            self.assertIn("WS1_CONTRACT_STATUS: FAIL", result.stdout)
            self.assertIn("Coverage mismatch", result.stdout)

    def test_ws1_validator_fails_on_deep_legacy_alias_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = Path(tmp_dir) / "workspace"
            workspace.mkdir(parents=True, exist_ok=True)

            shutil.copytree(ROOT / "contracts", workspace / "contracts")
            shutil.copytree(ROOT / "repos" / "knowledge", workspace / "repos" / "knowledge")

            deep_path = workspace / "repos" / "knowledge" / "deep" / "khoj.yaml"
            deep_doc = yaml.safe_load(deep_path.read_text(encoding="utf-8"))
            deep_doc["repo_id"] = "legacy_alias"
            deep_path.write_text(
                yaml.safe_dump(deep_doc, sort_keys=False),
                encoding="utf-8",
            )

            result = self._run_validator(
                external_policy="first_class",
                fixture_name="edge_node_consistency_valid.yaml",
                workspace_root=workspace,
            )

            self.assertNotEqual(result.returncode, 0, msg="expected deep schema failure")
            self.assertIn("WS1_CONTRACT_STATUS: FAIL", result.stdout)
            self.assertIn("legacy alias keys", result.stdout)


if __name__ == "__main__":
    unittest.main()
