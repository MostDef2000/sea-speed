# Tasks: Ubuntu Zero-Touch Production Transport

- Feature: 030-ubuntu-zero-touch-transport
- Issue: #234
- Specification: `specs/030-ubuntu-zero-touch-transport/spec.md`

## Delivery tasks

### Source phase

- [x] T001 Recover current public/main/Quality/runtime evidence and confirm `main` is currently unprotected.
- [x] T002 Define protected-public-main source hard gate and tests.
- [x] T003 Define GitHub-hosted runner -> VPS ProxyJump -> ZeroTier Worker workflow with strict host-key policy.
- [x] T004 Define dedicated `sea-speed-deploy` forced-command root gate with exact request validation and deterministic artifact verification.
- [x] T005 Define one-time bootstrap/removal script with password authentication disabled without locking the active public-key account, canonical SSH allowlist membership, `restrict`, forced command and gate-only sudoers rule.
- [x] T006 Update canonical delivery/release/deployment/control-plane contracts and operator documentation.
- [x] T007 Add SDD risk profile, test design, correct-course analysis and full eight-stage Deployment Transaction Audit.
- [x] T008 PR Validation and aggregate Quality pass on one exact head.
- [x] T009 Merge with expected head and exact-main Quality pass.

### Independent activation phase

- [x] T010 Human/admin enables public `main` protection: PR required, required `Repository validation` + `quality-integration`, force-push/delete disabled, no silent bypass/per-release reviewer.
- [x] T011 Human/admin confirms `production` standing delegation remains present and unchanged.
- [x] T012 Human/admin creates dedicated Ed25519 Worker deployment key outside chat/Git and stores private key as `UBUNTU_DEPLOY_SSH_PRIVATE_KEY` environment secret.
- [x] T013 Human/admin independently verifies Worker host key and stores known-host line as `UBUNTU_DEPLOY_SSH_KNOWN_HOSTS` environment secret.
- [ ] T014 Re-run one-time Worker bootstrap with corrected non-locking password-disabled account state and transactional canonical `AllowUsers` admission; capture sanitized fingerprint, effective sshd allowlist and boundary PASS evidence.
- [ ] T015 Positive/negative transport probes confirm dedicated-key authentication succeeds while existing operator access remains admitted and arbitrary command, PTY and forwarding cannot produce general execution.
- [ ] T016 Protected workflow reruns exact Issue #231 Ubuntu release through CONNECTOR with operator actions `0`.
- [ ] T017 Runtime evidence confirms deployment manifest `runtime_verified`, typed execution audit and both Authentik login stages `days=30`.
- [ ] T018 Reconcile Issue #231/#234/#229 completion from durable runtime evidence.

## Production-learning remediation

The first installed bootstrap returned `ZERO_TOUCH_TRANSPORT_BOOTSTRAP=PASS`, but the first GitHub CONNECTOR retry failed before forced-command execution with `Permission denied (publickey)`. Root cause #1 was `passwd -l sea-speed-deploy`; on Linux OpenSSH rejects a leading-`!` locked account before public-key authentication. PR #236 corrected the active account to the non-locking invalid password marker `*NP*` while preserving password-login denial.

After that corrected bootstrap was installed, runtime diagnostics proved the account state, authorized-key fingerprint, ownership/modes and `PubkeyAuthentication yes` were correct, but a second CONNECTOR retry failed identically. Effective sshd policy showed `AllowUsers seaspeedadmin`, the canonical hardening file contained `AllowUsers seaspeedadmin`, and the sshd journal explicitly reported `User sea-speed-deploy ... not allowed because not listed in AllowUsers`. Root cause #2 is therefore the existing Worker SSH allowlist, not the key pair.

This bounded remediation stays inside Issue #234 authorized paths: bootstrap preserves every existing principal in `/etc/ssh/sshd_config.d/00-sea-speed-hardening.conf`, adds only `sea-speed-deploy`, runs `sshd -t`, reloads and verifies effective policy, restores the original file on failure, and removes only the dedicated principal on `--remove`. Existing `seaspeedadmin` access, password denial, `restrict` + forced-command and gate-only sudo remain unchanged.

## Completion gate

Source completion requires exact-scope remediation PR evidence plus PR Validation, aggregate Quality, expected-head merge and exact-main Quality. Overall Outcome completion additionally requires T014-T018. Until corrected allowlist-aware transport bootstrap is installed, positive/negative probes pass and the #231 runtime retry is verified, terminal state remains BLOCKED or HUMAN DECISION REQUIRED rather than DONE.

## Requirements traceability

