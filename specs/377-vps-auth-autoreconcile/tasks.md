# Tasks: VPS deploy auto-reconcile Auth v1 privileged bundle (#377)

- Specification: specs/377-vps-auth-autoreconcile/spec.md
- Plan: specs/377-vps-auth-autoreconcile/plan.md
- Issue: #377

## Delivery tasks

- T1: Edit `deploy/vps/deploy.sh` `check_auth_privilege_boundary` to auto-reconcile on `PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES` and re-verify restricted markers (R1, R2, R4).
- T2: Add `tests/test_vps_deploy_transaction.py` coverage: bootstrap-required -> reconcile -> PASS (T-377-001), reconcile failure abort (T-377-002), other error without bootstrap aborts (T-377-003).
- T3: `bash -n deploy/vps/deploy.sh` + local CI gates (`validate_sdd`/`validate_repo`/`validate_contracts`/`validate_quality_contracts`/`validate_workflow_policy`) + `python -m unittest discover -s tests`.
- T4: Publish branch via Connector; open PR with Change Contract (VPS REQUIRED, Ubuntu NOT APPLICABLE, production safety envelope REQUIRED, operator actions 0).
- T5: PR CI green (`Repository validation` + `quality-integration`); exact-green-head merge.
- T6: Post-merge `Quality integration gate` (push) + `PR Validation` (push) SUCCESS; `deploy-runtime-autonomous` auto-re-cutovers bundle and passes VPS contour.
- T7: Operator RUNTIME-MANUAL confirms live cam1 overlay (from #375); close #375/#377.

## Requirements traceability

| Requirement | NFR | Test | Status |
|---|---|---|---|
| R1 auto-reconcile on bootstrap-required | NFR-377-001, NFR-377-004 | T-377-001, T-377-003 | DONE in code |
| R2 re-verify restricted markers | NFR-377-002 | T-377-001 | DONE in code |
| R3 non-bootstrap errors abort without reconcile | NFR-377-001 | T-377-003 | DONE in code |
| R4 no helper/topology/delegation change | NFR-377-004 | code review + CI | DONE in code |
| reconcile failure aborts | NFR-377-003 | T-377-002 | DONE in code |

## Completion gate

- `check_auth_privilege_boundary` auto-re-cutovers the Auth v1 bundle for the deployed
  commit when the installed bundle is stale, with identical restricted-marker
  verification as the existing recovery path.
- Unit tests cover the success and failure paths; all local CI gates pass.
- PR merged exact-green-head; post-merge Quality integration gate + PR Validation pass.
- Autonomous VPS deploy succeeds without manual operator re-cutover; deployment
  manifest `runtime_verified` with `auth_v1_road_private_m2m=passed`.
- Operator confirms live cam1 overlay; #375 and #377 closed.
