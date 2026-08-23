# Plan: Crossing speed in registry + top-5 overlay counter classes

- Issue: #276
- Specification: specs/043-crossing-speed-overlay-top5/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-043-001 | Category: DATA | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: speed consumed as-is from the already-computed detection field; optional_float guards absent values | Validation: unit tests for payload and persistence | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-043-002 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: overlay class limit raised 3 to 5; rendering path unchanged | Validation: source pin test + runtime observation | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED

## Architecture

Worker: crossing payload gains speed_kmh from the detection record; overlay counter renders top-5 classes. API: post_analytics_crossing persists speed_kmh into the record consumed by persist_object_event and the bounded store.

## Decisions

- D1: Speed passes through unchanged — no recomputation, no formula exposure.
- D2: Top-5 chosen over unlimited list to keep the overlay block compact.

## Affected contours

- Ubuntu Worker/relay: payload + overlay changes deploy canonically.
- VPS: ingest persistence change deploys canonically.

## Validation

- Unit: payload carries speed; ingest persists it; top-5 source pin.
- Full discovery green; validators pass; exact-head CI required.

## Runtime feedback

To be recorded after both-contour deployment acceptance.

## Test design

- TEST-043-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_line_crossing.py::CrossingDetectionTests
- TEST-043-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: tests/test_line_crossing.py::ApiCrossingTests
- TEST-043-003 | Covers: AC-003 | Level: unit | Priority: P1 | Evidence: OverlayLayoutTests source pin
- TEST-043-004 | Covers: AC-001, AC-002 | Level: runtime-manual | Priority: P1 | Evidence: operator verification post-deploy

## Correct-course check

- Adjacent-stage review: COMPLETE
- Trigger: NONE
- Issue impact: production data showed 55/99 road registry rows without speed (crossing-derived); person displaced from overlay top-3
- Specification impact: requirements R1-R3 capture passthrough and rendering precisely
- Plan impact: minimal-diff changes confined to two functions plus tests
- Tasks impact: traceability maps AC-001..AC-003 to tasks
- Authorization impact: NONE - fresh receipt src-auth-276-crossing-speed-overlay-top5 covers all changed paths
- Follow-up: verify new line_crossing rows show speed post-deploy

## Runtime feedback

To be recorded after both-contour deployment acceptance.

## Deployment transaction audit

Required: worker and api runtime deployment follow merge.

- Adjacent-stage review: COMPLETE
- Production-learning root cause: crossing payloads omitted the measured speed field so registry rows derived from crossings rendered em-dash speeds
- Production-learning adjacent-stage findings: MUTATION covers both contours; VERIFICATION gains registry-speed check; ROLLBACK unchanged per-contour

- TX-043-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport, previous releases continue serving | Retry: after policy/state correction via workflow rerun | Rollback: NOT REQUIRED - no mutation attempted | Evidence: autonomous workflow run log with policy decision id
- TX-043-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: source protection or Quality mismatch aborts before transport | Retry: after remediation | Rollback: NOT REQUIRED - no mutation attempted | Evidence: verify_source_protection.py output in protected workflow logs
- TX-043-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous release keeps serving when health gates fail | Retry: rerun deploy workflow for failed contour | Rollback: redeploy rollbackTarget from manifest | Evidence: deployment manifests both contours
- TX-043-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified=false blocks completion claims | Retry: rerun verification stage | Rollback: rollback target if verification cannot pass | Evidence: manifest checks arrays
- TX-043-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence artifact missing; completion not claimed | Retry: rerun evidence upload | Rollback: NOT REQUIRED - additive evidence | Evidence: exact-artifacts.json on workflow run
- TX-043-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: stale tmp may remain; functionality unaffected | Retry: next deployment | Rollback: NOT REQUIRED - cleanup only | Evidence: deploy logs
- TX-043-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: verified deployment without typed audit not claimed complete | Retry: rerun audit emission | Rollback: NOT REQUIRED - additive | Evidence: typed execution audit bound to policy decision
- TX-043-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback escalates to BLOCKED | Retry: manual decision then redeploy known-good target | Rollback: itself is the rollback path | Evidence: rollbackTarget hash in manifests
