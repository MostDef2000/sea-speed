# Plan — Issue #591 audit line stderr reachability

- Issue: #591
- Specification: specs/591-audit-stderr-reachability/spec.md

## Architecture

Logging-only wiring at module init in api/app/identity.py. The identity
module logger is created as logging.getLogger(__name__) (identity.py:101), so
its name differs between import modes (bare `identity` under the production
uvicorn app-dir invocation per api/requirements-api.txt:29-30 vs
`api.app.identity` in package context) — the wiring therefore targets the
logger OBJECT, never a name. Under default startup nothing configures
logging: the root logger has no handlers and the logger's effective level is
WARNING, so the INFO audit record dies at the logger level before any handler
is consulted (lastResort emits WARNING+ only). The fix attaches a marked
StreamHandler(sys.stderr) and sets the logger level to INFO, guarded by a
marked-handler presence check so repeated module init / importlib.reload()
cannot duplicate the handler (the Logger singleton survives reloads —
logging.manager keeps strong references; verified independently by peer
review with del+gc.collect()+reimport probes).

## Decisions

- **Handler on the logger object, not by name**: __name__ varies by import
  mode; a name-based lookup would wire the wrong logger in one of the two
  modes.
- **setLevel(INFO) is part of the fix**: with an unconfigured root the
  effective level is WARNING and INFO records are dropped before handlers
  run. The RED tests prove the base drops the line entirely.
- **Idempotence by marked-handler check on the logger object**: module-level
  flags reset on importlib.reload, but the Logger singleton (and its handler
  list) does not — the guard lives on the object, so reloads are safe.
- **No formatter**: the audit message already carries all fields; journald
  attaches its own timestamps. Cosmetic inconsistency with uvicorn's
  prefixed lines accepted (peer-review minor, documented).
- **Relative idempotence pin in tests**: the alias route POST /api/cam1/roi
  delegates to post_analytics_roi and both guards emit (spec #530 D-4,
  pinned by committed TEST-008 test_calibration_alias_records_attempt) — the
  test measures the single-init baseline N and asserts the reload scenario
  emits exactly N instead of pinning a literal count. Reachability tests pin
  presence + exact fields, not counts.
- **No basicConfig / no root changes**: explicitly rejected in the issue
  (global side effects); the wiring is scoped to the identity logger only.

## Affected contours

- API (deployed to VPS — release contour): api/app/identity.py (+20, module
  init only).
- Control plane: tests/test_591_audit_stderr_reachability.py (new), this SDD
  trio. Nothing else — no main.py, worker/, frontend/, deploy/, scripts/,
  .github/ changes.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: logging-only wiring scoped to the identity logger object; idempotence guard proven by reload tests in both import modes; full battery green; AST extraction of guards untouched (wiring placed outside extracted functions) | Validation: tests/test_591_audit_stderr_reachability.py + tests/test_sea_speed_rbac.py + full battery | Residual risk: an external setLevel(WARNING) after import would re-suppress the audit line — no current code path does this (peer-review minor, documented) | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: rides the normal VPS release contour with automatic rollback on failed gates; no schema/deploy plumbing changes | Validation: full battery + ruff + validate_sdd green before merge; post-deploy journalctl probe | Residual risk: standard release-contour deploy risk | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: integration | Priority: P0 | Evidence: tests/test_591_audit_stderr_reachability.py::test_audit_line_reaches_stderr_under_default_startup_app_dir_mode — real subprocess, default startup, TestClient in-process, authorized POST /api/cam1/roi, stderr contains the exact audit fields
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: tests/test_591_audit_stderr_reachability.py::test_audit_line_reaches_stderr_under_default_startup_package_mode — same via the api.app.* package import mode
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P0 | Evidence: tests/test_591_audit_stderr_reachability.py::test_audit_line_emitted_exactly_once_after_repeated_app_init_app_dir_mode — baseline N measured in a single-init subprocess; the reload subprocess must emit exactly N
- TEST-004 | Covers: AC-003 | Level: integration | Priority: P0 | Evidence: tests/test_591_audit_stderr_reachability.py::test_audit_line_emitted_exactly_once_after_repeated_app_init_package_mode — package-mode variant of the relative idempotence pin
- TEST-005 | Covers: AC-004 | Level: integration | Priority: P1 | Evidence: base-stash differential (4/4 fail on base 0d2763ac, line absent) + full battery 1382 OK + ruff clean (observed, see Validation)

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

