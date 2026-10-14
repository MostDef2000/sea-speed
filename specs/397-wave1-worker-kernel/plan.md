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

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: a missed re-export would break runtime main() call resolution or the test monkeypatch surface; integrity test (b) checks the re-export surface as an exact list in BOTH directions (missing re-export and extra re-export both fail), and the full battery runs every worker test unedited | Validation: tests/test_worker_kernel_module.py 3/3 OK; full discover battery green with ZERO test/pin edits | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: a hidden non-stdlib dependency inside a moved function would break the stdlib-only contract on the worker host; every candidate body was audited for imports/globals before the cut (write_passage_snapshot excluded for cv2, road_roi_enabled/parse_road_roi_polygon excluded for requests), and the isolated `python3 -I` import probe fails on any future heavy import | Validation: test (a) isolated-subprocess import probe OK; manual body audit recorded in the progress file | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: a pinned required-list miss (exact-artifact build/validate, validate_repo top-level required-files allowlist, install-systemd prepared-release check) would ship a payload without worker_kernel.py — failure surfaces at deploy boot instead of CI; all five convergence sites updated in the same diff (build_exact_artifacts ubuntu-worker+edge, validate_exact_artifacts matching sets, validate_repo REQUIRED_FILES, install-systemd.sh required loop), all validators run locally, install-systemd.sh fails closed at prepare-check, and the CI exact-artifact gate re-verifies at merge | Validation: validate_repo + validate_sdd (plain and --event) green at final head; artifact required lists verified to contain worker/worker_kernel.py in both build and validate | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: TECH | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: the #398 AST harness would lose sight of moved functions (function_node/extract_nodes raise "missing worker functions"); DEFAULT_WORKER_SOURCES now lists both worker files — the harness's designed #397 evolution path — so moved names resolve from the kernel and staying names from the worker | Validation: focused runs of every harness consumer (worker_contract, line_crossing, roi_pipeline, tracking_overlay, water_detection_pipeline, water_passage, analytics_profiles, frame_quality, rtsp_media_security) green | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the referenced decomposition line map (progress file) did not exist at wave start; the cut was re-derived from live source per the work order, and the durable progress file is (re)created at the workspace root with the verified line map for waves 2-3 | Validation: progress-397-worker-decomposition.md present OUTSIDE the git tree; git ls-files shows no progress file | Residual risk: LOW | Owner: Worker | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001, AC-003 | Level: unit | Priority: P1 | Evidence: tests/test_worker_kernel_module.py 3/3 OK (a: `python3 -I` stdlib-only probe; b: exact-list re-export check; c: moved/staying def placement)
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P1 | Evidence: per-function ast.dump equality HEAD vs worker_kernel.py for all 24 names ("all 24 AST-identical: True")
- TEST-003 | Covers: AC-003, AC-006 | Level: unit | Priority: P1 | Evidence: focused `python3 -m unittest tests.test_worker_kernel_module tests.test_worker_contract tests.test_line_crossing tests.test_worker_roi_pipeline` → Ran 61, OK
- TEST-004 | Covers: AC-006 | Level: integration | Priority: P1 | Evidence: full `python3 -m unittest discover -s tests -p 'test_*.py'` → Ran 923, OK (skipped=4), zero test edits
- TEST-005 | Covers: AC-004 | Level: integration | Priority: P1 | Evidence: validate_repo green; build/validate exact-artifact required lists contain worker/worker_kernel.py; validate_sdd plain and --event green at final head
- TEST-006 | Covers: AC-005 | Level: unit | Priority: P2 | Evidence: `python3 scripts/worker/check_ubuntu_compatibility.py` → compatible=True, forbidden_markers=[] (gate untouched)
- TEST-007 | Covers: AC-001 | Level: integration | Priority: P2 | Evidence: runtime import probe `python3 -c "import sys; sys.path.insert(0,'worker'); import worker_kernel"` → 25 public exports

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

