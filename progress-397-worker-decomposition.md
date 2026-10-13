# progress-397-worker-decomposition.md (durable, outside git)

## Wave 1 — worker_kernel pure-helper extraction — IMPLEMENTED 2026-10-13

- Branch: sdd/397-wave1-worker-kernel (base origin/main f83a1ce4).
- Moved 24 functions (AST-identical bodies, verified vs HEAD before write) into NEW worker/worker_kernel.py (stdlib-only: os/datetime/urllib.parse).
- Re-export: flat sibling `from worker_kernel import (...)` in hls_motion_yolo_worker_events.py; main() global-name resolution + monkeypatch surface preserved; battery green with ZERO test edits.
- Excluded: write_passage_snapshot (cv2.imwrite + frame.shape) -> wave-3 candidate; road_roi_enabled/parse_road_roi_polygon (requests-entangled) -> stay.
- Convergence: validate_repo REQUIRED_FILES, build_exact_artifacts (ubuntu-worker+edge), validate_exact_artifacts, deploy/worker/ubuntu/install-systemd.sh all include worker/worker_kernel.py. rollback-exact.sh deliberately untouched (pre-#397 releases have no kernel).
- check_ubuntu_compatibility.py: green untouched (REQUIRED_ENV_NAMES call sites remain in worker file).
- Integrity tests NEW tests/test_worker_kernel_module.py (3): isolated stdlib-only import probe; exact-list re-export check (both directions); def placement.
- Verification observed: battery 923 OK (skipped=4) = 920 + 3; focused 61 OK; ruff 0; validate_repo OK; validate_sdd OK (after Runtime feedback section added by orchestrator); check_ubuntu_compatibility compatible=True forbidden_markers=[]; import probe 25 exports.
- SDD trio: specs/397-wave1-worker-kernel/{spec,plan,tasks}.md, RISK-1..5, NFR-001..004, RF-001..002.
- Peer review: PENDING.
- Next: wave 2 (start_ffmpeg/readers -> media module; requires check_ubuntu_compatibility.py AST-gate extension for moved start_ffmpeg), wave 3 (snapshot/render cv2 module), waves 4-7 (detect/track/posting/config per issue plan).
