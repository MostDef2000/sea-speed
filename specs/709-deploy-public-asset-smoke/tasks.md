# Tasks: deploy public-asset smoke — a strict 200-only verifier for the public web-root helper

- Spec: specs/709-deploy-public-asset-smoke/spec.md
- Plan: specs/709-deploy-public-asset-smoke/plan.md
- Issue: #709

## Delivery tasks
- [x] Root cause confirmed on branch agent/fix-login-popup-deploy-smoke: `verify_public_url()` accepts `200|301|302|307|308|401|403`, so a public web-root helper answering 302/401/403/404 counts as a passed smoke, and a non-zero raised inside `verify_frontends` is masked by the trailing root-frontend check inside `if restart_and_verify`
- [x] Strict verifier added: `verify_public_asset_200()` in `deploy/vps/deploy.sh` immediately after `verify_public_url()`, same curl shape (`--silent --show-error --output /dev/null --write-out '%{http_code}' --max-time 15`), accepts ONLY 200, prints `<label> public asset smoke check failed with HTTP ${status}: ${target}` on any other status and `<label> public asset smoke check request failed: ${target}` on a curl transport failure, both returning 1
- [x] Dual success line: on 200 the strict helper logs both the legacy `<label> public smoke check passed with HTTP 200` line and the distinct `<label> public asset smoke check passed with HTTP 200` line, so existing success-smoke assertions are not weakened or rewritten
- [x] Login-popup call site switched inside `verify_frontends`: `verify_public_asset_200 "Login popup module" "$LOGIN_POPUP_URL" || return 1`, with the existing `[[ -f "$LOGIN_POPUP_TARGET" ]]` presence guard and its "absent in this rollback release" branch preserved
- [x] Permissive verifier preserved byte-identical: `verify_public_url()` still accepts `200|301|302|307|308|401|403` and still logs its existing pass line, so the protected operator assets behind authentik are unaffected
- [x] Regression tests added, additive only, in `tests/test_vps_deploy_transaction.py`: `test_deploy_defines_strict_200_only_public_asset_verifier` (source pin that a dedicated 200-only verifier exists and `verify_public_url` was not tightened), `test_login_popup_smoke_block_calls_strict_public_asset_verifier` (source pin that the login-popup block calls it and the permissive call is gone), `test_login_popup_smoke_is_strict_public_asset_check` (behavioral: per-URL statuses 302/401/403/404 must fail closed with rollback, 200 must pass with the distinct log line)
- [x] RED then GREEN proof for the new tests: RED before the fix 7 failed / 24 passed; GREEN after the fix 27 passed plus 13 subtests
- [x] Full battery and static gates green: 1432 tests OK (skipped=2); repo, contracts, quality, workflow and token validators PASS; ruff PASS; `bash -n deploy/vps/deploy.sh` OK
- [x] Write the SDD trio `specs/709-deploy-public-asset-smoke/{spec,plan,tasks}.md`
- [ ] PR #709 Change Contract declares exactly `Production impact: VPS`, `VPS deployment: REQUIRED`, `VPS execution capability: CONNECTOR`, `Ubuntu worker/relay update: NOT REQUIRED`, `Ubuntu worker execution capability: NOT APPLICABLE`, `Production safety envelope: REQUIRED`, `Operator actions expected: 0`, plus `Risk profile: REQUIRED` and `Specification: specs/709-deploy-public-asset-smoke/spec.md`
- [ ] Exact-head CI on PR #709 green, including the three new tests, the SDD validator for this trio, the contracts, quality, workflow and token validators, ruff and `bash -n`
- [ ] Exact-green-head merge of PR #709 to main
- [ ] Lane-A deploy of the merged main SHA dispatched with the DEPLOY-TRIGGER evidence (repo, full 40-hex SHA from origin/main, acceptance probes, rollback target `944a2c48637d801eb76d3ab102d74182c34e209a`)
- [ ] Post-deploy public fetch of `https://mostdef.ru/login-popup.js` returns HTTP 200 with the expected helper markers, and the deploy log carries `Login popup module public asset smoke check passed with HTTP 200`

## Completion gate
- The deploy-script diff contains only the new `verify_public_asset_200()` helper and the login-popup call-site switch; `verify_public_url()` and every other check in `verify_frontends` are byte-identical, and no other file under `deploy/**` changes
- The test diff is additive only — three new tests, no existing assertion weakened — and the full battery stays at 1432 tests OK (skipped=2) with validators, ruff and `bash -n` green
- The PR Change Contract declares the VPS REQUIRED fields listed in the delivery tasks, because `deploy/vps/deploy.sh` is in the diff and the autonomous policy derives `VPS deployment: REQUIRED` from the path
- Exact-head CI green on PR #709, PR merged to main with exact-green-head evidence, then the lane-A deploy of that merged SHA completes with the strict smoke line in its log
- Runtime acceptance is the post-deploy public fetch of `https://mostdef.ru/login-popup.js` returning HTTP 200 with the expected markers; the rollback target for the deploy is the previous main `944a2c48637d801eb76d3ab102d74182c34e209a`

## Requirements traceability
- AC-001 | Task: dedicated strict 200-only public-asset verifier added while `verify_public_url` keeps its permissive `200|301|302|307|308|401|403` contract | Evidence: tests/test_vps_deploy_transaction.py::test_deploy_defines_strict_200_only_public_asset_verifier and the read-back of `verify_public_url()` in deploy/vps/deploy.sh | Coverage: COVERED
- AC-002 | Task: login-popup smoke block calls the strict verifier and emits both the legacy and the distinct success line on 200 | Evidence: tests/test_vps_deploy_transaction.py::test_login_popup_smoke_block_calls_strict_public_asset_verifier plus the 200 branch of test_login_popup_smoke_is_strict_public_asset_check asserting `Login popup module public asset smoke check passed with HTTP 200` alongside the legacy line | Coverage: COVERED
- AC-003 | Task: a 302, 401, 403 or 404 for the login-popup URL fails the deploy closed with rollback and a clear error, not swallowed by the trailing root-frontend check | Evidence: tests/test_vps_deploy_transaction.py::test_login_popup_smoke_is_strict_public_asset_check — each status subtest asserts non-zero exit, old release restored, `Login popup module` and `HTTP <status>` in the output, absence of the permissive pass-through line, `rolled_back` manifest and `Rollback successful` | Coverage: COVERED
- AC-004 | Task: full battery and validators stay green with no existing assertion weakened | Evidence: 1432 tests OK (skipped=2); repo, contracts, quality, workflow and token validators PASS; ruff PASS; `bash -n deploy/vps/deploy.sh` OK; the three new tests are the only test changes and all earlier assertions remain untouched | Coverage: COVERED

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
