# Spec: wave-3 worker render — cv2 render/snapshot extraction (move-only)

- Issue: #397
- Specification: specs/397-wave3-worker-render/spec.md

## Product outcome

Waves 1-2 extracted the pure kernel (#475) and the media/reader layer (#476); the worker still mixes the cv2 render/snapshot layer (frame overlay drawing, passage snapshot writing, sharpness metric) with analytics/config-fetch/posting logic. Wave 3 extracts the render/snapshot layer verbatim into NEW `worker/worker_render.py` (3 defs: `crop_sharpness`, `draw_overlay`, `write_passage_snapshot` — AST-identical bodies verified against HEAD before the first write) and extends the compatibility gate's `MODULE_SOURCES` to the three-file union (worker + worker_media + worker_render; gate semantics unchanged, fail-closed preserved).

The full order cut was re-derived from live source and THREE candidates deliberately STAY (recorded, not silently dropped):
- `draw_roi_polygon` — its only non-builtin free variable is `parse_road_roi_polygon`, which calls `fetch_remote_roi` (requests-entangled, staying). Moving it would require either a requests import in the render module (forbidden by the allowlist) or a worker back-import (circular — the worker imports worker_render at module level) or a body edit (forbidden by move-only).
- `draw_speed_lines_overlay` — its first statement is `fetch_speed_lines_config()` (requests.get + `_speed_lines_cache` mutation, staying). Same constraint set → stays.
- `crossing_overlay_summary` — the CHECK resolves to LEAVE: it touches no cv2 and is a crossing-DOMAIN state reader (`_crossing_counts`/`_crossings_by_class`/`_crossing_line_cache`, all module-level mutables mutated in place by staying functions), AND it is dynamically referenced via the `"crossing_overlay_summary" in globals()` guard in `build_road_live_envelope` — moving it would push the call through the re-export binding and change the dynamic-dispatch surface the envelope builder probes (C-4: internal calls resolve PER-MODULE; the globals() guard tests the WORKER module's namespace by design).
No module-level constants are referenced by the moved defs (all overlay colors/offsets are inline literals) — the "constants move + re-export" contingency is empty, verified programmatically. `post_state`/`post_event`/`post_passage` stay (requests/posting = later wave).

## User scenarios

- US-1: the runtime worker boots on the Ubuntu worker host → `import worker_render` resolves as a flat sibling (shipped by the exact artifacts and the installer) → `main()`'s `crop_sharpness`/`draw_overlay`/`write_passage_snapshot` call sites keep resolving via the worker re-export → rendered frames and snapshots byte-identical to pre-split.
- US-2: a test patches `worker.draw_overlay` (monkeypatch surface) → the re-export keeps the binding on the worker module → patch semantics unchanged; per-module resolution (C-4) means internal render-module calls bind to worker_render's globals — documented in this trio for wave-4+ planning.
- US-3: the #398 AST harness extracts `draw_overlay` (or any moved helper) → DEFAULT_WORKER_SOURCES (now 4 files) resolves it from worker_render.py → existing pins pass UNTOUCHED (observed: focused + full battery green with zero pin edits).
- US-4: CI/validators run → the exact-artifact required lists (ubuntu-worker AND edge), validate_repo REQUIRED_FILES and the installer's prepared-release check all include worker/worker_render.py → a payload missing the render module fails closed at CI or install, never at boot.
- US-5: the compatibility gate's three-file union → REQUIRED_ENV_NAMES call sites all resolve (verified: none of HLS_URL/SEA_SPEED_API_URL/SEA_SPEED_API_TOKEN/MODEL_NAME moved — render code reads only ANALYTICS_PROFILE/ROAD_CLEAN_OVERLAY via env_str, names not in REQUIRED_ENV_NAMES; the union stays green); a missing worker_render.py fails closed.
- US-6: a future contributor adds `import requests` (or ultralytics/av/subprocess) to worker_render.py module level → the import-allowlist + no-network tests fail in CI instead of silently coupling the offline render layer to fetch/spawn surfaces.

## Scope

- NEW `worker/worker_render.py`: header docstring + imports (cv2; `from analytics_profiles import get_profile`; `from worker_kernel import env_str, format_detection_label, overlay_label_opacity`) + 3 moved defs, bodies byte-identical to HEAD.
- `worker/hls_motion_yolo_worker_events.py`: ONLY — remove the 3 moved def blocks (3 regions); add the flat sibling re-export `from worker_render import (3 names)` with a wave-3 comment AFTER the existing re-export blocks, BEFORE first use (before the ROAD_LIVE_SCHEMA constant block). No logic edits, no renames, no signature changes anywhere.
- `scripts/worker/check_ubuntu_compatibility.py`: `MODULE_SOURCES` gains `worker/worker_render.py` (three-file union scan; REQUIRED_ENV_NAMES/import/Popen/forbidden semantics unchanged; fail-closed missing-file preserved). NO weakening.
- Convergence lists: `scripts/ci/validate_repo.py` REQUIRED_FILES; `scripts/quality/build_exact_artifacts.py` ubuntu-worker + edge required; `scripts/quality/validate_exact_artifacts.py` ubuntu-worker + edge required sets; `deploy/worker/ubuntu/install-systemd.sh` prepared-release required loop. `rollback-exact.sh` untouched.
- `scripts/ci/validate_sdd.py`: GRANDFATHERED_PREFIX_COLLISIONS "397" set gains `397-wave3-worker-render` (exact-set equality requirement — the scheduled break flagged by the wave-2 review; mirrors the 396 staged-wave precedent).
- `tests/support/worker_source.py`: DEFAULT_WORKER_SOURCES gains `worker/worker_render.py` (4 files, first-definition-wins). No #398 pin edits.
- NEW `tests/test_worker_render_module.py`: (a) render import-allowlist AST check (top-level ⊆ cv2/numpy/os/time/datetime/pathlib/typing + worker_kernel/analytics_profiles); (b) NO-network-imports pin (requests/ultralytics/av/subprocess/socket forbidden at module level — the render analogue of the media lazy-av check; no cv2-lazy check since cv2 is deliberate); (c) exact-list re-export check (both directions); (d) def placement (moved only in render; the three STAYS plus detect_vehicles/fetch_remote_roi/main/post_state/post_event/post_passage remain only in the worker; nothing render-shaped in kernel/media); (e) gate three-file check (MODULE_SOURCES == 3 entries, all present, union compatible).
- Contract transfers (work-order-sanctioned, not pin fixes): `tests/test_worker_kernel_module.py` STAYING_NAMES loses `draw_overlay`/`write_passage_snapshot`/`crop_sharpness` (now guarded by the render test); `tests/test_worker_media_module.py` STAYING_IN_WORKER loses the same three and gains the wave-3 STAYS `draw_roi_polygon`/`draw_speed_lines_overlay`.
- SDD trio `specs/397-wave3-worker-render/` and the durable progress file (workspace root, outside git).
- OUT of scope: any behavior change in worker/**; `draw_roi_polygon`/`draw_speed_lines_overlay`/`crossing_overlay_summary` (recorded STAYS, see above); post_state/post_event/post_passage + fetch_* config family (requests — later wave); `.github/workflows/**`; `api/**`; `frontend/**`; mypy adoption of worker_render (deferred, #399-owner decision); entrypoint files (no render-name seams exist there — verified).

## Requirements

- R-1 (AC-001): all 3 moved defs are AST-identical to HEAD; no renames, no signature changes, no logic edits.
- R-2 (AC-002): the runtime worker re-exports exactly the 3 moved names via one flat sibling ImportFrom placed after the media re-export and before first use; the exact-list check fails on drift in either direction; moved defs exist ONLY in worker_render; staying defs remain ONLY in the worker; nothing render-shaped leaks into kernel/media.
- R-3 (AC-003): worker_render.py top-level imports stay within the render allowlist and contain NO network/process imports (requests/ultralytics/av/subprocess/socket forbidden).
- R-4 (AC-004): the compatibility gate scans THREE worker sources with union semantics; REQUIRED_ENV_NAMES resolve across the union (verified: no required env-name call site moved); missing file fails closed; schema keys unchanged; no weakening.
- R-5 (AC-005): all four convergence lists include `worker/worker_render.py`; the validate_sdd 397 grandfather set includes the wave-3 dir; validators stay green; rollback-exact.sh untouched.
- R-6 (AC-006): full unittest battery passes with NO #398 pin edits; expected 936 tests (931 + 5 new render-module tests), skipped=4; ruff, validate_repo and validate_sdd green.

## Acceptance criteria

- AC-001: per-function `ast.dump` equality between HEAD worker source and worker_render.py for all 3 defs (observed: "AST-identical moved=3: True; gone from worker: True; staying defs intact: True; re-exported-identical: True").
- AC-002: `tests/test_worker_render_module.py` re-export surface tests pass; alias set equals MOVED_RENDER_NAMES exactly; STAYS verified present in worker only.
- AC-003: import-allowlist test passes; no-network-imports test passes.
- AC-004: gate three-file union scan compatible=True with missing_required_environment_names=[] (CLI + unit); wave-2 negative tests still pass unchanged (two-file explicit-path calls unaffected).
- AC-005: validate_repo, build_exact_artifacts + validate_exact_artifacts (ubuntu-worker AND edge), and the install-systemd prepared-release loop all reference worker/worker_render.py; validate_sdd passes with the extended grandfather set.
- AC-006: full discover battery: 936 tests, OK (skipped=4); focused: render_module + kernel_module + media_module + worker_contract + line_crossing + roi_pipeline → Ran 74, OK; ruff `--config scripts/quality/ruff.toml` passes; py_compile of all four worker modules passes.

## Runtime feedback

- RF-001: Operator actions expected: 0; this wave changes only the worker source layout (move-only) plus gate/validator coverage — runtime verification lands with the next routine Ubuntu-worker deploy (batched with wave 4+, owner deploy gate); the orchestrator records runtime acceptance on issue #397.
- RF-002: Evidence: the next deploy-ubuntu-worker run for a post-wave-3 SHA shows the render module shipped in the exact artifacts and both worker services restarting green; AST-equivalence, symtable and battery transcripts are recorded in the durable progress file.

## NFR assessment

- NFR-001 | Area: reliability/operations | Target: move-only equivalence — rendered overlays, passage snapshots and sharpness metrics byte-identical: same bodies (AST-identical), same global-name resolution via re-export, monkeypatch surface preserved (C-4 per-module resolution documented) | Validation: AST-dump equality vs HEAD for all 3 defs; symtable free-variable check (NONE unresolved, worker closure set byte-identical to HEAD); full battery green with zero pin edits | Evidence: transcripts in the progress file | Status: PASS
- NFR-002 | Area: maintainability | Target: the render layer is an OFFLINE unit with a POLICED dependency surface — cv2 + repo-pure siblings only, no network/process imports | Validation: AST import-allowlist + no-network unit tests | Evidence: tests/test_worker_render_module.py OK | Status: PASS
- NFR-003 | Area: security | Target: no new exposure — the render layer draws and writes snapshots exactly as before (same bodies); forbidden-marker scan now covers THREE worker files; no secrets introduced; artifact lists only ADD a source file | Validation: diff inspection; gate CLI (forbidden_markers=[] across the union); validators green | Evidence: git diff reviewed; gate transcript | Status: PASS
- NFR-004 | Area: compatibility | Target: gate extension strictly ADDITIVE (third file joins the union; wave-2 semantics untouched — verified by wave-2 tests passing UNCHANGED); validate_sdd exact-set break resolved by the scheduled grandfather addition; all SDD validators green at final head | Validation: wave-2 gate tests green unedited; validate_sdd plain green | Evidence: transcripts in the progress file | Status: PASS

## Risks

| ID | Risk | Score (P×I) | Mitigation |
|---|---|---|---|
| RISK-1 | Re-export surface drift breaks main() render call resolution or the monkeypatch surface | 2×5=10 | Integrity test: exact-list re-export check in both directions + full battery (all worker tests green untouched) |
| RISK-2 | Free-variable sweep miss → runtime NameError in the render path (a moved body referencing a worker-module global that did not move) | 2×5=10 | Programmatic symtable sweep of worker_render (NONE unresolved) + worker closure set byte-identical to HEAD + full battery + focused overlay/ROI tests |
| RISK-3 | Module-level constant move changes the monkeypatch surface | 1×5=5 | Contingency verified EMPTY: no module-level constants are referenced by the moved defs (colors/offsets are inline literals); C-4 per-module resolution documented in this trio; re-export preserves worker-module attribute access |
| RISK-4 | Convergence list miss fails CI or ships a payload without worker_render.py (failure at deploy boot instead of CI) | 2×5=10 | All four convergence sites updated in the same diff; all validators run locally; install-systemd.sh fails closed at prepare-check; CI exact-artifact gate re-verifies at merge |
| RISK-5 | Gate extension misses a scan surface (three-file union silently narrower than the two-file reality) | 1×5=5 | Wave-2 negative tests pass UNCHANGED (they use explicit paths); new three-file unit test asserts MODULE_SOURCES == 3 entries, all files present, union compatible=True; gate CLI probe shows the union env set |
