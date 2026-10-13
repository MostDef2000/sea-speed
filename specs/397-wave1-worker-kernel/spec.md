# Spec: wave-1 worker kernel — pure-helper extraction (move-only)

- Issue: #397
- Specification: specs/397-wave1-worker-kernel/spec.md

## Product outcome

The runtime worker `worker/hls_motion_yolo_worker_events.py` (~1830 lines) mixes two kinds of code: pure stdlib helpers (env readers, media identity/auth URL parsing, geometry/crossing primitives, label formatting) and heavy-dependency runtime logic (cv2/numpy/ultralytics/requests inference, RTSP readers, overlay rendering, posting flow). The #397 decomposition moves toward a testable kernel; wave 1 extracts ONLY the pure helpers, verbatim.

This wave creates `worker/worker_kernel.py` containing 24 functions moved byte-for-byte (AST-identical bodies verified against HEAD before the first write) from the runtime worker, with a strict stdlib-only contract: the module must import in a bare, isolated CPython (`python3 -I`) with no cv2/numpy/requests/ultralytics available. The runtime worker re-exports every moved name at module level via a flat sibling import (`from worker_kernel import (...)`, same style as `analytics_profiles`/`water_passage`), preserving: (a) `main()` global-name resolution — no call-site edits anywhere; (b) the test monkeypatch surface (worker-module attributes stay patchable); (c) the #398 AST test harness (`tests/support/worker_source.py` DEFAULT_WORKER_SOURCES now parses BOTH files, its designed evolution path for exactly this decomposition).

`write_passage_snapshot` was evaluated for the cut and LEFT in the worker: it uses `cv2.imwrite` + `frame.shape` (numpy), violating the stdlib-only constraint — recorded as a wave-3 candidate. The env-flag family named in the decomposition plan (`is_preview_mode`, `is_show_tracks`, `is_save_clips`, `is_motion_enabled`, `is_speed_mode`) does not exist in the live source; the actual read-config-from-env family is `env_str`/`env_int`/`env_float` + the four boolean readers (`is_motion_gate_always_on`, `is_yolo_half_enabled`, `is_yolo_classes_filter_enabled`, `water_recall_diagnostics_enabled`), all moved. Functions whose env reads are entangled with `requests` fetches (`road_roi_enabled`, `parse_road_roi_polygon` via `fetch_remote_roi`) stay.

## User scenarios

- US-1: the runtime worker boots on the Ubuntu worker host → `import worker_kernel` resolves as a flat sibling (shipped by the exact artifacts and the installer) → every `main()` reference to a moved helper keeps resolving → behavior byte-identical to pre-split.
- US-2: a test patches a worker-module attribute (monkeypatch surface) → the re-export keeps the name as a worker-module binding → patch semantics unchanged.
- US-3: the #398 AST harness extracts `side_of_line`/`sign_with_deadzone`/`crossed_line` (or any moved helper) → DEFAULT_WORKER_SOURCES resolves it from worker_kernel.py → existing pins pass untouched (observed: full battery green without test edits).
- US-4: CI runs the four validators → the exact-artifact required lists (ubuntu-worker AND edge), the repo required-files list and the installer's prepared-release check all include worker_kernel.py → a payload missing the kernel fails closed instead of boot-looping on the target.
- US-5: a future contributor adds a numpy call to a kernel function → the stdlib-only import probe (isolated subprocess) fails in CI before merge.

## Scope

