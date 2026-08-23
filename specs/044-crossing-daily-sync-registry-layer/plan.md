# Plan: Crossing daily sync (VLZ midnight), full-class overlay, registry speed row and crossings period layer

- Issue: #278
- Specification: specs/044-crossing-daily-sync-registry-layer/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-044-001 | Category: DATA | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: daily reset preserves pending posts; reset pinned by fixed-timestamp unit tests | Validation: VlzDailyResetTests | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-044-002 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: summary date-window is additive; rolling-hours default preserved for existing consumers | Validation: SummaryDateRangeTests + existing suites | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-044-003 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: registry crossings layer is an additive view toggled off by default; DOM-ready guard pattern reused | Validation: UI-contract pins + node --check + operator check | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED

## Architecture

Worker: VLZ-date tracking with daily counter reset (pending posts preserved); overlay renders all classes. API: summary endpoint gains optional date_from/date_to (VLZ calendar days) alongside rolling hours. Frontend: panel headline/table read state.crossings; objects page gains a toggled crossings layer with VLZ date inputs.

## Decisions

- D1: Vladivostok uses fixed UTC+10 (no DST) — no tz database dependency.
- D2: Panel syncs via state.crossings so overlay and panel share one live source.
- D3: Period view reuses the summary endpoint rather than a new store.

## Affected contours

- Ubuntu Worker/relay: reset + overlay changes deploy canonically.
- VPS: API params and all frontend pages deploy canonically.

## Validation

- Unit: VLZ reset semantics, date-window filtering, malformed-date rejection, overlay cap removal, registry speed row, layer presence.
- Full discovery green; validators pass; exact-head CI required.

## Runtime feedback

To be recorded after both-contour deployment acceptance.

## Test design

- TEST-044-001 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_line_crossing.py::VlzDailyResetTests
- TEST-044-002 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: tests/test_line_crossing.py::SummaryDateRangeTests
- TEST-044-003 | Covers: AC-002 | Level: unit | Priority: P1 | Evidence: tests/test_line_crossing.py::OverlayAllClassesTests
- TEST-044-004 | Covers: AC-001, AC-005 | Level: unit | Priority: P1 | Evidence: RegistrySpeedRowTests
- TEST-044-005 | Covers: AC-001..AC-005 | Level: runtime-manual | Priority: P1 | Evidence: operator verification post-deploy

## Correct-course check

- Adjacent-stage review: COMPLETE
- Trigger: NONE
- Issue impact: operator requested five coordinated refinements to the crossing feature surface
- Specification impact: requirements R1-R5 capture display, reset, sync and period aggregation
- Plan impact: single-source-of-truth sync via state.crossings; additive API parameters
- Tasks impact: traceability maps AC-001..AC-005 to tasks
- Authorization impact: NONE - fresh receipt src-auth-277-crossing-daily-sync-registry-layer covers all changed paths
- Follow-up: operator verifies all five items post-deploy

## Runtime feedback

To be recorded after both-contour deployment acceptance.

## Deployment transaction audit

Required: worker and api runtime deployment follow merge.

- Adjacent-stage review: COMPLETE
- Production-learning root cause: counters lacked a defined day boundary and the panel diverged from the overlay; registry lacked a period aggregation view
- Production-learning adjacent-stage findings: MUTATION covers both contours; VERIFICATION gains midnight-reset and period-view checks; ROLLBACK unchanged per-contour

- TX-044-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport, previous releases continue serving | Retry: after policy/state correction via workflow rerun | Rollback: NOT REQUIRED - no mutation attempted | Evidence: autonomous workflow run log with policy decision id
- TX-044-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: source protection or Quality mismatch aborts before transport | Retry: after remediation | Rollback: NOT REQUIRED - no mutation attempted | Evidence: verify_source_protection.py output in protected workflow logs
- TX-044-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous release keeps serving when health gates fail | Retry: rerun deploy workflow for failed contour | Rollback: redeploy rollbackTarget from manifest | Evidence: deployment manifests both contours
- TX-044-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified=false blocks completion claims | Retry: rerun verification stage | Rollback: rollback target if verification cannot pass | Evidence: manifest checks arrays
- TX-044-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence artifact missing; completion not claimed | Retry: rerun evidence upload | Rollback: NOT REQUIRED - additive evidence | Evidence: exact-artifacts.json on workflow run
- TX-044-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: stale tmp may remain; functionality unaffected | Retry: next deployment | Rollback: NOT REQUIRED - cleanup only | Evidence: deploy logs
- TX-044-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: verified deployment without typed audit not claimed complete | Retry: rerun audit emission | Rollback: NOT REQUIRED - additive | Evidence: typed execution audit bound to policy decision
- TX-044-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback escalates to BLOCKED | Retry: manual decision then redeploy known-good target | Rollback: itself is the rollback path | Evidence: rollbackTarget hash in manifests
