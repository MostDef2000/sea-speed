# Tasks: Ingest frame conformance (black / slate / freeze)

- Feature: 700-ingest-frame-conformance
- Specification: specs/700-ingest-frame-conformance/spec.md
- Plan: specs/700-ingest-frame-conformance/plan.md
- Issue: #700
- Status: Source implementation

## Delivery tasks

- [x] T001 Add `FrameConformanceDetector` (grid sampling, black/slate/freeze, bounded env thresholds, typed transitions) to `worker/hls_motion_yolo_worker_events.py`.
- [x] T002 Gate the worker main loop: metadata-only state on confirmed rejection, skip analytics/new publications, recovery without the old reason.
- [x] T003 Add metadata-only `post_state(metadata, None)` support to `worker/worker_transport.py`.
- [x] T004 Document the opt-in, bounded thresholds in `deploy/worker/ubuntu/worker.env.example` and `road-worker.env.example`.
- [x] T005 Author the SDD trio under `specs/700-ingest-frame-conformance/`.
- [ ] T006 Record required CI and exact-green-head merge evidence after the bounded PR is opened by the orchestrator.
- [ ] T007 Record test-worker unit/integration evidence under `tests/**` (separate worker owns tests; PENDING here).

## Requirements traceability

- AC-001 | Task: T001, T002 | Evidence: `FrameConformanceDetector.__init__`/`log_startup` default-off path and `evaluate` pass-through; startup log line observed in smoke | Coverage: COVERED
- AC-002 | Task: T001 | Evidence: per-cell pixel luma std/max black rule; scratch smoke true black -> black_frame and dark noise -> None | Coverage: COVERED
- AC-003 | Task: T001 | Evidence: `_slate_detail` uniform-column/transition/saturation rules and black-first ordering; scratch smoke bars -> slate_frame | Coverage: COVERED
- AC-004 | Task: T001 | Evidence: `_update_freeze` elapsed + min-frames + low-signal exclusion; scratch smoke frozen at 10 s/11 frames | Coverage: COVERED
- AC-005 | Task: T002 | Evidence: main-loop metadata-only state + `continue` before ROI/analytics/publications; queued state untouched | Coverage: COVERED
- AC-006 | Task: T003 | Evidence: `post_state(metadata, None)` branch posts without opening a file; rejected metadata omits overlay_rev; scratch `requests.post` stub observed no `files` field | Coverage: COVERED
- AC-007 | Task: T004 | Evidence: both env examples carry the same `FRAME_CONFORMANCE_*` opt-in block | Coverage: COVERED
- AC-008 | Task: T005, T006 | Evidence: observed py_compile, ruff, validate_sdd and git scope outputs in the Evidence section; CI/merge PENDING | Coverage: COVERED

## Completion gate

- [x] Exact scope verified against Issue #700 allowed paths
- [x] SDD artifacts current
- [x] Local static verification observed (py_compile, ruff, validate_sdd)
- [ ] Required CI green on exact head
- [ ] Exact-green-head merge complete
- [ ] Test-worker tests/** evidence recorded

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [ ] Required tests and evidence complete (test-worker tests/** PENDING)
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [x] Deployment state resolved (Ubuntu worker release path unchanged; feature default OFF)
- [x] Runtime acceptance resolved (PENDING by design — no production enablement in this scope)
- [x] Deferred work recorded (test-worker coverage and field night observation)
- [x] Risks resolved or explicitly accepted (NFR-006 / RISK-001..004)
- [x] Waivers resolved or current (none required)

## Evidence

Observed on this working tree (2026-11-23), no fabricated results:

- `python3 -m py_compile worker/hls_motion_yolo_worker_events.py worker/worker_transport.py`
  → `PYCOMPILE_OK`.
- `ruff check --config scripts/quality/ruff.toml worker/hls_motion_yolo_worker_events.py worker/worker_transport.py`
  → `All checks passed!`.
- Scratch smoke `/tmp/opencode/700-frame-conformance/smoke.py` (real numpy, stubbed cv2/ultralytics because the local env lacks them):
  - true black → `black_frame`;
  - dark random-noise night control → `None`;
  - saturated vertical bars → `slate_frame`;
  - static bright frames across 10 s / 11 frames → `frozen_frame`;
  - moving frame → `None` with `recovered=True`.
- Metadata-only transport scratch check (`post_state(..., None)` with a stubbed
  `requests.post`) → `metadata_only_post_files_absent: True` (no `files` field,
  no file open).
- `python3 scripts/ci/validate_sdd.py` → `Sea Speed SDD validation passed` (exit 0).
- Feature quality-format harness (local, `validate_feature_quality` with a
  `- Risk profile: REQUIRED` PR body and the changed worker/deploy files) →
  `QUALITY_VALIDATION_PASSED`.
- `git status --short` → modified `deploy/worker/ubuntu/road-worker.env.example`,
  `deploy/worker/ubuntu/worker.env.example`,
  `worker/hls_motion_yolo_worker_events.py`,
  `worker/worker_transport.py`; untracked `specs/700-ingest-frame-conformance/`.
- `git diff --stat` → 4 files changed, 379 insertions(+), 6 deletions(-):
  `road-worker.env.example` +18/−0, `worker.env.example` +19/−1,
  `hls_motion_yolo_worker_events.py` +331/−0, `worker_transport.py` +11/−5;
  the SDD directory is new and therefore untracked in this stat.
- Test-worker unit/integration evidence under `tests/**`: PENDING — owned by a separate worker; this task did not edit tests.
