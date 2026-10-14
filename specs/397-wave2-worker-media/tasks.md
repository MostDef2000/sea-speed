# Tasks: wave-2 worker media — reader/media extraction + multi-file compatibility gate (move-only)

- Issue: #397
- Specification: specs/397-wave2-worker-media/spec.md

## Delivery tasks

- T-397-W2-001: RECON the cut from live source (per work order; the progress-file map is a guide, not authority): media/reader inventory of worker/hls_motion_yolo_worker_events.py; verified NO standalone lifecycle/restart helpers and NO module-level constants in the moved region; verified check_ubuntu_compatibility has zero workflow/CI invocation; confirmed `_resolve_frame_size` moves (forced by start_media_reader's call, move-only) with 4 staying call sites covered by the re-export; crop_sharpness stays (cv2, wave-3)
- T-397-W2-002: Verify move-only precondition: per-function ast.dump equality of all 7 cut defs (incl. class methods) between HEAD worker source and the new media module (observed "AST-identical moved=7: True; staying defs intact: True") BEFORE the first repository write
- T-397-W2-003: Execute the verbatim move: create worker/worker_media.py (subprocess/time/numpy + get_profile + 6 kernel-name imports + 7 defs, byte-exact bodies); cut the 2 source regions from hls_motion_yolo_worker_events.py; remove the orphaned `import subprocess`; add the flat sibling re-export from worker_media import (7 names) with the wave-2 comment; py_compile both files; symtable free-variable check → NONE unresolved
- T-397-W2-004: Extend scripts/worker/check_ubuntu_compatibility.py to the multi-file reality: MODULE_SOURCES tuple, inspect_worker accepts Path or sequence (back-compat), union scans (env call sites, Popen usage, pathlib/subprocess imports, forbidden markers), fail-closed missing-file checks in inspect_worker AND main(), schema keys unchanged, --worker single-file debug override, NO weakening
- T-397-W2-005: Update the hard-import convergence lists: scripts/quality/build_exact_artifacts.py (ubuntu-worker + edge required), scripts/quality/validate_exact_artifacts.py (matching sets), scripts/ci/validate_repo.py (REQUIRED_FILES), deploy/worker/ubuntu/install-systemd.sh (prepared-release required loop); rollback-exact.sh deliberately untouched (previous releases may predate the media module)
- T-397-W2-006: Update tests/support/worker_source.py DEFAULT_WORKER_SOURCES to parse all three worker files; ZERO #398 pin edits (observed green)
- T-397-W2-007: Add tests/test_worker_media_module.py (8 tests: import allowlist + lazy-av pin, re-export exact-list both directions, def placement, 4 gate tests incl. single-file-miss/union/negative-temp-tree/missing-file); update tests/test_worker_kernel_module.py STAYING_NAMES (contract transfer of the 3 wave-2-moved names, D-7) and tests/test_ubuntu_worker_compatibility.py default-contract test (scans MODULE_SOURCES)
- T-397-W2-008: Write the SDD trio specs/397-wave2-worker-media/ per the wave-1 validated house format (RISK-001..005 in the 9-field pipe format incl. the five mandated risks; `- Risk profile: REQUIRED`; TEST-001..008; Correct-course check 7 bullets; TX-001..008 — install-systemd.sh is in the changed set; AC-001..006; traceability with TEST evidence; DoD 10 markers)
- T-397-W2-009: Run the verification battery and record observed output: full discover (Ran 931 OK skipped=4 = 923 + 8 new); focused 6-module run (Ran 32 OK skipped=1); ruff --config scripts/quality/ruff.toml; validate_repo; validate_sdd; gate CLI (compatible=True, multi-file evidence); py_compile probe; refresh the durable progress file progress-397-worker-decomposition.md with the wave-2 section; NO commit, NO push (orchestrator-owned)

## Completion gate

- [x] T-397-W2-001
- [x] T-397-W2-002
- [x] T-397-W2-003
- [x] T-397-W2-004
- [x] T-397-W2-005
- [x] T-397-W2-006
- [x] T-397-W2-007
- [x] T-397-W2-008
- [x] T-397-W2-009
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (worker/**, scripts/worker/check_ubuntu_compatibility.py, 3 validators, install-systemd.sh, tests harness + 3 test files, SDD trio; durable progress file OUTSIDE the git tree)
- [x] Required tests and evidence complete (transcripts in /home/mostdef/vibe/projects/ai-playground/progress-397-worker-decomposition.md; worker-recorded; commit/PR/merge orchestrator-owned)

## Requirements traceability

- AC-001 | Task: T-397-W2-002, T-397-W2-003 | Evidence: TEST-001, TEST-003 | Coverage: COVERED
- AC-002 | Task: T-397-W2-003, T-397-W2-007 | Evidence: TEST-002 | Coverage: COVERED
- AC-003 | Task: T-397-W2-003, T-397-W2-007 | Evidence: TEST-002 | Coverage: COVERED
- AC-004 | Task: T-397-W2-004, T-397-W2-007 | Evidence: TEST-004, TEST-007 | Coverage: COVERED
- AC-005 | Task: T-397-W2-005 | Evidence: TEST-006 | Coverage: COVERED
- AC-006 | Task: T-397-W2-009 | Evidence: TEST-004, TEST-005, TEST-006, TEST-008 | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete
- [x] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [x] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] Deployment state resolved — rides the next routine Ubuntu-worker deploy (DEPLOY-TRIGGER, полоса A) — orchestrator-owned
- [ ] Runtime acceptance resolved — health gate probe on the next worker deploy — orchestrator-owned
- [x] Deferred work recorded — draw_overlay/write_passage_snapshot/crop_sharpness → wave 3 (cv2 render/snapshot family); mypy strict adoption of worker_media deferred to #399 owner
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-005 mitigated in plan.md
- [x] Waivers resolved or current — none
