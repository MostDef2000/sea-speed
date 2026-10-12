# Tasks: deploy.sh auto-reconcile accepts both helper outcomes (exit-44 marker fix)

- Specification: specs/462-deploy-autoreconcile-marker/spec.md

## Delivery tasks

- T-462-001: RECON the defect (issue #462 ops evidence: deploy runs 38232673841/38232898985 exit 44 after a green reconcile; real helper output grammar — helper.py:487 recovery-only SEA_SPEED_AUTH_RECOVERY=PASS vs normal-path completion markers; deploy.sh unsatisfiable greps :386 and :467; fake-helper infidelity at tests:280) and record in the durable progress file
- T-462-002: Restore fake-helper contract fidelity in tests/test_vps_deploy_transaction.py (normal reconcile path prints SEA_SPEED_AUTH_CUTOVER=PASS, WORKER_PRIVATE_ROAD_API_BASE=..., ROLLBACK_CAPABILITY=VERIFIED, SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS with NO recovery marker; recovery branch untouched; in-file fidelity comment) and capture RED against base deploy.sh: exactly the two mismatch auto-reconcile tests fail with 44 != 0
- T-462-003: Fix deploy/vps/deploy.sh at BOTH pre-mutation verification sites (:386 check_auth_privilege_boundary auto-reconcile block, :467 recover_auth_boundary_before_source_mutation): replace the unconditional recovery-marker grep with the conditional check (output containing SEA_SPEED_AUTH_RECOVERY= must carry =PASS; absence admissible; any other value fails closed, return 44); keep all five fixed marker greps byte-unchanged; keep per-site comments accurate about the two helper outcomes
- T-462-004: Regression coverage: add fake mode recovery-marker-fail; add test_privilege_boundary_mismatch_broken_500_recovery_keeps_recovery_marker_required (AC-2); add test_privilege_boundary_reconcile_recovery_fail_marker_stops_before_live_source_mutation (FAIL-shaped output aborts before live source mutation); strengthen test_privilege_boundary_mismatch_auto_reconciles_before_live_source_mutation (assertNotIn of any recovery marker — fake-fidelity pin) and test_public_500_is_recovered_before_live_source_mutation (assertIn SEA_SPEED_AUTH_RECOVERY=PASS); no existing assertion weakened
- T-462-005: Run the verification battery: file battery 22/22 OK (RED→GREEN); full discover suite 906 OK (skipped=4); validate_repo (649 files); validate_sdd; ruff; bash -n
- T-462-006: Write the SDD trio specs/462-deploy-autoreconcile-marker/ (REQUIRED risk profile; RISK-001..004; TEST-001..007; TX-001..008; AC traceability with 0 operator actions) and keep the PR Change Contract synchronized with the exact diff

## Completion gate

- [x] T-462-001
- [x] T-462-002
- [x] T-462-003
- [x] T-462-004
- [x] T-462-005
- [x] T-462-006
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED authenticity against base deploy.sh with the faithful fake + file battery 20→22/22 OK + full discover 906 OK skipped=4 + validate_repo 649 files + validate_sdd + ruff + bash -n; worker-recorded; exact-head CI is orchestrator-owned)
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (runtime verification lands with the next routine band-A deploy)
- [ ] Runtime acceptance resolved — orchestrator-owned (recorded on issue #462 at the next routine deploy; 0 operator actions)
- [x] Deferred work recorded — none: the site-2 normal-reconcile behavioral gap is accepted as RISK-004 in plan.md, not deferred work
- [x] Risks resolved or explicitly accepted — RISK-001..003 MITIGATED, RISK-004 ACCEPTED in plan.md Risk profile
- [x] Waivers resolved or current — none

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED authenticity against base deploy.sh with the faithful fake + file battery 20→22/22 OK + full discover 906 OK skipped=4 + validate_repo 649 files + validate_sdd + ruff + bash -n; exact-head PR CI is merge-phase, orchestrator-owned)
- [ ] Required CI green — exact-head PR CI — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (next routine band-A VPS deploy verifies the gate end-to-end)
- [ ] Runtime acceptance resolved — orchestrator-owned with recorded output (issue #462; 0 operator actions)
- [x] Deferred work recorded — none (out-of-scope items recorded in the spec Scope section)
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-004 in plan.md Risk profile (RISK-001..003 MITIGATED, RISK-004 ACCEPTED)
- [x] Waivers resolved or current — none

## Requirements traceability

- AC-1 | Task: T-462-002,T-462-003 | Evidence: test_privilege_boundary_mismatch_auto_reconciles_before_live_source_mutation + test_privilege_boundary_mismatch_plain_error_also_auto_reconciles (RED rc 44 at base → GREEN rc 0 with the faithful fake; current=CANDIDATE; recovery marker absent and not required) | Coverage: COVERED
- AC-2 | Task: T-462-003,T-462-004 | Evidence: test_privilege_boundary_mismatch_broken_500_recovery_keeps_recovery_marker_required (recovery path prints SEA_SPEED_AUTH_RECOVERY=PASS and the deploy completes) + test_public_500_is_recovered_before_live_source_mutation (strengthened with assertIn SEA_SPEED_AUTH_RECOVERY=PASS) | Coverage: COVERED
- AC-3 | Task: T-462-004 | Evidence: test_privilege_boundary_mismatch_reconcile_failure_stops_before_live_source_mutation + test_public_500_recovery_failure_stops_before_live_source_mutation (both unchanged and green: non-zero reconcile rc stops before live source mutation, no manifest) | Coverage: COVERED
- AC-4 | Task: T-462-003,T-462-004 | Evidence: diff inspection (the five fixed marker greps byte-unchanged at both sites) + test_privilege_boundary_reconcile_recovery_fail_marker_stops_before_live_source_mutation (corrupted FAIL-shaped output fails closed) + mismatch-normal tests exercising all five markers green | Coverage: COVERED
- AC-5 | Task: T-462-002,T-462-004 | Evidence: fake normal path no longer prints SEA_SPEED_AUTH_RECOVERY=PASS (assertNotIn pin in the mismatch test); recovery branch keeps it (assertIn in recovery tests); in-file fidelity comment binds the fake to helper.py run_cutover | Coverage: COVERED
