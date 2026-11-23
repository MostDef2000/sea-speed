# Implementation Plan: Ingest frame conformance (black / slate / freeze)

- Feature: 700-ingest-frame-conformance
- Specification: specs/700-ingest-frame-conformance/spec.md
- Issue: #700
- Status: Source implementation

## Architecture

One pixel-only detector lives in the worker entry module and is instantiated once
per reader beside `MotionDetector`:

1. `worker/hls_motion_yolo_worker_events.py` — `FrameConformanceDetector`
   samples a fixed 8×12 BGR grid of the ORIGINAL frame immediately after read,
   frame increment and receive timestamp (before ROI masking, motion gating,
   inference, crossings, passages, live publication and snapshots).
   - black: per-cell pixel luma stats (mean, within-cell std, pixel max); the
     contrast/bright-pixel veto rejects dark noisy scenes.
   - slate v1: per-column mean BGR with uniform-column check, ordered adjacent
     transitions, saturated-column fraction and black precedence.
   - freeze: one reference grid sample plus monotonic elapsed duration and a
     minimum consecutive-frame count; low-signal scenes are skipped.
   - `build_frame_conformance_state(...)` builds the metadata-only state with no
     `overlay_rev`.
2. Main loop: a non-conforming result posts state on entry and at the normal
   heartbeat cadence, then `continue`s before analytics and all new publications;
   queued events are untouched. Recovery posts `frame_conforming=true` with no
   old reason, and the ordinary heartbeat also carries `frame_conforming=true`
   while the detector is enabled.
3. `worker/worker_transport.py` — `post_state(metadata, overlay_path=None)`
   supports the metadata-only POST. `api/app/main.py` no-overlay state branch
   now merges the incoming payload into the stored row (`data = {**old_state, **data}`),
   so prior analytics fields survive while new conformance fields win; overlay
   bookkeeping and the non-finite scan are preserved.
4. `deploy/worker/ubuntu/worker.env.example` and `road-worker.env.example` —
   identical opt-in semantics and bounded thresholds.

## Decisions

- Pixel-only, no model/reference image: keeps the change inside the worker and
  avoids a second inference dependency; residual night-time risk is documented.
- Per-cell pixel statistics for black, not cell means: the failed first attempt
  proved cell means collapse sensor noise into "uniform black".
- Black > slate > freeze precedence and freeze-run reset on black/slate: a
  repeated slate is never reported frozen.
- Metadata-only state on the existing heartbeat rather than a bare `continue`:
  a bare continue skips the only ordinary heartbeat and would make the worker
  look offline while rejected frames stream.
- Merge, not replace, in the API no-overlay branch: `upsert_camera_state`
  replaces the whole JSON row, so preserving only overlay bookkeeping erased
  detections/tracks/crossings/model_name on every #700 heartbeat.
- Omit `overlay_rev` from rejected-frame metadata: the API then keeps the last
  accepted overlay revision instead of binding the last good image to a rejected
  frame number.
- Reasons loaded from the shared vocabulary by path (`water_passage.py` idiom),
  reusing an already-registered module object and never touching `sys.path`.

## Affected contours

- Contour: MIXED — VPS API + Ubuntu Worker/relay.
- VPS deployment: REQUIRED — `api/app/main.py` now merges a metadata-only state
  heartbeat into the prior camera-state row so #700 heartbeats do not wipe
  analytics fields; no route, schema or overlay-present behavior change.
- Ubuntu worker/relay update: REQUIRED — `worker/**` and the two Ubuntu env
  examples ship with the routine Ubuntu worker release; detector default OFF.
- Windows worker update: NOT APPLICABLE — retired from production.
- Production safety envelope: no new secrets, public exposure, authority or
  runtime mutation while the feature is disabled.

## Validation

Observed locally on this working tree (2026-11-23):

- `python3 -m py_compile worker/hls_motion_yolo_worker_events.py worker/worker_transport.py`
  → `PYCOMPILE_OK`.
