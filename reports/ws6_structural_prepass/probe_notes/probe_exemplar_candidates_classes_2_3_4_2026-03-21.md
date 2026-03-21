# Exemplar Candidates: Classes 2, 3, 4
**Date:** 2026-03-21
**Parent bead:** github_repos-wma
**This bead:** github_repos-fm4

These three subsystem classes have no corpus exemplar and cannot be probed until at least one candidate is onboarded. This note proposes 1–2 candidates per class with rationale and known structural features. **Output only — do not onboard here.** A follow-up intake bead is needed for each class that proceeds.

---

## Class 2: Infra/Ops Surfaces

**Target shape:** repos where infra IS the product. Primary artifact is deploy/, helm/, terraform/, or k8s/ content. Avoid app repos that merely include a docker-compose.yml alongside substantial application code.

### Candidate 2A — `external-secrets/external-secrets`

**Rationale:** Kubernetes operator whose product is the operator binary + CRD definitions + Helm chart. There is no "app" being operated — the operator itself is the deliverable. Clean Go + Helm structure.

**Known structural features:**
- `pkg/` — operator logic (Go)
- `cmd/` — operator entrypoint
- `apis/` — CRD type definitions (generated)
- `deploy/` — raw Kubernetes manifests and CRDs
- `helm/` — Helm chart for installation (primary distribution method)
- `docs/` — end-user documentation

**Probe signal:** `deploy/` and `helm/` are first-class artifacts, not clutter. A pre-pass that treats them as "auxiliary config" would underweight the infra surface. `pkg/` is the implementation but `helm/` is what users consume.

**Size estimate:** Medium. Go source + YAML charts, no large assets. Should be cloneable (est. 50–150 MB).

**Risk:** The operator has grown over time. `helm/` and `deploy/` are organized but may look like deep config nesting if the tool only scores top-level directories.

---

### Candidate 2B — `grafana/helm-charts`

**Rationale:** Pure Helm chart repository. The entire product is charts — no application code at all. Maximum signal-to-noise for the "infra is the product" shape.

**Known structural features:**
- `charts/` — top-level; each subdirectory is a distinct Helm chart (grafana, loki, tempo, mimir, etc.)
- Each chart: `Chart.yaml`, `values.yaml`, `templates/`, optional `ci/`
- No `src/`, no `cmd/`, no application runtime code

**Probe signal:** If `charts/` is not ranked as primary surface, something is wrong. A pure chart repo should be the easiest possible infra exemplar.

**Size estimate:** Small. All YAML. Well under any size cap.

**Risk:** Low. The repo may be too clean — if the tool handles it correctly, there may be no refinement signal. That's fine; it confirms the floor behavior for this class.

**Recommendation:** Onboard 2B first (clean/small, establishes baseline), then 2A (more complex, tests operator-specific patterns).

---

## Class 3: Plugin/Integration Ecosystems

**Target shape:** repos where providers/, connectors/, adapters/, or plugins/ are the primary surface and the core runtime is thin. Target is a connector framework, provider registry, or plugin host — not an app repo where integrations are extras alongside a substantial core.

### Candidate 3A — `hashicorp/terraform-provider-aws`

**Rationale:** Single Terraform provider repo where the resource definitions (connectors to AWS services) are the entire product. The `main.go` bootstrap is trivial; the work is in hundreds of per-service resource implementations.

**Known structural features:**
- `internal/service/` — per-service subdirectories (ec2/, s3/, rds/, iam/, lambda/, etc.), each containing resource and data source implementations
- `website/` — documentation for each resource (mirrors service/ structure)
- `main.go` — thin provider registration and schema wiring
- No substantial runtime beyond the provider binary

**Probe signal:** `internal/service/` is the primary surface. A ranking that elevates `main.go` as the representative surface would miss the point of this repo's shape — it's a resource library, not an application.

**Size estimate:** Large. Go source for 300+ AWS services. Probably 300–600 MB. Flag as size risk; may require checking against the clone size cap before onboarding.

**Risk:** May exceed size cap. `internal/service/` uses deep nesting rather than a flat `connectors/` root, which tests whether the tool identifies the ecosystem from structural depth rather than directory names.

---

### Candidate 3B — `open-telemetry/opentelemetry-collector-contrib`

**Rationale:** The canonical connector-ecosystem repo: `receiver/`, `exporter/`, `processor/`, `extension/` directories each contain dozens of plugin subdirectories. The core runtime lives in a sibling repo (`opentelemetry-collector`); this repo IS the plugin surface.

**Known structural features:**
- `receiver/` — 50+ receiver plugins (kafka, prometheus, jaeger, etc.), each a Go module
- `exporter/` — 50+ exporter plugins (elasticsearch, otlp, logging, etc.)
- `processor/` — transform/filter plugins
- `extension/` — auxiliary plugin types
- `internal/` — shared utilities (thin relative to plugin surface)

