# Tasks: #530 — server-side role authorization

- Specification: specs/530-roles/spec.md
- Plan: specs/530-roles/plan.md
- Status: IMPLEMENTED — T-1..T-7 complete with observed evidence; runtime
  acceptance gate and commit/PR lifecycle pending authorization

## Delivery tasks

- [x] T-1: Configuration and resolver.
  - Depends on: approved implementation scope.
  - Files: api/app/config.py, api/app/identity.py,
    tests/test_sea_speed_rbac.py.
  - Acceptance: empty-default immutable admin/operator lists; requested
    whitespace/comma syntax; exact username/group matching; env precedence,
    admin overlap and viewer fallback proven.
  - Verify: python3 -m pytest tests/test_sea_speed_rbac.py -q
  - Evidence: delivered; resolver tests green in full-suite run
    (1097 passed @ worktree 2026-10-18).

- [x] T-2: Identity-first guard and audit contract.
  - Depends on: T-1.
  - Files: api/app/identity.py, api/app/main.py,
    tests/test_sea_speed_rbac.py.
  - Acceptance: require_role delegates to unchanged identity primitive;
    insufficient role is 403; authorized attempts log safely encoded
    verified identity; unsupported minima never authorize; identity __all__
    and both main import seams updated together.
  - Verify: python3 -m pytest tests/test_sea_speed_rbac.py tests/test_auth_session_identity.py -q
  - Evidence: delivered; identity-first and audit tests green.

- [x] T-3: Object and preview enforcement.
  - Depends on: T-2.
  - Files: api/app/main.py, tests/test_sea_speed_rbac.py,
    tests/test_api_contract.py, tests/test_camera_preview_gallery.py.
  - Acceptance: seven routes wired — two PATCH, two DELETE, three preview;
    all three roles tested per route; denials have no side effects;
    Header/guard extraction bindings and snapshot signature pin repaired
    without weakening existing business checks.
  - Verify: python3 -m pytest tests/test_sea_speed_rbac.py tests/test_api_contract.py tests/test_camera_preview_gallery.py -q
  - Evidence: delivered; seven routes guarded and tested.

- [x] T-4: Calibration enforcement and alias forwarding.
  - Depends on: T-2.
  - Files: api/app/main.py, tests/test_sea_speed_rbac.py,
    tests/test_api_contract.py.
  - Acceptance: eight calibration POST routes require admin; cam1 aliases
    explicitly forward all identity/group headers to delegated handlers;
    no bypass switch; failed authorization produces no JSON writes.
    Existing GET normalization behavior remains unchanged.
  - Verify: python3 -m pytest tests/test_sea_speed_rbac.py tests/test_api_contract.py -q
  - Evidence: delivered; alias forwarding audited by tests.

- [x] T-5: Worker control and session.
  - Depends on: T-2.
  - Files: api/app/main.py, tests/test_sea_speed_rbac.py,
    tests/test_auth_session_identity.py, tests/test_api_contract.py,
    tests/test_worker_operator_control.py.
  - Acceptance: four worker POSTs require admin before outbound calls;
    requested_by is preserved. Two worker-status GETs remain identity-only.
    Session adds exactly role, with no new privilege minimum. Both session
    shape pins and the seven-handler identity/role wiring expectations are
    updated; all claims derive from verified identity.
  - Verify: python3 -m pytest tests/test_sea_speed_rbac.py tests/test_auth_session_identity.py tests/test_worker_operator_control.py tests/test_api_contract.py -q
  - Evidence: delivered; session exact shape {ok, username, role} pinned.

- [x] T-6: Complete security/compatibility matrix.
  - Depends on: T-3, T-4, T-5.
  - Files: tests/test_sea_speed_rbac.py; only already-admitted test harness
    files if a specific additional extraction seam is demonstrated.
  - Acceptance: 19 routes × three roles covered with real policy checks;
    every denial asserts no mutation; all nine ingestion routes preserve
    Bearer-only behavior; 33 GET routes retain existing role-neutral policy;
    /media unchanged; alias attribution and no-secret logging covered.
    Route-table baseline remains unchanged.
  - Verify: python3 -m pytest tests/test_sea_speed_rbac.py tests/test_route_table.py tests/test_api_contract.py -q
  - Evidence: delivered; 61-entry fingerprint unchanged in same run.

