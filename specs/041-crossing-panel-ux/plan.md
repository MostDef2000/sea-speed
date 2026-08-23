# Plan: Crossing panel UX refinements

- Issue: #271
- Specification: specs/041-crossing-panel-ux/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-041-001 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: changes confined to the self-contained panel script; handlers pinned by UI-contract tests | Validation: full unittest discovery + node --check | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-041-002 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: delete-line persists server state so worker stops counting immediately via existing refresh window | Validation: UI-contract pins + runtime verification | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED

## Architecture

Self-contained panel script on both pages; no API or worker changes; delete-line reuses the existing crossing-line config endpoint with the disabled empty payload.

## Decisions

- D1: Delete-line persists `{enabled:false, line:[]}` rather than clearing only local state, so counting stops deterministically.
- D2: Toggle derives its label from fetched config state and syncs after every mutation.

## Affected contours

- VPS: frontend pages deploy via the canonical VPS contour.

## Validation

- Unit: CrossingPanelUiTests pin labels, delete persistence payload and toggle logic.
- Full discovery green; validators pass before push; exact-head CI required.

## Runtime feedback

- To be recorded after VPS deployment acceptance.

## Test design

- TEST-041-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_line_crossing.py::CrossingPanelUiTests
- TEST-041-002 | Covers: AC-002, AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_line_crossing.py::CrossingPanelUiTests
- TEST-041-003 | Covers: AC-001, AC-002 | Level: runtime-manual | Priority: P1 | Evidence: operator UI verification post-deploy

## Correct-course check

- Adjacent-stage review: COMPLETE
- Trigger: NONE
- Issue impact: operator-requested UX refinement within the crossing feature surface
- Specification impact: requirements R1-R3 capture the two requested behaviors precisely
- Plan impact: minimal-diff approach over the existing panel script
- Tasks impact: traceability maps AC-001..AC-003 to implementation tasks
- Authorization impact: NONE - same approved six-field outcome, SDD artifacts added as mandatory companions
- Follow-up: verify both buttons post-deploy on both pages

## Runtime feedback

To be recorded after VPS deployment acceptance.

## Deployment transaction audit

Required: frontend deployment follows merge.

- Adjacent-stage review: COMPLETE
- Production-learning root cause: initial panel wording did not match operator mental model for line removal and toggle state
- Production-learning adjacent-stage findings: MUTATION stage covers the VPS contour only; VERIFICATION gains operator UI checks; ROLLBACK unchanged

- TX-041-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport, previous release continues serving | Retry: after policy/state correction via workflow rerun | Rollback: NOT REQUIRED - no mutation attempted | Evidence: autonomous workflow run log with policy decision id
- TX-041-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: source protection or Quality mismatch aborts before transport | Retry: after remediation | Rollback: NOT REQUIRED - no mutation attempted | Evidence: verify_source_protection.py output in protected workflow logs
- TX-041-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous release keeps serving when health gates fail | Retry: rerun deploy workflow | Rollback: redeploy rollbackTarget from manifest | Evidence: deployment-manifest-vps.json
- TX-041-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: service up but runtime_verified=false blocks completion claims | Retry: rerun verification stage | Rollback: rollback target if verification cannot pass | Evidence: manifest checks array
- TX-041-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence artifact missing; completion not claimed | Retry: rerun evidence upload | Rollback: NOT REQUIRED - additive evidence | Evidence: exact-artifacts.json on workflow run
- TX-041-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: stale tmp may remain; functionality unaffected | Retry: next deployment | Rollback: NOT REQUIRED - cleanup only | Evidence: deploy logs
- TX-041-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: verified deployment without typed audit not claimed complete | Retry: rerun audit emission | Rollback: NOT REQUIRED - additive | Evidence: typed execution audit bound to policy decision
- TX-041-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback escalates to BLOCKED | Retry: manual decision then redeploy known-good target | Rollback: itself is the rollback path | Evidence: rollbackTarget hash in manifest
