# Tasks: wave-4 worker transport — requests transport/posting extraction (move-only)

- Issue: #397
- Specification: specs/397-wave4-worker-transport/spec.md

## Delivery tasks

- T-397-W4-001: RECON the cut from live source (per work order; the progress-file notes are a guide, not authority): transport inventory of worker/hls_motion_yolo_worker_events.py; map the full cache read/write graph FIRST — programmatic bare-name use-map for _roi_cache/_speed_config_cache/_speed_lines_cache/_crossing_line_cache/_crossing_counts/_crossings_by_class/_roi_processing_points attributing every access to its owner; rebinding audit (zero rebindings of any moved cache; _roi_processing_points is the only rebinding global and it stays); verified the recorded STAYS — fetch_speed_config+_speed_config_cache (fetcher not in cut), post_crossing/flush_crossing_posts/_post_live_envelope_sync/live-publisher (not in cut), _crossing_counts/_crossings_by_class (staying mutators), _roi_processing_points (only rebinding global, staying reader); verified no timeout constants or env-flag booleans used only by movers; verified required-env reads move INTO the scanned union (SEA_SPEED_API_URL/TOKEN via post_*)
- T-397-W4-002: Verify move-only precondition: per-function ast.dump equality of the 6 cut defs + 3 caches between HEAD worker source and the new transport module BEFORE the first repository write; sweep free variables of each mover (requests/json/time/Path + kernel env/url/geometry helpers + media _resolve_frame_size); no timeout constants; no typing/datetime/os needed
- T-397-W4-003: Execute the verbatim move: create worker/worker_transport.py (requests + json/time/pathlib + worker_kernel ×8 + worker_media ×1 imports + 6 defs + 3 cache literals, byte-exact bodies; header documents the offline-layers-forbidden policy and the cache object-identity contract); cut the 9 source regions BOTTOM-UP (standing wave-3 policy); add the flat sibling re-export from worker_transport import (9 names incl. the caches) after the render block, before first use; py_compile; AST verify (6 defs + 3 caches identical, 64 staying defs intact, exact re-export list, placement render<transport<ROAD_LIVE_SCHEMA); symtable sweep → worker unresolved top-level symbols NONE
- T-397-W4-004: Extend scripts/worker/check_ubuntu_compatibility.py MODULE_SOURCES to four files (union semantics, fail-closed missing-file, schema keys unchanged — no other gate change); VERIFY by grep that the SEA_SPEED_API_URL/SEA_SPEED_API_TOKEN env_str call sites now live in worker_transport (the gate scans the union so stays green)
- T-397-W4-005: Update the hard-import convergence lists: scripts/quality/build_exact_artifacts.py (ubuntu-worker + edge required), scripts/quality/validate_exact_artifacts.py (matching sets), scripts/ci/validate_repo.py (REQUIRED_FILES), deploy/worker/ubuntu/install-systemd.sh (prepared-release required loop); rollback-exact.sh deliberately untouched
- T-397-W4-006: Extend scripts/ci/validate_sdd.py GRANDFATHERED_PREFIX_COLLISIONS "397" set with 397-wave4-worker-transport (exact-set equality; 396/waves-2-3 precedent)
- T-397-W4-007: Update tests/support/worker_source.py DEFAULT_WORKER_SOURCES to parse all five worker files; ZERO #398 pin edits (observed green)
- T-397-W4-008: Add tests/test_worker_transport_module.py (8 tests: import allowlist with requests double-armed REQUIRED, offline-layer pin, re-export exact-list both directions incl. caches, def/assign placement incl. the recorded STAYS, cache-identity pin IS + fetcher identity via mocked heavy-deps import, AST no-cache-rebinding guard, gate four-file check); record the contract transfers (D-7): test_worker_kernel_module STAYING_NAMES −1, test_worker_media_module STAYING_IN_WORKER −1, test_worker_render_module STAYING_IN_WORKER −4; record the C-4 patch-target analysis (D-6): ZERO patch-target transfers needed (ns-injection fakes survive; attribute reads resolve through the re-export)
- T-397-W4-009: Write the SDD trio specs/397-wave4-worker-transport/ per the wave-3 validated house format (RISK-001..006 nine-field pipe format incl. the cache-rebinding and monkeypatch-drift risks; `- Risk profile: REQUIRED`; TEST-001..008; Correct-course check 7 bullets incl. the standing bottom-up-cut policy; TX-001..008 — install-systemd.sh in the changed set; AC-001..007; traceability with TEST evidence; DoD 10 markers); run the verification battery and record observed output: full discover (Ran 944 OK skipped=4 = 936 + 8 new); focused 12-suite run (Ran 144 OK); ruff; validate_repo (Tracked files checked: 703); validate_sdd; gate CLI (four-file union, required env names complete); py_compile ×5; AST verify re-run; refresh the durable progress file wave-4 section; NO commit, NO push (orchestrator-owned)

## Completion gate

- [x] T-397-W4-001
- [x] T-397-W4-002
- [x] T-397-W4-003
- [x] T-397-W4-004
- [x] T-397-W4-005
- [x] T-397-W4-006
- [x] T-397-W4-007
- [x] T-397-W4-008
- [x] T-397-W4-009
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (worker/**, scripts/worker/check_ubuntu_compatibility.py, 3 validators + validate_sdd grandfather, install-systemd.sh, tests harness + 4 test files, SDD trio; durable progress file OUTSIDE the git tree)
- [x] Required tests and evidence complete (transcripts in /home/mostdef/vibe/projects/ai-playground/progress-397-worker-decomposition.md; worker-recorded; commit/PR/merge orchestrator-owned)

## Requirements traceability

- AC-001 | Task: T-397-W4-002, T-397-W4-003 | Evidence: TEST-001, TEST-003 | Coverage: COVERED
- AC-002 | Task: T-397-W4-003, T-397-W4-008 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-397-W4-003, T-397-W4-008 | Evidence: TEST-002 | Coverage: COVERED
- AC-004 | Task: T-397-W4-004, T-397-W4-008 | Evidence: TEST-004, TEST-007 | Coverage: COVERED
- AC-005 | Task: T-397-W4-005, T-397-W4-006 | Evidence: TEST-006 | Coverage: COVERED
- AC-006 | Task: T-397-W4-009 | Evidence: TEST-004, TEST-005, TEST-006, TEST-008 | Coverage: COVERED
- AC-007 | Task: T-397-W4-003, T-397-W4-008 | Evidence: TEST-003 | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [ ] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] Deployment state resolved — rides the next routine Ubuntu-worker deploy (DEPLOY-TRIGGER, полоса A) — orchestrator-owned
- [ ] Runtime acceptance resolved — health gate probe on the next worker deploy — orchestrator-owned
- [x] Deferred work recorded — fetch_speed_config+_speed_config_cache (fetcher not in cut), post_crossing/flush_crossing_posts/_post_live_envelope_sync/live-publisher (not in cut), _crossing_counts/_crossings_by_class (crossing-domain staying mutators), _roi_processing_points (only rebinding global) stay, recorded in spec/plan; remaining analytics/ROI + crossing/speed domain + MotionDetector/main → later waves; mypy strict adoption of worker_transport deferred to #399 owner
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-006 mitigated in plan.md
- [x] Waivers resolved or current — none