- `ruff check --config scripts/quality/ruff.toml worker/hls_motion_yolo_worker_events.py worker/worker_transport.py`
  → `All checks passed!`.
- Scratch smoke (`/tmp/opencode/700-frame-conformance/smoke.py`, stubbed cv2/ultralytics,
  numpy real):
  - true black → `black_frame`;
  - dark random-noise night control → `None` (not black);
  - saturated vertical bars → `slate_frame`;
  - static bright frames, elapsed 10 s / 11 frames → `frozen_frame`;
  - moving frame → `None` with `recovered=True`.
- `python3 scripts/ci/validate_sdd.py` → recorded in tasks.md evidence.
- `git status --short` / `git diff --stat` → recorded in tasks.md evidence.
- `python3 -m pytest tests/test_api_http_integration.py -q` →
  `19 passed, 1 warning, 9 subtests passed`.
- `python3 -m pytest tests/test_700_ingest_frame_conformance.py -q` →
  `2 failed, 18 passed, 1 subtests passed`: both failures are the pre-existing
  working-tree scope guards (`test_working_tree_touches_only_the_700_surface_and_tests`
  and the `api/app/main.py` subfail of `test_no_workflow_lockfile_or_api_change`),
  which still forbid any `api/**` change. All #700 behaviour tests pass.
