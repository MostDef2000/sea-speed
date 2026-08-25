# Tasks: Deterministic GitHub Actions Connector control

- Specification: specs/057-github-actions-connector/spec.md
- Plan: specs/057-github-actions-connector/plan.md
- Issue: #310

## Delivery tasks

- [x] T001 Record Issue #310 Outcome Contract, authorization receipt and Checkpoint v2.
- [x] T002 Create SDD 057 with NFR, risk/test design, correct-course and traceability.
- [x] T003 Replace the deprecated MCP package with secret-free official remote configuration.
- [x] T004 Synchronize exact Actions capability, bounded trigger and destructive-method denial across canonical entrypoints.
- [x] T005 Admit tracked root `opencode.json` without relaxing `.opencode/**` exact-path protection.
- [x] T006 Add deterministic config and contract coverage.
- [ ] T007 Run complete local validation and resolve findings.
- [ ] T008 Open exact Change Contract PR and obtain required exact-head CI.
- [ ] T009 Merge exact green head and verify exact-main Quality.
- [ ] T010 Restart OpenCode, discover four Actions tools and execute bounded #305 read/rerun.

## Requirements traceability

- AC-001 | Task: T003,T006 | Evidence: TEST-057-001 / opencode.json + tests/test_github_actions_connector_contract.py | Coverage: COVERED
- AC-002 | Task: T004,T006 | Evidence: TEST-057-002 / canonical entrypoints | Coverage: COVERED
- AC-003 | Task: T004,T006 | Evidence: TEST-057-002 / destructive-method assertions | Coverage: COVERED
- AC-004 | Task: T005,T007 | Evidence: TEST-057-003 / local validation | Coverage: COVERED
- AC-005 | Task: T008,T009 | Evidence: TEST-057-004 / PR and main checks | Coverage: RUNTIME-MANUAL | Reason: exact-head CI and merge evidence are produced by GitHub after PR admission
- AC-006 | Task: T010 | Evidence: TEST-057-005 / live official Connector probe after OpenCode restart | Coverage: RUNTIME-MANUAL | Reason: live tool discovery requires a restarted OpenCode process

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [x] Deployment state resolved: NOT REQUIRED for this control-plane source change
- [ ] Runtime acceptance resolved: post-restart capability probe pending
- [x] Deferred work recorded: resume Issue #305 after the live capability probe
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current: NOT REQUIRED

## Completion gate

- [x] Requirements are covered by tasks and traceability.
- [x] Spec, plan and tasks match the intended implementation.
- [ ] Required local and GitHub CI evidence is green.
- [ ] Exact-main source and Quality evidence is recorded in Issue #310.
- [ ] Live Actions capability and bounded #305 continuation evidence is recorded.
