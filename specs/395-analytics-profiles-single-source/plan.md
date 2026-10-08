# Plan: Single-source analytics profile defaults for the protected configure step

- Specification: specs/395-analytics-profiles-single-source/spec.md

## Architecture

Two-file change plus a new executed drift test:

- `worker/analytics_profiles.py` gains one minimal method,
  `AnalyticsProfile.env_file_defaults()`, that serializes the profile fields the
  configure step needs into env-file strings (`f"{confidence:.2f}"` for the
  two-decimal confidence, `str(image_size)`, and an integer-collapse for
  sample-fps so 10.0 serializes to "10"). No existing name or signature changes.
- `deploy/worker/ubuntu/configure-analytics-profiles.py` derives the worker
  directory from `Path(__file__).resolve().parents[3] / "worker"`, inserts it at
  the front of `sys.path`, and imports `analytics_profiles` at module scope; an
  import failure raises `SystemExit("ERROR canonical analytics profile module
  unavailable: ...")` so the step fails closed with no hardcoded fallback.
  `derived_profile_defaults()` returns the water/road default mappings from the
  canonical module, and `main()` splats them into the existing update dicts —
  the configure-local keys (SAMPLE_FPS precedence helpers, HD frame resolution,
  YOLO_HALF, YOLO_CLASSES_FILTER, MOTION_GATE_MODE, LATEST_FRAME_BOUNDED, road
  relay/M2M URLs, token) keep their exact base semantics and ordering.
- `tests/test_analytics_profiles_configure_drift.py` loads the canonical module
  from the worker directory and the configure script through the module-wide
  `SEA_SPEED_395_CONFIGURE_PATH` override (default: the repo-relative script),
  builds the expected mapping independently from canonical `PROFILES` fields,
  and asserts equality — so the whole chain script → helper → profile fields is
  pinned, and a re-introduced hardcoded copy or a broken derivation fails RED.

## Decisions

- DEC-1: String-serialization lives on the canonical module
  (`env_file_defaults()`), not in the configure script: the two-decimal
  confidence format and the integer fps collapse are profile semantics, and
  keeping them next to `profile_defaults()` leaves one place that owns profile
  values. The existing raw-typed `profile_defaults()` is left untouched for its
  current callers.
- DEC-2: Fail closed with `SystemExit` instead of a try/except fallback:
  silently degrading to stale literals would reintroduce the exact drift #395
  removes; the configure step runs inside the deploy transaction, whose
  existing configure-failure rollback (`DEPLOY_CONFIG_ROLLED_BACK
  reason=configure_failed`) already handles a non-zero exit correctly.
- DEC-3: The worker directory is derived from `Path(__file__).resolve()` rather
  than CWD or env: the script is invoked by deploy-authorized.sh with an
  absolute staged path and unknown CWD; the repo layout
  (`deploy/worker/ubuntu/…` next to `worker/…`) is a structural property of the
  exact artifacts, so `parents[3] / "worker"` is stable in CI, tests and the
  staged release.
- DEC-4: The drift test builds its expected mapping directly from canonical
  `AnalyticsProfile` fields instead of calling the new helper, so a defect in
  the helper itself cannot make the test self-confirming.
- DEC-5: Profile names ("water-v1"/"road-v1") stay as the configure script's
  selectors: names are the derivation key, not drifted values; configure-local
  tuning knobs are deliberately kept out of the canonical module because they
  are deployment tuning, not profile semantics.

## Affected contours

- Ubuntu Worker/relay deploy configuration only:
  `deploy/worker/ubuntu/configure-analytics-profiles.py`,
  `worker/analytics_profiles.py`, the new drift test, and this SDD trio.
- No change to update-exact.sh, rollback-exact.sh, install scripts, deploy
  workflows, the VPS contour, the sync-bot, env examples, docs or any
  credential material; threshold values (0.10/0.15) are unchanged.

## Validation

- `ruff check` (E9+F, `scripts/quality/ruff.toml`) on the three touched files.
- `python3 -m unittest tests.test_analytics_profiles
  tests.test_analytics_profiles_configure_drift
  tests.test_ubuntu_worker_deploy_authorized -v` green.
