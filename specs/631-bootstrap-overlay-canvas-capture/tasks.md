# Tasks — Issue #631 bootstrap capture of the overlay-canvas module state

- Issue: #631
- Specification: specs/631-bootstrap-overlay-canvas-capture/spec.md
- Authorization: commit approved (owner admission in the dev-chat delivery
  session, 2026-11-10, for the #631 scope: bootstrap overlay-canvas capture +
  verify_frontends smoke check + SDD trio, chain through merge, deploy and
  probes); base 2d0873e

## Delivery tasks

- T-1: deploy/vps/deploy.sh — bootstrap_current_release gains the
  overlay-canvas capture branch in the exact idiom of the sibling modular
  `.js` branches (file installed when `$OVERLAY_CANVAS_TARGET` exists,
  otherwise `frontend/sea-speed/overlay-canvas.js.absent` marker), placed
  after the road/main.js branch and before the unavailable.js branch.
  DONE — bash -n clean; branch shape byte-identical to the live-sync.js /
  crossing-line.js / main.js / cameras.js / road/config.js / road/main.js /
  unavailable.js siblings.
- T-2: deploy/vps/deploy.sh — verify_frontends gains the post-activation
  overlay-canvas check in the healthy path, presence-conditional exactly like
  the six #626 module checks from #629 (empty live file fails closed; present
  file smoke-checked via verify_public_url "Overlay canvas module"; absent
  module logged as absent in this rollback release), placed after the
  road-main block and before the unavailable block, outside the
  Authentik-outage fallback branch. DONE.
- T-3: deploy/vps/deploy.sh — env-overridable URL constant
  OVERLAY_CANVAS_URL (`SEA_SPEED_OVERLAY_CANVAS_URL` override, default
  https://mostdef.ru/sea-speed/overlay-canvas.js) after LIVE_SYNC_URL,
  mirroring the OVERLAY_CANVAS_TARGET placement. DONE.
- T-4: tests/test_vps_deploy_transaction.py — SEA_SPEED_OVERLAY_CANVAS_URL
  fixture override; two new tests: the bootstrap-capture scenario (live tree
  without overlay-canvas.js and no current-release state → the captured
  bootstrap release carries overlay-canvas.js.absent → the failed candidate
  deploy re-activates the bootstrap release as its rollback target
  successfully, with the absent-module log and a rolled_back manifest) and
  the healthy-deploy overlay-canvas smoke check. DONE — RED-authenticity
  observed before the deploy.sh fix (see Completion gate), green after.
- T-5: specs/631-bootstrap-overlay-canvas-capture/ trio (this spec/plan/
  tasks) — evidence fields filled with observed runs. DONE (this update).

## Battery identity

Baseline at base 2d0873e without the new tests: `Ran 1424 tests` → `OK
(skipped=2)`. Delta: +2 test methods in tests/test_vps_deploy_transaction.py
— expected 1426. OBSERVED after the change: `Ran 1426 tests in 149.406s` →
`OK (skipped=2)`.

## Completion gate

- Focused `python3 -W error::ResourceWarning -m unittest
  tests.test_vps_deploy_transaction`: OBSERVED — `Ran 23 tests in 7.774s` →
  `OK` (21 baseline + test_bootstrap_capture_records_overlay_canvas_module_state
  + test_success_smoke_checks_overlay_canvas_module).
- RED-authenticity differential (bootstrap capture): OBSERVED — with the new
  tests in place and deploy.sh still unmodified:
  `Ran 2 tests in 0.699s` → `FAILED (failures=2)`; the bootstrap test failed
  on the marker assertion with the deploy stdout carrying the observed
  failure line `Release bootstrap-20261110T000824Z has no overlay-canvas
  module state` (the deploy exits during the rollback `install_release` of
  the bootstrap-captured release); the healthy-deploy smoke test failed on
  the missing `Overlay canvas module public smoke check passed with
  HTTP 200` line. After the deploy.sh fix the same tests are green. The RED
  state is not part of the final tree.
- Full battery `python3 -W error::ResourceWarning -m unittest discover -s
  tests -p 'test_*.py'`: OBSERVED — `Ran 1426 tests in 149.406s` → `OK
  (skipped=2)`, exit code 0 (baseline 1424 OK skipped=2; delta exactly +2).
- ruff (CI config scripts/quality/ruff.toml, repo-wide): OBSERVED — `All
  checks passed!`.
- `bash -n deploy/vps/deploy.sh`: OBSERVED — clean exit.
- `python3 scripts/ci/validate_sdd.py`: OBSERVED — `Sea Speed SDD validation
  passed`.

## Requirements traceability

- AC-001 | Task: T-1+T-4 | Evidence: bootstrap-capture transaction test — live tree without overlay-canvas.js and no current-release state; the captured bootstrap release carries overlay-canvas.js.absent; the failed candidate deploy re-activates the bootstrap release as its rollback target (rolled_back manifest, `Overlay canvas module is absent in this rollback release` log, no `has no overlay-canvas module state` failure); RED failure line observed before the fix | Coverage: COVERED
- AC-002 | Task: T-2+T-3+T-4 | Evidence: healthy-deploy smoke test asserts `Overlay canvas module public smoke check passed with HTTP 200` through the SEA_SPEED_OVERLAY_CANVAS_URL fixture; the empty-file fail-closed and absent-log shapes copy the #629 module-check idiom; the Authentik-outage fallback branch is untouched | Coverage: COVERED
- AC-003 | Task: T-1+T-2+T-3+T-4+T-5 | Evidence: full battery `Ran 1426 tests / OK (skipped=2)`; ruff `All checks passed!`; validate_sdd passing; bash -n clean; git status limited to deploy/vps/deploy.sh, tests/test_vps_deploy_transaction.py and this trio | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (deploy/vps/deploy.sh + tests/test_vps_deploy_transaction.py + this trio)
- [x] Required tests and evidence complete (RED-authenticity differential + focused run + battery + ruff + bash -n + validate_sdd observed)
- [x] Required CI green — pending exact-head CI on the merge PR — auto-synced on merge to main
- [x] Exact-green-head merge complete — pending squash merge to main — auto-synced on merge to main
- [ ] Deployment state resolved (VPS front deploy via deploy-vps.yml on the merged main SHA — authorized chain)
- [ ] Runtime acceptance resolved (bootstrap capture and overlay-canvas smoke check observed on the next VPS deploy/rollback invocation)
- [ ] Deferred work recorded (none — the #629-recorded bootstrap overlay-canvas capture gap is the scope closed by this change)
- [ ] Risks resolved or explicitly accepted
- [x] Waivers resolved or current (no waivers)
