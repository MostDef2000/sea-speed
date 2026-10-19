# Tasks: #538 — unified admission phrase `commit approved`

- Specification: specs/538-unified-admission-phrase/spec.md
- Plan: specs/538-unified-admission-phrase/plan.md
- Status: IMPLEMENTED — T-1..T-4 complete in the working tree with observed
  evidence below; commit/PR lifecycle pending orchestrator by design

## Delivery tasks

- [x] T-1: Machinery — dual-accept in validators, schema and admission surfaces.
  - Depends on: approved implementation scope (#538 DUAL-ACCEPT decision).
  - Files: scripts/ci/validate_change_contract.py,
    scripts/ci/validate_delivery_checkpoint.py,
    schemas/delivery-checkpoint-v2.schema.json,
    .github/pull_request_template.md, scripts/ci/build_sync_pr_body.py.
  - Acceptance: SOURCE_AUTHORIZATIONS/AUTHORIZATION_RECEIPTS accept exactly
    `commit approved` and `OUTCOME APPROVED`; schema uses the two-value
    enum; error texts name the new phrase and legacy acceptance; template
    and generator present `commit approved`; machine-gate flag names
    byte-identical.
  - Verify: python3 -m py_compile scripts/ci/validate_change_contract.py scripts/ci/validate_delivery_checkpoint.py
  - Evidence: delivered; compile clean (see plan Validation record).

- [x] T-2: Tests — update phrase-coupled assertions, add dual-accept and rejection cases.
  - Depends on: T-1.
  - Files: tests/test_change_contract.py,
    tests/test_delivery_checkpoint_state_machine.py,
    tests/test_delivery_contract_convergence.py,
    tests/test_delivery_resume_contract.py,
    tests/test_delivery_quality_layer.py.
  - Acceptance: new cases (a) unified-phrase validate_authorization pass,
    (b) legacy dual-accept pass for both validators, (c) v1-upgrade with
    legacy receipt validates, (d) garbage phrases rejected; convergence
    pins updated to the new exact literals (template line, validator
    SOURCE line, schema enum).
  - Verify: python3 -m unittest tests.test_change_contract tests.test_delivery_checkpoint_state_machine tests.test_delivery_contract_convergence tests.test_delivery_resume_contract tests.test_delivery_quality_layer -v
  - Evidence: delivered; all green in the recorded battery.

- [x] T-3: Live contracts and docs sync.
  - Depends on: T-1.
  - Files: AGENTS.md, README.md, specs/README.md,
    contracts/SEA_SPEED_GOVERNANCE.md,
    contracts/SEA_SPEED_DELIVERY_POLICY.md,
    contracts/runtime/SEA_SPEED_TASK_RUNTIME.md,
    contracts/runtime/RELEASE_READINESS_GATE.md,
    contracts/branches/task-intake.md, contracts/branches/governance.md,
    contracts/branches/project-manager.md,
    .specify/memory/constitution.md, docs/agents/PM_BOOTSTRAP.md,
    docs/architecture/sea-speed-control-plane.md,
    .opencode/agents/sea-speed-delivery-orchestrator.md.
  - Acceptance: admission phrase is `commit approved` in live rules;
    legacy `OUTCOME APPROVED` acceptance noted wherever machine validation
    is described; global-contract pointer line added to AGENTS.md in the
    SLF family style; specs/** narrative and DR-004/005/006 untouched;
    flag names untouched.
  - Verify: grep -rn "OUTCOME APPROVED" over live paths with per-hit categorization
  - Evidence: delivered; sweep recorded in the delivery report, every hit
    categorized.

- [x] T-4: SDD triplet and verification battery.
  - Depends on: T-1, T-2, T-3.
  - Files: specs/538-unified-admission-phrase/spec.md, plan.md, tasks.md.
  - Acceptance: triplet passes validate_sdd.py structure checks and the
    delivery-quality layer (NFR, risk profile REQUIRED with scored rows,
    test design, correct-course with Authorization impact, traceability,
    DoD); full verification battery green and recorded.
  - Verify: python3 scripts/ci/validate_sdd.py
  - Additional verification: python3 -m unittest discover -s tests -v
  - Additional verification: python3 scripts/ci/validate_contracts.py
  - Additional verification: python3 -c quality-layer check of this triplet with the draft PR body
  - Evidence: delivered; battery outputs recorded in plan.md Validation
    and in the delivery report; mypy-strict/ruff re-run by CI on the PR.

## Completion gate

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [x] Required CI green — auto-synced on merge to main (fcf596d3)
- [x] Exact-green-head merge complete — auto-synced on merge to main (fcf596d3)
- [ ] Deployment state resolved (runtime-manual: not applicable — control-plane only, no deploy contour)
- [ ] Runtime acceptance resolved (not applicable: no runtime surface changed; required CI is the acceptance evidence)
- [ ] Deferred work recorded (none — no follow-up scope)
- [ ] Risks resolved or explicitly accepted
- [ ] Waivers resolved or current

## Requirements traceability

- AC-001 | Task: T-1, T-2 | Evidence: tests/test_change_contract.py unified-phrase cases green in recorded battery | Coverage: COVERED
- AC-002 | Task: T-1, T-2 | Evidence: dual-accept cases (change contract + checkpoint + v1 upgrade) green in recorded battery | Coverage: COVERED
- AC-003 | Task: T-2, T-4 | Evidence: garbage-rejection cases and convergence literal pins green; validate_sdd.py green | Coverage: COVERED
- AC-004 | Task: T-1, T-2 | Evidence: tests/test_sync_tasks_md_flow.py real-validator run green; flag-name grep clean | Coverage: COVERED
- AC-005 | Task: T-3, T-4 | Evidence: categorized grep sweep in delivery report; git diff --stat shows no historical narrative or decision-record paths | Coverage: COVERED
- AC-006 | Task: T-4 | Evidence: full unittest summary, py_compile, validate_contracts.py and validate_sdd.py outputs recorded in the delivery report | Coverage: COVERED

## Definition of Done

- [ ] Issue/spec/plan/tasks current — current for the implemented scope at the working tree
- [ ] Exact changed-file scope verified — full list in the PR Change Contract; git diff --stat inspected
- [ ] Required tests and evidence complete — battery recorded in plan Validation and the delivery report
- [x] Required CI green — pending PR creation on an authorized exact head — auto-synced on merge to main (fcf596d3)
- [x] Exact-green-head merge complete — pending authorized PR/merge — auto-synced on merge to main (fcf596d3)
- [ ] Deployment state resolved — no deploy contour; nothing to resolve
- [ ] Runtime acceptance resolved — no runtime surface; required CI is the acceptance evidence
- [ ] Deferred work recorded — none
- [ ] Risks resolved or explicitly accepted — RISK-001..003 mitigated, see plan Risk profile
- [ ] Waivers resolved or current — none requested
