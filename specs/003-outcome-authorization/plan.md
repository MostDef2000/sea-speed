# Implementation Plan: Outcome Authorization

- Specification: specs/003-outcome-authorization/spec.md
- Issue: #107
- Status: Accepted / completed

## Architecture

Outcome Authorization is enforced by governance + PR template + `scripts/ci/validate_change_contract.py`. Production authorization remains separate and exact-SHA bound.

## Decisions

### D-001 - Outcome covers source lifecycle through merge
Reversible repository transitions are covered while exact scope/protected boundaries remain unchanged.

### D-002 - Protected boundaries stale authorization
Material scope, destructive/security/runtime/schema/data-migration redesign requires fresh approval.

### D-003 - Production is separate
Source authorization never grants runtime mutation.

### D-004 - Legacy bridge is historical
Issue #107 used the legacy bridge to activate Outcome Authorization. Stage B closes the transition for new PRs: legacy phrases remain audit evidence only.

## Affected contours

- Repository: governance/control plane.
- VPS: NONE.
- Ubuntu Worker/relay: NONE.
- Windows AI Worker: NONE.
- Public interfaces: NONE.

## Validation

Change Contract tests, repository/SDD validation, aggregate CI. Runtime acceptance NOT REQUIRED.

## Rollout and rollback

Issue #107 transition is complete. Revert governance if necessary; no runtime rollback.

## Runtime feedback

Issue #107 closed completed. Subsequent tasks have used Outcome Authorization; Stage B removes the no-longer-needed active legacy admission path.
