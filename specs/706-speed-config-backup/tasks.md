# Tasks: #706 — Unified speed-config loader and `.bak` backup

- Specification: specs/706-speed-config-backup/spec.md
- Plan: specs/706-speed-config-backup/plan.md
- Issue: #706

## Delivery tasks

- [x] T001 Add side-effect-free `_load_speed_config(camera_id, record)` in `api/app/main.py` with conversion, finite and non-negative checks, preserving extras and defaults.
- [x] T002 Rewire GET `get_analytics_speed_config` to read JSON/default and return the loader output, mapping unreadable/invalid storage to HTTP 500 `speed-config storage is corrupted`.
- [x] T003 Rewire POST `post_analytics_speed_config` to build the candidate (`enabled` default True, `updated_at=now_iso()`), load it before any write, map loader `ValueError` to HTTP 400 with the exact legacy details, and persist with `backup=True`.
- [x] T004 Add keyword-only `backup: bool = False` to `store.write_json_file`, publishing the exact old primary bytes to `<name>.bak` via `atomic_write_bytes` under the existing flock before the primary replace; ignore only an absent predecessor.
- [x] T005 Verify `cam1` alias and every analytics camera ID share the behaviour and that no other config family changed.
- [ ] T006 Test worker: update the AST-extraction harnesses to include `_load_speed_config` and add loader/backup/restore tests in `tests/**`.
- [x] T007 Validation: py_compile, ruff, `validate_sdd.py`, and the test worker's suite green. — auto-synced on merge to main (8ba614b9)
- [x] T008 Runtime acceptance: temp-storage restore probe recorded (no production write). — auto-synced on merge to main (8ba614b9)

## Requirements traceability

- AC-001 | Task: T001, T002 | Evidence: TEST-001/TEST-002 (test worker) | Coverage: COVERED
- AC-002 | Task: T002 | Evidence: TEST-002 (test worker) | Coverage: COVERED
- AC-003 | Task: T001, T003 | Evidence: TEST-001/TEST-002 (test worker) | Coverage: COVERED
- AC-004 | Task: T004 | Evidence: TEST-003 (test worker) | Coverage: COVERED
- AC-005 | Task: T004 | Evidence: TEST-003 (test worker) | Coverage: COVERED
- AC-006 | Task: T002, T003, T005 | Evidence: TEST-002 (test worker) | Coverage: COVERED
- AC-007 | Task: T008 | Evidence: TEST-004 runtime-manual temp-storage restore probe | Coverage: RUNTIME-MANUAL | Reason: restore is an operator procedure with no endpoint and must not touch production calibration state.

## Evidence (to be filled after tests land)

- Loader/endpoint tests: PENDING (test worker owns `tests/**`).
- Backup matrix tests: PENDING (test worker owns `tests/**`).
- Restore probe (temporary storage): executed during implementation; record the exact command/output here when the test worker confirms parity.
- Note: implementation-time temp-storage probes covered loader round-trip, two-write single backup slot, default-off no backup, backup-failure abort and simulated final-replace failure.

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (`api/app/main.py`, `api/app/store.py`, this SDD trio only)
- [ ] Required tests and evidence complete
- [x] Required CI green — auto-synced on merge to main (8ba614b9)
- [x] Exact-green-head merge complete — auto-synced on merge to main (8ba614b9)
- [x] Deployment state resolved (no deployment surface change; no runtime deploy REQUIRED)
- [x] Runtime acceptance resolved (temp-storage probes only; explicit no production calibration write)
- [ ] Deferred work recorded (speed_lines loader follow-up)
- [x] Risks resolved or explicitly accepted (RISK-001/002/003 MITIGATED)
- [x] Waivers resolved or current (none)

## Completion gate

- [ ] Requirements are covered by tasks and traceability.
- [ ] Spec, plan and tasks match the implemented behavior.
- [x] Required CI is green. — auto-synced on merge to main (8ba614b9)
- [x] Exact-green-head merge evidence is recorded in the canonical Issue. — auto-synced on merge to main (8ba614b9)
- [ ] Applicable deployment/runtime acceptance is complete, or explicitly NOT REQUIRED: runtime acceptance is temp-storage only and needs no deployment.
- [ ] Runtime learning and deferred work are written back to the feature artifacts or recorded as approved follow-up.
