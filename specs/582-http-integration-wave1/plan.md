# Plan — Issue #582 wave 1: real FastAPI HTTP integration tests

- Issue: #582
- Spec: specs/582-http-integration-wave1/spec.md
- Base: dc1e9f7 (branch fix/582-api-http-integration-wave1)

## Architecture

- New test module `tests/test_api_http_integration.py` boots the real
  `api.app.main` in-process. `setUpClass` points `SEA_SPEED_BASE_DIR` at a
  disposable temp root (config derives every data/media path from it and
  performs its import-time mkdirs there), sets the auth/edge/worker-control
  fixture env values, and registers class cleanups that restore the exact
  prior environment. Tests drive `TestClient(app)` (real FastAPI routing,
  httpx ASGI transport) and assert status codes plus persisted side effects
  in the temp data root (state.sqlite3, objects.sqlite3, JSON config files).
- The unset-token 500 path runs in a fresh subprocess (cwd = repo root,
  `SEA_SPEED_API_TOKEN` removed) so the module-level token read is exercised
  honestly instead of via a second in-process app import.
- `api/app/config.py` gains the two env overrides; the module-level mkdirs
  and every derived path keep their existing semantics, so the override is
  the only change.
- Guarded-optional idiom (repo precedent `tests/test_live_envelope_validators.py`):
  the module-level try-import decides `HTTP_TESTS_ENABLED`; CI (no fastapi)
  skips the class, dev environments with fastapi run it.

## Decisions

