#!/usr/bin/env python3
"""WS7 read model compiler.

Reads canonical YAML artifacts and materializes a SQLite read model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

SCHEMA_VERSION = "1.1.0"
INDEX_FILE = "master_index.yaml"
GRAPH_FILE = "master_graph.yaml"
FACTS_FILE = "master_deep_facts.yaml"
OUTPUT_DB = "knowledge.db"
LOG_FILE = "reports/ws7_read_model/compile_log.yaml"


class GateFailure(Exception):
    def __init__(self, gate_name: str, detail: str):
        super().__init__(detail)
        self.gate_name = gate_name
        self.detail = detail


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"invalid timestamp: {value!r}")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed


def load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"YAML root must be a mapping: {path.as_posix()}")
    return payload


def ensure_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    out: list[dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            out.append(item)
    return out


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def json_dump(item: dict[str, Any]) -> str:
    return json.dumps(item, ensure_ascii=False, default=str)


def make_log_template(started_at_utc: str, force_flag: bool) -> dict[str, Any]:
    return {
        "compile_run": {
            "started_at_utc": started_at_utc,
            "finished_at_utc": None,
            "duration_ms": 0,
            "result": "FAILED",
            "force_flag": bool(force_flag),
        },
        "source_files": {
            "index": {
                "path": INDEX_FILE,
                "sha256": "",
                "generated_at_utc": "",
                "repo_count": 0,
            },
            "graph": {
                "path": GRAPH_FILE,
                "sha256": "",
                "generated_at_utc": "",
                "node_count": 0,
                "edge_count": 0,
            },
            "facts": {
                "path": FACTS_FILE,
                "sha256": "",
                "generated_at_utc": "",
                "fact_count": 0,
            },
        },
        "gates": {
            "snapshot_consistency": {
                "status": "fail",
                "detail": "not run",
            },
            "row_count_parity": {
                "status": "fail",
                "expected": {"repos": 0, "nodes": 0, "edges": 0, "facts": 0},
                "actual": {"repos": 0, "nodes": 0, "edges": 0, "facts": 0},
            },
            "orphan_edge_detection": {
                "status": "fail",
                "orphan_count": 0,
                "orphans": [],
            },
            "query_parity": {
                "status": "fail",
                "checks": [],
            },
            "deterministic_rebuild": {
                "status": "fail",
                "detail": "not run",
            },
        },
        "output": {
            "path": OUTPUT_DB,
            "size_bytes": 0,
            "table_counts": {
                "repos": 0,
                "nodes": 0,
                "edges": 0,
                "facts": 0,
                "compile_metadata": 0,
            },
        },
    }


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA foreign_keys=ON;

        CREATE TABLE repos (
          node_id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          github_full_name TEXT,
          html_url TEXT,
          category TEXT,
          shard TEXT,
          summary TEXT,
          source TEXT,
          raw_yaml TEXT NOT NULL
        );

        CREATE INDEX idx_repos_name ON repos(name);
        CREATE INDEX idx_repos_github_full_name ON repos(github_full_name);
        CREATE INDEX idx_repos_category ON repos(category);
        CREATE INDEX idx_repos_shard ON repos(shard);

        CREATE TABLE nodes (
          node_id TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          label TEXT NOT NULL
        );

        CREATE INDEX idx_nodes_kind ON nodes(kind);

        CREATE TABLE edges (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          src_id TEXT NOT NULL REFERENCES nodes(node_id),
          dst_id TEXT NOT NULL REFERENCES nodes(node_id),
          dst_kind TEXT,
          relation TEXT NOT NULL,
          note TEXT,
          as_of TEXT,
          raw_yaml TEXT NOT NULL
        );

        CREATE INDEX idx_edges_src_id ON edges(src_id);
        CREATE INDEX idx_edges_dst_id ON edges(dst_id);
        CREATE INDEX idx_edges_relation ON edges(relation);
        CREATE INDEX idx_edges_src_relation ON edges(src_id, relation);
        CREATE INDEX idx_edges_dst_relation ON edges(dst_id, relation);

        CREATE TABLE facts (
          fact_id TEXT PRIMARY KEY,
          node_id TEXT NOT NULL REFERENCES repos(node_id),
          fact_type TEXT,
          predicate TEXT,
          object_kind TEXT,
          object_value TEXT,
          confidence REAL,
          note TEXT,
          as_of TEXT,
          source_file TEXT,
          source_section TEXT,
          raw_yaml TEXT NOT NULL
        );

        CREATE INDEX idx_facts_node_id ON facts(node_id);
        CREATE INDEX idx_facts_predicate ON facts(predicate);
        CREATE INDEX idx_facts_fact_type ON facts(fact_type);
        CREATE INDEX idx_facts_object_kind ON facts(object_kind);
        CREATE INDEX idx_facts_node_predicate ON facts(node_id, predicate);

        CREATE TABLE compile_metadata (
          schema_version TEXT,
          compiled_at_utc TEXT,
          source_index_hash TEXT,
          source_graph_hash TEXT,
          source_facts_hash TEXT,
          source_index_generated_at TEXT,
          source_graph_generated_at TEXT,
          source_facts_generated_at TEXT,
          repo_count INTEGER,
          node_count INTEGER,
          edge_count INTEGER,
          fact_count INTEGER
        );
        """
    )


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in ("repos", "nodes", "edges", "facts", "compile_metadata"):
        counts[table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    return counts


def populate_database(
    db_path: Path,
    repos: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    source_hashes: dict[str, str],
    source_generated_at: dict[str, str],
    compiled_at_utc: str,
) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        create_schema(conn)

        with conn:
            conn.executemany(
                """
                INSERT INTO repos (
                  node_id, name, github_full_name, html_url, category, shard, summary, source, raw_yaml
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        repo.get("node_id"),
                        repo.get("name"),
                        repo.get("github_full_name"),
                        repo.get("html_url"),
                        repo.get("category"),
                        repo.get("provenance", {}).get("shard"),
                        repo.get("summary"),
                        repo.get("source"),
                        json_dump(repo),
                    )
                    for repo in repos
                ],
            )

            conn.executemany(
                """
                INSERT INTO nodes (node_id, kind, label)
                VALUES (?, ?, ?)
                """,
                [
                    (
                        node.get("node_id"),
                        node.get("kind"),
                        node.get("label"),
                    )
                    for node in nodes
                ],
            )

            conn.executemany(
                """
                INSERT INTO edges (src_id, dst_id, dst_kind, relation, note, as_of, raw_yaml)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        edge.get("src_id"),
                        edge.get("dst_id"),
                        edge.get("dst_kind"),
                        edge.get("relation"),
                        edge.get("note"),
                        edge.get("as_of"),
                        json_dump(edge),
                    )
                    for edge in edges
                ],
            )

            conn.executemany(
                """
                INSERT INTO facts (
                  fact_id, node_id, fact_type, predicate, object_kind, object_value,
                  confidence, note, as_of, source_file, source_section, raw_yaml
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        fact.get("fact_id"),
                        fact.get("node_id"),
                        fact.get("fact_type"),
                        fact.get("predicate"),
                        fact.get("object_kind"),
                        fact.get("object_value"),
                        fact.get("confidence"),
                        fact.get("note"),
                        fact.get("as_of"),
                        fact.get("provenance", {}).get("source_file"),
                        fact.get("provenance", {}).get("source_section"),
                        json_dump(fact),
                    )
                    for fact in facts
                ],
            )

            conn.execute(
                """
                INSERT INTO compile_metadata (
                  schema_version, compiled_at_utc,
                  source_index_hash, source_graph_hash, source_facts_hash,
                  source_index_generated_at, source_graph_generated_at, source_facts_generated_at,
                  repo_count, node_count, edge_count, fact_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    SCHEMA_VERSION,
                    compiled_at_utc,
                    source_hashes["index"],
                    source_hashes["graph"],
                    source_hashes["facts"],
                    source_generated_at["index"],
                    source_generated_at["graph"],
                    source_generated_at["facts"],
                    len(repos),
                    len(nodes),
                    len(edges),
                    len(facts),
                ),
            )

        return table_counts(conn)
    finally:
        conn.close()


