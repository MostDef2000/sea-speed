# Plan: Line-crossing counter (both contours)

- Issue: #265
- Specification: specs/040-line-crossing-counter/spec.md

## Risk profile declaration

- Risk profile: REQUIRED
- Risk triggers: MIXED contour deployment; new ingest endpoint; registry write path extension.

## Architecture

- Worker: cached per-camera crossing-line config (speed-lines pattern), per-track side memory with horizontal-displacement direction and cooldown debounce, live counters rendered bottom-right, stats block relocated bottom-left, bounded pending-post queue flushed each frame.
- API: additive endpoints only — crossing-line config GET/POST with cam1 aliases, authenticated crossings ingest persisting through `persist_object_event` plus a bounded store, 24h summary aggregation.
- Frontend: self-contained editor block (canvas + buttons) and summary panel on both main screens; no changes to existing minified logic.

## Decisions

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

## RISK records

- RISK-040-001 | Category: REGRESSION | Probability: LOW | Impact: MEDIUM | Score: 6 | Mitigation: overlay changes are pure draw-coordinate moves; state/event/passage paths untouched | Validation: full unittest discovery + existing suites green | Residual risk: minimal visual-only | Owner: orchestrator | Status: MITIGATED
- RISK-040-002 | Category: DOUBLE_COUNT | Probability: MEDIUM | Impact: LOW | Score: 4 | Mitigation: per-track side memory plus cooldown window; direction from horizontal displacement | Validation: synthetic wobble test | Residual risk: tracker ID switches may under/over-count rare cases | Owner: orchestrator | Status: MITIGATED
- RISK-040-003 | Category: INGEST_ABUSE | Probability: LOW | Impact: MEDIUM | Score: 6 | Mitigation: bearer auth like other ingest endpoints; strict payload validation; bounded store cap | Validation: unit tests for validation and cap | Residual risk: none identified | Owner: orchestrator | Status: MITIGATED
- RISK-040-004 | Category: DEPLOY_MIXED | Probability: LOW | Impact: MEDIUM | Score: 6 | Mitigation: standing delegation autonomous routing; exact-artifact gates; rollback targets recorded by manifests | Validation: runtime_verified manifests both contours | Residual risk: transient SSH drops observed historically; rerun succeeds | Owner: orchestrator | Status: MITIGATED

## TEST records

- TEST-040-001 | Covers: AC-001, AC-002, AC-003 | Level: unit | Priority: HIGH | Evidence: tests/test_line_crossing.py::CrossingDetectionTests
- TEST-040-002 | Covers: AC-004 | Level: unit | Priority: HIGH | Evidence: tests/test_line_crossing.py::PersonGateTests
- TEST-040-003 | Covers: AC-005, AC-006 | Level: unit | Priority: HIGH | Evidence: tests/test_line_crossing.py::ApiCrossingTests
- TEST-040-004 | Covers: AC-007 | Level: unit | Priority: MEDIUM | Evidence: tests/test_line_crossing.py::OverlayLayoutTests
- TEST-040-005 | Covers: AC-008 | Level: manual-runtime | Priority: MEDIUM | Evidence: operator UI verification post-deploy

## Correct-course check

- Adjacent-stage review: COMPLETE
- Root cause of prior adjacent friction: GitHub rerun-failed-jobs reuses original event payload; canonical PR sections and SDD record formats validated locally before push this time.
- Deployment Transaction Audit stages mapped in tasks.md TX records (deployment REQUIRED for both contours).

## DOD markers

- [x] Exact changed-file scope verified
- [x] Linked SDD artifacts current
- [x] Required tests passed
- [ ] Runtime acceptance complete
