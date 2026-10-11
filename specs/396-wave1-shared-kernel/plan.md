# Plan: Shared kernel extraction — api/app/config.py + api/app/identity.py (Wave 1)

- Issue: #396
- Specification: specs/396-wave1-shared-kernel/spec.md

## Implementation approach

1. `api/app/config.py` (new) — byte-range extraction of main.py:35-111
   (constants) plus the import-time mkdir block (113-118) as module top-level
   statements, with a stdlib-only import header (`ipaddress`, `os`, `re`,
   `threading`, `pathlib.Path`) and a docstring recording the
   exactly-one-owner decision for the mkdir side effects and the
   single-canonical-module-instance rule. The extraction is performed by
   line-range copy from the base `main.py` (never retyped), so the constants
   are byte-identical to the originals.
2. `api/app/identity.py` (new) — byte-range extraction of main.py:124-214
   (`now_iso`, `deployed_source_commit`, `require_auth`,
   `require_operator_identity`, `worker_control_origin`, `call_worker_control`)
   and 1045-1049 (`analytics_identity`); imports `config` via the same dual
   idiom as `main.py`'s store import and `fastapi.HTTPException` module-level
   (the originals raised it directly).
3. `api/app/main.py` — delete the moved blocks; extend the existing dual
   import idiom (L25-32) to also import `config` and `identity` and to
   re-export every moved name through explicit name lists (no star imports),
   placed so `config` is imported before `app = FastAPI(...)` and the media
   mount.
4. Tests — update the four harnesses that pin moved functions/literals to a
   main→identity→config resolution order (loader fallback) and a combined
   source text for text markers (main.py + config.py + identity.py, existing
   files only, so the base tree still validates); add config/identity
   fixtures to the synthetic releases in `test_vps_deploy_transaction.py`.
5. `deploy/vps/deploy.sh` — add `CONFIG_TARGET`/`IDENTITY_TARGET`
   (`$(dirname "$API_TARGET")/config.py|identity.py`), extend
   `release_complete`, the download required list and the release install,
   and mirror the store.py soft pattern in `install_release` (stage `.next`
   when the release ships the module, promote before `main.py`, clean
   removal on a release that lacks it) and in `bootstrap_current_release`
   (capture live copies when present, keep rollback bootable).

## Architecture

Two new leaf modules under `api/app/`, deployed before `main.py`:

- `api/app/config.py` — stdlib-only constants leaf (no app-dir imports);
  single owner of the import-time directory creation side effects.
- `api/app/identity.py` — depends only on `config` (constants) and
  `fastapi.HTTPException`; holds the deployment-identity and trust
  primitives.
- `api/app/main.py` — unchanged logic; thin explicit re-exports keep the
  historical import surface (`main.API_TOKEN`, `main.require_auth`, ...)
  working for callers and AST harnesses.

Import-cycle rule: neither new module imports `main`; `identity` imports
`config` only. The dual try/except idiom is replicated exactly so both
modules resolve the same module objects in every load mode:

- package mode (`import api.app.main`): `from . import config` /
  `from .config import ...` everywhere → one `api.app.config` instance.
- direct-file mode (uvicorn app-dir, spec_from_file_location): relative
  imports raise ImportError → both `main` and `identity` anchor the app dir
  on `sys.path` and import `config`/`identity` absolutely → the already-
  loaded `config` is reused (sys.modules cache), never re-instantiated.

`config`/`identity` hold only constants and functions (no mutable cross-
module state except `CAMERA_PREVIEW_LOCK`, which stays a single object via
the same single-instance guarantee).

## Decisions

- mkdir side effects move INTO `config.py` module top (exactly-one-owner);
  `main.py` imports `config` first, so boot ordering and side-effect count
  are unchanged.
- `identity.py` imports `fastapi` module-level (same as `main.py` did for
  these functions) rather than lazily: import-safety under the
  roi-normalization mocks is identical because the mock installs a MagicMock
  for `fastapi` in `sys.modules` before `main.py` (and therefore
  `identity.py`) is imported.
- Exact-artifact manifest (`build_exact_artifacts.py` /
  `validate_exact_artifacts.py`) stays unchanged: `store.py` is not in the
  VPS required list either; release completeness is governed by deploy.sh
  (verified against `test_vps_deploy_transaction.py` synthetic releases).
- Test updates use fallback/combined-source readers instead of hard re-pins
  so the same test file remains valid against the base and head trees.
- Extraction done by line-range copy (scripted), not retyped, so moved
  code is byte-identical and secret-shaped env lines are never reproduced
  by hand.

## Affected contours

- VPS only (`api/**` + `deploy/vps/deploy.sh`): deploy envelope REQUIRED;
  deploy rides the merge via deploy-vps.yml (orchestrator DEPLOY-TRIGGER,
  полоса A). No Ubuntu worker, no edge, no frontend change.

## Validation

- Full suite `python3 -m unittest discover -s tests` green (baseline: 907
  tests / 4 skipped).
