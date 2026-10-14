# Tasks: wave-5 worker posting — crossing/speed-config posting surface extraction (move-only)

- Issue: #397
- Specification: specs/397-wave5-worker-posting/spec.md

## Delivery tasks

- T-397-W5-001: RECON the cut from live source at main d92e811 (per work order): verify the 4 cut defs (fetch_speed_config 542-566, post_crossing 706-729, flush_crossing_posts 732-739, _post_live_envelope_sync 438-456) + 2 state literals (_speed_config_cache 539, _crossing_pending_posts 587) with exact line numbers; map the bare-name access graph for _crossing_pending_posts (defining literal + in-place .append 684 / .pop(0) 738 / .clear 603 only — zero rebindings) and _speed_config_cache (sole accessor fetch_speed_config, item assignment only); verify the pairing constraint (flush calls post_crossing by bare name; transport cannot import the worker without a cycle); verify the recorded STAYS with forced reasons (datetime/threading/queue off-allowlist; _crossing_vlz_date/_LIVE_PUBLISH_THREAD/_roi_processing_points rebind via global; crossing_overlay_summary pinned by render STAYS + globals()-guard call site; _line_speed_state sole consumer stays); verify requests becomes dead in the worker after the cut and the gate union scan does not pin it
- T-397-W5-002: Execute the verbatim move with an assertion-guarded script: extract the 5 regions byte-exactly, cut BOTTOM-UP (standing wave-3 policy: 706-741, 587, 539-568, 438-458, each removing its trailing blank pair), remove the dead `import requests`, append the 6 names to the EXISTING single `from worker_transport import (...)` block with a wave-5 comment (wave-4 comment lines byte-untouched); extend worker_transport.py (posting section after post_passage: _post_live_envelope_sync + _crossing_pending_posts + post_crossing + flush_crossing_posts; fetcher section after fetch_crossing_line_config: _speed_config_cache + fetch_speed_config; kernel ImportFrom gains get_speed_config_url; docstring wave-5 sentence); verify: byte-segment equality 5/5, ast.dump equality 6/6, moved names gone from worker, exactly one worker_transport ImportFrom with the exact 15-name alias set, zero remaining `requests` references in the worker, py_compile both modules; record line arithmetic (worker 1336→1259, transport 312→410)
- T-397-W5-003: Extend tests/test_worker_transport_module.py per the contract transfer: MOVED_TRANSPORT_DEFS += fetch_speed_config/post_crossing/flush_crossing_posts/_post_live_envelope_sync; MOVED_TRANSPORT_CACHES += _speed_config_cache/_crossing_pending_posts; STAYING_IN_WORKER loses the 4 def names; import allowlist tuple UNCHANGED; VERIFY the auto-extending tests pass (re-export exact-list both directions over 15 names, identity IS over 5 state objects, pristine-import subprocess probe over 10 defs, AST no-rebinding guard across worker+transport, placement incl. STAYS); VERIFY tests/test_worker_render_module.py needs NO change (green unedited)
- T-397-W5-004: Extend scripts/ci/validate_sdd.py GRANDFATHERED_PREFIX_COLLISIONS "397" set with 397-wave5-worker-posting (exact-set equality; 396/waves-1-4 precedent); NO other validator or convergence-list edits (worker_transport.py already in validate_repo REQUIRED_FILES, build/validate_exact_artifacts ubuntu-worker+edge, install-systemd.sh prepared-release loop; gate stays 4-file with check_ubuntu_compatibility.py untouched)
- T-397-W5-005: Write the SDD trio specs/397-wave5-worker-posting/ per the wave-4 validated house format (RISK-001..006 nine-field pipe format incl. the four work-order-mandated rows: flush/post_crossing pairing, single-ImportFrom constraint, _crossing_pending_posts future-rebind risk, whole-tree AST scans requiring verbatim move; `- Risk profile: REQUIRED`; TEST-001..008; Correct-course check 7 bullets incl. the standing bottom-up-cut policy; TX-001..008 — worker/*.py are deployables so the full deployment transaction audit is included, VPS deployment NOT REQUIRED, Ubuntu worker/relay update REQUIRED; AC-001..007; traceability with TEST evidence; DoD 10 markers in the house format); run the verification battery and record observed output: full pytest battery (baseline pre-change 990 passed, 4 skipped); focused 5-suite run (71 passed); ruff CI-config clean (plain-config findings byte-identical to baseline — zero new); validate_repo; validate_sdd; gate CLI (compatible=True, four-file union, required env names complete); py_compile; byte/AST proof re-run; NO push (orchestrator-owned)
- T-397-W5-006: Record the one forced deviation in the durable progress file: dead `import requests` removed from the worker (post-cut AST sweep: zero remaining `requests` Name nodes; ruff F401 otherwise; gate union scan does not pin requests in the worker file); worker's kernel ImportFrom keeps get_speed_config_url (wave-1 re-export surface, noqa F401 block untouched per the work order)

## Completion gate

- [x] T-397-W5-001
- [x] T-397-W5-002
- [x] T-397-W5-003
- [x] T-397-W5-004
- [x] T-397-W5-005
- [x] T-397-W5-006
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (worker/hls_motion_yolo_worker_events.py, worker/worker_transport.py, tests/test_worker_transport_module.py, scripts/ci/validate_sdd.py, specs/397-wave5-worker-posting/**; tests/test_worker_render_module.py verified NO change needed; durable progress file OUTSIDE the git tree)
- [x] Required tests and evidence complete (transcripts in the durable progress file; worker-recorded; commit/PR/merge orchestrator-owned)

## Requirements traceability

- AC-001 | Task: T-397-W5-001, T-397-W5-002 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T-397-W5-002, T-397-W5-003 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-397-W5-002, T-397-W5-003 | Evidence: TEST-002 | Coverage: COVERED
- AC-004 | Task: T-397-W5-002, T-397-W5-003 | Evidence: TEST-003 | Coverage: COVERED
- AC-005 | Task: T-397-W5-004 | Evidence: TEST-004, TEST-007 | Coverage: COVERED
- AC-006 | Task: T-397-W5-003, T-397-W5-005 | Evidence: TEST-004, TEST-005, TEST-006, TEST-008 | Coverage: COVERED
- AC-007 | Task: T-397-W5-004, T-397-W5-005 | Evidence: TEST-006 | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [x] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main (98b3e91d)
- [x] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main (98b3e91d)
- [ ] Deployment state resolved — rides the next routine Ubuntu-worker deploy (DEPLOY-TRIGGER, полоса A) — orchestrator-owned
- [ ] Runtime acceptance resolved — health gate probe on the next worker deploy — orchestrator-owned
- [x] Deferred work recorded — crossing-domain state/mutators (datetime off-allowlist; _crossing_vlz_date rebinds), live-publisher loop (threading/queue off-allowlist; _LIVE_PUBLISH_THREAD rebinds), ROI cluster (_roi_processing_points rebinds + cv2/numpy), _line_speed_state (sole consumer stays) remain in the worker, recorded in spec/plan; remaining analytics/ROI + MotionDetector/main consolidation → later waves
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-006 mitigated in plan.md
- [x] Waivers resolved or current — none
