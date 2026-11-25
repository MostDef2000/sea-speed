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
- [x] T006 Add the API no-overlay merge and the conforming-recovery transient-key clearing in `api/app/main.py`.
- [x] T007 Record required CI and exact-green-head merge evidence after the bounded PR is opened by the orchestrator. — auto-synced on merge to main (172e938b)
- [x] T008 Record test-worker unit/integration evidence under `tests/**` (recovery clear test included).

## Requirements traceability

- AC-001 | Task: T001, T002 | Evidence: `FrameConformanceDetector.__init__`/`log_startup` default-off path and `evaluate` pass-through; startup log line observed in smoke | Coverage: COVERED
- AC-002 | Task: T001 | Evidence: per-cell pixel luma std/max black rule; scratch smoke true black -> black_frame and dark noise -> None | Coverage: COVERED
- AC-003 | Task: T001 | Evidence: `_slate_detail` uniform-column/transition/saturation rules and black-first ordering; scratch smoke bars -> slate_frame | Coverage: COVERED
- AC-004 | Task: T001 | Evidence: `_update_freeze` elapsed + min-frames + low-signal exclusion; scratch smoke frozen at 10 s/11 frames | Coverage: COVERED
- AC-005 | Task: T002, T006 | Evidence: main-loop metadata-only state + `continue` before ROI/analytics/publications; queued state untouched; `test_recovery_state_carries_no_stale_unknown_reason` covers recovery clearing | Coverage: COVERED
- AC-006 | Task: T003, T006 | Evidence: `post_state(metadata, None)` posts without opening a file; rejected metadata omits overlay_rev; state merge preserves prior analytics; `test_metadata_only_state_post_preserves_prior_analytics_fields` passing | Coverage: COVERED
- AC-007 | Task: T004 | Evidence: both env examples carry the same `FRAME_CONFORMANCE_*` opt-in block | Coverage: COVERED
- AC-008 | Task: T005, T008 | Evidence: observed targeted API suite 20 passed/9 subtests, clean-tree full suite 1725 passed/2 skipped/939 subtests/0 failed, py_compile, ruff and validate_sdd; CI/merge PENDING | Coverage: COVERED

## Completion gate

- [x] Exact scope verified against Issue #700 allowed paths
- [x] SDD artifacts current
- [x] Local static verification observed (py_compile, ruff, validate_sdd)
- [x] Required CI green on exact head — auto-synced on merge to main (172e938b)
- [x] Exact-green-head merge complete — auto-synced on merge to main (172e938b)
- [x] Test-worker tests/** evidence recorded (targeted 20 passed/9 subtests; clean-tree full suite 1725 passed/2 skipped/939 subtests/0 failed)

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (targeted 20 passed/9 subtests; clean-tree full suite 1725 passed/2 skipped/939 subtests/0 failed)
- [x] Required CI green — auto-synced on merge to main (172e938b)
- [x] Exact-green-head merge complete — auto-synced on merge to main (172e938b)
- [x] Deployment state resolved (MIXED: VPS API state merge + Ubuntu worker release path; feature default OFF)
- [x] Runtime acceptance resolved (PENDING by design — no production enablement in this scope)
- [x] Deferred work recorded (field night observation; required CI and merge evidence)
- [x] Risks resolved or explicitly accepted (NFR-006 / RISK-001..004)
- [x] Waivers resolved or current (none required)

## Evidence

Observed on this working tree (2026-11-23), no fabricated results:

- `python3 -m py_compile api/app/main.py` → `PYCOMPILE_OK`.
- `python3 -m ruff check --config scripts/quality/ruff.toml api/app/main.py`
  → `All checks passed!`.
- `python3 -m pytest tests/test_api_http_integration.py -q` →
  `20 passed, 1 warning, 9 subtests passed`, including
  `test_metadata_only_state_post_preserves_prior_analytics_fields` and
  `test_recovery_state_carries_no_stale_unknown_reason`.
- Post-commit clean-tree `python3 -m pytest tests/ -q` (delivery-orchestrator
  observed) → `1725 passed, 2 skipped, 939 subtests, 0 failed` (the earlier
  1724-passed clean-tree baseline plus the new recovery test).
- Scratch smoke `/tmp/opencode/700-frame-conformance/smoke.py` (real numpy,
  stubbed cv2/ultralytics because the local env lacks them):
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
  `- Risk profile: REQUIRED` PR body and the changed API/worker/deploy files) →
  `QUALITY_VALIDATION_PASSED`.
- This worker changed only `api/app/main.py` and
  `specs/700-ingest-frame-conformance/{spec,plan,tasks}.md`; the RED test in
  `tests/test_api_http_integration.py` was pre-existing and was not edited here.
