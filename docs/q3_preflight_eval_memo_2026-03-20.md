## Q3 Preflight Evaluation Memo

Issue: `github_repos-er4`

Scope: first post-implementation usefulness pass for `query_master.py preflight` on realistic coding-session prompts.

### Prompt set and outcome

| Category | Prompt-shaped term | Result | Classification | Notes |
|---|---|---|---|---|
| `vector_database` | `batch` | 5 hits including write-load/indexing failures | actionable | Changes planning toward ingestion/index-build caution. |
| `vector_database` | `grpc` | 2 hits including port/bind failures | actionable | Good pre-startup warning for service/API work. |
| `inference_serving` | `gpu` | 5 hits including OOM, NCCL, runtime library issues | actionable | Strong caution posture for serving changes. |
| `rag_frameworks` | `indexing` | 3 indexing-specific failures | actionable | Useful for review focus on document pipelines. |
| `agent_framework` | `memory` | 0 hits, `scope_repo_count: 0` | no useful signal | Corpus coverage gap, not a query bug. |
| `inference_serving` | `multi gpu` | 0 hits before fix; 2 hits after fix | weak improvement -> fixed by term matching refinement | Hyphen/spacing mismatch blocked relevant evidence. |
| `vector_database` | `read only` | 0 hits before fix; relevant hit after fix | weak improvement -> fixed by term matching refinement | Hyphen/spacing mismatch blocked relevant evidence. |
| `vector_database` | `batch upserts` | 0 hits | weak improvement | Remaining gap is synonym/phrase mismatch, not punctuation. |

### Recommendation

Choose `query hardening / term-matching refinement`.

Why:

- The surface is already useful when prompts use direct corpus wording.
- The clearest failures were retrieval misses caused by punctuation and whitespace variation, which we fixed without changing ranking or ontology.
- The remaining empty case (`batch upserts`) points to synonym coverage limits, but that is a second-step refinement, not evidence that output formatting or ranking is the main blocker.
- Corpus maintenance still matters for categories like `agent_framework`, but the first follow-up with the best leverage was query hardening because it immediately improved existing covered categories.

### Implemented follow-up

- Normalized preflight term matching so prompt text like `multi gpu` matches corpus text like `multi-GPU`.
- Normalized preflight term matching so `read only` matches `read-only`.
- Added regression tests for both cases.

### Residual limits

- No synonym inference yet: `batch upserts` still will not match `batch insertions` or `batch writes`.
- Categories with `scope_repo_count: 0` still require corpus work under `github_repos-7yf`; query changes alone cannot fix absent evidence.