- NEW `worker/worker_kernel.py`: stdlib imports (os, datetime, urllib.parse) + 24 moved functions, bodies byte-identical to HEAD.
- `worker/hls_motion_yolo_worker_events.py`: ONLY — remove the 24 moved def blocks; remove the now-unused `from urllib.parse import urlsplit` import; add the flat sibling re-export `from worker_kernel import (...)` with a wave-1 comment. No logic edits, no renames, no signature changes anywhere.
- `tests/support/worker_source.py`: DEFAULT_WORKER_SOURCES gains `worker/worker_kernel.py` (+ comment). No helper API changes; no test/pin edits.
- Convergence lists (hard-import convergence): `scripts/ci/validate_repo.py` REQUIRED_FILES; `scripts/quality/build_exact_artifacts.py` ubuntu-worker + edge required; `scripts/quality/validate_exact_artifacts.py` ubuntu-worker + edge required sets; `deploy/worker/ubuntu/install-systemd.sh` prepared-release required loop (worker/worker_kernel.py alongside the worker file).
- NEW `tests/test_worker_kernel_module.py`: (a) isolated-subprocess stdlib-only import probe; (b) exact-list re-export surface AST check (both directions of drift); plus a defined-where-expected check (moved defs in kernel only, staying defs in worker only).
- SDD trio `specs/397-wave1-worker-kernel/` and the durable progress file `progress-397-worker-decomposition.md` (repo root, outside git).
- OUT of scope: any behavior change in worker/**; moving `start_ffmpeg`/readers/`detect_vehicles`/overlay/posting/config-fetch logic (waves 2+); `check_ubuntu_compatibility.py` (single-file gate, stays green untouched); `rollback-exact.sh` (targets PREVIOUS releases which may predate the kernel — adding a kernel requirement there would break rollback to pre-#397 releases); `.github/workflows/**`; `api/**`; `frontend/**`; mypy strict-list adoption of worker_kernel (mypy.ini suggests new pure modules SHOULD be adopted — deferred to review, CI mypy invocation unchanged).

## Requirements

- R-1 (AC-1): `worker/worker_kernel.py` is stdlib-only — `python3 -I -c "import worker_kernel"` with only worker/ on sys.path exits 0.
- R-2 (AC-2): all 24 moved function bodies are AST-identical to HEAD (verified programmatically before the first write); no renames, no signature changes, no logic edits.
- R-3 (AC-3): the runtime worker re-exports exactly the 24 moved names via one flat sibling ImportFrom; the exact-list check fails on drift in either direction; moved defs exist ONLY in the kernel; `main()` and all staying functions are untouched in the worker.
- R-4 (AC-4): all four convergence lists include `worker/worker_kernel.py`; validators stay green; no validator weakened.
- R-5 (AC-5): `check_ubuntu_compatibility.py` stays green with zero changes (its env-name call-site scan still finds HLS_URL/SEA_SPEED_API_URL/SEA_SPEED_API_TOKEN/MODEL_NAME calls in the worker file — only definitions moved).
- R-6 (AC-6): full unittest battery passes with NO test edits beyond the new integrity test; expected 923 tests (920 + 3 new), skipped=4; any delta must be justified.

## Acceptance criteria

- AC-1: import probe exit code 0 in isolated subprocess (observed).
- AC-2: per-function `ast.dump` equality between HEAD worker source and worker_kernel.py for all 24 names (observed: "all 24 AST-identical: True").
- AC-3: `tests/test_worker_kernel_module.py` 3/3 OK; re-export set equals MOVED_NAMES exactly.
- AC-4: validate_repo, build_exact_artifacts (via validate_quality_contracts path), validate_exact_artifacts, install-systemd list all reference worker/worker_kernel.py; validators exit 0.
- AC-5: `python3 scripts/worker/check_ubuntu_compatibility.py` (default worker) exits 0 with `compatible=True`.
- AC-6: full discover battery: 923 tests, OK (skipped=4); focused: tests.test_worker_contract + tests.test_line_crossing + tests.test_worker_roi_pipeline + tests.test_worker_kernel_module OK; ruff `--config scripts/quality/ruff.toml .` passes; validate_repo + validate_sdd pass.

## Runtime feedback

- RF-001: Operator actions expected: 0; this wave changes only the worker source layout (move-only) — runtime verification lands with the next routine Ubuntu-worker deploy (batched with wave 2, owner deploy gate); the orchestrator records runtime acceptance on issue #397.
- RF-002: Evidence: the next deploy-ubuntu-worker run for a post-#474 SHA shows the kernel shipped in the exact artifacts and both worker services restarting green; AST-equivalence and battery transcripts are recorded in the durable progress file.

## NFR assessment

- NFR-001 | Area: reliability/operations | Target: move-only equivalence — runtime behavior byte-identical: same helper bodies (AST-identical), same global-name resolution via re-export, no call-site edits, monkeypatch surface preserved | Validation: AST-dump equality check vs HEAD for all 24 names; full battery green with zero test edits; import probe | Evidence: battery transcripts in progress file | Status: PASS
- NFR-002 | Area: maintainability | Target: the kernel is a genuinely standalone stdlib module usable by future waves and tests without heavy deps | Validation: isolated-subprocess import probe (python3 -I, only worker/ on path) | Evidence: test (a) OK | Status: PASS
- NFR-003 | Area: security | Target: no new exposure — the kernel reads env and parses URLs exactly as before (same bodies); no secrets introduced; artifact lists only ADD a source file | Validation: diff inspection (no string literals added beyond docstring); validators green | Evidence: git diff reviewed | Status: PASS
- NFR-004 | Area: compatibility | Target: existing #398 AST harness, ubuntu compatibility gate, exact artifacts and installer all keep working without semantic changes | Validation: full battery + all validators + compatibility checker observed green | Evidence: transcripts in progress file | Status: PASS

## Risks

| ID | Risk | Score (P×I) | Mitigation |
|---|---|---|---|
| RISK-1 | A missed re-export breaks runtime `main()` call resolution or the test monkeypatch surface | 2×5=10 | Integrity test (b): exact-list re-export check in both directions + full battery (all worker tests green untouched) |
| RISK-2 | A hidden non-stdlib dependency inside a moved function breaks the stdlib-only contract on the worker host | 2×4=8 | Isolated-subprocess import probe (python3 -I, worker/ only); each candidate body manually audited for imports/globals before the cut; write_passage_snapshot excluded (cv2) |
| RISK-3 | A pinned required-list miss (artifact build/validate, validate_repo, installer) ships a payload without worker_kernel.py — failure surfaces at deploy boot instead of CI | 2×5=10 | All four convergence sites updated in the same diff; all validators run locally; install-systemd.sh fails closed at prepare-check; CI exact-artifact gate re-verifies at merge |
| RISK-4 | The #398 AST harness loses sight of moved functions (function_node/extract_nodes would raise "missing worker functions") | 1×4=4 | DEFAULT_WORKER_SOURCES now lists both files (the harness's designed #397 evolution path); focused runs of every harness consumer observed green |
| RISK-5 | Drift between this repo copy and the missing progress-file line map (the decomposition map file did not exist at wave start) | 1×2=2 | The cut was re-derived from live source (order's own instruction); progress-397-worker-decomposition.md is (re)created this wave with the verified line map for waves 2-3 |
