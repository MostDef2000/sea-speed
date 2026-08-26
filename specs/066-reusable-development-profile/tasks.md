# Tasks: Reusable health-aware development profile

- Specification: specs/066-reusable-development-profile/spec.md
- Plan: specs/066-reusable-development-profile/plan.md
- Issue: #331

## Delivery tasks

- [x] T001 Record Issue #331 Outcome, authorization receipt and Checkpoint v2.
- [x] T002 Create SDD 066 with NFR, risk/test design, correct-course and traceability.
- [x] T003 Add the project profile marker and Sea Speed delivery gate manifest.
- [x] T004 Add bounded `profile-worker-*` delegation rules without replacing the canonical Orchestrator.
- [x] T005 Extend repository validation with the exact three-path `.opencode/**` allowlist.
- [x] T006 Update deterministic tests for the exact allowlist and worker delegation contract.
- [x] T007 Run project doctor, complete local gates and resolve findings.
- [x] T008 Verify exact changed-file scope and synchronize SDD evidence.
- [ ] T009 Open one bounded Change Contract PR and obtain exact-head required CI.
- [ ] T010 Merge exact green head, verify exact-main Quality and restart OpenCode for control-plane acceptance.

## Requirements traceability

- AC-001 | Task: T003,T007 | Evidence: TEST-066-001 / project doctor | Coverage: COVERED
- AC-002 | Task: T004,T010 | Evidence: TEST-066-002 / restarted OpenCode agent discovery | Coverage: RUNTIME-MANUAL | Reason: effective plugin configuration loads only at process startup
- AC-003 | Task: T003,T007 | Evidence: TEST-066-003 / delivery runner list and full output | Coverage: COVERED
- AC-004 | Task: T005,T006 | Evidence: TEST-066-004 / exact allowlist tests | Coverage: COVERED
- AC-005 | Task: T006,T007 | Evidence: TEST-066-005 / complete local validators and suites | Coverage: COVERED
- AC-006 | Task: T008 | Evidence: TEST-066-006 / exact changed-file comparison | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current.
- [x] Exact changed-file scope verified: ten approved paths only.
- [x] Required local tests and evidence complete.
- [ ] Required CI green.
- [ ] Exact-green-head merge complete.
- [x] Deployment state resolved: NOT REQUIRED.
- [ ] Runtime acceptance resolved: post-restart control-plane verification pending.
- [x] Deferred work recorded: NONE.
- [x] Risks resolved or explicitly accepted.
- [x] Waivers resolved or current: NOT REQUIRED.

## Completion gate

- [x] Requirements are covered by tasks and traceability.
- [x] Spec, plan and tasks match the intended implementation.
- [ ] Required local and GitHub CI evidence is green: local PASS; GitHub pending.
- [ ] Exact-main source and Quality evidence is recorded in Issue #331.
- [ ] Post-restart default-agent and worker discovery evidence is recorded: branch-process PASS; exact-main pending.
