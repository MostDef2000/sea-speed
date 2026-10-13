# 396 — D-6 Tasks: exact-artifact convergence (bidirectional)

- Issue: #396
- Specification: specs/396-d6-artifact-convergence/spec.md

## Delivery tasks

- [x] T001 RECON: map the exact-artifact validation flow and the precise gap (validator checks only the artifact-inventory side; deploy.sh mirror sites unchecked in both directions) — progress-d6.md
- [x] T002 RED-first evidence: sandbox drift scenarios A (build→deploy) and B (deploy→build) observed exiting 0 against base validator b9309dc; new test module observed failing (ImportError) pre-fix
- [x] T003 Implement: deploy_app_module_targets() + validate_vps_module_convergence() in scripts/quality/validate_exact_artifacts.py, wired into main() after the schema check; required side from COMPONENT_FILES (single source of truth)
- [x] T004 Tests: tests/quality/test_exact_artifact_convergence.py — 5 tests (real-repo equality, parser contract, direction A fail-closed, direction B fail-closed, end-to-end + wiring pin); 5/5 OK
- [x] T005 Trio + validate_sdd grandfather entry for the #396 program follow-up dir (wave-6 D-5 precedent)
- [x] T006 Battery: full suite Ran 915 OK (skipped=4), delta exactly +5; validate_repo 678; validate_sdd; ruff 0.16.10 (CI config) clean; bash -n deploy/vps/deploy.sh OK
- [ ] T007 Required CI is green for the exact merge-head SHA
- [ ] T008 Exact-green-head squash merge to main

## Completion gate

- [ ] Required CI green: T007
- [ ] Exact-green-head merge complete: T008
- [ ] Required local and GitHub CI evidence is green: battery 915/4 + validate_repo 678 + validate_sdd + ruff observed at head; CI tick at merge-head
- [x] Post-restart evidence is recorded: not applicable — CI-tooling-only change, no runtime deploy, no post-restart probes required
- [x] Runtime acceptance resolved: not applicable — no runtime behavior change on any contour (validation-only)
- [ ] PR Change Contract assembled by the delivery orchestrator (VPS deployment: NOT REQUIRED)

## Requirements traceability

- AC-001 | Task: T004 | Evidence: test_real_repo_converges_in_both_directions + test_deploy_targets_parser_ignores_non_python_targets (exactly 10 api/app modules, no frontend targets) | Coverage: COVERED
- AC-002 | Task: T003+T004 | Evidence: test_direction_a_build_module_without_deploy_mirror_fails_closed (SystemExit "not mirrored" naming api/app/ghost_module.py) | Coverage: COVERED
- AC-003 | Task: T003+T004 | Evidence: test_direction_b_deploy_target_without_build_entry_fails_closed (SystemExit "missing from vps required list" on GHOST_TARGET fixture) | Coverage: COVERED
- AC-004 | Task: T002 | Evidence: RED-first observed — sandbox scenarios A and B exit 0 against base validator, exit 1 with fail-closed messages after the fix (progress-d6.md RED/VERIFY sections) | Coverage: COVERED
- AC-005 | Task: T006 | Evidence: battery Ran 915 OK (skipped=4), delta exactly +5; validate_repo 678; validate_sdd; ruff 0.16.10 clean; bash -n OK | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (validator + validate_sdd grandfather line + 1 new test module + this trio; no api/**, no deploy.sh, no workflow changes)
- [x] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [x] Deployment state resolved: VPS deployment NOT REQUIRED — validation-only CI change, no deploy path touched
- [x] Runtime acceptance resolved: not applicable — no runtime behavior change on any contour
- [x] Deferred work recorded: NONE — invariant closed bidirectionally; no residual follow-up (deploy.sh internal seven-site consistency remains covered by the deploy transaction suite, unchanged)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current
