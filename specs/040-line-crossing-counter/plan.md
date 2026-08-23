# Plan: Line-crossing counter (both contours)

- Issue: #265
- Specification: specs/040-line-crossing-counter/spec.md

## Risk profile

- Risk profile: REQUIRED

- RISK-040-001 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: overlay changes are pure draw-coordinate moves; state/event/passage paths untouched | Validation: full unittest discovery + existing suites green | Residual risk: minimal visual-only | Owner: orchestrator | Status: MITIGATED
- RISK-040-002 | Category: TECH | Probability: 3 | Impact: 2 | Score: 6 | Mitigation: per-track side memory plus cooldown window; direction from horizontal displacement | Validation: synthetic wobble test | Residual risk: tracker ID switches may under/over-count rare cases | Owner: orchestrator | Status: MITIGATED
- RISK-040-003 | Category: SEC | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: bearer auth like other ingest endpoints; strict payload validation; bounded store cap | Validation: unit tests for validation and cap | Residual risk: none identified | Owner: orchestrator | Status: MITIGATED
- RISK-040-004 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: standing delegation autonomous routing; exact-artifact gates; rollback targets recorded by manifests | Validation: runtime_verified manifests both contours | Residual risk: transient SSH drops observed historically; rerun succeeds | Owner: orchestrator | Status: MITIGATED

## Architecture

- Worker: cached per-camera crossing-line config (speed-lines pattern), per-track side memory with horizontal-displacement direction and cooldown debounce, live counters rendered bottom-right, stats block relocated bottom-left, bounded pending-post queue flushed each frame.
- API: additive endpoints only — crossing-line config GET/POST with cam1 aliases, authenticated crossings ingest persisting through `persist_object_event` plus a bounded store, 24h summary aggregation.
- Frontend: self-contained editor block (canvas + buttons) and summary panel on both main screens; no changes to existing minified logic.

## Decisions

- D5: The private worker M2M ingress allowlist is extended by exactly four exact-location entries (GET crossing-line, POST crossings for cam1 and road1); no prefix or wildcard proxying is introduced.
- D6: flush_crossing_posts peeks before posting so a failed transport retains the event at the queue head and a successful retry removes it exactly once.
- Direction derives from horizontal centroid displacement so left-to-right matches frame semantics regardless of line angle.
- Road person detections are excluded from crossings to stay consistent with the event publication gate.
- Crossings reuse the objects registry write path instead of a new store, keeping one durable object truth.

## Affected contours

- Ubuntu Worker/relay: worker detection + overlay changes deploy via the canonical Ubuntu workflow.
- VPS: API endpoints, registry persistence, frontend pages deploy via the canonical VPS workflow.

## Validation

- Unit: tests/test_line_crossing.py covers both directions, wobble debounce, person gate, registry persistence, summary window, overlay layout anchors.
- Full discovery must stay green; SDD/repo/contract/quality validators run before push.
- Runtime: runtime_verified manifests for both contours plus operator UI verification.

## Runtime feedback

- Overlay counters update within one state interval after enabling the line.
- Summary panels poll every 15 seconds and reflect newly persisted crossings.

## Approach

1. Worker: cached crossing-line config fetch (speed-lines pattern), per-track side memory with direction from horizontal motion, debounce cooldown per track, live counters, bottom-left stats block and bottom-right counters block in `draw_overlay`, crossing posts to the new API endpoint.
2. API: additive endpoints (crossing-line config GET/POST with cam1 aliases, crossings ingest POST, 24h summary GET). Ingest persists via existing `persist_object_event` and appends to a bounded per-camera store.
3. Frontend: both main screens get a two-click line editor on a dedicated canvas plus a 24h summary panel polling the summary endpoint.
4. Tests mirror existing AST-load patterns for worker functions and API handlers.

## Test design

Risk-based selection: directional counting and debounce (RISK-040-002) get synthetic track sequences; person gate gets an explicit negative; ingest validation and bounded store (RISK-040-003) get unit coverage; summary window uses fresh/stale fixtures; overlay layout is anchored by source assertions to catch regressions of the relayout.


