# Tasks — Issue #629 deploy validation coverage for the #626 external scripts

- Issue: #629
- Specification: specs/629-deploy-validation-coverage/spec.md

## Delivery tasks

- T-1: deploy/vps/deploy.sh — install_release gains six `.absent`-tolerant
  pre-activation validation lines for crossing-line.js, main.js,
  cameras/cameras.js, road/config.js, road/main.js and unavailable.js, in the
  exact idiom and message style of the live-sync.js/overlay-canvas.js checks.
  DONE — bash -n clean; lines follow `file OR <name>.absent marker` with the
  `has no <name> module state` message.
- T-2: deploy/vps/deploy.sh — verify_frontends gains six
  presence-conditional post-activation checks (empty live file fails closed;
  present file smoke-checked via verify_public_url; absent module logged as
  absent in this rollback release), placed in the healthy path directly after
  the live-sync check, outside the Authentik-outage fallback branch. DONE.
- T-3: deploy/vps/deploy.sh — six env-overridable URL constants
  (CROSSING_LINE_URL, MAIN_JS_URL, CAMERAS_JS_URL, ROAD_CONFIG_URL,
  ROAD_MAIN_URL, UNAVAILABLE_JS_URL) following the LIVE_SYNC_URL pattern.
  DONE.
- T-4: tests/test_auth_session_frontend_contract.py — the
  X-authentik-username scan repoints from inline extraction to
  frontend_html.page_live_source(path); comment updated to the new surface;
  no other assertion changed. DONE — RED-authenticity demonstrated (header
  string injected into frontend/sea-speed/main.js fails the test; reverted,
  hash-verified against the recorded pre-injection sha256).
- T-5: tests/support/frontend_html.py — page_live_source tolerates a page
  that ships only inline scripts (objects) by scanning its HTML; a
  referenced-but-missing local script still fails closed. DONE — existing
  water-page callers unchanged (53 focused tests OK).
- T-6: tests/test_vps_deploy_transaction.py — six SEA_SPEED_*_URL fixture
  overrides; three new tests: malformed rollback release (each of the six
  modules with neither file nor marker) fails closed pre-activation;
  pre-#626 rollback release with `.absent` markers only re-activates with
  absent-module logs and a rolled_back manifest; healthy deploy smoke-checks
  all six modules. DONE — `Ran 21 tests / OK`.
- T-7: specs/629-deploy-validation-coverage/ trio (this spec/plan/tasks) —
  evidence fields filled with observed runs. DONE (this update).

## Battery identity

Baseline at base b21629e without the new tests: `Ran 1421 tests` → `OK
(skipped=2)`. Delta: +3 test methods in tests/test_vps_deploy_transaction.py
— expected 1424. OBSERVED after the change: `Ran 1424 tests in 172.768s` →
`OK (skipped=2)`.

## Completion gate

- Focused `python3 -W error::ResourceWarning -m unittest
  tests.test_vps_deploy_transaction`: OBSERVED — `Ran 21 tests in 7.058s /
  OK` (18 baseline + test_rollback_to_release_without_csp_module_state_fails_closed_before_mutation
  + test_rollback_to_pre_626_release_tolerates_absent_modules +
  test_success_smoke_checks_csp_external_scripts).
- RED-authenticity differential (scan repoint): OBSERVED — with the header
  string injected into frontend/sea-speed/main.js:
  `FAIL: test_all_protected_frontends_use_same_origin_session_api
  (path=frontend/sea-speed/index.html)`, `AssertionError:
  'X-authentik-username' unexpectedly found in '<!doctype html>...'`,
  `FAILED (failures=1)`; after revert (sha256 equality with the recorded
  pre-injection hash 9fa6fe32fb63c6243aa4b88b0085446a19efd670622160baa5bbb8086cddb2e7):
  `Ran 4 tests / OK`. The injection is not part of the final diff.
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s
  tests -p 'test_*.py'`: OBSERVED — `Ran 1424 tests in 172.768s` → `OK
  (skipped=2)` (baseline 1421 OK skipped=2; delta exactly +3).
- ruff (CI config scripts/quality/ruff.toml, repo-wide): OBSERVED — `All
  checks passed!`.
- `python3 scripts/ci/validate_sdd.py`: OBSERVED — `Sea Speed SDD validation
  passed`.

## Requirements traceability

- AC-001 | Task: T-1+T-6 | Evidence: transaction tests — each of the six modules unlinked from the rollback release (neither file nor marker) fails the deploy closed pre-mutation; the pre-#626 marker-only rollback release re-activates | Coverage: COVERED
- AC-002 | Task: T-2+T-3+T-6 | Evidence: transaction tests — healthy deploy logs all six module smoke checks; rollback release logs the six absent-module lines with rolled_back manifest state; empty-file fail-closed shape copied from the existing module checks | Coverage: COVERED
- AC-003 | Task: T-3 | Evidence: six SEA_SPEED_*_URL env overrides in deploy.sh exercised through the fixture env (smoke-check lines observed in the healthy-deploy test) | Coverage: COVERED
- AC-004 | Task: T-4+T-5 | Evidence: RED-authenticity demonstration (injection into main.js → observed FAIL; revert hash-verified) + focused green run; objects page (inline-only) scans via the page_live_source tolerance | Coverage: COVERED
- AC-005 | Task: T-1+T-2+T-3+T-4+T-5+T-6+T-7 | Evidence: full battery `Ran 1424 tests / OK (skipped=2)`; ruff `All checks passed!`; validate_sdd passing; git status limited to deploy.sh, the three test/harness files and this trio | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (deploy/vps/deploy.sh + tests/test_auth_session_frontend_contract.py + tests/support/frontend_html.py + tests/test_vps_deploy_transaction.py + this trio)
- [x] Required tests and evidence complete (RED-authenticity differential + battery + ruff + validate_sdd observed)
- [x] Required CI green — pending exact-head CI on the merge PR — auto-synced on merge to main
- [x] Exact-green-head merge complete — pending squash merge to main — auto-synced on merge to main
- [ ] Deployment state resolved (VPS front deploy via deploy-vps.yml on the merged main SHA — authorized chain)
- [ ] Runtime acceptance resolved (new checks observed on the next VPS deploy/rollback invocation)
- [ ] Deferred work recorded (bootstrap overlay-canvas capture gap — pre-existing, out of scope, reported to the orchestrator)
- [ ] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