- `python3 -m pytest tests/ -q` →
  `5 failed, 1720 passed, 2 skipped, 1 warning, 942 subtests passed in 161.36s`.
  The five failures are stale cross-issue working-tree scope guards
  (`test_685_shared_operator_css`, `test_687_single_opencv_wheel`,
  `test_697_typed_unknown_reason`, and the two #700 guards) rejecting the
  required `api/app/main.py` modification. Tests were not edited per the work
  order; the guard update is owned by the test worker/orchestrator.

Automated coverage now exists: `tests/test_700_ingest_frame_conformance.py`
(behaviour tests) and the new
`test_metadata_only_state_post_preserves_prior_analytics_fields` in
`tests/test_api_http_integration.py`. Observed results are recorded in the
Validation section; the full-suite scope-guard conflict caused by the required
`api/app/main.py` working-tree change is reported there and was not "fixed" by
editing tests.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: per-cell pixel luma std/max plus bright-pixel veto; textured night control exercised in smoke | Validation: scratch smoke night control returns None while true black returns black_frame | Residual risk: a genuinely uniform lens-capped/night frame is indistinguishable from black | Owner: worker implementation | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: detector default OFF, bounded thresholds, explicit startup log, state-only diagnostics on rejection | Validation: startup "available but not enabled" path and heartbeat metadata review | Residual risk: operator enables it with an unsuitable threshold on a night camera | Owner: operator enablement | Status: MITIGATED
- RISK-003 | Category: DATA | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: `continue` before analytics/publication and omit `overlay_rev`; queued events are not cleared | Validation: main-loop guard and `post_state(None)` inspection | Residual risk: a false rejection briefly withholds new analytics until recovery | Owner: worker implementation | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: slate v1 is narrowly defined and conservative; unrecognized content is ordinary input | Validation: synthetic slate smoke | Residual risk: broadcast slate variants are not recognized | Owner: worker implementation | Status: ACCEPTED

## Test design

- TEST-700-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: `tests/test_700_ingest_frame_conformance.py::test_flag_off_keeps_the_detector_inactive` — passing in the observed 18-passed behaviour set
- TEST-700-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: `test_zero_frame_is_black` and `test_dark_noisy_night_frame_is_conforming` — passing; the night control is not black
- TEST-700-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: `test_saturated_bars_frame_is_slate`, `test_diagnostic_on_entry_and_reason_change_only_and_recovery`, `test_water_rejects_slate_frame_publications_and_resumes` — passing
- TEST-700-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: `test_repeated_texture_freezes_exactly_at_the_confirm_window`, `test_changing_texture_is_not_frozen`, `test_long_gap_between_different_frames_is_not_frozen` — passing
- TEST-700-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: `test_rejected_state_is_metadata_only_with_typed_reason`, `test_recovery_state_has_no_reason_and_no_overlay_rev`, `test_road_rejects_black_frames_publications_and_resumes` — passing
- TEST-700-006 | Covers: AC-006 | Level: unit | Priority: P0 | Evidence: `test_metadata_only_post_never_opens_a_path_and_sends_no_file_part`, `test_overlay_post_keeps_the_file_part_behaviour` — passing
- TEST-700-007 | Covers: AC-007 | Level: unit | Priority: P1 | Evidence: no dedicated env-content test exists; both `deploy/worker/ubuntu/*.env.example` files were inspected with the identical opt-in block, and `test_working_tree_touches_only_the_700_surface_and_tests` only scopes them as allowed paths
- TEST-700-008 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: `tests/test_api_http_integration.py::test_metadata_only_state_post_preserves_prior_analytics_fields` — 19 passed / 9 subtests in the targeted run; observed py_compile, ruff, validate_sdd and git scope; full-suite stale guard conflict reported in Validation

## Correct-course check

- Trigger: NONE
- Issue impact: Issue #700 defines the outcome; no issue rewrite required.
- Specification impact: New specs/700-ingest-frame-conformance/spec.md authored for this scope.
- Plan impact: This plan; no scope change after admission.
- Tasks impact: Tasks T001-T006 cover code, transport, env examples, SDD and verification.
- Authorization impact: Bounded worker/SDD scope only; no new protected or production authority.
- Follow-up: Stale cross-issue working-tree scope guards must be updated by the test worker to allow the authorized `api/app/main.py` fix; field observation before enabling remains follow-up, not a scope change.

## Runtime feedback

- Runtime acceptance: PENDING — feature ships disabled by default; no production enablement.
- Accepted production behavior: unchanged while disabled; when enabled, rejected frames yield state-only diagnostics.
- Regressions/learning: cell-mean-only black detection was rejected after the smoke night control; the repaired per-cell statistic is the accepted design.
- Follow-up work: stale scope-guard refresh in tests (not edited here); night-time false-positive rate to be observed before remote enablement.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged working tree and branch | Retry: NO | Rollback: NONE | Evidence: work order for Issue #700 on branch agent/wave8-697-700; allowed paths are the two worker .py files, two Ubuntu env examples and specs/700-ingest-frame-conformance/**; base_sha ordered as edd26a49 is absent locally, effective base is branch HEAD de883e83
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: repository still on the previous worker release | Retry: NO | Rollback: NONE | Evidence: py_compile + ruff on both changed .py files; detector enabled flag defaults to 0 so the existing worker behavior is unchanged at startup; no secrets, credentials or public exposure added
- TX-003 | Stage: MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: staged release discarded; running worker services unchanged | Retry: NO | Rollback: routine Ubuntu worker release rollback to the previous complete release via rollback-exact.sh | Evidence: worker source and env examples are installed by the existing Ubuntu worker release path; the change is code-only with no installer or systemd unit change
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release remains active | Retry: NO | Rollback: NONE | Evidence: existing post-deploy worker health gate (verify-runtime-progression.py / check-worker-health.py) applies unchanged; local verification observed py_compile OK, ruff passed, validate_sdd result recorded in tasks.md
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker state store | Retry: NO | Rollback: NONE | Evidence: rejected-frame state POST is additive metadata; API merges previous overlay_rev/last_overlay_url when overlay is None; no schema or database change
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: temporary scratch only in /tmp/opencode, no repository residue | Retry: NO | Rollback: NONE | Evidence: all scratch artifacts live under /tmp/opencode/700-frame-conformance; no progress or cache file added to the repository
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial but no runtime effect | Retry: NO | Rollback: NONE | Evidence: observed API test run 19 passed/9 subtests; #700 behaviour tests 18 passed; full-suite stale scope-guard conflict recorded in Validation and not represented as green
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: revert the bounded PR or roll the Ubuntu worker back to the previous complete release; because the feature is default OFF, runtime impact while disabled is none | Evidence: diff limited to allowed paths; detector disable path is a pass-through with no frame_conforming claim
