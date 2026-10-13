# Tasks: wave-1 worker kernel — pure-helper extraction (move-only)

- Issue: #397
- Specification: specs/397-wave1-worker-kernel/spec.md

## Delivery tasks

- T-397-W1-001: RECON the cut from live source (per work order; the referenced progress-file line map did not exist at wave start): full function inventory of worker/hls_motion_yolo_worker_events.py; stdlib-only audit of every candidate body (write_passage_snapshot → cv2 → STAYS, wave-3 note; road_roi_enabled/parse_road_roi_polygon → fetch_remote_roi/requests → STAY); confirmed the decomposition-note flag names (is_preview_mode etc.) do not exist; confirmed the 4 REQUIRED_ENV_NAMES of check_ubuntu_compatibility keep call sites in the worker file
- T-397-W1-002: Verify move-only precondition: per-function ast.dump equality of all 24 cut candidates between HEAD worker source and the new kernel (observed "all 24 AST-identical: True") BEFORE the first repository write
- T-397-W1-003: Execute the verbatim move: create worker/worker_kernel.py (stdlib imports os/datetime/urllib.parse + 24 functions, byte-exact bodies); cut the 8 source regions from hls_motion_yolo_worker_events.py; remove the orphaned urlsplit import; add the flat sibling re-export from worker_kernel import (...) with the wave-1 comment; py_compile both files
- T-397-W1-004: Update tests/support/worker_source.py DEFAULT_WORKER_SOURCES to parse both worker files (the harness's designed #397 evolution path); no helper API or test/pin edits
- T-397-W1-005: Update the hard-import convergence lists: scripts/quality/build_exact_artifacts.py (ubuntu-worker + edge required), scripts/quality/validate_exact_artifacts.py (matching sets), scripts/ci/validate_repo.py (REQUIRED_FILES), deploy/worker/ubuntu/install-systemd.sh (prepared-release required loop); rollback-exact.sh deliberately untouched (previous releases may predate the kernel)
- T-397-W1-006: Add tests/test_worker_kernel_module.py: (a) isolated-subprocess stdlib-only import probe (python3 -I, only worker/ on sys.path); (b) exact-list re-export surface AST check (both drift directions); (c) moved defs in kernel only / staying defs in worker only
- T-397-W1-007: Write the SDD trio specs/397-wave1-worker-kernel/ per house pattern (RISK-1..5 with Score=P×I incl. the three mandated risks; NFR-001..004; correct-course triggers: fix the MOVE on pin failure, fix the LIST on validator failure — never the test, never weaken the validator)
- T-397-W1-008: Run the verification battery and record observed output: full discover (expected 923 OK skipped=4 = 920 + 3 new); focused runs (worker_contract, line_crossing, roi_pipeline, kernel_module); ruff --config scripts/quality/ruff.toml .; validate_repo; validate_sdd; check_ubuntu_compatibility; worker-module runtime import probe; kernel import probe (dir(...) count)
- T-397-W1-009: Create/refresh the durable progress file progress-397-worker-decomposition.md (repo root, outside git): wave-1 status + the verified wave-1 line map + forward notes (write_passage_snapshot → wave 3; named-but-nonexistent env flags documented; rollback caveat); NO commit, NO push (orchestrator-owned)

## Completion gate

- [x] T-397-W1-001
- [x] T-397-W1-002
- [x] T-397-W1-003
- [x] T-397-W1-004
- [x] T-397-W1-005
- [x] T-397-W1-006
- [x] T-397-W1-007
- [x] T-397-W1-008
- [x] T-397-W1-009
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (worker/**, tests/support/worker_source.py, tests/test_worker_kernel_module.py, 3 validators, install-systemd.sh, SDD trio)
- [x] Required tests and evidence complete (transcripts in progress-397-worker-decomposition.md; worker-recorded; commit/PR/merge orchestrator-owned)
