# Tasks: #520 — edge vhost renderer codification (PR-2)

- Specification: specs/520-edge-vhost-renderer/spec.md

## Delivery tasks

- [ ] T-001: renderer — mode axis (authentik default / basic-auth), basic-auth
  location snippet with client identity blanking, shared edge-injection pair
  in both snippets, server-scoped marker stripping, materialize marker-span
  guard, edge include path validation, CLI --mode/--edge-auth-include (R-1,
  R-2, R-5, R-6, R-7)
- [ ] T-002: tests — tests/test_sea_speed_edge_vhost_renderer.py: both-mode
  goldens, edge-injection/strip pins, verify fail matrix, mode-mixing
  rejection, worker-private live-facts pin, secret-absence pins, materialize
  guard, CLI round-trip, idempotence (R-1..R-7)
- [ ] T-003: docs — docs/operations/SEA_SPEED_AUTH_V1.md #520 section (edge
  pair, injection, stripping, phase-2 ordering, полоса C routing) and
  deploy/vps/README.md provisioning note (include before candidate,
  fail-closed) (R-8)
- [ ] T-004: SDD trio specs/520-edge-vhost-renderer/ + PR body with exact
  eight-file Change Contract (impact VPS, Risk profile REQUIRED, no
  issue-closing reference) (R-8)
- [ ] T-005: validators and CI — validate_sdd (event mode), validate_repo,
  validate_change_contract, focused suites + full battery green on the exact
  head; exact-green-head merge (R-1..R-8)
- [ ] T-006 (runtime-manual): phase-2 sysadmin transaction (полоса C,
  ИБ-этап) — provision edge include, render+apply candidates from the merged
  head, run acceptance probes on #520; phase-3 API env + deploy follows in
  PR-1 scope (AC-007)

## Completion gate

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [x] Required CI green — auto-synced on merge to main (c1440190)
- [x] Exact-green-head merge complete — auto-synced on merge to main (c1440190)
- [ ] Deployment state resolved (deferred to phase-2/3 sysadmin lanes, полоса C — Reason: on-box edge include provisioning and rendered-candidate application are VPS mutations outside repo scope; TX audit in plan.md pins the transaction)
- [ ] Runtime acceptance resolved (AC-007, runtime-manual — Reason: VPS vhosts and the edge include are reachable only through the sysadmin session, полоса C)
- [ ] Deferred work recorded (forward-auth migration of the basic-auth contour is an owner decision; phase-3 API env + deploy is PR-1 scope; transitional-mode cleanup per PR-1)
- [ ] Risks resolved or explicitly accepted
- [ ] Waivers resolved or current

## Requirements traceability

- AC-001 | Task: T-001, T-002 | Evidence: TEST-001, TEST-003 | Coverage: COVERED
- AC-002 | Task: T-001, T-002 | Evidence: TEST-001, TEST-002, TEST-009 | Coverage: COVERED
- AC-003 | Task: T-001, T-002 | Evidence: TEST-002, TEST-004 | Coverage: COVERED
- AC-004 | Task: T-001, T-002 | Evidence: TEST-005 | Coverage: COVERED
- AC-005 | Task: T-001, T-002 | Evidence: TEST-006, TEST-007 | Coverage: COVERED
- AC-006 | Task: T-003, T-004, T-005 | Evidence: TEST-008, TEST-009, validate_sdd, validate_repo, Change Contract check | Coverage: COVERED
- AC-007 | Task: T-006 | Evidence: TEST-010 | Coverage: RUNTIME-MANUAL | Reason: VPS vhost application and edge-include provisioning are on-box mutations reachable only through the sysadmin session (полоса C, ИБ-этап)

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
