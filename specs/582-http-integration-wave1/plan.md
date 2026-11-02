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

## Validation

- Baseline on dc1e9f7: 1274 passed / 2 skipped / 357 subtests (pytest
  rendering, recorded at resume).
- Final tree, canonical gate: `python3 scripts/run_tests.py` → PASS 2/2 CI
  battery commands green (Python 3.14.4 cpython, deps: pyyaml==6.0.3).
- Final tree, fastapi present (`PYTHONPATH=/tmp/opencode/582/pylibs:`):
  `pytest tests/ -q` → 1289 passed / 2 skipped / 363 subtests / 0 failed
  (~84.5 s).
- Focused: new module 15 passed + 6 subtests (fastapi present); 15 skipped
  (fastapi absent); `tests/test_run_tests_script.py` 27 passed + 11 subtests.

## Runtime feedback

- Operator actions expected: 0. No runtime contour is mutated by this
  wave; the post-merge autonomous pipeline is observed as usual.
