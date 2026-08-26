# Feature Specification: Reusable health-aware development profile

- Feature: 066-reusable-development-profile
- Issue: #331
- Status: ACTIVE
- Owner outcome: Sea Speed uses bounded specialist workers and deterministic local gates without replacing its canonical Delivery Orchestrator or weakening source/runtime authority.

## Product outcome

Connect Sea Speed to the reusable OpenCode project profile so exploration, architecture, implementation, testing, review and UI analysis can use dynamically assigned FREE models with health-aware fallback chains. Preserve the Sea Speed Delivery Orchestrator as the only primary delivery authority and make the repository's existing validation suite executable through one deterministic local gate manifest.

## User scenarios

### Scenario 1 - Health-aware specialist delegation

Given a Sea Speed delivery session with a valid admitted scope, when the canonical Orchestrator delegates bounded work, then the matching `profile-worker-*` agent uses the current FREE-model assignment without gaining independent source, merge or runtime authority.

### Scenario 2 - Deterministic local validation

Given an approved source change, when the project delivery gates run, then the built-in secret scan and Sea Speed repository, contract, SDD, quality and behavioral checks execute from a repository-owned manifest without installing dependencies or mutating tracked source.

### Scenario 3 - Exact OpenCode control-plane admission

Given the reusable profile files are tracked, when repository validation runs, then exactly the canonical agent, project marker and delivery manifest are admitted under `.opencode/**`, while every other tracked path remains rejected.

### Scenario 4 - Sea Speed remains primary

Given OpenCode restarts after profile activation, when project configuration loads, then `sea-speed-delivery-orchestrator` remains the default agent and the reusable profile contributes only specialist workers, LSP defaults and bounded GitHub target checks.

## Requirements

- FR-001: Track a valid `.opencode/project-profile.json` enabling delivery, SDD and GitHub integration for `MostDef2000` with automatic stack detection.
- FR-002: Track a valid `.opencode/delivery-pipeline.json` whose gates reproduce the repository's deterministic local validation domains and rely on the reusable runner's mandatory secret scan.
- FR-003: Document the six `profile-worker-*` roles in the canonical agent entry points, including when each role may run and that worker output is advisory to the Sea Speed Delivery Orchestrator.
- FR-004: Implementation-capable workers MUST run only after valid Sea Speed source admission and MUST remain bounded to approved repository paths.
- FR-005: Dynamic model selection MUST remain owned by the global health-aware assignment cache; Sea Speed source MUST NOT hardcode transient model IDs.
- FR-006: Repository validation MUST admit only `.opencode/agents/sea-speed-delivery-orchestrator.md`, `.opencode/project-profile.json` and `.opencode/delivery-pipeline.json` under `.opencode/**`.
- FR-007: Tests MUST prove the exact allowlist and preserve deterministic rejection of unapproved `.opencode/**` paths.
- FR-008: Existing production policy, deployment workflows, runtime source, global model preferences and model-health implementation MUST remain unchanged.

## Acceptance criteria

- AC-001: Project doctor accepts the profile as `mixed`, SDD/GitHub enabled, with required LSP executables available.
- AC-002: After OpenCode restart, `sea-speed-delivery-orchestrator` remains default and all six dynamically assigned `profile-worker-*` agents are available.
- AC-003: The delivery runner lists and executes the Sea Speed gate manifest with mandatory secret scanning and no tracked-source mutation.
- AC-004: Repository tests assert the exact three-path `.opencode/**` allowlist and reject any fourth tracked path.
- AC-005: Repository, contract, SDD, quality-contract, workflow-policy, full unittest, property, fuzz/recovery and quality-architecture checks pass.
- AC-006: Exact changed-file scope contains only the ten approved paths recorded in Issue #331.

## NFR assessment

- NFR-066-001 | Area: SECURITY | Target: zero credential values enter tracked files or FREE-model context, and exactly three tracked `.opencode/**` paths are admitted | Validation: built-in gate-runner secret scan plus exact allowlist tests | Evidence: `.opencode/delivery-pipeline.json`, `scripts/ci/validate_repo.py`, repository tests | Status: PASS
- NFR-066-002 | Area: RELIABILITY | Target: all six specialist roles resolve through live assignment data or deterministic profile defaults without changing the primary agent | Validation: project doctor, assignment cache inspection and fresh-process agent discovery | Evidence: profile doctor PASS; six `profile-worker-*` agents listed; architect resolved to the current `opencode/x-preview-f-free` assignment; `opencode.json` retains the Sea Speed default | Status: PASS
- NFR-066-003 | Area: OPERABILITY | Target: one local runner invocation executes every required Sea Speed validation domain and returns nonzero on any failure or tracked mutation | Validation: delivery runner full execution | Evidence: secret scan and all nine gates PASS, including 572 unittest cases (2 skipped) and 8 quality-architecture tests | Status: PASS
- NFR-066-004 | Area: MAINTAINABILITY | Target: model preference changes require zero Sea Speed repository edits | Validation: no model IDs in new Sea Speed profile/delegation contract and assignments sourced from global cache | Evidence: changed-file review | Status: PASS

## Compatibility and boundaries

- Stable public interfaces: existing application URLs, APIs, runtime contours, GitHub workflow names and Sea Speed delivery authority.
- Out of scope: production policy, standing delegation, secrets, GitHub/environment settings, deployment workflows, runtime transport, application/API/frontend/worker behavior, global model preferences and health-check implementation.
- Security constraints: deny-by-default routing remains authoritative; FREE cloud workers receive no secrets; workers cannot grant source, merge or runtime authority; `.opencode/**` remains exact-path allowlisted.

## Runtime feedback

- Runtime acceptance: pre-merge CONTROL_PLANE fresh-process verification PASS; exact-main restart evidence remains pending.
- Accepted production behavior: NOT APPLICABLE.
- Regressions/learning: local environment exposes `python3` but no `python`; the repository manifest uses `python3` for deterministic local and GitHub Ubuntu execution.
- Follow-up work: NONE YET.
