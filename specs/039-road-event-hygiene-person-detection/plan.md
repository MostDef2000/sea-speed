# Implementation Plan: Road event hygiene + person detection

- Feature: 039-road-event-hygiene-person-detection
- Specification: specs/039-road-event-hygiene-person-detection/spec.md
- Issue: #263
- Status: Source implementation

## Architecture

- Worker (`worker/hls_motion_yolo_worker_events.py`): the road event gate
  gains two O(1) conditions before posting — best detection must have a
  non-None `track_id`, and its canonical `object_type` must not be `person`.
  Overlay drawing, state counters and tracking are untouched.
- Profile (`worker/analytics_profiles.py`): road-v1 class_map gains
  `"person": "person"`; detector output for persons now flows into tracking,
  overlay and state counters exactly like vehicle classes.
- API (`api/app/main.py`): `post_analytics_event` returns ok without
  persisting or appending to the event log when the event is road-domain and
  its canonical object type is `person` (structural guarantee).

## Decisions

| ID | Decision | Rationale | Alternatives considered |
| --- | --- | --- | --- |
| D1 | Require track_id instead of building a road passage engine | minimal diff, preserves existing product semantics, removes the observed 36% noise | reuse water passage engine (rejected: large refactor, changes road semantics) |
| D2 | Person gate in worker AND API guard | worker gate is the primary filter; API guard is a structural guarantee independent of worker version | worker-only (weaker guarantee) |
| D3 | Person enters class_map rather than a side channel | reuses existing profile plumbing for overlay/state with zero new code paths | separate person counter pipeline (new code, no benefit) |

## Affected contours

MIXED: `worker/**` -> Ubuntu Worker/relay (REQUIRED); `api/**` -> VPS
(REQUIRED). Deployment order per autonomous router policy evaluation.

## Validation

- New tests `tests/test_road_event_hygiene.py`: worker gates (AST-level),
  API person guard, profile class_map.
- Updated `tests/test_analytics_profiles.py` if it asserts exact class sets.
- Full unittest discovery; repository validators; quality validators.

## Risk profile

- Risk profile: REQUIRED

- RISK-039-001 | Category: DATA | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: None-track events are pure noise (no dedup possible); dropping them loses no identifiable history | Validation: production analysis on Issue #263 (181/500 None-track) | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-039-002 | Category: TECH | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: person gate placed at single publication point; unit tests pin behavior | Validation: tests/test_road_event_hygiene.py | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-039-003 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: both contours deploy via standing delegation with rollback targets recorded by manifests | Validation: deployment manifests after merge | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-039-004 | Category: PERF | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: persons add tracker load proportional to their presence; sample_fps unchanged | Validation: existing worker runtime envelope; post-deploy observation | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED

## Test design

- TEST-039-001 | Covers: AC-001, AC-002 | Level: unit | Priority: P0 | Evidence: tests/test_road_event_hygiene.py worker gate assertions
- TEST-039-002 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_analytics_profiles.py or test_road_event_hygiene class_map assertion
- TEST-039-003 | Covers: AC-004, AC-005 | Level: unit | Priority: P0 | Evidence: tests/test_road_event_hygiene.py API guard + regression
- TEST-039-004 | Covers: AC-006, AC-007 | Level: integration | Priority: P0 | Evidence: full unittest discovery incl. water suites
- TEST-039-005 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: required CI runs on exact PR head
- TEST-039-006 | Covers: AC-009 | Level: runtime-manual | Priority: P1 | Evidence: post-deploy journal/event-feed verification recorded in Issue #263

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: production analysis (Issue #263) quantified 36% None-track noise; scope adds person detection requested by operator
- Specification impact: requirements R1-R4 define publication gating and structural persistence guarantee
- Plan impact: decisions D1-D3 bind minimal-diff approach over passage-engine reuse
- Tasks impact: tasks.md traceability maps AC-001..AC-010 to implementation tasks
- Authorization impact: NONE - same approved six-field scope, protected formulas untouched
- Follow-up: verify event-rate reduction and person visibility at post-deploy acceptance (AC-009)

## Runtime feedback

To be recorded after Ubuntu/VPS deployment acceptance.

## Deployment transaction audit

Required: worker and api runtime deployment follow merge.

- Adjacent-stage review: COMPLETE
- Production-learning root cause: road event publication allowed unidentified (None-track) detections which bypassed per-track dedup by design, producing ~36% non-deduplicable noise
- Production-learning adjacent-stage findings: MUTATION/VERIFICATION stages gain one more contour (Ubuntu) routed by the same autonomous policy; EVIDENCE stage gains worker journal check for person absence; ROLLBACK unchanged per-contour

- TX-039-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport, previous releases continue serving | Retry: after policy/state correction via workflow rerun | Rollback: NOT REQUIRED - no mutation attempted | Evidence: deploy-runtime-autonomous workflow run log with policy decision id
- TX-039-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: source protection or Quality mismatch aborts before transport | Retry: after remediation of protection/Quality state | Rollback: NOT REQUIRED - no mutation attempted | Evidence: verify_source_protection.py output in protected workflow logs
- TX-039-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous release keeps running when health checks gate service switch; otherwise restarted service flagged unverified | Retry: rerun deploy workflow for the failed contour | Rollback: redeploy rollbackTarget recorded by deployment manifest | Evidence: deployment-manifest-vps.json and ubuntu deployment manifest
- TX-039-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: service up but runtime_verified=false blocks completion claims | Retry: rerun verification stage via workflow rerun | Rollback: rollback target from manifest if verification cannot pass | Evidence: manifest checks array entries
- TX-039-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: mutation done but evidence artifact missing; completion not claimed | Retry: rerun evidence upload stage | Rollback: NOT REQUIRED - state commit is additive evidence | Evidence: exact-artifacts.json artifacts on workflow run
- TX-039-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: old media/tmp may remain; functionality unaffected | Retry: opportunistic on next sweep/deployment | Rollback: NOT REQUIRED - cleanup only | Evidence: deploy logs
- TX-039-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: verified deployment without typed audit must not be claimed complete | Retry: rerun audit emission stage | Rollback: NOT REQUIRED - evidence is additive | Evidence: sea_speed_production_execution_audit_v1 bound to policy decision
- TX-039-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback escalates to BLOCKED with human decision required | Retry: manual decision then redeploy known-good target | Rollback: itself is the rollback path | Evidence: rollbackTarget hash in deployment manifests
