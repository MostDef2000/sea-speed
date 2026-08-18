# Delivery Tasks: Deny-by-default Tool Routing Allowlist

- Specification: specs/025-tool-routing-contract/spec.md
- Plan: specs/025-tool-routing-contract/plan.md
- Issue: #221
- Status: In implementation

## Delivery tasks

- T-001 [P0] Record canonical Issue #221, exact intake main and the immediately preceding eight-path `OUTCOME APPROVED` source authorization. COMPLETE.
- T-002 [P0] Add feature 025 SDD with deny-by-default semantics, closed route matrix, NFR assessment, test design, correct-course check, traceability and Definition of Done. IN PROGRESS.
- T-003 [P0] Update `AGENTS.md` with the concise normative tool-routing admission rule and full approved route matrix. PENDING.
- T-004 [P0] Update `contracts/SEA_SPEED_GOVERNANCE.md` so unlisted tools/services are forbidden and availability never grants permission. PENDING.
- T-005 [P0] Update `contracts/SEA_SPEED_DELIVERY_POLICY.md` with lifecycle-specific primary/fallback routes and explicit forbidden implicit fallbacks. PENDING.
- T-006 [P0] Update `contracts/branches/project-manager.md` so the Delivery Orchestrator never discovers alternate services after an allowlist gap and escalates only through the declared fallback or `HUMAN DECISION REQUIRED`. PENDING.
- T-007 [P0] Update `contracts/runtime/RELEASE_READINESS_GATE.md` with tool-routing admission checks while preserving CONTROL_PLANE/no-production semantics for this Outcome. PENDING.
- T-008 [P0] Open a draft PR with exact eight-file Change Contract, `CONTROL_PLANE`, VPS/Ubuntu deployment `NOT REQUIRED`, execution capabilities `NOT APPLICABLE`, and zero operator runtime actions. PENDING.
- T-009 [P0] Reach exact-head PR Validation and aggregate Quality; remediate only deterministic defects inside the approved eight paths. PENDING.
- T-010 [P0] Re-check main/head/scope/reviews and merge only the exact green head with expected-head protection, then require exact-main Quality. PENDING.
- T-011 [P0] Persist terminal source evidence to Issue #221 and close only after the control-plane acceptance criteria are satisfied. PENDING.

## Requirements traceability

- AC-001 | Task: T-003,T-004,T-005,T-006,T-007 | Evidence: synchronized deny-by-default language in all five canonical entry points | Coverage: COVERED
- AC-002 | Task: T-003,T-004,T-005,T-006 | Evidence: explicit availability-is-not-authorization and no-alternate-service rules | Coverage: COVERED
- AC-003 | Task: T-003,T-004,T-005,T-006 | Evidence: Connector-only GitHub lifecycle clauses | Coverage: COVERED
- AC-004 | Task: T-003,T-005,T-006,T-007 | Evidence: exact CI endpoint fallback limited to one bounded read-only GitHub API/PowerShell command | Coverage: COVERED
- AC-005 | Task: T-003,T-004,T-005 | Evidence: local ephemeral tooling declared preparation-only/non-publication/non-production | Coverage: COVERED
- AC-006 | Task: T-003,T-005,T-006 | Evidence: public HTTP read-only route and exact `curl`/PowerShell fallback | Coverage: COVERED
- AC-007 | Task: T-005,T-006,T-007 | Evidence: existing VPS/Ubuntu repository-owned deployment entrypoints remain exclusive | Coverage: COVERED
- AC-008 | Task: T-003,T-004,T-005,T-006 | Evidence: explicit prohibition on ad-hoc SSH/shell, direct DB mutation, cloud-console and side-channel fallbacks | Coverage: COVERED
- AC-009 | Task: T-003,T-004,T-005,T-006 | Evidence: protected-input locality rules | Coverage: COVERED
- AC-010 | Task: T-003,T-004,T-005,T-006 | Evidence: Gmail/Calendar/Drive/Notion and all unlisted services forbidden as implicit fallbacks | Coverage: COVERED
- AC-011 | Task: T-008,T-009,T-010 | Evidence: Connector exact changed-file comparison and machine-valid CONTROL_PLANE Change Contract | Coverage: COVERED
- AC-012 | Task: T-009,T-010,T-011 | Evidence: exact-head PR Validation/Quality, expected-head merge, exact-main Quality and Issue evidence | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current — Issue #221 and feature 025 represent the approved deny-by-default routing Outcome.
- [ ] Exact changed-file scope verified — final PR must contain only the eight authorized paths.
- [ ] Required tests and evidence complete — cross-contract route consistency and existing repository validation must pass.
- [ ] Required CI green — exact-head PR Validation and aggregate Quality plus exact-main Quality are required.
- [ ] Exact-green-head merge complete — merge remains pending.
- [x] Deployment state resolved — this Outcome is CONTROL_PLANE and requires no VPS/Ubuntu deployment.
- [x] Runtime acceptance resolved — no runtime acceptance applies because no runtime source/workflow/topology is changed.
- [x] Deferred work recorded — any future unlisted tool/service requires a separate allowlist Scope rather than implicit expansion.
- [x] Risks resolved or explicitly accepted — full risk profile is NOT REQUIRED for this bounded control-plane documentation contract.
- [x] Waivers resolved or current — no waiver is active.

## Completion gate

`DONE` is forbidden until the exact eight-path source diff is synchronized across all five canonical entry points, feature 025 SDD remains machine-valid, the PR Change Contract derives CONTROL_PLANE with both runtime deployments NOT REQUIRED, exact-head PR Validation and aggregate Quality are green, the exact green head is merged with freshness/scope/review protection, and exact-main Quality succeeds. No production authorization or runtime mutation is part of this Outcome.