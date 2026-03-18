# proposed-contract-redesign-cbap-takeaways

## Status

Working draft. This document is intended as context for the contract redesign, not as a final decision record or replacement contract.

## Why This Doc Exists

An older analysis pipeline project contains design patterns that may help the current deep narrative contract redesign. The goal here is to capture useful takeaways without prematurely locking in design decisions. This should give later agents and reviewers a grounded starting point for refinement.

## Source Inputs

- User-provided transcript describing the older pipeline's scaffold, prompt generation, coverage controls, split policy, strict gate, and output artifacts.
- `/Users/szilaa/scripts/projects/analyze_RLMs/docs/CANONICAL_TEST_RUN_SPEC.md`
- `/Users/szilaa/scripts/projects/analyze_RLMs/docs/TEST_RUN_HANDBOOK.md`
- `/Users/szilaa/scripts/projects/analyze_RLMs/reference_notes/LESSONS_LEARNED_TROUBLESHOOTING.md`
- `/Users/szilaa/scripts/projects/analyze_RLMs/scripts/generate_phase23_dispatch_prompt.py`
- `/Users/szilaa/scripts/projects/analyze_RLMs/scripts/generate_phase23_selection_log.py`
- `/Users/szilaa/scripts/projects/analyze_RLMs/scripts/enforce_canary_split_policy.py`
- `/Users/szilaa/scripts/projects/analyze_RLMs/implementation-plans/template-packs/phase2-3-canary/domain_findings.template.json`
- `/Users/szilaa/scripts/projects/analyze_RLMs/outputs/code-analysis/north-star-semantic-audit-helm/checkpoints/CALIBRATION_SINGLE_CALL_PROMPT_PROTOCOL_SAFE.md`

## High-Value Takeaways

### 1. The old pipeline did not rely on prompt text alone

The most important transferable lesson is architectural: the old system paired prompts with a frozen intent artifact, deterministic selection, token-aware dispatch policy, and a strict validation gate.

Useful implication for this project:

- The contract should probably not be treated as the only control surface.
- If we want better behavioral coverage, we may need a small supporting layer around the contract that freezes intent and validates outputs before compile.

Why this matters now:

- Our current deep narrative contract is acting as both interface spec and prioritization system.
- That makes it easy for agents to remain "compliant" while still producing inventory-heavy files.

### 2. Frozen intent prevented prompt drift

In the old pipeline, `run_scope.json` acted as the single source of truth for run intent, scope bounds, selected domains, and estimator family. The dispatch prompt was generated from that file rather than hand-maintained across runs.

Useful implication for this project:

- We may benefit from a small, repo-level extraction scope artifact that is generated or declared before deep writing begins.
- That artifact could specify repo archetype, required section families, optional section families, and scope limits.

Open design question:

- Should this redesign remain contract-only, or introduce a sidecar "deep extraction scope" artifact?

### 3. The old prompts taught the agent what a good unit of output looked like

The older prompt did not only say "analyze these domains." It told the agent how to write a finding:

- name the mechanism or pattern, not just the symptom
- prefer direct evidence
- keep output inside a strict schema
- cap output and prioritize high-confidence findings

Useful implication for this project:

- Our redesign likely needs stronger guidance on what a good behavioral section entry looks like.
- Right now, the contract defines section names and rough shapes, but it does not strongly teach the writer how to produce high-utility `supports_task`, `has_failure_mode`, or `uses_protocol` facts.

Possible analogs for deep narratives:

- `troubleshooting`: name a concrete failure mode, not a vague pain point
- `commands` / `common_tasks`: name the supported task and operational purpose, not just the command string
- `supported_protocols`: name the protocol and the repo's role or usage context, not a loose mention

This is a prompt-design takeaway more than a schema-only takeaway.

### 4. Coverage was engineered, not left to agent judgment

The old pipeline used deterministic stride sampling to avoid first-files bias and a split policy to prevent oversized calls from collapsing into shallow output.

Useful implication for this project:

- If we keep a single monolithic "write the deep file" step, structural sections will keep dominating because they are the easiest broad summary to produce.
- A redesign may need one of:
  - preselected evidence sources for behavioral sections
  - focused generation passes by section family
  - explicit per-archetype coverage requirements

Practical translation for this repo:

