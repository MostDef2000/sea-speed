# Plan: wave-1 worker kernel — pure-helper extraction (move-only)

- Issue: #397
- Specification: specs/397-wave1-worker-kernel/spec.md

## Implementation approach

1. RECON-established facts (re-derived from live source, per the work order — the referenced progress-file line map did not exist at wave start): the worker file defines ~90 top-level functions; the pure-helper cut resolves to exactly 24 functions: env readers `env_str`/`env_int`/`env_float` + boolean env flags `is_motion_gate_always_on`/`is_yolo_half_enabled`/`is_yolo_classes_filter_enabled`/`water_recall_diagnostics_enabled` (the flag names in the decomposition notes — is_preview_mode/is_show_tracks/is_save_clips/is_motion_enabled/is_speed_mode — do not exist anywhere in the repo), ROI point scalers `_scale_norm_points`/`_maybe_scale_legacy_absolute`, `now_iso`, media identity/auth quartet `_media_input_scheme`/`safe_media_input_label`/`media_basic_auth_for_input`/`roi_basic_auth`, URL builders `get_roi_url`/`get_speed_config_url`/`get_speed_lines_url`/`get_crossing_line_url` (env+string work only — the fetch_* siblings use requests and stay), labels `format_detection_label`/`overlay_label_opacity`, crossing geometry `side_of_line`/`sign_with_deadzone`/`crossed_line`, and `bbox_center`. `write_passage_snapshot` uses `cv2.imwrite`+`frame.shape` → STAYS (wave-3 note). None of the 24 reference worker-module globals outside the moved set (only each other + stdlib), so the kernel needs no stubs. The four REQUIRED_ENV_NAMES of check_ubuntu_compatibility keep call sites in the worker file (SEA_SPEED_API_TOKEN: post_* family; SEA_SPEED_API_URL: post_* family; HLS_URL: start_ffmpeg/start_media_reader; MODEL_NAME: build_event/main) — the gate scans CALLS, not defs.
2. Move-only mechanics: a script extracted the 24 def blocks verbatim from the worker (8 contiguous regions, bottom-up cuts, blank-line runs collapsed to exactly 2), wrote worker_kernel.py (stdlib imports: os, datetime, urllib.parse.urlsplit) and deleted the regions from the worker; the re-export `from worker_kernel import (...)` (one ImportFrom, `# noqa: F401`, flat sibling style) was inserted before the ROAD_LIVE_SCHEMA constant block. The now-orphaned `from urllib.parse import urlsplit` import was removed from the worker (its only users moved).
3. Convergence: worker_kernel.py added to build_exact_artifacts ubuntu-worker+edge required lists, validate_exact_artifacts matching sets, validate_repo REQUIRED_FILES, and install-systemd.sh prepared-release required loop (fail-closed at install). rollback-exact.sh deliberately untouched (its check targets PREVIOUS releases that may predate the kernel). check_ubuntu_compatibility.py untouched (single-file gate, verified green).
4. Harness: tests/support/worker_source.py DEFAULT_WORKER_SOURCES gains worker/worker_kernel.py — the exact evolution path the #398 harness docstring reserved for the #397 waves; module_trees/extract_nodes/function_node then resolve moved names from the kernel and staying names from the worker; AST checks that target staying functions (main, draw_overlay, start_media_reader) are unaffected because the moved pieces were definitions, not call sites.
5. Integrity tests (tests/test_worker_kernel_module.py): (a) `python3 -I` subprocess import probe with only worker/ on sys.path (stdlib-only proof, fails on any future heavy import); (b) exact-list re-export surface check (sorted alias set == MOVED_NAMES, both drift directions); (c) moved defs live ONLY in the kernel, staying defs ONLY in the worker.
6. Verification battery: full discover (expected 923 OK skipped=4 = 920 + 3 new tests); focused runs (worker_contract/line_crossing/roi_pipeline/kernel_module); ruff with the CI config; validate_repo; validate_sdd; check_ubuntu_compatibility; runtime import probe of the worker module's re-export surface.

## Architecture

- worker_kernel.py: stdlib-only leaf module (imports NOTHING from the worker); intra-kernel calls (crossed_line→sign_with_deadzone, media_basic_auth_for_input→_media_input_scheme, flags→env_str, labels→env_float) resolve inside the kernel.
- hls_motion_yolo_worker_events.py: keeps ALL runtime code; worker functions calling moved helpers (fetch_remote_roi→get_roi_url/roi_basic_auth/_scale_norm_points/_maybe_scale_legacy_absolute, draw_overlay→format_detection_label/overlay_label_opacity/bbox_center, update_speed_lines_estimate→side_of_line/sign_with_deadzone, _resolve_frame_size→env_str/env_int, post_*→now_iso) resolve via module globals of the worker file where the re-export lives — runtime monkeypatching of worker-module attributes keeps working.
- Import cycle safety: worker_kernel imports nothing from the worker → no cycle; the worker's `from worker_kernel import ...` sits after the stdlib/third-party imports, sibling style.
- Test harness: tests/support/worker_source.py parses BOTH files; first definition wins if a name ever appeared twice (it does not); SEA_SPEED_WORKER_SOURCE override semantics unchanged.

