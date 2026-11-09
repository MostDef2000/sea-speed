# Plan — Issue #617 analytics-state non-finite boundary guard

- Issue: #617
- Specification: specs/617-analytics-state-nonfinite/spec.md

## Architecture

Guard at two placements in `post_analytics_state`
(api/app/main.py:748), both using the existing #587 helper
``store.find_nonfinite_json_value(data)`` (api/app/store.py:390 — returns
the offending dotted path or None; deliberately fastapi-free) and raising
``HTTPException(400, f"{path} must be a finite number")`` — the exact
rejection idiom of the two sibling #587 sites in the same file
(post_cam1_passage measurement_meta guard, main.py:550; post_analytics_event
guard, main.py:829). ``upsert_camera_state`` serializes with
``json.dumps``'s default ``allow_nan=True``, so an unscanned NaN/±Infinity
leaf lands as a bare NaN/Infinity token in ``camera_state.payload_json`` —
invalid strict JSON for JS clients. The EARLY scan (main.py:768) sits
immediately before the overlay media write (tmp write + os.replace of
``{camera_id}_latest_overlay.jpg``), so a rejected request writes nothing —
the #587 AC-2 standard for this defect class (rejected input causes NO state
change, media included). The FINAL scan (main.py:795, immediately before the
``upsert_camera_state`` call at main.py:800) stays because the no-overlay
branch merges ``overlay_rev`` from ``old_state``, which can carry NaN from
pre-fix rows — an early-only scan would let that propagate into the
persisted payload (the exact defect #617 targets). Both scans run on the
merged ``data`` (the exact object handed to the upsert); all
handler-injected fields are finite, so any offending path points into the
worker-supplied payload structure. store.py is not modified.

## Decisions

- **Boundary guards before every write, mirroring #587**: the two sibling
  persist paths (measurement_meta, deliver_event) already reject non-finite
  input at the boundary with the offending path in the detail; the
  analytics-state upsert gets the identical idiom so all three verbatim
  persist paths behave uniformly. The EARLY guard sits before the overlay
  media write (a rejected request writes nothing — #587 AC-2 standard,
  media included); the FINAL guard sits right before the persist call (the
  last write the handler performs), so a rejection cannot be followed by
  any store mutation.
- **Existing helper, no store.py change**: ``find_nonfinite_json_value``
  (#587) already returns the offending dotted path; re-using it keeps the
  fix to +8 lines in main.py and keeps store.py importable in CI
  (fastapi-free) for the exec harness.
- **Handler-level exec harness instead of TestClient**: the regression pins
  run the REAL ``post_analytics_state`` (AST-extracted from api/app/main.py,
  ``@app.post`` route decorator stripped — registration seam, not handler
  code) with the REAL ``api.app.store`` module bound into the namespace, so
  the actual persist path (``upsert_camera_state`` →
  ``camera_state.payload_json`` bytes) is exercised, not a stubbed sink; only
  the auth/identity/clock seams and the fastapi Form/File/Header
  decorator-arg seam are stubbed. A TestClient variant would need
  guarded-optional fastapi/httpx tuples registered in
  tests/test_run_tests_script.py's pinned import-hygiene list
  (test_guarded_optional_probe_is_the_fastapi_stub_fallback), which lives
  outside this fix's allowed paths — the handler-level harness pins the same
  defect without a third-party import, so the one-process battery stays
  green and the import-hygiene gate is not gamed with scanner-invisible
  dynamic imports (tests/test_616_optional_int_overflow.py precedent).
- **Dual placement (early + final), orchestrator decision on the flagged
  nuance**: the single pre-persist guard left the overlay media write
  (tmp write + os.replace) unguarded — a rejected request carrying an
  overlay mutated the overlay file, violating the #587 no-state-change
  standard for this defect class. The early scan closes that; the final
  scan is NOT redundant: the no-overlay branch copies ``overlay_rev`` from
  ``old_state``, which can carry NaN from pre-fix rows, and an early-only
  scan would let that propagate into the persisted payload (the exact
  defect #617 targets).
- **No stored-data migration**: rows written before the fix may already
  contain bare NaN/Infinity tokens; #617 scopes the boundary only (RF-002).

## Affected contours

- API (deployed to VPS — release contour): api/app/main.py (+10, dual
  non-finite scans in post_analytics_state: early scan before the overlay
  media write at main.py:768, final scan before the upsert at main.py:795).
- Control plane: tests/test_617_analytics_state_nonfinite.py (new, 6 tests),
  this SDD trio. Nothing else — no store.py/analytics.py/
  objects_registry.py, no other tests, worker/, frontend/, deploy/,
  scripts/, .github/ changes.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the guard is a strictly additive pre-check before the persist call, reusing the #587-delivered helper unchanged; finite payloads keep their exact behavior (floats/ints/strings/null/bools/nested structures/exact large ints pinned byte-level through the real SQLite persist); the scan runs on the same merged dict the upsert receives, so no persist path is bypassed | Validation: tests/test_617_analytics_state_nonfinite.py + test_587_nonfinite_residual_paths.py + full battery | Residual risk: a future persist path for camera state bypassing post_analytics_state could reintroduce the gap — the #617 test file pins the known site | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: DATA | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the guard rejects before any write, so no partial state is possible (single upsert, no read-modify-write); workers posting non-finite payloads previously got 200 + invalid strict JSON at rest and now get an explicit 400 with the offending path — a behavior tightening, not a break; pre-existing legacy rows with bare tokens are explicitly out of scope (RF-002) and are not touched | Validation: no-state-change pins (seeded state byte-identical, fresh camera gets no row) + full battery | Residual risk: historical rows written before the fix may still contain bare tokens — recorded as out-of-scope in spec RF-002 | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: rides the normal VPS release contour with automatic rollback on failed gates; no schema/deploy plumbing changes; the previously-accepted non-finite payload path now answers 400 (strictly less invalid data at rest) | Validation: full battery + ruff + validate_sdd green before merge; post-deploy external probes (GET /, /sea-speed/, /sea-speed/api/health signatures + unauthenticated non-finite POST intercepted by the auth boundary) | Residual risk: standard release-contour deploy risk | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: integration | Priority: P0 | Evidence: tests/test_617_analytics_state_nonfinite.py test_nan_nested_in_payload_rejected_400_with_offending_path — NaN nested in dict / list element / top level → 400 with the offending path, no state change (RED on base 358a2ff: payload persisted with bare NaN token)
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: same file test_infinity_nested_in_payload_rejected_400_with_offending_path — ±inf nested (dict/list) and the raw 1e999 / -1e999 JSON literals → 400 with the offending path, no state change
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P0 | Evidence: same file test_rejection_causes_no_state_change — seeded finite state byte-identical after rejected NaN/1e999 POSTs; fresh camera gets no camera_state row (no upsert ran)
- TEST-004 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: same file test_rejection_with_overlay_writes_nothing — rejected request CARRYING an overlay → 400 with the sentinel overlay file byte-unchanged and no .tmp stray (RED on base 358a2ff: request succeeded and overwrote the sentinel — overlay_tree [] → ['cam1_latest_overlay.jpg'])
- TEST-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: same file test_finite_payload_persists_exactly_as_before — floats/ints/strings/null/bools/nested lists+dicts/exact large int persist exactly as before; stored payload_json contains no NaN/Infinity tokens and round-trips to the merged state
- TEST-006 | Covers: AC-006 | Level: unit | Priority: P0 | Evidence: exact detail assertions in the rejection tests — detail == f"{path} must be a finite number" with paths metadata.telemetry.speed_kmh / metadata.detections[1].conf / metadata.quality / metadata.values[1] / metadata.speed (dict keys and list indices into the payload structure)
- TEST-007 | Covers: AC-007 | Level: integration | Priority: P1 | Evidence: RED differential (test file byte-identical, sha256 64f964d9, on base 358a2ff with main.py at base → FAILED failures=12 incl. the overlay and dirty-row pins; with the fix → 6/6 OK) + full battery 1412 OK (skipped=2; baseline 1406) + ruff clean (observed, see Validation)
- TEST-008 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: same file test_final_scan_rejects_nan_overlay_rev_from_dirty_stored_row — dirty stored row (``overlay_rev: NaN``, seeded via the REAL store.upsert_camera_state) + finite no-overlay POST without overlay_rev → 400 detail "metadata.overlay_rev must be a finite number" from the FINAL scan, dirty row byte-unchanged (RED on base 358a2ff: request succeeded and re-persisted the NaN merged from old_state — proves the early scan alone is insufficient)

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

Lane-A VPS API rollout of the analytics-state non-finite boundary guard
(same contour as #587 and #616); it does not redeploy Ubuntu or Windows.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production VPS remains on the accepted previous release | Retry: correct exact SHA/quality/authorization evidence then re-enter the protected VPS deploy workflow | Rollback: NOT REQUIRED before mutation | Evidence: exact merged main SHA, push/main Quality integration, wave-2 task-B authorization (commit approved, 2026-11-09)
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate release may be staged while current VPS release remains active | Retry: verify staged exact release and previous/current identities then retry | Rollback: NOT REQUIRED while active release is unchanged | Evidence: exact VPS artifact/release manifest and current/previous release markers
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate VPS release may be active but is not accepted until verification succeeds | Retry: only after existing deploy transaction restores or proves a coherent current release | Rollback: existing VPS deploy rollback restores the previous deployed main SHA | Evidence: repository-owned deploy-vps activation logs
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not accepted | Retry: resolve health/public-smoke failure after actual current release is known | Rollback: automatic previous-release verification through accepted loopback origin and protected public smoke | Evidence: origin health, public smoke, exact API release identity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment evidence is incomplete and completion is forbidden | Retry: verify actual runtime before persisting evidence | Rollback: previous deployed main SHA remains the declared rollback target | Evidence: current/previous markers plus runtime-verified deployment manifest
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime remains valid while stale release cleanup may remain pending | Retry: clean stale non-current/non-previous releases independently | Rollback: NOT REQUIRED solely for stale cleanup failure | Evidence: warning-only pruning behavior already regression-protected
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed runtime may be healthy but validation acceptance remains incomplete | Retry: replay the #617 probes without redeployment when exact runtime identity is unchanged | Rollback: decide from actual API/runtime behavior, not evidence upload alone | Evidence: deployment manifest plus external read-only probe that GET /, /sea-speed/ and /sea-speed/api/health signatures hold and an unauthenticated non-finite state POST is intercepted by the auth boundary (wave-1 #587 precedent)
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if the previous deployed main SHA cannot be restored/verified, stop automated mutation and recover actual VPS state | Retry: read current/previous/runtime evidence before any new mutation | Rollback: no guessed secondary target; use the protected previous deployed main SHA | Evidence: existing VPS rollback logs and verified origin/public health

## Validation

- Focused run `python3 -W error::ResourceWarning -m unittest tests.test_617_analytics_state_nonfinite -v`: OBSERVED 6/6 tests OK with the fix (EXIT=0).
- RED differential: test file byte-identical (sha256 64f964d9 verified before/after) with api/app/main.py reverted to base 358a2ff (both scans removed, git diff empty) → OBSERVED FAILED (failures=12) — bare NaN/Infinity persisted into camera_state.payload_json, the overlay-carrying rejected request succeeded and wrote the overlay media file, and the finite POST against the dirty stored row re-persisted the stored NaN overlay_rev; with the fix → 6/6 OK; main.py restored byte-identical (regenerated diff byte-identical to the saved fix-v3.patch, sha256 9b9a2c79 restored).
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'`: OBSERVED 1412 tests OK (skipped=2); baseline at 358a2ff without the new file 1406 OK (skipped=2) — delta +6 tests as accounted.
- ruff `RUFF_CACHE=/tmp/opencode/toolcache/sea-speed ruff check --config scripts/quality/ruff.toml api/app/main.py tests/test_617_analytics_state_nonfinite.py`: OBSERVED "All checks passed!".
- `python3 scripts/ci/validate_sdd.py` with this trio: OBSERVED pass (EXIT=0).

## Runtime feedback

- RF-001: Operator actions expected: 0 — the change rides the normal VPS
  release contour; runtime acceptance = exact-head CI green plus the
  post-deploy external probes (GET /, /sea-speed/, /sea-speed/api/health
  signatures; unauthenticated non-finite state POST intercepted by the auth
  boundary — wave-1 #587 precedent).
- RF-002: no stored-data migration is needed or performed; the boundary
  prevents new bare NaN/Infinity tokens in camera_state.payload_json;
  pre-fix rows are inert history for the JS clients until overwritten by
  the next finite state POST (the 1 Hz upsert overwrites camera_state rows
  on every worker post).
