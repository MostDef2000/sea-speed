# Spec: Registry hygiene — reject objects without photo (road + water)

- Issue: #283
- Status: ACTIVE
- Runtime contour: MIXED

## Product outcome

Registry on `mostdef.ru/sea-speed/objects` must not contain useless records with «Фотография отсутствует». For both domains — road `road1` (analytics events → objects) and water `cam1` (passages → objects) — an object is persisted only when a valid `snapshot_url` (`/sea-speed/media/...`) is present. Requests without a snapshot are rejected/not persisted. Existing snapshot-less records are soft-deleted and no longer returned by API/UI. Investigation covers water — same guard applies.

## User scenarios

- Road camera posts a detection but snapshot write fails → no registry card appears; worker logs the failure and does not create a «Фотография отсутствует» entry.
- Water passage tracking creates a vessel event without photo → no registry entry is created.
- Operator opens Objects registry (Road or Water) → never sees «Фотография отсутствует» cards; every card shows a photo.
- Existing polluted records from before the fix disappear after deploy (soft-deleted).

## Requirements

- R1: `persist_object_event` persists only when `snapshot_url` is a non-empty `/sea-speed/media/...` URL.
- R2: `persist_passage_object` persists only when `snapshot_url` is present.
- R3: `POST /api/analytics/{camera_id}/events` requires a `snapshot` file; missing snapshot → 422 and no object persisted. Covers both `cam1` and `road1`.
- R4: `POST /api/cam1/passages` requires a snapshot for new passages; incremental update of an existing passage may reuse its stored snapshot.
- R5: Worker `post_event`/`post_passage` only posts when snapshot file was successfully written and exists.
- R6: Existing objects with `snapshot_url IS NULL OR ''` and `deleted_at IS NULL` are soft-deleted (or excluded) — count becomes 0 for both cameras.

## NFR assessment

- NFR-045-001 | Area: correctness | Target: zero snapshot-less objects after deploy; no new snapshot-less objects creatable via API | Validation: unit tests for persist guards + API 422 tests | Evidence: tests/test_api_contract.py::NoPhotoGuardTests, tests/test_water_passage.py | Status: PASS
- NFR-045-002 | Area: reliability | Target: no silent data loss — legitimate detections with valid snapshots are unaffected | Validation: existing persist tests still pass when snapshot present | Evidence: tests/test_api_contract.py | Status: PASS
- NFR-045-003 | Area: operability | Target: cleanup is idempotent and safe to rerun | Validation: migration test with mixed records | Evidence: unit test | Status: PASS

## Acceptance criteria

- AC-001: POST event without snapshot returns 422 and does not create an object.
- AC-002: POST passage without snapshot for a new passage_id returns 422 and does not create a passage or object.
- AC-003: `persist_object_event` / `persist_passage_object` return false when snapshot_url missing.
- AC-004: Worker does not attempt POST when snapshot file missing/write failed.
- AC-005: After deploy, `GET /api/cam1/objects` and `GET /api/analytics/road1/objects` contain zero records with empty snapshot_url; UI shows no «Фотография отсутствует».
- AC-006: Existing polluted records are soft-deleted (deleted_at set) and excluded from counts.

## Runtime feedback

To be recorded after both-contour deployment acceptance.
