# Feature Specification: Domain-scoped Object Registry

- Feature: 026-domain-scoped-object-registry
- Issue: #223
- Status: Source implementation
- Owner outcome: Water and Road operators open a registry that remains locked to the domain they came from, without changing backend storage or retention.

## Product outcome

The Water operator opens a Water registry scoped to `camera_id=cam1` and `domain=water`. The Road operator opens a Road registry scoped to `camera_id=road1` and `domain=road`. The shared Objects page remains one frontend and one existing SQLite/API contract, but its ordinary navigation and reset flow cannot silently broaden a domain-scoped view into the combined registry.

Existing Water/Road operator markup may keep the common `/sea-speed/objects/` destination. When that destination has no explicit `scope`, the Objects page derives the initial scope only from the same-origin operator referrer (`/sea-speed/road/` -> Road; otherwise Water), immediately canonicalizes the current URL to `?scope=water|road`, and thereafter treats that explicit scope as authoritative across reload/reset. The Objects page itself exposes explicit Water/Road scoped links.

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

- NFR-001 | Area: BACKWARD_COMPATIBILITY | Target: no backend/API/storage contract change | Validation: exact diff plus frontend tests | Status: PASS
- NFR-002 | Area: DATA_SAFETY | Target: no retention/schema mutation | Validation: `api/app/main.py` absent from diff | Status: PASS
- NFR-003 | Area: UX_SAFETY | Target: ordinary navigation/reset cannot silently broaden a scoped registry | Validation: static contract + browser acceptance | Status: CONCERNS
- NFR-004 | Area: OPERABILITY | Target: VPS-only rollout under existing deployment transaction | Validation: Change Contract + later deployment evidence | Status: CONCERNS
