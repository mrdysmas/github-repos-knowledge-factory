# Probe: SDK/Client Families and Library-First Repos
**Date:** 2026-03-21
**Parent bead:** github_repos-wma
**This bead:** github_repos-3sl

---

## Probe Target

**Classes:**
- **(4) SDK/client families** — library packages published as client SDKs, sometimes under `clients/`, `sdks/`, or as single-package repos
- **(7) Library-first repos with thin CLIs** — repos where the real core is a library package and thin CLI or script entrypoints might outrank it

Combined because they share the structural concern: the real core is a library package, not a process entrypoint, and the ranking risk is that scripts or CLI entries outrank the library root.

---

## Exemplar Repo

**`airtable/airtable.js`** (B15 output: `reports/ws6_structural_prepass/B15_ws6_prepass_default_promotion_calibration/airtable__airtable.js.yaml`)

**Structure:**
- `src/` — TypeScript source (the authored library code)
- `lib/` — compiled JS output (what consumers import; `package.json main: ./lib/airtable.js`)
- `build/` — browser bundle (`build/airtable.browser.js`)
- `scripts/` — dev utility only (`check-is-build-fresh.sh`)
- No `bin` field in `package.json` → no CLI entrypoint
- `files: ["/lib/"]` in `package.json` → publish surface is lib/ only
- `types: ./lib/airtable.d.ts` → TypeScript types in lib/

---

## B15 Output

```
orientation_hints:
  likely_first_read:
  - lib/airtable.js
  - src
  likely_runtime_surfaces:
  - lib/airtable.js
  - tsconfig.json
```

---

## Probe Findings

### Q1: Is lib/ correctly ranked as primary surface over thin CLI/script?

**YES — unambiguous.**

`lib/airtable.js` is first in both `likely_first_read` and `likely_runtime_surfaces`. The `scripts/` shell utility is absent from output (correctly excluded). No `bin` entrypoint exists, so there's nothing to outrank `lib/`. The tool correctly identifies the `package.json main` field and surfaces the library entry.

### Q2: Does the tool produce useful orientation for a pure-library repo with no process entrypoints?

**YES, with one noise item.**

`lib/airtable.js` is the correct surface for a library consumer — it IS the published API surface (even though it's not a process entrypoint). `src` in `likely_first_read` correctly points to authored source. A reader understands where to start.

**Noise item:** `tsconfig.json` in `likely_runtime_surfaces`. Root cause: `typescript_config` is included in `preferred_config_kinds` for the runtime surfaces ranking pass (line 1276 of `ws6_structural_prepass.py`). This logic was designed for app repos where tsconfig configures the TypeScript compilation environment. For a library-first repo, tsconfig is build-only and not a runtime surface. The issue is not library-specific — any TypeScript repo would get tsconfig.json here.

This is mild noise, not misleading. `lib/airtable.js` still leads.

### Q3: Are there structural signals that could flag library-first shape?

**YES — available but unused:**
- No `bin` field in `package.json` → no process entrypoints, library-only
- `files` array pointing only to `lib/` → published surface is the library, not scripts
- Presence of `types` field → TypeScript library with a defined API contract
- `lib/` as compiled output (not in `prefer_source_equivalent_path`'s recognized dist dirs: `dist/`, `build/`, `out/`)

These signals could support a future library-first shape annotation, but since Q1 and Q2 are satisfied, this is a future enhancement, not a current gap.

---

## Refinement Decision

**NO refinement bead.** Neither threshold condition is met:

1. **Library core ranked below noise?** — NO. `lib/airtable.js` is first in both orientation lists.
2. **Output misleading for consumer expecting a runtime surface that doesn't exist?** — NO. `lib/airtable.js` IS the correct surface for a library consumer (the published API). The output is accurate.

The `tsconfig.json` noise is a broader TypeScript config classification issue (not library-specific). It doesn't cross the threshold on its own.

---

## Coverage Gap (Not Blocking)

This probe tested the **single-package library SDK** case (airtable/airtable.js). The **multi-package SDK family** case (e.g., repos with `clients/`, `packages/`, or language-specific binding subdirectories) was not tested — no corpus exemplar available. If encountered, the risk is that individual client files inside subdirectories outrank the package roots. Defer until a corpus exemplar exists.

---

## Summary

Classes 4 and 7 pass for the single-package library case. The tool correctly promotes the library export surface, excludes dev utilities, and produces a coherent orientation. No structural refinement needed at this time.
