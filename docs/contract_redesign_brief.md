# Deep Narrative Contract Redesign — Session Brief

**For:** Fresh agent session  
**Prepared by:** Supervisor (Claude), based on grounding session findings  
**Repo:** `https://github.com/mrdysmas/github-repos-knowledge-factory`  
**Branch:** `main` at `b2debf5`  
**Date:** 2026-03-18

---

## What this session is for

The `deep_narrative_contract.md` (currently v1.2) needs to be redesigned before any further extraction or skill work. This session is **exploratory and diagnostic**, not prescriptive. You are not expected to produce a new contract draft. You are expected to build a clear, evidence-based picture of what the contract gets wrong and what a better one should accomplish.

The redesign is a breaking change. It affects how every future deep narrative is written and what facts the corpus produces. That decision deserves careful grounding before anyone writes a line.

---

## Background: why this is happening

The corpus has 5,538 facts across 122 repos. The predicate distribution is heavily lopsided:

| predicate | count | % of total |
|---|---|---|
| `has_component` | 2,354 | 42.5% |
| `has_config_option` | 1,055 | 19.1% |
| `implements_pattern` | 773 | 14.0% |
| `has_extension_point` | 676 | 12.2% |
| `supports_task` | 464 | 8.4% |
| `exposes_api_endpoint` | 91 | 1.6% |
| `has_failure_mode` | 78 | 1.4% |
| `uses_protocol` | 47 | 0.8% |

The top 4 predicates account for ~88% of all facts. The bottom 3 — `exposes_api_endpoint`, `has_failure_mode`, `uses_protocol` — together account for under 4%.

This is not random noise or LLM behavior. It is a direct consequence of how the contract ranks sections.

---

## The root cause: tier ranking encodes the wrong priority

The current contract organizes recognized sections into three tiers. Here is the relevant excerpt from `contracts/deep_narrative_contract.md`:

> **Tier 1 — high fact yield, use whenever the repo has the relevant content:**  
> `architecture`, `code_patterns`, `implementation_patterns`, `configuration`, `cli_arguments`, `api_surface`, `key_features`, `key_files`, `core_modules`

> **Tier 2 — moderate fact yield:**  
> `environment`, `tech_stack`, `testing`, `extension_points`, `integrations`, `commands`, `common_tasks`, `procedures`, `quick_reference`, `sdk_usage`

> **Tier 3 — lower fact yield, use when applicable:**  
> `cross_references`, `key_sections`, `content_coverage`, `supported_protocols`, `troubleshooting`, `ports`, `related_repos`, ...

The tier labels tell an agent what to prioritize. An agent doing a good job on this contract will load Tier 1 sections and treat Tier 3 as optional. The resulting fact distribution is exactly what you'd expect: `has_component` and `has_config_option` dominate because Tier 1 sections are almost entirely structural inventory.

Now look at where the behaviorally rich sections land:

- `commands` / `common_tasks` → `supports_task` → **Tier 2**
- `troubleshooting` → `has_failure_mode` → **Tier 3**
- `supported_protocols` → `uses_protocol` → **Tier 3**

The tier system ranks sections by **extraction ease** — how reliably an agent can pull them from source code. This was the right frame when the pipeline was being built and reliability was the primary concern. It is the wrong frame now. The corpus is stable. Reliability is no longer the bottleneck. **Query utility** is.

For the north star use cases (see below), `supports_task` and `has_failure_mode` are *more* valuable than `has_component`. A debugging agent does not care what the modules are named. It cares what can go wrong and what the repo is capable of doing.

---

## Historical context: how the contract got here

The original deep narratives were produced by a GLM model using a haphazardly built early skill — before the pipeline existed in its current form. Much of the pipeline was built ad-hoc to clean up those outputs. The contract evolved from that cleanup work.

The early agent produced component inventories not because it naturally thinks that way but because the section names it was given — `architecture`, `core_modules`, `key_files` — invited structural enumeration. The contract formalized that pattern into a tier hierarchy, and every subsequent agent has followed it.

This means the predicate distribution in the corpus reflects the precedent set by the original GLM agent under poor prompting conditions, now codified in a contract that perpetuates that pattern. The contract is not describing best practice; it is describing what was easiest to extract reliably in the early pipeline stages.

---

## North star use cases (keep these in mind throughout)

