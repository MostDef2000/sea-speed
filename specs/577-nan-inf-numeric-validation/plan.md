# Plan — Issue #577 NaN/Infinity numeric input validation

- Issue: #577
- Specification: specs/577-nan-inf-numeric-validation/spec.md

## Architecture

Smallest-change input-validation hardening on the API ingest/calibration
contour. NaN and ±Infinity are float-convertible, so they pass every existing
`try: float(x) except` conversion and then bypass every `if x < 0` range
guard, because all NaN comparisons are false. The fix adds one
`math.isfinite` gate at each of the five audited sites — the shared ingest
helper (which covers event ingest everywhere through its callers in
`water_passages.py`, `analytics.py`, `passage_mirrors.py` and the registry
persist path), the ROI point cleaner, both calibration endpoints in `main.py`
and the object-update path. No new bounds or ranges: existing range checks
stay exactly as they are; only the non-finite class of input is rejected.
`optional_int` needs no change — `int(nan)` already raises `ValueError` into
the existing except path (verified during recon).

## Decisions

- **Fix at the shared helper, not at callers**: `optional_float` is the single
  ingest funnel (water_passages, analytics, passage_mirrors, registry persist);
  one gate there covers every `if x < 0` caller guard without touching them.
- **Drop, don't clamp, in `_clean_norm_points`**: non-finite coordinates are
  dropped with the same `continue` the malformed-conversion path uses; the
  previous max/min clamp silently turned NaN/+inf into 1.0 (and -inf into
  0.0), corrupting ROI geometry.
- **400 with `must be a finite number` detail** on the three endpoint sites:
  matches the existing `<field> must be <constraint>` detail style and sits
  between the existing conversion and range checks, so the old messages and
  ordering are preserved exactly.
