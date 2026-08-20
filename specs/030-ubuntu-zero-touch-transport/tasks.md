# Tasks: Ubuntu Zero-Touch Production Transport

- Feature: 030-ubuntu-zero-touch-transport
- Issue: #234

## Source tasks

- [x] T001 Recover current public/main/Quality/runtime evidence and confirm `main` is currently unprotected.
- [x] T002 Define protected-public-main source hard gate and tests.
- [x] T003 Define GitHub-hosted runner -> VPS ProxyJump -> ZeroTier Worker workflow with strict host-key policy.
- [x] T004 Define dedicated `sea-speed-deploy` forced-command root gate with exact request validation and deterministic artifact verification.
- [x] T005 Define one-time bootstrap/removal script with locked account, `restrict`, forced command and gate-only sudoers rule.
- [x] T006 Update canonical delivery/release/deployment/control-plane contracts and operator documentation.
- [x] T007 Add SDD risk profile, test design, correct-course analysis and full eight-stage Deployment Transaction Audit.
- [ ] T008 PR Validation and aggregate Quality pass on one exact head.
- [ ] T009 Merge with expected head and exact-main Quality pass.

## Independent activation tasks

- [ ] T010 Human/admin enables public `main` protection: PR required, required `Repository validation` + `quality-integration`, force-push/delete disabled, no silent bypass/per-release reviewer.
- [ ] T011 Human/admin confirms `production` standing delegation remains present and unchanged.
- [ ] T012 Human/admin creates dedicated Ed25519 Worker deployment key outside chat/Git and stores private key as `UBUNTU_DEPLOY_SSH_PRIVATE_KEY` environment secret.
- [ ] T013 Human/admin independently verifies Worker host key and stores known-host line as `UBUNTU_DEPLOY_SSH_KNOWN_HOSTS` environment secret.
- [ ] T014 One-time Worker bootstrap installs restricted deploy account/gate and returns sanitized fingerprints/boundary PASS evidence.
- [ ] T015 Negative transport probes confirm arbitrary command, PTY and forwarding cannot produce general execution.
- [ ] T016 Protected workflow reruns exact Issue #231 Ubuntu release through CONNECTOR with operator actions `0`.
- [ ] T017 Runtime evidence confirms deployment manifest `runtime_verified`, typed execution audit and both Authentik login stages `days=30`.
- [ ] T018 Reconcile Issue #231/#234/#229 completion from durable runtime evidence.

## Requirements traceability

| Requirement | Tasks | Evidence |
|---|---|---|
| FR-001..FR-003 protected source | T002, T008-T011 | verifier tests, workflows, GitHub settings/Connector |
| FR-004..FR-006 runner/ProxyJump | T003, T012-T016 | workflow tests + production run |
| FR-007..FR-010 dedicated forced command | T004-T005, T012-T015 | gate/bootstrap tests + installed-boundary probe |
| FR-011..FR-014 exact source/artifact/manifest | T004, T016-T017 | gate tests + deployment evidence |
| FR-015..FR-016 strict SSH/no fallback | T003, T012-T016 | workflow policy + negative probe |
| FR-017..FR-018 bootstrap/rollback | T005, T014-T015 | bootstrap output + remove path |
| FR-019..FR-020 authority unchanged | T006, T008-T018 | policy/contract tests + policy decision evidence |

## Definition of Done

- [ ] Exact changed-file scope equals the approved Issue #234 Scope.
- [ ] Security risk profile is REQUIRED and has no unresolved FAIL finding.
- [ ] Full Deployment Transaction Audit contains all eight canonical stages.
- [ ] New scripts pass Python/shell syntax and repository behavioral tests.
- [ ] Workflow policy proves source protection before policy/transport and no recurring Ubuntu manual fallback.
- [ ] PR Validation + aggregate Quality pass on the exact merged head.
- [ ] Exact-main Quality passes after merge.
- [ ] `main` protection and required checks are independently enabled and verified.
- [ ] Standing delegation remains unchanged/valid.
- [ ] Dedicated Worker transport is installed with restricted key and gate-only sudo.
- [ ] Negative SSH capability probes pass.
- [ ] Exact #231 release completes through zero-touch CONNECTOR with `runtime_verified` and typed audit.
- [ ] Authentik UI/runtime confirms both login stages at `days=30` and explicit logout semantics remain.
- [ ] Operator actions expected for subsequent ordinary Ubuntu releases: `0`.
- [ ] Terminal completion is not claimed before durable runtime acceptance.