Standing correction policy (pre-declared triggers, no event occurred during wave 1):
any existing pin/test failing after the move → fix the MOVE (constraint 5), never the test
(observed: no test edits were needed); validator failure on artifact lists → fix the list
(convergence), never weaken the validator (observed: all five sites updated, validators green).

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
- `python3 scripts/ci/validate_repo.py` → passed at final head; `python3 scripts/ci/validate_sdd.py` → passed (plain mode) AND `python3 scripts/ci/validate_sdd.py --event <synthetic PR event>` → passed ("PR specification linkage and delivery quality layer valid") — the event carries the wave-1 changed-file set against base f83a1ce4 and exercises the REQUIRED risk-profile quality layer (Risk profile/Test design/Correct-course check/Deployment transaction audit/traceability/DoD).
- `python3 scripts/worker/check_ubuntu_compatibility.py` → `compatible=True`, `forbidden_markers=[]` (untouched gate).
- Runtime import probe: `python3 -c "import sys; sys.path.insert(0,'worker'); import worker_kernel"` → 25 public exports.

## Runtime feedback

- RF-001: Operator actions expected: 0; this wave changes only the worker source layout (move-only) — runtime verification lands with the next routine Ubuntu-worker deploy (batched with wave 2, owner deploy gate); the orchestrator records runtime acceptance on issue #397.
- RF-002: Evidence: the next deploy-ubuntu-worker run for a post-#474 SHA shows the kernel shipped in the exact artifacts and both worker services restarting green; AST-equivalence and battery transcripts are recorded in the durable progress file.
- RF-003 (live, 2026-10-14): PR #475 head 4e8d7f0 passed CI 8/8 (zero non-success check runs on the exact head) and was squash-merged as 62524ee. The DoD CI markers below are therefore factually satisfied; the unchecked boxes were left pending because the early #477 auto-sync cycles superseded their flips. This merge re-examines the dir so the flow flips them — expected to be the first fully COMPLETING autonomous cycle (RF-013 synthetic fixtures, RF-014 REST reuse-refresh, RF-015 REST ref-push + polled final gate are all on main).

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: work order W-A1 for #397 wave 1 (move-only extraction scope); branch sdd/397-wave1-worker-kernel from origin/main f83a1ce4; install-systemd.sh is the only deploy/** change (prepared-release required check)
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker host state | Retry: NO | Rollback: NONE | Evidence: install-systemd.sh required loop now also demands worker/worker_kernel.py in the prepared release before any install step — a payload missing the kernel exits 4 before the live tree is touched (deploy/worker/ubuntu/install-systemd.sh required-loop check)
- TX-003 | Stage: MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: staged release discarded; currently-running worker services unchanged | Retry: NO | Rollback: the installer stages the release before service restart exactly as before; the kernel ships as one additional source file in the same staged tree, so the mutation pattern is unchanged — no new staging or promotion step | Evidence: install-systemd.sh install flow untouched apart from the required check; runtime verification lands with the next routine worker deploy (owner deploy gate)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: the next worker deploy's health gate (deploy-authorized.sh → verify-runtime-progression/check-worker-health) applies unchanged; this wave ships no runtime mutation itself
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: the worker's output/state contour (output/, state JSON) is untouched by the source-layout move; no state schema or write path changes
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging dirs may remain on abrupt kill only | Retry: NO | Rollback: NONE | Evidence: installer staging layout semantics unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: deployment/acceptance evidence for the next worker deploy is orchestrator-owned (DEPLOY-TRIGGER lane); this wave's repo-level evidence is the validator + battery transcripts in the durable progress file
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh contour DELIBERATELY UNCHANGED: it targets PREVIOUS complete releases which may predate the kernel (adding a kernel requirement there would break rollback to pre-#397 releases); a rollback target is self-consistent by construction — its own release tree contains its own worker sources | Evidence: deploy/worker/ubuntu/rollback-exact.sh:144 target_worker check unchanged; releases are self-contained exact artifacts
