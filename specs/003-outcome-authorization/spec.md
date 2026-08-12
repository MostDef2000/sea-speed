# Feature Specification: Outcome Authorization

- Feature: 003-outcome-authorization
- Issue: #107
- Status: Implementation authorized under legacy bridge
- Owner outcome: Approve the bounded product result once and let the Project Manager execute safe repository delivery without repetitive technical approval prompts.

## Product outcome

Sea Speed delivery uses product-outcome authorization rather than per-step technical authorization. For ordinary bounded work, the operator approves what result will be delivered and what boundaries must remain protected; the Project Manager then owns branch, implementation, PR, CI remediation and exact-green-head merge without asking for separate commit or merge confirmations.

## User scenarios

### Scenario 1 - Approve a bounded feature once

Given a canonical Issue and explicit Outcome Contract, when the operator issues `OUTCOME APPROVED`, then reversible repository work continues through exact-green-head merge without separate `COMMIT APPROVED` or `MERGE APPROVED` prompts while scope and protected boundaries remain unchanged.

### Scenario 2 - CI finds an in-scope defect

Given an active Outcome Authorization, when CI exposes a defect that can be fixed inside the approved outcome and file scope, then the Project Manager may commit the repair and rerun CI without asking for new authorization.

### Scenario 3 - Work crosses a protected boundary

Given active Outcome Authorization, when implementation would materially expand product scope, change protected runtime behavior, weaken a security boundary, use secrets differently, perform destructive work, or require incompatible schema/data migration, then work stops before that boundary and fresh authorization is required.

### Scenario 4 - Production is required

Given source has merged under Outcome Authorization, when production mutation is needed, then source authorization alone is insufficient. A separate production safety envelope authorizes the bounded rollout and declared safe rollback, with final execution pinned to an exact green SHA.

## Requirements

- FR-001: Governance MUST define an explicit Outcome Contract before `OUTCOME APPROVED`.
- FR-002: `OUTCOME APPROVED` MUST authorize bounded reversible repository writes, commits, PR operations, in-scope CI remediation and exact-green-head merge.
- FR-003: Merge MUST still require fresh base/head identity, exact changed-file scope, required CI success, zero unresolved review threads and expected-head protection where supported.
- FR-004: Material product-scope expansion, destructive work, secret/security-boundary changes, protected behavior changes, incompatible schema changes and data migrations MUST require fresh authorization.
- FR-005: Source Outcome Authorization MUST NOT authorize production mutation.
- FR-006: A separate production safety envelope MAY cover the task's exact gated deployment, required normal restarts/smokes and an explicitly declared safe rollback condition/target.
- FR-007: Bounded source/CI remediation MUST NOT stale Outcome Authorization or a compatible production envelope when product outcome, runtime contour and protected boundaries remain unchanged.
- FR-008: Change Contract template and validator MUST recognize the authorization model and reject declarations that admit a material scope/protected-boundary change without fresh authorization.
- FR-009: Legacy `COMMIT APPROVED` and separate legacy merge approval MUST remain understandable during transition.
- FR-010: Connector-only GitHub operations, source truth, secret rules, provenance, quality gates and runtime acceptance distinctions MUST remain unchanged.

## Acceptance criteria

- AC-001: A valid future PR may declare `Source authorization: OUTCOME APPROVED` and pass Change Contract validation.
- AC-002: A PR may declare `LEGACY COMMIT APPROVED` during transition and pass source-authorization validation, while governance still requires legacy separate merge authorization.
- AC-003: Invalid/unknown source authorization is rejected by unit tests/CI.
- AC-004: `Material scope/protected-boundary change since authorization: YES` is rejected until fresh authorization is recorded.
- AC-005: Runtime-impact Change Contracts require `Production safety envelope: REQUIRED`; control-plane/non-runtime changes require `NOT REQUIRED`.
- AC-006: Governance states that Outcome Authorization alone is sufficient merge authorization only while all exact-green-head merge gates and Outcome Contract boundaries remain satisfied.
- AC-007: No VPS, worker, Camera 1, camera preview, AI, application schema or secret behavior changes occur in this feature.
- AC-008: Required aggregate CI passes for the transition PR; runtime deployment is NOT REQUIRED.

## Compatibility and boundaries

- Stable public interfaces: Application URLs, APIs, telemetry and runtime behavior unchanged.
- Out of scope: runtime deployment, worker install, Camera 1/preview/AI behavior, application schema changes, `skills/**`, GitHub repository-setting changes.
- Security constraints: Outcome Authorization cannot waive secret/security, destructive, protected-runtime, schema-migration or provenance gates.

## Runtime feedback

- Runtime acceptance: NOT REQUIRED for this governance-only feature.
- Accepted production behavior: unchanged.
- Regressions/learning: repetitive source/merge prompts during Camera Preview delivery motivated explicit outcome-level authorization with protected escalation boundaries.
- Follow-up work: use `OUTCOME APPROVED` for the next bounded feature after this transition PR is merged under legacy authorization.
