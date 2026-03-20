#!/usr/bin/env python3
"""query_master.py regression tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "query_master.py"
LOADER_SCRIPT = ROOT / "tools" / "query_master_loader.py"


class QueryMasterPatternTests(unittest.TestCase):
    def _sha256_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        hasher.update(path.read_bytes())
        return hasher.hexdigest()

    def _write_yaml(self, path: Path, payload: dict) -> None:
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def _make_workspace(self, tmp_dir: str) -> Path:
        workspace = Path(tmp_dir)
        self._write_yaml(workspace / "master_index.yaml", {"repos": []})
        self._write_yaml(workspace / "master_graph.yaml", {"nodes": [], "edges": []})
        self._write_yaml(workspace / "master_deep_facts.yaml", {"facts": []})

        db_path = workspace / "knowledge.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "CREATE TABLE compile_metadata ("
                "source_index_hash TEXT, "
                "source_graph_hash TEXT, "
                "source_facts_hash TEXT)"
            )
            conn.execute(
                "CREATE TABLE repos ("
                "node_id TEXT PRIMARY KEY, "
                "name TEXT NOT NULL, "
                "github_full_name TEXT, "
                "html_url TEXT, "
                "category TEXT, "
                "shard TEXT, "
                "summary TEXT, "
                "source TEXT, "
                "raw_yaml TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE facts ("
                "fact_id TEXT PRIMARY KEY, "
                "node_id TEXT NOT NULL, "
                "predicate TEXT NOT NULL, "
                "object_kind TEXT, "
                "object_value TEXT, "
                "note TEXT)"
            )

            conn.execute(
                "INSERT INTO compile_metadata VALUES (?, ?, ?)",
                (
                    self._sha256_file(workspace / "master_index.yaml"),
                    self._sha256_file(workspace / "master_graph.yaml"),
                    self._sha256_file(workspace / "master_deep_facts.yaml"),
                ),
            )

            repos = [
                ("repo::qdrant/qdrant", "Qdrant", "qdrant/qdrant", "vector_database"),
                ("repo::weaviate/weaviate", "Weaviate", "weaviate/weaviate", "vector_database"),
                ("repo::lancedb/lancedb", "LanceDB", "lancedb/lancedb", "vector_database"),
                ("repo::chroma-core/chroma", "Chroma", "chroma-core/chroma", "vector_database"),
                ("repo::open-webui/open-webui", "Open WebUI", "open-webui/open-webui", "ui_tools"),
            ]
            for node_id, name, github_full_name, category in repos:
                conn.execute(
                    "INSERT INTO repos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        node_id,
                        name,
                        github_full_name,
                        f"https://github.com/{github_full_name}",
                        category,
                        "repos",
                        f"{name} summary",
                        "repos",
                        "{}",
                    ),
                )

            facts = [
                ("fact-1", "repo::qdrant/qdrant", "has_failure_mode", "issue", "Query timeout under high-ingest load"),
                ("fact-2", "repo::weaviate/weaviate", "has_failure_mode", "issue", "Query timeout under high-ingest load"),
                ("fact-3", "repo::lancedb/lancedb", "has_failure_mode", "issue", "Query timeout under high-ingest load"),
                ("fact-4", "repo::chroma-core/chroma", "has_failure_mode", "issue", "Background indexing stalls"),
                ("fact-5", "repo::open-webui/open-webui", "has_failure_mode", "issue", "Query timeout under high-ingest load"),
                ("fact-6", "repo::qdrant/qdrant", "uses_protocol", "protocol", "gRPC"),
            ]
            for fact_id, node_id, predicate, object_kind, object_value in facts:
                conn.execute(
                    "INSERT INTO facts VALUES (?, ?, ?, ?, ?, ?)",
                    (fact_id, node_id, predicate, object_kind, object_value, ""),
                )

            conn.commit()
        finally:
            conn.close()

        return workspace

    def _run_query(self, workspace: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace-root", str(workspace), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        output_lines = result.stdout.strip().splitlines()
        if output_lines and output_lines[-1].startswith("# query_ms:"):
            output_lines = output_lines[:-1]
        payload = yaml.safe_load("\n".join(output_lines)) if output_lines else {}
        return result, payload

    def test_pattern_supports_category_filter_in_flat_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)

            result, payload = self._run_query(
                workspace,
                "pattern",
                "--predicate",
                "has_failure_mode",
                "--category",
                "VECTOR_DATABASE",
                "--value",
                "timeout",
                "--limit",
                "10",
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            self.assertEqual(payload["artifact_type"], "master_query_pattern")
            self.assertEqual(payload["category_filter"], "VECTOR_DATABASE")
            self.assertEqual(payload["value_filter"], "timeout")
            self.assertEqual(payload["result_count"], 3)
            self.assertEqual(
                [row["node_id"] for row in payload["results"]],
                [
                    "repo::lancedb/lancedb",
                    "repo::qdrant/qdrant",
                    "repo::weaviate/weaviate",
                ],
            )
            self.assertTrue(all(row["category"] == "vector_database" for row in payload["results"]))

    def test_pattern_frequency_groups_repo_counts_with_examples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)

            result, payload = self._run_query(
                workspace,
                "pattern",
                "--predicate",
                "has_failure_mode",
                "--category",
                "vector_database",
                "--frequency",
                "--limit",
                "10",
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            self.assertEqual(payload["artifact_type"], "master_query_pattern_frequency")
            self.assertEqual(payload["category_filter"], "vector_database")
            self.assertEqual(payload["scope_repo_count"], 4)
            self.assertEqual(payload["grouped_result_count"], 2)
            self.assertEqual(payload["results"][0]["object_value"], "Query timeout under high-ingest load")
            self.assertEqual(payload["results"][0]["repo_count"], 3)
            self.assertEqual(payload["results"][0]["repo_fraction"], 0.75)
            self.assertEqual(
                payload["results"][0]["example_repos"],
                [
                    "lancedb/lancedb",
                    "qdrant/qdrant",
                    "weaviate/weaviate",
                ],
            )
            self.assertEqual(payload["results"][1]["object_value"], "Background indexing stalls")
            self.assertEqual(payload["results"][1]["repo_count"], 1)
            self.assertEqual(payload["results"][1]["repo_fraction"], 0.25)

    def test_loader_passes_boolean_pattern_frequency_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)

            result = subprocess.run(
                [
                    sys.executable,
                    str(LOADER_SCRIPT),
                    "--workspace-root",
                    str(workspace),
                    "--machine-reference",
                    str(ROOT / "docs" / "query_master_reference.machine.yaml"),
                    "--query-script",
                    str(SCRIPT),
                    "--command",
                    "pattern",
                    "--arg",
                    "predicate=has_failure_mode",
                    "--arg",
                    "category=vector_database",
                    "--arg",
                    "frequency=true",
                    "--arg",
                    "limit=3",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            payload = yaml.safe_load(result.stdout)
            self.assertTrue(payload["ok"])
            self.assertEqual(payload["parsed"]["artifact_type"], "master_query_pattern_frequency")
            self.assertIn("--frequency", payload["argv"])


class QueryMasterPreflightTests(unittest.TestCase):
    def _write_yaml(self, path: Path, payload: dict) -> None:
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def _sha256_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        hasher.update(path.read_bytes())
        return hasher.hexdigest()

    def _make_workspace(self, tmp_dir: str) -> Path:
        workspace = Path(tmp_dir)
        self._write_yaml(workspace / "master_index.yaml", {"repos": []})
        self._write_yaml(workspace / "master_graph.yaml", {"nodes": [], "edges": []})
        self._write_yaml(workspace / "master_deep_facts.yaml", {"facts": []})

        db_path = workspace / "knowledge.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "CREATE TABLE compile_metadata ("
                "source_index_hash TEXT, "
                "source_graph_hash TEXT, "
                "source_facts_hash TEXT)"
            )
            conn.execute(
                "CREATE TABLE repos ("
                "node_id TEXT PRIMARY KEY, "
                "name TEXT NOT NULL, "
                "github_full_name TEXT, "
                "html_url TEXT, "
                "category TEXT, "
                "shard TEXT, "
                "summary TEXT, "
                "source TEXT, "
                "raw_yaml TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE facts ("
                "fact_id TEXT PRIMARY KEY, "
                "node_id TEXT NOT NULL, "
                "predicate TEXT NOT NULL, "
                "object_kind TEXT, "
                "object_value TEXT, "
                "note TEXT)"
            )
            conn.execute(
                "INSERT INTO compile_metadata VALUES (?, ?, ?)",
                (
                    self._sha256_file(workspace / "master_index.yaml"),
                    self._sha256_file(workspace / "master_graph.yaml"),
                    self._sha256_file(workspace / "master_deep_facts.yaml"),
                ),
            )

            repos = [
                ("repo::qdrant/qdrant", "Qdrant", "qdrant/qdrant", "vector_database"),
                ("repo::weaviate/weaviate", "Weaviate", "weaviate/weaviate", "vector_database"),
                ("repo::lancedb/lancedb", "LanceDB", "lancedb/lancedb", "vector_database"),
                ("repo::chroma-core/chroma", "Chroma", "chroma-core/chroma", "vector_database"),
                ("repo::open-webui/open-webui", "Open WebUI", "open-webui/open-webui", "ui_tools"),
            ]
            for node_id, name, github_full_name, category in repos:
                conn.execute(
                    "INSERT INTO repos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        node_id,
                        name,
                        github_full_name,
                        f"https://github.com/{github_full_name}",
                        category,
                        "repos",
                        f"{name} summary",
                        "repos",
                        "{}",
                    ),
                )

            # Three vector_database repos share "Query timeout under high-ingest load".
            # Qdrant and Weaviate have notes; LanceDB does not.
            # Chroma has a distinct failure mode with a note containing "batch writes".
            # Open WebUI is ui_tools — must not appear in vector_database preflight.
            facts = [
                ("pf-1", "repo::qdrant/qdrant", "has_failure_mode", "issue",
                 "Query timeout under high-ingest load", "Seen during sustained write load tests"),
                ("pf-2", "repo::weaviate/weaviate", "has_failure_mode", "issue",
                 "Query timeout under high-ingest load", "Manifests when indexing exceeds 1M vectors"),
                ("pf-3", "repo::lancedb/lancedb", "has_failure_mode", "issue",
                 "Query timeout under high-ingest load", ""),
                ("pf-4", "repo::chroma-core/chroma", "has_failure_mode", "issue",
                 "Background indexing stalls", "Reproducible with large batch writes"),
                ("pf-5", "repo::open-webui/open-webui", "has_failure_mode", "issue",
                 "Query timeout under high-ingest load", ""),
            ]
            for fact_id, node_id, predicate, object_kind, object_value, note in facts:
                conn.execute(
                    "INSERT INTO facts VALUES (?, ?, ?, ?, ?, ?)",
                    (fact_id, node_id, predicate, object_kind, object_value, note),
                )

            conn.commit()
        finally:
            conn.close()

        return workspace

    def _run_query(self, workspace: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace-root", str(workspace), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        output_lines = result.stdout.strip().splitlines()
        if output_lines and output_lines[-1].startswith("# query_ms:"):
            output_lines = output_lines[:-1]
        payload = yaml.safe_load("\n".join(output_lines)) if output_lines else {}
        return result, payload

    def test_preflight_basic_output_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            result, payload = self._run_query(
                workspace, "preflight", "--category", "vector_database", "--limit", "10"
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            self.assertEqual(payload["artifact_type"], "master_query_preflight")
            self.assertEqual(payload["category_filter"], "vector_database")
            self.assertIsNone(payload["term_filter"])
            self.assertEqual(payload["scope_repo_count"], 4)
            self.assertEqual(payload["result_count"], 2)

            # "Query timeout" has 3 repos — must rank first
            self.assertEqual(payload["results"][0]["failure_mode"], "Query timeout under high-ingest load")
            self.assertEqual(payload["results"][0]["repo_count"], 3)
            self.assertAlmostEqual(payload["results"][0]["repo_fraction"], 0.75, places=3)
            self.assertEqual(len(payload["results"][0]["example_repos"]), 3)

            # "Background indexing stalls" has 1 repo — ranks second
            self.assertEqual(payload["results"][1]["failure_mode"], "Background indexing stalls")
            self.assertEqual(payload["results"][1]["repo_count"], 1)
            self.assertAlmostEqual(payload["results"][1]["repo_fraction"], 0.25, places=3)

    def test_preflight_term_filter_object_value(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            result, payload = self._run_query(
                workspace, "preflight", "--category", "vector_database", "--term", "Background"
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            self.assertEqual(payload["term_filter"], "Background")
            self.assertEqual(payload["result_count"], 1)
            self.assertEqual(payload["results"][0]["failure_mode"], "Background indexing stalls")

    def test_preflight_term_filter_matches_note(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            # "batch writes" only appears in the note for "Background indexing stalls",
            # not in any object_value — verifies note-based filtering.
            result, payload = self._run_query(
                workspace, "preflight", "--category", "vector_database", "--term", "batch writes"
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            self.assertEqual(payload["term_filter"], "batch writes")
            self.assertEqual(payload["result_count"], 1)
            self.assertEqual(payload["results"][0]["failure_mode"], "Background indexing stalls")

    def test_preflight_evidence_notes_capped_at_two(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            result, payload = self._run_query(
                workspace, "preflight", "--category", "vector_database"
            )

            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            timeout_result = payload["results"][0]
            self.assertEqual(timeout_result["failure_mode"], "Query timeout under high-ingest load")
            # Three repos matched but only two had non-empty notes
            self.assertEqual(len(timeout_result["evidence_notes"]), 2)
            self.assertIn("Seen during sustained write load tests", timeout_result["evidence_notes"])
            self.assertIn("Manifests when indexing exceeds 1M vectors", timeout_result["evidence_notes"])


class QueryMasterRiskcheckTests(unittest.TestCase):
    def _write_yaml(self, path: Path, payload: dict) -> None:
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def _sha256_file(self, path: Path) -> str:
        hasher = hashlib.sha256()
        hasher.update(path.read_bytes())
        return hasher.hexdigest()

    def _make_workspace(self, tmp_dir: str) -> Path:
        workspace = Path(tmp_dir)
        self._write_yaml(workspace / "master_index.yaml", {"repos": []})
        self._write_yaml(workspace / "master_graph.yaml", {"nodes": [], "edges": []})
        self._write_yaml(workspace / "master_deep_facts.yaml", {"facts": []})

        db_path = workspace / "knowledge.db"
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "CREATE TABLE compile_metadata ("
                "source_index_hash TEXT, "
                "source_graph_hash TEXT, "
                "source_facts_hash TEXT)"
            )
            conn.execute(
                "CREATE TABLE repos ("
                "node_id TEXT PRIMARY KEY, "
                "name TEXT NOT NULL, "
                "github_full_name TEXT, "
                "html_url TEXT, "
                "category TEXT, "
                "shard TEXT, "
                "summary TEXT, "
                "source TEXT, "
                "raw_yaml TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE facts ("
                "fact_id TEXT PRIMARY KEY, "
                "node_id TEXT NOT NULL, "
                "predicate TEXT NOT NULL, "
                "object_kind TEXT, "
                "object_value TEXT, "
                "note TEXT)"
            )
            conn.execute(
                "INSERT INTO compile_metadata VALUES (?, ?, ?)",
                (
                    self._sha256_file(workspace / "master_index.yaml"),
                    self._sha256_file(workspace / "master_graph.yaml"),
                    self._sha256_file(workspace / "master_deep_facts.yaml"),
                ),
            )

            # 5 repos in agent_cli, 1 in other_cat
            repos = [
                ("repo::org/repo-a", "repo-a", "org/repo-a", "agent_cli"),
                ("repo::org/repo-b", "repo-b", "org/repo-b", "agent_cli"),
                ("repo::org/repo-c", "repo-c", "org/repo-c", "agent_cli"),
                ("repo::org/repo-d", "repo-d", "org/repo-d", "agent_cli"),
                ("repo::org/repo-e", "repo-e", "org/repo-e", "agent_cli"),
                ("repo::org/repo-x", "repo-x", "org/repo-x", "other_cat"),
            ]
            for node_id, name, github_full_name, category in repos:
                conn.execute(
                    "INSERT INTO repos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (node_id, name, github_full_name, f"https://github.com/{github_full_name}",
                     category, "repos", f"{name} summary", "repos", "{}"),
                )

            # implements_pattern "Command-driven task loop" in repos a, b, c (3/5 = 0.6) → established
            # has_component "ACP server" in repo c only (1/5 = 0.2, count=1) → rare
            # uses_protocol "MCP" nowhere in agent_cli → absent
            # uses_protocol "gRPC" in repos a, b (2/5 = 0.4) → established
            # repo-x has "Command-driven task loop" but in other_cat — must not count for agent_cli
            facts = [
                ("rc-1", "repo::org/repo-a", "implements_pattern", "concept", "Command-driven task loop"),
                ("rc-2", "repo::org/repo-b", "implements_pattern", "concept", "Command-driven task loop"),
                ("rc-3", "repo::org/repo-c", "implements_pattern", "concept", "Command-driven task loop"),
                ("rc-4", "repo::org/repo-c", "has_component", "concept", "ACP server"),
                ("rc-5", "repo::org/repo-a", "uses_protocol", "protocol", "gRPC"),
                ("rc-6", "repo::org/repo-b", "uses_protocol", "protocol", "gRPC"),
                ("rc-7", "repo::org/repo-x", "implements_pattern", "concept", "Command-driven task loop"),
            ]
            for fact_id, node_id, predicate, object_kind, object_value in facts:
                conn.execute(
                    "INSERT INTO facts VALUES (?, ?, ?, ?, ?, ?)",
                    (fact_id, node_id, predicate, object_kind, object_value, ""),
                )

            conn.commit()
        finally:
            conn.close()

        return workspace

    def _run_query(self, workspace: Path, *args: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace-root", str(workspace), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        output_lines = result.stdout.strip().splitlines()
        if output_lines and output_lines[-1].startswith("# query_ms:"):
            output_lines = output_lines[:-1]
        payload = yaml.safe_load("\n".join(output_lines)) if output_lines else {}
        return result, payload

    def test_riskcheck_missing_proposal_terms_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            result, payload = self._run_query(workspace, "riskcheck", "--category", "agent_cli")
            self.assertEqual(result.returncode, 2)
            self.assertIn("error", payload)

    def test_riskcheck_established_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            result, payload = self._run_query(
                workspace, "riskcheck", "--category", "agent_cli",
                "--pattern", "command-driven"
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            self.assertEqual(payload["artifact_type"], "master_query_riskcheck")
            self.assertEqual(payload["category_filter"], "agent_cli")
            self.assertEqual(payload["scope_repo_count"], 5)
            self.assertEqual(payload["signal_counts"]["established_in_category"], 1)
            self.assertEqual(payload["signal_counts"]["rare_in_category"], 0)
            self.assertEqual(payload["signal_counts"]["absent_from_category"], 0)
            sig = payload["signals"]["established_in_category"][0]
            self.assertEqual(sig["input_kind"], "pattern")
            self.assertEqual(sig["predicate"], "implements_pattern")
            self.assertEqual(sig["matched_repo_count"], 3)
            self.assertAlmostEqual(sig["matched_repo_fraction"], 0.6, places=3)
            self.assertIn("Command-driven task loop", sig["matched_values"])
            self.assertEqual(len(sig["example_repos"]), 3)

    def test_riskcheck_rare_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            result, payload = self._run_query(
                workspace, "riskcheck", "--category", "agent_cli",
                "--component", "ACP server"
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            self.assertEqual(payload["signal_counts"]["rare_in_category"], 1)
            self.assertEqual(payload["signal_counts"]["established_in_category"], 0)
            self.assertEqual(payload["signal_counts"]["absent_from_category"], 0)
            sig = payload["signals"]["rare_in_category"][0]
            self.assertEqual(sig["matched_repo_count"], 1)
            self.assertAlmostEqual(sig["matched_repo_fraction"], 0.2, places=3)

    def test_riskcheck_absent_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            result, payload = self._run_query(
                workspace, "riskcheck", "--category", "agent_cli",
                "--protocol", "MCP"
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            self.assertEqual(payload["signal_counts"]["absent_from_category"], 1)
            sig = payload["signals"]["absent_from_category"][0]
            self.assertEqual(sig["matched_repo_count"], 0)
            self.assertEqual(sig["matched_repo_fraction"], 0.0)
            self.assertEqual(sig["matched_values"], [])
            self.assertEqual(sig["example_repos"], [])

    def test_riskcheck_category_is_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            result_lower, payload_lower = self._run_query(
                workspace, "riskcheck", "--category", "agent_cli",
                "--pattern", "command-driven"
            )
            result_upper, payload_upper = self._run_query(
                workspace, "riskcheck", "--category", "AGENT_CLI",
                "--pattern", "command-driven"
            )
            self.assertEqual(result_lower.returncode, 0)
            self.assertEqual(result_upper.returncode, 0)
            self.assertEqual(
                payload_lower["signal_counts"], payload_upper["signal_counts"]
            )
            self.assertEqual(
                payload_lower["scope_repo_count"], payload_upper["scope_repo_count"]
            )

    def test_riskcheck_predicate_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            result, payload = self._run_query(
                workspace, "riskcheck", "--category", "agent_cli",
                "--pattern", "command-driven",
                "--component", "ACP",
                "--protocol", "MCP",
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            all_sigs = (
                payload["signals"]["established_in_category"]
                + payload["signals"]["rare_in_category"]
                + payload["signals"]["absent_from_category"]
            )
            predicates = {s["input_kind"]: s["predicate"] for s in all_sigs}
            self.assertEqual(predicates["pattern"], "implements_pattern")
            self.assertEqual(predicates["component"], "has_component")
            self.assertEqual(predicates["protocol"], "uses_protocol")

    def test_riskcheck_unique_repo_counting(self) -> None:
        # Repo c has only one fact for ACP server — counted once
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            result, payload = self._run_query(
                workspace, "riskcheck", "--category", "agent_cli",
                "--component", "ACP"
            )
            self.assertEqual(result.returncode, 0)
            sig = payload["signals"]["rare_in_category"][0]
            self.assertEqual(sig["matched_repo_count"], 1)

    def test_riskcheck_category_scoping_excludes_other_categories(self) -> None:
        # repo-x is in other_cat and also has "Command-driven task loop"
        # It must NOT count toward agent_cli scope or matches
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            result, payload = self._run_query(
                workspace, "riskcheck", "--category", "agent_cli",
                "--pattern", "command-driven"
            )
            self.assertEqual(result.returncode, 0)
            sig = payload["signals"]["established_in_category"][0]
            self.assertEqual(sig["matched_repo_count"], 3)
            self.assertNotIn("org/repo-x", sig["example_repos"])

    def test_riskcheck_multiple_buckets_sorting(self) -> None:
        # established: "command-driven" (count=3), "gRPC" (count=2)
        # absent: "MCP" (count=0)
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            result, payload = self._run_query(
                workspace, "riskcheck", "--category", "agent_cli",
                "--pattern", "command-driven",
                "--protocol", "gRPC",
                "--protocol", "MCP",
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + "\n" + result.stderr)
            self.assertEqual(payload["signal_counts"]["established_in_category"], 2)
            self.assertEqual(payload["signal_counts"]["absent_from_category"], 1)
            # Within established bucket: sorted by count desc then term
            estab = payload["signals"]["established_in_category"]
            self.assertEqual(estab[0]["matched_repo_count"], 3)  # command-driven
            self.assertEqual(estab[1]["matched_repo_count"], 2)  # gRPC

    def test_riskcheck_example_repos_capped_at_three(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            result, payload = self._run_query(
                workspace, "riskcheck", "--category", "agent_cli",
                "--pattern", "command-driven"
            )
            self.assertEqual(result.returncode, 0)
            sig = payload["signals"]["established_in_category"][0]
            self.assertLessEqual(len(sig["example_repos"]), 3)
            self.assertLessEqual(len(sig["matched_values"]), 3)

    def test_riskcheck_proposal_echoed_in_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            workspace = self._make_workspace(tmp_dir)
            result, payload = self._run_query(
                workspace, "riskcheck", "--category", "agent_cli",
                "--pattern", "command-driven",
                "--component", "ACP",
                "--protocol", "MCP",
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("patterns", payload["proposal"])
            self.assertIn("components", payload["proposal"])
            self.assertIn("protocols", payload["proposal"])


if __name__ == "__main__":
    unittest.main()