- For behavioral coverage, likely prioritize README sections, docs, CLI help text, operational scripts, tests, troubleshooting docs, integration docs, protocol docs, and config docs before defaulting to code structure.

### 5. Strict gates matter as much as prompt quality

The older system used a strict gate to enforce schema, grounding, integrity, and scope after generation.

Useful implication for this project:

- A redesigned contract is stronger if it has a corresponding validator mindset.
- We should consider validating not just YAML shape, but behavioral coverage expectations where the repo type makes them clearly relevant.

Potential gate ideas:

- required sections present for the repo archetype
- no unmapped sections
- section shapes valid
- evidence present for behavioral entries
- minimum behavioral density or minimum section presence for targeted categories

Open design question:

- Do we want hard failure on missing behavioral sections, soft warnings, or category-specific audit reports first?

### 6. Output artifacts were structured for resume, audit, and downstream use

The old project kept a clean artifact tree with checkpoints, findings, metrics, and reports. That made resume and backfill work much easier.

Useful implication for this project:

- If contract redesign leads to a backfill of thin deep files, structured checkpoints and reports will make that manageable.
- This is especially relevant if we end up parallelizing re-extraction or running focused repair passes for low-coverage repos.

This is more pipeline-adjacent than contract-adjacent, but still relevant to redesign rollout.

### 7. Trace the pipeline before blaming the writer

The troubleshooting note from the older project is one of the most important cautionary lessons:

> When output looks wrong, inspect the full transformation path before blaming the model.

In the old incident, the model was not disobeying the prompt. A normalization layer was applying stale vocabulary mapping.

Useful implication for this project:

- If the corpus continues to look lopsided after redesign, we should inspect:
  - the contract wording
  - any deep-writing prompt layer
  - WS6 extractor behavior
  - downstream compilation or normalization assumptions
- We should avoid treating "the agent didn't follow the contract" as the default diagnosis.

This matters because our current contract redesign is tightly coupled to WS6's extractor map and fixed predicates.

### 8. The docs made validation criteria explicit, not implied

The old docs were useful not because they introduced a new architecture, but because they made the lifecycle and validity criteria very explicit.

Useful implication for this project:

- If we add any supporting process around the contract redesign, we should be clear about what counts as a valid deep-generation run versus an exploratory draft.
- The old run spec treated some artifacts as mandatory and attached explicit `required_audits` and `confidence_gates` to run scope.

Potential translation for this project:

- a lightweight extraction-scope artifact could declare not just repo archetype and required section families, but also required validation checks
- we could define confidence gates such as "required behavioral sections present for this archetype" or "no behavioral entry without evidence anchor"

This is mostly a process-design takeaway, but it is a useful complement to the contract redesign because it turns quality expectations into something testable.

### 9. Different content types may deserve different strictness levels

The second-brain research notes introduced a useful distinction: some content types were treated as strict-structure ingestion targets, while others were intentionally more flexible.

Useful implication for this project:

- We do not necessarily need the same level of structure everywhere in the deep narrative contract.
- A stronger redesign may selectively tighten the sections that produce the highest-value behavioral facts while leaving lower-value narrative inventory sections more permissive.

Potential translation for this project:

- structural sections such as `architecture` or `key_features` can likely remain relatively flexible
- behavioral sections such as `troubleshooting`, `commands`, `common_tasks`, and `supported_protocols` may deserve stricter entry expectations and stronger validation

This is useful because it offers a middle path between two bad extremes:

- keeping the whole contract loose and hoping quality improves
- over-constraining every section and making the writing process brittle

It also pairs well with a post-generation audit layer: validation can focus more heavily on the sections that matter most for query utility.

## What Seems Most Transferable To The Current Redesign

### A. Treat the redesign as a system, not just a rewritten markdown file

The old pipeline suggests that quality came from alignment across:

- frozen intent
- generated prompt
- deterministic selection
- strict validation
- downstream normalization

For us, the comparable system would be:

- contract
- deep-writing instructions
- evidence/source selection strategy
- WS6 extraction
- post-generation validation or audits

This may be the single biggest takeaway.

### B. Shift from "recognized sections" to "required evidence families"

The old system framed work around scoped domains and required finding fields. That pushed the model toward meaningful units of analysis.

For our redesign, one promising framing is:

- structural evidence family
- operational tasks evidence family
- failure modes evidence family
- protocol/integration evidence family

