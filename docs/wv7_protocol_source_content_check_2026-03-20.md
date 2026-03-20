# WS6 uses_protocol Source-Content Check — vector_database

Date: 2026-03-20
Issue: `github_repos-wv7`

## Question

Does source content for the affected categories contain extractable protocol vocabulary?
If yes, the uses_protocol gap is a real WS6 extraction failure and backfill is warranted.

## Method

Grep README.md and docs/ in all cloned repos for the affected categories.
Clones available in `workspace/clones/` for category `vector_database`:
- `lancedb__lancedb`
- `qdrant__qdrant`
- `weaviate__weaviate`

(No clones available for agent_cli, agent_framework, or structured_outputs repos —
vector_database was the viable sample given current clone coverage.)

## Findings

### qdrant (README.md)

```
### REST
### gRPC
For faster production-tier searches, Qdrant also provides a gRPC interface.
```

### weaviate (README.md)

```
Weaviate exposes REST API, gRPC API, and GraphQL API to communicate with the
database server.
```

### lancedb (README.md + CONTRIBUTING.md)

```
Seamless Integration: Python, Node.js, Rust, and REST APIs for easy integration.
REST API | https://docs.lancedb.com/api-reference/rest
protoc (Protocol Buffers compiler)
```

## Verdict

**Extraction failure, not content sparsity.**

All three cloned vector_database repos name REST, gRPC, and/or protobuf explicitly
in their top-level README or docs. These are the files WS6 reads during extraction.
The protocol vocabulary is present and prominent; WS6 did not capture it as
`uses_protocol` facts.

Comparison with tunneling: tunneling has 60 uses_protocol facts across 9/9 repos,
confirming WS6 is capable of protocol extraction. The gap is category-selective and
represents an extraction failure, not a global WS6 weakness.

## Recommendation

WS6 backfill for `uses_protocol` is warranted for `vector_database`. Extend the
same targeted check to `agent_cli` and `agent_framework` clones if/when they become
available, but the vector_database result is sufficient to proceed with backfill
planning for that category.

The suspected root cause: WS6 may require a protocol-extraction pass that was not
run (or was configured to skip) for non-tunneling categories. Inspect the WS6 deep
integrator prompt or config for any category-scoped exclusion before writing backfill
YAML by hand.