**Probe signal:** If any of `receiver/`, `exporter/`, `processor/` are not ranked as primary orientation surfaces, the tool is failing on the connector-ecosystem class. The plugin directories should dominate.

**Size estimate:** Very large. 200+ Go modules with generated code. Likely 1–2 GB. **High size risk — may not be cloneable.** Confirm against size cap before attempting intake.

**Risk:** Size is the primary blocker. If it cannot be cloned, this candidate cannot be used. 3A is the safer fallback.

**Recommendation:** Attempt 3A first. If size cap is not an issue, add 3B for a second pass with the canonical flat-plugin-directory structure.

---

## Class 4: Multi-Package SDK Monorepos

**Target shape:** repos with `packages/` or `sdks/` subtrees containing multiple distinct client libraries (language bindings or per-service platform SDKs). Core runtime is thin or absent. Avoid monorepos where `packages/` exists only for build tooling.

### Candidate 4A — `firebase/firebase-js-sdk`

**Rationale:** Official Firebase JavaScript SDK, structured as a monorepo where each Firebase product is a separately-published `@firebase/*` package. The packages ARE the product — consumers install individual packages, not a single bundle.

**Known structural features:**
- `packages/` — 30+ directories, one per Firebase product: auth/, firestore/, storage/, database/, functions/, messaging/, analytics/, etc.
- Each package: `src/`, `test/`, `package.json`, own `tsconfig.json`
- `packages-exp/` — experimental versions of some packages (some repos may have this)
- `scripts/` — repo-level build/release tooling (not part of the SDK surface)
- Top-level `package.json` is workspace root only — thin bootstrap

**Probe signal:** `packages/auth/`, `packages/firestore/`, etc. should be ranked as primary surfaces, not the workspace root `package.json`. If `scripts/` outranks the package directories, the tool is misreading the SDK monorepo shape.

**Size estimate:** Medium-large. TypeScript source across 30+ packages. Probably 200–500 MB. Should be cloneable; no large binary assets.

**Risk:** Deep nesting (`packages/auth/src/`) may compete with the package root `packages/auth/` for ranking. The key question is whether the tool surfaces `packages/` subtrees or only looks at the top-level directory shape.

---

### Candidate 4B — `clerk/javascript`

**Rationale:** Per-platform SDK monorepo: `packages/` contains distinct client libraries for different JavaScript environments (nextjs, react, gatsby, chrome-extension, clerk-js, etc.). Core shared code is in `packages/shared/` and `packages/backend/`. Smaller and more focused than 4A.

**Known structural features:**
- `packages/nextjs/` — Next.js SDK package
- `packages/react/` — React SDK package
- `packages/clerk-js/` — Vanilla JS SDK (browser)
- `packages/backend/` — Node.js backend SDK
- `packages/shared/` — shared utilities (not a user-facing package)
- Each package: `src/`, `package.json`, own build config
- Top-level `package.json` is Turborepo workspace root

**Probe signal:** Per-platform packages should dominate `likely_first_read`. If `packages/shared/` outranks `packages/nextjs/` or `packages/clerk-js/`, that would indicate the tool cannot distinguish thin-shared-utility packages from primary SDK packages.

**Size estimate:** Medium. TypeScript monorepo with ~15 packages. Probably 100–300 MB. Lower risk than 4A.

**Risk:** Some packages (shared, backend) are utilities rather than user-facing SDKs. The distinction between "package that is a client library" vs "package that is internal shared code" is semantic and may not be detectable from structure alone.

**Recommendation:** Onboard 4B first (smaller, cleaner per-platform structure), then 4A for the larger per-service variant. Both are needed to probe different monorepo shapes.

---

## Summary Table

| Class | Candidate | GitHub | Size Risk | Priority |
|---|---|---|---|---|
| 2 — Infra/ops | Pure Helm chart repo | `grafana/helm-charts` | Low | Onboard first |
| 2 — Infra/ops | k8s operator | `external-secrets/external-secrets` | Medium | Onboard second |
| 3 — Plugin ecosystems | Single provider w/ rich internals | `hashicorp/terraform-provider-aws` | High | Check size cap first |
| 3 — Plugin ecosystems | Canonical flat plugin dirs | `open-telemetry/opentelemetry-collector-contrib` | Very High | Fallback only if size allows |
| 4 — SDK monorepos | Per-platform SDK packages | `clerk/javascript` | Low-Medium | Onboard first |
| 4 — SDK monorepos | Per-service SDK packages | `firebase/firebase-js-sdk` | Medium | Onboard second |
