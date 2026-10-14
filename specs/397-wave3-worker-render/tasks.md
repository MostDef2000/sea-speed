# Tasks: wave-3 worker render — cv2 render/snapshot extraction (move-only)

- Issue: #397
- Specification: specs/397-wave3-worker-render/spec.md

## Delivery tasks

- T-397-W3-001: RECON the cut from live source (per work order; the progress-file notes are a guide, not authority): render/snapshot inventory of worker/hls_motion_yolo_worker_events.py; verified the three recorded STAYS — draw_roi_polygon (parse_road_roi_polygon→fetch_remote_roi→requests), draw_speed_lines_overlay (fetch_speed_lines_config→requests.get+cache), crossing_overlay_summary (no cv2; crossing-domain mutable caches; build_road_live_envelope references it DYNAMICALLY via a globals() guard); verified NO module-level constants are referenced by the moved defs; verified no REQUIRED_ENV_NAMES call site moves; verified no entrypoint render seams exist
- T-397-W3-002: Verify move-only precondition: per-function ast.dump equality of the 3 cut defs between HEAD worker source and the new render module (observed "AST-identical moved=3: True; staying defs intact: True") BEFORE the first repository write; the same check caught a corrupted first cut (top-down region order) — worker restored from HEAD and the cut re-run bottom-up
- T-397-W3-003: Execute the verbatim move: create worker/worker_render.py (cv2 + get_profile + 3 kernel-name imports + 3 defs, byte-exact bodies); cut the 3 source regions bottom-up; add the flat sibling re-export from worker_render import (3 names) after the media block, before first use; py_compile; symtable free-variable check → NONE unresolved; worker closure set byte-identical to HEAD
- T-397-W3-004: Extend scripts/worker/check_ubuntu_compatibility.py MODULE_SOURCES to three files (union semantics, fail-closed missing-file, schema keys unchanged — no other gate change)
- T-397-W3-005: Update the hard-import convergence lists: scripts/quality/build_exact_artifacts.py (ubuntu-worker + edge required), scripts/quality/validate_exact_artifacts.py (matching sets), scripts/ci/validate_repo.py (REQUIRED_FILES), deploy/worker/ubuntu/install-systemd.sh (prepared-release required loop); rollback-exact.sh deliberately untouched
- T-397-W3-006: Extend scripts/ci/validate_sdd.py GRANDFATHERED_PREFIX_COLLISIONS "397" set with 397-wave3-worker-render (exact-set equality — the scheduled break flagged by the wave-2 review; 396 precedent)
- T-397-W3-007: Update tests/support/worker_source.py DEFAULT_WORKER_SOURCES to parse all four worker files; ZERO #398 pin edits (observed green)
- T-397-W3-008: Add tests/test_worker_render_module.py (5 tests: import allowlist, no-network pin, re-export exact-list both directions, def placement incl. the three STAYS, gate three-file check); record the contract transfers (D-7): test_worker_kernel_module STAYING_NAMES −3, test_worker_media_module STAYING_IN_WORKER −3/+2
- T-397-W3-009: Write the SDD trio specs/397-wave3-worker-render/ per the wave-2 validated house format (RISK-001..005 nine-field pipe format; `- Risk profile: REQUIRED`; TEST-001..008; Correct-course check 7 bullets; TX-001..008 — install-systemd.sh in the changed set; AC-001..006; traceability with TEST evidence; DoD 10 markers); run the verification battery and record observed output: full discover (Ran 936 OK skipped=4 = 931 + 5 new); focused 6-module run (Ran 74 OK); ruff; validate_repo; validate_sdd; gate CLI (three-file union); py_compile ×4; refresh the durable progress file wave-3 section; NO commit, NO push (orchestrator-owned)

## Completion gate

- [x] T-397-W3-001
- [x] T-397-W3-002
- [x] T-397-W3-003
- [x] T-397-W3-004
- [x] T-397-W3-005
- [x] T-397-W3-006
- [x] T-397-W3-007
- [x] T-397-W3-008
- [x] T-397-W3-009
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (worker/**, scripts/worker/check_ubuntu_compatibility.py, 3 validators + validate_sdd grandfather, install-systemd.sh, tests harness + 3 test files, SDD trio; durable progress file OUTSIDE the git tree)
- [x] Required tests and evidence complete (transcripts in /home/mostdef/vibe/projects/ai-playground/progress-397-worker-decomposition.md; worker-recorded; commit/PR/merge orchestrator-owned)

## Requirements traceability

- AC-001 | Task: T-397-W3-002, T-397-W3-003 | Evidence: TEST-001, TEST-003 | Coverage: COVERED
- AC-002 | Task: T-397-W3-003, T-397-W3-008 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-397-W3-003, T-397-W3-008 | Evidence: TEST-002 | Coverage: COVERED
- AC-004 | Task: T-397-W3-004, T-397-W3-008 | Evidence: TEST-004, TEST-007 | Coverage: COVERED
- AC-005 | Task: T-397-W3-005, T-397-W3-006 | Evidence: TEST-006 | Coverage: COVERED
- AC-006 | Task: T-397-W3-009 | Evidence: TEST-004, TEST-005, TEST-006, TEST-008 | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [ ] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] Deployment state resolved — rides the next routine Ubuntu-worker deploy (DEPLOY-TRIGGER, полоса A) — orchestrator-owned
- [ ] Runtime acceptance resolved — health gate probe on the next worker deploy — orchestrator-owned
- [x] Deferred work recorded — draw_roi_polygon/draw_speed_lines_overlay (requests-entangled callers) + crossing_overlay_summary (domain state + globals() dynamic reference) stay, recorded in spec/plan; post_*/fetch_* family → later wave; mypy strict adoption of worker_render deferred to #399 owner
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-005 mitigated in plan.md
- [x] Waivers resolved or current — none
