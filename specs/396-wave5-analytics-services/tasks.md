# Tasks: Analytics services extraction — api/app/analytics.py (Wave 5)

- Specification: specs/396-wave5-analytics-services/spec.md

## Delivery tasks

- T001: Extract `api/app/analytics.py` (27 names — 18 functions:
  sweep_events_media, default_state, analytics_data_file,
  analytics_default_state, analytics_state, clean_points_list,
  _is_normalized_point, _clean_norm_points, _infer_legacy_ref_w_h,
  _normalize_from_absolute, _denormalize_to_absolute,
  _normalize_legacy_polygon, get_analytics_crossing_line,
  post_analytics_crossing_line, append_crossing_record,
  post_analytics_crossing, _vlz_day_bounds,
  get_analytics_crossings_summary; 9 constants: EVENTS_MEDIA_GRACE_SECONDS,
  EVENTS_SWEEP_INTERVAL_SECONDS, _events_sweep_state, DEFAULT_ROI_REF_W,
  DEFAULT_ROI_REF_H, LEGACY_ROI_W, LEGACY_ROI_H, CROSSING_DIRECTIONS,
  VLZ_TIMEZONE) from `api/app/main.py` by scripted byte-range copy of the
  three regions (286-329, 342-511, 1051-1218 at base beea1067); rewrite
  main.py with the wave-5 seam (explicit re-exports of all 27 names, dual
  idiom) and the dropped dead imports (7 config seam names + `date`/
  `timedelta` + `typing.List`; no behavior change, routes, the
  passage_mirrors binding and the module-tail init calls untouched;
  `_events_sweep_state` moves as slice-exclusive mutable state — plan
  D-1/D-2/D-6; `now_iso` imported from identity in both idioms — plan D-7)
- T002: Extend the six reader suites by walk extension only (teeth
  byte-effective, no assertion weakened): `tests/test_api_state_transaction.py`
  (multi-source extract), `tests/test_line_crossing.py` (source list +
  tree_candidates + two text joins), `tests/test_storage_retention.py`,
  `tests/test_api_contract.py` (two walks), `tests/test_analytics_profiles.py`
  (additive/camera-isolated walk); add `api/app/analytics.py` to the
  synthetic releases in `tests/test_vps_deploy_transaction.py`; verify by
  grep that no other reader references a moved name
  (`test_road_event_hygiene.py` needs no edit — it extracts
  `post_analytics_event`, which stays in main.py)
- T003: Extend `deploy/vps/deploy.sh` through all seven wave-1/2/3/4
  pattern sites (target var, release_complete, download required list,
  release install, bootstrap capture, install staging, activation before
  main.py) and converge `scripts/quality/build_exact_artifacts.py` (vps
  required list gains `api/app/analytics.py`)
- T004: Grandfather `396-wave5-analytics-services` in
  `scripts/ci/validate_sdd.py` (GRANDFATHERED_PREFIX_COLLISIONS, one
  entry) and add the SDD trio
  `specs/396-wave5-analytics-services/{spec,plan,tasks}.md` (Risk REQUIRED;
  RISK/TEST rows; TX-001..008; DoD) — this directory
- T005: Run the verification battery — full unittest suite (baseline 908/4,
  expected 908/4), `python3 scripts/ci/validate_repo.py`,
  `python3 scripts/ci/validate_sdd.py`, ruff
  (`scripts/quality/ruff.toml`, 0 errors — F821/F401 closure guard),
  `bash -n deploy/vps/deploy.sh`, byte-identity audit of the moved regions
  vs the base commit, route-table 61==61 with handler names, AST
  dependency-closure audit (18/18), import-mode smoke (package +
  roi-mock standalone) — commit on the wave branch is orchestrator-owned
  (no push from this session)

## Requirements traceability

- AC-001 | Task: T005 | Evidence: TEST-001 | Coverage: COVERED
- AC-002 | Task: T004, T005 | Evidence: TEST-004 | Coverage: COVERED
- AC-003 | Task: T003 | Evidence: TEST-002, TEST-003 | Coverage: COVERED
- AC-004 | Task: T001, T002 | Evidence: TEST-005, TEST-006 | Coverage: COVERED
- AC-005 | Task: T001, T005 | Evidence: TEST-007, TEST-008 | Coverage: COVERED
- AC-006 | Task: T001, T003 | Evidence: TEST-005 | Coverage: COVERED
- AC-007 | Task: T003, T005 | Evidence: TEST-004 | Coverage: COVERED

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
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-007 mitigated in plan.md
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
- [ ] Risks resolved or explicitly accepted — RISK-001..RISK-007 mitigated in plan.md
- [ ] Waivers resolved or current — none
