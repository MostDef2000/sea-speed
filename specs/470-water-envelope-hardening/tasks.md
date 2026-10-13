# 470 — Tasks

Specification: specs/470-water-envelope-hardening/spec.md

## Delivery tasks

- [x] T001 RED-first tests: tests/test_live_envelope_validators.py — 2 tests (road control + water), water observed failing against base (TypeError → 500)
- [x] T002 Fix: guard json.dumps in _validate_water_live_envelope, 400 "invalid json", block textually identical to road (live_feeds.py 168-174)
- [x] T003 Battery: full suite 910 OK skipped=4 (+2 exact delta), validate_repo 674, validate_sdd, ruff, route table 61==61, focused neighbor run 28 OK
- [x] T004 Independent adversarial peer review: APPROVE (unanimous)
- [x] T005 SDD trio + PR change contract validated locally with the CI-side linkage rules
- [ ] T007 Required CI is green for the exact merge-head SHA
- [ ] T008 Exact-green-head squash merge to main

## Completion gate

- [ ] Required CI green: T007
- [ ] Exact-green-head merge complete: T008
- [ ] Required local and GitHub CI evidence is green: battery 910/4 + validate_repo + validate_sdd + ruff observed at head; CI tick at merge-head
- [ ] Post-restart evidence is recorded: runtime acceptance probes recorded on #470 after the deploy gate
- [ ] Runtime acceptance resolved: post-restart control-plane verification pending deploy gate

## Requirements traceability

- AC-001 | Task: T002 | Evidence: guard blocks road 97-103 / water 168-174 textually identical (peer review verified) | Coverage: COVERED
- AC-002 | Task: T001+T002 | Evidence: tests/test_live_envelope_validators.py 2/2 OK (400 + "invalid json" both validators) | Coverage: COVERED
- AC-003 | Task: T001 | Evidence: RED-first observed: water ERROR (TypeError) pre-fix; road ok pre-fix; 2/2 OK post-fix | Coverage: COVERED
- AC-004 | Task: T002 | Evidence: code-path trace: guard precedes deepcopy/lock/seq/append (peer review verified main.py:1109-1119) | Coverage: COVERED
- AC-005 | Task: T003 | Evidence: battery Ran 910 OK (skipped=4); delta exactly +2; fingerprint untouched | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (live_feeds.py + 1 test file + this trio)
- [x] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [ ] Deployment state resolved (deploy via DEPLOY-TRIGGER owner gate)
- [ ] Runtime acceptance resolved: post-restart control-plane verification pending
- [ ] Deferred work recorded (SSE generator dumps guard — residual D-4, tracked on #470)
- [x] Risks resolved or explicitly accepted
- [x] Waivers resolved or current
