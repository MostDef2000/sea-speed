# Feature Specification: Domain-scoped Object Registry

- Feature: 025-domain-scoped-object-registry
- Issue: #223
- Status: Source implementation
- Owner outcome: Water and Road operators open a registry that remains locked to the domain they came from, without changing backend storage or retention.

## Product outcome

The Water operator links to a Water registry scoped to `camera_id=cam1` and `domain=water`. The Road operator links to a Road registry scoped to `camera_id=road1` and `domain=road`. The shared Objects page remains one frontend and one existing SQLite/API contract, but its ordinary navigation and reset flow cannot silently broaden a domain-scoped view into the combined registry.

## Requirements

- FR-001: Water Operator MUST link to `/sea-speed/objects/?scope=water` and Road Operator MUST link to `/sea-speed/objects/?scope=road`.
- FR-002: `scope=water` MUST force `camera_id=cam1` and `domain=water` on every Objects list request.
- FR-003: `scope=road` MUST force `camera_id=road1` and `domain=road` on every Objects list request.
- FR-004: Camera and domain controls MUST visibly reflect the locked scope and MUST NOT allow ordinary form interaction to remove or cross the domain lock.
- FR-005: Reset MUST clear ordinary filters while preserving the active domain lock.
- FR-006: A missing or unsupported scope MUST canonicalize to Water scope rather than expose the combined registry through normal page entry.
- FR-007: Search, date, speed, status, pagination, detail, edit and delete behavior MUST remain compatible.
- FR-008: The implementation MUST reuse the existing generic `/sea-speed/api/objects` endpoint; `api/app/main.py`, SQLite schema and retention behavior are out of scope.
- FR-009: Existing combined newest-100 retention and Water Passage newest-300 retention MUST remain unchanged.
- FR-010: Production deployment MUST be VPS-only and separately exact-SHA authorized after merge.

## Acceptance criteria

- AC-001: Static frontend contract proves Water and Road pages use distinct scoped registry URLs.
- AC-002: Objects frontend contract proves Water maps only to `cam1/water` and Road only to `road1/road`.
- AC-003: Reset contract proves the domain scope is reapplied after form reset.
- AC-004: Camera/domain controls are locked while ordinary filters and pagination remain present.
- AC-005: PATCH/DELETE detail workflow and same-origin session behavior remain present.
- AC-006: Exact PR diff contains only the seven authorized paths and passes PR Validation plus aggregate Quality on one exact head.
- AC-007: Expected-head merge is followed by exact-main Quality.
- AC-008: After separate exact-SHA VPS authorization, browser acceptance proves Water and Road navigation each show only their own domain and scope survives reload/reset.

## NFR assessment

- NFR-001 | Area: BACKWARD_COMPATIBILITY | Target: no backend/API/storage contract change | Validation: exact diff plus frontend tests | Status: PASS
- NFR-002 | Area: DATA_SAFETY | Target: no retention/schema mutation | Validation: `api/app/main.py` absent from diff | Status: PASS
- NFR-003 | Area: UX_SAFETY | Target: ordinary navigation/reset cannot silently broaden a scoped registry | Validation: static contract + browser acceptance | Status: CONCERNS
- NFR-004 | Area: OPERABILITY | Target: VPS-only rollout under existing deployment transaction | Validation: Change Contract + later deployment evidence | Status: CONCERNS