- D-1: guarded-optional, not a hard dependency. CI's battery is
  stdlib-only apart from `pyyaml==6.0.3`; adding fastapi to CI deps is a
  separate decision (later #582 waves). The tests run wherever fastapi is
  present and skip cleanly where it is not — the same idiom the repo already
  pins for `test_live_envelope_validators.py`.
- D-2: boot the real app through env overrides instead of mocks or a test
  double. `SEA_SPEED_BASE_DIR` redirects the whole derived tree (the
  import-time mkdirs land in the temp root), `SEA_SPEED_DEPLOYED_COMMIT_FILE`
  lets the health endpoint's source-commit probe be deterministic. Unset
  behavior is byte-for-byte identical to the hardcoded defaults.
- D-3: one-process battery contract. The class restores every env name it
  touched (pre-existing pattern) AND evicts the fastapi modules it cached
  (`MANAGED_MODULE_NAMES`, evicting only non-preexisting names). Root cause
  that forced D-3: `tests/test_roi_normalization.py::_import_app` stubs
  `fastapi`/`fastapi.staticfiles`/`fastapi.responses` only while they are
  ABSENT from `sys.modules`; the new module's module-level real import
  cached them, the harness silently ran against real starlette
  `StaticFiles`, and three roi tests failed with
  `RuntimeError: Directory '/opt/sea-speed-api/media' does not exist`.
  Containment lives in the polluter (this module's class cleanup); the roi
  harness is untouched.
- D-4: the import-hygiene pin in `tests/test_run_tests_script.py`
  (`test_guarded_optional_probe_is_the_fastapi_stub_fallback`) asserts the
  guarded set exactly and is a designed drift detector; it was updated to
  the actual scanned set — `("test_api_http_integration.py", 83, "fastapi")`,
  `(..., 84, "fastapi")`, `(..., 86, "httpx")`,
  `("test_live_envelope_validators.py", 61, "fastapi")` — after the
  containment and the review fixes (docstring truth-up, containment-boundary
  comment) shifted the import lines. `run_tests.py` DECLARED_DEPS is
  untouched: the scan classifies fastapi/httpx as guarded-optional and no
  test demands pins (the owner delegated this decision to the scan test).
- D-5: worker-control tests use a loopback URL (`http://127.0.0.1:19001`)
  that the app's own `worker_control_origin` guard rejects before any
  connection attempt — deterministic fail-closed, zero network.

## Affected contours

- `tests/**`: new module + pin update. `api/app/config.py`: two env
  overrides (no behavior change when unset). `specs/**`: this trio.
- No deployment/release/workflow change → no Deployment Transaction Audit
  (per the #577 precedent for api/app changes that are not deployment
  changes). The post-merge autonomous runtime pipeline evaluates the push to
  main as usual and is observed, not dispatched, by this wave.
- VPS contour ships `config.py`; with no env set the resolved paths are
  byte-identical to the previous hardcoded values.

## Risk profile

- Risk profile: NOT REQUIRED

- R-1 (highest): one-process battery pollution — env vars and cached
  fastapi modules leaking into later test modules. Mitigation: class
  cleanups restore env (pre-existing pattern) and evict cached modules
  (this wave); verified by the combined run and the full battery with
  fastapi present.
- R-2: the guarded-optional pin is line-number-sensitive; any edit to the
  import block re-reds it by design. Mitigation: pin updated from scanner
  output, never guessed.
- R-3: config.py is production code — a wrong default would break the VPS.
  Mitigation: defaults are the previous literals verbatim; unset-behavior
  equivalence is asserted by the canonical battery (which runs without the
  env set) and by the full CI battery on the merge head.

## Test design

- TEST-001 | Covers: AC-001 | Level: integration | Priority: P0 | Evidence: focused run — new module 15 passed + 6 subtests with fastapi present (orchestrator-observed); full-battery delta is exactly the new module
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: canonical gate `python3 scripts/run_tests.py` PASS 2/2 without fastapi; skip path observed (15 skipped without fastapi)
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P0 | Evidence: canonical battery (env unset) green on the final tree — unset behavior byte-identical to pre-#582
- TEST-004 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: combined run and full battery with fastapi present green after the containment (CC-1)
- TEST-005 | Covers: AC-005 | Level: unit | Priority: P1 | Evidence: `tests/test_run_tests_script.py` 27 passed + 11 subtests; pin = scanner output (83/84/86 + live_envelope 61); RED captured before the fix
- TEST-006 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: both battery modes green on the final tree (canonical PASS 2/2; fastapi present 1293 passed / 2 skipped / 363 subtests / 0 failed)

- 15 tests / 6 subtests, one class, one temp data root per class run:
  health identity (unauthenticated), bearer boundary (missing 403, wrong
  403, correct passes), unset-token 500 in a fresh subprocess, event
  ingestion round trip with persisted feed row + media file + receipt,
  malformed metadata 400, missing snapshot 422, ROI GET defaults → admin
  POST round trip → persistence, ROI <3 points 400, speed-config and
  speed-lines finite-number gates (NaN/Inf 400, negative/<=0 400) with
  persistence, object soft-delete admin gate + 404 after delete,
  worker-control unreachable-origin 503 and untrusted-identity rejection.
- Risk-based emphasis: every fail-closed path the production role gates
  introduced (#530) is asserted through the real HTTP boundary, because
  those are the paths the 403 incident (#590) showed we had never exercised
  end-to-end.

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

In-wave course corrections (no formal correct-course trigger; scope,
authorization and SDD structure unchanged):

- CC-1: the first full battery with fastapi present failed 3 roi tests
  (diagnosed above, R-1). Correct-course: containment moved into the new
  module (snapshot before the guarded import, eviction of non-preexisting
  names in the class cleanup) instead of touching the roi harness; the pin
  was re-pointed at the shifted line numbers. Re-verified: combined run
  green, full battery 1289 passed / 2 skipped / 363 subtests / 0 failed.
- CC-2: the guarded-optional pin RED discovered at resume (the scan counts
  the new module's guarded imports) was fixed as the first code order, RED
  output captured before the fix.
- CC-3: independent peer review (adversarial, re-derived from the repo)
  returned no blockers: F-1 — the module docstring falsely claimed the
  runner declares fastapi/httpx pins (fixed: docstring now states the
  runner does not install them and only classifies the guarded imports);
  F-2 — the containment boundary (transitive modules starlette/pydantic/
  httpx stay cached; no harness stubs those names, so eviction stays
  shallow by design) is now documented in the module comment; F-3 — the
  reviewer could not execute tests in its sandbox, closed by the
  orchestrator running both battery modes itself and observing the output.

## Deployment transaction audit

This audit models the autonomous post-merge VPS rollout of the additive
config env overrides; it does not redeploy Ubuntu or Windows and expects
zero operator actions.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: main remains on the previous accepted release; the wave is not admitted | Retry: correct exact SHA/quality/authorization evidence then re-enter the PR → exact-green-head merge path | Rollback: NOT REQUIRED before mutation | Evidence: exact merged main SHA, green exact-head CI on that SHA, owner authorization `commit approved` (2026-11-02)
- TX-002 | Stage: PRE-MUTATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate release may be staged while the current VPS release remains active | Retry: verify staged exact release and current/previous identities then retry | Rollback: NOT REQUIRED while the active release is unchanged | Evidence: exact VPS artifact/release manifest (sea_speed_release_manifest_v3) and current/previous release markers
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate VPS release may be active but is not accepted until verification succeeds | Retry: only after the existing deploy transaction restores or proves a coherent current release | Rollback: existing VPS deploy rollback restores the previous exact release | Evidence: autonomous deploy-runtime workflow activation logs on the merged main SHA
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: candidate is not accepted | Retry: resolve health/smoke failure after the actual current release is known | Rollback: automatic previous-release verification through the accepted loopback origin and protected smoke | Evidence: origin health, smoke, exact API release identity
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: deployment evidence is incomplete and completion is forbidden | Retry: verify actual runtime before persisting evidence | Rollback: previous exact VPS release remains the declared rollback target | Evidence: current/previous markers plus runtime-verified deployment manifest
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime remains valid while stale release cleanup may remain pending | Retry: clean stale non-current/non-previous releases independently | Rollback: NOT REQUIRED solely for stale cleanup failure | Evidence: warning-only pruning behavior already regression-protected
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed runtime may be healthy but wave acceptance evidence remains incomplete | Retry: recollect evidence without redeployment when the exact runtime identity is unchanged | Rollback: decide from actual API/runtime behavior, not evidence upload alone | Evidence: deployment manifest plus the autonomous pipeline run evidence on the merged main SHA
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if the previous exact release cannot be restored/verified, stop automated mutation and recover actual VPS state | Retry: read current/previous/runtime evidence before any new mutation | Rollback: no guessed secondary target; use the protected previous exact VPS release | Evidence: existing VPS rollback logs and verified origin/public health

## Validation

- Baseline on dc1e9f7: 1274 passed / 2 skipped / 357 subtests (pytest
  rendering, recorded at resume).
- Wave tree on dc1e9f7 (pre-rebase), fastapi present: 1289 passed /
  2 skipped / 363 subtests / 0 failed.
- Final tree (rebased onto main 349b39c), canonical gate:
  `python3 scripts/run_tests.py` → PASS 2/2 CI battery commands green
  (Python 3.14.4 cpython, deps: pyyaml==6.0.3).
- Final tree (rebased onto main 349b39c), fastapi present
  (`PYTHONPATH=/tmp/opencode/582/pylibs:.`): `pytest tests/ -q` →
  1293 passed / 2 skipped / 363 subtests / 0 failed (~84.5 s; main
  baseline 1278/2/357 + exactly the new module).
- Focused: new module 15 passed + 6 subtests (fastapi present); 15 skipped
  (fastapi absent); `tests/test_run_tests_script.py` 27 passed + 11 subtests.

## Runtime feedback

- Operator actions expected: 0. No runtime contour is mutated by this
  wave; the post-merge autonomous pipeline is observed as usual.
