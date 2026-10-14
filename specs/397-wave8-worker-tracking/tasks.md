# Tasks: wave-8 worker tracking — tracking-cluster extraction (move-only)

- Issue: #397
- Specification: specs/397-wave8-worker-tracking/spec.md

## Delivery tasks

- T-397-W8-001: RECON the cut from live source at main f9d4f37 (per work order): verify the ONE contiguous region 479-739 — state literals _speed_track/_track_states (479-480), def block detection_center_px/update_speed_estimate/convert_px_s_to_kmh (483-529), _line_speed_state literal (532), update_speed_lines_estimate (535-699, nested helpers median_value/update_sample_metadata/apply_held_speed/valid_line/midpoint/progress_m_from_calibration inside), track_event_posted/mark_track_event_posted/water_event_candidates/prune_track_states (702-739); map the access graph (main loop reads update_speed_estimate/update_speed_lines_estimate/convert_px_s_to_kmh/prune_track_states/water_event_candidates/track_event_posted/mark_track_event_posted flat; staying build_event calls convert_px_s_to_kmh; draw_speed_lines_overlay 742-753 calls ONLY fetch_speed_lines_config + cv2 — ZERO moved names; zero entrypoint/runtime/deploy/scripts uses; zero staying worker-namespace readers of the 3 state names outside the moved defs); ENV AUDIT: zero REQUIRED_ENV_NAMES reads in the moved region (only env_float DETECTION_* tunables) → test_worker_media_module.py needs NO change; verify the recorded STAYS with forced reasons (ROI family _roi_processing_points rebinds + cv2/numpy; draw_speed_lines_overlay render surface; detect_vehicles/build_event/build_*_live_envelope/MotionDetector/main); verify all 3 state names are strictly non-rebinding (only Store access = defining literals) and zero `global` statements name the moved names
- T-397-W8-002: Execute the verbatim move with an assertion-guarded script: extract region 479-739 byte-exactly, cut it in the worker with the trailing blank pair (two-blank separator closes), insert the wave-8 comment block + `from worker_tracking import (  # noqa: F401` + 11 sorted names after the wave-7 worker_live re-export block (transport 15-name, crossings 6-name and live 6-name blocks UNCHANGED) and before first use (EOF no-newline preserved); create worker/worker_tracking.py (header docstring: wave-8 of #397, verbatim extraction, object-identity coupling, import policy; imports EXACTLY time/worker_kernel.env_float/worker_transport.fetch_speed_config+fetch_speed_lines_config; then 3 state literals + 8 defs in source order, NOTHING else); verify: byte-segment equality vs git show f9d4f37 for the moved region AND staying regions 1-136/138-478/742-1129 (True), ast.dump equality ×11 (True), moved names gone from worker, exactly one worker_tracking ImportFrom with the exact 11-name alias set, transport/crossings/live ImportFrom unchanged (15/6/6 aliases), zero globals naming moved names, py_compile the worker modules; record line arithmetic (worker 1129→889 content lines, numstat +24/−264; worker_tracking 296)
- T-397-W8-003: Convergence/gate (fail-closed, same commit): scripts/worker/check_ubuntu_compatibility.py MODULE_SOURCES 6→7 (REQUIRED_ENV_NAMES unchanged); scripts/ci/validate_repo.py REQUIRED_FILES += worker/worker_tracking.py; scripts/quality/build_exact_artifacts.py ubuntu-worker AND edge += worker/worker_tracking.py; scripts/quality/validate_exact_artifacts.py ubuntu-worker AND edge += worker/worker_tracking.py; deploy/worker/ubuntu/install-systemd.sh prepared-release required loop += worker/worker_tracking.py; scripts/ci/validate_sdd.py GRANDFATHERED_PREFIX_COLLISIONS "397" set += 397-wave8-worker-tracking
- T-397-W8-004: Test pin transfers (contract transfers, not weakenings): tests/test_worker_transport_module.py — gate count 6→7 with wave-8 message; tests/test_worker_crossings_module.py — docstring gate note six→seven-file union, gate pin 6→7 with wave-8 transfer comment; tests/test_worker_live_module.py — docstring gate note six→seven-file union, gate pin 6→7 with wave-8 transfer comment; tests/support/worker_source.py — DEFAULT_WORKER_SOURCES 7→8 (wave-8 docstring note); NO STAYING_IN_WORKER transfers (the moved names are in NEITHER the media nor the render STAYS lists); test_worker_media_module.py verified UNTOUCHED (env audit held — battery green); harness-consumer tests verified NO edits needed (exec-injection location-independent)
- T-397-W8-005: Write NEW tests/test_worker_tracking_module.py mirroring the live-module test's structure/idioms: (a) import-allowlist pin ⊆ {time, worker_kernel, worker_transport} (double-armed: all three REQUIRED) + forbidden set absent (cv2/numpy/datetime/threading/queue/ultralytics/av/subprocess/socket/requests/json/pathlib/os — derived from the actual moved bodies and documented); (b) placement — 8 defs + 3 state literals defined ONLY in worker_tracking (no duplicates in worker/transport/crossings/live), re-export exact set (11 names), transport block unchanged (15), crossings block unchanged (6), live block unchanged (6); (c) strict no-rebinding guard across ALL worker/*.py for _speed_track/_track_states/_line_speed_state + no `global` statement anywhere naming any of the 11 moved names; (d) identity + re-export regression (pristine subprocess probe: worker.<name> IS worker_tracking.<name> ×11 + "_speed_track"/"_track_states"/"_line_speed_state" in vars(worker); in-process identity; staying tracking call-site pin); (e) gate test — MODULE_SOURCES == 7 with worker_tracking.py present, union compatible, required env complete; (f) draw_speed_lines_overlay placement pin — def present in the worker, absent from worker_tracking
- T-397-W8-006: Write the SDD trio specs/397-wave8-worker-tracking/ per the wave-7 validated house format (spec: Product outcome with STAYS + forced reasons, US-1..6, Scope, R-1..7, AC-1..7, Runtime feedback, NFR-1..4; plan: Implementation approach, Architecture, Decisions D-1..8, `- Risk profile: REQUIRED` + RISK-001..007 ranked + TEST-001..008 + Correct-course + Affected contours + Validation + TX-001..008 deployment transaction audit — deployable file list changes, VPS deployment NOT REQUIRED, Ubuntu worker/relay update REQUIRED, production safety envelope REQUIRED; tasks: DoD markers in the house format, UNCHECKED until the post-merge auto-sync); run the verification battery and record observed output: full pytest battery; ruff CI-config; validate_repo; validate_sdd; gate CLI (seven-file union, compatible: true, required env complete); install-systemd.sh bash -n; py_compile worker/*.py; byte/AST proof + line arithmetic; git diff origin/main --stat scope check; NO push (orchestrator-owned)

## Completion gate

- [ ] T-397-W8-001
- [ ] T-397-W8-002
- [ ] T-397-W8-003
- [ ] T-397-W8-004
- [ ] T-397-W8-005
- [ ] T-397-W8-006
- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete

## Requirements traceability

- AC-001 | Task: T-397-W8-001, T-397-W8-002 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T-397-W8-002, T-397-W8-004, T-397-W8-005 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-397-W8-002, T-397-W8-005 | Evidence: TEST-003 | Coverage: COVERED
- AC-004 | Task: T-397-W8-002, T-397-W8-005 | Evidence: TEST-001, TEST-002 | Coverage: COVERED
- AC-005 | Task: T-397-W8-003, T-397-W8-005 | Evidence: TEST-005, TEST-008 | Coverage: COVERED
- AC-006 | Task: T-397-W8-004, T-397-W8-006 | Evidence: TEST-005, TEST-006, TEST-007, TEST-008 | Coverage: COVERED
- AC-007 | Task: T-397-W8-003, T-397-W8-006 | Evidence: TEST-007 | Coverage: COVERED

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [ ] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] Deployment state resolved — rides the next routine Ubuntu-worker deploy (DEPLOY-TRIGGER, полоса A) — orchestrator-owned
- [ ] Runtime acceptance resolved — health gate probe on the next worker deploy — orchestrator-owned
- [ ] Deferred work recorded — ROI family (_roi_processing_points rebinds + cv2/numpy callees), draw_speed_lines_overlay (render surface, pinned placement), detect_vehicles/build_event/build_*_live_envelope/MotionDetector/main loop remain in the worker, recorded in spec/plan; remaining analytics/ROI + MotionDetector/main consolidation → later waves
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-007 mitigated in plan.md
- [ ] Waivers resolved or current — none
