# Tasks: Single-source analytics profile defaults for the protected configure step

- Specification: specs/395-analytics-profiles-single-source/spec.md

## Delivery tasks

- T-395-001: Add the minimal string-serialization helper
  (`AnalyticsProfile.env_file_defaults()`) to `worker/analytics_profiles.py`
  producing the env-file default mapping (ANALYTICS_PROFILE, CAMERA_ID,
  MODEL_NAME, YOLO_TRACKER, YOLO_IMAGE_SIZE, YOLO_CONFIDENCE, SAMPLE_FPS)
  without changing the existing module surface
- T-395-002: Rewire `deploy/worker/ubuntu/configure-analytics-profiles.py` to
  import the canonical module via a `__file__`-relative sys.path entry with a
  fail-closed `SystemExit` on import failure, expose
  `derived_profile_defaults()`, and replace both hardcoded water/road default
  blocks with derived mappings while keeping the `_preserve_float`/`_road_float`
  precedence semantics and configure-local tuning knobs
- T-395-003: Add the executed drift regression module
  `tests/test_analytics_profiles_configure_drift.py`: derivation equality
  against independently re-derived canonical fields, confidence-literal and
  serialization pins, no-hardcoded-value structural pin, and an executed
  subprocess precedence run (water SAMPLE_FPS=7.5 preserved, persisted road
  SAMPLE_FPS=12.5 preferred) through the module-wide
  `SEA_SPEED_395_CONFIGURE_PATH` override
- T-395-004: Run the verification battery (ruff, targeted unittest modules, full
  unittest discover suite, SDD validator, RED check against the base configure
  script materialized from f82a968) and leave the changes uncommitted for
  orchestrator admission

## Completion gate

- [ ] T-395-001
- [ ] T-395-002
- [ ] T-395-003
- [ ] T-395-004

## Requirements traceability

- AC-001 | Task: T-395-001,T-395-002,T-395-003 | Evidence: test_water_and_road_defaults_equal_canonical_profile_fields, demonstrated RED against the base script via SEA_SPEED_395_CONFIGURE_PATH | Coverage: COVERED
- AC-002 | Task: T-395-001,T-395-003 | Evidence: test_confidence_literals_unchanged_and_two_decimal_serialized (0.10/0.15 literals; "0.10"/"0.15"/"960"/"10" serialization) | Coverage: COVERED
- AC-003 | Task: T-395-002,T-395-003 | Evidence: test_existing_env_value_overrides_derived_default (executed configure run over the real script) | Coverage: COVERED
- AC-004 | Task: T-395-002,T-395-003,T-395-004 | Evidence: test_configure_script_derives_and_fails_closed_without_hardcoded_values plus green pre-existing tests.test_analytics_profiles and tests.test_ubuntu_worker_deploy_authorized pins | Coverage: COVERED

## Definition of Done

- [ ] Issue/spec/plan/tasks current
- [ ] Exact changed-file scope verified
- [ ] Required tests and evidence complete
- [ ] Required CI green — orchestrator-owned (PR creation and exact-head CI)
- [ ] Exact-green-head merge complete — orchestrator-owned
- [ ] Deployment state resolved — orchestrator-owned
- [ ] Runtime acceptance resolved — orchestrator-owned (derived defaults land on a live protected deploy)
- [ ] Deferred work recorded — none in this unit
- [ ] Risks resolved or explicitly accepted — RISK-001 mitigated; live-host behaviour verified post-deploy
- [ ] Waivers resolved or current — none