- TEST-040-001 | Covers: AC-001, AC-002, AC-003 | Level: unit | Priority: P0 | Evidence: tests/test_line_crossing.py::CrossingDetectionTests
- TEST-040-002 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: tests/test_line_crossing.py::PersonGateTests
- TEST-040-003 | Covers: AC-005, AC-006 | Level: unit | Priority: P0 | Evidence: tests/test_line_crossing.py::ApiCrossingTests
- TEST-040-004 | Covers: AC-007 | Level: unit | Priority: P1 | Evidence: tests/test_line_crossing.py::OverlayLayoutTests
- TEST-040-005 | Covers: AC-008 | Level: runtime-manual | Priority: P1 | Evidence: operator UI verification post-deploy

## Correct-course check

- Adjacent-stage review: COMPLETE
- Trigger: PRODUCTION_LEARNING
- Issue impact: operator requested counting lines for both contours plus overlay relayout; scope covers water and road symmetrically
- Specification impact: requirements R1-R7 define config, detection, persistence, summary, UI and overlay layout
- Plan impact: decisions bind direction semantics, person gate consistency and registry reuse over a parallel store
- Tasks impact: tasks.md maps AC-001..AC-009 to TASK-040-01..08 with evidence cursors
- Authorization impact: NONE - same approved six-field scope, protected formulas untouched
- Follow-up: verify counters, summaries and overlay blocks at post-deploy acceptance on both contours

## DOD markers

- [x] Exact changed-file scope verified
- [x] Linked SDD artifacts current
- [x] Required tests passed
- [ ] Runtime acceptance complete

## Deployment transaction audit

Required: worker and api runtime deployment follow merge.

- Adjacent-stage review: COMPLETE
- Production-learning root cause: operator needs directional object counting; existing overlay placed stats top-left with no crossing awareness
- Production-learning adjacent-stage findings: MUTATION stage covers both contours for the new worker+API release; VERIFICATION gains counter/summary checks in acceptance; ROLLBACK unchanged per-contour

- TX-040-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no transport, previous releases continue serving | Retry: after policy/state correction via workflow rerun | Rollback: NOT REQUIRED - no mutation attempted | Evidence: deploy-runtime-autonomous workflow run log with policy decision id
- TX-040-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: source protection or Quality mismatch aborts before transport | Retry: after remediation of protection/Quality state | Rollback: NOT REQUIRED - no mutation attempted | Evidence: verify_source_protection.py output in protected workflow logs
- TX-040-003 | Stage: MUTATION | Mutation: YES | Failure disposition: CONDITIONAL | State after failure: previous release keeps running when health checks gate service switch; otherwise restarted service flagged unverified | Retry: rerun deploy workflow for the failed contour | Rollback: redeploy rollbackTarget recorded by deployment manifest | Evidence: deployment-manifest-vps.json and ubuntu deployment manifest
- TX-040-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: service up but runtime_verified=false blocks completion claims | Retry: rerun verification stage via workflow rerun | Rollback: rollback target from manifest if verification cannot pass | Evidence: manifest checks array entries
- TX-040-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: mutation done but evidence artifact missing; completion not claimed | Retry: rerun evidence upload stage | Rollback: NOT REQUIRED - state commit is additive evidence | Evidence: exact-artifacts.json artifacts on workflow run
- TX-040-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: old media/tmp may remain; functionality unaffected | Retry: opportunistic on next sweep/deployment | Rollback: NOT REQUIRED - cleanup only | Evidence: deploy logs
- TX-040-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: FATAL | State after failure: verified deployment without typed audit must not be claimed complete | Retry: rerun audit emission stage | Rollback: NOT REQUIRED - evidence is additive | Evidence: sea_speed_production_execution_audit_v1 bound to policy decision
- TX-040-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: FATAL | State after failure: failed rollback escalates to BLOCKED with human decision required | Retry: manual decision then redeploy known-good target | Rollback: itself is the rollback path | Evidence: rollbackTarget hash in deployment manifests
