# Spec: Single-source analytics profile defaults for the protected configure step

- Issue: #395
- Specification: specs/395-analytics-profiles-single-source/spec.md

## Product outcome

`deploy/worker/ubuntu/configure-analytics-profiles.py` carries its own copies of
the non-secret analytics profile values (model name, tracker, image size,
confidence, sample-fps default) that are already owned by
`worker/analytics_profiles.py`. When a profile value changes in the canonical
module, the configure step silently keeps the stale copy and the next protected
deploy writes drifted defaults into the protected worker.env/road-worker.env —
exactly the multi-source drift class #395 exists to remove.

This change makes the canonical module the single source of truth: the configure
step derives its water/road env-file defaults from `analytics_profiles` via a
direct import (worker directory resolved from the script's own path) and fails
closed with a `SystemExit` ERROR when the canonical module cannot be imported —
no hardcoded fallback values remain in the configure script.

## User scenarios

- US-1: A profile value changes in `worker/analytics_profiles.py`; the next
  protected configure run derives the new default for both water and road env
  files without any edit to the deploy-side script.
- US-2: The protected env files already carry machine/secret/operator overrides
  (e.g. SAMPLE_FPS); the configure run keeps those values and only fills keys
  without a valid override with the derived canonical defaults.
- US-3: The canonical module is missing or unreadable in the staged release; the
  configure step exits with a clear ERROR instead of writing stale defaults.

## Requirements

- R-1: `worker/analytics_profiles.py` gains one minimal string-serialization
  helper on `AnalyticsProfile` producing the env-file default mapping
  (ANALYTICS_PROFILE, CAMERA_ID, MODEL_NAME, YOLO_TRACKER, YOLO_IMAGE_SIZE,
  YOLO_CONFIDENCE, SAMPLE_FPS); existing module surface (`PROFILES`,
  `DEFAULT_PROFILE`, `get_profile`, `normalize_model_class`, `profile_defaults`)
  keeps its names and semantics.
- R-2: The configure step imports the canonical module via a `__file__`-relative
  sys.path entry (worker directory derived from `Path(__file__).resolve()`) and
  fails closed with a `SystemExit` ERROR when the import fails; the script must
  not contain hardcoded profile default values.
- R-3: Precedence semantics stay byte-identical to the base behaviour:
  machine/secret/operator overrides already present in the protected env files
  keep winning over derived defaults (water `_preserve_float` and road
  `_road_float` semantics unchanged, road still preferring the persisted road
  value); configure-local tuning knobs (YOLO_HALF, YOLO_CLASSES_FILTER,
  MOTION_GATE_MODE, LATEST_FRAME_BOUNDED) and the HD frame resolution logic stay
  configure-local.
- R-4: Serialized values are byte-identical to the base script: YOLO_CONFIDENCE
  as two-decimal strings ("0.10"/"0.15"), YOLO_IMAGE_SIZE "960", SAMPLE_FPS
  default "10"; canonical confidence literals remain 0.10/0.15; no change to VPS
  code, deploy workflows, the sync-bot, docs, env examples or any other contour.

## Acceptance criteria

- AC-001: The configure script exposes `derived_profile_defaults()` whose
  water/road mappings equal the independently re-derived canonical field
  mapping; the equality pins fail RED against the base script via
  `SEA_SPEED_395_CONFIGURE_PATH`.
- AC-002: Canonical confidence literals are pinned at 0.10/0.15 and serialize to
  "0.10"/"0.15"; image size serializes to "960"; sample-fps default serializes
  to "10".
- AC-003: An executed configure run proves an existing protected env value
  overrides the derived default (water SAMPLE_FPS=7.5 preserved; persisted road
  SAMPLE_FPS=12.5 preferred over water) while derived canonical defaults land
  where no override exists.
- AC-004: The configure script source contains no hardcoded profile default
  values and keeps the fail-closed `SystemExit` import path; all pre-existing
  analytics/deploy pins stay green.

## Runtime feedback

- RF-001: Operator actions expected: 0; derivation happens inside the existing
  deploy-authorized configure step.
- RF-002: On canonical-module import failure the configure step exits with an
  `ERROR canonical analytics profile module unavailable` line instead of writing
  drifted env values.

## NFR assessment

- NFR-001 | Area: maintainability | Target: non-secret profile values exist in exactly one place (worker/analytics_profiles.py); the configure step derives them and carries no copies | Validation: executed derivation-equality and structural no-hardcoded-value tests demonstrated RED against the base script and GREEN after the change | Evidence: ConfigureDerivesFromCanonicalProfilesTests | Status: PASS
- NFR-002 | Area: reliability | Target: a missing or unreadable canonical module fails the configure step closed instead of writing stale defaults | Validation: fail-closed SystemExit import path pinned; executed subprocess run proves the step still completes when the module is present | Evidence: test_configure_script_derives_and_fails_closed_without_hardcoded_values, test_existing_env_value_overrides_derived_default | Status: PASS
- NFR-003 | Area: security | Target: no secrets enter the canonical module and no new exposure is introduced; protected env modes (0600) and the private-ingress URL gates are untouched | Validation: executed mode-600 assertion in the precedence run; source review of the exact diff | Evidence: PR exact diff (worker/analytics_profiles.py, deploy/worker/ubuntu/configure-analytics-profiles.py, tests/test_analytics_profiles_configure_drift.py, SDD trio) | Status: PASS
- NFR-004 | Area: reversibility | Target: the change reverts cleanly without env-file schema or state migration; written env bytes are identical to the base script for the same inputs | Validation: serialization pins ("0.10"/"0.15"/"960"/"10") plus precedence run; diff scope review against the admitted scope | Evidence: test_confidence_literals_unchanged_and_two_decimal_serialized | Status: PASS
- NFR-005 | Area: operability | Target: no operator action and no workflow change; the derive step lives entirely inside the existing configure script invoked by the unchanged deploy-authorized flow | Validation: deploy-authorized call-order pins stay green unchanged | Evidence: tests.test_ubuntu_worker_deploy_authorized green | Status: PASS
