# Tasks: Auth outage fallback

- Specification: specs/033-auth-outage-fallback/spec.md
- Plan: specs/033-auth-outage-fallback/plan.md
- Issue: #250

## Delivery tasks

- [x] T001 Serve fail-closed Sea Speed Auth outage page asset on VPS local filesystem
- [ ] T002 Render fallback `error_page 500 =503 /sea-speed-unavailable.html` inside every protected `/sea-speed/**` location and provide `internal` outage location with `Cache-Control: no-store` + `Retry-After: 30`
- [ ] T003 Keep public `/` and `auth.mostdef.ru` unaffected and keep ordinary application 500 distinguishable
- [ ] T004 Extend deterministic tests for renderer, fallback, bypass, and degraded-state deployment transaction
- [ ] T005 Extend VPS deployment transaction to accept already-degraded `500 + private Authentik unreachable` baseline with exact-source/digest/nginx -t/rollback
- [ ] T006 Validate SDD, contracts, repo, SDD linkage, and full test suite
- [ ] T007 Open exact Change Contract PR and obtain exact-head CI (PR Validation + Quality integration)
- [ ] T008 Merge exact green head, verify exact-main Quality, and execute protected VPS deployment with typed evidence
- [ ] T009 Record production acceptance (`/sea-speed/ -> 503` while Worker unavailable, `/ -> 200`, no anonymous bypass, automatic return after recovery) in canonical Issue #250

## Requirements traceability

- FR-001 | Task: T002, T004 | Evidence: renderer test retains `auth_request` on every protected location | Coverage: COVERED
- FR-002 | Task: T002, T004, T005 | Evidence: unavailable Authentik yields 503 with outage page, Cache-Control no-store, Retry-After 30 | Coverage: COVERED
- FR-003 | Task: T001, T005 | Evidence: `frontend/sea-speed/unavailable.html` shipped and staged to VPS-local `/var/www/mostdef.ru/sea-speed-unavailable.html` | Coverage: COVERED
- FR-004 | Task: T002, T004 | Evidence: outage location is `internal` and not directly bypassable | Coverage: COVERED
- FR-005 | Task: T003, T004 | Evidence: healthy-auth real app 500 stays 500 and does not return outage page | Coverage: COVERED
- FR-006 | Task: T003, T004 | Evidence: public `/ -> 200` under outage | Coverage: COVERED
- FR-007 | Task: T002, T005, T009 | Evidence: recovery restores normal `302/401/403` without reload | Coverage: RUNTIME-MANUAL
- FR-008 | Task: T005, T004 | Evidence: degraded 500 baseline is admissible for bounded VPS deploy with exact-source/rollback | Coverage: COVERED
- AC-001 | Task: T002, T004 | Evidence: auth retention + fallback tests | Coverage: COVERED
- AC-002 | Task: T002, T004 | Evidence: 503 fallback test | Coverage: COVERED
- AC-003 | Task: T002, T004 | Evidence: internal guard + public smoke test | Coverage: COVERED
- AC-004 | Task: T002, T003, T004 | Evidence: no anonymous content + app-500 distinguish test | Coverage: COVERED
- AC-005 | Task: T001, T005, T004 | Evidence: staging carries outage asset + nginx health | Coverage: COVERED
- AC-006 | Task: T005, T004 | Evidence: degraded baseline transition test | Coverage: COVERED
- AC-007 | Task: T006, T007, T008, T009 | Evidence: SDD/CI/merge/deploy/acceptance | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current with NFR, risk, test design, correct-course, transaction audit, traceability
- [ ] Renderer carries fail-closed 503 fallback for every protected `/sea-speed/**` location without weakening `auth_request`
- [ ] VPS-local outage asset shipped, staged, and installed with bounded deployment transaction evidence
- [ ] Degraded `500 + private Authentik unreachable` baseline can safely transition to `503` fallback without Worker recovery
- [ ] Protected content never exposed anonymous; public `/` unaffected; real app 500 distinguishable
- [ ] Privileged helper stays exact-source/fixed-action/no-shell and restores nginx on failed transaction
- [ ] Deterministic tests prove all acceptance gates; SDD/repo/contract validators pass
- [ ] Exact-head PR Validation + Quality integration green; exact-green-head merge; exact-main Quality green
- [ ] Protected VPS deployment manifest and execution evidence present; production acceptance recorded

## Completion gate

- [x] Requirements are covered by tasks and traceability.
- [x] Spec, plan and tasks match implemented behavior.
- [ ] Required deterministic tests are green.
- [ ] Required CI is green on exact head.
- [ ] Exact-green-head merge evidence is recorded in #250.
- [ ] VPS deployment and runtime acceptance evidence is recorded.
