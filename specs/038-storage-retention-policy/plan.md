# Implementation Plan: Storage retention policy

- Feature: 038-storage-retention-policy
- Specification: specs/038-storage-retention-policy/spec.md
- Issue: #261
- Status: Source implementation

## Architecture

- `prune_objects_registry` becomes per-domain: one SQL statement using
  `ROW_NUMBER() OVER (PARTITION BY domain ORDER BY detected_at DESC, object_id DESC)`,
  keeping rows with rn <= OBJECTS_RETENTION_LIMIT. Returns evicted snapshot URLs.
- New module-level media sweep helpers: `sweep_events_media(force=False)` with
  in-process `_last_events_sweep_at` throttle (3600s); deletes only safe `.jpg`
  names under EVENTS_MEDIA_DIR that are unreferenced and older than 24h.
- Passage mirror sync: after `prune_water_passages` returns pruned passage ids,
  the upsert/delete flows delete matching `passage-<id>` objects rows; startup
  reconciliation (`reconcile_passage_mirrors`) removes mirrors whose passage is gone.

## Decisions

| ID | Decision | Rationale | Alternatives considered |
| --- | --- | --- | --- |
| D1 | Window-function prune partitioned by domain | single statement, exact newest-per-domain semantics | two subqueries per known domain (breaks if domains grow) |
| D2 | Grace period 24h on mtime for media deletion | protects files whose DB row is mid-write; simple deterministic rule | reference-only check (races with insert order), no grace (risk of deleting fresh files) |
| D3 | Sweep throttled in-process to 1/hour + startup run | bounded IO cost, no new timers/threads | background thread (new lifecycle complexity) |
| D4 | Mirror deletion piggybacks existing passage prune flow | same transaction boundary as source deletion, no new endpoints | periodic full resync (heavier, still eventual) |

## Affected contours

VPS only: `api/**`. Ubuntu Worker/relay: NOT REQUIRED.

## Validation

- New tests `tests/test_storage_retention.py`: per-domain retention, media sweep
  grace/reference/unsafe-name rules, throttle, mirror sync and reconciliation.
- Updated `tests/test_api_contract.py` retention tests to per-domain semantics.
- Full unittest discovery; repository validators; quality validators.

## Risk profile

- Risk profile: REQUIRED

- RISK-038-001 | Category: DATA | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: grace period prevents deletion of in-flight snapshots; only unreferenced files removed; unsafe names ignored | Validation: dedicated unit tests for grace/reference/unsafe cases | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-038-002 | Category: PERF | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: sweep throttled to 1/hour; directory scan is a single listdir | Validation: throttle unit test without sleeps | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-038-003 | Category: TECH | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: window functions supported by SQLite >=3.25 (Ubuntu 24.04 ships 3.45); local suite exercises real SQLite file DBs | Validation: full unittest discovery on real sqlite3 connections | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-038-004 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: unlink failures logged to stderr and never propagate to request path | Validation: failure-injection unit test | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED

## Test design

- TEST-038-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_storage_retention.py::test_per_domain_retention_keeps_100_each
- TEST-038-002 | Covers: AC-002, AC-003, AC-004 | Level: unit | Priority: P0 | Evidence: tests/test_storage_retention.py media sweep tests
- TEST-038-003 | Covers: AC-005 | Level: unit | Priority: P1 | Evidence: tests/test_storage_retention.py throttle test with injected clock
- TEST-038-004 | Covers: AC-006, AC-007 | Level: unit | Priority: P0 | Evidence: tests/test_storage_retention.py mirror sync/reconciliation tests
- TEST-038-005 | Covers: AC-008, AC-009 | Level: integration | Priority: P0 | Evidence: local discovery run + required CI on exact head
- TEST-038-006 | Covers: AC-010 | Level: runtime-manual | Priority: P1 | Evidence: post-deploy UI verification recorded in Issue #261

## Correct-course check

- Trigger: PRODUCTION_LEARNING
- Issue impact: storage audit on Issue #261 identified shared-quota eviction, unbounded events media growth and mirror desync; scope records all three fixes
- Specification impact: spec requirements R1-R6 define deterministic retention semantics
- Plan impact: decisions D1-D4 bind implementation to single-statement prune, grace-guarded sweep, throttled IO and transactional mirror sync
- Tasks impact: tasks.md traceability maps AC-001..AC-011 to the retention implementation
- Authorization impact: NONE - same approved six-field scope, no protected-boundary change
- Follow-up: verify per-domain retention and bounded media growth at post-deploy acceptance (AC-010)

## Runtime feedback

To be recorded after VPS deployment acceptance.

## Deployment transaction audit

Required: API write-path change merged to main followed by autonomous VPS deployment.

- Adjacent-stage review: COMPLETE
- Production-learning root cause: storage audit found objects registry used a single shared 100-row quota across domains, media/events had no cleanup path at all, and passage pruning did not remove mirror rows - three independent drift sources between registries and disk
- Production-learning adjacent-stage findings: MUTATION/VERIFICATION stages unaffected (no deploy logic change); STATE-COMMIT/EVIDENCE stages gain bounded-storage evidence via sweep logs; ROLLBACK unchanged because policy is additive and revert restores prior prune behavior

- TX-038-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport, previous release continues serving | Retry: after policy/state correction via workflow rerun | Rollback: NOT REQUIRED - no mutation attempted | Evidence: deploy-runtime-autonomous workflow run log with policy decision id
- TX-038-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: source protection or Quality mismatch aborts before transport | Retry: after remediation of protection/Quality state | Rollback: NOT REQUIRED - no mutation attempted | Evidence: verify_source_protection.py output in protected workflow log
- TX-038-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous release keeps running when health checks gate service switch; otherwise restarted service flagged unverified | Retry: rerun deploy-vps.yml workflow | Rollback: redeploy rollbackTarget recorded by deployment manifest | Evidence: deployment-manifest-vps.json
- TX-038-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: service up but runtime_verified=false blocks completion claims | Retry: rerun verification stage via workflow rerun | Rollback: rollback target from manifest if verification cannot pass | Evidence: manifest checks array entries
- TX-038-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: mutation done but evidence artifact missing; completion not claimed | Retry: rerun evidence upload stage | Rollback: NOT REQUIRED - state commit is additive evidence | Evidence: exact-artifacts.json artifact on workflow run
- TX-038-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: old media may remain; functionality unaffected | Retry: opportunistic on next sweep/deployment | Rollback: NOT REQUIRED - cleanup only | Evidence: deploy logs and sweep stderr notes
- TX-038-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: verified deployment without typed audit must not be claimed complete | Retry: rerun audit emission stage | Rollback: NOT REQUIRED - evidence is additive | Evidence: sea_speed_production_execution_audit_v1 bound to policy decision
- TX-038-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback escalates to BLOCKED with human decision required | Retry: manual decision then redeploy known-good target | Rollback: itself is the rollback path | Evidence: rollbackTarget hash in deployment manifest
