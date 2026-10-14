# Tasks: wave-6 worker crossings — crossing-domain cluster extraction (move-only)

- Issue: #397
- Specification: specs/397-wave6-worker-crossings/spec.md

## Delivery tasks

- T-397-W6-001: RECON the cut from live source at main 854b08f (per work order): verify the ONE contiguous region 544-664 (state literals 544-548: _crossing_track_sides/_crossing_counts/_crossings_by_class/VLZ_TIMEZONE/_crossing_vlz_date; defs 551-554 vlz_date, 557-562 reset_crossing_counts, 565-573 maybe_reset_daily_crossings, 576-583 prune_crossing_tracks, 586-646 update_crossing_counts, 649-662 crossing_overlay_summary; trailing blank pair 663-664); map the access graph (zero staying readers of the 5 state names; _crossing_vlz_date's sole rebinder maybe_reset_daily_crossings at :567 with the only ast.Global; transport-owned _crossing_line_cache/_crossing_pending_posts/fetch_crossing_line_config used in place; staying callers update_crossing_counts :1016 + crossing_overlay_summary :139 globals()-guard/:1139); verify the recorded STAYS with forced reasons (ROI family _roi_processing_points rebinds :349 + cv2/numpy; live-publisher threading/queue + _LIVE_PUBLISH_THREAD rebinds :459/462; _line_speed_state + update_speed_lines_estimate; detect_vehicles/track/event/main); verify datetime becomes dead in the worker after the cut (sole uses :7/:547/:554/:641) and json stays (:437)
- T-397-W6-002: Execute the verbatim move with an assertion-guarded script: extract region 544-664 byte-exactly, cut it in the worker with the trailing blank pair (two-blank separators close), remove the dead `from datetime import ...` (:7), insert the wave-6 comment block + `from worker_crossings import (  # noqa: F401` + 6 sorted def names after the worker_transport re-export block (block and 15 names UNCHANGED) and before first use; create worker/worker_crossings.py (header docstring: wave-6 of #397, verbatim extraction, object-identity coupling with worker_transport, _crossing_vlz_date moves WITH its sole rebinder; imports EXACTLY time/datetime/worker_kernel/worker_transport; then state literals + 6 defs in source order, NOTHING else); verify: byte-segment equality vs git show 854b08f (True), ast.dump equality ×11 (True ×11), moved names gone from worker, exactly one worker_crossings ImportFrom with the exact 6-name alias set, transport ImportFrom unchanged (15 aliases), zero remaining datetime references, import json untouched, py_compile the three worker modules; record line arithmetic (worker 1259→1155; crossings 156 = 37 header+imports + 119 region)
- T-397-W6-003: Convergence/gate (fail-closed, same commit): scripts/worker/check_ubuntu_compatibility.py MODULE_SOURCES 4→5 (REQUIRED_ENV_NAMES unchanged); scripts/ci/validate_repo.py REQUIRED_FILES += worker/worker_crossings.py; scripts/quality/build_exact_artifacts.py ubuntu-worker (:19) AND edge (:20) += worker/worker_crossings.py; scripts/quality/validate_exact_artifacts.py ubuntu-worker (:11) AND edge (:12) += worker/worker_crossings.py; deploy/worker/ubuntu/install-systemd.sh prepared-release required loop (:54-66) += worker/worker_crossings.py; scripts/ci/validate_sdd.py GRANDFATHERED_PREFIX_COLLISIONS "397" set += 397-wave6-worker-crossings
- T-397-W6-004: Test pin transfers (contract transfers, not weakenings): tests/test_worker_transport_module.py — gate count 4→5 with wave-6 message, STAYING_IN_WORKER loses update_crossing_counts/reset_crossing_counts/crossing_overlay_summary (MOVED_* tuples unchanged; 15 names stay), no-rebinding scan extended to the crossings file (documented choice: the loop's purpose is scanning where moved-cache names may appear — crossings now hosts the .append/.clear mutators); tests/test_worker_render_module.py — STAYING_IN_WORKER loses crossing_overlay_summary, docstring gains the wave-6 transfer note; tests/support/worker_source.py — DEFAULT_WORKER_SOURCES 5→6 (docstring "five"→"six"); tests/test_line_crossing.py — NO edits (verified green unedited)
- T-397-W6-005: Write NEW tests/test_worker_crossings_module.py mirroring the transport test's structure: (a) import-allowlist pin ⊆ {time, datetime, worker_kernel, worker_transport} + forbidden offline-layers absent; (b) placement — 6 defs + 5 state literals defined ONLY in worker_crossings, worker top-level defs clean, re-export exact set (6 defs, state NOT re-exported), transport block unchanged (15); (c) strict no-rebinding guard across ALL worker/*.py for _crossing_counts/_crossings_by_class/_crossing_track_sides/VLZ_TIMEZONE; (d) rebinder-coupling pin for _crossing_vlz_date (exactly ONE Assign beyond the literal; enclosing FunctionDef maybe_reset_daily_crossings; only ast.Global in that def; both top-level in worker_crossings); (e) identity + globals-guard regression (pristine subprocess probe: worker.<def> IS worker_crossings.<def> ×6 + "crossing_overlay_summary" in vars(worker); in-process identity; AST pin of the membership guard in build_road_live_envelope); (f) gate test — MODULE_SOURCES == 5, union compatible, required env complete
- T-397-W6-006: Write the SDD trio specs/397-wave6-worker-crossings/ per the wave-5 validated house format (spec: Product outcome with STAYS + forced reasons, US-1..6, Scope, R-1..7, AC-1..7, Runtime feedback, NFR-1..4; plan: Implementation approach, Architecture, Decisions D-1..8, `- Risk profile: REQUIRED` + RISK-001..006 ranked + TEST-001..008 + Correct-course + Affected contours + Validation + TX-001..008 deployment transaction audit — deployable file list changes, VPS deployment NOT REQUIRED, Ubuntu worker/relay update REQUIRED, production safety envelope REQUIRED; tasks: DoD markers in the house format with the 4 orchestrator-owned markers UNCHECKED); run the verification battery and record observed output: full pytest battery; focused suites; ruff CI-config; validate_repo; validate_sdd; gate CLI (five-file union, compatible=True, required env complete); py_compile; byte/AST proof + line arithmetic; NO push (orchestrator-owned)

## Completion gate

- [x] T-397-W6-001
- [x] T-397-W6-002
- [x] T-397-W6-003
- [x] T-397-W6-004
- [x] T-397-W6-005
- [x] T-397-W6-006
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (worker/hls_motion_yolo_worker_events.py, worker/worker_crossings.py, scripts/worker/check_ubuntu_compatibility.py, scripts/ci/validate_repo.py, scripts/ci/validate_sdd.py, scripts/quality/build_exact_artifacts.py, scripts/quality/validate_exact_artifacts.py, deploy/worker/ubuntu/install-systemd.sh, tests/support/worker_source.py, tests/test_worker_transport_module.py, tests/test_worker_render_module.py, tests/test_worker_crossings_module.py, specs/397-wave6-worker-crossings/**; tests/test_line_crossing.py verified NO change needed; durable progress file OUTSIDE the git tree)
- [x] Required tests and evidence complete (transcripts in the durable progress file; worker-recorded; commit/PR/merge orchestrator-owned)

## Requirements traceability

- AC-001 | Task: T-397-W6-001, T-397-W6-002 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T-397-W6-002, T-397-W6-004, T-397-W6-005 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-397-W6-002, T-397-W6-005 | Evidence: TEST-003 | Coverage: COVERED
- AC-004 | Task: T-397-W6-002, T-397-W6-005 | Evidence: TEST-001, TEST-002 | Coverage: COVERED
- AC-005 | Task: T-397-W6-003, T-397-W6-005 | Evidence: TEST-005, TEST-008 | Coverage: COVERED
- AC-006 | Task: T-397-W6-004, T-397-W6-006 | Evidence: TEST-005, TEST-006, TEST-007, TEST-008 | Coverage: COVERED
- AC-007 | Task: T-397-W6-003, T-397-W6-006 | Evidence: TEST-007 | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — rides the next routine Ubuntu-worker deploy (DEPLOY-TRIGGER, полоса A) — orchestrator-owned
- [ ] Runtime acceptance resolved — health gate probe on the next worker deploy — orchestrator-owned
- [x] Deferred work recorded — ROI family (_roi_processing_points rebinds + cv2/numpy callees), live-publisher family (threading/queue + _LIVE_PUBLISH_THREAD rebinds), _line_speed_state + update_speed_lines_estimate (sole consumer stays), detect_vehicles/track/event/main loop remain in the worker, recorded in spec/plan; remaining analytics/ROI + MotionDetector/main consolidation → later waves
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-006 mitigated in plan.md
- [x] Waivers resolved or current — none
