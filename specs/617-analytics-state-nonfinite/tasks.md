# Tasks — Issue #617 analytics-state non-finite boundary guard

- Issue: #617
- Specification: specs/617-analytics-state-nonfinite/spec.md

## Delivery tasks

- T-1: api/app/main.py — post_analytics_state dual non-finite boundary
  scans: EARLY scan (store.find_nonfinite_json_value → HTTPException 400
  with the offending path, exact #587 idiom) immediately before the overlay
  media write (main.py:768) so a rejected request writes nothing, and FINAL
  scan immediately before the upsert_camera_state persist call (main.py:
  795) — kept because the no-overlay branch merges overlay_rev from
  old_state, which can carry NaN from pre-fix rows; store.py untouched.
  DONE.
- T-2: tests/test_617_analytics_state_nonfinite.py — 6 tests / 1 class
  (handler-level exec harness over the REAL post_analytics_state with the
  REAL api.app.store persist path; only auth/identity/clock/overlay-upload
  seams stubbed; no third-party imports so the import-hygiene registry in
  tests/test_run_tests_script.py needs no change), incl. the overlay pin
  (rejected request carrying an overlay leaves the sentinel overlay file
  byte-unchanged, no .tmp stray) and the final-scan pin (dirty stored row
  with overlay_rev NaN seeded via the REAL store.upsert_camera_state +
  finite no-overlay POST → 400 from the FINAL scan, dirty row
  byte-unchanged), RED on base 358a2ff verified (byte-identical test file
  with main.py at base → FAILED failures=12, bare NaN/Infinity persisted +
  overlay media file written + dirty-row NaN re-persisted), byte-unchanged
  through the fix. DONE.
- T-3: specs/617-analytics-state-nonfinite/ trio (this spec/plan/tasks).
  DONE.

## Battery identity

Baseline at base 358a2ff without the new file: 1406 passed / 2 skipped.
Delta: +6 tests in tests/test_617_analytics_state_nonfinite.py — expected
1412 passed / 2 skipped. Observed: recorded in the completion gate below.

## Completion gate

- Focused `python3 -W error::ResourceWarning -m unittest tests.test_617_analytics_state_nonfinite -v`: OBSERVED 6/6 tests OK with the fix (EXIT=0).
- RED differential (byte-identical test file, sha256 64f964d9, with api/app/main.py reverted to base 358a2ff — both scans removed): OBSERVED FAILED (failures=12) — bare NaN/Infinity persisted into camera_state.payload_json, the rejected overlay-carrying request overwrote the overlay media file, and the finite POST against the dirty stored row re-persisted the stored NaN overlay_rev — RED authenticity; fix restored byte-identical afterwards (regenerated diff byte-identical to the saved fix-v3.patch).
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'`: OBSERVED 1412 tests OK (skipped=2).
- ruff `RUFF_CACHE=/tmp/opencode/toolcache/sea-speed ruff check --config scripts/quality/ruff.toml api/app/main.py tests/test_617_analytics_state_nonfinite.py`: OBSERVED "All checks passed!".
- `python3 scripts/ci/validate_sdd.py`: OBSERVED pass (EXIT=0) with this trio.

## Requirements traceability

- AC-001 | Task: T-1+T-2 | Evidence: NaN nested (dict / list element / top level) → 400 with offending path, no state change (exec-harness pins over the real persist path) + RED differential (FAILED failures=12 on base 358a2ff — payload persisted with bare NaN token) | Coverage: COVERED
- AC-002 | Task: T-1+T-2 | Evidence: ±Infinity nested dict/list pins plus the 1e999 / -1e999 JSON overflow literals (parsed by json.loads to ±inf) → 400, no state change | Coverage: COVERED
- AC-003 | Task: T-1+T-2 | Evidence: test_rejection_causes_no_state_change — seeded finite camera_state byte-identical after rejected NaN/1e999 POSTs; fresh camera gets no camera_state row (no upsert ran) | Coverage: COVERED
- AC-004 | Task: T-1+T-2 | Evidence: test_rejection_with_overlay_writes_nothing — rejected request carrying an overlay → 400 with the sentinel overlay file byte-unchanged and no .tmp stray (RED on base: request succeeded, sentinel overwritten) — pins the EARLY scan placement | Coverage: COVERED
- AC-005 | Task: T-1+T-2 | Evidence: finite-payload pin — floats (1.5, 10.5, 2.5), ints, strings, null, bools, nested lists/dicts and exact large int 10**30 persist exactly as before; stored payload_json free of NaN/Infinity tokens and round-trips to the merged state | Coverage: COVERED
- AC-006 | Task: T-1+T-2 | Evidence: exact detail assertions — f"{path} must be a finite number" with dotted paths into the payload structure (metadata.telemetry.speed_kmh, metadata.detections[1].conf, metadata.quality, metadata.values[1], metadata.speed), matching the #587 rejection idiom | Coverage: COVERED
- AC-007 | Task: T-1+T-2+T-3 | Evidence: full battery 1412 OK (skipped=2; baseline 1406), ruff clean, validate_sdd green, RED differential failures=12 on base 358a2ff (observed outputs in the completion gate); store.py untouched, no new guarded-optional import (test file imports stdlib + repo-local api.app.store only) | Coverage: COVERED
- AC-008 | Task: T-1+T-2 | Evidence: test_final_scan_rejects_nan_overlay_rev_from_dirty_stored_row — dirty stored row (overlay_rev NaN, seeded via the REAL store.upsert_camera_state) + finite no-overlay POST without overlay_rev → 400 detail "metadata.overlay_rev must be a finite number" from the FINAL scan, dirty row byte-unchanged (RED on base: request succeeded, NaN re-persisted merged from old_state — pins the FINAL scan placement) | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (api/app/main.py + tests/test_617_analytics_state_nonfinite.py + this trio)
- [x] Required tests and evidence complete
- [ ] Required CI green — pending exact-head CI on the merge PR — auto-synced on merge to main
- [ ] Exact-green-head merge complete — pending squash merge to main — auto-synced on merge to main
- [ ] Deployment state resolved (lane-A VPS API contour)
- [ ] Runtime acceptance resolved (health/signature probes + unauthenticated non-finite state POST intercepted by auth boundary, post-deploy)
- [x] Deferred work recorded (pre-fix rows with bare NaN/Infinity tokens are not migrated — RF-002; boundary-only scope)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
