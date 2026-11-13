# Tasks: private-repo deploy chain (protected main without public visibility)

- Specification: specs/668-private-repo-deploy-chain/spec.md

## Delivery tasks
- [x] F1: scripts/release/verify_source_protection.py — delete the public-visibility hard gate, keep the protection/required-context fail-closed checks and error fragments, print the actual visibility derived from the repository payload
- [x] F2: remove `persist-credentials: false` from the checkouts in .github/workflows/deploy-runtime-autonomous.yml and .github/workflows/deploy-vps.yml so the post-checkout `git fetch` steps authenticate (deploy-ubuntu-worker.yml checkout untouched)
- [x] F3: deploy-vps.yml — add "Pre-place exact source archive on VPS" step (git archive of the verified DEPLOY_SHA, idempotent remote mkdir, scp with the deploy step's identity/options, VPS_HOST/VPS_USER guards, no tokens in argv/logs); deploy/vps/deploy.sh download_release — use the pre-placed archive (SEA_SPEED_RELEASE_ARCHIVE override, default $DEPLOY_ROOT/state/<SHA>.tar.gz) with the curl fallback intact and shared sha256/completeness/extraction
- [x] F4: rename the flow marker to "Verify protected production source" atomically in the three deploy workflows (step name, comment markers, summary lines), .github/actions/verify-exact-release/action.yml (step name, description) and scripts/quality/validate_workflow_policy.py (markers + success text); repo-wide grep clean outside tests/ and historical specs/
- [x] F5: rewrite the public-visibility mandates in contracts/SEA_SPEED_DELIVERY_POLICY.md, contracts/runtime/RELEASE_READINESS_GATE.md, contracts/branches/deploy.md, specs/README.md, docs/WORKFLOW_OVERVIEW.md, docs/operations/UBUNTU_ZERO_TOUCH_DEPLOYMENT.md (minimum diff)
- [x] Write the SDD trio specs/668-private-repo-deploy-chain/{spec,plan,tasks}.md and pass scripts/ci/validate_sdd.py
- [ ] Peer verification of the combined diff (independent second worker)
- [ ] Required CI green on the #668 PR
- [ ] Exact-green-head merge complete
- [ ] Lane-A deploy on the merged main SHA (VPS contour; autonomous router path)
- [ ] Post-deploy acceptance: autonomous VPS deploy succeeds on the private repository — freshness fetch authenticates, source protection admits the private repo, archive is pre-placed (no curl fallback), deployment manifest runtime_verified
- [ ] Follow-up issue filed: Ubuntu Worker private-repo contour (checkout credential persistence + archive transport through the forced-command protocol)

## Completion gate
- Peer verification of the #668 diff complete
- Required CI green on the #668 PR
- Exact-green-head merge complete
- Lane-A deploy completed and post-deploy acceptance recorded (private-repo deploy chain works fail-closed)
- Follow-up issue for the Ubuntu Worker contour recorded

## Requirements traceability
- AC-001 | Task: F1 source-protection trust model | Evidence: tests.test_production_source_protection → Ran 7 tests, OK (admit private-protected; deny unprotected/missing-check with exact fragments) | Coverage: COVERED
- AC-002 | Task: F2 credential persistence + F4 marker rename | Evidence: tests.test_autonomous_execution_policy → Ran 11 tests, OK (parsed-YAML persisted-credentials twin, flow-marker twin, policy chain unchanged) | Coverage: COVERED
- AC-003 | Task: F3 archive transport (workflow step + deploy.sh) | Evidence: tests.test_vps_deploy_transaction → Ran 24 tests, OK (sentinel-curl proves pre-placed archive skips curl, sha256 recorded, deploy succeeds; transaction matrix green) | Coverage: COVERED
- AC-004 | Task: validators + full battery + diff scope | Evidence: validate_workflow_policy.py / validate_quality_contracts.py / validate_sdd.py / validate_repo.py outputs and the unittest discover tail quoted in the PR delivery record | Coverage: COVERED

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
