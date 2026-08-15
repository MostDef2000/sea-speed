# Implementation Plan: Delivery Orchestrator Convergence

- Specification: specs/013-delivery-orchestrator-convergence/spec.md
- Issue: #174
- Status: Active governance contract

## Architecture

```text
GitHub Issue + current main
 -> Sea Speed Delivery Orchestrator
    -> optional Task Intake lens
    -> Outcome Contract / OUTCOME APPROVED
    -> implementation coordination
    -> optional domain/release review lenses
    -> integrity + PR/CI
    -> expected-head merge
    -> separately authorized runtime contours when applicable
    -> terminal Issue evidence
```

Canonical ownership:

- Governance: authorization/role/audit rules.
- Delivery Policy: runtime applicability, server-pull, fastest-safe execution, production evidence.
- Task Runtime: state semantics.
- Domain/Core Release paths: review lenses only.
- SDD: product/architecture/task/runtime truth; historical Issues/PRs/DRs remain audit history.

## Decisions

### D-001 - Keep compatibility paths, change active meaning
Avoid path breakage while retiring the old PM/Core Release ownership model.

### D-002 - One orchestrator context
Specialist review returns findings; it does not transfer lifecycle ownership.

### D-003 - End the active legacy authorization bridge
`OUTCOME APPROVED` is the only new Change Contract source authorization. Old records remain unchanged.

### D-004 - Grandfather only known SDD collision
Full directory names are canonical; only the pre-policy 002 pair is exempt from numeric-prefix uniqueness.

### D-005 - Audit-preserving SDD reconciliation
Update active artifacts from durable Issue/runtime evidence but never rewrite historical Issues/PRs/DR-001/002/003.

### D-006 - Lifecycle evidence stays on the Issue
Do not create post-merge source-bookkeeping commits solely to tick PR/merge boxes. Source tasks describe implementation; Issue #174 records terminal lifecycle evidence.

## Affected contours

- Repository: governance/contracts/docs/validators/tests/SDD only.
- VPS: NONE.
- Ubuntu Worker/relay: NONE.
- Windows AI Worker: NONE.
- Public interfaces: NONE.

## Validation

- Python compile/unit tests for Change Contract, SDD and convergence rules.
- repository contract/quality validation.
- exact 66-path compare against authorized base.
- PR Validation and Quality integration on exact final head.
- post-merge exact-main PR Validation + Quality integration.

## Rollout and rollback

Source-only expected-head merge. Rollback is revert of the governance PR; no runtime rollback applies.

## Runtime feedback

Production deployment is NOT REQUIRED and forbidden by this Stage B outcome. Terminal source lifecycle evidence belongs on Issue #174.