def run_row_count_gate(
    conn: sqlite3.Connection,
    expected: dict[str, int],
    log_doc: dict[str, Any],
) -> None:
    actual = {
        "repos": int(conn.execute("SELECT COUNT(*) FROM repos").fetchone()[0]),
        "nodes": int(conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]),
        "edges": int(conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0]),
        "facts": int(conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]),
    }
    gate = log_doc["gates"]["row_count_parity"]
    gate["expected"] = dict(expected)
    gate["actual"] = dict(actual)

    if actual != expected:
        gate["status"] = "fail"
        raise GateFailure(
            "row_count_parity",
            f"expected={expected} actual={actual}",
        )

    gate["status"] = "pass"


def run_orphan_edge_gate(conn: sqlite3.Connection, log_doc: dict[str, Any]) -> None:
    rows = conn.execute(
        """
        SELECT id, src_id, dst_id FROM edges
        WHERE src_id NOT IN (SELECT node_id FROM nodes)
           OR dst_id NOT IN (SELECT node_id FROM nodes)
        """
    ).fetchall()
    orphans = [
        {"id": int(row[0]), "src_id": row[1], "dst_id": row[2]}
        for row in rows
    ]

    gate = log_doc["gates"]["orphan_edge_detection"]
    gate["orphan_count"] = len(orphans)
    gate["orphans"] = orphans

    if orphans:
        gate["status"] = "fail"
        raise GateFailure(
            "orphan_edge_detection",
            f"orphan edges found: {orphans}",
        )

    gate["status"] = "pass"