- Full suite `python3 -m unittest discover -s tests -p 'test_*.py'` green.
- `python3 scripts/ci/validate_sdd.py` green.
- RED check: `git show` the base configure script (`f82a968bed50b86b66cd9d01b7e
  bbf3ca4d3fd1c`) into a temp file and run the whole
  `tests.test_analytics_profiles_configure_drift` module with
  `SEA_SPEED_395_CONFIGURE_PATH` pointed at it — the derivation, fail-closed and
  no-hardcoded-value pins must fail while the precedence run passes (it guards
  behaviour that already existed).

## Runtime feedback

- RF-001: Operator actions expected: 0; derivation happens inside the existing
  deploy-authorized configure step.
- RF-002: On canonical-module import failure the configure step exits with an
  `ERROR canonical analytics profile module unavailable` line instead of writing
  drifted env values.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: fail-closed canonical import with no hardcoded fallback, byte-identical serialization pins ("0.10"/"0.15"/"960"/"10"), precedence helpers untouched, executed derivation-equality test built independently from canonical fields, executed subprocess precedence run over the real script, RED anchor against the base script via the module-wide SEA_SPEED_395_CONFIGURE_PATH override, exact three-file scope | Validation: targeted unittest modules (drift, analytics profiles, deploy-authorized), full unittest discover suite, ruff and SDD validators green locally; derivation/fail-closed pins RED against the base script materialized from f82a968 | Residual risk: LOW — the deployed configure step resolves the canonical module from the staged release layout (worker/ at the script's parents[3]); that relative layout is a structural property of the exact artifacts (both files are required members of the ubuntu-worker artifact set) and is exercised by the executed subprocess runs from the real repo layout; behaviour on a live host is verified after production deploy | Owner: Delivery Orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: R-1,R-2 | Level: unit | Priority: P0 | Evidence: test_water_and_road_defaults_equal_canonical_profile_fields and test_configure_script_derives_and_fails_closed_without_hardcoded_values (RED vs base via SEA_SPEED_395_CONFIGURE_PATH)
- TEST-002 | Covers: R-4 | Level: unit | Priority: P0 | Evidence: test_confidence_literals_unchanged_and_two_decimal_serialized (canonical literals 0.10/0.15; two-decimal, "960" and "10" serialization)
- TEST-003 | Covers: R-3 | Level: integration | Priority: P0 | Evidence: test_existing_env_value_overrides_derived_default (executed configure run: water SAMPLE_FPS=7.5 preserved, persisted road SAMPLE_FPS=12.5 preferred, derived defaults land elsewhere, mode 600 kept)
- TEST-004 | Covers: R-1,R-2,R-3,R-4 | Level: integration | Priority: P1 | Evidence: pre-existing tests.test_analytics_profiles and tests.test_ubuntu_worker_deploy_authorized pins green unchanged; full unittest discover suite, ruff and SDD validators green

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: Issue #395 checkpoint + authorization receipt (OUTCOME APPROVED, issuecomment-6049885440)
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: configure-step preflight gates unchanged (worker.env presence and mode 600, preview catalog presence); canonical import resolves before any env mutation and fails closed on failure
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: unchanged protected env files | Retry: NO | Rollback: DEPLOY_CONFIG_ROLLED_BACK reason=configure_failed path (restore_protected_config) already covered by deploy-authorized.sh; this unit changes only which values the configure step derives, not the transaction around it | Evidence: test_ubuntu_worker_deploy_authorized configure-failure rollback pins green; executed precedence run writes derived defaults and preserves overrides
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: verification gates behave as before | Retry: NO | Rollback: NONE | Evidence: ANALYTICS output lines unchanged (ANALYTICS_PROFILES_CONFIGURED=YES, ROAD_API=protected_private_worker_ingress); worker state gates untouched
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: active-source-commit marker (deploy-authorized.sh) unchanged
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: write_env atomic tmp+replace pattern unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: execution-audit v1
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh contour unchanged; the configure step is re-runnable and derives the same values from the canonical module | Evidence: rollback manifest
