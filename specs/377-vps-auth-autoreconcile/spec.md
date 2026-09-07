# Spec: VPS deploy auto-reconcile Auth v1 privileged bundle

- Issue: #377
- Status: ACTIVE
- Specification: specs/377-vps-auth-autoreconcile/spec.md
- Runtime contour: VPS (`deploy/vps/**`); Ubuntu Worker/relay NOT APPLICABLE

## Product outcome

Make the VPS deploy self-sufficient for the Auth v1 privileged bundle: when
`check_auth_privilege_boundary` reports `PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES`
(the installed bundle is bound to a different source SHA than the commit being
deployed), the deploy performs a bounded auto-reconcile via the existing
`reconcile` privileged action (which re-renders the Auth v1 nginx boundary from
the exact release and re-binds the bundle to `COMMIT_SHA`), then re-verifies the
same restricted markers. This removes the recurring manual re-cutover step that
currently blocks every deploy after a commit change.

## User scenarios

- Operator merges a VPS-impacting change: the autonomous deploy proceeds without
  any manual Auth v1 bundle re-cutover on the VPS.
- The deployed bundle remains bound to the exact deployed commit SHA (integrity
  preserved); only the stale bundle is replaced.
- If auto-reconcile fails, the deploy aborts before live source mutation (no
  partial/unverified boundary left behind).

## Requirements

- R1: `check_auth_privilege_boundary` performs a bounded auto-reconcile (privileged
  `reconcile` action) when `status` returns `PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES`
  (bundle SHA mismatch with `COMMIT_SHA`).
- R2: After `reconcile`, re-verify the restricted markers:
  `SEA_SPEED_AUTH_PRIVILEGE_BOUNDARY=PASS`, `SOURCE_SHA=${COMMIT_SHA}`,
  `ACTION=reconcile`, `ARBITRARY_ROOT_EXECUTION=NO`, `SEA_SPEED_AUTH_RECOVERY=PASS`,
  `SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS`. On any missing marker, abort.
- R3: Non-bootstrap errors from `status` (e.g. helper not installed, other rc) still
  abort without attempting reconcile.
- R4: No change to the privileged helper contract (`sea-speed-auth-privileged-helper.py`),
  Auth boundary topology, standing delegation, or #375 frontend scope. The `reconcile`
  action semantics are unchanged; it reuses the exact release at `TARGET_RELEASE`
  (already staged by `download_release` before this gate).

## NFR assessment

- NFR-377-001 | Area: correctness | Target: auto-reconcile triggers ONLY on `PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES`, not on other non-zero rc | Validation: unit test with mocked helper returning bootstrap-required vs other error | Evidence: `tests/test_vps_deploy_transaction.py` | Status: PASS
- NFR-377-002 | Area: security | Target: bundle re-bound to exact `COMMIT_SHA`; no arbitrary root execution; markers re-verified | Validation: test asserts `SOURCE_SHA=${COMMIT_SHA}` + `ARBITRARY_ROOT_EXECUTION=NO` after reconcile; code review | Evidence: `deploy/vps/deploy.sh`, tests | Status: PASS
- NFR-377-003 | Area: reliability | Target: on reconcile failure the deploy aborts (no unverified boundary mutation) | Validation: test with mocked helper failing reconcile returns non-zero and deploy aborts | Evidence: tests | Status: PASS
- NFR-377-004 | Area: maintainability | Target: reuse existing `reconcile` action + marker set (consistent with `recover_auth_boundary_before_source_mutation`) | Validation: grep confirms identical marker checks; no new privilege path | Evidence: `deploy/vps/deploy.sh` | Status: PASS

## Acceptance criteria

- AC-001: A deploy of a new commit whose Auth v1 bundle is stale auto-re-cutovers and
  passes the boundary preflight (no manual operator re-cutover).
- AC-002: `tests/test_vps_deploy_transaction.py` covers `status -> bootstrap-required ->
  reconcile -> PASS` and the reconcile-failure path.
- AC-003: Routine VPS deploys require 0 manual operator Auth boundary actions.

## Runtime feedback

- Prior behaviour: `check_auth_privilege_boundary` aborted on bundle SHA mismatch,
  requiring the operator to manually run `sea-speed-auth-cutover.sh prepare/activate`
  for each new commit. The `reconcile` privileged action already existed (used by
  `recover_auth_boundary_before_source_mutation` on HTTP 500/503), so the fix reuses
  it for the bootstrap-required case, preserving the exact-commit binding.