That framing is probably more useful than only rearranging current tiers.

### C. Introduce repo-archetype-aware expectations

The estimator family idea from the older pipeline is useful even though the exact implementation is different.

For us, the analog is not token estimation first. It is repo-type-aware coverage:

- serving and database repos should likely require failure-oriented sections
- CLI and orchestration repos should likely require task-oriented sections
- network and tunneling repos should likely require protocol-oriented sections

This would directly address the current problem where some categories remain compliant but behaviorally thin.

### D. Make behavioral entries explicit and evidence-first

The old prompts required direct evidence and named patterns. We should likely push our behavioral sections in the same direction.

Examples:

- prefer "KV cache memory exhausted" over "memory issues"
- prefer "gitnexus impact <target>" over "impact analysis tooling"
- prefer "WireGuard" with context over a broad networking label

This is a content-shaping lesson that could materially improve predicate quality without immediate schema expansion.

## What Should Stay Open

### 1. Whether to add a sidecar scope artifact

This seems promising, but it is also a meaningful workflow change. It should remain open until we decide whether contract-only redesign is sufficient.

### 2. Whether to split generation into multiple focused passes

The old pipeline's split policy is attractive because it protects depth, but it adds orchestration complexity. We should keep this open rather than assuming it is required.

### 3. Whether to add controlled vocabularies for behavioral sections

The older pipeline benefited from controlled fields like `pattern_name`, but too much normalization too early could flatten nuance in deep narratives.

Possible middle ground:

- define stronger examples and entry expectations first
- only add controlled vocab if quality still drifts

### 4. Whether the redesign should remain within the current 8-predicate WS6 boundary

Some old-pipeline lessons point toward richer structured output. But in this project, new structure is only useful if WS6 and downstream consumers can honor it.

That means the redesign likely needs to distinguish:

- what can improve immediately within current WS6 limits
- what would require later extractor or schema changes

## What Not To Copy Blindly

### 1. Do not import audit-specific fields that do not map to our use case

Fields like `anti_pattern`, `related_findings`, and blocker semantics were meaningful in the older findings pipeline, but they do not map cleanly to deep narrative extraction as-is.

### 2. Do not overfit on hard caps

The old pipeline capped finding counts. A similar cap for deep narratives could accidentally suppress useful behavioral coverage if applied too early or globally.

### 3. Do not create multiple conflicting sources of truth

The troubleshooting note is a warning here. If we add archetype rules, prompts, examples, validator rules, and WS6 assumptions, they must stay aligned.

Otherwise we risk reproducing the older problem in a new form.

## Candidate Proposal Directions

These are intentionally framed as options, not decisions.

### Option 1. Contract-first redesign only

Keep the redesign limited to:

- new tier framing
- stronger section guidance
- better examples for behavioral sections

Pros:

- smallest scope
- easiest to adopt quickly

Cons:

- may not be enough to change coverage in practice

### Option 2. Contract plus validation guidance

Redesign the contract and define a lightweight post-generation audit process for:

- section presence
- evidence grounding
- behavioral section expectations by repo archetype

Pros:

- better chance of actual behavior change
- still avoids major orchestration changes

Cons:

- adds enforcement work outside the contract itself

### Option 3. Contract plus scope artifact plus focused generation

Adopt the strongest lesson from the old pipeline:

- declare intent first
- generate focused prompts from that intent
- validate afterward

Pros:

- best chance of materially improving behavioral coverage

Cons:

- highest implementation cost
- easiest place to overdesign too early

## Working Recommendations For Follow-On Agents

- Treat the old pipeline's biggest lesson as systemic alignment, not prompt cleverness.
- When proposing contract changes, separate immediate WS6-compatible improvements from ideas that require later extractor work.
- Keep asking whether a change improves actual behavioral evidence coverage, not just section completeness.
- If output still looks weak after redesign, inspect the whole write -> extract -> compile path before blaming the narrative writer.

## Suggested Next Questions

- Which parts of the redesign can improve behavioral predicates without any WS6 changes?
- Which repo categories should get archetype-specific required sections first?
- Would a lightweight validator give enough leverage before we invest in focused multi-pass generation?
- What is the smallest "frozen intent" artifact that would materially reduce prompt drift and coverage ambiguity?
