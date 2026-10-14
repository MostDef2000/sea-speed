# Plan: wave-3 worker render — cv2 render/snapshot extraction (move-only)

- Issue: #397
- Specification: specs/397-wave3-worker-render/spec.md

## Implementation approach

1. RECON-established facts (re-derived from live source, per the work order): the cv2 render/snapshot cut resolves to exactly 3 defs — `crop_sharpness` (cv2.Laplacian), `draw_overlay` (cv2 drawing + get_profile/env_str + kernel label/opacity helpers; crossing counters arrive as the `crossing_summary` PARAMETER, no direct state access), `write_passage_snapshot` (cv2.imwrite + frame.shape) — in 3 non-contiguous regions. The remaining order-listed candidates were CHECKED and LEAVE (each recorded in the spec): `draw_roi_polygon` (free var `parse_road_roi_polygon` → `fetch_remote_roi` → requests), `draw_speed_lines_overlay` (first statement `fetch_speed_lines_config()` → requests.get + `_speed_lines_cache`), `crossing_overlay_summary` (no cv2; crossing-domain mutable caches; dynamically referenced via the `"crossing_overlay_summary" in globals()` guard in build_road_live_envelope). NO module-level constants are referenced by the moved defs (colors/offsets inline literals). REQUIRED_ENV_NAMES call sites do NOT move (render code reads only ANALYTICS_PROFILE/ROAD_CLEAN_OVERLAY — not required names). No entrypoint render-name seams exist (deploy/worker/ubuntu/*.py reference only start_media_reader/reader names).
2. Move-only mechanics: a script extracted the 3 regions verbatim with BOTTOM-UP cuts (write_passage_snapshot first, then draw_overlay, then crop_sharpness — original line indices stay valid after each deletion; a first-cut top-down order was caught by the post-move AST check during development, the worker was restored from HEAD and the cut re-run — the final proof is the verification below), wrote `worker/worker_render.py` (imports: cv2; `from analytics_profiles import get_profile`; `from worker_kernel import env_str, format_detection_label, overlay_label_opacity`) and deleted the regions from the worker; the re-export `from worker_render import (3 names)` (`# noqa: F401`, flat sibling style) was inserted after the wave-2 media re-export block, BEFORE first use (before the ROAD_LIVE_SCHEMA constant block). No orphaned worker imports resulted (cv2/numpy/requests all still used by staying code).
3. Gate extension: `MODULE_SOURCES` gains `worker/worker_render.py` (three entries). No other gate change — union scans, fail-closed missing-file checks and schema keys are unchanged from wave 2; the wave-2 negative tests use explicit paths and pass UNCHANGED (proving the extension is purely additive).
4. Convergence: worker_render.py added to build_exact_artifacts ubuntu-worker+edge required lists, validate_exact_artifacts matching sets, validate_repo REQUIRED_FILES, install-systemd.sh prepared-release required loop (fail-closed at install). rollback-exact.sh deliberately untouched (same rationale as waves 1-2).
5. SDD layer: validate_sdd GRANDFATHERED_PREFIX_COLLISIONS "397" set gains `397-wave3-worker-render` (exact-set equality — the scheduled break flagged by the wave-2 review; mirrors the 396 staged-wave precedent).
6. Harness: tests/support/worker_source.py DEFAULT_WORKER_SOURCES gains worker/worker_render.py (4 files, first-definition-wins); #398 pins resolve moved names from worker_render and staying names from the worker with ZERO pin edits (observed).
7. Integrity tests (tests/test_worker_render_module.py, 5 tests): import allowlist + no-network pin (requests/ultralytics/av/subprocess/socket forbidden at module level); exact-list re-export (both directions); def placement incl. the three recorded STAYS; gate three-file check.
8. Verification battery: full discover (observed 936 OK skipped=4 = 931 + 5 new); focused 6-module run (Ran 74, OK); ruff with the CI config; validate_repo; validate_sdd; gate CLI (three-file union evidence); py_compile of all four worker modules.

## Architecture

- worker_render.py: OFFLINE render layer over the kernel — imports worker_kernel (env_str/format_detection_label/overlay_label_opacity) and analytics_profiles (profile detection in draw_overlay's clean-overlay probe) plus cv2; NO numpy needed by the moved defs (np.array in draw_roi_polygon stays with it in the worker); no requests/ultralytics/av/subprocess (pinned by test).
- hls_motion_yolo_worker_events.py: keeps analytics/ROI/config-fetch/posting/road-live envelopes; staying functions calling moved helpers (main → crop_sharpness/draw_overlay/write_passage_snapshot) resolve via worker-module globals where the re-export lives (C-4: internal calls resolve PER-MODULE — e.g. crossing_overlay_summary's internal reads of _crossing_counts bind to the WORKER's globals, one more reason it stays; draw_overlay's internal calls to format_detection_label/overlay_label_opacity/env_str/get_profile bind to WORKER_RENDER's module globals = its own imports + re-exported kernel names, which is why those names are imported IN worker_render).
- Import cycle safety: worker_render imports worker_kernel + analytics_profiles, never the worker → no cycle; the worker's `from worker_render import ...` sits after the media re-export, sibling style.
- Gate scan model: REQUIRED_ENV_NAMES union across the THREE MODULE_SOURCES files — after the move the union is exactly the pre-wave-3 set (no required env call site moved); HLS_URL lives in worker_media, SEA_SPEED_API_URL/TOKEN/MODEL_NAME in the worker; draw_overlay's ANALYTICS_PROFILE/ROAD_CLEAN_OVERLAY env reads move to worker_render but are not required names.

## Decisions

- D-1: Verbatim byte-level move (script-extracted regions, bottom-up) instead of retyping: guarantees AST-identity, verified programmatically after the move against `git show HEAD` (3/3 identical, staying defs intact, zero duplicate defs). A top-down first cut was caught by the AST check and redone — recorded as evidence the proof gates work.
- D-2: `draw_roi_polygon` STAYS: its free variable `parse_road_roi_polygon` is requests-entangled (via fetch_remote_roi); move-only forbids the body edits that would be needed to decouple it; recording beats forcing.
- D-3: `draw_speed_lines_overlay` STAYS: same constraint set via `fetch_speed_lines_config` (requests + cache mutation). Both stay WITH their entanglements for the later config/posting wave, which can then move caller+callee together.
- D-4: `crossing_overlay_summary` STAYS (the order's CHECK resolves to LEAVE): no cv2, crossing-domain mutable state, and the build_road_live_envelope `globals()` dynamic reference — C-4 per-module resolution means the call binds against the defining module; keeping it in the worker preserves the exact dynamic-dispatch semantics probed today.
- D-5: No module-level constants move (none referenced — verified programmatically); the spec's "constants move" contingency is recorded as empty.
- D-6: Render allowlist = cv2/numpy/os/time/datetime/pathlib/typing + repo-pure worker_kernel/analytics_profiles; network/process imports (requests/ultralytics/av/subprocess/socket) are explicitly forbidden at module level by a dedicated test. No cv2-lazy check (cv2 is the layer's purpose — the media module's lazy-av analogue is the no-network pin).
- D-7: Contract transfers (work-order-sanctioned, not pin fixes): test_worker_kernel_module STAYING_NAMES loses draw_overlay/write_passage_snapshot/crop_sharpness (down to 4 names); test_worker_media_module STAYING_IN_WORKER loses the same three and gains the wave-3 STAYS draw_roi_polygon/draw_speed_lines_overlay — each transfer recorded here per the work order.
- D-8: validate_sdd GRANDFATHERED_PREFIX_COLLISIONS "397" gains the wave-3 dir — the scheduled exact-set break the wave-2 review flagged; mirrors the 396 staged-wave precedent.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: re-export surface drift would break runtime main() render call resolution or the test monkeypatch surface; integrity test checks the re-export surface as an exact list in BOTH directions (missing and extra both fail), and the full battery runs every worker test unedited | Validation: tests/test_worker_render_module.py re-export tests OK; full discover battery Ran 936 OK (skipped=4) with ZERO #398 pin edits | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: a free-variable sweep miss (moved body referencing a worker-module global that did not move) would NameError in the render path at runtime; a programmatic symtable free-variable check of worker_render found NONE unresolved, the staying worker's closure set was verified byte-identical to HEAD, and the focused overlay/ROI/line-crossing suites run green | Validation: symtable transcript in the progress file; focused Ran 74 OK; full battery Ran 936 OK | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 1 | Impact: 5 | Score: 5 | Mitigation: moving a module-level constant would change the monkeypatch surface (per-module resolution, C-4); the contingency was verified EMPTY — no module-level constants are referenced by the moved defs (all overlay colors/offsets are inline literals); C-4 per-module monkeypatch semantics are documented in this trio and the re-export keeps worker-module attribute access intact | Validation: free-variable/constant sweep observed empty; exact-list + battery green | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-004 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: a pinned required-list miss (exact-artifact build/validate, validate_repo top-level required-files allowlist, install-systemd prepared-release check) would ship a payload without worker_render.py — failure at deploy boot instead of CI; all four convergence sites updated in the same diff, all validators run locally, install-systemd.sh fails closed at prepare-check, and the CI exact-artifact gate re-verifies at merge | Validation: validate_repo green at final head; artifact required lists verified to contain worker/worker_render.py in both build and validate | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-005 | Category: TECH | Probability: 1 | Impact: 5 | Score: 5 | Mitigation: the gate extension could narrow the scan or miss a surface; the three-file union is purely additive — the wave-2 negative unit tests (explicit-path) pass UNCHANGED, and a new unit test pins MODULE_SOURCES == 3 entries with all files present and the union compatible; the gate CLI probe shows the union env set across the three files | Validation: tests/test_worker_render_module.py gate test OK; wave-2 gate tests green unedited; CLI transcript compatible=True | Residual risk: LOW | Owner: Worker | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P1 | Evidence: per-function ast.dump equality HEAD vs worker_render.py for all 3 defs ("AST-identical moved=3: True; gone from worker: True; staying defs intact: True")
- TEST-002 | Covers: AC-002, AC-003 | Level: unit | Priority: P1 | Evidence: tests/test_worker_render_module.py — re-export exact-list (both directions), def placement incl. the three STAYS, import allowlist, no-network pin — 4/4 OK
- TEST-003 | Covers: AC-001 | Level: unit | Priority: P1 | Evidence: symtable free-variable check of worker_render → NONE unresolved; worker closure set byte-identical to HEAD's
- TEST-004 | Covers: AC-004, AC-006 | Level: unit | Priority: P1 | Evidence: gate three-file unit test + focused 6-module run → Ran 74, OK
- TEST-005 | Covers: AC-006 | Level: integration | Priority: P1 | Evidence: full `python3 -m unittest discover -s tests -p 'test_*.py'` → Ran 936, OK (skipped=4) = 931 + 5 new, zero #398 pin edits
- TEST-006 | Covers: AC-005, AC-006 | Level: integration | Priority: P1 | Evidence: validate_repo green; build/validate exact-artifact required lists contain worker/worker_render.py (ubuntu-worker AND edge); validate_sdd green with the extended grandfather set; ruff clean
- TEST-007 | Covers: AC-004 | Level: unit | Priority: P2 | Evidence: `python3 scripts/worker/check_ubuntu_compatibility.py` → compatible=True, forbidden_markers=[], three-file union evidence (worker=…worker_media, …worker_render)
- TEST-008 | Covers: AC-006 | Level: unit | Priority: P2 | Evidence: py_compile of worker_render.py + the other three worker modules → OK

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

Standing correction policy (pre-declared triggers, no unresolved event during wave 3):
any existing #398 pin failing after the move → fix the MOVE, never the test (observed:
zero pin edits); wave-1/wave-2 STAYING-list changes are contract transfers required by
the work order, recorded as D-7 (recorded per transfer); validator failure on artifact
lists → fix the list (convergence), never weaken the validator (observed: all four sites
updated + validate_sdd grandfather entry, validators green); a failed cut (top-down
order corrupted a staying region during development) → restore from HEAD, fix the
MECHANICS, re-verify AST identity before proceeding (observed: final state verified
"AST-identical moved=3: True; staying defs intact: True").

## Affected contours

- Ubuntu Worker/relay: `worker/worker_render.py` (NEW), `worker/hls_motion_yolo_worker_events.py` (3 moved defs → re-export); shipped by the exact artifacts (build_exact_artifacts ubuntu-worker+edge) and installed by deploy/worker/ubuntu/install-systemd.sh; runtime verification lands with the next routine worker deploy.
- Control plane: `scripts/worker/check_ubuntu_compatibility.py` (MODULE_SOURCES third entry — semantics unchanged); `scripts/ci/validate_repo.py`, `scripts/quality/build_exact_artifacts.py`, `scripts/quality/validate_exact_artifacts.py` (required-list convergence only — additions); `scripts/ci/validate_sdd.py` (397 grandfather set).
- Test harness: `tests/support/worker_source.py` (DEFAULT_WORKER_SOURCES gains the render module), NEW `tests/test_worker_render_module.py`, `tests/test_worker_kernel_module.py` + `tests/test_worker_media_module.py` (contract transfers, D-7).
- SDD trio `specs/397-wave3-worker-render/` (+ durable progress file outside the repo tree).
- No change to: deploy/vps/**, api/**, frontend/**, .github/workflows/**, rollback-exact.sh, entrypoint files (no render seams), any #398 test pin, live worker host state.

## Validation

- AST equivalence: per-function `ast.dump` equality between `git show HEAD:worker/hls_motion_yolo_worker_events.py` and worker_render.py for all 3 defs → "AST-identical moved=3: True; gone from worker: True; staying defs intact: True; re-exported-identical: True" (observed after the corrected bottom-up cut).
- Free-variable proof: symtable scan of worker_render → "render free vars unresolved: NONE"; worker free-var set byte-identical to HEAD's (15 pre-existing closure entries, unchanged).
- Integrity: tests/test_worker_render_module.py 5/5 OK (allowlist, no-network, re-export both directions, placement incl. STAYS, gate three-file).
- Focused: render_module + kernel_module + media_module + worker_contract + line_crossing + roi_pipeline → `Ran 74 ... OK`.
- Full suite: `python3 -m unittest discover -s tests -p 'test_*.py'` → `Ran 936 tests ... OK (skipped=4)` = 931 + 5 new, ZERO #398 pin edits (observed; delta = 5 new tests in test_worker_render_module.py).
- `ruff check . --config scripts/quality/ruff.toml` → clean ("All checks passed!").
- `python3 scripts/ci/validate_repo.py` → passed at final head.
- `python3 scripts/ci/validate_sdd.py` → passed (plain mode) at final head with the extended 397 grandfather set; the orchestrator's --event run uses the same trio (`- Specification: specs/397-wave3-worker-render/spec.md` + `- Risk profile: REQUIRED` present).
- `python3 scripts/worker/check_ubuntu_compatibility.py` → `compatible=True`, `forbidden_markers=[]`, three-file union evidence in the transcript.
- py_compile: all four worker modules compile clean.

## Runtime feedback

- RF-001: Operator actions expected: 0; this wave changes only the worker source layout (move-only) plus gate/validator coverage — runtime verification lands with the next routine Ubuntu-worker deploy (batched with wave 4+, owner deploy gate); the orchestrator records runtime acceptance on issue #397.
- RF-002: Evidence: the next deploy-ubuntu-worker run for a post-wave-3 SHA shows the render module shipped in the exact artifacts and both worker services restarting green; AST-equivalence, symtable and battery transcripts are recorded in the durable progress file.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: work order W-A3 for #397 wave 3 (move-only render extraction + gate third-file scope); branch sdd/397-wave3-worker-render from origin/main ea0b41ef; install-systemd.sh is the only deploy/** change (prepared-release required check)
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged worker host state | Retry: NO | Rollback: NONE | Evidence: install-systemd.sh required loop now also demands worker/worker_render.py in the prepared release before any install step — a payload missing the render module exits 4 before the live tree is touched
- TX-003 | Stage: MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: staged release discarded; currently-running worker services unchanged | Retry: NO | Rollback: the installer stages the release before service restart exactly as before; the render module ships as one additional source file in the same staged tree — the mutation pattern is unchanged | Evidence: install-systemd.sh install flow untouched apart from the required check; runtime verification lands with the next routine worker deploy (owner deploy gate)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: the next worker deploy's health gate (deploy-authorized.sh → verify-runtime-progression/check-worker-health) applies unchanged; this wave ships no runtime mutation itself
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: the worker's output/state contour (output/, state JSON) is untouched by the source-layout move; snapshot write paths move as code but keep identical behavior/targets
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging dirs may remain on abrupt kill only | Retry: NO | Rollback: NONE | Evidence: installer staging layout semantics unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: deployment/acceptance evidence for the next worker deploy is orchestrator-owned (DEPLOY-TRIGGER lane); this wave's repo-level evidence is the validator + battery + gate transcripts in the durable progress file
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh contour DELIBERATELY UNCHANGED (same rationale as waves 1-2): it targets PREVIOUS complete releases which may predate the render module; a rollback target is self-consistent by construction — its own release tree contains its own worker sources | Evidence: deploy/worker/ubuntu/rollback-exact.sh untouched in this diff; releases are self-contained exact artifacts
