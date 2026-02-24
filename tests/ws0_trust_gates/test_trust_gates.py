#!/usr/bin/env python3
"""Regression tests for WS0 trust gates."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import shutil
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
TRUST_GATES_PATH = ROOT / "tools" / "trust_gates.py"


def _load_trust_gates_module():
    spec = importlib.util.spec_from_file_location("trust_gates", TRUST_GATES_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load trust gates module from {TRUST_GATES_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


trust_gates = _load_trust_gates_module()


class TrustGatesRegressionTests(unittest.TestCase):
    def _run_fixture(self, fixture_name: str, production: bool) -> dict:
        fixture_source = FIXTURES_DIR / fixture_name
        if not fixture_source.exists():
            self.fail(f"Fixture missing: {fixture_source}")

        with tempfile.TemporaryDirectory() as tmp_dir:
            work_dir = Path(tmp_dir) / "knowledge"
            shutil.copytree(fixture_source, work_dir)

            report, report_path = trust_gates.run_trust_gates(work_dir, production=production)

            self.assertTrue(report_path.exists())
            with report_path.open("r", encoding="utf-8") as f:
                loaded_report = yaml.safe_load(f)

            self.assertIsInstance(loaded_report, dict)
            self.assertEqual(report["overall_status"], loaded_report["overall_status"])
            return loaded_report

    def test_parse_invalid_audit_artifact_blocks_g1(self) -> None:
        report = self._run_fixture("parse_invalid_audit", production=True)

        self.assertEqual(report["gates"]["g1_parse_integrity"]["status"], "FAIL")
        self.assertEqual(report["gates"]["g2_status_semantics"]["status"], "PASS")
        self.assertEqual(report["overall_status"], "BLOCKED")
        self.assertFalse(report["ready_state_allowed"])

        parse_error_files = {
            item["file"] for item in report["gates"]["g1_parse_integrity"]["parse_errors"]
        }
        self.assertIn("audit-progress.yaml", parse_error_files)

    def test_complete_with_pending_contradiction_blocks_g2(self) -> None:
        report = self._run_fixture("status_complete_pending", production=True)

        self.assertEqual(report["gates"]["g1_parse_integrity"]["status"], "PASS")
        self.assertEqual(report["gates"]["g2_status_semantics"]["status"], "FAIL")
        self.assertEqual(report["overall_status"], "BLOCKED")
        self.assertFalse(report["ready_state_allowed"])

        rules = {item["rule"] for item in report["gates"]["g2_status_semantics"]["violations"]}
        self.assertIn("progress.deepening_pending_must_be_empty", rules)

    def test_clean_pass_case(self) -> None:
        report = self._run_fixture("clean_pass", production=True)

        self.assertEqual(report["gates"]["g1_parse_integrity"]["status"], "PASS")
        self.assertEqual(report["gates"]["g2_status_semantics"]["status"], "PASS")
        self.assertEqual(report["gates"]["g3_spec_validator_contract"]["status"], "PASS")
        self.assertEqual(report["overall_status"], "PASS")
        self.assertTrue(report["ready_state_allowed"])


if __name__ == "__main__":
    unittest.main()
