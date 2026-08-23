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

- RISK-037-001 | Category: PERF | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: single short ON CONFLICT statement on the existing connection pattern; no new polling or locks held beyond one write | Validation: unit tests exercise repeated mirroring; full suite timing unchanged | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-037-002 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: mirror wrapped in try/except with stderr log so passage POST contract never fails because of mirroring | Validation: dedicated failure-isolation unit test | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-037-003 | Category: DATA | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: startup backfill reuses prune_objects_registry and stable ids; retention limit enforced identically for mirrored rows | Validation: backfill idempotency unit test | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-037-004 | Category: OPS | Probability: 3 | Impact: 2 | Score: 6 | Mitigation: static frontend contract tests assert enabled selector, switch handler and referrer pre-selection before merge | Validation: tests/test_unified_registry.py::RegistryPageContractTests + updated test_frontend_contract | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED

## Test design

- TEST-037-001 | Covers: AC-001, AC-002, AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_unified_registry.py::PassageMirrorTests (mapping, refresh without duplicates, operator-field preservation)
- TEST-037-002 | Covers: AC-004, AC-005 | Level: unit | Priority: P0 | Evidence: tests/test_unified_registry.py backfill idempotency and domain-filter tests
- TEST-037-003 | Covers: AC-006, AC-007, AC-008 | Level: unit | Priority: P1 | Evidence: tests/test_unified_registry.py::RegistryPageContractTests static contracts plus updated tests/test_frontend_contract.py
- TEST-037-004 | Covers: AC-009, AC-010 | Level: integration | Priority: P0 | Evidence: local unittest discovery run and required CI checks on exact PR head
- TEST-037-005 | Covers: AC-011 | Level: runtime-manual | Priority: P1 | Evidence: post-deploy verification recorded in Issue #259

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: Task Intake corrected root cause from "events endpoint not called" to "water pipeline posts passages which bypass persist_object_event"; Issue #259 scope already reflects the corrected outcome
- Specification impact: spec.md requirements R1-R5 target the passage boundary instead of the analytics events path
- Plan impact: plan decisions D1-D4 record mirroring at the passage upsert boundary with ON CONFLICT refresh
- Tasks impact: tasks.md traceability maps AC-001..AC-012 to the passage-mirror implementation
- Authorization impact: NONE - same approved six-field scope, no protected-boundary change
- Follow-up: verify mirrored water rows in production during post-deploy acceptance (AC-011) and record runtime feedback in spec.md

## Runtime feedback

To be recorded after VPS deployment acceptance.

## Deployment transaction audit

Required: API write-path change merged to main followed by autonomous VPS deployment.

- Adjacent-stage review: COMPLETE
- Production-learning root cause: water pipeline posts passages to /api/cam1/passages whose handler bypassed persist_object_event, so water rows never reached the objects registry while road events did
- Production-learning adjacent-stage findings: MUTATION and VERIFICATION stages unaffected (no deploy logic change); STATE-COMMIT/EVIDENCE stages gain mirrored-row evidence via existing registry queries; ROLLBACK unchanged because mirror is additive and reversible by revert

- TX-037-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport, previous release continues serving | Retry: after policy/state correction via workflow rerun | Rollback: NOT REQUIRED - no mutation attempted | Evidence: deploy-runtime-autonomous workflow run log with policy decision id
- TX-037-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: source protection or Quality mismatch aborts before transport | Retry: after remediation of protection/Quality state | Rollback: NOT REQUIRED - no mutation attempted | Evidence: verify_source_protection.py output in protected workflow log
- TX-037-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous release keeps running when health checks gate service switch; otherwise restarted service flagged unverified | Retry: rerun deploy-vps.yml workflow | Rollback: redeploy rollbackTarget recorded by deployment manifest | Evidence: deployment-manifest-vps.json
- TX-037-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: service up but runtime_verified=false blocks completion claims | Retry: rerun verification stage via workflow rerun | Rollback: rollback target from manifest if verification cannot pass | Evidence: manifest checks array entries
- TX-037-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: mutation done but evidence artifact missing; completion not claimed | Retry: rerun evidence upload stage | Rollback: NOT REQUIRED - state commit is additive evidence | Evidence: exact-artifacts.json artifact on workflow run
- TX-037-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: old media/tmp may remain; functionality unaffected | Retry: opportunistic on next deployment | Rollback: NOT REQUIRED - cleanup only | Evidence: deploy logs
- TX-037-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: verified deployment without typed audit must not be claimed complete | Retry: rerun audit emission stage | Rollback: NOT REQUIRED - evidence is additive | Evidence: sea_speed_production_execution_audit_v1 bound to policy decision
- TX-037-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback escalates to BLOCKED with human decision required | Retry: manual decision then redeploy known-good target | Rollback: itself is the rollback path | Evidence: rollbackTarget hash in deployment manifest

