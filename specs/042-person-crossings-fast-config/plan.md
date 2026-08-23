# Plan: Person crossings + fast crossing-line config refresh

- Issue: #274
- Specification: specs/042-person-crossings-fast-config/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-042-001 | Category: DATA | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: registry guard is structural (domain+class check) placed before persist call; pinned by unit test | Validation: ApiCrossingTests road-person case | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-042-002 | Category: PERF | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: 1s polling of a file-read endpoint from two workers only | Validation: runtime observation post-deploy | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-042-003 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: person counting reuses the same track side-memory path as other classes | Validation: CrossingDetectionTests person case | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED

## Architecture

Worker: drop the person skip in update_crossing_counts; lower CROSSING_LINE_REFRESH_SEC default to 1.0. API: conditional persist_object_event inside post_analytics_crossing guarded by domain/class; store append unchanged.

## Decisions

- D1: Persons flow through canonical /crossings ingest so counters and the 24h summary share one source of truth.
- D2: Registry exclusion stays structural at the API boundary, mirroring the #263 event-feed guard.

## Affected contours

- Ubuntu Worker/relay: counting + config TTL changes deploy canonically.
- VPS: API guard deploys canonically.

## Validation

- Unit: person counted; road-person ingest skips registry but feeds store; TTL default pin.
- Full discovery green; validators pass; exact-head CI required.

## Runtime feedback

To be recorded after both-contour deployment acceptance.

## Test design

- TEST-042-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_line_crossing.py::CrossingDetectionTests
- TEST-042-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: tests/test_line_crossing.py::ApiCrossingTests
- TEST-042-003 | Covers: AC-003 | Level: unit | Priority: P1 | Evidence: tests/test_line_crossing.py::CrossingConfigRefreshTests
- TEST-042-004 | Covers: AC-001, AC-002 | Level: runtime-manual | Priority: P1 | Evidence: operator verification post-deploy

## Correct-course check

- Adjacent-stage review: COMPLETE
- Trigger: NONE
- Issue impact: operator requested person counting without registry/event pollution and a faster line-update trail
- Specification impact: requirements R1-R3 capture counting, registry guard and TTL precisely
- Plan impact: minimal-diff changes confined to two functions plus tests
- Tasks impact: traceability maps AC-001..AC-003 to tasks
- Authorization impact: NONE - fresh receipt src-auth-274-person-crossings-fast-config covers all changed paths
- Follow-up: verify person counters and clean registry post-deploy on both contours

## Runtime feedback

To be recorded after both-contour deployment acceptance.

## Deployment transaction audit

Required: worker and api runtime deployment follow merge.

- Adjacent-stage review: COMPLETE
- Production-learning root cause: person detections were excluded from counting entirely while the operator wants them counted but kept out of durable stores
- Production-learning adjacent-stage findings: MUTATION stage covers both contours; VERIFICATION gains person-counter and clean-registry checks; ROLLBACK unchanged per-contour

- TX-042-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport, previous releases continue serving | Retry: after policy/state correction via workflow rerun | Rollback: NOT REQUIRED - no mutation attempted | Evidence: autonomous workflow run log with policy decision id
- TX-042-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: source protection or Quality mismatch aborts before transport | Retry: after remediation | Rollback: NOT REQUIRED - no mutation attempted | Evidence: verify_source_protection.py output in protected workflow logs
- TX-042-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous release keeps serving when health gates fail | Retry: rerun deploy workflow for failed contour | Rollback: redeploy rollbackTarget from manifest | Evidence: deployment manifests both contours
- TX-042-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified=false blocks completion claims | Retry: rerun verification stage | Rollback: rollback target if verification cannot pass | Evidence: manifest checks arrays
- TX-042-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence artifact missing; completion not claimed | Retry: rerun evidence upload | Rollback: NOT REQUIRED - additive evidence | Evidence: exact-artifacts.json on workflow run
- TX-042-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: stale tmp may remain; functionality unaffected | Retry: next deployment | Rollback: NOT REQUIRED - cleanup only | Evidence: deploy logs
- TX-042-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: verified deployment without typed audit not claimed complete | Retry: rerun audit emission | Rollback: NOT REQUIRED - additive | Evidence: typed execution audit bound to policy decision
- TX-042-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback escalates to BLOCKED | Retry: manual decision then redeploy known-good target | Rollback: itself is the rollback path | Evidence: rollbackTarget hash in manifests
