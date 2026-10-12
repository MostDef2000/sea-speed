# Tasks: Camera preview/snapshot extraction — api/app/camera_preview.py (Wave 4)

- Specification: specs/396-wave4-camera-preview/spec.md

## Delivery tasks

- T001: Extract `api/app/camera_preview.py` (15 functions:
  validate_camera_preview_source, load_camera_preview_catalog,
  camera_snapshot_path, camera_snapshot_public_metadata,
  build_camera_snapshot_extract_args, camera_snapshot_luma_spread,
  camera_snapshot_candidate_is_usable, commit_camera_snapshot_locked,
  camera_preview_public_state, camera_preview_pid_matches,
  cleanup_camera_preview_media, terminate_camera_preview_locked,
  active_camera_preview_locked, build_camera_preview_ffmpeg_args,
  start_camera_preview_locked) from `api/app/main.py` by scripted
  byte-range copy; rewrite main.py with the wave-4 seam (explicit
  re-exports, dual idiom) and the dropped `import ipaddress` / `import re`
  / `import signal` / `import subprocess` /
  `from urllib.parse import urlsplit` (no behavior change, routes and
  `CAMERA_PREVIEW_LOCK` acquisition points untouched; no mutable state
  moves — plan D-1/D-2)
- T002: Extend the gallery source walk in
  `tests/test_camera_preview_gallery.py` to join `camera_preview.py` right
  after `main.py` (definitions/markers resolve from the owning module,
  no assertion weakened); add `api/app/camera_preview.py` to the synthetic
  releases in `tests/test_vps_deploy_transaction.py`; verify by grep that
  no other reader references a moved name
- T003: Extend `deploy/vps/deploy.sh` through all seven wave-1/2/3 pattern
  sites (target var, release_complete, download required list, release
  install, bootstrap capture, install staging, activation before main.py)
  and converge `scripts/quality/build_exact_artifacts.py` (vps required
  list gains `api/app/camera_preview.py`)
- T004: Grandfather `396-wave4-camera-preview` in
  `scripts/ci/validate_sdd.py` (GRANDFATHERED_PREFIX_COLLISIONS, one
  entry) and add the SDD trio
  `specs/396-wave4-camera-preview/{spec,plan,tasks}.md` (Risk REQUIRED;
  RISK/TEST rows; TX-001..008; DoD) — this directory
- T005: Run the verification battery — full unittest suite (baseline 908/4,
  expected 908/4), `python3 scripts/ci/validate_repo.py`,
  `python3 scripts/ci/validate_sdd.py`, ruff
  (`scripts/quality/ruff.toml`), `bash -n deploy/vps/deploy.sh`,
  byte-identity audit of the 287-line moved region vs the base commit,
  route-table 61==61 with handler names, import-mode smoke (package +
  direct-file + lock singleton) — and commit on the wave branch (no push)

## Requirements traceability

- AC-001 | Task: T005 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T004, T005 | Evidence: TEST-004 | Coverage: COVERED
- AC-003 | Task: T003 | Evidence: TEST-002, TEST-003 | Coverage: COVERED
- AC-004 | Task: T001, T002 | Evidence: TEST-005, TEST-006 | Coverage: COVERED
- AC-005 | Task: T001 | Evidence: TEST-007 | Coverage: COVERED
- AC-006 | Task: T001, T003 | Evidence: TEST-005 | Coverage: COVERED
- AC-007 | Task: T003, T005 | Evidence: TEST-004 | Coverage: COVERED

## Completion gate

- [x] T001
- [x] T002
- [x] T003
- [x] T004
- [x] T005
- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [ ] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] Deployment state resolved — rides the VPS deploy of this wave (DEPLOY-TRIGGER, полоса A) — orchestrator-owned
- [ ] Runtime acceptance resolved — health gate probe on the VPS deploy — orchestrator-owned
- [ ] Deferred work recorded — none
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-006 mitigated in plan.md
- [ ] Waivers resolved or current — none

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [ ] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] Deployment state resolved — rides the VPS deploy of this wave (DEPLOY-TRIGGER, полоса A) — orchestrator-owned
- [ ] Runtime acceptance resolved — health gate probe on the VPS deploy — orchestrator-owned
- [ ] Deferred work recorded — none
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-006 mitigated in plan.md
- [ ] Waivers resolved or current — none