def run_query_parity_gate(
    conn: sqlite3.Connection,
    repos: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    expected_repo_count: int,
    log_doc: dict[str, Any],
) -> None:
    checks: list[dict[str, Any]] = []

    count_row = conn.execute("SELECT COUNT(*) FROM repos").fetchone()
    count_value = count_row[0] if count_row else None
    checks.append(
        {
            "check": "repos_count",
            "status": "pass" if isinstance(count_value, int) and count_value == expected_repo_count else "fail",
            "expected": expected_repo_count,
            "actual": count_value,
        }
    )

    if repos:
        first_repo_node_id = repos[0].get("node_id")
        first_repo_name = repos[0].get("name")
        repo_row = conn.execute(
            "SELECT node_id, name FROM repos WHERE node_id = ?",
            (first_repo_node_id,),
        ).fetchone()
        repo_check_pass = bool(repo_row) and repo_row[1] == first_repo_name
        checks.append(
            {
                "check": "first_repo_lookup",
                "status": "pass" if repo_check_pass else "fail",
                "node_id": first_repo_node_id,
                "expected_name": first_repo_name,
                "actual_name": repo_row[1] if repo_row else None,
            }
        )
    else:
        checks.append(
            {
                "check": "first_repo_lookup",
                "status": "fail",
                "detail": "master_index.yaml repos list is empty",
            }
        )

    if edges:
        first_edge_src_id = edges[0].get("src_id")
        edge_count = conn.execute(
            "SELECT COUNT(*) FROM edges WHERE src_id = ?",
            (first_edge_src_id,),
        ).fetchone()[0]
        checks.append(
            {
                "check": "first_edge_src_lookup",
                "status": "pass" if edge_count > 0 else "fail",
                "src_id": first_edge_src_id,
                "rows": edge_count,
            }
        )
    else:
        checks.append(
            {
                "check": "first_edge_src_lookup",
                "status": "fail",
                "detail": "master_graph.yaml edges list is empty",
            }
        )

    if facts:
        first_fact_node_id = facts[0].get("node_id")
        fact_count = conn.execute(
            "SELECT COUNT(*) FROM facts WHERE node_id = ?",
            (first_fact_node_id,),
        ).fetchone()[0]
        checks.append(
            {
                "check": "first_fact_node_lookup",
                "status": "pass" if fact_count > 0 else "fail",
                "node_id": first_fact_node_id,
                "rows": fact_count,
            }
        )
    else:
        checks.append(
            {
                "check": "first_fact_node_lookup",
                "status": "fail",
                "detail": "master_deep_facts.yaml facts list is empty",
            }
        )

    gate = log_doc["gates"]["query_parity"]
    gate["checks"] = checks

    failed = [row for row in checks if row.get("status") != "pass"]
    if failed:
        gate["status"] = "fail"
        raise GateFailure(
            "query_parity",
            f"checks failed: {[row.get('check') for row in failed]}",
        )

    gate["status"] = "pass"


