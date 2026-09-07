# Plan: VPS deploy auto-reconcile Auth v1 privileged bundle (#377)

- Specification: specs/377-vps-auth-autoreconcile/spec.md
- Issue: #377
- Runtime contour: VPS (`deploy/vps/**`); Ubuntu Worker/relay NOT APPLICABLE

## Architecture

- `deploy/vps/deploy.sh` `check_auth_privilege_boundary` is the restricted gate that
  runs before any live source mutation. It writes a privileged request with
  `action: status` and verifies the installed Auth v1 bundle is bound to `COMMIT_SHA`.
- On `PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES` (bundle bound to a different source
  SHA), the gate now performs a bounded auto-reconcile: it writes a request with
  `action: reconcile` and re-verifies the same restricted markers. The `reconcile`
  action re-renders the Auth v1 nginx boundary from the exact release at
  `TARGET_RELEASE` (already staged by `download_release`) and re-binds the bundle to
  `COMMIT_SHA`.
- No change to the privileged helper binary, its forced-command boundary, the Auth
  topology, or standing delegation. The `reconcile` action is the same one already
  used by `recover_auth_boundary_before_source_mutation` on HTTP 500/503.

## Decisions

- Reuse the existing `reconcile` privileged action for the bootstrap-required case
  instead of adding a new privilege path; this preserves the exact-commit binding and
  the restricted marker set.
- Trigger auto-reconcile ONLY on the exact `PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES`
  token; any other non-zero status rc still aborts unchanged (no silent recovery).
- Keep rollback MANUAL for the cutover (identical to the existing recovery path); the
  deploy's own source rollback (`install_release "$old_current"`) still protects the
  application code on failure.

## Affected contours

- VPS only: `deploy/vps/deploy.sh` (one function), `tests/test_vps_deploy_transaction.py`,
  `specs/377-vps-auth-autoreconcile/*`.
- Ubuntu Worker/relay: NOT affected.
- Runtime contour: VPS. Production safety envelope: REQUIRED.

## Validation

- `python3 -m unittest discover -s tests -p "test_*.py"` (643 tests, green).
- `python3 scripts/ci/validate_sdd.py`, `validate_repo.py`, `validate_contracts.py`,
  `validate_quality_contracts.py`, `validate_workflow_policy.py`.
- `bash -n deploy/vps/deploy.sh`.
- New tests: `test_privilege_boundary_mismatch_auto_reconciles_before_live_source_mutation`
  (bootstrap-required -> reconcile -> PASS), `test_privilege_boundary_mismatch_reconcile_failure_stops_before_live_source_mutation`
  (reconcile fails -> abort), `test_other_priv_status_error_without_bootstrap_aborts_before_live_source_mutation`
  (other error -> no reconcile).
- Operator RUNTIME-MANUAL: after autonomous deploy, confirm live cam1 overlay (from #375)
  and that the Auth v1 boundary remains auth-gated.

## Runtime feedback

- Root cause (observed): `check_auth_privilege_boundary` aborted on bundle SHA mismatch,
  requiring the operator to manually run `sea-speed-auth-cutover.sh prepare/activate` for
  each new commit. The `reconcile` privileged action already existed (used by the 500/503
  recovery path), so the fix reuses it for the bootstrap-required case, preserving the
  exact-commit binding and removing the recurring manual step.

## Risk profile

- Risk profile: REQUIRED

- RISK-377-001 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: reuses existing restricted reconcile action + forced-command boundary; bundle re-bound only to exact COMMIT_SHA; all restricted markers re-verified; on failure deploy aborts before live source mutation | Validation: unit tests T-377-001/T-377-002 + code review | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-377-002 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: deploy aborts on reconcile failure; application source rolled back via install_release; operator RUNTIME-MANUAL verifies boundary after deploy | Validation: T-377-002; deployment manifest | Residual risk: LOW | Owner: operator | Status: MITIGATED
- RISK-377-003 | Category: TECH | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: reconcile attempted ONLY when output contains PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES; other non-zero rc aborts unchanged | Validation: T-377-003 | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-377-004 | Category: TECH | Probability: 1 | Impact: 1 | Score: 1 | Mitigation: explicit unit tests for success + failure paths; full local CI gate | Validation: T-377-001..T-377-004; unittest | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-377-001 | Covers: AC-001, AC-002 | Level: integration | Priority: P0 | Evidence: tests/test_vps_deploy_transaction.py::test_privilege_boundary_mismatch_auto_reconciles_before_live_source_mutation asserts bootstrap-required -> reconcile -> PASS and deploy proceeds
- TEST-377-002 | Covers: AC-001, AC-003 | Level: integration | Priority: P0 | Evidence: tests/test_vps_deploy_transaction.py::test_privilege_boundary_mismatch_reconcile_failure_stops_before_live_source_mutation asserts reconcile failure aborts before live source mutation
- TEST-377-003 | Covers: R3 | Level: integration | Priority: P1 | Evidence: tests/test_vps_deploy_transaction.py::test_other_priv_status_error_without_bootstrap_aborts_before_live_source_mutation asserts other error without bootstrap marker aborts without reconcile
- TEST-377-004 | Covers: R2, R4 | Level: unit | Priority: P1 | Evidence: bash -n + full local CI + grep confirms identical marker set to recover_auth_boundary_before_source_mutation

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-377-01 | Stage: ADMISSION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: scope recorded in #377 | Retry: NONE | Rollback: NONE | Evidence: Sea Speed Delivery Checkpoint v2 in #377
- TX-377-02 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: branch unchanged | Retry: NONE | Rollback: NONE | Evidence: branch agent/vps-auth-autoreconcile from origin/main 3cd3fcac
- TX-377-03 | Stage: MUTATION | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: working tree revertible | Retry: NONE | Rollback: git revert of feature commit | Evidence: deploy.sh check_auth_privilege_boundary + tests
- TX-377-04 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: CI red blocks merge | Retry: rerun CI | Rollback: NONE | Evidence: required CI green on PR
- TX-377-05 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: BEST-EFFORT | State after failure: main protected, revert merge | Retry: NONE | Rollback: revert merge commit | Evidence: exact-green-head merge to main
- TX-377-06 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: issue reopened | Retry: NONE | Rollback: NONE | Evidence: #377 closed; #375 noted as beneficiary
- TX-377-07 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: re-run evidence collection | Retry: NONE | Rollback: NONE | Evidence: PR linked to #377; Change Contract VPS REQUIRED / Ubuntu NOT
- TX-377-08 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: previous bundle + source restored | Retry: NONE | Rollback: revert merge + VPS redeploy prior good commit | Evidence: bundle re-cutover is manual fallback; source rollback via install_release
