# Tasks: Shared kernel extraction — api/app/config.py + api/app/identity.py (Wave 1)

- Specification: specs/396-wave1-shared-kernel/spec.md

## Delivery tasks

- T001: Extract `api/app/config.py` (stdlib-only constants block +
  import-time mkdir side effects, single owner, documented single-instance
  rule) and `api/app/identity.py` (`now_iso`, `deployed_source_commit`,
  `require_auth`, `require_operator_identity`, `analytics_identity`,
  `worker_control_origin`, `call_worker_control`) from `api/app/main.py` by
  line-range copy; add thin explicit re-exports in `main.py` under the
  existing dual package/direct-file import idiom (no behavior change, routes
  untouched)
- T002: Re-pin the AST/text harnesses that reference moved functions or
  literals — `tests/test_api_contract.py`, `tests/test_393_control_token_separation.py`,
  `tests/test_analytics_profiles.py`, `tests/test_worker_operator_control.py`, `tests/test_camera_preview_gallery.py`, `tests/test_water_passage.py` —
  to resolve from `identity.py`/`config.py` with fallback-to-main, without
  weakening any assertion
- T003: Extend `deploy/vps/deploy.sh` in all four places (CONFIG_TARGET/
  IDENTITY_TARGET, release_complete, download required list, release
  install) plus activation staged+promoted before main.py with the store.py
  soft pattern and bootstrap capture of live copies; add config/identity
  fixtures to the synthetic releases in `tests/test_vps_deploy_transaction.py`
- T004: Add the SDD trio `specs/396-wave1-shared-kernel/{spec,plan,tasks}.md`
  (Risk REQUIRED; RISK/TEST rows; TX; DoD) — this directory
- T005: Run the verification battery — full unittest suite (baseline 907/4),
  `python3 scripts/ci/validate_repo.py`, `bash -n deploy/vps/deploy.sh`,
  ast.parse/import smoke for the new modules — and leave the exact-artifact
  scripts unchanged per the store.py precedent; commit on the wave branch
  (no push)

## Requirements traceability

- AC-001 | Task: T001 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T001 | Evidence: TEST-004 | Coverage: COVERED
- AC-003 | Task: T003 | Evidence: TEST-002 | Coverage: COVERED
- AC-004 | Task: T002 | Evidence: TEST-006 | Coverage: COVERED
- AC-005 | Task: T001 | Evidence: TEST-005 | Coverage: COVERED
- AC-006 | Task: T001 | Evidence: TEST-001 | Coverage: COVERED

## Completion gate

- [x] T001
- [x] T002
- [x] T003
- [x] T004
- [x] T005
- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [ ] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] Deployment state resolved — rides the VPS deploy of this wave (DEPLOY-TRIGGER, полоса A) — orchestrator-owned
- [ ] Runtime acceptance resolved — health gate probe on the VPS deploy — orchestrator-owned
- [ ] Deferred work recorded — none
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-005 mitigated in plan.md
- [ ] Waivers resolved or current — none

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [ ] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] Deployment state resolved — rides the VPS deploy of this wave (DEPLOY-TRIGGER, полоса A) — orchestrator-owned
- [ ] Runtime acceptance resolved — health gate probe on the VPS deploy — orchestrator-owned
- [ ] Deferred work recorded — none
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-005 mitigated in plan.md
- [ ] Waivers resolved or current — none
