# Tasks: Water passages extraction — api/app/water_passages.py (Wave 3)

- Specification: specs/396-wave3-water-passages/spec.md

## Delivery tasks

- T001: Extract `api/app/water_passages.py` (8 functions: open_passages_db,
  cleanup_passage_media, prune_water_passages, initialize_water_passages_db,
  _validate_passage_payload, passage_row_to_dict, upsert_water_passage,
  list_water_passages) from `api/app/main.py` by scripted byte-range copy;
  rewrite main.py with the wave-3 seam (explicit re-exports, dual idiom),
  the updated binding comment with the byte-identical
  `passage_mirrors.open_passages_db = open_passages_db` binding line and
  the dropped `import sqlite3` / `from contextlib import contextmanager`
  (no behavior change, routes untouched)
- T002: Extend the multi-source AST readers in `tests/test_water_passage.py`,
  `tests/test_storage_retention.py`, `tests/test_unified_registry.py`,
  `tests/test_api_contract.py` (api_sources() join + function walk),
  `tests/test_line_crossing.py`, `tests/test_analytics_profiles.py` to
  resolve moved functions/markers from the new module with
  fallback-to-main, without weakening any assertion; add
  `api/app/water_passages.py` to the synthetic releases in
  `tests/test_vps_deploy_transaction.py`
- T003: Extend `deploy/vps/deploy.sh` through all seven wave-1/wave-2
  pattern sites (target var, release_complete, download required list,
  release install, bootstrap capture, install staging, activation before
  main.py); deliver hardening A (route-name pinning in
  `tests/test_route_table.py`: (handler_name, method, path) for all 61
  endpoints, still 1 test) and hardening B (vps required list convergence
  in `scripts/quality/build_exact_artifacts.py`)
- T004: Grandfather `396-wave3-water-passages` in `scripts/ci/validate_sdd.py`
  (GRANDFATHERED_PREFIX_COLLISIONS, one entry) and add the SDD trio
  `specs/396-wave3-water-passages/{spec,plan,tasks}.md` (Risk REQUIRED;
  RISK/TEST rows; TX-001..008; DoD) — this directory
- T005: Run the verification battery — full unittest suite (baseline 908/4,
  expected 908/4), `python3 scripts/ci/validate_repo.py`,
  `python3 scripts/ci/validate_sdd.py`, ruff
  (`scripts/quality/ruff.toml`), `bash -n deploy/vps/deploy.sh`,
  byte-identity audit of the 8 moved regions + binding line vs the base
  commit, route-table 61==61 with handler names, exact-artifacts
  build+validate — and commit on the wave branch (no push)

## Requirements traceability

- AC-001 | Task: T005 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T004, T005 | Evidence: TEST-004 | Coverage: COVERED
- AC-003 | Task: T003 | Evidence: TEST-002, TEST-003 | Coverage: COVERED
- AC-004 | Task: T001, T002 | Evidence: TEST-005, TEST-006 | Coverage: COVERED
- AC-005 | Task: T001 | Evidence: TEST-007 | Coverage: COVERED
- AC-006 | Task: T001, T003 | Evidence: TEST-005 | Coverage: COVERED
- AC-007 | Task: T003 | Evidence: TEST-005 | Coverage: COVERED
- AC-008 | Task: T003, T005 | Evidence: TEST-008 | Coverage: COVERED

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
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-006 mitigated in plan.md
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
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-006 mitigated in plan.md
- [ ] Waivers resolved or current — none
