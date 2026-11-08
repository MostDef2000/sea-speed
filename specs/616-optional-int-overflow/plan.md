# Plan — Issue #616 optional_int non-finite guard

- Issue: #616
- Specification: specs/616-optional-int-overflow/spec.md

## Architecture

Guard at the numeric-coercion seam (objects_registry.optional_int), not at
the route — the same pattern as the #577 optional_float guard directly
above it in the same module. optional_int gains an isinstance(value, float)
chained-comparison finiteness guard (not (float("-inf") < value <
float("inf"))) placed before int() and returning None for non-finite
floats, so a JSON number like 1e999 (parsed by json.loads to float inf on
the crossing ingestion path) is dropped exactly like non-numeric input;
OverflowError joins the except tuple as a belt for non-float overflowers.
The guard is isinstance-scoped to floats, so exact integers never
round-trip through float() and keep full precision. The crossing handler
post_analytics_crossing (api/app/analytics.py:454, track_id parsed via
optional_int(data.get("track_id")); the route POST /api/cam1/crossings adds
no exception handling of its own, and unlike the passage/event metadata
paths there is no #587 boundary scan here) inherits the fix with no handler
change.

## Decisions

- **Coercion-seam guard, mirroring #577**: optional_float already carries
  the identical chained-comparison finiteness guard (#577); optional_int
  gets the same shape so both scalar coercions behave uniformly and no
  caller guard (`if x < 0`) can be bypassed by a non-finite value.
- **isinstance-float guard, not a float() round-trip**: converting value
  through float() before int() would destroy exact-integer precision
  (float(10**30) loses precision); the isinstance-scoped check touches only
  non-finite floats, so 10**30 passes through int() unchanged.
- **OverflowError belt**: int() can raise OverflowError from non-float
  inputs too (e.g. Decimal('Infinity')); adding it to the except tuple
  makes the None-on-overflow contract total without a Decimal-specific
  branch.
- **Module-import-free body preserved**: the chained comparison is
  math.isfinite(value) with a module-import-free body — the AST/exec test
  harnesses (test_numeric_input_validation.py idiom; the new test file's
  stub namespace holds only typing.Any/Optional) exec the function
  verbatim, so any module-level reference would raise NameError at call
  time.
- **Handler-level exec harness instead of TestClient**: the ingestion pins
  run the REAL post_analytics_crossing with the REAL optional_int /
  optional_float and stub only the sinks (persist_object_event,
  append_crossing_record) and the identity seam; a TestClient variant would
  need guarded-optional fastapi/httpx tuples registered in
  tests/test_run_tests_script.py's pinned import-hygiene list, which lives
  outside this fix's allowed paths — the handler-level harness pins the
  same defect (the route adds no exception handling) without a third-party
  import, so the one-process battery stays green and the import-hygiene
  gate is not gamed with scanner-invisible dynamic imports.
- **optional_float untouched**: already hardened by #577; no behavioral
  delta.

## Affected contours

- API (deployed to VPS — release contour): api/app/objects_registry.py
  (+11/-1, optional_int finiteness guard + OverflowError in the except
  tuple).
- Control plane: tests/test_616_optional_int_overflow.py (new, 245 lines,
  8 tests), this SDD trio. Nothing else — no store.py/main.py/analytics.py,
  worker/, frontend/, deploy/, scripts/, .github/ changes.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the guard is a strictly additive pre-check placed before int() and scoped to non-finite floats; finite/normal inputs keep their exact behavior (bools, numeric strings, None/""/non-numeric, finite floats, exact large ints — all pinned); OverflowError belt only converts raises into the existing None contract; module-import-free body enforced by the exec-harness stub namespace and proven by the full battery | Validation: tests/test_616_optional_int_overflow.py + test_numeric_input_validation.py + full battery | Residual risk: a future numeric coercion path bypassing optional_int could reintroduce the gap — the #616 test file pins the known site | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: rides the normal VPS release contour with automatic rollback on failed gates; no schema/deploy plumbing changes; the previously-500 crossing ingestion path now degrades track_id to None (strictly fewer server errors) | Validation: full battery + ruff + validate_sdd green before merge; post-deploy external probes (GET /, /sea-speed/, /sea-speed/api/health signatures + unauthenticated 1e999 POST intercepted by the auth boundary) | Residual risk: standard release-contour deploy risk | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_616_optional_int_overflow.py OptionalIntOverflowTests.test_non_finite_floats_return_none — inf/-inf/nan → None via the exec harness (RED on base fa8148f9: OverflowError)
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: same file test_exact_large_int_survives_unchanged — 10**30 returned exact and isinstance int (no float() round-trip)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: same file test_numeric_string_overflow_returns_none ("1e999" string → None via the ValueError path) + test_none_empty_and_non_numeric_return_none (None/""/"abc") + test_finite_and_integer_behavior_unchanged (3.0→3, 12, "42", True→1, 0)
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P1 | Evidence: except tuple (TypeError, ValueError, OverflowError) in optional_int verified by code reading — belt for non-float overflowers (e.g. Decimal('Infinity')); the float overflow cases are pinned by TEST-001
- TEST-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: same file CrossingTrackIdIngestionTests — real post_analytics_crossing with only sinks/identity stubbed: non-finite track_id (inf/-inf/nan/raw 1e999/-1e999) ingests ok with track_id None at both sinks; valid+large (10**30) and absent track_id contracts unchanged
- TEST-006 | Covers: AC-006 | Level: unit | Priority: P1 | Evidence: exec-harness stub namespace holds only typing.Any/Optional — any module-level reference in the optional_int body raises NameError, pinning the module-import-free-body contract
- TEST-007 | Covers: AC-007 | Level: integration | Priority: P1 | Evidence: RED differential (test file byte-identical on base fa8148f9 → FAILED errors=6 OverflowError; with fix → 8/8 OK) + full battery 1406 OK (skipped=2; baseline 1398) + ruff clean (observed, see Validation)

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

Lane-A VPS API rollout of the optional_int non-finite guard (same contour
as #577 and #587); it does not redeploy Ubuntu or Windows.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production VPS remains on the accepted previous release | Retry: correct exact SHA/quality/authorization evidence then re-enter the protected VPS deploy workflow | Rollback: NOT REQUIRED before mutation | Evidence: exact merged main SHA, push/main Quality integration, wave-2 owner authorization (commit approved, 2026-11-08)
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate release may be staged while current VPS release remains active | Retry: verify staged exact release and previous/current identities then retry | Rollback: NOT REQUIRED while active release is unchanged | Evidence: exact VPS artifact/release manifest and current/previous release markers
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate VPS release may be active but is not accepted until verification succeeds | Retry: only after existing deploy transaction restores or proves a coherent current release | Rollback: existing VPS deploy rollback restores the previous deployed main SHA | Evidence: repository-owned deploy-vps activation logs
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not accepted | Retry: resolve health/public-smoke failure after actual current release is known | Rollback: automatic previous-release verification through accepted loopback origin and protected public smoke | Evidence: origin health, public smoke, exact API release identity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment evidence is incomplete and completion is forbidden | Retry: verify actual runtime before persisting evidence | Rollback: previous deployed main SHA remains the declared rollback target | Evidence: current/previous markers plus runtime-verified deployment manifest
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime remains valid while stale release cleanup may remain pending | Retry: clean stale non-current/non-previous releases independently | Rollback: NOT REQUIRED solely for stale cleanup failure | Evidence: warning-only pruning behavior already regression-protected
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed runtime may be healthy but validation acceptance remains incomplete | Retry: replay the #616 probes without redeployment when exact runtime identity is unchanged | Rollback: decide from actual API/runtime behavior, not evidence upload alone | Evidence: deployment manifest plus external read-only probe that GET /, /sea-speed/ and /sea-speed/api/health signatures hold and an unauthenticated 1e999 crossing POST is intercepted by the auth boundary (wave-1 #587 precedent, issuecomment-6724516508)
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if the previous deployed main SHA cannot be restored/verified, stop automated mutation and recover actual VPS state | Retry: read current/previous/runtime evidence before any new mutation | Rollback: no guessed secondary target; use the protected previous deployed main SHA | Evidence: existing VPS rollback logs and verified origin/public health

## Validation

- Focused run `python3 -W error::ResourceWarning -m unittest tests.test_616_optional_int_overflow`: OBSERVED 8/8 tests OK with the fix.
- RED differential: test file copied byte-identical onto base fa8148f9 (api/ at base state) → OBSERVED FAILED (errors=6) OverflowError; with the fix → 8/8 OK; test file byte-unchanged throughout.
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'`: OBSERVED 1406 tests OK (skipped=2); baseline at fa8148f9 without the new file 1398 OK (skipped=2) — delta +8 tests as accounted.
- ruff `ruff check --config scripts/quality/ruff.toml api/app/objects_registry.py tests/test_616_optional_int_overflow.py`: OBSERVED "All checks passed!".
- `python3 scripts/ci/validate_sdd.py` with this trio: OBSERVED pass (EXIT=0).

## Runtime feedback

- RF-001: Operator actions expected: 0 — the change rides the normal VPS
  release contour; runtime acceptance = exact-head CI green plus the
  post-deploy external probes (GET /, /sea-speed/, /sea-speed/api/health
  signatures; unauthenticated 1e999 crossing POST intercepted by the auth
  boundary — wave-1 #587 precedent).
- RF-002: no stored-data migration is needed or performed; a non-finite
  track_id now degrades to None exactly like an absent or non-numeric one —
  no schema change, no stored-data migration.
