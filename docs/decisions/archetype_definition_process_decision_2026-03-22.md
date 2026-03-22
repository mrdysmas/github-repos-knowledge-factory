# Archetype Definition Process for New Repo Shapes (`github_repos-aj0`)

Date: 2026-03-22

## Decision

**Define archetypes before writing deep files for new repo shapes.**

The established backfill workflow (audit → identify thin coverage → backfill to meet requirements → re-audit) assumes the repo is already ingested. For repos with no deep files, the sequence is reversed: archetype design must come first so the deep file author knows what predicate families to target.

## Context

The calibration batch (4em) includes repos with shapes not covered by existing archetypes:
`helm_chart_repo`, `sdk_library` (covering `sdk_client`/`sdk_monorepo`), `k8s_operator`,
and `plugin_ecosystem`. These repos have pre-pass manifests but no WS6 deep files.

An agent applying the standard backfill workflow would attempt to write deep files
to cover the archetype requirements — but if no archetype exists yet, there are no
requirements to target, and the resulting facts will be shaped by guesswork rather
than deliberate design.

## Archetype Design Process

For any new shape with no existing archetype:

1. **Identify the shape's primary knowledge value.** Ask: what does an agent actually need from this repo? The answer drives which families to require.

2. **Map to families using these rules:**
   - `structure` — always required (components and config options are the floor for any repo)
   - `tasks` — require if the repo is consumed operationally (users run commands, call APIs, deploy it); skip or recommend if it's purely declarative or reference
   - `protocols` — require if the repo's integration surface is its defining value (what it connects to, what APIs it exposes or consumes); recommend otherwise
   - `failures` — require unless the repo is purely static or reference material

3. **Set `predicate_checks` to distinguish meaningful protocols from incidental ones:**
   - Use `uses_protocol` for integration-heavy shapes where backend protocol facts are the primary value (SDKs, operators, providers)
   - Use `has_extension_point` for customization-first shapes where the extension interface is the primary contract (Helm charts, plugin frameworks)
   - Omit predicate_checks when any protocols fact satisfies the archetype

4. **Check for category collisions before assigning.** Multiple repos sharing a broad provisional category (e.g. `infra_ops`) must be promoted with specific categories that match their archetype. The pre-pass manifest category is provisional — the deep file sets the authoritative category.

## Archetypes Defined (2026-03-22, commit `eb70a7c`)

| Archetype | Required families | Recommended | Protocol predicate |
|---|---|---|---|
| `helm_chart_repo` | structure, failures, protocols | tasks | `has_extension_point` |
| `sdk_library` | structure, tasks, failures, protocols | — | `uses_protocol` |
| `k8s_operator` | structure, tasks, failures, protocols | — | `uses_protocol` |
| `plugin_ecosystem` | structure, failures, protocols | tasks | `uses_protocol` |

**Rationale per shape:**

- **`helm_chart_repo`**: Purely declarative — no process entrypoints. The values.yaml customization interface is the defining API contract (`has_extension_point` required). Deployment procedures (tasks) are useful but secondary.
- **`sdk_library`**: SDKs wrap backend APIs — all 4 families are essential. Covers `sdk_client` and `sdk_monorepo` category values. `uses_protocol` required because backend protocol facts are more meaningful than extension hooks for an SDK.
- **`k8s_operator`**: Bridges k8s and external backends (Vault, AWS SM, GCP). All 4 families required — the backend integrations are the operator's core value. `uses_protocol` distinguishes from repos that only expose extension hooks.
- **`plugin_ecosystem`**: Flat connector surface (e.g. 263 per-AWS-service subdirs in terraform-provider-aws). Tasks are secondary — consumers write HCL config, not CLI commands. `uses_protocol` captures the backend API (e.g. AWS Signature v4).

## Category Collision Warning

Both `grafana/helm-charts` and `external-secrets/external-secrets` have
`category: infra_ops` in their pre-pass manifests. These must be promoted with
specific categories in their deep files:

- `grafana/helm-charts` → `category: helm_chart_repo`
- `external-secrets/external-secrets` → `category: k8s_operator`
- `hashicorp/terraform-provider-aws` → `category: plugin_ecosystem`
- `clerk/javascript` → `category: sdk_client` (already covered by `sdk_library` archetype)

Using `infra_ops` for both helm-charts and external-secrets would cause both repos
to match the same archetype, producing a coverage audit failure for one of them.
