# Tasks: Road event hygiene + person detection

- Feature: 039-road-event-hygiene-person-detection
- Specification: specs/039-road-event-hygiene-person-detection/spec.md
- Plan: specs/039-road-event-hygiene-person-detection/plan.md
- Issue: #263
- Status: Source implementation

## Delivery tasks

- [x] T1: SDD artifacts (spec/plan/tasks) for Issue 263.
- [x] T2: Worker event gate — require non-None track_id; skip person events
  (`worker/hls_motion_yolo_worker_events.py`).
- [x] T3: road-v1 class_map gains person (`worker/analytics_profiles.py`).
- [x] T4: API person guard in `post_analytics_event`
  (`api/app/main.py`).
- [x] T5: Tests `tests/test_road_event_hygiene.py`; profile test updates.
- [x] T6: Local validation (unittest discovery, repository validators,
  quality validators).
- [x] T7: PR with exact Change Contract; required CI green on exact head;
  exact-green-head merge.
- [ ] T8: Post-deploy runtime acceptance on both contours (AC-009) recorded
  in Issue 263.

## Requirements traceability

- AC-001 | Task: T2, T5 | Evidence: tests/test_road_event_hygiene.py worker None-track gate | Coverage: COVERED
- AC-002 | Task: T2, T5 | Evidence: tests/test_road_event_hygiene.py worker person gate | Coverage: COVERED
- AC-003 | Task: T3, T5 | Evidence: tests/test_road_event_hygiene.py class_map assertion | Coverage: COVERED
- AC-004 | Task: T4, T5 | Evidence: tests/test_road_event_hygiene.py API guard ok-without-persistence | Coverage: COVERED
- AC-005 | Task: T5 | Evidence: regression assertions for vehicle events | Coverage: COVERED
- AC-006 | Task: T6 | Evidence: full unittest discovery incl. water suites | Coverage: COVERED
- AC-007 | Task: T6 | Evidence: local unittest discovery run log | Coverage: COVERED
- AC-008 | Task: T7 | Evidence: required CI runs on exact PR head in Issue #263 checkpoint | Coverage: COVERED
- AC-009 | Task: T8 | Evidence: post-deploy verification comment to be recorded in Issue #263 | Coverage: RUNTIME-MANUAL | Reason: worker journal and live overlay observable only after protected deployment
- AC-010 | Task: T7 | Evidence: scripts/ci/validate_change_contract.py PASS on PR body | Coverage: COVERED

## Completion gate

All AC checked with evidence; required CI green on merged main; deployment
policy decision recorded; runtime acceptance comment posted.

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved
- [ ] Runtime acceptance resolved
- [x] Deferred work recorded (none)
- [x] Risks resolved or explicitly accepted (RISK-039-001..004 MITIGATED)
- [x] Waivers resolved or current (none)
