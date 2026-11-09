# Spec: #617 — post_analytics_state must reject non-finite payload JSON (bare NaN/Infinity persisted into camera_state.payload_json)

- Issue: #617
- Specification: specs/617-analytics-state-nonfinite/spec.md
- Authorization: commit approved (wave-2 task B admission, 2026-11-09); base
  358a2ff5a08a6d6f5084d465a06e2b1a23bc51c0 (includes merged #616), branch
  fix/617-analytics-state-nonfinite.

## Product outcome

The #587 wave hardened every other externally-supplied non-finite persist
path (measurement_meta, deliver_event), but `post_analytics_state`
(api/app/main.py:748) still accepts free-form worker JSON in its
``metadata`` form field and persists it verbatim via
``store.upsert_camera_state`` (api/app/store.py:704, ``json.dumps`` default
``allow_nan=True``): a payload containing NaN / ±Infinity (including the
``1e999`` overflow literal, which ``json.loads`` parses to ``inf``) lands as
bare ``NaN``/``Infinity`` tokens in ``camera_state.payload_json`` — invalid
strict JSON for JS clients. After the fix: the handler scans the parsed
payload with the existing #587 helper ``store.find_nonfinite_json_value``
(api/app/store.py:390 — returns the offending dotted path or None) and
rejects with HTTP 400 BEFORE the upsert/persist call, using the exact #587
rejection idiom (offending path in the detail); rejected input causes no
state change, and finite payloads persist exactly as before.

## User scenarios

- SC-1: an authorized worker POSTs analytics state whose payload carries a
  NaN nested anywhere (nested dict, nested list element, top level) — the
  API answers 400 with the offending dotted path (e.g.
  ``metadata.telemetry.speed_kmh must be a finite number``) and the stored
  camera_state is untouched (no upsert, no row created).
- SC-2: an authorized worker POSTs analytics state with ±Infinity nested in
  the payload (including the 1e999 / -1e999 JSON overflow literals, which
  json.loads parses to ±inf) — 400 with the offending path, no state change.
- SC-3: an authorized worker POSTs a finite payload — floats (1.5, 10.5),
  ints, strings, null, bools, nested lists/dicts and exact large ints
  persist exactly as before, merged with the handler-injected fields, as
  strict JSON in camera_state.payload_json (no bare NaN/Infinity tokens).

## Requirements

- R-1: api/app/main.py post_analytics_state scans the parsed payload with
  the existing helper ``store.find_nonfinite_json_value`` (api/app/store.py:
  390 — returns the offending dotted path or None; delivered by #587) and
  raises ``HTTPException(400, f"{path} must be a finite number")`` when a
  non-finite leaf is found — same rejection idiom as the #587 sites
  (post_cam1_passage measurement_meta guard at main.py:550,
  post_analytics_event guard at main.py:827) — at TWO placements: an EARLY
  scan immediately before the overlay media write (tmp write + os.replace of
  ``{camera_id}_latest_overlay.jpg``), so a rejected request writes nothing,
  and a FINAL scan immediately before the ``store.upsert_camera_state``
  persist call (api/app/main.py:800) — kept because the no-overlay branch
  merges ``overlay_rev`` from ``old_state``, which can carry NaN from
  pre-fix rows.
- R-2: api/app/store.py is NOT modified — the helper already exists and is
  reused verbatim; no new helpers are introduced in main.py.
- R-3: finite payloads (floats like 1.5/10.5, ints, strings, null, bools,
  nested lists/dicts, exact large ints) persist exactly as before — the
  merged state (camera_id/analytics_profile/domain/schema defaults/
  updated_at/worker_online/overlay bookkeeping) round-trips through
  camera_state.payload_json as strict JSON.
- R-4: tests/test_617_analytics_state_nonfinite.py (6 tests) is the
  acceptance oracle, byte-unchanged through the fix, RED on base 358a2ff
  (FAILED, failures=12 — the NaN/Infinity payload is persisted, a rejected
  overlay-carrying request overwrites the overlay media file, and a finite
  POST against a dirty stored row re-persists the stored NaN overlay_rev)
  and GREEN with the fix; it uses the handler-level exec-harness variant
  (real post_analytics_state with the REAL api.app.store persist path, only
  the auth/identity/clock/overlay-upload seams stubbed) and introduces NO
  TestClient/third-party import, so the import-hygiene registry in
  tests/test_run_tests_script.py needs no change (see
  tests/test_616_optional_int_overflow.py file notes).

## Acceptance criteria

- AC-001: a NaN nested in the camera_state payload JSON (nested dict
  metadata.telemetry.speed_kmh, nested list element
  metadata.detections[1].conf, top level metadata.quality) is rejected with
  HTTP 400 and the offending path in the detail; on base 358a2ff the payload
  was persisted verbatim (200, bare NaN token in camera_state.payload_json)
  — RED differential verified.
- AC-002: ±Infinity nested in the payload (nested dict, list element, and
  the 1e999 / -1e999 overflow literals parsed by json.loads to ±inf) is
  rejected with HTTP 400 and the offending path; no state change.
- AC-003: rejected input causes NO state change — a previously seeded finite
  camera_state stays byte-identical (payload_json unchanged) and a fresh
  camera gets no camera_state row at all (no upsert ran).
- AC-004: a rejected request CARRYING an overlay file writes nothing — the
  early scan rejects before the overlay media write, so the previous
  overlay file stays byte-unchanged and no ``.tmp`` stray is left; on base
  358a2ff the request succeeded and overwrote the sentinel overlay (RED
  differential verified).
- AC-005: a finite payload (floats 1.5/10.5/2.5, ints, strings, null, bools,
  nested lists/dicts, exact large int 10**30) persists exactly as before —
  the merged state round-trips through camera_state.payload_json as strict
  JSON (no NaN/Infinity tokens in the stored bytes).
- AC-006: the offending-path reporting is accurate — the 400 detail names
  the dotted path into the payload structure (dict keys as ``.key``, list
  elements as ``[index]``), matching the #587 rejection idiom.
- AC-007: full battery green with the fix (1412 tests, skipped=2; baseline
  at 358a2ff without the new file 1406 — delta +6), ruff clean on the
  changed files, and the new test file is RED on base 358a2ff (FAILED,
  failures=12) / GREEN with the fix, byte-unchanged; api/app/store.py
  untouched and no new guarded-optional import registered.
- AC-008: the FINAL scan catches non-finite state merged from the STORED row
  (early-scan blind spot): a pre-fix dirty camera_state row carrying
  ``overlay_rev: NaN`` (seeded via the REAL ``store.upsert_camera_state``),
  followed by a finite no-overlay POST without an explicit ``overlay_rev``,
  is rejected 400 with detail ``metadata.overlay_rev must be a finite
  number`` (the early scan sees only the finite worker payload; the NaN
  enters via the no-overlay branch copying ``overlay_rev`` from
  ``old_state``), and the dirty stored row stays byte-unchanged; on base
  358a2ff the POST succeeded and re-persisted the NaN (RED differential
  verified).

## Runtime feedback

- RF-001: Operator actions expected: 0 — api/** rides the normal VPS release
  contour. Runtime acceptance = exact-head CI green on the merge PR, then
  the lane-A deploy probe: external read-only probes confirm GET /,
  /sea-speed/ and /sea-speed/api/health signatures, and an unauthenticated
  non-finite state POST is intercepted by the auth boundary (wave-1 #587
  precedent).
- RF-002: behavior-tightening change — the previously-accepted NaN/Infinity
  state payload now answers 400 (strictly less invalid strict JSON at rest);
  workers already posting finite payloads are unaffected; no schema change,
  no stored-data migration. Existing rows that already contain bare
  NaN/Infinity tokens (written before the fix) are NOT migrated by this
  change — out of #617 scope; the boundary prevents new ones.

## NFR assessment

- NFR-001 | Area: input validation / API robustness | Target: no non-finite numeric leaf (NaN/±Infinity incl. 1e999 literals) in the analytics-state payload reaches upsert_camera_state or the overlay media write — such payloads are rejected with HTTP 400 and the offending path before any write, including non-finite values merged from a dirty stored row (pre-fix ``overlay_rev: NaN``) | Validation: tests/test_617_analytics_state_nonfinite.py (6 tests; RED on base 358a2ff failures=12, GREEN 6/6 with fix) | Evidence: focused run + base differential recorded in plan.md | Status: PASS
- NFR-002 | Area: compatibility | Target: zero change for finite payloads — the merged state persists byte-identically (same json.dumps serialization, same merge order); store.py untouched; no new third-party test imports (import-hygiene registry unbroken) | Validation: full battery 1412 OK (skipped=2) incl. test_587_nonfinite_residual_paths.py and test_run_tests_script.py; ruff clean | Evidence: observed runs recorded in plan.md and tasks.md | Status: PASS
- NFR-003 | Area: performance | Target: negligible — two recursive scans of the already-parsed payload (O(payload size) each, pure Python comparisons; the second usually short-circuits on the first leaf) against a SQLite upsert that dominates the request | Validation: code review; no hot-loop additions | Evidence: diff inspection (+10 lines in api/app/main.py, two guard blocks only) | Status: PASS