- [x] T-7: Full-suite and design-integrity gate — final source task.
  - Depends on: T-6.
  - Files: specs/530-roles/spec.md, plan.md, tasks.md for observed evidence;
    no speculative code changes.
  - Acceptance: full suite and validators pass on exact implementation
    head; changed-file scope inspected independently; no test completion
    claimed from worker prose; runtime/security disposition recorded.
  - Verify: python3 -m pytest tests/ -q
  - Additional verification: python3 scripts/ci/validate_sdd.py
  - Additional verification: python3 scripts/ci/validate_repo.py
  - Evidence: full suite 1097 passed, 4 skipped, 260 subtests passed
    (101.87s) and ruff clean observed by the orchestrator; validate_repo
    passed (755 tracked files); validate_sdd green after this artifact
    repair. Changed-file scope independently inspected (3 api files, 4
    test files, specs/530-roles/). Commit/PR and runtime acceptance remain
    open by design.

## Completion gate

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [x] Required CI green — auto-synced on merge to main (4e431fe3)
- [x] Exact-green-head merge complete — auto-synced on merge to main (4e431fe3)
- [ ] Deployment state resolved (runtime-manual, post-merge)
- [ ] Runtime acceptance resolved (AC-006 runtime probes)
- [ ] Deferred work recorded (transitional-mode removal; cosmetic UI
      role-awareness as separate follow-up)
- [ ] Risks resolved or explicitly accepted
- [ ] Waivers resolved or current

## Runtime acceptance gate

Not executed or authorized by this task list. The delivery orchestrator
must reconcile security-sensitive rollout classification, obtain applicable
handoff/authority gates, use the existing protected VPS workflow and record:
exact SHA, representative role/session probes, denied-mutation evidence,
ingestion continuity and previous-SHA rollback readiness.

Pytest cannot establish live authentik membership, header format or runtime
authority. Do not fabricate a pytest command as evidence of those facts.

## Requirements traceability

- AC-001 | Task: T-3, T-4, T-5, T-6 | Evidence: 19-route three-role matrix green (test_sea_speed_rbac.py) | Coverage: COVERED
- AC-002 | Task: T-1, T-2, T-5 | Evidence: resolver and identity-order tests green | Coverage: COVERED
- AC-003 | Task: T-3, T-4, T-5, T-6 | Evidence: denial side-effect assertions green | Coverage: COVERED
- AC-004 | Task: T-3, T-5, T-6 | Evidence: exact session shape, import seams, unchanged 61-entry fingerprint/read/M2M contracts green | Coverage: COVERED
- AC-005 | Task: T-2, T-6 | Evidence: captured verified-user audit events incl. aliases green | Coverage: COVERED
- AC-006 | Task: T-7, runtime acceptance gate | Evidence: full suite 1097 passed + ruff clean + validate_repo green observed 2026-10-18; validate_sdd green after artifact repair | Coverage: RUNTIME-MANUAL | Reason: role behavior through the live trusted edge (authentik group emission, representative memberships, session role) is observable only after merge and deployment; runtime acceptance gate records the remaining probes

## Definition of Done

- [ ] Issue/spec/plan/tasks current — current for the implemented scope;
      runtime acceptance evidence pending post-merge
- [ ] Exact changed-file scope verified — 3 api files, 4 test files,
      specs/530-roles/; inspected independently by the orchestrator
- [ ] Required tests and evidence complete — full suite 1097 passed,
      4 skipped, 260 subtests passed; ruff clean; observed 2026-10-18
- [x] Required CI green — pending PR creation on an authorized exact head — auto-synced on merge to main (4e431fe3)
- [x] Exact-green-head merge complete — pending authorized PR/merge — auto-synced on merge to main (4e431fe3)
- [ ] Deployment state resolved — runtime-manual; protected VPS workflow
      post-merge under standing delegation plus security handoff
- [ ] Runtime acceptance resolved — pending post-merge role/session probes
      through the live edge (AC-006)
- [ ] Deferred work recorded — transitional-mode removal and cosmetic UI
      role-awareness remain separate follow-ups
- [ ] Risks resolved or explicitly accepted — RISK-002/RISK-004 open,
      mitigated by fail-closed viewer default and protected rollback gates
- [ ] Waivers resolved or current — none requested
