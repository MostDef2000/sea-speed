# Feature Specification: Domain-scoped Object Registry

- Feature: 026-domain-scoped-object-registry
- Issue: #223
- Status: Source implementation
- Owner outcome: Water and Road operators open a registry that remains locked to the domain they came from, without changing backend storage or retention.

## Product outcome

The Water operator opens a Water registry scoped to `camera_id=cam1` and `domain=water`. The Road operator opens a Road registry scoped to `camera_id=road1` and `domain=road`. The shared Objects page remains one frontend and one existing SQLite/API contract, but its ordinary navigation and reset flow cannot silently broaden a domain-scoped view into the combined registry.

Existing Water/Road operator markup may keep the common `/sea-speed/objects/` destination. When that destination has no explicit `scope`, the Objects page derives the initial scope only from the same-origin operator referrer (`/sea-speed/road/` -> Road; otherwise Water), immediately canonicalizes the current URL to `?scope=water|road`, and thereafter treats that explicit scope as authoritative across reload/reset. The Objects page itself exposes explicit Water/Road scoped links.

## User scenarios

### Scenario 1 - Water operator opens the Water registry

Given an authenticated operator is on `/sea-speed/`, when the operator opens `Реестр объектов`, then the shared Objects page resolves to Water scope, canonicalizes the URL to `?scope=water`, and every list request remains locked to `camera_id=cam1` and `domain=water`.

### Scenario 2 - Road operator opens the Road registry

Given an authenticated operator is on `/sea-speed/road/`, when the operator opens `Реестр объектов`, then the shared Objects page resolves to Road scope, canonicalizes the URL to `?scope=road`, and every list request remains locked to `camera_id=road1` and `domain=road`.

### Scenario 3 - Scope survives ordinary navigation and reset

Given either scoped registry is open, when the operator reloads the page, copies the scoped URL, changes ordinary filters, paginates or presses Reset, then the selected Water/Road domain remains authoritative while search/date/speed/status filters and object detail operations continue to work within that domain.

### Scenario 4 - Existing backend and retention remain unchanged

Given the scoped registry UI is deployed, the generic `/sea-speed/api/objects` endpoint, SQLite schema, newest-100 Objects retention, newest-300 Water Passage retention, object edit/delete semantics, workers and analytics runtime remain unchanged.

## Requirements

- FR-001: Entry from Water Operator MUST resolve to Water scope and entry from Road Operator MUST resolve to Road scope; this MAY be implemented by same-origin operator-referrer inference when the existing navigation URL has no explicit `scope`.
- FR-002: `scope=water` MUST force `camera_id=cam1` and `domain=water` on every Objects list request.
- FR-003: `scope=road` MUST force `camera_id=road1` and `domain=road` on every Objects list request.
- FR-004: Camera and domain controls MUST visibly reflect the locked scope and MUST NOT allow ordinary form interaction to remove or cross the domain lock.
- FR-005: Reset MUST clear ordinary filters while preserving the active domain lock.
- FR-006: A valid explicit scope MUST be authoritative. When scope is absent, only a same-origin Road operator referrer MAY select Road; otherwise Water is the default. An unsupported explicit scope MUST canonicalize to Water rather than expose the combined registry.
- FR-007: The page MUST canonicalize the selected scope into `?scope=water|road` so reload and copied scoped URLs preserve the domain without depending on referrer state.
- FR-008: Search, date, speed, status, pagination, detail, edit and delete behavior MUST remain compatible.
- FR-009: The implementation MUST reuse the existing generic `/sea-speed/api/objects` endpoint; `api/app/main.py`, SQLite schema and retention behavior are out of scope.
- FR-010: Existing combined newest-100 retention and Water Passage newest-300 retention MUST remain unchanged.
- FR-011: Production deployment MUST be VPS-only and separately exact-SHA authorized after merge.

## Acceptance criteria

- AC-001: Static frontend contract proves the unchanged Water/Road registry links plus contextual Objects entry logic resolve Water to `cam1/water` and Road to `road1/road`.
- AC-002: Objects frontend contract proves every list request contains the locked `camera_id` and `domain` and ignores form attempts to override those two keys.
- AC-003: Reset contract proves the domain scope is reapplied after form reset.
- AC-004: Camera/domain controls are locked while ordinary filters and pagination remain present.
- AC-005: The selected scope is canonicalized into the page URL and therefore survives reload/direct scoped navigation.
- AC-006: PATCH/DELETE detail workflow and same-origin session behavior remain present.
- AC-007: Exact PR diff is a subset of the seven authorized paths and passes PR Validation plus aggregate Quality on one exact head.
- AC-008: Expected-head merge is followed by exact-main Quality.
- AC-009: After separate exact-SHA VPS authorization, browser acceptance proves Water and Road navigation each show only their own domain and scope survives reload/reset.

## NFR assessment

- NFR-001 | Area: BACKWARD_COMPATIBILITY | Target: no backend/API/storage contract change | Validation: exact diff plus frontend behavioral tests | Evidence: `api/app/main.py` and storage paths absent from PR diff; `tests/test_frontend_contract.py` retained edit/delete/session assertions | Status: PASS
- NFR-002 | Area: DATA_SAFETY | Target: no retention or schema mutation | Validation: exact changed-file scope | Evidence: final PR changed-file set contains only one frontend file, one test file and the linked SDD triplet | Status: PASS
- NFR-003 | Area: UX_SAFETY | Target: ordinary navigation, reload and Reset cannot silently broaden a scoped registry | Validation: focused frontend contract plus later authenticated browser acceptance | Evidence: `tests/test_frontend_contract.py` scope-lock/canonicalization assertions; runtime acceptance remains pending until separately authorized deployment | Status: CONCERNS
- NFR-004 | Area: OPERABILITY | Target: VPS-only rollout uses exact-SHA production authorization and canonical deployment transaction | Validation: Change Contract, exact-main Quality, deployment manifest and browser smoke | Evidence: source CI/merge evidence will be recorded on Issue #223 before any runtime authorization; runtime evidence is intentionally pending | Status: CONCERNS

## Runtime feedback

- Source authorization for the original seven-path outcome was granted with exact `OUTCOME APPROVED` after the operator-visible Scope on Issue #223.
- Initial CI admission exposed only Change Contract metadata defects and then an SDD numeric-prefix collision because `025-tool-routing-contract` already exists on `main`; no product-source behavioral failure was observed in those attempts.
- Fresh path-correction Scope was approved with exact `OUTCOME APPROVED`; the SDD triplet moved from branch-only `025-domain-scoped-object-registry` to unique `026-domain-scoped-object-registry` while the product outcome and runtime contour remained unchanged.
- The final base-to-head diff is intentionally five paths: `frontend/sea-speed/objects/index.html`, `tests/test_frontend_contract.py`, and this `026` SDD triplet. Water/Road operator page bytes do not require modification because the shared Objects page can derive same-origin operator context when `scope` is absent.
- Production mutation is not authorized by source approval. After exact-green merge and exact-main Quality, VPS runtime activation requires a separate exact-SHA production authorization and later authenticated browser acceptance.
