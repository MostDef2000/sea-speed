# Plan: AI overlay — remove per-class crossing lines, keep CROSSINGS only

- Issue: #289
- Specification: specs/048-ai-overlay-crossing-class-removal/spec.md

## Risk profile

- Risk profile: NOT REQUIRED

## Architecture

Worker-only (Ubuntu Worker/relay shared executable):
- `worker/hls_motion_yolo_worker_events.py:draw_overlay` — remove the `by_class` loop that appended `${class_name}: ${total}` lines to `counter_lines`. Keep `ltr`/`rtl` parsing and single `CROSSINGS -> {ltr} <- {rtl}` entry. Yellow line drawing (`cv2.line` with `(0,255,255)`) remains untouched. Counting state (`_crossings_by_class`, `crossing_overlay_summary`, API) stays intact.

No API, frontend, deploy, or contract change.

## Decisions

- D1: Remove only per-class text generation, not data collection — `by_class` remains in `crossing_overlay_summary` for Crossing counter panel and API, only overlay rendering is trimmed.
- D2: Keep single-line block metrics (width/height) calculation valid for one line — no layout shift, just smaller block.
- D3: Shared worker change covers both water and road contours (single `worker/**` executable).

## Affected contours

- VPS: NOT REQUIRED
- Ubuntu Worker/relay: REQUIRED (worker overlay)

## Validation

- Unit: mock cv2 and assert `putText` calls contain exactly one `CROSSINGS` line and no `car:`/`person:`/`truck:`; assert `cv2.line` still called for yellow line.
- Full discover green; validators pass; exact-head CI required.

## Runtime feedback

To be recorded after Ubuntu Worker deployment acceptance.

## Test design

- TEST-048-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_overlay_crossing.py — overlay with by_class data shows only CROSSINGS, no per-class | Coverage: COVERED
- TEST-048-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: tests/test_overlay_crossing.py — yellow line drawn via cv2.line | Coverage: COVERED
- TEST-048-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_overlay_crossing.py — summary still returns by_class | Coverage: COVERED
- TEST-048-004 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: `python -m unittest discover -s tests -p test_*.py -v` green | Coverage: COVERED
- TEST-048-005 | Covers: AC-001, AC-002 | Level: runtime-manual | Priority: P1 | Evidence: worker frame screenshot shows single CROSSINGS line + yellow line on both profiles | Coverage: RUNTIME-MANUAL | Reason: visual overlay requires device

## Correct-course check

- Adjacent-stage review: COMPLETE (reviewed draw_overlay, crossing counting, Crossing counter panel, shared worker scope)
- Trigger: NONE
- Issue impact: user clarified to keep CROSSINGS aggregate line, remove only per-class lines on both contours
- Specification impact: R1-R4 narrow overlay text to single line, preserve line and data
- Plan impact: Ubuntu REQUIRED, validates via unit mock + manual frame check
- Tasks impact: traceability maps AC-001..AC-005 to tasks
- Authorization impact: NONE — fresh receipt src-auth-289-ai-overlay-crossing-class-removal covers exact worker file
- Follow-up: operator verifies single CROSSINGS line on water & road after deploy

## Deployment transaction audit

Required: runtime deployment REQUIRED (Ubuntu Worker).

- TX-048-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport, previous worker serving | Retry: after policy/state correction | Rollback: NOT REQUIRED | Evidence: autonomous workflow log with policy decision id
- TX-048-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: source protection/Quality mismatch aborts before transport | Retry: after remediation | Rollback: NOT REQUIRED | Evidence: verify_source_protection.py output
- TX-048-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous worker keeps serving on health gate failure | Retry: rerun failed contour | Rollback: redeploy rollbackTarget | Evidence: deployment-manifest Ubuntu runtime_verified
- TX-048-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified=false blocks DONE | Retry: rerun verification | Rollback: rollback target | Evidence: manifest checks array
- TX-048-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing blocks completion | Retry: rerun evidence upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-048-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: stale tmp remains | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-048-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: verified deploy without audit not claimed complete | Retry: rerun audit emission | Rollback: NOT REQUIRED | Evidence: typed execution audit
- TX-048-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual decision + redeploy known-good | Rollback: itself is rollback path | Evidence: rollbackTarget hash
