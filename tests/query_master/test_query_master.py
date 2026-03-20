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


if __name__ == "__main__":
    unittest.main()
