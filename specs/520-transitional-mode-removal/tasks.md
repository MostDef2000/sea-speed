# Tasks — #520 residual: transitional edge-auth mode removal (fail-closed 503)

- Issue: #520
- Specification: specs/520-transitional-mode-removal/spec.md
- Plan: specs/520-transitional-mode-removal/plan.md
- Date: 2026-10-24

## Delivery tasks

- T-520-601 [DONE]: remove the transitional branch from `require_operator_identity`
  (module latch `_EDGE_AUTH_TRANSITIONAL_WARNING_EMITTED`, the `global` statement and
  both WARNING branches deleted); unconfigured/blank secret now fails closed with
  503 "Trusted Authentik identity is unavailable" before any username handling.
- T-520-602 [DONE]: replace the transitional acceptance pins with fail-closed pins
  (assertRaises 503 + assertNoLogs) at both the primitive level
  (tests/test_auth_session_identity.py OperatorEdgeAuthTests) and the require_role
  level (tests/test_sea_speed_rbac.py IdentityFirstOrderingTests).
- T-520-603 [DONE]: migrate the incidental unconfigured-secret tests to the strict
  fixture (edge header supplied) so trim/role-join/blank-username pins keep holding
  under the strict posture; strict-mode pins stay untouched and green.
- T-520-604 [DONE]: verify RED authenticity on base main @ 0139f3e8 (detached
  worktree, test-only copy: the new fail-closed pins fail on base; the base
  transitional branch raises NameError once the latch is dropped from the harness
  extraction — behavioral failure observed) and GREEN on the fix head (focused run
  40 passed + 130 subtests; ruff clean under scripts/quality/ruff.toml).
- T-520-605 [DONE]: SDD trio (this directory) synchronized with the exact
  changed-file scope; grandfather-set entry added to scripts/ci/validate_sdd.py for
  the 520 staged-PR set.

## Completion gate

- [ ] CI gate: full battery green on the exact PR head — orchestrator-owned
- [ ] review gate: independent review of the trust-primitive diff (security-adjacent) — orchestrator-owned
- [ ] merge gate: exact-green-head merge complete — orchestrator-owned
- [ ] deploy gate: VPS deploy of the merged exact SHA — SEPARATE OWNER GATE (security-sensitive contour; ИБ-этап + deploy-authorized pipeline; NOT covered by the standing worker-deploy delegation)
- [ ] runtime gate: post-deploy acceptance probes on operator routes (200 with edge header / 403 without) — owner-gated with the deploy

## Requirements traceability

- AC-001 | Task: T-520-601,T-520-602 | Evidence: tests/test_auth_session_identity.py OperatorEdgeAuthTests.test_unconfigured_edge_secret_fails_closed + test_blank_edge_secret_fails_closed; tests/test_sea_speed_rbac.py IdentityFirstOrderingTests.test_unconfigured_edge_secret_fails_closed — all RED on base 0139f3e8, GREEN on the fix head | Coverage: COVERED
- AC-002 | Task: T-520-603 | Evidence: existing strict-mode suites pass unmodified (focused run 40 passed + 130 subtests on the fix head); incidental tests migrated to the strict fixture keep their pins | Coverage: COVERED
- AC-003 | Task: T-520-605 | Evidence: orchestrator diff inspection of the PR (exact changed-file scope: api/app/identity.py, tests/test_auth_session_identity.py, tests/test_sea_speed_rbac.py, specs/520-transitional-mode-removal/**, scripts/ci/validate_sdd.py grandfather line); protected suites stay green | Coverage: RUNTIME-MANUAL | Reason: zero-diff property is verified by review, not by an executable test

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (api/app/identity.py, tests/test_auth_session_identity.py, tests/test_sea_speed_rbac.py, specs/520-transitional-mode-removal/**, scripts/ci/validate_sdd.py)
- [x] Required tests and evidence complete (RED authenticity on base 0139f3e8 + GREEN focused run + full battery 1138 OK skipped=4 + ruff canon)
- [ ] CI gate: Required CI green on the exact PR head — orchestrator-owned
- [ ] review gate: independent review verdict recorded — orchestrator-owned
- [ ] merge gate: Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved (VPS deploy — SEPARATE OWNER GATE, security-sensitive contour)
- [ ] runtime gate: Runtime acceptance resolved — owner-gated with the deploy
- [ ] Deferred work recorded — none
- [ ] Risks resolved or explicitly accepted — Risk profile NOT REQUIRED (plan.md)
- [ ] Waivers resolved or current — none
