  Now the step-back view.

  What problems are ahead

  1. Trust problem (highest priority)
     READY/COMPLETE can be reported while artifacts are parse-invalid or semantically contradictory.
     Meaning: current signals are not safe to automate against.
  2. Spec vs implementation drift
     Skill docs claim broad validation scope, but validator behavior is narrower.
     Meaning: you can “pass the process” while missing real failures.
  3. Identity drift
     Repo records are not yet anchored to one canonical remote-first identity model.
     Meaning: scaling to starred/followed repos without local clones will be brittle.
  4. Graph contract drift
     Different edge schemas and relation vocabularies across shards.
     Meaning: merge logic becomes one-off glue unless normalized first.
  5. Deep-schema heterogeneity
     LLM deep is now complete, but uses multiple schema shapes and mixed identifiers.
     Meaning: difficult to query, validate, and compile consistently.
  6. Open-world vs closed-world mismatch
     One shard expects all nodes local; another includes external ecosystem targets.
     Meaning: master graph semantics are undefined unless node kinds are explicit.

  What we’ll do to work them out (execution order)

  1. WS0 Trust Gates first
     Implement strict parse + status-semantic gates and block false-green states.
     Deliverable: knowledge/trust-gates-report.yaml per run.
  2. Contract freeze (WS1)
     Lock canonical schemas: repo identity, node kinds, edge schema, relation ontology mapping.
  3. Normalization (WS2 + WS3)
     Backfill canonical identity fields and normalize edge/relation formats from both shards.
  4. Unified validation + compiler (WS4)
     Single deterministic compile path to master artifacts with shared validation rules.
  5. Remote-first ingestion (WS5)
     Add refresh workflow for repos without local clones, including provenance/freshness fields.

  How this de-risks the project

  - Prevents bad state propagation early (WS0).
  - Keeps merge implementation small and deterministic (contract before code).
  - Makes future repo groups additive instead of cleanup-heavy.