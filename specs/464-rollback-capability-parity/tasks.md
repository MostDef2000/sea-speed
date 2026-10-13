# Tasks: run_auth_boundary accepts the bounded recovery outcome (rollback-capability parity)

- Specification: specs/464-rollback-capability-parity/spec.md

## Delivery tasks

- T-464-001: RECON the F-4 asymmetry (issue #464): pre-mutation sites accept the identical helper success via the universal =PASS recovery rule (deploy.sh :406-426, :502-523) while the post-mutation run_auth_boundary unconditionally required ROLLBACK_CAPABILITY=VERIFIED (:1007); real helper recovery output grammar (helper.py:448-487 → cutover MANUAL :598/:665-666 + RECOVERY=PASS :487; normal path VERIFIED :500-506); fake recovery branch omitted MANUAL (masking class of #462); record in the durable progress file
- T-464-002: Restore fake-helper fidelity and write RED-first tests in tests/test_vps_deploy_transaction.py: recovery branch prints ROLLBACK_CAPABILITY=MANUAL (+ fidelity comment mirroring the normal-path comment); new fake modes reconcile-recovery (post-mutation bounded-recovery success shape) and capability-missing (no capability marker, no recovery marker); tests (a) test_post_mutation_reconcile_bounded_recovery_accepts_manual_capability and (b) test_normal_reconcile_without_capability_marker_rolls_back; capture RED against base deploy.sh: exactly test (a) fails with 1 != 0 (deploy aborts and rolls back on the honest recovery success); no existing assertion weakened
- T-464-003: Fix deploy/vps/deploy.sh run_auth_boundary: replace the unconditional ROLLBACK_CAPABILITY=VERIFIED grep with the two-outcome capability contract (recovery lines captured via the :422-425 pattern; if present AND universally =PASS require ROLLBACK_CAPABILITY=MANUAL, else require ROLLBACK_CAPABILITY=VERIFIED as today; fail-closed both ways — missing/FAIL-shaped recovery output still returns 1, recovery success without MANUAL returns 1); keep the rc gate, the five fixed marker greps and SEA_SPEED_AUTH_PRIVILEGED_RECONCILE=PASS byte-unchanged; keep run_auth_boundary() present (pinned by tests/test_sea_speed_auth_v1.py:467); leave sea-speed-auth-cutover.sh untouched (byte-pinned by test_sea_speed_auth_v1.py:438)
- T-464-004: Run the verification battery: file battery 25/25 OK (RED→GREEN); full discover suite 917 OK (skipped=4); validate_repo (682 files); validate_sdd; ruff clean (one transient F841 in the new test fixed); bash -n
- T-464-005: Write the SDD trio specs/464-rollback-capability-parity/ (REQUIRED risk profile; RISK-001..004 with Score=P×I; TEST-001..007; correct-course Trigger NONE; TX-001..008 all eight stages; degraded-503 no-marker residual as D-7; run_auth_boundary pin preserved) and keep the PR Change Contract synchronized with the exact diff
- T-464-006: Record the durable progress file (RED/GREEN transcripts, battery counts, residual note) — outside the repo tree; NO commit at worker level (commit/PR/merge orchestrator-owned)

## Completion gate

- [x] T-464-001
- [x] T-464-002
- [x] T-464-003
- [x] T-464-004
- [x] T-464-005
- [x] T-464-006
- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED authenticity against base deploy.sh with the fidelity-fixed fake: exactly test_post_mutation_reconcile_bounded_recovery_accepts_manual_capability failed 1 != 0; file battery 25/25 OK (23 pre-existing + 2 new) + full discover 917 OK skipped=4 + validate_repo 682 files + validate_sdd + ruff clean + bash -n; worker-recorded; exact-head CI is orchestrator-owned)
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (runtime verification lands with the next routine band-A deploy)
- [ ] Runtime acceptance resolved — orchestrator-owned (recorded on issue #464 at the next routine deploy; 0 operator actions)
- [x] Deferred work recorded — the degraded-503 no-capability-marker residual is recorded as D-7 in plan.md and to be flagged on issue #464 (out of scope for this task, not deferred work of this task's ACs)
- [x] Risks resolved or explicitly accepted — RISK-001..003 MITIGATED, RISK-004 ACCEPTED in plan.md Risk profile
- [x] Waivers resolved or current — none

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified
- [x] Required tests and evidence complete (RED authenticity against base deploy.sh with the fidelity-fixed fake + file battery 25/25 OK (23 pre-existing + 2 new) + full discover 917 OK skipped=4 + validate_repo 682 files + validate_sdd + ruff clean + bash -n; exact-head PR CI is merge-phase, orchestrator-owned)
- [ ] Required CI green — exact-head PR CI — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned (next routine band-A VPS deploy verifies the gate end-to-end)
- [ ] Runtime acceptance resolved — orchestrator-owned with recorded output (issue #464; 0 operator actions)
- [x] Deferred work recorded — none within scope (out-of-scope items and the degraded-503 residual recorded in the spec Scope section and plan D-7)
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-004 in plan.md Risk profile (RISK-001..003 MITIGATED, RISK-004 ACCEPTED)
- [x] Waivers resolved or current — none

## Requirements traceability

- AC-1 | Task: T-464-002,T-464-003 | Evidence: test_post_mutation_reconcile_bounded_recovery_accepts_manual_capability (reconcile-recovery fake mode → rc 0, current=CANDIDATE, ROLLBACK_CAPABILITY=MANUAL + SEA_SPEED_AUTH_RECOVERY=PASS in output, manifest check auth_v1_road_private_m2m passed; RED 1 != 0 at base deploy.sh) | Coverage: COVERED
- AC-2 | Task: T-464-003 | Evidence: test_success_commits_all_frontends_boundary_and_state + test_privilege_boundary_mismatch_auto_reconciles_before_live_source_mutation (unchanged, green: normal reconcile VERIFIED accepted, all five fixed markers enforced) + diff inspection (rc gate and fixed marker greps byte-unchanged) | Coverage: COVERED
- AC-3 | Task: T-464-002,T-464-003 | Evidence: test_normal_reconcile_without_capability_marker_rolls_back (capability-missing fake mode → rc 1, current=OLD, api restored to OLD, no recovery marker in output, manifest state=rolled_back; green in both RED and GREEN runs — behavior preserved) | Coverage: COVERED
- AC-4 | Task: T-464-003 | Evidence: test_privilege_boundary_reconcile_recovery_fail_marker_stops_before_live_source_mutation + test_privilege_boundary_reconcile_recovery_fail_with_stray_pass_stops_before_live_source_mutation (non-PASS recovery occurrences fail closed at the pre-mutation sites and never reach the post-mutation gate) + the new gate's else-branch keeps the VERIFIED requirement (fail-closed by construction; recovery success without MANUAL returns 1) | Coverage: COVERED
- AC-5 | Task: T-464-002 | Evidence: fake broken-500 recovery branch prints ROLLBACK_CAPABILITY=MANUAL + SEA_SPEED_AUTH_RECOVERY=PASS with in-file fidelity comment binding it to helper.py run_cutover recovery output (prepare :598 / activate :665-666 / helper :487); reconcile-recovery mode reproduces the same shape; recovery tests assert both markers | Coverage: COVERED