- **No TestClient**: the suite has none (issue #582); the new test file uses
  the established AST-extract/exec harness idiom of
  `tests/test_water_passage.py` / `tests/test_sea_speed_rbac.py`, including
  the `@contextmanager`-decorator special case for `open_objects_db`.
- **Old-code differential proof**: the fix was stashed and the new suite run
  against base 79ffab2 — 28 failures/subfailures across all five sites — then
  restored; the unchanged-behavior pins pass identically on base and fix.
- **Dependency-free finite check**: the finite gate is implemented as a
  chained comparison `float("-inf") < x < float("inf")` (exactly
  `math.isfinite` semantics) rather than a `math.isfinite` call, because the
  AST/exec test harnesses exec extracted function bodies against stub
  namespaces without `math` — adding the import broke 32 existing tests.

## Affected contours

- API (deployed to VPS — release contour): api/app/objects_registry.py,
  api/app/analytics.py, api/app/main.py.
- Control plane: tests/test_numeric_input_validation.py (new).
- This SDD trio. Nothing else — no worker/, frontend/, deploy/, scripts/,
  .github/ changes.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: strictly narrowing validation — only non-finite inputs change behavior; unchanged-behavior pin tests cover finite (including negative finite at ingest), null, empty, malformed and clamping paths, and were verified to pass identically on base 79ffab2 | Validation: tests/test_numeric_input_validation.py + full battery | Residual risk: a client that deliberately sent NaN/Infinity and "worked" now gets 400 — that state was corrupt (NaN comparisons, infinite speeds) | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: five one-line gates, no refactoring, no schema/deploy plumbing changes; rides the normal release contour with automatic rollback on failed gates | Validation: full battery + ruff + validate_sdd green before merge | Residual risk: standard release-contour deploy risk | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_numeric_input_validation.py::OptionalFloatFiniteTests — NaN/+inf/-inf (float and string forms) → None; finite/null/empty/malformed pins unchanged
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: tests/test_numeric_input_validation.py::CleanNormPointsFiniteTests — non-finite points dropped, valid clamping and malformed-drop pins unchanged, mixed-input survival
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_numeric_input_validation.py::SpeedConfigEndpointFiniteTests — handler-level 400 on NaN/±inf with no write; finite/range pins unchanged
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: tests/test_numeric_input_validation.py::SpeedLinesEndpointFiniteTests — handler-level 400 on NaN/±inf distance_m, valid enabled config still writes, NaN line point cannot complete an enabled config
- TEST-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: tests/test_numeric_input_validation.py::PatchObjectSpeedFiniteTests — real sqlite registry in a temp dir; NaN/±inf → 400; finite/null/`>= 0`/malformed pins unchanged
- TEST-006 | Covers: AC-006 | Level: integration | Priority: P1 | Evidence: full battery, ruff and validate_sdd runs recorded in tasks.md; base-stash differential run (28 failures on base) recorded above

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

This audit models the VPS-only rollout of the API numeric-validation fix; it
does not redeploy Ubuntu or Windows.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production VPS remains on the accepted previous release | Retry: correct exact SHA/quality/authorization evidence then re-enter the protected VPS deploy workflow | Rollback: NOT REQUIRED before mutation | Evidence: exact merged main SHA, push/main Quality integration, owner-approved #534 decomposition chain (commit approved 2026-11-01)
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate release may be staged while current VPS release remains active | Retry: verify staged exact release and previous/current identities then retry | Rollback: NOT REQUIRED while active release is unchanged | Evidence: exact VPS artifact/release manifest and current/previous release markers
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate VPS release may be active but is not accepted until verification succeeds | Retry: only after existing deploy transaction restores or proves a coherent current release | Rollback: existing VPS deploy rollback restores previous exact release | Evidence: repository-owned deploy-vps activation logs
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not accepted | Retry: resolve health/public-smoke failure after actual current release is known | Rollback: automatic previous-release verification through accepted loopback origin and protected public smoke | Evidence: origin health, public smoke, exact API release identity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment evidence is incomplete and completion is forbidden | Retry: verify actual runtime before persisting evidence | Rollback: previous exact VPS release remains the declared rollback target | Evidence: current/previous markers plus runtime-verified deployment manifest
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime remains valid while stale release cleanup may remain pending | Retry: clean stale non-current/non-previous releases independently | Rollback: NOT REQUIRED solely for stale cleanup failure | Evidence: warning-only pruning behavior already regression-protected
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed runtime may be healthy but validation acceptance remains incomplete | Retry: recollect the ingest/calibration probe without redeployment when exact runtime identity is unchanged | Rollback: decide from actual API/runtime behavior, not evidence upload alone | Evidence: deployment manifest plus external read-only probe that valid ingest/calibration still succeed and NaN/Infinity payloads return 400
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if previous exact release cannot be restored/verified, stop automated mutation and recover actual VPS state | Retry: read current/previous/runtime evidence before any new mutation | Rollback: no guessed secondary target; use the protected previous exact VPS release | Evidence: existing VPS rollback logs and verified origin/public health

## Validation

- Focused run `python3 -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/577/pytest-tmp tests/test_numeric_input_validation.py -q`: OBSERVED 13 passed / 34 subtests passed.
- Base differential: fix stashed, same focused run on base 79ffab2 → OBSERVED 28 failed / 11 passed (every non-finite assertion fails on base; every unchanged-behavior pin passes on both) — fix restored afterwards.
- Full battery `python3 -m pytest -p no:cacheprovider --basetemp=/tmp/opencode/577/pytest-tmp tests/ -q`: OBSERVED 1247 passed / 2 skipped / 346 subtests (baseline 1234/2/312 on base 79ffab2; delta +13 methods, +34 subtests).
- ruff (CI config, repo-wide): `ruff check --config scripts/quality/ruff.toml .` clean — OBSERVED.
- `python3 scripts/ci/validate_sdd.py` plain run passes with the new trio — OBSERVED.
- `python3 scripts/quality/validate_workflow_policy.py` passes (workflow layer unaffected) — OBSERVED.

## Runtime feedback

- RF-001: Operator actions expected: 0 — the change rides the normal VPS
  release contour; runtime acceptance = exact-head CI green plus the standard
  post-deploy probe (ingest, calibration and object edit flows unchanged for
  valid input; non-finite payloads now 400).
- RF-002: no stored-data migration is needed or performed: rows already
  containing NaN/Infinity (if any) remain readable; only new writes are
  guarded.
