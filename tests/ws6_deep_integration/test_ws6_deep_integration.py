#!/usr/bin/env python3
"""WS6 deep integration regression tests."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "ws6_deep_integrator.py"


class WS6DeepIntegrationTests(unittest.TestCase):
    def _write_yaml(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def _make_workspace(self, tmp_path: Path) -> Path:
        for shard in ("repos",):
            (tmp_path / shard / "knowledge" / "repos").mkdir(parents=True, exist_ok=True)
            (tmp_path / shard / "knowledge" / "deep").mkdir(parents=True, exist_ok=True)

        (tmp_path / "contracts" / "ws1").mkdir(parents=True, exist_ok=True)

        deep_fact_schema = {
            "contract_version": "1.0.0-ws6-draft",
            "artifact_type": "ws1_deep_fact_schema",
            "source_enums": ["repos", "remote_metadata", "remote_api", "compiled_master"],
            "fact_type_enums": [
                "component",
                "config_option",
                "api_endpoint",
                "implementation_pattern",
                "extension_point",
                "operational_task",
                "failure_mode",
                "protocol_usage",
            ],
            "predicate_enums": [
                "has_component",
                "has_config_option",
                "exposes_api_endpoint",
                "implements_pattern",
                "has_extension_point",
                "supports_task",
                "has_failure_mode",
                "uses_protocol",
            ],
            "object_kind_enums": [
                "text",
                "repo",
                "external_tool",
                "concept",
                "path",
                "config_key",
                "api_route",
                "command",
                "protocol",
                "issue",
            ],
            "evidence_kind_enums": ["file_line", "file_block", "doc_url", "command_output"],
        }
        self._write_yaml(tmp_path / "contracts" / "ws1" / "deep_fact.schema.yaml", deep_fact_schema)

        relation_mapping = {
            "contract_version": "1.0.0-ws1",
            "artifact_type": "ws1_relation_mapping",
            "canonical_relations": ["integrates_with"],
            "mappings": [
                {
                    "shard": "repos",
                    "observed_label": "integrates_with",
                    "canonical_relation": "integrates_with",
                    "status": "mapped",
                }
            ],
        }
        self._write_yaml(tmp_path / "contracts" / "ws1" / "relation_mapping.yaml", relation_mapping)

        shallow_repo = {
            "name": "demo-repo",
            "node_id": "repo::example/demo-repo",
            "github_full_name": "example/demo-repo",
            "html_url": "https://github.com/example/demo-repo",
            "source": "repos",
            "category": "demo",
            "summary": "demo",
            "core_concepts": ["demo"],
            "key_entry_points": ["README.md"],
            "build_run": {"language": "python"},
            "provenance": {
                "shard": "repos",
                "source_file": "repos/knowledge/repos/demo-repo.yaml",
                "as_of": "2026-02-24",
            },
        }
        self._write_yaml(tmp_path / "repos" / "knowledge" / "repos" / "demo-repo.yaml", shallow_repo)

        return tmp_path

    def _run_ws6(self, workspace: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess[str]:
        args = [
            sys.executable,
            str(SCRIPT),
            "--workspace-root",
            str(workspace),
            "--reports-dir",
            "reports/ws6_deep_integration",
            "--materialize-spec",
            "reports/ws6_deep_integration/spec.yaml",
        ]
        if extra_args:
            args.extend(extra_args)
        return subprocess.run(args, capture_output=True, text=True, check=False)

    def test_materializes_canonical_deep_facts_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(Path(tmp_dir))

            deep_payload = {
                "name": "demo-repo",
                "node_id": "repo::example/demo-repo",
                "github_full_name": "example/demo-repo",
                "html_url": "https://github.com/example/demo-repo",
                "source": "repos",
                "provenance": {
                    "shard": "repos",
                    "source_file": "repos/knowledge/deep/demo-repo.yaml",
                    "as_of": "2026-02-24",
                },
                "architecture": {
                    "module_breakdown": [
                        {"module": "core", "responsibility": "main logic", "key_files": ["src/core.py"]}
                    ],
                    "key_abstractions": [{"name": "Coordinator", "purpose": "orchestrates flows"}],
                },
                "implementation_patterns": [
                    {"pattern": "Factory Registration", "description": "register plugins", "location": "src/plugins.py"}
                ],
                "configuration": [
                    {
                        "name": "runtime",
                        "options": [
                            {
                                "key": "FEATURE_FLAG",
                                "default": "on",
                                "description": "Enable feature",
                            }
                        ],
                    }
                ],
                "api_surface": {
                    "rest_endpoints": [
                        {"path": "/v1/items", "purpose": "list items"},
                    ]
                },
                "extension_points": [
                    {"location": "src/plugins", "hook": "register", "example": "custom plugin"}
                ],
                "common_tasks": [
                    {"task": "python -m pytest", "steps": ["install", "run tests"]}
                ],
                "troubleshooting": [
                    {"symptom": "Timeout", "cause": "slow network", "fix": "retry"}
                ],
                "supported_protocols": ["http", "grpc"],
                "quick_reference": [{"topic": "CLI", "content": "Use --help"}],
            }
            self._write_yaml(workspace / "repos" / "knowledge" / "deep" / "demo-repo.yaml", deep_payload)

            result = self._run_ws6(workspace)
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

            deep_facts_path = workspace / "repos" / "knowledge" / "deep_facts" / "demo-repo.yaml"
            self.assertTrue(deep_facts_path.exists())
            deep_facts = yaml.safe_load(deep_facts_path.read_text(encoding="utf-8"))
            self.assertTrue(len(deep_facts.get("facts", [])) > 0)
            for fact in deep_facts["facts"]:
                self.assertTrue(0.0 <= float(fact["confidence"]) <= 1.0)
                self.assertTrue(isinstance(fact.get("evidence"), list) and len(fact["evidence"]) > 0)

            master_path = workspace / "master_deep_facts.yaml"
            self.assertTrue(master_path.exists())
            master = yaml.safe_load(master_path.read_text(encoding="utf-8"))
            self.assertTrue(len(master.get("facts", [])) > 0)

            coverage = yaml.safe_load(
                (workspace / "reports" / "ws6_deep_integration" / "coverage.yaml").read_text(encoding="utf-8")
            )
            mismatch = yaml.safe_load(
                (workspace / "reports" / "ws6_deep_integration" / "mismatch_report.yaml").read_text(encoding="utf-8")
            )
            validation_runs = yaml.safe_load(
                (workspace / "reports" / "ws6_deep_integration" / "validation_runs.yaml").read_text(encoding="utf-8")
            )

            self.assertIn("unmapped_sections_count", coverage["metrics"])
            self.assertIn("unmapped_sections_count", coverage["gate_metrics"])
            self.assertTrue(any(r["node_id"] == "repo::example/demo-repo" for r in coverage["metrics"]["per_repo"]))
            self.assertIn("gate_ready", mismatch)
            self.assertEqual(validation_runs["execution_mode"], "materialize_only")
            self.assertTrue(validation_runs["gate_bools"]["execution_results_pending_zero"])

            required_statuses = {row["status"] for row in validation_runs["required_commands"]}
            self.assertEqual(required_statuses, {"PLANNED"})
            result_statuses = {row["status"] for row in validation_runs["execution_results"]}
            self.assertTrue(result_statuses.issubset({"PASS", "FAIL", "NOT_RUN"}))
            self.assertNotIn("PENDING_EXECUTION", result_statuses)

    def test_unknown_predicate_in_draft_is_blocking_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(Path(tmp_dir))

            deep_payload = {
                "name": "demo-repo",
                "node_id": "repo::example/demo-repo",
                "github_full_name": "example/demo-repo",
                "html_url": "https://github.com/example/demo-repo",
                "source": "repos",
                "provenance": {
                    "shard": "repos",
                    "source_file": "repos/knowledge/deep/demo-repo.yaml",
                    "as_of": "2026-02-24",
                },
                "implementation_patterns": [{"pattern": "P1", "description": "d", "location": "a.py"}],
            }
            self._write_yaml(workspace / "repos" / "knowledge" / "deep" / "demo-repo.yaml", deep_payload)

            draft_payload = {
                "name": "demo-repo",
                "node_id": "repo::example/demo-repo",
                "github_full_name": "example/demo-repo",
                "html_url": "https://github.com/example/demo-repo",
                "source": "repos",
                "provenance": {
                    "shard": "repos",
                    "source_file": "repos/knowledge/deep_facts_draft/demo-repo.yaml",
                    "as_of": "2026-02-24",
                },
                "facts": [
                    {
                        "fact_type": "implementation_pattern",
                        "predicate": "mystery_predicate",
                        "object_kind": "concept",
                        "object_value": "P1",
                        "confidence": 0.95,
                        "as_of": "2026-02-24",
                        "evidence": [
                            {
                                "kind": "file_block",
                                "ref": "facts[0]",
                                "source_file": "repos/knowledge/deep_facts_draft/demo-repo.yaml",
                            }
                        ],
                    }
                ],
            }
            self._write_yaml(
                workspace / "repos" / "knowledge" / "deep_facts_draft" / "demo-repo.yaml",
                draft_payload,
            )

            result = self._run_ws6(workspace)
            self.assertNotEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

            mismatch = yaml.safe_load(
                (workspace / "reports" / "ws6_deep_integration" / "mismatch_report.yaml").read_text(encoding="utf-8")
            )
            reasons = [row.get("reason") for row in mismatch.get("blocking_findings", [])]
            self.assertIn("unknown_predicate", reasons)
            self.assertFalse(mismatch["gate_bools"]["unmapped_deep_predicates_zero"])

    def test_draft_authority_overrides_derived_collision_and_merges_duplicate_derived(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(Path(tmp_dir))

            deep_payload = {
                "name": "demo-repo",
                "node_id": "repo::example/demo-repo",
                "github_full_name": "example/demo-repo",
                "html_url": "https://github.com/example/demo-repo",
                "source": "repos",
                "provenance": {
                    "shard": "repos",
                    "source_file": "repos/knowledge/deep/demo-repo.yaml",
                    "as_of": "2026-02-24",
                },
                "implementation_patterns": [
                    {"pattern": "Factory Registration", "description": "d1", "location": "src/a.py"},
                    {"pattern": "Factory Registration", "description": "d1", "location": "src/a.py"},
                ],
            }
            self._write_yaml(workspace / "repos" / "knowledge" / "deep" / "demo-repo.yaml", deep_payload)

            draft_payload = {
                "name": "demo-repo",
                "node_id": "repo::example/demo-repo",
                "github_full_name": "example/demo-repo",
                "html_url": "https://github.com/example/demo-repo",
                "source": "repos",
                "provenance": {
                    "shard": "repos",
                    "source_file": "repos/knowledge/deep_facts_draft/demo-repo.yaml",
                    "as_of": "2026-02-24",
                },
                "facts": [
                    {
                        "fact_type": "implementation_pattern",
                        "predicate": "implements_pattern",
                        "object_kind": "concept",
                        "object_value": "Factory Registration",
                        "note": "authoritative draft",
                        "confidence": 0.91,
                        "as_of": "2026-02-24",
                        "evidence": [
                            {
                                "kind": "file_block",
                                "ref": "facts[0]",
                                "source_file": "repos/knowledge/deep_facts_draft/demo-repo.yaml",
                            }
                        ],
                    }
                ],
            }
            self._write_yaml(
                workspace / "repos" / "knowledge" / "deep_facts_draft" / "demo-repo.yaml",
                draft_payload,
            )

            result = self._run_ws6(workspace)
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

            deep_facts = yaml.safe_load(
                (workspace / "repos" / "knowledge" / "deep_facts" / "demo-repo.yaml").read_text(encoding="utf-8")
            )
            facts = deep_facts.get("facts", [])
            target = [f for f in facts if f.get("object_value") == "Factory Registration"]
            self.assertEqual(len(target), 1)
            self.assertIn("authoritative draft", target[0].get("note", ""))

            mismatch = yaml.safe_load(
                (workspace / "reports" / "ws6_deep_integration" / "mismatch_report.yaml").read_text(encoding="utf-8")
            )
            dropped_reasons = [row.get("reason") for row in mismatch.get("dropped_facts", [])]
            self.assertIn("draft_precedence_override", dropped_reasons)
            self.assertIn("duplicate_derived_merged", dropped_reasons)

    def test_new_section_extractors_map_testing_quick_reference_and_integration_family(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(Path(tmp_dir))

            deep_payload = {
                "name": "demo-repo",
                "node_id": "repo::example/demo-repo",
                "github_full_name": "example/demo-repo",
                "html_url": "https://github.com/example/demo-repo",
                "source": "repos",
                "provenance": {
                    "shard": "repos",
                    "source_file": "repos/knowledge/deep/demo-repo.yaml",
                    "as_of": "2026-02-24",
                },
                "testing": {
                    "framework": "pytest",
                    "coverage_areas": ["unit", "integration"],
                    "example": "pytest -q tests/ws6_deep_integration",
                },
                "quick_reference": [
                    {"topic": "Run tests", "content": "pytest -q tests/ws6_deep_integration"},
                    {"topic": "Docs", "content": "Read docs for setup"},
                ],
                "integrations": {
                    "api_endpoints": [
                        {"path": "/api/v1/chat", "method": "POST", "description": "chat endpoint"},
                    ],
                    "providers": ["OpenAI", "Anthropic"],
                },
                "tech_stack": ["Python", "FastAPI"],
                "technology_stack": {"vector_db": ["Qdrant"]},
                "api_structure": {
                    "chat": {
                        "path": "/api/v1/chat",
                        "operations": ["create"],
                    }
                },
            }
            self._write_yaml(workspace / "repos" / "knowledge" / "deep" / "demo-repo.yaml", deep_payload)

            result = self._run_ws6(workspace)
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

            deep_facts = yaml.safe_load(
                (workspace / "repos" / "knowledge" / "deep_facts" / "demo-repo.yaml").read_text(encoding="utf-8")
            )
            facts = deep_facts.get("facts", [])

            testing_commands = [
                fact
                for fact in facts
                if fact.get("provenance", {}).get("source_section", "").startswith("testing.")
                and fact.get("fact_type") == "operational_task"
                and fact.get("predicate") == "supports_task"
                and fact.get("object_kind") == "command"
            ]
            self.assertTrue(testing_commands)

            testing_patterns = [
                fact
                for fact in facts
                if fact.get("provenance", {}).get("source_section", "").startswith("testing.")
                and fact.get("fact_type") == "implementation_pattern"
                and fact.get("predicate") == "implements_pattern"
                and fact.get("object_kind") == "concept"
            ]
            self.assertTrue(testing_patterns)

            api_routes = [
                fact
                for fact in facts
                if fact.get("fact_type") == "api_endpoint"
                and fact.get("predicate") == "exposes_api_endpoint"
                and fact.get("object_kind") == "api_route"
            ]
            self.assertTrue(any(fact.get("object_value") == "/api/v1/chat" for fact in api_routes))

            components = [
                fact
                for fact in facts
                if fact.get("fact_type") == "component"
                and fact.get("predicate") == "has_component"
                and fact.get("object_kind") == "concept"
            ]
            self.assertTrue(any(fact.get("object_value") == "Python" for fact in components))

            mismatch = yaml.safe_load(
                (workspace / "reports" / "ws6_deep_integration" / "mismatch_report.yaml").read_text(encoding="utf-8")
            )
            unmapped_sections = {
                row.get("section")
                for row in mismatch.get("non_blocking_findings", [])
                if row.get("reason") == "unmapped_section"
            }
            self.assertFalse(
                {
                    "testing",
                    "quick_reference",
                    "integrations",
                    "tech_stack",
                    "technology_stack",
                    "api_structure",
                }
                & unmapped_sections
            )

    def test_new_section_extractors_map_languages_related_type_primary_language_and_ports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(Path(tmp_dir))

            deep_payload = {
                "name": "demo-repo",
                "node_id": "repo::example/demo-repo",
                "github_full_name": "example/demo-repo",
                "html_url": "https://github.com/example/demo-repo",
                "source": "repos",
                "provenance": {
                    "shard": "repos",
                    "source_file": "repos/knowledge/deep/demo-repo.yaml",
                    "as_of": "2026-02-24",
                },
                "type": "application_platform",
                "primary_language": "Go",
                "languages": ["Python", "Rust"],
                "ports": {"grpc": 19530, "metrics": 9091},
                "related_repos": ["langchain", "llama_index"],
            }
            self._write_yaml(workspace / "repos" / "knowledge" / "deep" / "demo-repo.yaml", deep_payload)

            result = self._run_ws6(workspace)
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)

            deep_facts = yaml.safe_load(
                (workspace / "repos" / "knowledge" / "deep_facts" / "demo-repo.yaml").read_text(encoding="utf-8")
            )
            facts = deep_facts.get("facts", [])

            repo_type_facts = [
                fact
                for fact in facts
                if fact.get("provenance", {}).get("source_section", "").startswith("type.")
                and fact.get("fact_type") == "component"
                and fact.get("predicate") == "has_component"
                and fact.get("object_kind") == "concept"
                and fact.get("object_value") == "application_platform"
            ]
            self.assertTrue(repo_type_facts)

            primary_language_facts = [
                fact
                for fact in facts
                if fact.get("provenance", {}).get("source_section", "").startswith("primary_language.")
                and fact.get("fact_type") == "component"
                and fact.get("predicate") == "has_component"
                and fact.get("object_kind") == "concept"
                and fact.get("object_value") == "Go"
            ]
            self.assertTrue(primary_language_facts)

            language_facts = [
                fact
                for fact in facts
                if fact.get("provenance", {}).get("source_section", "").startswith("languages")
                and fact.get("fact_type") == "component"
                and fact.get("predicate") == "has_component"
                and fact.get("object_kind") == "concept"
                and fact.get("object_value") in {"Python", "Rust"}
            ]
            self.assertEqual({fact.get("object_value") for fact in language_facts}, {"Python", "Rust"})

            port_facts = [
                fact
                for fact in facts
                if fact.get("provenance", {}).get("source_section", "").startswith("ports")
                and fact.get("fact_type") == "config_option"
                and fact.get("predicate") == "has_config_option"
                and fact.get("object_kind") == "config_key"
                and fact.get("object_value") in {"grpc", "metrics"}
            ]
            self.assertEqual({fact.get("object_value") for fact in port_facts}, {"grpc", "metrics"})
            self.assertTrue(any("19530" in fact.get("note", "") for fact in port_facts))
            self.assertTrue(any("9091" in fact.get("note", "") for fact in port_facts))

            related_repo_facts = [
                fact
                for fact in facts
                if fact.get("provenance", {}).get("source_section", "").startswith("related_repos")
                and fact.get("fact_type") == "extension_point"
                and fact.get("predicate") == "has_extension_point"
                and fact.get("object_kind") == "concept"
                and fact.get("object_value") in {"langchain", "llama_index"}
            ]
            self.assertEqual({fact.get("object_value") for fact in related_repo_facts}, {"langchain", "llama_index"})

            mismatch = yaml.safe_load(
                (workspace / "reports" / "ws6_deep_integration" / "mismatch_report.yaml").read_text(encoding="utf-8")
            )
            unmapped_sections = {
                row.get("section")
                for row in mismatch.get("non_blocking_findings", [])
                if row.get("reason") == "unmapped_section"
            }
            self.assertFalse(
                {"languages", "related_repos", "type", "primary_language", "ports"} & unmapped_sections
            )


if __name__ == "__main__":
    unittest.main()
