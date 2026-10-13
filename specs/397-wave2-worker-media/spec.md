# Spec: wave-2 worker media — reader/media extraction + multi-file compatibility gate (move-only)

- Issue: #397
- Specification: specs/397-wave2-worker-media/spec.md

## Product outcome

Wave 1 (#475) extracted the pure stdlib kernel; the worker still mixes the media/reader layer (ffmpeg HLS spawn, in-process RTSP reader, frame/time helpers, the `start_media_reader` supervision seam) with analytics/rendering/posting logic. Wave 2 extracts the media/reader layer verbatim into NEW `worker/worker_media.py` (7 defs: `_resolve_frame_size`, `start_ffmpeg`, `read_exact`, `_frame_time_seconds`, `class FFmpegFrameReader`, `class RtspFrameReader`, `start_media_reader` — AST-identical bodies verified against HEAD before the first write) and extends the Ubuntu compatibility gate (`scripts/worker/check_ubuntu_compatibility.py`) to the multi-file reality it now must police: the gate scans BOTH worker sources (`MODULE_SOURCES` tuple mirroring the test harness's DEFAULT_WORKER_SOURCES naming), unions env-name call sites/imports/Popen usage across files, keeps every schema key and its fail-closed semantics, and fails closed when a worker source file is missing from the checked-out tree (gate validity — `worker_media.py` is now a required worker source, not an optional one).

`_resolve_frame_size` was listed in the cut as "if cv2-entangled": it is NOT cv2-entangled, but the move is forced by `start_media_reader` (a moved function calls it, and move-only forbids rewriting that call) — it moves with a re-export covering its 4 staying call sites (`fetch_remote_roi`, `fetch_speed_lines_config` region ×2, `main`). No module-level constants exist in the moved region (verified: the only reader-process lifecycle code is `FFmpegFrameReader.close()`'s `proc.kill()`, which moves with its class; no standalone terminate/kill/wait/restart helpers exist in the worker file — restart supervision lives in `ubuntu_worker_entrypoint.py`, untouched). `crop_sharpness` (cv2 Laplacian) stays — wave-3 candidate together with `draw_overlay`/`write_passage_snapshot`. `check_ubuntu_compatibility.py` has NO workflow/CI invocation (verified: zero references in `.github/workflows/**` and `scripts/ci/**`) — the extension is exercised by its unit tests and CLI, both updated.

## User scenarios

- US-1: the runtime worker boots on the Ubuntu worker host → `import worker_media` resolves as a flat sibling (shipped by the exact artifacts and the installer) → `main()`/entrypoint references to `start_media_reader` and every moved helper keep resolving via the worker re-export → behavior byte-identical to pre-split (AST-identical bodies, same spawn/cleanup semantics).
- US-2: the entrypoint supervision seam rebinds `worker.start_media_reader` (monkeypatch surface) → the re-export keeps the name as a worker-module binding → patch semantics unchanged.
- US-3: the #398 AST harness extracts `start_ffmpeg` (or any moved helper) → DEFAULT_WORKER_SOURCES (now 3 files) resolves it from worker_media.py → existing pins pass UNTOUCHED (observed: focused + full battery green with zero pin edits).
- US-4: CI/validators run → the exact-artifact required lists (ubuntu-worker AND edge), validate_repo REQUIRED_FILES and the installer's prepared-release check all include worker/worker_media.py → a payload missing the media layer fails closed at CI or install, never at boot.
- US-5: the compatibility gate scans BOTH worker sources → `HLS_URL` call sites now living only in worker_media.py satisfy the requirement (union semantics); if a required env-name call site is removed from BOTH files the gate FAILS; if worker_media.py is absent from the tree the gate FAILS (missing file is gate-invalid, never silently green).
- US-6: a future contributor hoists `import av` (or adds ultralytics/requests) to worker_media.py module level → the AST import-allowlist test fails in CI instead of silently bloating the media layer's dependency surface.

## Scope

- NEW `worker/worker_media.py`: header docstring documenting the import policy + imports (subprocess, time, numpy as np, `from analytics_profiles import get_profile`, 6 names from worker_kernel) + 7 moved defs, bodies byte-identical to HEAD.
- `worker/hls_motion_yolo_worker_events.py`: ONLY — remove the moved def blocks (2 contiguous regions); remove the now-unused `import subprocess` (its only user, `start_ffmpeg`'s Popen, moved); add the flat sibling re-export `from worker_media import (7 names)` with a wave-2 comment. No logic edits, no renames, no signature changes anywhere.
- `scripts/worker/check_ubuntu_compatibility.py`: `MODULE_SOURCES` tuple at top; `inspect_worker` accepts a Path or a list/tuple of paths (single-Path back-compat preserved); union scans across files for (a) REQUIRED_ENV_NAMES env_str/env_int/env_float call sites, (b) subprocess.Popen usage check, (c) pathlib/subprocess import presence, (d) forbidden_markers; missing file → SystemExit (fail closed); `main()` default scans MODULE_SOURCES with an explicit missing-file error; `--worker` stays a single-file debug override; output schema keys unchanged (`worker` value = comma-joined display paths). NO weakening anywhere.
- Convergence lists (hard-import convergence): `scripts/ci/validate_repo.py` REQUIRED_FILES; `scripts/quality/build_exact_artifacts.py` ubuntu-worker + edge required; `scripts/quality/validate_exact_artifacts.py` ubuntu-worker + edge required sets; `deploy/worker/ubuntu/install-systemd.sh` prepared-release required loop (worker/worker_media.py alongside the worker file and the kernel).
- `tests/support/worker_source.py`: DEFAULT_WORKER_SOURCES gains `worker/worker_media.py` (3 files, first-definition-wins). No helper API changes; no #398 pin edits.
- NEW `tests/test_worker_media_module.py`: (a) media import-allowlist AST check (top-level imports ⊆ explicit allowlist: cv2/numpy/subprocess/os/time/pathlib/datetime/urllib.parse/typing + repo-pure worker_kernel/analytics_profiles; `av` deliberately EXCLUDED — lazy import inside RtspFrameReader pinned by test); (b) exact-list re-export check (both directions); (c) def placement (moved defs only in media, staying defs only in worker, nothing media-shaped in the kernel); (d) gate extension tests: single-file worker scan now MISSES HLS_URL (proves the cross-file scan is real), union across both files is compatible, negative temp-tree test (required env call site removed from BOTH files → gate fails), missing-file → SystemExit.
- `tests/test_worker_kernel_module.py`: STAYING_NAMES updated — the three wave-2-moved names transfer to the wave-2 guard (contract transfer per work order, not a pin fix).
- `tests/test_ubuntu_worker_compatibility.py`: the default-contract test scans `module.MODULE_SOURCES` (the gate's own multi-file reality).
- SDD trio `specs/397-wave2-worker-media/` and the durable progress file (workspace root, outside git).
- OUT of scope: any behavior change in worker/**; `draw_overlay`/`write_passage_snapshot`/`crop_sharpness` (cv2 render/snapshot family — wave 3); `rollback-exact.sh` (targets PREVIOUS complete releases which are self-consistent by construction — unchanged since wave 1, same rationale); `.github/workflows/**` (the gate has no workflow invocation); `api/**`; `frontend/**`; mypy adoption of worker_media (deferred, #399-owner decision).

## Requirements

- R-1 (AC-001): all 7 moved defs (functions AND classes with their methods) are AST-identical to HEAD; no renames, no signature changes, no logic edits.
- R-2 (AC-002): the runtime worker re-exports exactly the 7 moved names via one flat sibling ImportFrom; the exact-list check fails on drift in either direction; moved defs exist ONLY in worker_media; staying defs (crop_sharpness, fetch_remote_roi, detect_vehicles, main, write_passage_snapshot, draw_overlay) remain ONLY in the worker; nothing moved leaks into the stdlib kernel.
- R-3 (AC-003): worker_media.py top-level imports stay within the explicit media allowlist; `import av` remains lazy inside RtspFrameReader.__init__ (the no-PyAV RuntimeError fallback path is preserved byte-identically).
- R-4 (AC-004): the compatibility gate scans BOTH worker sources with union semantics for env call sites, imports, Popen usage and forbidden markers; missing call sites in EITHER file satisfy the requirement; a missing file fails closed; schema keys unchanged; no weakening.
- R-5 (AC-005): all four convergence lists include `worker/worker_media.py`; validators stay green; rollback-exact.sh untouched.
- R-6 (AC-006): full unittest battery passes with NO #398 pin edits; expected 931 tests (923 + 8 new media-module/gate tests), skipped=4; ruff, validate_repo and validate_sdd green.

## Acceptance criteria

- AC-001: per-function `ast.dump` equality between HEAD worker source and worker_media.py for all 7 defs including class methods (observed: "AST-identical moved=7: True; defs removed from worker: True; staying defs intact: True").
- AC-002: `tests/test_worker_media_module.py` re-export surface tests pass; alias set equals MOVED_MEDIA_NAMES exactly.
- AC-003: import-allowlist test passes; lazy-av test passes (exactly one `import av` inside RtspFrameReader.__init__).
- AC-004: gate tests prove union semantics (single-file scan misses HLS_URL, union scan passes), the negative (call site removed from both → HLS_URL in missing_required_environment_names, compatible=False) and fail-closed file validity (missing worker_media.py → SystemExit); `python3 scripts/worker/check_ubuntu_compatibility.py` (default MODULE_SOURCES) exits 0 with compatible=True, forbidden_markers=[].
- AC-005: validate_repo (693 tracked files), build_exact_artifacts + validate_exact_artifacts (ubuntu-worker AND edge), and the install-systemd prepared-release loop all reference worker/worker_media.py; validators exit 0.
- AC-006: full discover battery: 931 tests, OK (skipped=4); focused: media_module + kernel_module + ubuntu_worker_compatibility + rtsp_media_security + worker_contract + worker_roi_pipeline → Ran 32, OK (skipped=1); ruff `--config scripts/quality/ruff.toml` passes; validate_repo + validate_sdd pass; py_compile of both worker modules passes (the cv2-dependent runtime import probe is replaced by py_compile + AST parse — worker_media deliberately needs cv2-class deps absent from this sandbox).

## Runtime feedback

- RF-001: Operator actions expected: 0; this wave changes only the worker source layout (move-only) plus gate/validator coverage — runtime verification lands with the next routine Ubuntu-worker deploy (batched with wave 3, owner deploy gate); the orchestrator records runtime acceptance on issue #397.
- RF-002: Evidence: the next deploy-ubuntu-worker run for a post-wave-2 SHA shows the media module shipped in the exact artifacts and both worker services restarting green; AST-equivalence, symtable and battery transcripts are recorded in the durable progress file.

## NFR assessment

- NFR-001 | Area: reliability/operations | Target: move-only equivalence — runtime behavior byte-identical: same reader bodies (AST-identical), same spawn/kill/close semantics (the only lifecycle primitive, `proc.kill()` in FFmpegFrameReader.close, moved with its class), same global-name resolution via re-export, monkeypatch surface preserved | Validation: AST-dump equality vs HEAD for all 7 defs; symtable free-variable check (NONE unresolved); full battery green with zero pin edits; focused rtsp media security tests | Evidence: transcripts in the progress file | Status: PASS
- NFR-002 | Area: maintainability | Target: the media layer is a coherent unit with a POLICED dependency surface — top-level imports limited to the media allowlist, `av` lazy, no ultralytics/requests creep | Validation: AST import-allowlist unit test + lazy-av pin | Evidence: tests/test_worker_media_module.py OK | Status: PASS
- NFR-003 | Area: security | Target: no new exposure — the media layer spawns ffmpeg and reads env exactly as before (same bodies); forbidden-marker scan now covers BOTH worker files; no secrets introduced; artifact lists only ADD a source file | Validation: diff inspection; gate CLI output (forbidden_markers=[] across the union); validators green | Evidence: git diff reviewed; gate transcript | Status: PASS
- NFR-004 | Area: compatibility | Target: the gate extension is strictly ADDITIVE in coverage — union semantics keep every previously-passing case passing (existing single-Path inspect_worker callers work unchanged), fail-closed file validity is new strictness, and all SDD delivery-layer validators stay green at final head | Validation: existing compat tests green (updated default-contract test), gate unit tests incl. negatives, validate_sdd plain green | Evidence: transcripts in the progress file | Status: PASS

## Risks

| ID | Risk | Score (P×I) | Mitigation |
|---|---|---|---|
| RISK-1 | Re-export surface drift breaks `main()`/entrypoint resolution (worker.start_media_reader seam) or the monkeypatch surface | 2×5=10 | Integrity test: exact-list re-export check in both directions + full battery (all worker tests green untouched) |
| RISK-2 | Compatibility-gate extension misses a call site that lives only in worker_media.py → gate falsely green | 2×5=10 | Cross-file union scan + three gate unit tests: single-file worker scan demonstrably misses HLS_URL (proves the union does real work), required env call site removed from BOTH files → gate FAILS, missing file → SystemExit |
| RISK-3 | Process-lifecycle move changes spawn/cleanup behavior (Popen args, kill/close, RTSP open/read/reformat) | 1×5=5 | Byte-level AST identity for all 7 defs (incl. class methods) + full battery + focused test_worker_rtsp_media_security green untouched |
| RISK-4 | Convergence list miss fails CI or ships a payload without worker_media.py (failure at deploy boot instead of CI) | 2×5=10 | All four convergence sites updated in the same diff; all validators run locally; install-systemd.sh fails closed at prepare-check; CI exact-artifact gate re-verifies at merge |
| RISK-5 | Free-variable sweep miss → NameError at runtime (a moved body referencing a worker-module global that did not move) | 2×5=10 | Programmatic symtable free-variable check of worker_media (result: NONE unresolved); staying-worker closure set verified byte-identical to HEAD (pre-existing, not introduced) |