- AC-001 | Task: T001,T010 | Evidence: Connector repository visibility plus independently verified protected-main settings | Coverage: RUNTIME-MANUAL | Reason: branch/ruleset activation is an independently administered GitHub settings action outside repository writes
- AC-002 | Task: T002 | Evidence: `tests/test_production_source_protection.py` private/unprotected/missing-context denial cases | Coverage: COVERED
- AC-003 | Task: T002,T003,T006 | Evidence: workflow-policy and architecture tests proving source protection precedes policy/transport | Coverage: COVERED
- AC-004 | Task: T003 | Evidence: Ubuntu workflow source and zero-touch transport tests | Coverage: COVERED
- AC-005 | Task: T004,T015 | Evidence: forced-command gate tests plus installed-boundary negative probe | Coverage: RUNTIME-MANUAL | Reason: source tests cover parser denial; installed sshd forced-command behavior requires runtime probe
- AC-006 | Task: T004 | Evidence: gate source/tests prove first-parent validation and deterministic artifact recomputation before target transaction | Coverage: COVERED
- AC-007 | Task: T005,T014 | Evidence: bootstrap source/tests prove `restrict`, forced command, password-disabled but non-locked active account, transactional canonical `AllowUsers` admission/removal, root-owned gate and exact sudo rule | Coverage: COVERED
- AC-008 | Task: T008 | Evidence: PR Change Contract and exact changed-file comparison against Issue #234 Scope | Coverage: COVERED
- AC-009 | Task: T008,T009 | Evidence: PR Validation, aggregate Quality, expected-head merge and exact-main Quality | Coverage: COVERED
- AC-010 | Task: T010 | Evidence: Connector/settings evidence for PR/check enforcement, force-push/delete denial and bypass disposition | Coverage: RUNTIME-MANUAL | Reason: repository protection settings are independently administered outside agent repository writes
- AC-011 | Task: T011,T012,T013 | Evidence: production environment standing-delegation presence and secret-name/host-trust presence without exposing values | Coverage: RUNTIME-MANUAL | Reason: credentials and environment settings are operator-controlled protected state
- AC-012 | Task: T014,T015 | Evidence: installed account/authorized-key/sudo boundary, effective sshd `AllowUsers` preserving operator principal(s), successful dedicated-key authentication and rejected shell/PTY/forward/non-protocol probes | Coverage: RUNTIME-MANUAL | Reason: sshd admission and capability restriction must be verified on the commissioned Worker
- AC-013 | Task: T016,T017 | Evidence: protected #231 Ubuntu deployment manifest and typed execution audit with operator actions 0 | Coverage: RUNTIME-MANUAL | Reason: physical production execution cannot be proven by hosted CI alone
- AC-014 | Task: T017,T018 | Evidence: runtime ORM/UI evidence for both login stages `days=30` and reconciled Issue completion | Coverage: RUNTIME-MANUAL | Reason: Authentik runtime state and browser behavior require commissioned production evidence

## Definition of Done

- [x] Issue/spec/plan/tasks current for canonical Issue #234 and `specs/030-ubuntu-zero-touch-transport/spec.md`.
- [x] Exact changed-file scope verified against the approved Issue #234 Scope for the integrated source phase; bounded remediations remain inside the same authorized paths.
- [ ] Required tests and evidence complete, including corrected AllowUsers-aware runtime evidence after independent activation.
- [x] Required CI green on exact PR heads and exact-main pushes for the original zero-touch source integration and first account-lock remediation; current AllowUsers remediation PR CI remains pending.
- [x] Exact-green-head merge complete for original source integration and first account-lock remediation; current AllowUsers remediation merge remains pending.
- [ ] Deployment state resolved: corrected zero-touch transport installed or explicitly rolled back/removed.
- [ ] Runtime acceptance resolved: #231 retry is `runtime_verified` with typed execution audit.
- [x] Deferred work recorded: T014-T018 remain explicit post-merge activation/runtime acceptance work and are not silently treated as complete.
- [ ] Risks resolved or explicitly accepted; no unresolved FAIL finding.
- [x] Waivers resolved or current: no waiver is used for source authorization, CI, standing production policy, source protection or runtime acceptance.
- [x] Security risk profile is REQUIRED and full Deployment Transaction Audit contains all eight canonical stages.
- [x] Workflow policy requires source protection before policy/transport and removes recurring Ubuntu one-command fallback from steady state.
- [x] `main` protection and required checks are independently enabled and verified.
- [x] Standing delegation remains unchanged/valid by independently supplied environment evidence.
- [ ] Dedicated Worker transport is installed with public-key-accessible/password-disabled account, preserved operator allowlist + dedicated deploy allowlist membership, restricted key and gate-only sudo.
- [ ] Negative SSH capability probes pass.
- [ ] Authentik runtime confirms both login stages at `days=30`; explicit logout semantics remain.
- [ ] Operator actions expected for subsequent ordinary Ubuntu releases: `0`.
- [ ] Terminal completion is not claimed before durable runtime acceptance.