These are the queries the knowledge base should eventually serve well. You are not solving for them today — use them as a compass when evaluating whether a section or predicate is valuable.

1. **A planning or debugging agent asks:** "what does the fact database have that might inform this architectural decision or bug fix?"  
   *Needs: `has_failure_mode`, `supports_task`, `implements_pattern`, `uses_protocol`. Structural inventory (has_component) is low-value here.*

2. **A development agent asks:** "how does this project compare to similar repos in the corpus, and where can we avoid reinventing the wheel?"  
   *Needs: cross-repo pattern matching on `implements_pattern`, `supports_task`, `uses_protocol`. Comparison requires these predicates to exist at comparable density across repos.*

---

## What to explore in this session

This is a reading and analysis session. Use the live corpus and the repo's own files as primary sources.

### 1. Read the current contract in full

```bash
cat contracts/deep_narrative_contract.md
```

Pay particular attention to:
- The tier definitions and what each tier claims about yield
- The section shapes — especially `troubleshooting`, `commands`/`common_tasks`, `supported_protocols`
- The quality guidelines section at the bottom
- What the contract says about agent sourcing and grounding

### 2. Compile the read model and orient yourself

```bash
python3 tools/ws7_read_model_compiler.py --workspace-root .
python3 tools/query_master.py --workspace-root . stats
python3 tools/query_master.py --workspace-root . aggregate --group-by predicate
python3 tools/query_master.py --workspace-root . aggregate --group-by category --top 10
```

### 3. Study contrast cases in the corpus

The goal is to understand what distinguishes files that produce behaviorally rich facts from files that only produce inventory facts. Look at a range of examples.

**Files that are behaviorally rich** (notable for `supports_task` or `has_failure_mode`):

```bash
python3 tools/query_master.py --workspace-root . facts --id vllm-project/vllm --predicate has_failure_mode
python3 tools/query_master.py --workspace-root . facts --id openai/codex --predicate supports_task
python3 tools/query_master.py --workspace-root . facts --id ansible/ansible --predicate supports_task
```

Then read the corresponding deep files directly:

- `repos/knowledge/deep/vllm.yaml` — has 5 `has_failure_mode` facts; notice the `troubleshooting:` section structure
- `repos/knowledge/deep/openai__codex.yaml` — has 10 `supports_task` facts; notice `commands:` section
- `repos/knowledge/deep/bore.yaml` — the reference small file; unusually balanced predicate mix

**Files that are inventory-heavy** (the typical pattern):

- `repos/knowledge/deep/ladybugdb__ladybug.yaml` — sections are `architecture`, `core_modules`, `api_surface`, `configuration`, `implementation_patterns`, `key_features`, `key_files`; zero `supports_task`, zero `has_failure_mode`
- `repos/knowledge/deep/abhigyanpatwari__gitnexus.yaml` — similar structure; has `commands:` but no `troubleshooting:`

For each file, note which top-level sections are present and absent. The pattern will be clear.

### 4. Cross-repo pattern queries to understand sparse predicates

Get a feel for the actual signal in the low-count predicates:

```bash
# What do uses_protocol facts actually look like?
python3 tools/query_master.py --workspace-root . pattern --predicate uses_protocol --limit 50

# Which repos have has_failure_mode and for what symptoms?
python3 tools/query_master.py --workspace-root . pattern --predicate has_failure_mode --limit 50

# What kinds of tasks does supports_task capture?
python3 tools/query_master.py --workspace-root . pattern --predicate supports_task --limit 50
```

Then ask: are these facts *useful*? Would a planning agent reach for them? What would more of them look like across the corpus?

### 5. Look at what's absent from analytically interesting repos

GitNexus and LadybugDB are good test cases because we know their real-world relationship (GitNexus depends on LadybugDB). Check what facts they have and what's missing:

```bash
python3 tools/query_master.py --workspace-root . facts --id abhigyanpatwari/gitnexus
python3 tools/query_master.py --workspace-root . facts --id ladybugdb/ladybug
python3 tools/query_master.py --workspace-root . neighbors --id abhigyanpatwari/gitnexus
```

LadybugDB has zero `supports_task` and zero `has_failure_mode` despite being a database engine with known operational failure modes (WAL checkpoint pressure, buffer pool sizing, read-only path enforcement, single-writer gate). Those would be highly useful facts. They're absent because the agent writing it correctly followed a contract that ranked `troubleshooting` as Tier 3.

