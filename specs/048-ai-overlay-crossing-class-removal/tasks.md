# Tasks: AI overlay — remove per-class crossing lines, keep CROSSINGS only

- Issue: #289
- Specification: specs/048-ai-overlay-crossing-class-removal/spec.md
- Plan: specs/048-ai-overlay-crossing-class-removal/plan.md

## Requirements traceability

- AC-001 | Task: TASK-048-01 | Evidence: tests/test_overlay_crossing.py — no per-class text | Coverage: COVERED
- AC-002 | Task: TASK-048-01 | Evidence: tests/test_overlay_crossing.py — yellow line | Coverage: COVERED
- AC-003 | Task: TASK-048-01 | Evidence: tests/test_overlay_crossing.py — summary intact | Coverage: COVERED
- AC-004 | Task: TASK-048-01 | Evidence: git diff --stat single file | Coverage: COVERED
- AC-005 | Task: TASK-048-02 | Evidence: discover green | Coverage: COVERED

## Delivery tasks

Ordered sequence: worker overlay text trim, unit tests, validators, PR, exact-green-head merge, Ubuntu Worker deploy, runtime manual frame check.

## Task records

- TASK-048-01 | Worker overlay — remove per-class loop from draw_overlay, keep CROSSINGS single line + yellow line in `worker/hls_motion_yolo_worker_events.py` | AC-001, AC-002, AC-003, AC-004 | Evidence: tests/test_overlay_crossing.py + diff | Status: COMPLETE
- TASK-048-02 | Validation & deploy — SDD validators, file-scope, PR, merge, Ubuntu runtime_verified, manual frame check | AC-005 | Evidence: CI + manifest + frame screenshot | Status: PENDING

## Completion gate

- [ ] All TASK-048 records COMPLETE or explicitly RUNTIME-MANUAL with reason
- [ ] Exact-head CI green before merge
- [ ] Ubuntu Worker runtime_verified after merge
- [ ] Operator acceptance: single CROSSINGS line on both profiles verified

## Definition of Done

- [ ] Issue/spec/plan/tasks current and linked
- [ ] Exact changed-file scope verified (worker file + SDD)
- [ ] Required tests and evidence complete
- [ ] Required CI green (Repository validation + quality-integration)
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (Ubuntu runtime_verified)
- [ ] Runtime acceptance resolved
- [ ] Deferred work recorded (none)
- [ ] Risks resolved or explicitly accepted (NOT REQUIRED)
- [ ] Waivers resolved or current (none)