## Decisions

- D-1: Verbatim byte-level move (script-extracted regions) instead of retyping: guarantees AST-identity, verified programmatically after the move against `git show HEAD`.
- D-2: The 24-name cut is exactly what the order lists AND survives the stdlib-only audit; the plan-note flag names that don't exist are recorded as non-existent in the spec (re-derivation over the stale map, per the work order).
- D-3: install-systemd.sh gets the kernel in its prepared-release required loop (fail-closed), while rollback-exact.sh does NOT: rollback targets an older complete release which is self-consistent by construction; adding a kernel requirement there would hard-break rollback to pre-#397 releases.
- D-4: `# noqa: F401` on the re-export import: the import IS the contract (re-export surface), and three moved names (is_yolo_half_enabled, is_yolo_classes_filter_enabled, crossed_line) were already defined-but-uncalled inside the worker at HEAD — the re-export preserves them for tests/monkeypatch/runtime API exactly as before.
- D-5: mypy strict adoption of worker_kernel deferred (mypy.ini invites it for new pure modules, but the CI mypy invocation lists explicit files; widening it is a #399-owner decision, not wave-1 scope).

## Correct-course

- Trigger: any existing pin/test failing after the move → fix the MOVE (per constraint 5), never the test. Observed: no test edits were needed; battery green on first run.
- Trigger: validator failure on artifact lists → fix the list (convergence), never weaken the validator. Observed: all four updated, all validators green.

## Affected contours

- Ubuntu Worker/relay: `worker/worker_kernel.py` (NEW), `worker/hls_motion_yolo_worker_events.py` (moved defs → re-export); shipped by the exact artifacts (`build_exact_artifacts` ubuntu-worker+edge) and installed by `deploy/worker/ubuntu/install-systemd.sh`; runtime verification lands with the next routine worker deploy.
- Control plane: `scripts/ci/validate_repo.py`, `scripts/quality/build_exact_artifacts.py`, `scripts/quality/validate_exact_artifacts.py` (required-list convergence only — additions).
- Test harness: `tests/support/worker_source.py` (DEFAULT_WORKER_SOURCES gains the kernel — designed #397 path), NEW `tests/test_worker_kernel_module.py`.
- SDD trio `specs/397-wave1-worker-kernel/` (+ durable progress file outside the repo tree).
- No change to: deploy/vps/**, api/**, frontend/**, .github/workflows/**, check_ubuntu_compatibility.py, rollback-exact.sh, any test pin, live worker host state.

## Validation

- AST equivalence: per-function `ast.dump` equality between `git show HEAD:worker/hls_motion_yolo_worker_events.py` and worker_kernel.py for all 24 names → "all 24 AST-identical: True" (observed before the first test run).
- Integrity: tests/test_worker_kernel_module.py 3/3 OK (isolated stdlib-only import probe via `python3 -I`; exact-list re-export check both directions; def placement).
- Focused: `python3 -m unittest tests.test_worker_kernel_module tests.test_worker_contract tests.test_line_crossing tests.test_worker_roi_pipeline` → `Ran 61 ... OK`.
- Full suite: `python3 -m unittest discover -s tests -p 'test_*.py'` → `Ran 923 tests ... OK (skipped=4)` = 920 + 3 new, ZERO test edits (observed by the orchestrator).
- `python3 -m ruff check . --config scripts/quality/ruff.toml` → clean (exit 0).
- `python3 scripts/ci/validate_repo.py` → passed; `python3 scripts/ci/validate_sdd.py` → passed (after the orchestrator completed the trio's house sections — spec Runtime feedback, plan Affected contours/Validation/Runtime feedback).
- `python3 scripts/worker/check_ubuntu_compatibility.py` → `compatible=True`, `forbidden_markers=[]` (untouched gate).
- Runtime import probe: `python3 -c "import sys; sys.path.insert(0,'worker'); import worker_kernel"` → 25 public exports.

## Runtime feedback

- RF-001: Operator actions expected: 0; this wave changes only the worker source layout (move-only) — runtime verification lands with the next routine Ubuntu-worker deploy (batched with wave 2, owner deploy gate); the orchestrator records runtime acceptance on issue #397.
- RF-002: Evidence: the next deploy-ubuntu-worker run for a post-#474 SHA shows the kernel shipped in the exact artifacts and both worker services restarting green; AST-equivalence and battery transcripts are recorded in the durable progress file.
