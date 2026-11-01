# Spec: #577 — NaN/Infinity must not bypass numeric external input validation

- Issue: #577
- Specification: specs/577-nan-inf-numeric-validation/spec.md
- Authorization: the #577 scope (five numeric-validation sites in api/app + the
  new regression test + this trio; audit #534 section P2-03) admitted by the
  delivery orchestrator; base 79ffab2 (branch fix/577-nan-inf-numeric-validation).

## Product outcome

Every float-convertible external numeric input in the API ingest/calibration
surface rejects NaN and ±Infinity exactly like non-numeric input. Today
`float("nan")`/`float("inf")` convert successfully and slip past every
existing `if x < 0` range guard (NaN comparisons are always false), so a
client can persist NaN speeds into the objects registry, corrupt ROI/line
geometry through silent clamping, or store non-finite calibration constants.
After the fix: the shared ingest helper `optional_float` returns `None` for
non-finite results (event ingest everywhere inherits the guard), ROI
normalization drops non-finite points exactly like malformed ones, and both
calibration endpoints plus the object-update endpoint answer 400 with a
detail message in the existing style. Valid finite behavior is unchanged
byte-for-byte; no new bounds or ranges are introduced.

## User scenarios

- SC-1: an event producer posts a passage/object event with
  `"speed_kmh": NaN` (or the string `"nan"`, or ±Infinity) — the event is
  stored with `speed_kmh = NULL` instead of a NaN value that would poison
  every downstream `speed_kmh >= ?`/`<= ?` registry filter and average.
- SC-2: an operator (or a buggy client) saves speed-lines calibration with a
  NaN/Infinity `distance_m` or a NaN coordinate inside `line_a_norm` — the
  API answers 400 with `distance_m must be a finite number` (or drops the
  non-finite point, so an enabled calibration that required 2 valid points
  fails its existing 2-point check) instead of persisting corrupted geometry.
- SC-3: an operator saves speed-config with `kmh_per_px_s: Infinity` — 400
  `kmh_per_px_s must be a finite number` instead of a stored Infinity that
  makes every computed speed infinite.
- SC-4: an operator patches an object with `speed_kmh: NaN` — 400
  `speed_kmh must be a finite number` instead of a NaN cell in the registry.
- SC-5: all previously valid inputs behave exactly as before: finite floats
  (including negative finite values at the `optional_float` ingest layer,
  where range checks belong to callers), null/empty → None, malformed strings
  → None, out-of-range ROI points still clamp to 0..1, existing 400 messages
  for the old failure modes (non-numeric, out-of-range finite) are unchanged;
  the only message change is that −Infinity at the three endpoint sites now
  answers `must be a finite number` instead of the range message.

## Acceptance criteria

- AC-001: `optional_float` returns `None` for NaN/+inf/-inf (float or
  numeric-string forms) and is byte-for-byte unchanged for every finite and
  non-numeric input; `optional_int` is untouched (`int(nan)` already raises
  into the existing except path).
- AC-002: `_clean_norm_points` drops any point with a non-finite x_norm/y_norm
  exactly the way malformed points are dropped, while still clamping valid
  out-of-range values to 0..1 as before.
- AC-003: `POST /api/analytics/{camera_id}/speed-config` rejects NaN/±inf
  `kmh_per_px_s` with 400 `kmh_per_px_s must be a finite number` and writes
  nothing; the existing `must be a number` / `must be >= 0` behavior is
  unchanged.
- AC-004: `POST /api/analytics/{camera_id}/speed-lines` rejects NaN/±inf
  `distance_m` with 400 `distance_m must be a finite number` and writes
  nothing; the existing `must be a number` / `must be > 0` behavior and the
  valid enabled-calibration path are unchanged.
- AC-005: `patch_object_record` rejects NaN/±inf `speed_kmh` with 400
  `speed_kmh must be a finite number`; the existing null, finite and
  `must be >= 0` behaviors are unchanged.
- AC-006: every site has at least one assertion the base (79ffab2) code fails;
  full battery, ruff and validate_sdd stay green with the battery delta
  accounted.

## Requirements

- R-1: `api/app/objects_registry.py` `optional_float` returns `None` when the
  converted result is not finite (`math.isfinite` semantics, implemented as a
  dependency-free chained comparison — see plan.md Decisions); no other change
  to the helper.
- R-2: `api/app/analytics.py` `_clean_norm_points` `continue`s (drops) any
  point whose converted x_norm/y_norm is not finite, immediately after the
  existing conversion try/except.
- R-3: `api/app/main.py` `post_analytics_speed_config` raises 400
  `kmh_per_px_s must be a finite number` for non-finite values, between the
  existing conversion and `< 0` checks.
- R-4: `api/app/main.py` `post_analytics_speed_lines` raises 400
  `distance_m must be a finite number` for non-finite values, between the
  existing conversion and `<= 0` checks.
- R-5: `api/app/objects_registry.py` `patch_object_record` raises 400
  `speed_kmh must be a finite number` for non-finite values, between the
  existing conversion and `< 0` checks.
- R-6: `tests/test_numeric_input_validation.py` covers all five sites in the
  suite's AST/exec harness idiom (no TestClient — issue #582), including
  old-code-failing assertions and unchanged-behavior pins.
- R-7: the SDD trio `specs/577-nan-inf-numeric-validation/{spec,plan,tasks}.md`
  is created; no other files change (no new bounds, no refactoring beyond the
  five sites, `optional_int` untouched).

## Runtime feedback

- RF-001: Operator actions expected: 0 — api/** rides the normal VPS release
  contour. Runtime acceptance = exact-head CI green on the merge PR, then the
  standard post-deploy probe: event ingest, calibration saves and object
  edits behave as before for valid input; NaN/Infinity payloads now get 400.
- RF-002: strictly narrowing change — every previously accepted finite input
  is still accepted with identical stored values; only non-finite inputs
  (which produced corrupt NaN/Infinity state) change behavior.

## NFR assessment

- NFR-001 | Area: input validation / data integrity | Target: no NaN/±inf value can be persisted through event ingest, calibration endpoints or object update | Validation: tests/test_numeric_input_validation.py (13 methods, 34 subtests; non-finite assertions observed failing on base 79ffab2) | Evidence: focused pytest run + base-stash differential run recorded in plan.md | Status: PASS
- NFR-002 | Area: compatibility | Target: zero behavior change for finite/absent/malformed inputs across all five sites | Validation: unchanged-behavior pin tests (finite values, negative finite at ingest, null, empty, malformed strings, ROI clamping, existing 400 details) | Evidence: same focused run — pin tests pass identically on base and fix | Status: PASS
- NFR-003 | Area: performance | Target: negligible — one finiteness check per converted value (dependency-free chained comparison with `math.isfinite` semantics; see plan.md Decisions) | Validation: code review; no loops added | Evidence: diff inspection | Status: PASS
