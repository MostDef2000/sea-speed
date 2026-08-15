# Implementation Plan: Server-Pull Runtime Deployment Handoff

- Specification: specs/006-server-pull-deployment/spec.md
- Issue: #135
- Status: Accepted / completed

## Architecture

```text
operator target shell
 -> short exact-repo/exact-SHA bootstrap
 -> target-local staging
 -> repository-owned entrypoint
 -> bounded mutation + sanitized evidence
```

## Decisions

### D-001 - Repository owns deployment programs
Chat bootstrap is transport only.

### D-002 - Independent runtime contours
VPS and Ubuntu Worker do not orchestrate each other merely to reduce actions.

### D-003 - Fastest safe UX
Largest safe deterministic stage is one operator round trip where possible.

### D-004 - Policy ownership
Detailed execution requirements live in `contracts/SEA_SPEED_DELIVERY_POLICY.md`; orchestration contract references them.

## Affected contours

Repository/control plane only for Issue #135. VPS/Ubuntu/Windows runtime: NONE.

## Validation

Contract/SDD quality gates; runtime acceptance NOT REQUIRED.

## Rollout and rollback

Merge repository policy only; revert source if needed.

## Runtime feedback

Issue #135 is closed completed. Stage B preserves the accepted model while removing duplicated policy text from the compatibility orchestration contract.
