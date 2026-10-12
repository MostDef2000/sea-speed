# Tasks: Objects registry extraction — api/app/objects_registry.py + api/app/passage_mirrors.py (Wave 2)

- Specification: specs/396-wave2-objects-registry/spec.md

## Delivery tasks

- T001: Extract `api/app/objects_registry.py` (13 functions: open_objects_db,
  prune_objects_registry, initialize_objects_db, optional_float, optional_int,
  stable_object_id, prune_snapshotless_objects, persist_object_event,
  import_existing_events, object_row_to_dict, build_objects_where,
  patch_object_record, delete_object_record) and
  `api/app/passage_mirrors.py` (persist_passage_object,
  import_existing_passages, _delete_passage_mirrors,
  reconcile_passage_mirrors + open_passages_db sentinel) from
  `api/app/main.py` by scripted byte-range copy; rewrite main.py with the
  wave-2 seam (explicit re-exports, dual idiom), the one-line
  `passage_mirrors.open_passages_db = open_passages_db` binding and the
  dropped `import hashlib` (no behavior change, routes untouched)
- T002: Extend the multi-source AST readers in `tests/test_api_contract.py`,
  `tests/test_unified_registry.py`, `tests/test_storage_retention.py`,
  `tests/test_water_passage.py`, `tests/test_line_crossing.py` to resolve
  moved functions/markers from the new modules with fallback-to-main, and
  repoint the `test_endpoint_requires_snapshot` source read, without
  weakening any assertion
- T003: Add `tests/test_route_table.py` (frozen 61-endpoint AST
  fingerprint); extend `deploy/vps/deploy.sh` through all seven wave-1
  pattern sites (targets, release_complete, download required list, release
  install, bootstrap capture, install staging, activation before main.py);
  add both-module fixtures to the synthetic releases in
  `tests/test_vps_deploy_transaction.py`
- T004: Grandfather the #396 wave pair in `scripts/ci/validate_sdd.py`
  (GRANDFATHERED_PREFIX_COLLISIONS, one entry) and add the SDD trio
  `specs/396-wave2-objects-registry/{spec,plan,tasks}.md` (Risk REQUIRED;
  RISK/TEST rows; TX-001..008; DoD) — this directory
- T005: Run the verification battery — full unittest suite (baseline 907/4,
  expected 908/4), `python3 scripts/ci/validate_repo.py`,
  `python3 scripts/ci/validate_sdd.py`, ruff
  (`scripts/quality/ruff.toml`), `bash -n deploy/vps/deploy.sh`,
  byte-identity audit of the 17 moved regions vs the base commit — and
  commit on the wave branch (no push)

## Requirements traceability

- AC-001 | Task: T005 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T005 | Evidence: TEST-004 | Coverage: COVERED
- AC-003 | Task: T003 | Evidence: TEST-002, TEST-003 | Coverage: COVERED
- AC-004 | Task: T001, T002 | Evidence: TEST-005, TEST-006 | Coverage: COVERED
- AC-005 | Task: T001 | Evidence: TEST-007 | Coverage: COVERED
- AC-006 | Task: T001, T003 | Evidence: TEST-005 | Coverage: COVERED

## Completion gate

- [x] T001
- [x] T002
- [x] T003
- [x] T004
- [x] T005
- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [ ] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] Deployment state resolved — rides the VPS deploy of this wave (DEPLOY-TRIGGER, полоса A) — orchestrator-owned
- [ ] Runtime acceptance resolved — health gate probe on the VPS deploy — orchestrator-owned
- [ ] Deferred work recorded — none
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-005 mitigated in plan.md
- [ ] Waivers resolved or current — none

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [ ] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] Deployment state resolved — rides the VPS deploy of this wave (DEPLOY-TRIGGER, полоса A) — orchestrator-owned
- [ ] Runtime acceptance resolved — health gate probe on the VPS deploy — orchestrator-owned
- [ ] Deferred work recorded — none
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-005 mitigated in plan.md
- [ ] Waivers resolved or current — none
