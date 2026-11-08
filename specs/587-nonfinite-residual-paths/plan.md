# Plan — Issue #587 residual non-finite input paths

- Issue: #587
- Specification: specs/587-nonfinite-residual-paths/spec.md

## Architecture

Boundary rejection at the external-input perimeter (API/JSON), not internal
arithmetic — the same pattern as the #577 fix (main.py distance_m guard).
store.py gains a fastapi-free recursive scanner find_nonfinite_json_value
(store.py:390, after event_content_fingerprint) that walks parsed JSON —
float → chained-comparison finite check (no math import needed), dict →
recurse values building dotted paths, list → recurse with index paths,
scalars pass — and returns the offending path or None; the handler owns the
HTTP concern and raises HTTPException(400). The two free-form JSON ingest
handlers (post_cam1_passage measurement_meta, post_analytics_event
metadata) scan immediately after parse and before any snapshot read /
normalization / mirror / media / persist write. The two object-list
endpoints and the three reference-dimension config handlers use inline
chained-comparison guards placed before the existing downstream checks so
the pre-existing failure modes (< 0 guards, non-floatable ValueError) are
untouched.

## Decisions

- **Boundary rejection, not internal arithmetic**: mirrors the #577 pattern
  (main.py distance_m guard) — validate once at the external-input
  perimeter so internal code can assume finite floats.
- **Inline-vs-helper split**: post_cam1_passage and post_analytics_event may
  call the store helper, but the speed-filter and reference-dimension guards
  are inline chained comparisons because those handlers are exec'd by
  AST/exec test harnesses (test_numeric_input_validation.py,
  test_api_contract.py, test_sea_speed_rbac.py — the last stubs `store` with
  ONLY JSON_READ_ERRORS) with fixed stub namespaces: no `import math`, no
  helper calls there. The store helper appears only in post_cam1_passage
  (never AST-exec'd) and post_analytics_event (harnesses pass the real
  store module).
- **Registry mirrors need no change**: persist_object_event has THREE
  callers — analytics.py:473 (scalar-only record via the #577-hardened
  optional_float/optional_int), main.py:899 (post-scan), and
  objects_registry.py:261 (import_existing_events — startup import from
  legacy events.json, called at main.py:383; a startup/legacy-data path,
  not externally-supplied per-request input); persist_passage_object
  callers are post-scan or the startup rebuild — no non-finite value can
  reach them.
- **Test-protected fix**: tests/test_587_nonfinite_residual_paths.py is the
  acceptance oracle, byte-unchanged through the fix; RED differential
  verified (stash api/ on base ef01fa80 → 38 subtest failures → pop → 8/8
  methods OK).
- **Hygiene registration, not weakening**: tests/test_run_tests_script.py's
  import-hygiene scan gained exactly 3 tuples (new test file lines 123/124
  fastapi, 126 httpx) — registration of the new test file's
  guarded-optional imports, the same mechanism existing test files use.

## Affected contours

- API (deployed to VPS — release contour): api/app/store.py (+32, helper),
  api/app/main.py (+51, five handler guard sites), api/app/analytics.py
  (+15, crossing-line guard).
- Control plane: tests/test_587_nonfinite_residual_paths.py (new, 8
  methods), tests/test_run_tests_script.py (+3 hygiene tuples), this SDD
  trio. Nothing else — no worker/, frontend/, deploy/, scripts/, .github/
  changes.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: guards are strictly additive pre-checks placed before existing downstream checks; falsy/non-floatable reference dimensions keep their existing behavior; speed_min=-1e999 → 400 pinned by tests; AST/exec harness compatibility enforced by the inline-only rule for extracted handlers and proven by the full battery | Validation: tests/test_587_nonfinite_residual_paths.py + test_numeric_input_validation.py + test_api_contract.py + test_sea_speed_rbac.py + full battery | Residual risk: a future handler ingesting free-form JSON without the scan could reintroduce the gap — the hygiene scan and the #587 test file pin the known sites | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: rides the normal VPS release contour with automatic rollback on failed gates; no schema/deploy plumbing changes; previously-500 paths become clean 400s (strictly fewer server errors) | Validation: full battery + ruff + validate_sdd green before merge; post-deploy replay probe of the issue payloads | Residual risk: standard release-contour deploy risk | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: integration | Priority: P0 | Evidence: tests/test_587_nonfinite_residual_paths.py — cam1 passage measurement_meta non-finite variants (top-level, nested dict/list, 1e999, numeric strings) → 400 with offending path, no state change
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: same file — analytics event metadata non-finite variants → 400, no event row
- TEST-003 | Covers: AC-003, AC-004, AC-009 | Level: integration | Priority: P0 | Evidence: same file — query-param guard tested on /api/cam1/objects (speed_min/speed_max non-finite → 400; speed_min=-1e999 stability pin); the same inline guard covers get_objects (serving /api/objects and /api/analytics/{camera_id}/objects via delegation) — verified by code reading, not by test
- TEST-004 | Covers: AC-005, AC-006, AC-007 | Level: integration | Priority: P0 | Evidence: same file — reference-dimension guards on roi/speed-lines/crossing-line: floatable-non-finite → 400, falsy → defaults, non-floatable → existing failure mode
- TEST-005 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: same file — no-state-change assertions on every rejected request (sqlite/mirror/media untouched)
- TEST-006 | Covers: AC-010 | Level: integration | Priority: P1 | Evidence: RED differential (8 test methods / 39 subtests: 38 fail on base ef01fa80 with api/ stashed, the speed_min=-1e999 stability pin is green on base via the pre-existing < 0 guard; all pass with fix) + full battery 1390 OK (skipped=2) + ruff clean (observed, see Validation)

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

