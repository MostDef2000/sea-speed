# Plan: Registry hygiene — reject objects without photo

- Issue: #283
- Specification: specs/045-no-photo-registry-guard/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-045-001 | Category: DATA | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: API guards at lowest persist layer plus endpoint validation; existing polluted records soft-deleted via idempotent cleanup; pinned by unit tests | Validation: NoPhotoGuardTests + migration test | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-045-002 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: endpoint 422 is additive — valid snapshots path unchanged; worker guard prevents false 422 from transient write failure | Validation: existing persist tests with snapshot + worker guard test | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED
- RISK-045-003 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: cleanup soft-deletes (reversible via deleted_at) not hard deletes; migration runs at startup and is rerunnable | Validation: idempotency test | Residual risk: LOW | Owner: delivery-orchestrator | Status: MITIGATED

## Architecture

API (VPS): add snapshot_url presence checks in `persist_object_event` and `persist_passage_object`; enforce `snapshot` required in `post_analytics_event` (all cameras) and in `upsert_water_passage`/`post_cam1_passage` for new passages; add startup/one-shot helper `prune_snapshotless_objects` that soft-deletes objects where `snapshot_url` is empty.

Worker (Ubuntu, shared executable): harden `post_event`/`post_passage` and main loop snapshot writes — only post when `cv2.imwrite` succeeded and file exists.

Frontend: no change required; `photoMarkup` fallback remains but should no longer be triggered.

## Decisions

- D1: Use soft-delete (set deleted_at) for existing polluted records — reversible and consistent with existing delete flow, not hard DELETE.
- D2: API is source of truth for registry hygiene — worker hardening is complementary but not required for correctness.
- D3: New passages require snapshot; updates to an existing passage may reuse stored snapshot_url if no new bytes supplied.

## Affected contours

- VPS: API persist guards, endpoint validation, cleanup helper.
- Ubuntu Worker/relay: worker snapshot-write guard.

## Validation

- Unit: persist guards, endpoint 422, passage snapshot requirement, worker guard, cleanup idempotency.
- Full discover green; validators pass; exact-head CI required.

## Runtime feedback

To be recorded after both-contour deployment acceptance.

## Test design

- TEST-045-001 | Covers: AC-001, AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_api_contract.py::NoPhotoGuardTests (persist + endpoint)
- TEST-045-002 | Covers: AC-002, AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_water_passage.py + api contract (passage guard)
- TEST-045-003 | Covers: AC-004 | Level: unit | Priority: P1 | Evidence: tests/test_line_crossing.py or worker extract test (write guard)
- TEST-045-004 | Covers: AC-005, AC-006 | Level: unit | Priority: P0 | Evidence: cleanup migration test
- TEST-045-005 | Covers: AC-001..AC-006 | Level: runtime-manual | Priority: P1 | Evidence: operator verification post-deploy (both domains, zero missing photos)

## Correct-course check

- Adjacent-stage review: COMPLETE
- Trigger: NONE
- Issue impact: operator reports many road «Фотография отсутствует» cards; water to be investigated and fixed identically
- Specification impact: R1-R6 capture snapshot requirement for both domains plus cleanup
- Plan impact: adds DATA-risk path with soft-delete migration
- Tasks impact: traceability maps AC-001..AC-006 to tasks
- Authorization impact: NONE — fresh receipt src-auth-283-no-photo-guard covers exact paths
- Follow-up: operator verifies zero missing photos post-deploy for road and water

## Deployment transaction audit

Required: runtime deployment REQUIRED for both contours (API + worker).

- TX-045-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport, previous releases serving | Retry: after policy/state correction | Rollback: NOT REQUIRED | Evidence: autonomous workflow log with policy decision id
- TX-045-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: source protection/Quality mismatch aborts before transport | Retry: after remediation | Rollback: NOT REQUIRED | Evidence: verify_source_protection.py output
- TX-045-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous release keeps serving on health gate failure | Retry: rerun failed contour | Rollback: redeploy rollbackTarget from manifest | Evidence: deployment manifests (both contours)
- TX-045-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime_verified=false blocks DONE | Retry: rerun verification | Rollback: rollback target if cannot pass | Evidence: manifest checks arrays (snapshot guard checks)
- TX-045-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: evidence missing blocks completion | Retry: rerun evidence upload | Rollback: NOT REQUIRED | Evidence: exact-artifacts.json
- TX-045-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: stale tmp remains | Retry: next deploy | Rollback: NOT REQUIRED | Evidence: deploy logs
- TX-045-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: verified deploy without audit not claimed complete | Retry: rerun audit emission | Rollback: NOT REQUIRED | Evidence: typed execution audit bound to policy decision
- TX-045-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback → BLOCKED | Retry: manual decision + redeploy known-good | Rollback: itself is rollback path | Evidence: rollbackTarget hash in manifests
