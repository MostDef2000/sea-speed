# Tasks: wave-7 worker live — live-publisher family extraction (move-only)

- Issue: #397
- Specification: specs/397-wave7-worker-live/spec.md

## Delivery tasks

- T-397-W7-001: RECON the cut from live source at main 20657e7 (per work order): verify the TWO regions — state literals 127-129 (_LIVE_PUBLISH_QUEUE/_LIVE_PUBLISH_LOCK/_LIVE_PUBLISH_THREAD) between `_LAST_FRAME_CAPTURE_MS` (:126, stays) and `_WATER_RECALL_DIAGNOSTIC_STATE` (:130, stays); def region 466-502 (_live_publisher_loop 466-472, _ensure_live_publisher 475-484 with the global stmt :476 and rebinding assign :479-484, post_live_envelope 487-502) between draw_roi_polygon and _speed_track; map the access graph (_post_live_envelope_sync transport-owned since wave 5; zero staying readers of the queue/lock state in the worker body; _LIVE_PUBLISH_THREAD's sole rebinder _ensure_live_publisher with the only ast.Global; staying callers post_live_envelope :977/:1005 post-cut); verify the recorded STAYS with forced reasons (ROI family _roi_processing_points rebinds + cv2/numpy; _line_speed_state + update_speed_lines_estimate; detect_vehicles/track/event/main); verify queue/threading become dead in the worker after the cut (sole uses :3-4/:127-129/:466-502)
- T-397-W7-002: Execute the verbatim move with an assertion-guarded script: extract regions 127-129 and 466-502 byte-exactly, cut them in the worker with the trailing blank pairs (two-blank separators close), remove the dead `import queue`/`import threading` (:3-4), insert the wave-7 comment block + `from worker_live import (  # noqa: F401` + 6 sorted names after the worker_crossings re-export block (transport 15-name and crossings 6-name blocks UNCHANGED) and before first use; create worker/worker_live.py (header docstring: wave-7 of #397, verbatim extraction, thread-lifecycle ownership, object-identity coupling, _LIVE_PUBLISH_THREAD moves WITH its sole rebinder; imports EXACTLY queue/threading/worker_kernel/worker_transport; then state literals + 3 defs in source order, NOTHING else); verify: byte-segment equality vs git show 20657e7 (True ×2), ast.dump equality ×3 (True ×3), moved names gone from worker, exactly one worker_live ImportFrom with the exact 6-name alias set, transport ImportFrom unchanged (15 aliases), crossings ImportFrom unchanged (6 aliases), zero remaining queue/threading references, py_compile the worker modules; record line arithmetic (worker 1155→1129; worker_live 78)
- T-397-W7-003: Convergence/gate (fail-closed, same commit): scripts/worker/check_ubuntu_compatibility.py MODULE_SOURCES 5→6 (REQUIRED_ENV_NAMES unchanged); scripts/ci/validate_repo.py REQUIRED_FILES += worker/worker_live.py; scripts/quality/build_exact_artifacts.py ubuntu-worker AND edge += worker/worker_live.py; scripts/quality/validate_exact_artifacts.py ubuntu-worker AND edge += worker/worker_live.py; deploy/worker/ubuntu/install-systemd.sh prepared-release required loop += worker/worker_live.py; scripts/ci/validate_sdd.py GRANDFATHERED_PREFIX_COLLISIONS "397" set += 397-wave7-worker-live
- T-397-W7-004: Test pin transfers (contract transfers, not weakenings): tests/test_worker_transport_module.py — STAYING_IN_WORKER loses _ensure_live_publisher (wave-7 transfer note; MOVED_* tuples unchanged; 15 names stay), gate count 5→6 with wave-7 message, gate test class renamed CompatibilityGateFourFileTests/test_gate_scans_four_worker_sources → CompatibilityGateModuleSourcesTests/test_gate_scans_module_sources (stale wave-4 name hygiene, no semantic change); tests/test_worker_crossings_module.py — docstring gate note five→six-file union, gate pin 5→6 with wave-7 transfer comment; tests/support/worker_source.py — DEFAULT_WORKER_SOURCES 6→7 (wave-7 docstring note); harness-consumer tests verified NO edits needed (exec-injection location-independent)
- T-397-W7-005: Write NEW tests/test_worker_live_module.py mirroring the crossings test's structure/idioms: (a) import-allowlist pin ⊆ {queue, threading, worker_kernel, worker_transport} + forbidden offline-layers absent (cv2/numpy/datetime/ultralytics/av/subprocess/socket/requests/json/pathlib/os); (b) placement — 3 defs + 3 state literals defined ONLY in worker_live (no duplicates in worker/transport/crossings; _post_live_envelope_sync stays transport-owned), re-export exact set (6 names), transport block unchanged (15), crossings block unchanged (6); (c) strict no-rebinding guard across ALL worker/*.py for _LIVE_PUBLISH_QUEUE/_LIVE_PUBLISH_LOCK + no `global` statement anywhere naming them or the moved defs; (d) rebinder-coupling pin for _LIVE_PUBLISH_THREAD (exactly ONE Assign beyond the literal; enclosing FunctionDef _ensure_live_publisher; only ast.Global in that def; both top-level in worker_live — global + rebinder in the SAME module); (e) identity + re-export regression (pristine subprocess probe: worker.<name> IS worker_live.<name> ×6 + "_LIVE_PUBLISH_QUEUE"/"_LIVE_PUBLISH_THREAD" in vars(worker); in-process identity; staying post_live_envelope call-site pin); (f) gate test — MODULE_SOURCES == 6 with worker_live.py present, union compatible, required env complete
- T-397-W7-006: Write the SDD trio specs/397-wave7-worker-live/ per the wave-6 validated house format (spec: Product outcome with STAYS + forced reasons, US-1..6, Scope, R-1..7, AC-1..7, Runtime feedback, NFR-1..4; plan: Implementation approach, Architecture, Decisions D-1..8, `- Risk profile: REQUIRED` + RISK-001..007 ranked + TEST-001..008 + Correct-course + Affected contours + Validation + TX-001..008 deployment transaction audit — deployable file list changes, VPS deployment NOT REQUIRED, Ubuntu worker/relay update REQUIRED, production safety envelope REQUIRED; tasks: DoD markers in the house format, UNCHECKED until the post-merge auto-sync); run the verification battery and record observed output: full pytest battery; ruff CI-config; validate_repo; validate_sdd; gate CLI (six-file union, compatible: true, required env complete); install-systemd.sh bash -n; py_compile worker/*.py; byte/AST proof + line arithmetic; git diff origin/main --stat scope check; NO push (orchestrator-owned)

## Completion gate

- [ ] T-397-W7-001
- [ ] T-397-W7-002
- [ ] T-397-W7-003
- [ ] T-397-W7-004
- [ ] T-397-W7-005
- [ ] T-397-W7-006
- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete

## Requirements traceability

- AC-001 | Task: T-397-W7-001, T-397-W7-002 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T-397-W7-002, T-397-W7-004, T-397-W7-005 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-397-W7-002, T-397-W7-005 | Evidence: TEST-003 | Coverage: COVERED
- AC-004 | Task: T-397-W7-002, T-397-W7-005 | Evidence: TEST-001, TEST-002 | Coverage: COVERED
- AC-005 | Task: T-397-W7-003, T-397-W7-005 | Evidence: TEST-005, TEST-008 | Coverage: COVERED
- AC-006 | Task: T-397-W7-004, T-397-W7-006 | Evidence: TEST-005, TEST-006, TEST-007, TEST-008 | Coverage: COVERED
- AC-007 | Task: T-397-W7-003, T-397-W7-006 | Evidence: TEST-007 | Coverage: COVERED

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [x] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [x] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] Deployment state resolved — rides the next routine Ubuntu-worker deploy (DEPLOY-TRIGGER, полоса A) — orchestrator-owned
- [ ] Runtime acceptance resolved — health gate probe on the next worker deploy — orchestrator-owned
- [ ] Deferred work recorded — ROI family (_roi_processing_points rebinds + cv2/numpy callees), _line_speed_state + update_speed_lines_estimate (sole consumer stays), detect_vehicles/track/event/main loop remain in the worker, recorded in spec/plan; remaining analytics/ROI + MotionDetector/main consolidation → later waves
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-007 mitigated in plan.md- [ ] Waivers resolved or current — none
