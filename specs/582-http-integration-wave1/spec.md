# Spec: #582 wave 1 — real FastAPI HTTP integration tests for the API boundary

- Issue: #582
- Specification: specs/582-http-integration-wave1/spec.md
- Authorization: the #582 wave-1 scope (api/app/config.py env overrides +
  tests/test_api_http_integration.py + the guarded-optional pin in
  tests/test_run_tests_script.py + this trio) admitted by the delivery
  orchestrator; base dc1e9f7 (branch fix/582-api-http-integration-wave1).

## Product outcome

The API's HTTP boundary — bearer auth, edge identity, role gates, request
validation, persistence — is exercised by real HTTP integration tests:
`tests/test_api_http_integration.py` boots the real `api.app.main` FastAPI
application against a disposable temp data root and drives it through
starlette's TestClient (httpx ASGI transport), asserting status codes and
persisted side effects end-to-end. Today the closest coverage is the
roi-normalization harness, which execs main.py against MagicMock stand-ins
for fastapi/PIL/sqlite3 — real routing, real validation and real auth
semantics are never exercised over HTTP. The tests are guarded-optional
(the repo's established idiom, `tests/test_live_envelope_validators.py`):
CI has no fastapi and skips the module cleanly, while any environment with
fastapi installed runs the full suite. `api/app/config.py` gains two env
overrides (`SEA_SPEED_BASE_DIR`, `SEA_SPEED_DEPLOYED_COMMIT_FILE`) so the
real app can boot against a throwaway root; unset behavior is
byte-for-byte identical to the previous hardcoded defaults.

## User scenarios

- SC-1: a developer with fastapi available runs the battery — the new
  module executes 15 tests / 6 subtests against the real app: unauthenticated
  health, 403 on missing/wrong bearer, 500 fail-closed on unset token env
  (fresh subprocess), event ingestion round trip persisting to the temp data
  root, 400 on malformed metadata, 422 on missing snapshot, ROI
  defaults/admin-save round trip and <3-points 400, speed-config and
  speed-lines finite-number gates with persistence, admin-gated object
  soft-delete, worker-control fail-closed on unreachable origin and on
  untrusted identity.
- SC-2: CI (no fastapi installed) runs the same battery — the module's
  guarded-optional probe fails cleanly, the class skips, zero failures, and
  the import-hygiene scan classifies the guarded imports without complaint.
- SC-3: the one-process battery runs the new module before
  `tests/test_roi_normalization.py` — the class cleanup restores the
  process environment AND evicts the fastapi modules it cached, so the roi
  harness's absent-name mock condition still holds and the whole battery is
  green with fastapi present.
- SC-4: someone edits the new module's guarded import lines — the
  import-hygiene pin in `tests/test_run_tests_script.py` re-reds with the
  actual scanned set, keeping the guarded-optional surface a drift detector.

## Acceptance criteria

- AC-001: `tests/test_api_http_integration.py` (new) runs 15 tests / 6
  subtests against the real app over TestClient with `SEA_SPEED_BASE_DIR`
  pointed at a disposable temp root: health identity, bearer 403/500
  fail-closed paths, event ingestion round trip + 400/422 rejections, ROI
  round trip + 400, speed-config/speed-lines finite gates + persistence,
  admin-gated object soft-delete, worker-control fail-closed (unreachable
  origin 503, untrusted identity).
- AC-002: with fastapi absent the module skips cleanly (guarded-optional,
  same idiom as `tests/test_live_envelope_validators.py`); the canonical
  `scripts/run_tests.py` gate stays green.
- AC-003: `api/app/config.py` reads `SEA_SPEED_BASE_DIR` and
  `SEA_SPEED_DEPLOYED_COMMIT_FILE` with the previous hardcoded values as
  defaults; every derived path keeps deriving from `BASE_DIR`; unset
  behavior is byte-for-byte identical to pre-#582.
- AC-004: the one-process battery contract holds: the class restores every
  `MANAGED_ENV_NAMES` variable and evicts the `MANAGED_MODULE_NAMES` it
  cached (never preexisting ones) in class cleanup, so later test modules
  see the original environment and `sys.modules`.
- AC-005: the guarded-optional pin in `tests/test_run_tests_script.py`
  matches the actual scanned set (the new module's three guarded imports at
  their real line numbers plus the pre-existing
  `test_live_envelope_validators.py` entry); `run_tests.py` DECLARED_DEPS
  stays untouched (the scan gate accepts fastapi/httpx as guarded-optional;
  no test demands pins).
- AC-006: full battery green in both modes — canonical
  `python3 scripts/run_tests.py` (no fastapi) PASS, and with fastapi on the
  path 1293 passed / 2 skipped / 363 subtests / 0 failed on the rebased
  tree (main 349b39c baseline 1278 / 2 / 357 + exactly the new tests).

## Requirements

- R-1: `api/app/config.py` — `BASE_DIR` and `DEPLOYED_COMMIT_FILE` read
  `SEA_SPEED_BASE_DIR` / `SEA_SPEED_DEPLOYED_COMMIT_FILE` via
  `os.environ.get` with the previous hardcoded values as defaults (the
  established `SEA_SPEED_CAMERA_PREVIEW_CATALOG` precedent); no other
  config behavior changes.
- R-2: `tests/test_api_http_integration.py` (new, ~530 lines) — module-level
  guarded-optional probe for fastapi/httpx; class-scoped temp data root via
  `SEA_SPEED_BASE_DIR` with class cleanups restoring env and evicting
  cached fastapi modules; gitleaks-safe low-entropy fixture constants
  (repo precedent `edge-fixture-520` style); one fresh-subprocess probe for
  the unset-token 500 path.
- R-3: `tests/test_run_tests_script.py` — the guarded-optional pin updated
  to the actual scanned set (line numbers included); no assertion weakened.
- R-4: the SDD trio `specs/582-http-integration-wave1/{spec,plan,tasks}.md`
  is created; no other files change (`.github/**`, `contracts/**`,
  `tests/test_roi_normalization.py` and all other tests untouched).

## Runtime feedback

- RF-001: Operator actions expected: 0 — test-only plus a no-behavior-change
  config override. No deployment workflow, schema or stored-data change; the
  post-merge autonomous runtime pipeline evaluates the contour as usual and
  is observed, not dispatched, by this wave.
- RF-002: strictly additive — with no env set, `config.py` resolves the same
  paths as before; production behavior is unchanged. The new tests run only
  where fastapi is installed and always against a disposable temp root.

## NFR assessment

- NFR-001 | Area: test fidelity | Target: the HTTP boundary (auth, roles, validation, persistence) exercised through real FastAPI routing instead of mocks | Validation: 15 tests / 6 subtests green against the real app; 500/403/400/422/503 fail-closed paths asserted on real responses | Evidence: completion gate in tasks.md | Status: PASS
- NFR-002 | Area: CI parity | Target: zero CI impact — guarded-optional skip without fastapi, import-hygiene scan clean, canonical gate green | Validation: `python3 scripts/run_tests.py` PASS 2/2 on the final tree; skip path observed (15 skipped without fastapi) | Evidence: tasks.md Battery identity | Status: PASS
- NFR-003 | Area: process isolation | Target: zero cross-test pollution in the one-process battery — env and sys.modules restored after the class | Validation: combined and full-battery runs with fastapi present are green (the roi harness's absent-name mock condition holds); env/sys.modules restore covered by the class cleanups | Evidence: plan.md Correct-course check; tasks.md Battery identity | Status: PASS
- NFR-004 | Area: performance | Target: battery delta bounded (~+1.5 s for the new module; full battery ~85 s with fastapi, unchanged canonical gate runtime) | Validation: observed full-battery timings on the final tree | Evidence: plan.md Validation section | Status: PASS
