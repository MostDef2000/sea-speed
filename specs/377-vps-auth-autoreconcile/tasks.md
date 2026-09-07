# Tasks: VPS deploy auto-reconcile Auth v1 privileged bundle (#377)

- Specification: specs/377-vps-auth-autoreconcile/spec.md
- Plan: specs/377-vps-auth-autoreconcile/plan.md
- Issue: #377

## Delivery tasks

- T-377-001 [x] Edit `deploy/vps/deploy.sh` `check_auth_privilege_boundary` to auto-reconcile on `PRIVILEGE_BOUNDARY_BOOTSTRAP_REQUIRED=YES` and re-verify restricted markers (R1, R2, R4)
- T-377-002 [x] Add `tests/test_vps_deploy_transaction.py` coverage: bootstrap-required -> reconcile -> PASS (T-377-001), reconcile failure abort (T-377-002), other error without bootstrap aborts (T-377-003)
- T-377-003 [x] Validate `bash -n deploy/vps/deploy.sh` + local CI gates (`validate_sdd`/`validate_repo`/`validate_contracts`/`validate_quality_contracts`/`validate_workflow_policy`) + `python -m unittest discover -s tests` (643 tests)
- T-377-004 [x] Publish branch `agent/vps-auth-autoreconcile` via Connector; open PR #378 with Change Contract (VPS REQUIRED, Ubuntu NOT APPLICABLE, production safety envelope REQUIRED, operator actions 0)
- T-377-005 [ ] PR CI green (`Repository validation` + `quality-integration` 4 domains); exact-green-head merge
- T-377-006 [ ] Post-merge `Quality integration gate` (push) + `PR Validation` (push) SUCCESS; `deploy-runtime-autonomous` auto-re-cutovers bundle and passes VPS contour
- T-377-007 [ ] Operator RUNTIME-MANUAL confirms live cam1 overlay (from #375) and Auth v1 boundary; close #375/#377

## Requirements traceability

- AC-001 | Task: T-377-001, T-377-002, T-377-004 | Evidence: `deploy/vps/deploy.sh` auto-reconcile path + `tests/test_vps_deploy_transaction.py::test_privilege_boundary_mismatch_auto_reconciles_before_live_source_mutation` | Coverage: COVERED
- AC-002 | Task: T-377-002, T-377-003 | Evidence: `tests/test_vps_deploy_transaction.py` 3 new tests cover success and failure paths + `bash -n` | Coverage: COVERED
- AC-003 | Task: T-377-001, T-377-002, T-377-006 | Evidence: autonomous VPS deploy without manual re-cutover; `deployment-manifest.json` `auth_v1_road_private_m2m=passed` + operator RUNTIME-MANUAL | Coverage: RUNTIME-MANUAL | Reason: requires exact deployed bundle on live VPS and autonomous deploy evidence; not reproducible in CI without production Auth v1 boundary

## Definition of Done

- [x] Issue/spec/plan/tasks current — #377 outcome, scope and SDD linked
- [x] Exact changed-file scope verified — `deploy/vps/deploy.sh`, `tests/test_vps_deploy_transaction.py`, `specs/377-vps-auth-autoreconcile/*` only
- [x] Required tests and evidence complete — 643 tests PASS including 3 new VpsDeployTransactionTests; `bash -n` PASS; local validators PASS
- [ ] Required CI green — PR exact head must pass PR Validation and Quality integration, then exact-main Quality
- [ ] Exact-green-head merge complete — merge only after fresh base/head and required checks green
- [ ] Deployment state resolved — autonomous VPS deploy with auto-reconcile pending post-merge Quality
- [ ] Runtime acceptance resolved — operator RUNTIME-MANUAL cam1 overlay and Auth boundary pending
- [ ] Deferred work recorded — none; next is PR merge, autonomous deploy, runtime acceptance
- [x] Risks resolved or explicitly accepted — Risk profile REQUIRED with 4 mitigated risks (SEC-6, OPS-4, TECH-2, TECH-1)
- [x] Waivers resolved or current — no waiver

## Completion gate

- `check_auth_privilege_boundary` auto-re-cutovers the Auth v1 bundle for the deployed commit when the installed bundle is stale, with identical restricted-marker verification as the existing recovery path
- Unit tests cover the success and failure paths; all local CI gates pass
- PR merged exact-green-head; post-merge Quality integration gate + PR Validation pass
- Autonomous VPS deploy succeeds without manual operator re-cutover; deployment manifest `runtime_verified` with `auth_v1_road_private_m2m=passed`
- Operator confirms live cam1 overlay; #375 and #377 closed
