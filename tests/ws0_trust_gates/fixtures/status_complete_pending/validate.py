"""Fixture validator.
VALIDATOR_SCOPE: index.yaml, graph.yaml, repos/*.yaml
"""

from pathlib import Path

INDEX_FILE = Path("index.yaml")
GRAPH_FILE = Path("graph.yaml")
REPOS_DIR = Path("repos")

for _repo_file in REPOS_DIR.glob("*.yaml"):
    pass
