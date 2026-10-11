# Spec: Shared kernel extraction — api/app/config.py + api/app/identity.py (Wave 1)

- Issue: #396
- Specification: specs/396-wave1-shared-kernel/spec.md

## Product outcome

The Sea Speed API monolith `api/app/main.py` (~2600 lines, one module owning
paths, env-derived limits, identity primitives and every route) is the only
deployment unit besides `store.py`. Any consumer (worker-side tooling, future
API sub-modules, tests) that needs a path constant or the auth/identity
primitives must import the whole FastAPI application. Wave 1 carves out the
dependency-free kernel with **zero behavior change**:

1. `api/app/config.py` (new, standard library only) — the paths/env/constants
   block (base/data/media dirs, DB files, feed/store limits, operator
   env-derived tokens and timeouts, schema strings, validation regexes) plus
   the import-time data-directory creation side effects, which move WITH an
   exactly-one-owner decision: the `mkdir` calls run at `config.py` module
   top level, and `main.py` imports `config` first (before `app = FastAPI()`
   and before any path use), so boot behavior and ordering are unchanged.
2. `api/app/identity.py` (new) — the deployment identity and trust
   primitives: `now_iso`, `deployed_source_commit`, `require_auth`,
   `require_operator_identity`, `analytics_identity`, `worker_control_origin`
   and `call_worker_control`. These functions are moved verbatim; the module
   imports `config` (constants) and `fastapi.HTTPException` exactly where the
   originals used them.

`api/app/main.py` keeps every route, every remaining function and the
FastAPI app; the moved names remain importable from `main` via thin explicit
re-exports (`from .config import BASE_DIR, ...` / `from .identity import
now_iso, ...` under the same dual package/direct-file import idiom the store
seam already uses), so all existing callers — AST-harness suites that exec
functions by name, text-pinning suites, and the deployed module itself —
see identical behavior.

No API surface change: routes, response shapes, schemas, defaults, limits
and failure modes are byte-for-byte the same semantics.

## User scenarios

- US-1: An operator deploys this release to the VPS; `deploy.sh` stages
  `config.py` and `identity.py` into the release and activates them
  **before** `main.py` (mirroring the `store.py`-before-`main` pattern), so
  the first boot of the new `main.py` finds its imports and the health gate
  passes exactly as before.
- US-2: A rollback to a pre-#396 release removes the live `config.py` /
  `identity.py` cleanly (the old `main.py` does not import them); a staged
  `.next` left by an interrupted install is never promoted; the bootstrap
  capture keeps live `config.py`/`identity.py` next to the captured
  `main.py` so the rollback release stays bootable on its own.
- US-3: The AST-harness suites continue to exec the moved primitives
  (`analytics_identity`, `require_auth`, `worker_control_origin`,
  `call_worker_control`) and pin their literal text — the harnesses now
  resolve those functions/markers from `identity.py`/`config.py` with a
  fallback to `main.py`, without weakening any assertion.
- US-4: A test loads `main.py` standalone (spec_from_file_location with
  mocked `fastapi`/`Path.mkdir`/`sqlite3`); `config.py` (stdlib-only) and
  `identity.py` (fastapi import where the original had it) import safely
  under the same mocks, and no second module instance of `config` is ever
  created inside one process (both `main` and `identity` resolve `config`
  through the same try/except idiom, so the import identity is canonical).

## Scope

- `api/app/config.py` (new): paths/env/constants block + import-time mkdir
  side effects (single owner).
- `api/app/identity.py` (new): `now_iso`, `deployed_source_commit`,
  `require_auth`, `require_operator_identity`, `analytics_identity`,
  `worker_control_origin`, `call_worker_control` (moved verbatim).
- `api/app/main.py`: remove the moved blocks; add thin explicit re-export
  imports (dual idiom, explicit name lists, no star imports). Routes and all
  other logic untouched this wave.
