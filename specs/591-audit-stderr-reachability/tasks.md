# Tasks — Issue #591 audit line stderr reachability

- Issue: #591
- Specification: specs/591-audit-stderr-reachability/spec.md

## Delivery tasks

- T-1: api/app/identity.py — module-init wiring: marked
  logging.StreamHandler(sys.stderr) attached to the module logger object
  (never by name) + setLevel(INFO), idempotent via a marked-handler presence
  check that survives importlib.reload(). DONE (4/4 green).
- T-2: tests/test_591_audit_stderr_reachability.py — new file, 4
  subprocess-based tests (reachability in app-dir and package import modes;
  relative idempotence pins in both modes), no mocks, no caplog/assertLogs;
  RED on base verified in both directions (stash differential). DONE.
- T-3: specs/591-audit-stderr-reachability/ trio (this spec/plan/tasks).
  DONE.

## Battery identity

Baseline on base 0d2763ac without the new file: 1378 passed / 2 skipped
(orchestrator-observed). Delta: +4 test methods in
tests/test_591_audit_stderr_reachability.py — expected 1382 passed /
2 skipped. Observed: recorded in the completion gate below.

## Completion gate

- Focused `python3 -W error::ResourceWarning -m unittest tests.test_591_audit_stderr_reachability`: OBSERVED 4/4 OK with the fix.
- Base differential (fix stashed): OBSERVED 4/4 FAILED — audit line absent from stderr under default startup (RED authenticity).
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s tests -p 'test_*.py'`: OBSERVED 1382 tests OK (skipped=2).
- ruff `ruff check --config scripts/quality/ruff.toml api/`: OBSERVED "All checks passed!".
- `python3 scripts/ci/validate_sdd.py`: OBSERVED pass with this trio before push.
- `python3 scripts/ci/validate_change_contract.py --event <synthetic>`: OBSERVED pass on the PR body before push.

## Requirements traceability

- AC-001 | Task: T-1+T-2 | Evidence: reachability test, app-dir mode + base-stash differential (4/4 fail on base) | Coverage: COVERED
- AC-002 | Task: T-1+T-2 | Evidence: reachability test, package import mode | Coverage: COVERED
- AC-003 | Task: T-1+T-2 | Evidence: relative idempotence tests in both modes (post-reload count == single-init baseline) | Coverage: COVERED
- AC-004 | Task: T-1+T-2+T-3 | Evidence: full battery 1382 OK (skipped=2), ruff clean, validate_sdd green (observed outputs in the completion gate) | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (api/app/identity.py + 1 test file + this trio)
- [x] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (lane-A VPS API contour)
- [ ] Runtime acceptance resolved (journalctl probe post-deploy)
- [x] Deferred work recorded (none — no deferred work)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