def row_hash(row: tuple[Any, ...]) -> str:
    text = json.dumps(list(row), ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compare_table_hashes(db_a: Path, db_b: Path, table: str, order_key: str) -> bool:
    conn_a = sqlite3.connect(db_a)
    conn_b = sqlite3.connect(db_b)
    try:
        rows_a = conn_a.execute(f"SELECT * FROM {table} ORDER BY {order_key}").fetchall()
        rows_b = conn_b.execute(f"SELECT * FROM {table} ORDER BY {order_key}").fetchall()
        hashes_a = sorted(row_hash(row) for row in rows_a)
        hashes_b = sorted(row_hash(row) for row in rows_b)
        return hashes_a == hashes_b
    finally:
        conn_a.close()
        conn_b.close()


def run_deterministic_rebuild_gate(
    workspace_root: Path,
    repos: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    facts: list[dict[str, Any]],
    source_hashes: dict[str, str],
    source_generated_at: dict[str, str],
    first_db: Path,
    log_doc: dict[str, Any],
) -> None:
    gate = log_doc["gates"]["deterministic_rebuild"]
    second_tmp = tempfile.NamedTemporaryFile(
        prefix="knowledge.db.rebuild.",
        suffix=".tmp",
        dir=workspace_root,
        delete=False,
    )
    second_tmp_path = Path(second_tmp.name)
    second_tmp.close()

    table_keys = {
        "repos": "node_id",
        "nodes": "node_id",
        "edges": "id",
        "facts": "fact_id",
    }

    try:
        populate_database(
            second_tmp_path,
            repos,
            nodes,
            edges,
            facts,
            source_hashes,
            source_generated_at,
            utc_now_iso(),
        )

        for table, key in table_keys.items():
            if not compare_table_hashes(first_db, second_tmp_path, table, key):
                gate["status"] = "fail"
                gate["detail"] = f"table differs: {table}"
                raise GateFailure("deterministic_rebuild", f"table differs: {table}")

        gate["status"] = "pass"
        gate["detail"] = "all compared tables match"
    finally:
        if second_tmp_path.exists():
            second_tmp_path.unlink()


def write_compile_log(log_path: Path, payload: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False, default_flow_style=False),
        encoding="utf-8",
    )


def print_failure(gate_name: str, detail: str) -> None:
    print("compile: FAILED")
    print(f"  gate: {gate_name}")
    print(f"  detail: {detail}")


