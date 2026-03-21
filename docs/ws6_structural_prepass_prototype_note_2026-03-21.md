# WS6 Structural Pre-Pass Prototype Note

Date: 2026-03-21
Issue: `github_repos-9yt`

## Prototype Outcome

The narrow prototype now exists as an executable repo-local tool:

- `tools/ws6_structural_prepass.py`

It reads a WS6 clone manifest, inspects a checked-out repo with cheap deterministic
signals only, writes non-canonical artifacts under:

- `reports/ws6_structural_prepass/<batch_id>/<file_stem>.yaml`

and emits a batch summary with explicit contract and boundary checks:

- `reports/ws6_structural_prepass/<batch_id>/summary.yaml`

Representative live sample produced in this prototype pass:

- `reports/ws6_structural_prepass/B11_gitnexus_ladybugdb_deepagents/langchain-ai__deepagents.yaml`

## Verification

Verification completed in two layers:

1. Regression tests:
   - `python3 -m unittest discover -s tests/ws6_structural_prepass -p 'test_*.py'`
2. Live batch-scoped sample:
   - refreshed clones with `tools/ws6_clone_prep.py` for `B11_gitnexus_ladybugdb_deepagents`
   - generated a real pre-pass artifact for `langchain-ai/deepagents`
   - confirmed the summary reports:
     - required sections present
     - evidence attached to non-trivial claims
     - no behavioral or cross-repo sections emitted
     - output stays under `reports/` and does not write canonical WS6/WS7 artifacts

## Deferred

The following are still intentionally deferred:

- richer AST-assisted grouping or symbol extraction
- retrieval-helper integration
- automatic WS6 consumption or canonical fact materialization
- `run_batch` / default workflow integration
- calibration on a small new batch for usefulness comparison (`github_repos-tl0`)

This keeps the prototype aligned with the contract: orientation scaffold first,
not a second knowledge system.