- `deploy/vps/deploy.sh`: `CONFIG_TARGET`/`IDENTITY_TARGET`; release
  completeness; download required list; release install; activation staged
  and promoted before `main.py` with the store.py soft pattern (clean removal
  on pre-#396 rollback); bootstrap capture of the live modules.
- Tests: harness updates in `tests/test_api_contract.py`,
  `tests/test_393_control_token_separation.py`, `tests/test_analytics_profiles.py`,
  `tests/test_worker_operator_control.py`; synthetic-release fixtures in
  `tests/test_vps_deploy_transaction.py`.
- SDD: this trio.

Out of scope: routes/logic extraction (Wave 2+), `worker/`, `frontend/`,
`.github/`, exact-artifact manifest changes (`store.py` is likewise not in
the exact-artifact required list — release manifest completeness is governed
by `deploy/vps/deploy.sh`), any behavior/limit/schema change.

## Requirements

- R-1: `api/app/config.py` owns the constants block (main.py:35-111 at
  base) verbatim — `BASE_DIR`/`DATA_DIR`/media dirs/DB files/
  `EVENTS_FEED_LIMIT`/`CROSSINGS_STORE_LIMIT`/`ANALYTICS_IDENTITIES`/
  camera-preview env knobs/`API_TOKEN`/worker-control envs/schema strings/
  retention sets/regexes/`CAMERA_PREVIEW_RFC1918`/`CAMERA_PREVIEW_LOCK` —
  is standard-library-only, and runs the data-directory `mkdir` side effects
  (main.py:113-118 at base) exactly once at module import (single owner;
  `main.py` imports `config` before any path use).
- R-2: `api/app/identity.py` owns `now_iso`, `deployed_source_commit`,
  `require_auth`, `require_operator_identity`, `analytics_identity`,
  `worker_control_origin`, `call_worker_control` (main.py:124-214 and
  1045-1049 at base) moved verbatim; it imports the needed constants from
  `config` and `fastapi.HTTPException` module-level exactly where the
  originals used it.
- R-3: `api/app/main.py` re-exports every moved name explicitly (no star
  imports) under the same dual idiom as the store import
  (try relative `from . import config, identity` + explicit name lists /
  except ImportError → sys.path anchor + absolute import), keeping a single
  canonical module instance per process for `config`/`identity` (documented
  in the module docstrings).
- R-4: `deploy/vps/deploy.sh` — `CONFIG_TARGET`/`IDENTITY_TARGET` defined
  next to `API_TARGET`; both files join `release_complete` and the download
  required list and are installed into the release; activation stages and
  promotes them **before** `main.py` bound to the selected release's content
  (staged `.next` promoted only when the release ships the file; otherwise
  the live copy and stale `.next` are removed — the store.py soft pattern);
  the bootstrap capture keeps a live `config.py`/`identity.py` with the
  captured `main.py` when present.
- R-5: The AST/text harnesses that pin moved functions or literals
  (`tests/test_api_contract.py`, `tests/test_393_control_token_separation.py`,
  `tests/test_analytics_profiles.py`, `tests/test_worker_operator_control.py`)
  resolve them from the new modules with fallback to `main.py` so the pins
  hold on both the base and head trees; no assertion is weakened.
  `tests/test_vps_deploy_transaction.py` synthetic releases carry
  `config.py`/`identity.py` so release completeness stays satisfiable.

## Acceptance criteria

- AC-001: The full unittest suite is green on head (no skipped-or-failing
  regression versus the 907-test/4-skip baseline).
- AC-002: `scripts/ci/validate_repo.py` passes on head (new `api/app/*.py`
  files admitted; `api/app/main.py` still required and present).
- AC-003: `deploy/vps/deploy.sh` is extended in all four places (targets,
  `release_complete`, download required list, release install) plus
  activation-before-`main` and bootstrap capture; `bash -n` passes and the
  VPS deploy transaction suite (synthetic releases with/without the new
  modules) stays green.
- AC-004: The moved primitives remain reachable through `main` and are
  behavior-identical: harness-executed `analytics_identity`,
  `require_auth`, `worker_control_origin`, `call_worker_control` tests
  pass against the extracted sources with the same injected namespaces.
- AC-005: `config.py` and `identity.py` are import-safe standalone and
  under the roi-normalization mock context (stdlib-only `config`; `identity`
  imports fastapi exactly where the originals did); `python3 -c
  "import ast; ast.parse(...)"` smoke passes for both new modules.
- AC-006: No behavior change: all route decorators, response shapes,
  defaults and limits stay in `main.py` untouched; the only main.py edits
  are the removal of the moved blocks and the added re-export imports.

## Runtime feedback

- RF-001: Operator actions expected: 1 — the VPS deploy of this wave rides
  the merge (DEPLOY-TRIGGER, полоса A); deploy.sh stages `config.py`/
  `identity.py` before `main.py`, restarts and runs the origin/public health
  gate; rollback removes both modules when returning to a pre-#396 release.
- RF-002: Failure evidence: a missing `config.py`/`identity.py` in a release
  fails in `release_complete`/download BEFORE any live source mutation; a
  failed activation health gate rolls the full source set back via the
  existing install_release(rollback) path.

## NFR assessment

- NFR-001 | Area: reliability | Target: zero behavior change on the VPS — boot ordering identical (config import first, mkdir exactly once, app created after), all 56 routes and response shapes unchanged | Validation: full suite green; route/logic diff of main.py limited to moved blocks + re-export imports; deploy transaction suite green | Evidence: tests/test_api_contract.py, tests/test_vps_deploy_transaction.py | Status: PASS
- NFR-002 | Area: compatibility | Target: AST-harness and text-pinning suites keep working without weakened assertions; moved literals re-pinned to the owning module with fallback-to-main so the base tree stays clean | Validation: updated harness suites resolve moved functions/markers from config.py/identity.py; suite green on head; base-run spot check for fallback logic | Evidence: tests/test_api_contract.py, tests/test_393_control_token_separation.py, tests/test_analytics_profiles.py, tests/test_worker_operator_control.py | Status: PASS
- NFR-003 | Area: deployability/rollback | Target: a release missing config.py/identity.py can never reach activation (fails in release completeness/download), and a rollback to a pre-#396 release removes both modules while keeping the old main bootable; bootstrap capture stays bootable | Validation: deploy.sh four-place extension + soft activation pattern; synthetic-release tests (store/config/identity present and absent shapes) | Evidence: tests/test_vps_deploy_transaction.py | Status: PASS
- NFR-004 | Area: security | Target: trust primitives (require_auth, require_operator_identity, worker-control origin allowlist) move verbatim with no semantic drift; identity.py holds the auth seams; single canonical module identity per process avoids split-brain globals (e.g. WORKER_CONTROL_TIMEOUT_SEC, CAMERA_PREVIEW_LOCK) | Validation: verbatim byte-range extraction of the function bodies; import-idiom symmetry between main.py and identity.py documented and reviewed; token-separation suite green | Evidence: tests/test_393_control_token_separation.py, tests/test_sea_speed_auth_v1.py | Status: PASS
- NFR-005 | Area: maintainability | Target: config.py is standard-library-only with a documented exactly-one-owner mkdir; identity.py depends only on config + fastapi; no module imports main (import-cycle rule) | Validation: module source review; standalone-import smoke; ast.parse smoke | Evidence: api/app/config.py, api/app/identity.py | Status: PASS

## Deviations from the work order

- None material. The work order's "decide" item for the exact-artifact
  manifest is resolved by the store.py precedent: `config.py`/`identity.py`
  are NOT added to `build_exact_artifacts.py`/`validate_exact_artifacts.py`;
  release manifest completeness remains governed by `deploy/vps/deploy.sh`
  (verified against `tests/test_vps_deploy_transaction.py` pins).
- Baseline suite observed at 907 tests (4 skipped), not the 943 quoted in
  the work order; the acceptance comparison uses the observed baseline.