Lane-A VPS API rollout of the logging fix (same contour as #577); it does
not redeploy Ubuntu or Windows.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production VPS remains on the accepted previous release | Retry: correct exact SHA/quality/authorization evidence then re-enter the protected VPS deploy workflow | Rollback: NOT REQUIRED before mutation | Evidence: exact merged main SHA, push/main Quality integration, wave-1 owner authorization (2026-11-08, continue per last approved plan)
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate release may be staged while current VPS release remains active | Retry: verify staged exact release and previous/current identities then retry | Rollback: NOT REQUIRED while active release is unchanged | Evidence: exact VPS artifact/release manifest and current/previous release markers
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate VPS release may be active but is not accepted until verification succeeds | Retry: only after existing deploy transaction restores or proves a coherent current release | Rollback: existing VPS deploy rollback restores previous exact release | Evidence: repository-owned deploy-vps activation logs
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not accepted | Retry: resolve health/public-smoke failure after actual current release is known | Rollback: automatic previous-release verification through accepted loopback origin and protected public smoke | Evidence: origin health, public smoke, exact API release identity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment evidence is incomplete and completion is forbidden | Retry: verify actual runtime before persisting evidence | Rollback: previous exact VPS release remains the declared rollback target | Evidence: current/previous markers plus runtime-verified deployment manifest
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime remains valid while stale release cleanup may remain pending | Retry: clean stale non-current/non-previous releases independently | Rollback: NOT REQUIRED solely for stale cleanup failure | Evidence: warning-only pruning behavior already regression-protected
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed runtime may be healthy but validation acceptance remains incomplete | Retry: recollect the journalctl audit probe without redeployment when exact runtime identity is unchanged | Rollback: decide from actual API/runtime behavior, not evidence upload alone | Evidence: deployment manifest plus external read-only probe that `journalctl -u sea-speed-api -g "authorized mutation attempt"` now returns records
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if previous exact release cannot be restored/verified, stop automated mutation and recover actual VPS state | Retry: read current/previous/runtime evidence before any new mutation | Rollback: no guessed secondary target; use the protected previous exact VPS release | Evidence: existing VPS rollback logs and verified origin/public health

## Validation

- Focused run `python3 -W error::ResourceWarning -m unittest tests.test_591_audit_stderr_reachability`: OBSERVED 4/4 OK with the fix.
- Base differential: identity.py fix stashed, same focused run on base 0d2763ac → OBSERVED 4/4 FAILED (audit line absent from stderr; the 200-status assertions passed first, so the failure is precisely the missing line) — fix restored byte-identical afterwards.
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'`: OBSERVED 1382 tests OK (skipped=2); baseline without the new file 1378 OK (skipped=2) — delta +4 methods as accounted.
- ruff `ruff check --config scripts/quality/ruff.toml api/` (and the new test file): OBSERVED "All checks passed!".
- `python3 scripts/ci/validate_sdd.py` with this trio: OBSERVED pass before push.
- `python3 scripts/ci/validate_change_contract.py --event <synthetic>` on the PR body: OBSERVED pass before push.

## Runtime feedback

- RF-001: Operator actions expected: 0 — the change rides the normal VPS
  release contour; runtime acceptance = exact-head CI green plus the
  post-deploy probe `journalctl -u sea-speed-api -g "authorized mutation
  attempt"` returning records after the next authorized mutation (0 hits
  today).
- RF-002: no stored-data migration is needed or performed; logging-only.
