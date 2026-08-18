# Implementation Plan: Water detection activation and registry cap

- Specification: specs/022-water-detection-registry-cap/spec.md
- Issue: #212
- Status: Implementing

## Architecture

The existing shared analytics-profile layer remains the only source of model/profile defaults. `water-v1` becomes the safe no-argument default while Road continues to select `road-v1` explicitly through protected configuration.

The Objects Registry remains one SQLite `objects` table shared by Water and Road. Retention is implemented in the persistence layer, not the frontend or list API: a small deterministic pruning helper deletes all rows outside the newest 100 ordered by `detected_at DESC, object_id DESC`. It runs after schema/index initialization and after a successful new insert. JSON event history and snapshot/media lifecycle remain unchanged.

Runtime applicability is MIXED. VPS receives the API/storage change. Ubuntu receives the shared Worker profile-default change and later Water activation. Source integration performs no production mutation.

## Decisions

- D-001: Use `water-v1` as the safe default because the primary shared Water worker is the no-argument analytics consumer; Road already has explicit protected `road-v1` configuration.
- D-002: Enforce the test cap in SQLite persistence so API filters/pagination cannot bypass retention.
- D-003: Cap the combined Water + Road registry at 100 rows, matching the approved test-stage outcome.
- D-004: Retain deterministic newest ordering by `detected_at DESC, object_id DESC`.
- D-005: Do not delete snapshot/media assets or truncate JSON event-history files in this Outcome.
- D-006: Deploy VPS before Ubuntu so storage retention is active before Water begins adding new detections.

## Affected contours

- VPS: REQUIRED — `api/app/main.py` changes persistent storage behavior. Execution capability: CONNECTOR.
- Ubuntu Worker/relay: REQUIRED — `worker/analytics_profiles.py` changes shared executable Worker default semantics and the accepted Outcome includes Water activation. Execution capability: ONE_COMMAND_FALLBACK unless restricted Connector transport is independently proven available.
- Windows: retired; NOT APPLICABLE.
- Operator actions expected: 1 when Ubuntu remains ONE_COMMAND_FALLBACK.

## Validation

Source validation covers Python syntax, analytics-profile unit contracts, API persistence tests, SDD validation, exact seven-path scope, secret/runtime-artifact absence, PR Validation and aggregate Quality integration.

Runtime validation occurs only after separate exact-SHA production authorization. VPS acceptance verifies exact source and a registry count no greater than 100 before/after new event ingestion. Ubuntu acceptance verifies exact source/runtime identity, protected model/profile values, Water service running, advancing frame/state/AI telemetry and Water `vessel` events reaching the VPS registry.

## Risk profile

- Risk profile: REQUIRED
- RISK-001 | Category: DATA | Probability: 5 | Impact: 4 | Score: 20 | Mitigation: deterministic pruning only outside newest 100; explicit test-stage contract; no media deletion | Validation: oversized initialization and insertion tests | Residual risk: pruned SQLite history is not recoverable by source rollback | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-002 | Category: OPS | Probability: 3 | Impact: 4 | Score: 12 | Mitigation: VPS-first rollout establishes retention before Water activation; separate exact-SHA production gate | Validation: deployment manifests and runtime registry count | Residual risk: a failed mixed rollout can leave one contour on the new release; contours remain backward compatible | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-003 | Category: TECH | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: preserve exact YOLO26x/ByteTrack/threshold/class-map values and add default-profile regression | Validation: analytics-profile tests | Residual risk: protected runtime config can still override defaults intentionally | Owner: Delivery Orchestrator | Status: MITIGATED
- RISK-004 | Category: PERF | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: pruning operates on at most the transient current registry and uses existing detected-at index | Validation: unit contract and production smoke | Residual risk: one delete query occurs after each successful insert | Owner: Delivery Orchestrator | Status: ACCEPTED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: `tests/test_analytics_profiles.py`
- TEST-002 | Covers: AC-002,AC-003 | Level: unit | Priority: P0 | Evidence: `tests/test_api_contract.py`
- TEST-003 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: existing API contract suite
- TEST-004 | Covers: AC-005,AC-006 | Level: integration | Priority: P0 | Evidence: exact compare, PR Validation, aggregate Quality, post-merge Quality
- TEST-005 | Covers: AC-007 | Level: runtime-manual | Priority: P0 | Evidence: VPS deployment manifest and direct registry-count evidence
- TEST-006 | Covers: AC-008 | Level: runtime-manual | Priority: P0 | Evidence: Ubuntu deployment manifest, Water service/telemetry and resulting Water object evidence

## Correct-course check

- Trigger: NONE
- Issue impact: none beyond the approved Outcome Contract.
- Specification impact: current specification directly reflects approved Water default and 100-row combined registry cap.
- Plan impact: no architecture pivot identified.
- Tasks impact: implement exact seven paths, then source integration, then separately authorized runtime rollout.
- Authorization impact: RESOLVED — complete six-field Scope immediately preceded operator `OUTCOME APPROVED` on 2026-08-18 and is durably recorded in Issue #212.
- Follow-up: any change to retention count, per-camera versus combined semantics, media deletion, JSON retention or detector parameters is material and requires fresh Scope + `OUTCOME APPROVED`.

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: production unchanged | Retry: only after exact source, quality, release provenance and production authorization pass | Rollback: not applicable | Evidence: runtime router admission
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: accepted runtime unchanged | Retry: after exact artifact/config/rollback checks pass | Rollback: not applicable | Evidence: VPS/Ubuntu preflight
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: candidate rejected; deployment transaction restores prior release where supported | Retry: only after actual state/root cause is resolved | Rollback: known prior VPS and Ubuntu exact releases | Evidence: deployment logs
- TX-004 | Stage: VERIFICATION | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: unverified candidate is not accepted | Retry: after verification defect is resolved | Rollback: prior exact release; note DB rows already pruned cannot be restored by source rollback | Evidence: source/health/registry/telemetry checks
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: release markers/manifests remain unaccepted | Retry: after exact runtime state is revalidated | Rollback: prior release markers where safe | Evidence: deployment manifests/current-release state
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified release remains accepted; stale cleanup may remain | Retry: safe after acceptance | Rollback: none for housekeeping-only failure | Evidence: cleanup output
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: task cannot reach DONE without durable evidence | Retry: re-read machine state and persist sanitized evidence; do not redeploy solely for evidence | Rollback: not applicable | Evidence: Issue #212, manifests, CI runs
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: prior executable release restored or critical state recorded | Retry: prohibited until safety is resolved | Rollback: exact known prior VPS/Ubuntu release; pruned registry history is explicitly non-restorable | Evidence: rollback markers and health checks

## Runtime feedback

- Initial PR Validation #445 exposed a PR Change Contract enum defect; the PR metadata was corrected without source-scope expansion.
- PR Validation #446 then exposed SDD validator contract mismatches: missing required User scenarios, unsupported test-level/trigger enums, and non-canonical traceability progress coverage. These are SDD-only remediation inside the approved feature paths; product behavior and protected boundaries are unchanged.
