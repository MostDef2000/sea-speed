# Feature Specification: Unified objects registry

- Feature: 037-unified-objects-registry
- Issue: #259
- Status: Source implementation

Runtime contour: VPS

## Product outcome

Water passages observed by the water analytics pipeline are persisted into the
objects registry with the same reliability as road events, so the registry at
`/sea-speed/objects/` shows both domains. The registry is a single contour: the
domain selector is enabled and clickable, entry from a domain page pre-selects
that domain, and the operator can switch domains in place without navigating to
a different URL contour.

## User scenarios

1. A vessel passes the water ROI; the worker posts the passage to
   `POST /api/cam1/passages`. The passage appears in the objects registry under
   `domain=water` with class, speed (when measured), confidence and snapshot.
2. Repeated passage updates (tracking -> measuring -> measured -> completed)
   refresh source-derived fields of the same registry row without duplicating
   rows and without clobbering operator-entered status/comment.
3. An operator opens the registry from the water page: the water domain is
   pre-selected. They switch the domain selector to `road` in place; title,
   filters, URL query and listing update without a page navigation pattern
   change.
4. Existing historical passages are mirrored into the objects registry once at
   API startup (idempotent backfill).

## Requirements

- R1: Successful water passage upsert MUST mirror the passage into the objects
  registry (`persist_passage_object`) with stable object id
  `passage-<passage_id>`, `camera_id=cam1`, `domain=water`,
  `analytics_profile=water-v1`.
- R2: Registry mirroring MUST be idempotent per passage id and MUST update
  source-derived fields (class_name, confidence, speed_kmh, snapshot_url,
  original_event_json, updated_at) on later passage updates via ON CONFLICT.
- R3: Operator-owned fields (status, comment) MUST NOT be overwritten by
  passage mirroring.
- R4: Passage deletion/pruning from the water-passage registry MUST NOT delete
  or mutate the mirrored objects-registry row (registry row keeps its own
  lifecycle under existing retention pruning).
- R5: At startup the API MUST backfill existing water passages into the
  objects registry idempotently (`import_existing_passages`).
- R6: The registry page MUST enable the domain select; changing it switches
  scope in place: header texts, camera/domain filter values, scope label,
  document title, URL `scope` query param, pagination reset and data reload.
- R7: Entry-point pre-selection (referrer road -> road, otherwise water;
  explicit `?scope=` wins) MUST be preserved.
- R8: The registry page nav MUST expose one registry link instead of two
  domain-scoped links.

## NFR assessment

| ID | Area | Requirement | Status | Evidence |
| --- | --- | --- | --- | --- |
| NFR-037-001 | Performance | Mirroring adds one SQLite statement per passage POST; no polling loops introduced | PASS | tests/test_unified_registry.py timing-free assertions; single-statement ON CONFLICT design |
| NFR-037-002 | Reliability | Mirror failures MUST NOT fail the passage POST response contract for callers (mirror wrapped so passage result is unchanged on mirror error logged to stderr) | PASS | try/except around mirror call; unit test asserts passage ok even when mirror raises |
| NFR-037-003 | Compatibility | `/api/cam1/passages` request/response contract unchanged; objects API filters already support `domain` | PASS | no signature changes; existing tests green |
| NFR-037-004 | Security | No new endpoints, no auth changes, no secrets; mirror runs inside existing authenticated handler | PASS | diff review; auth unchanged |
| NFR-037-005 | Data integrity | Stable ids prevent duplicates across restarts/backfill | PASS | idempotency unit tests |

## Acceptance criteria

- AC-001: POSTing a water passage results in an objects-registry row with
  `object_id=passage-<id>`, `domain=water`, `camera_id=cam1`.
- AC-002: A second POST of the same passage with improved speed does not create
  a second row; the row's `speed_kmh` reflects the newer value.
- AC-003: Operator status/comment edits survive subsequent passage mirroring.
- AC-004: Startup backfill imports existing passages exactly once across
  repeated starts.
- AC-005: Objects listing filtered by `domain=water` returns mirrored passages.
- AC-006: Domain selector on the registry page is enabled and switching it
  updates scope-dependent UI and reloads data in place.
- AC-007: Referrer-based pre-selection still works (road referrer -> road).
- AC-008: Registry page nav contains a single registry link.
- AC-009: Full local unittest suite passes.
- AC-010: Both required CI checks pass on exact PR head.
- AC-011: Post-deploy runtime verification: a real water passage appears in the
  registry (or seeded verification passage), domain switch works in production
  UI.
- AC-012: Change Contract matches final diff exactly.

## Runtime feedback

None yet; record production observations here after deployment.
