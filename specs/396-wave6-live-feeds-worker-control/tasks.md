# Tasks: Live feeds + worker control extraction — api/app/live_feeds.py (Wave 6)

- Specification: specs/396-wave6-live-feeds-worker-control/spec.md

## Delivery tasks

- T001: Extract `api/app/live_feeds.py` (10 names — 4 functions:
  _validate_road_live_envelope, _road_live_stream_gen,
  _validate_water_live_envelope, _water_live_stream_gen; 6
  constants/state objects: ROAD_LIVE_MAX, ROAD_LIVE, ROAD_LIVE_LOCK,
  WATER_LIVE_MAX, WATER_LIVE, WATER_LIVE_LOCK) from `api/app/main.py` by
  scripted byte-range copy of the six regions (1038-1041 minus seq, 1043-1093,
  1118-1132, 1147-1150 minus seq, 1152-1194, 1218-1232 at base b9a956b9);
  rewrite main.py with the wave-6 seam (explicit re-exports of all 10 names,
  dual idiom) and the dropped dead imports (`import threading`,
  `from collections import deque`; no behavior change, routes byte-untouched;
  ROAD_LIVE_SEQ/WATER_LIVE_SEQ stay module-local to main — plan D-1;
  worker-control scope resolves to EMPTY — plan D-2)
- T002: Reader audit — verify by repo-wide grep over every moved name that no
  logic test/script/fixture references the live-feed slice (evidence: only
  worker/hls_motion_yolo_worker_events.py's own constants and historical
  wave-5 spec prose); apply the single per-wave deploy-envelope fixture line
  (test_vps_deploy_transaction.py write_release += api/app/live_feeds.py,
  wave-3/4/5 precedent — required because release_complete now rejects
  fixture releases without the module); #393 teeth byte-effective (focused
  run 12/12 OK after extraction); #393/workers/contract/state-transaction
  walks verified against the staying route set and identity.py ownership
- T003: Extend `deploy/vps/deploy.sh` through all seven wave-1..5 pattern
  sites (target var, release_complete, download required list, release
  install, bootstrap capture, install staging, activation before main.py)
  and converge `scripts/quality/build_exact_artifacts.py` (vps required list
  gains `api/app/live_feeds.py`)
- T004: Grandfather `396-wave6-live-feeds-worker-control` in
  `scripts/ci/validate_sdd.py` (GRANDFATHERED_PREFIX_COLLISIONS, one entry,
  closing the 396 set) and add the SDD trio
  `specs/396-wave6-live-feeds-worker-control/{spec,plan,tasks}.md` (Risk
  REQUIRED; RISK/TEST rows; TX-001..008; DoD) — this directory
- T005: Run the verification battery — full unittest suite (baseline 908/4,
  expected 908/4), `python3 scripts/ci/validate_repo.py`,
  `python3 scripts/ci/validate_sdd.py`, ruff
  (`scripts/quality/ruff.toml`, 0 errors — F821/F401 closure guard),
  `bash -n deploy/vps/deploy.sh`, byte-identity audit of the moved regions
  and staying live routes vs the base commit, route-table 61==61 with
  handler names, AST dependency-closure audit (4/4 moved fns, both idioms),
  single-definition state audit (8/8), import-mode smoke (package +
  roi-mock standalone) — commit on the wave branch is orchestrator-owned
  (no push from this session)

## Requirements traceability

- AC-001 | Task: T005 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T004, T005 | Evidence: TEST-004 | Coverage: COVERED
- AC-003 | Task: T003 | Evidence: TEST-002, TEST-003 | Coverage: COVERED
- AC-004 | Task: T001, T002 | Evidence: TEST-005 | Coverage: COVERED
- AC-005 | Task: T001, T005 | Evidence: TEST-007, TEST-008 | Coverage: COVERED
- AC-006 | Task: T001, T003 | Evidence: TEST-005 | Coverage: COVERED
- AC-007 | Task: T001, T002 | Evidence: TEST-005 | Coverage: COVERED

## Completion gate

- [ ] T001
- [ ] T002
- [ ] T003
- [ ] T004
- [ ] T005
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
