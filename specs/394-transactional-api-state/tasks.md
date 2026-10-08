# Tasks: Transactional mutable API state persistence

- Specification: specs/394-transactional-api-state/spec.md

## Delivery tasks

- T-394-001: Add `api/app/store.py` (stdlib only): fail-loud
  `read_json_file` / atomic flock + uuid-tmp `write_json_file`, WAL SQLite
  hot-state store (`crossings`/`event_feed`/`camera_state` with
  `camera_id`, per-camera same-transaction caps 5000/500, single-statement
  camera-state upsert) and the transition-protocol primitives:
  content-keyed `INSERT OR IGNORE` legacy merge (`camera_has_rows` probe,
  documented SHA-256 canonical-payload key), newer-wins camera-state
  import
- T-394-002: Rewire `api/app/main.py`: SQLite-authoritative state, event
  feed and crossings with best-effort legacy JSON projection mirrors,
  fail-loud HTTP 500 on corrupt config/preview stores, necessity-gated
  fail-closed startup migration (`import_legacy_state_store`: empty target
  → raise on corrupt legacy; populated target → stderr warning + skip),
  constants (`STATE_DB_FILE`, `EVENTS_FEED_LIMIT`, `CROSSINGS_STORE_LIMIT`
  at the top block for import-time ordering)
- T-394-003: Add `tests/test_api_state_transaction.py` (fail-loud, no
  lost updates, unique-tmp collision, caps, upsert, transition-protocol
  T-A..T-D; RED on the base implementation, store-level tests green) and
  update the harnesses (`test_api_contract.py`, `test_line_crossing.py`,
  `test_road_event_hygiene.py`, `test_vps_deploy_transaction.py`) minimally
  for the new store seam without weakening any assertion
- T-394-004: Update `deploy/vps/deploy.sh`: atomic uuid-tmp write in the
  ROI-migration heredoc and minimal `api/app/store.py` install plumbing
  (release completeness, download required list, install, soft activation
  bound to the selected release's content with clean removal on pre-#394
  rollback, bootstrap capture of a live store.py) — disclosed deviation
  recorded in spec.md
- T-394-005: Run the verification battery (full pytest, new behavioral
  suite verbose, RED check against the stashed base implementation, ruff
  E9/F, bash -n) and leave the changes uncommitted for orchestrator
  admission

## Completion gate

- [ ] T-394-001
- [ ] T-394-002
- [ ] T-394-003
- [ ] T-394-004
- [ ] T-394-005
- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [ ] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned (VPS restart, health gate, dual-write window verified post-deploy)
- [ ] Deferred work recorded — none
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-005 mitigated or disclosed in plan.md
- [ ] Waivers resolved or current — none

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI) — auto-synced on merge to main
- [ ] Exact-green-head merge complete — orchestrator-owned — auto-synced on merge to main
- [ ] Deployment state resolved — orchestrator-owned (full autonomous VPS contour deploy fans out at merge)
- [ ] Runtime acceptance resolved — orchestrator-owned (fail-closed boot health gate + dual-write window verified post-deploy; ИБ-пробы relayed per #393 tail plan)
- [ ] Deferred work recorded — dual-write JSON mirror retirement in a follow-up release
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-005 in plan.md Risk profile
- [ ] Waivers resolved or current — none

## Requirements traceability

- AC-001 | Task: T-394-001,T-394-003 | Evidence: test_write_round_trip_is_atomic, test_concurrent_writers_leave_one_valid_file_and_no_tmp (25+25 alternating writers, no tmp leftovers) | Coverage: COVERED
- AC-002 | Task: T-394-001,T-394-003 | Evidence: test_legacy_fixed_tmp_collision_is_eliminated (deterministic barrier RED vs base: fixed `.tmp` consumed by the first rename, second writer explodes) | Coverage: COVERED
- AC-003 | Task: T-394-002,T-394-003 | Evidence: FailLoudReadTests — speed-config/speed-lines/crossing-line corrupt stores raise HTTP 500 (RED on base: silent default), events endpoint reads SQLite authoritatively | Coverage: COVERED
- AC-004 | Task: T-394-002,T-394-003 | Evidence: test_concurrent_appenders_never_lose_records (8 barrier-forced racers, zero lost records on head, RED on base RMW) | Coverage: COVERED
- AC-005 | Task: T-394-001,T-394-003 | Evidence: StoreCapTests — crossings prune to 5000, events to 500, caps per camera | Coverage: COVERED
- AC-006 | Task: T-394-001,T-394-003 | Evidence: CameraStateTests (last-write-wins upsert, absent state reads None) | Coverage: COVERED
- AC-007 | Task: T-394-002,T-394-003 | Evidence: T-A test_corrupt_legacy_mirror_is_best_effort_when_store_is_populated, T-B test_corrupt_legacy_file_fails_closed, T-C test_rollback_window_records_are_merged_content_keyed, T-D test_camera_state_import_is_newer_wins + StartupMigrationTests (never deletes legacy files, restart-idempotent) | Coverage: COVERED
- AC-008 | Task: T-394-003,T-394-004 | Evidence: T-E test_store_less_rollback_removes_live_store_and_stale_next, test_store_release_stages_and_promotes_normally (release-bound activation, stale .next never promoted, bootstrap captures live store.py) | Coverage: COVERED
- AC-009 | Task: T-394-003,T-394-005 | Evidence: tests.test_api_contract (14), tests.test_line_crossing (45), tests.test_road_event_hygiene (7), tests.test_roi_normalization (unchanged green), tests.test_vps_deploy_transaction (20) — full suite green (exact counts in the verification transcript); two-file battery 42 passed / 1 skipped; RED on base: 6 failed / 12 passed / 2 skipped | Coverage: COVERED
