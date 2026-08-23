# Implementation Plan: Unified objects registry

- Feature: 037-unified-objects-registry
- Specification: specs/037-unified-objects-registry/spec.md
- Issue: #259
- Status: Source implementation

## Architecture

- API (`api/app/main.py`): new pure-ish function `persist_passage_object(passage)`
  next to `persist_object_event`; uses the same `open_objects_db` connection
  pattern and SQLite `INSERT ... ON CONFLICT(object_id) DO UPDATE` for
  source-derived fields only. Called from `post_cam1_passage` after successful
  `upsert_water_passage`, and from `import_existing_passages()` at startup.
- Frontend (`frontend/sea-speed/objects/index.html`): enable `domainInput`,
  add change handler that swaps the active scope in place (header, filters,
  label, title, URL query, pagination reset, reload). Referrer/`?scope=`
  pre-selection logic unchanged. Nav collapses two registry links into one.

## Decisions

| ID | Decision | Rationale | Alternatives considered |
| --- | --- | --- | --- |
| D1 | Mirror in API handler rather than worker | single write path, works for any passage producer, no worker redeploy | worker posts twice (rejected: duplicates transport concerns) |
| D2 | ON CONFLICT update of source fields only | keeps operator edits authoritative (R3) | INSERT OR IGNORE (stale speed), DELETE+INSERT (loses operator fields) |
| D3 | Stable id `passage-<passage_id>` | collision-free with event ids and legacy ids | raw passage_id (risk of collision) |
| D4 | Startup backfill via SELECT over passages DB | makes existing history visible without manual scripts | skip backfill (registry stays empty for old data) |
| D5 | Domain switch client-side only | registry already scopes queries by domain; no API change needed | separate routes per domain (recreates two-contour problem) |

## Affected contours

VPS only: `api/**`, `frontend/**`. Ubuntu Worker/relay: NOT REQUIRED (no
worker changes; `/api/cam1/passages` contract unchanged).

## Validation

- New unit tests in `tests/test_unified_registry.py` covering AC-001..AC-005,
  AC-007 (frontend pre-selection asserted via static HTML/JS contract checks),
  mirror-failure resilience (NFR-037-002).
- Existing suites must remain green (full unittest discovery).
- Repository validators: validate_change_contract.py, validate_sdd.py,
  validate_repo.py, validate_contracts.py; quality validators;
  build_exact_artifacts.py.

## Risk profile

- Risk profile: REQUIRED

| ID | Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- | --- |
| RISK-037-001 | Mirror write slows passage POST under lock contention | Low | Medium | single short statement on existing connection pattern; timeout unchanged; NFR-037-001 test |
| RISK-037-002 | Mirror error masks passage success | Low | Medium | mirror wrapped in try/except with stderr log; NFR-037-002 test |
| RISK-037-003 | Backfill floods registry pruning on first deploy | Low | Low | backfill reuses prune_objects_registry; retention limit enforced identically |
| RISK-037-004 | Frontend regression breaks scope pre-selection | Medium | Low | static contract tests assert referrer logic and enabled selector |

## Test design

Risk-based selection: write-path correctness (RISK-001/002) -> unit tests for
idempotency, field refresh, operator-field preservation, failure isolation;
data growth (RISK-003) -> prune interaction test; UX regression (RISK-004) ->
static frontend contract assertions. Exact-artifact E2E covered by CI domain 3;
runtime acceptance by post-deploy verification (AC-011).

## Correct-course check

Trigger: PRODUCTION_LEARNING
Check performed after Task Intake found the water pipeline posts passages, not
analytics events; original assumption ("events endpoint not called") corrected
to "passages path bypasses persist_object_event". Scope adjusted to mirror at
the passage boundary. No protected-boundary impact.

## Runtime feedback

To be recorded after VPS deployment acceptance.

## Deployment transaction audit

Required (API write-path + production deployment follows merge).

| ID | Stage | Mutation | Failure disposition | State after failure | Retry | Rollback | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TX-037-001 | ADMISSION | none | policy deny -> no transport | unchanged | n/a | n/a | workflow run log |
| TX-037-002 | PRE-MUTATION | none | source protection / Quality mismatch aborts | unchanged | after fix | n/a | verify_source_protection output |
| TX-037-003 | MUTATION | VPS service restart with new api/frontend | deploy script non-zero exit | previous release still running or restarted service flagged | rerun workflow | rollback target from manifest | deployment-manifest-vps.json |
| TX-037-004 | VERIFICATION | none | health/smoke fail marks runtime_verified=false | service up, unverified | rerun | rollback | manifest checks array |
| TX-037-005 | STATE-COMMIT | manifest committed as artifact | artifact upload failure | mutation done, evidence missing | rerun evidence stage | n/a | exact-artifacts.json |
| TX-037-006 | HOUSEKEEPING | prune old media/tmp | non-fatal logged | functional | opportunistic | n/a | deploy logs |
| TX-037-007 | EVIDENCE | typed execution audit written | audit write failure blocks completion claim | verified but unaudited | rerun | n/a | sea_speed_production_execution_audit_v1 |
| TX-037-008 | ROLLBACK | revert to prior release target | rollback failure escalates to BLOCKED | degraded | manual decision | itself | rollbackTarget hash |