- `python3 scripts/ci/validate_repo.py` green.
- `bash -n deploy/vps/deploy.sh` clean.
- `ast.parse` smoke on both new modules; standalone import smoke for
  `config.py`.
- VPS deploy transaction suite (release shapes with the new modules)
  green.
- validate_sdd event JSON against base ae1070d and the head commit.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: OPS | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: deploy.sh extended in all four places (targets, release_complete, download required list, install) with staging+activation of config.py/identity.py BEFORE main.py mirroring the store.py pattern; bootstrap capture keeps rollback releases bootable; a missing module fails the release before any live mutation | Validation: deploy transaction suite + bash -n + release-shape fixtures | Residual risk: LOW | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: AST-harness suites pin moved literals; harnesses get a main→identity→config resolution order and combined-source text readers with fallback-to-main so assertions are re-pointed, never weakened | Validation: updated harness suites green on head; baseline suite run for comparison | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: single canonical import identity — main.py and identity.py use the identical dual try/except idiom; identity imports config (never main); sys.modules cache guarantees one instance per process; documented in module docstrings | Validation: standalone + mocked import smoke; suite green | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-004 | Category: OPS | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: import-time mkdir side effects keep exactly one owner (config.py module top); main.py imports config before app creation, so boot side effects are unchanged | Validation: suite green (roi-normalization mock covers Path.mkdir); deploy health gate unchanged | Residual risk: LOW | Owner: Worker | Status: MITIGATED
- RISK-005 | Category: SEC | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: trust primitives moved by byte-range copy (no retyping, no semantic drift); token-separation suite re-run; env reads stay in config.py only | Validation: tests/test_393_control_token_separation.py green; verbatim extraction review | Residual risk: LOW | Owner: Worker | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001, AC-002, AC-004, AC-006 | Level: unit | Priority: P1 | Evidence: python3 -m unittest discover -s tests (full suite green on head; baseline 907/4-skip)
- TEST-002 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: tests/test_vps_deploy_transaction.py (synthetic releases carry config/identity; store-less rollback shape unchanged)
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P1 | Evidence: bash -n deploy/vps/deploy.sh
- TEST-004 | Covers: AC-002 | Level: unit | Priority: P1 | Evidence: python3 scripts/ci/validate_repo.py
- TEST-005 | Covers: AC-005 | Level: unit | Priority: P2 | Evidence: ast.parse + standalone import smoke for api/app/config.py and api/app/identity.py; tests/test_roi_normalization.py (mocked import path)
- TEST-006 | Covers: AC-004 | Level: unit | Priority: P1 | Evidence: tests/test_api_contract.py, tests/test_393_control_token_separation.py, tests/test_analytics_profiles.py, tests/test_worker_operator_control.py (re-pinned harnesses)

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Runtime feedback

- RF-001: Deploy rides the merge (deploy-vps.yml, orchestrator-owned
  DEPLOY-TRIGGER); health gate = origin + public smoke as before; no new
  operator steps.
- RF-002: If activation health fails, deploy.sh rolls back to the previous
  release via install_release(previous) — for a pre-#396 previous release
  the new modules are removed from live (old main.py imports neither).

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: work order for #396 wave 1 (extraction-only scope); branch sdd/396-wave1-kernel from ae1070d
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged VPS state | Retry: NO | Rollback: NONE | Evidence: release_complete (deploy.sh:205) and download required list (deploy.sh:245) now also require api/app/config.py and api/app/identity.py; the gate exits before any mutation of the live tree
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: staged .next copies discarded; live API unchanged | Retry: NO | Rollback: install_release stages config.py/identity.py to .next and promotes via mv only after all copies stage successfully; config/identity mv precedes store.py and main.py mv (the new main imports all of them at boot) (deploy.sh:633-698) | Evidence: install_release soft pattern; test_vps_deploy_transaction behavioral suite (20 tests, write_release fixtures carry the new files)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: previous release still active | Retry: NO | Rollback: NONE | Evidence: restart_and_verify health gate (deploy.sh:808) unchanged by wave 1
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: NONE | Evidence: dual-write window semantics untouched; wave 1 moves no state-mutation code
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: staging dirs may remain on abrupt kill only | Retry: NO | Rollback: NONE | Evidence: deploy.sh staging layout semantics unchanged
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence partial | Retry: NO | Rollback: NONE | Evidence: DEPLOYMENT_ACCEPTED line from the autonomous chain at exact-green-head merge
- TX-008 | Stage: ROLLBACK | Mutation: NO | Failure disposition: FATAL | State after failure: NONE | Retry: NO | Rollback: rollback-exact.sh contour unchanged; activation is bound to the selected release content for config.py/identity.py exactly as for store.py — staged .next promoted only when the release ships the module, otherwise the live copy and any stale .next are removed so a pre-#396 rollback boots cleanly; bootstrap capture preserves live config.py/identity.py alongside the captured main.py (deploy.sh:496-508) | Evidence: deploy.sh:663-698 (activation), deploy.sh:496-508 (bootstrap capture) + test_vps_deploy_transaction rollback tests