def run_compile(workspace_root: Path, force: bool) -> int:
    started_at = datetime.now(timezone.utc)
    started_at_utc = started_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    log_doc = make_log_template(started_at_utc, force)

    output_path = workspace_root / OUTPUT_DB
    log_path = workspace_root / LOG_FILE
    tmp_handle = tempfile.NamedTemporaryFile(
        prefix="knowledge.db.",
        suffix=".tmp",
        dir=workspace_root,
        delete=False,
    )
    tmp_db_path = Path(tmp_handle.name)
    tmp_handle.close()

    failure: GateFailure | None = None
    current_gate = "snapshot_consistency"
    warning_snapshot_divergence = False

    try:
        index_path = workspace_root / INDEX_FILE
        graph_path = workspace_root / GRAPH_FILE
        facts_path = workspace_root / FACTS_FILE

        yaml_index = load_yaml(index_path)
        yaml_graph = load_yaml(graph_path)
        yaml_facts = load_yaml(facts_path)

        repos = ensure_list_of_dicts(yaml_index.get("repos"))
        nodes = ensure_list_of_dicts(yaml_graph.get("nodes"))
        edges = ensure_list_of_dicts(yaml_graph.get("edges"))
        facts = ensure_list_of_dicts(yaml_facts.get("facts"))

        source_hashes = {
            "index": sha256_file(index_path),
            "graph": sha256_file(graph_path),
            "facts": sha256_file(facts_path),
        }
        source_generated_at = {
            "index": str(yaml_index.get("generated_at_utc") or ""),
            "graph": str(yaml_graph.get("generated_at_utc") or ""),
            "facts": str(yaml_facts.get("generated_at_utc") or ""),
        }

        log_doc["source_files"]["index"].update(
            {
                "sha256": source_hashes["index"],
                "generated_at_utc": source_generated_at["index"],
                "repo_count": len(repos),
            }
        )
        log_doc["source_files"]["graph"].update(
            {
                "sha256": source_hashes["graph"],
                "generated_at_utc": source_generated_at["graph"],
                "node_count": len(nodes),
                "edge_count": len(edges),
            }
        )
        log_doc["source_files"]["facts"].update(
            {
                "sha256": source_hashes["facts"],
                "generated_at_utc": source_generated_at["facts"],
                "fact_count": len(facts),
            }
        )

        index_ts = parse_utc_timestamp(source_generated_at["index"])
        graph_ts = parse_utc_timestamp(source_generated_at["graph"])
        facts_ts = parse_utc_timestamp(source_generated_at["facts"])
        timestamps = [index_ts, graph_ts, facts_ts]

        max_delta_seconds = 0
        for left_idx in range(len(timestamps)):
            for right_idx in range(left_idx + 1, len(timestamps)):
                delta = abs((timestamps[left_idx] - timestamps[right_idx]).total_seconds())
                if delta > max_delta_seconds:
                    max_delta_seconds = int(delta)

        if max_delta_seconds > 300:
            detail = (
                f"index(ts={source_generated_at['index']},sha256={source_hashes['index']}), "
                f"graph(ts={source_generated_at['graph']},sha256={source_hashes['graph']}), "
                f"facts(ts={source_generated_at['facts']},sha256={source_hashes['facts']}), "
                f"max_delta_seconds={max_delta_seconds}"
            )
            warning_snapshot_divergence = True
            log_doc["gates"]["snapshot_consistency"]["status"] = "warn"
            log_doc["gates"]["snapshot_consistency"]["detail"] = (
                f"timestamp divergence (non-blocking): {detail}"
            )
        else:
            log_doc["gates"]["snapshot_consistency"]["status"] = "pass"
            log_doc["gates"]["snapshot_consistency"]["detail"] = (
                f"max_delta_seconds={max_delta_seconds}"
            )

        current_gate = "row_count_parity"
        compile_counts = populate_database(
            tmp_db_path,
            repos,
            nodes,
            edges,
            facts,
            source_hashes,
            source_generated_at,
            utc_now_iso(),
        )

        expected_counts = {
            "repos": len(repos),
            "nodes": len(nodes),
            "edges": len(edges),
            "facts": len(facts),
        }

        current_gate = "row_count_parity"
        conn = sqlite3.connect(tmp_db_path)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            run_row_count_gate(conn, expected_counts, log_doc)
            current_gate = "orphan_edge_detection"
            run_orphan_edge_gate(conn, log_doc)
            current_gate = "query_parity"
            run_query_parity_gate(conn, repos, edges, facts, len(repos), log_doc)
        finally:
            conn.close()

        current_gate = "deterministic_rebuild"
        run_deterministic_rebuild_gate(
            workspace_root,
            repos,
            nodes,
            edges,
            facts,
            source_hashes,
            source_generated_at,
            tmp_db_path,
            log_doc,
        )

        os.replace(tmp_db_path, output_path)
        log_doc["output"]["size_bytes"] = output_path.stat().st_size
        log_doc["output"]["table_counts"] = {
            "repos": compile_counts["repos"],
            "nodes": compile_counts["nodes"],
            "edges": compile_counts["edges"],
            "facts": compile_counts["facts"],
            "compile_metadata": compile_counts["compile_metadata"],
        }

        finished_at = datetime.now(timezone.utc)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        finished_at_utc = finished_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")

        log_doc["compile_run"].update(
            {
                "finished_at_utc": finished_at_utc,
                "duration_ms": duration_ms,
                "result": "ok",
            }
        )

        write_compile_log(log_path, log_doc)

        if warning_snapshot_divergence:
            print("WARNING: snapshot_consistency timestamp divergence detected (non-blocking).")
            print(f"  index: {source_generated_at['index']}")
            print(f"  graph: {source_generated_at['graph']}")
            print(f"  facts: {source_generated_at['facts']}")
            print(f"  max_delta_seconds: {max_delta_seconds}")

        print("compile: ok")
        print(f"  schema_version: {SCHEMA_VERSION}")
        print(f"  repos: {compile_counts['repos']}")
        print(f"  nodes: {compile_counts['nodes']}")
        print(f"  edges: {compile_counts['edges']}")
        print(f"  facts: {compile_counts['facts']}")
        print(f"  duration_ms: {duration_ms}")
        print(f"  output: {OUTPUT_DB}")
        return 0

    except GateFailure as exc:
        failure = exc
    except Exception as exc:
        failure = GateFailure(current_gate, str(exc))

    if tmp_db_path.exists():
        tmp_db_path.unlink()

    finished_at = datetime.now(timezone.utc)
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)
    finished_at_utc = finished_at.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    log_doc["compile_run"].update(
        {
            "finished_at_utc": finished_at_utc,
            "duration_ms": duration_ms,
            "result": "FAILED",
        }
    )
    write_compile_log(log_path, log_doc)

    assert failure is not None
    print_failure(failure.gate_name, failure.detail)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="WS7 read model materializer")
    parser.add_argument("--workspace-root", required=True, help="Workspace root path")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Compatibility flag; timestamp divergence is warning-only and no longer blocks compile.",
    )
    args = parser.parse_args()

    workspace_root = Path(args.workspace_root).resolve()
    return run_compile(workspace_root, args.force)


if __name__ == "__main__":
    raise SystemExit(main())
