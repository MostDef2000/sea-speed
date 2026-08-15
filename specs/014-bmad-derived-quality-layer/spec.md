# Feature Specification: BMAD-derived delivery quality layer

- Feature: 014-bmad-derived-quality-layer
- Issue: #176
- Status: Approved for implementation
- Owner outcome: Add explicit risk, NFR, traceability, test-design and completion quality to the existing Sea Speed delivery flow without a second workflow engine.

## Product outcome

Significant Sea Speed work must carry durable, executable quality reasoning inside the existing Issue -> SDD -> PR -> CI lifecycle so the Delivery Orchestrator can identify high-risk changes, prove acceptance coverage, surface NFR concerns, and close work against a consistent Definition of Done without introducing BMAD agents, generated workflow configuration, or a parallel source of truth.

## User scenarios

### Scenario 1 - low-risk control-plane work

Given a significant but low-risk control-plane change, when the Delivery Orchestrator opens its PR, then the Change Contract may declare `Risk profile: NOT REQUIRED` while the linked SDD still provides NFR assessment, test design, traceability, correct-course and Definition-of-Done evidence.

### Scenario 2 - high-risk change

Given security, schema, destructive/data-migration, mixed-runtime or another explicit high-risk impact, when the PR is validated, then a complete risk profile is mandatory and is connected to prioritized test/evidence design.

### Scenario 3 - bounded quality concern

Given a known delivery-quality concern, when the PR verdict is `WAIVED`, then the waiver contains a finding, reason, approving owner, review/expiry date, compensating controls and remediation target, while all hard authorization, scope, CI, production and rollback gates remain mandatory.

## Requirements

- FR-001: Significant linked SDD MUST carry the delivery-quality sections in the existing `spec.md`, `plan.md` and `tasks.md` artifacts.
- FR-002: PR admission MUST derive full-risk-profile applicability from security, API/event/state/storage schema, destructive/data-migration, `MIXED` runtime and explicit other-high-risk triggers.
- FR-003: Risk records MUST use categories `TECH`, `SEC`, `PERF`, `DATA`, `BUS`, `OPS`, probability/impact scores 1-5, and a score equal to probability multiplied by impact.
- FR-004: NFR assessment MUST use measurable targets and statuses `PASS`, `CONCERNS`, `FAIL`, `NOT APPLICABLE`; an unknown target MUST NOT be `PASS`.
- FR-005: Test design MUST classify evidence as `unit`, `integration`, `end-to-end` or `runtime-manual` and prioritize it `P0` through `P3`.
- FR-006: Every `AC-*` MUST map to a delivery task plus test/evidence or an explicitly justified runtime-manual evidence path.
- FR-007: PR quality verdict MUST be one of `PASS`, `CONCERNS`, `FAIL`, `WAIVED`; `FAIL` MUST block admission.
- FR-008: `WAIVED` MUST require a complete durable waiver record and MUST NOT override any hard gate.
- FR-009: Correct-course analysis MUST represent production learning, architecture pivot and material scope change impacts on Issue/spec/plan/tasks/authorization.
- FR-010: Definition of Done MUST cover canonical artifacts, exact files, tests/evidence, CI, merge, deployment state, runtime acceptance, deferred work, risks and waivers before terminal completion.
- FR-011: Historical SDD MUST remain readable without mass retrofit; current quality sections become mandatory when an older feature becomes the linked significant work in a new PR.
- FR-012: Existing Delivery Orchestrator ownership, three runtime contours and separate exact-SHA production authorization MUST remain unchanged.

## Acceptance criteria

- AC-001: A new significant PR without the linked quality-enabled SDD is rejected by the existing aggregate quality path.
- AC-002: Low-risk work can validly declare `Risk profile: NOT REQUIRED`.
- AC-003: Security/schema/destructive-data-migration/MIXED/other-high-risk triggers require `Risk profile: REQUIRED`.
- AC-004: A required risk profile without a complete risk row is rejected.
- AC-005: An NFR row with target `UNKNOWN` and status `PASS` is rejected.
- AC-006: Missing acceptance-criterion traceability is rejected.
- AC-007: Test design accepts only canonical levels and `P0-P3` priorities.
- AC-008: Quality verdict `FAIL` blocks Change Contract admission.
- AC-009: `WAIVED` without the complete durable waiver record is rejected; a complete bounded waiver can pass without bypassing hard gates.
- AC-010: Correct-course trigger vocabulary and required impact/follow-up fields are machine checked.
- AC-011: The tasks template no longer requires a separate merge approval and includes the terminal Definition of Done.
- AC-012: Historical feature directories remain repository-valid until they are used as linked significant work again.
- AC-013: Delivery Orchestrator, `OUTCOME APPROVED`, exact-green-head merge, VPS/Ubuntu Worker/relay/Windows AI Worker and `PRODUCTION APPROVED <sha>` semantics remain intact.
- AC-014: Exact final-head PR Validation and aggregate Quality integration pass, followed by successful post-merge push/main validation, with no production workflow dispatched.

## NFR assessment

- NFR-001 | Area: RELIABILITY | Target: invalid quality declarations fail closed in deterministic unit tests | Validation: validator unit tests | Evidence: tests/test_validate_sdd.py and tests/test_change_contract.py | Status: PASS
- NFR-002 | Area: MAINTAINABILITY | Target: quality artifacts remain inside existing SDD and Change Contract files with no new workflow engine | Validation: structural contract test | Evidence: tests/test_delivery_quality_layer.py | Status: PASS
- NFR-003 | Area: COMPATIBILITY | Target: historical SDD remains repository-valid until linked by new significant work | Validation: historical-compatibility unit test | Evidence: test_historical_repository_does_not_require_quality_layer_until_linked | Status: PASS
- NFR-004 | Area: SECURITY | Target: quality waiver never bypasses source authorization, exact scope, CI or production authorization | Validation: contract assertions plus existing hard-gate validators | Evidence: tests/test_delivery_quality_layer.py and tests/test_change_contract.py | Status: PASS

## Compatibility and boundaries

- Stable public interfaces: Delivery Orchestrator lifecycle, Change Contract hard gates, SDD directory identity, aggregate quality workflow context, production safety-envelope semantics.
- Out of scope: BMAD workflow engine, BMAD agent hierarchy, generated OpenCode configuration, separate QA source-of-truth document tree, production deployment, GitHub settings changes, Issue #170/specs/011 changes, PR #158/Issue #157 changes.
- Security constraints: No waiver may reduce authorization, protected-boundary reauthorization, secrets, exact-scope, CI, production authorization, rollback or runtime-acceptance controls.

## Runtime feedback

- Runtime acceptance: NOT REQUIRED (CONTROL_PLANE)
- Accepted production behavior: NOT REQUIRED
- Regressions/learning: NONE YET
- Follow-up work: NONE YET