Lane-A VPS API rollout of the input-validation fix (same contour as #577
and #591); it does not redeploy Ubuntu or Windows.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production VPS remains on the accepted previous release | Retry: correct exact SHA/quality/authorization evidence then re-enter the protected VPS deploy workflow | Rollback: NOT REQUIRED before mutation | Evidence: exact merged main SHA, push/main Quality integration, wave-1 owner authorization (2026-11-08 continuation instruction)
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate release may be staged while current VPS release remains active | Retry: verify staged exact release and previous/current identities then retry | Rollback: NOT REQUIRED while active release is unchanged | Evidence: exact VPS artifact/release manifest and current/previous release markers
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate VPS release may be active but is not accepted until verification succeeds | Retry: only after existing deploy transaction restores or proves a coherent current release | Rollback: existing VPS deploy rollback restores previous exact release | Evidence: repository-owned deploy-vps activation logs
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not accepted | Retry: resolve health/public-smoke failure after actual current release is known | Rollback: automatic previous-release verification through accepted loopback origin and protected public smoke | Evidence: origin health, public smoke, exact API release identity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment evidence is incomplete and completion is forbidden | Retry: verify actual runtime before persisting evidence | Rollback: previous exact VPS release remains the declared rollback target | Evidence: current/previous markers plus runtime-verified deployment manifest
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime remains valid while stale release cleanup may remain pending | Retry: clean stale non-current/non-previous releases independently | Rollback: NOT REQUIRED solely for stale cleanup failure | Evidence: warning-only pruning behavior already regression-protected
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed runtime may be healthy but validation acceptance remains incomplete | Retry: replay the #587 non-finite probes without redeployment when exact runtime identity is unchanged | Rollback: decide from actual API/runtime behavior, not evidence upload alone | Evidence: deployment manifest plus external read-only probe that non-finite payloads (measurement_meta NaN, speed_min=1e999, reference_width="1e999") now return 400 on prod
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if previous exact release cannot be restored/verified, stop automated mutation and recover actual VPS state | Retry: read current/previous/runtime evidence before any new mutation | Rollback: no guessed secondary target; use the protected previous exact VPS release | Evidence: existing VPS rollback logs and verified origin/public health

## Validation

- Focused run `python3 -W error::ResourceWarning -m unittest tests.test_587_nonfinite_residual_paths`: OBSERVED 8/8 methods OK (39 subtests) with the fix.
- RED differential: api/ fix stashed on base ef01fa80 → OBSERVED 38 subtest failures across the 8 methods; fix popped → 8/8 OK; test file byte-unchanged throughout.
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'`: OBSERVED 1390 tests OK (skipped=2); baseline at ef01fa80 without the new file 1382 OK (skipped=2) — delta +8 methods as accounted.
- ruff `ruff check --config scripts/quality/ruff.toml api/` (and the new test file): OBSERVED "All checks passed!".
- `python3 scripts/ci/validate_sdd.py --event /tmp/opencode/zerotouch-gate/cleanup/event-587.json` with this trio: OBSERVED pass (final green run in the tasks.md completion gate).

## Runtime feedback

- RF-001: Operator actions expected: 0 — the change rides the normal VPS
  release contour; runtime acceptance = exact-head CI green plus the
  post-deploy replay of the issue's non-finite payloads returning 400
  (today: 500 / silent empty set / NaN persisted).
- RF-002: no stored-data migration is needed or performed; previously
  persisted bare NaN tokens (if any) are legacy values and out of scope for
  this fix.