### 6. Read the WS6 extractor map

The section names in the contract are only valuable if WS6 knows how to extract from them. Verify alignment:

```bash
grep -n "extractor_map\|def extract_" tools/ws6_deep_integrator.py | head -40
```

This tells you the full set of sections WS6 actually handles, which may differ slightly from what the contract documents. Any redesign has to respect this boundary — adding new section names to the contract without a corresponding WS6 extractor produces unmapped sections and zero facts.

### 7. Graph edge sparsity — understand the scope

```bash
python3 tools/query_master.py --workspace-root . aggregate --group-by relation
python3 tools/query_master.py --workspace-root . graph --id ladybugdb/ladybug --hops 2
python3 tools/query_master.py --workspace-root . graph --id abhigyanpatwari/gitnexus --hops 2
```

Graph edges are hand-authored at ingestion time. GitNexus and LadybugDB have zero edges despite a real dependency that is legible in the facts. Note this gap — it is relevant context for skill design later, but it is a separate problem from the contract redesign. The contract redesign is about predicate density; edge authoring is about ingestion workflow.

---

## What you should be able to answer by end of session

1. **What does the contract actually incentivize?** Can you trace a specific section name through the contract's tier ranking → an agent's section selection → a WS6 extractor → a predicate in the DB?

2. **Which sections produce which predicates?** Build the mapping explicitly. There are 8 predicates and ~30 recognized sections. Many sections map to the same predicate.

3. **Where is the predicate gap most harmful?** Which categories in the corpus (vector databases, agent frameworks, inference serving) have the worst `supports_task`/`has_failure_mode` coverage relative to how useful that coverage would be?

4. **What would `has_failure_mode`-rich files look like at scale?** Is the `troubleshooting:` section shape adequate for producing useful failure mode facts, or does the shape itself need rethinking?

5. **What's the right framing for a redesigned tier system?** The current frame is extraction ease. The proposed frame is query utility. Are there other frames worth considering — e.g., grounding reliability (some claims are harder to verify than others)?

---

## Key files to read

| File | Why |
|---|---|
| `contracts/deep_narrative_contract.md` | The document under redesign — read it in full |
| `repos/knowledge/deep/vllm.yaml` | Best example of `has_failure_mode` facts in corpus |
| `repos/knowledge/deep/openai__codex.yaml` | Good `supports_task` coverage via `commands:` section |
| `repos/knowledge/deep/bore.yaml` | Reference small file; balanced predicate mix |
| `repos/knowledge/deep/ladybugdb__ladybug.yaml` | Typical inventory-heavy file; zero behavioral predicates |
| `repos/knowledge/deep/abhigyanpatwari__gitnexus.yaml` | Same pattern; also missing the LadybugDB edge |
| `tools/ws6_deep_integrator.py` | Find `extractor_map` to understand what WS6 actually handles |
| `docs/query_master_reference.machine.yaml` | See `workflow_recipes` and predicate context |

---

## Constraints any redesign must respect

- The 8 predicate names are fixed — they live in WS6's extractor logic. Changing predicate names requires a WS6 code change, a schema version bump, and a full re-extraction pass. That is a large scope change and should be treated as a separate decision.
- New section names require a corresponding WS6 extractor function before they produce facts. Don't add sections to the contract that WS6 can't handle.
- The contract is an interface spec, not a style guide. It governs agent output consumed by a deterministic pipeline. Changes must be precise.
- Backfill implications matter. Any redesign will need to be followed by a re-extraction pass over repos with thin behavioral coverage. That pass is token-heavy and parallelizable — a good Codex candidate. Keep that in mind when scoping changes.

---

## What success looks like for this session

A clear written analysis — not a contract draft — covering:

- The section-to-predicate mapping (which sections produce which predicates)
- A ranked assessment of which predicates are most valuable for the north star use cases
- A diagnosis of which current Tier 1 sections could be demoted without meaningful quality loss
- A diagnosis of which current Tier 2/3 sections should be elevated
- Any gaps between what WS6 can extract and what the north star use cases would need
- Open questions that require supervisor input before the redesign can proceed

Bring that analysis back and the supervisor will use it to make the contract decisions.
