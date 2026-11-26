# Tasks: #739 — Deploy preserves the protected recorder configuration

- Specification: specs/739-config-preserve/spec.md
- Plan: specs/739-config-preserve/plan.md
- Issue: #739

## Delivery tasks

- [x] T001 Add the recorder contract and `preserved_recorder_env(source)` to `deploy/worker/ubuntu/configure-analytics-profiles.py`: literal/bounds validation with safe fallback, relative-destination enforcement, relative spool path, HTTP(S)-only HLS URL, unknown extras preserved verbatim, status-only output.
- [x] T002 Spread the validated recorder block into the Water dict (from `worker.env`) and the Road dict (from the existing `road-worker.env`) in `main()`, keeping the existing mode-600, API token, M2M URL and relay URL checks untouched.
- [x] T003 Change `DEFAULT_DESTINATION` in `worker/recorder.py` to the relative `root@10.123.239.127:./`, keeping the `SEA_SPEED_RECORDER_DESTINATION` override working.
- [x] T004 Provision `shared/runtime/recorder-spool` and `shared/road-runtime/recorder-spool` (service-user owner, mode 750, symlink refused, absent runtime root skipped) in `deploy-authorized.sh` after the reconcile and before activation.
- [x] T005 Create the same recorder spool directories in `install-systemd.sh` and include them in the existing 750 pass.
- [x] T006 Document the relative-destination constraint and the relative default in `worker.env.example` and `road-worker.env.example`, keeping both recorder blocks identical; write this SDD trio.
- [ ] T007 Test worker: add reconcile/preservation, invalid-value, destination, `RecorderConfig` default and spool-provisioning tests in `tests/**`.
- [ ] T008 Validation: py_compile, bash -n, ruff, `validate_sdd.py` and the test worker's suite green on the exact head.

## Requirements traceability

- AC-001 | Task: T001, T002 | Evidence: TEST-001/TEST-002 (test worker); implementation-time temp-root reconcile preserved ENABLED=1, SOURCE_TYPE=rtsp, POLL_SEC=3, RSYNC_RETRIES=5 in `worker.env` while `road-worker.env` kept its own block | Coverage: COVERED
- AC-002 | Task: T001 | Evidence: TEST-002/TEST-003 (test worker); implementation probe rewrote ENABLED=yes to 0 and POLL_SEC=abc to 2 with exit 0 | Coverage: COVERED
- AC-003 | Task: T001, T003 | Evidence: TEST-001/TEST-004 (test worker); implementation probe rewrote the legacy absolute destination to `root@10.123.239.127:./` in both files | Coverage: COVERED
- AC-004 | Task: T003 | Evidence: TEST-004 (test worker); implementation probe of `RecorderConfig.from_env()` returned the relative destination with no env value and kept a timeout override | Coverage: COVERED
- AC-005 | Task: T004, T005 | Evidence: TEST-005 post-deploy `stat` of both spool directories (service-user owner, 750) and the recorder start line | Coverage: RUNTIME-MANUAL | Reason: directory ownership/mode provisioning runs as root inside the protected deploy transaction and is verified on the GPU box after deployment.
- AC-006 | Task: T006 | Evidence: diff of both env examples shows the identical relative-destination block and value | Coverage: COVERED
- AC-007 | Task: T001, T002 | Evidence: TEST-003 (test worker); reconcile output contains only status words (`SECRETS_DISPLAYED=NO`) and both files stay mode 600 | Coverage: COVERED

## Evidence (to be filled after tests land)

- Reconcile preservation/negative/destination tests: PENDING (test worker owns `tests/**`).
- `RecorderConfig` default and override tests: PENDING (test worker owns `tests/**`).
- Spool provisioning acceptance: PENDING (post-deploy `stat` and journal start line).
- Note: implementation-time temp-root probes covered preservation, per-file independence, malformed-value fallback, absolute-destination rewrite, repeat-run idempotency and mode 600.

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (`deploy/worker/ubuntu/configure-analytics-profiles.py`, `deploy-authorized.sh`, `install-systemd.sh`, both env examples, `worker/recorder.py`, this SDD trio only)
- [ ] Required tests and evidence complete
- [ ] Required CI green
- [ ] Exact-green-head merge complete
- [x] Deployment state resolved (Ubuntu worker/relay deploy REQUIRED; VPS NOT REQUIRED; acceptance planned)
- [x] Runtime acceptance resolved (recorder start, spool ownership/mode and rrsync path probes planned for the merged SHA deploy)
- [x] Deferred work recorded (SSH `known_hosts` provisioning for the service user is a separate issue)
- [x] Risks resolved or explicitly accepted (RISK-001..RISK-004 MITIGATED)
- [x] Waivers resolved or current (none)

## Completion gate

- [ ] Requirements are covered by tasks and traceability.
- [ ] Spec, plan and tasks match the implemented behavior after the test worker's suite lands.
- [ ] Required CI is green on the exact head.
- [ ] Exact-green-head merge evidence is recorded in the canonical Issue.
- [ ] Deploy acceptance shows the recorder block preserved, the relative destination in use and both spool directories owned by the service user with mode 750.
- [ ] Runtime learning and deferred work are written back to the feature artifacts or recorded as approved follow-up.
