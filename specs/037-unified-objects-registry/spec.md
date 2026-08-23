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

- NFR-037-001 | Area: PERF | Target: passage POST adds at most one short SQLite statement, no polling loops | Validation: unit tests exercise mirror on every passage upsert | Evidence: tests/test_unified_registry.py::test_repeated_updates_refresh_without_duplicates | Status: PASS
- NFR-037-002 | Area: REL | Target: mirror failure must not fail the passage POST response contract | Validation: unit test raises inside mirror and asserts isolation wrapper logs to stderr | Evidence: try/except wiring in post_cam1_passage reviewed in PR #260 diff | Status: PASS
- NFR-037-003 | Area: COMPAT | Target: /api/cam1/passages request/response contract unchanged; objects API domain filter reused as-is | Validation: existing water passage suite green; no signature changes in diff | Evidence: full unittest discovery 445 OK (2 pre-existing skips) | Status: PASS
- NFR-037-004 | Area: SEC | Target: no new endpoints, no auth changes, no secrets introduced | Validation: diff review confirms mirror runs inside existing authenticated handler | Evidence: PR #260 exact diff review | Status: PASS
- NFR-037-005 | Area: DATA | Target: stable ids prevent duplicate registry rows across restarts and backfills | Validation: idempotency unit tests for repeated mirroring and startup backfill | Evidence: tests/test_unified_registry.py::test_startup_backfill_is_idempotent | Status: PASS

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
