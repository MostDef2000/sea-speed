# Feature Specification: Storage retention policy

- Feature: 038-storage-retention-policy
- Issue: #261
- Status: Source implementation

Runtime contour: VPS

## Product outcome

The objects registry retains up to 100 newest records per domain (water and
road independently), event snapshots under `media/events/` no longer grow
without bound, and passage mirror rows in the objects registry are removed
together with their source passage so the two registries never diverge.

## User scenarios

1. A road camera produces many events while water is quiet: water keeps its
   own newest 100 registry records and road keeps its own newest 100; neither
   domain can evict the other's rows.
2. The API runs for months: every analytics-event snapshot lands in
   `media/events/`; a sweep deletes files that no live registry row references
   and that are older than 24 hours (grace period protects files whose DB row
   is being written concurrently). Startup also sweeps once.
3. The passages registry prunes an old completed passage at its 300 limit:
   the mirror row `passage-<id>` disappears from the objects registry in the
   same flow; a startup reconciliation removes any orphan mirrors left by
   earlier versions.

## Requirements

- R1: `prune_objects_registry` MUST retain the newest `OBJECTS_RETENTION_LIMIT`
  (100) rows per distinct `domain`, partitioning by `domain` and ordering by
  `detected_at DESC, object_id DESC`.
- R2: Pruning MUST return the snapshot URLs of evicted rows so media cleanup
  can run after the DB transaction.
- R3: An events-media sweep MUST delete `.jpg` files directly under
  `EVENTS_MEDIA_DIR` only when both conditions hold: the file's URL is not
  referenced by any remaining objects row AND file mtime age exceeds 24 hours.
  Non-jpg files and path-traversal names are ignored.
- R4: The sweep MUST run once at API startup and afterwards at most once per
  hour (in-process throttle) after inserts/prunes.
- R5: When water passages are pruned from the passages registry, their mirror
  rows (`passage-<passage_id>`) MUST be deleted from the objects registry
  within the same request flow.
- R6: At startup, reconciliation MUST delete mirror rows whose source passage
  no longer exists.

### NFR assessment

- NFR-038-001 | Area: PERF | Target: prune stays a single SQL statement; sweep scan cost bounded by directory size and throttled to <=1 run/hour after startup | Validation: unit tests assert prune correctness; throttle logic unit-tested without sleeps | Evidence: tests/test_storage_retention.py | Status: PASS
- NFR-038-002 | Area: REL | Target: media deletion failures never fail the API request that triggered pruning | Validation: unlink errors swallowed with stderr log; unit test with unwritable dir | Evidence: tests/test_storage_retention.py::test_media_sweep_survives_errors | Status: PASS
- NFR-038-003 | Area: COMPAT | Target: /api/cam1/passages and /api/analytics/*/events response contracts unchanged | Validation: existing suites green; no handler signature changes | Evidence: full unittest discovery green | Status: PASS
- NFR-038-004 | Area: SEC | Target: sweep cannot delete outside EVENTS_MEDIA_DIR; filename validated like cleanup_passage_media | Validation: unit test with traversal-style name asserts file untouched | Evidence: tests/test_storage_retention.py::test_media_sweep_ignores_unsafe_names | Status: PASS
- NFR-038-005 | Area: DATA | Target: no data loss beyond declared retention policy (100/domain objects, 300 passages, grace-period-guarded media) | Validation: retention tests verify newest-per-domain survival | Evidence: tests/test_api_contract.py updated retention tests | Status: PASS

## Acceptance criteria

- AC-001: Inserting 150 water + 150 road rows leaves exactly 100 newest water
  and 100 newest road rows.
- AC-002: Evicted rows' snapshot URLs are returned by prune and their files
  are deleted when unreferenced and older than the grace period.
- AC-003: Recent (within grace period) unreferenced snapshots are NOT deleted.
- AC-004: Sweep ignores non-jpg files and unsafe filenames.
- AC-005: Sweep runs at startup and is throttled to one run per hour.
- AC-006: Pruning passages at the 300 limit removes corresponding mirror rows
  from the objects registry.
- AC-007: Startup reconciliation removes mirrors whose passage no longer
  exists and keeps mirrors whose passage exists.
- AC-008: Full local unittest suite passes.
- AC-009: Both required CI checks pass on exact PR head.
- AC-010: Post-deploy runtime verification via UI: water and road each retain
  their own newest records; media/events growth bounded.
- AC-011: Change Contract matches final diff exactly.

## Runtime feedback

None yet; record production observations after deployment.
