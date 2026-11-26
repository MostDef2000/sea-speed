# Tasks: REC indicator from successful segment uploads

- Specification: specs/699-rec-indicator/spec.md
- Plan: specs/699-rec-indicator/plan.md
- Issue: #699
- Sub-issue: REC
- Status: Source implementation landed on branch; tests owned by the test worker

## Delivery tasks

- [x] T001 Add `RECORDING_WITNESS_FRESHNESS_SEC`, `recording_witness_path` and the best-effort atomic `write_recording_witness` to `worker/recorder.py`; add a `record_witness` flag to `HlsRecorder.capture` and wire only the completed-segment call site in `run()` so init objects never write a witness.
- [x] T002 Call `write_recording_witness` in `worker/recorder_rtsp.py` `_finalize` only in the successful nonempty finalized-clip branch.
- [x] T003 Add `recording_last_success_at` and `_with_recording_state` to `worker/worker_transport.py`; enrich a copy of the metadata in `post_state` with the fresh ISO timestamp or explicit `null`, using the fixed `0 <= age < 30 s` window, function-local `datetime`/`re`, and no credential/URL recorder config.
- [x] T004 Document the witness contract with identical text in `deploy/worker/ubuntu/worker.env.example` and `road-worker.env.example`, adding no new flag.
- [x] T005 Author this SDD trio (`spec.md`, `plan.md`, `tasks.md`) under `specs/699-rec-indicator/`.
- [ ] T006 Test worker: add HLS/RTSP witness-write, freshness/wrong-camera/corrupt matrix, disabled/init-only/incomplete/failed-upload, left-over-witness, copy-enrichment and import-allowlist tests in `tests/**`.
- [x] T007 Validation: py_compile, ruff and `validate_sdd.py` green locally, then required CI green on the exact head and exact-green-head merge evidence recorded in the canonical Issue. — auto-synced on merge to main (6e4ed479)

## Requirements traceability

- AC-001 | Task: T001, T003 | Evidence: PENDING — TEST-003 (test worker) drives disabled recording and asserts no witness file plus `recording_last_success_at=null`; implementation keeps the writer behind the enabled-only recorder process | Coverage: COVERED
- AC-002 | Task: T001 | Evidence: PENDING — TEST-003 (test worker) drives an init-only HLS cycle and asserts no witness; implementation passes `record_witness=True` only at the segment call site | Coverage: COVERED
- AC-003 | Task: T002 | Evidence: PENDING — TEST-003 (test worker) drives an empty/over-cap RTSP clip and asserts no witness; implementation writes only in the `if ok:` finalized-clip branch | Coverage: COVERED
- AC-004 | Task: T001, T002 | Evidence: PENDING — TEST-003 (test worker) forces upload failure and asserts no witness; both arms call the writer only on successful upload | Coverage: COVERED
- AC-005 | Task: T001, T003 | Evidence: PENDING — TEST-001/TEST-004 (test worker) assert a successful HLS segment writes a witness and the next state carries the timestamp | Coverage: COVERED
- AC-006 | Task: T002, T003 | Evidence: PENDING — TEST-001 (test worker) asserts a successful nonempty RTSP clip writes a witness and the next state carries the timestamp | Coverage: COVERED
- AC-007 | Task: T003 | Evidence: PENDING — TEST-002 (test worker) asserts 29.9 s fresh, exactly 30 s expired and future null with the fixed constant | Coverage: COVERED
- AC-008 | Task: T003 | Evidence: PENDING — TEST-002/TEST-005 (test worker) assert missing/malformed/corrupt/wrong-camera null and that a read failure never suppresses the state POST | Coverage: COVERED
- AC-009 | Task: T003 | Evidence: PENDING — TEST-003 (test worker) leaves a fresh witness with recording disabled and asserts `null` | Coverage: COVERED

## Evidence (to be filled after tests land)

- HLS/RTSP success-only witness-write tests: PENDING (test worker owns `tests/**`).
- Freshness/wrong-camera/corrupt/disabled-with-leftover matrix: PENDING (test worker owns `tests/**`).
- Copy-enrichment and transport import-allowlist tests: PENDING (test worker owns `tests/**`).
- Local static verification observed at implementation time: `py_compile` OK, `ruff` clean, `validate_sdd.py` passed.
- Runtime acceptance (`recording_last_success_at` null-to-timestamp-to-null on the deployed SHA): PENDING post-deploy.

## Completion gate

- [ ] Requirements are covered by tasks and traceability.
- [ ] Spec, plan and tasks match the implemented behavior after the test worker's suite lands.
- [x] Required CI is green on the exact head. — auto-synced on merge to main (6e4ed479)
- [x] Exact-green-head merge evidence is recorded in the canonical Issue. — auto-synced on merge to main (6e4ed479)
- [ ] Deploy acceptance shows the REC indicator transitioning from `null` to a fresh timestamp while the recorder uploads completed segments and back to `null` when recording stops.
- [ ] Runtime learning and deferred work are written back to the feature artifacts or recorded as approved follow-up.

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (`worker/recorder.py`, `worker/recorder_rtsp.py`, `worker/worker_transport.py`, both Ubuntu env examples, this SDD trio only)
- [ ] Required tests and evidence complete
- [x] Required CI green — auto-synced on merge to main (6e4ed479)
- [x] Exact-green-head merge complete — auto-synced on merge to main (6e4ed479)
- [x] Deployment state resolved (Ubuntu worker/relay deploy REQUIRED; VPS consumer-only, no deploy mutation)
- [ ] Runtime acceptance resolved
- [x] Deferred work recorded (test-worker-owned `tests/**` updates and the no-gap/playable-archive non-goal)
- [x] Risks resolved or explicitly accepted (RISK-001..RISK-004 MITIGATED, RISK-005 ACCEPTED)
- [x] Waivers resolved or current (none)
