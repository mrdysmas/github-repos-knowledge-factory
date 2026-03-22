# Probe: hashicorp/terraform-provider-aws (github_repos-c12)
**Date:** 2026-03-22  
**Batch:** B19_terraform_provider_aws  
**Archetype target:** Class (3) — plugin/integration ecosystem  

## Repo shape
- Root `main.go`: thin 50-line bootstrap → calls `provider.ProtoV5ProviderServerFactory`, registers with Terraform plugin protocol
- `internal/service/`: 263 per-AWS-service subdirectories (s3, ec2, acm, …) — the canonical flat-plugin connector surface
- `internal/provider/`: provider factory/registration  
- `.ci/providerlint/`: standalone Go CI linting tool (own go.mod)  
- `skaff/`: scaffolding CLI tool (own go.mod)  

## Prepass output assessment

### likely_first_read
1. `internal/service/cloudformation/test-fixtures/.../cmd/main.go` ← test fixture, noise
2. `.ci/providerlint/main.go` ← CI tool, noise
3. `.ci` ← CI dir, noise
4. **`internal/service`** ← correct connector surface ✅
5. `internal/acctest` ← test infra, noise
6. `skaff/main.go` ← scaffolding tool, noise

Root `main.go` absent entirely.

### likely_runtime_surfaces
All noise:
- Test fixture `cmd/main.go`
- `.ci/providerlint/main.go` (CI tool)
- `skaff/main.go` (scaffolding)
- `internal/acctest/acctest.go` (test infra)
- `mkdocs.yml`, `.github/workflows/mkdocs.yml` (docs config)

The actual runtime surface (`internal/service/`, `internal/provider/`, root `main.go`) is entirely absent.

### module_groups
- `internal/service` appears as one group "service" — correct label, wrong granularity
- No per-service subdirs visible (s3, ec2, etc.)
- The flat-plugin shape is invisible at connector level

## Verdict: SPAWN REFINEMENT BEAD

Failure modes:
1. **Spurious main.go pollution**: Ancillary go.mod packages (`.ci/providerlint/`, `skaff/`) have their own `main.go` files that rank above the canonical root bootstrap. Root `main.go` is displaced.
2. **likely_runtime_surfaces is noise-dominated**: No connector surface in the output. All entries are CI tools, test infra, scaffolding, or docs.
3. **Flat-plugin shape invisible**: 263 per-service connectors collapsed to one `internal/service` group. Reader cannot see the "one subpackage per AWS service" shape.
4. **internal/service rank**: Appears at rank 4 in `likely_first_read` — below three noise entries. Insufficient for class (3) orientation.

## Refinement needed
The prepass needs a signal to recognize multi-module repos where ancillary tools (CI linters, scaffolding) have own go.mod + main.go. These should be demoted. The primary package root (root go.mod) and its `main.go` should be the anchor. For `internal/service/`-style layouts, per-connector subdirectory visibility (or at minimum, correct top-rank for the aggregate) is needed in `likely_runtime_surfaces`.
