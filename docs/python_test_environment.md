# Python Test Environment

This repo's supported Python test environment is a local virtual environment at `.venv/`.

Host prerequisite on Ubuntu 24.04 / Python 3.12: install `python3.12-venv` once so `python3 -m venv` works.

Use this path when a task needs `pytest` or other repo-local Python tooling:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` currently carries the shared baseline needed for pytest-based verification in this repo: `pytest` plus `PyYAML`.

Run tests through the virtual environment so agents do not depend on machine-global packages:

```bash
python -m pytest tests/ws1_contract -q
```

If a task only needs the standard library, `python3 -m unittest ...` remains fine. Use `pytest` when the task explicitly calls for it or when the repo's verification flow expects it.
