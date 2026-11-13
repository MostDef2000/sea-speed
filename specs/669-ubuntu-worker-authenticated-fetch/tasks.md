# Tasks: Ubuntu Worker authenticated fetches (private-repo worker contour)

- Specification: specs/669-ubuntu-worker-authenticated-fetch/spec.md

## Delivery tasks
- [x] F1: deploy/worker/ubuntu/deploy-authorized.sh — move the token read+validation block before the staging fetch (exit-5 semantics and messages unchanged), authenticate the fetch with the env-fed inline credential helper (leading empty credential.helper reset), unset the token after the fetch
- [x] F2: deploy/worker/ubuntu/update-exact.sh — read the token before the staging fetch, authenticate the fetch with the same helper pattern, keep the same token instance for the verify_quality_status.py provenance check, unset after it
- [x] F3: scripts/operations/sea_speed_ubuntu_zero_touch_gate.sh — root mode reads and validates the root-owned token (exists, mode 600, root-owned, non-empty → fail) before the root-mode fetch and authenticates it with the same helper; unprivileged protocol mode untouched; stat added to the required-command list
- [x] F4: .github/workflows/deploy-ubuntu-worker.yml — remove `persist-credentials: false` from the checkout so the composite post-checkout `git fetch` authenticates (composite action untouched)
- [x] F5: contracts/SEA_SPEED_DELIVERY_POLICY.md §10 — drop the "re-fetches public main" claim; the clause now states the gate's and the deploy transaction's fetches authenticate with the root-owned GitHub read token and never embed credentials in URLs or argv
- [x] F6: contract tests — tests/test_ubuntu_worker_deploy_authorized.py (4 pins), tests/test_ubuntu_worker_exact_updater.py (3 pins), tests/test_ubuntu_zero_touch_transport.py (structural gate-fetch pins + executed missing-token fail-closed path + policy-doc pin + harness token-file adaptation), tests/test_autonomous_execution_policy.py (Ubuntu workflow joins the persisted-credentials pin); RED-first on base 5a004e7
- [x] Write the SDD trio specs/669-ubuntu-worker-authenticated-fetch/{spec,plan,tasks}.md and pass scripts/ci/validate_sdd.py
- [ ] Peer verification of the combined diff (independent second worker)
- [ ] Required CI green on the #669 PR
- [ ] Exact-green-head merge complete
- [ ] Lane-A deploy on the merged main SHA (Ubuntu Worker contour; autonomous router path, ubuntu_worker_required=='true')
- [ ] Post-deploy acceptance: Ubuntu Worker deploy succeeds on the private repository — gate fetch, deploy-authorized staging fetch and update-exact fetch all authenticate with the root-owned token; deployment manifest runtime_verified

## Completion gate
- Peer verification of the #669 diff complete
- Required CI green on the #669 PR
- Exact-green-head merge complete
- Lane-A deploy completed and post-deploy acceptance recorded (worker deploy path fetches main authenticated with the existing root-owned token)
- No deferred work: the gate fetch was the last anonymous fetch on the worker contour

## Requirements traceability
- AC-001 | Task: F1 deploy-authorized.sh authenticated staging fetch | Evidence: tests.test_ubuntu_worker_deploy_authorized.UbuntuWorkerAuthenticatedFetchTests → 4 tests, OK (ordering, single block, no-exposure fetch pins, unset-after) | Coverage: COVERED
- AC-002 | Task: F2 update-exact.sh authenticated fetch + shared token instance | Evidence: tests.test_ubuntu_worker_exact_updater.UbuntuWorkerUpdaterAuthenticatedFetchTests → 3 tests, OK | Coverage: COVERED
- AC-003 | Task: F3 gate root-mode authenticated fetch + F5 policy clause | Evidence: tests.test_ubuntu_zero_touch_transport → 28 tests, OK (structural fetch pins, executed missing-token fail-closed, preserved fetch-failure cleanup, policy pin) | Coverage: COVERED
- AC-004 | Task: F4 workflow credential persistence | Evidence: tests.test_autonomous_execution_policy.test_deploy_checkouts_keep_persisted_credentials_for_git_fetch → OK for all three workflows | Coverage: COVERED
- AC-005 | Task: F6 validators + full battery + diff scope | Evidence: validate_sdd.py / validate_repo.py / validate_contracts.py / validate_quality_contracts.py / validate_workflow_policy.py / validate_token_preflight.py / py_compile / ruff outputs and the unittest discover tail quoted in the delivery record | Coverage: COVERED

## Definition of Done
- Issue/spec/plan/tasks current
- Exact changed-file scope verified
- Required tests and evidence complete
- Required CI green
- Exact-green-head merge complete
- Deployment state resolved
- Runtime acceptance resolved
- Deferred work recorded
- Risks resolved or explicitly accepted
- Waivers resolved or current
