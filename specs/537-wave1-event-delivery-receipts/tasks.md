# Tasks — issue #537 wave 1: durable road-event delivery receipts (API)

- Specification: specs/537-wave1-event-delivery-receipts/spec.md
- Issue: #537
- Date: 2026-10-19

## Delivery tasks

- [x] T-537-101 Recon: verify base `27107db05da44e57b8b6a63139f1ee4c322ceaae`, clean tree, create branch `537-wave1-event-delivery-receipts`; map store/main/analytics anchors.
- [x] T-537-102 `api/app/store.py`: `event_receipts` schema + retention index; additive-at-boot migration (nullable `event_feed.event_id`, backfill, duplicate inventory without deletion, deferred/created unique index); `deliver_event` single transaction with degraded fallback; `atomic_write_bytes`; `event_content_fingerprint`; `safe_event_filename`; `find_event_receipt`; `prune_event_receipts` (90 days); `append_event` populates `event_id`.
- [x] T-537-103 `api/app/main.py` `post_analytics_event`: ingest sequence per FR-004 (fingerprint → receipt pre-check → lock + re-check → atomic snapshot publish → registry crash-repair → `deliver_event` → 409 conversion → additive `duplicate` response); person gate and 422 pins preserved verbatim.
- [x] T-537-104 `api/app/analytics.py` `sweep_events_media`: orphaned `*.tmp` sibling sweep with the existing grace window; `.jpg` semantics unchanged.
- [x] T-537-104 `tests/test_api_state_transaction.py`: store-level receipt, migration, retention, atomic-write and identity-helper test classes.
- [x] T-537-105 `tests/test_road_event_delivery.py` (new): 16 handler-level fault-injection tests (duplicate collapse, post-prune receipt, conflicts 409, atomic publish, crash repair both directions, 8-thread concurrency, person gate verbatim, sweep tmp, legacy payload compat, water camera path).
- [x] T-537-106 RED authenticity: both suites executed against base `27107db0` in a detached worktree — 37 behavioral failures / 20 pre-existing passes; per-test reasons verified behavioral; worktree removed afterwards.
- [x] T-537-107 Focused suites green: `pytest tests/test_road_event_delivery.py tests/test_api_state_transaction.py -q` → 57 passed / 1 skipped.
- [x] T-537-108 SDD trio authored (this directory) against the validate_sdd contract.
- [ ] CI green on exact head — orchestrator-owned: full battery (full pytest suite, ruff canon, validate_sdd repo-wide + PR-fixture event, validate_repo) recorded in issue #537, then branch commits + PR.
- [ ] exact-head PR CI — orchestrator-owned (PR creation and required checks).
- [ ] Lane-A VPS deploy of the merged exact head — orchestrator-owned (DEPLOY-TRIGGER with owner chat confirmation per lane A).
- [ ] Post-deploy probes recorded in issue #537 (duplicate collapse, receipt after prune, migration over the live database, 409 visibility) — orchestrator-owned.

## Completion gate

- All four verification channels green: full pytest suite, ruff canon, validate_sdd, validate_repo.
- PR Change Contract declares exact changed files, Risk profile: REQUIRED, production impact and VPS deployment REQUIRED / worker NOT REQUIRED.
- Independent review completed before PR; peer verification recorded before merge.
- Merge = exact-green-head only; post-merge freshness auto-sync applies.

## Requirements traceability

- AC-001 | Task: T-537-102,T-537-103,T-537-105 | Evidence: DuplicateDeliveryTests (stored success, single registry object) + EventReceiptStoreTests (one feed row + one receipt) | Coverage: COVERED
- AC-002 | Task: T-537-102,T-537-105 | Evidence: DuplicateAfterPruneTests.test_receipt_prevents_reinsertion_after_feed_pruning | Coverage: COVERED
- AC-003 | Task: T-537-102,T-537-103 | Evidence: ConflictTests.test_same_id_different_snapshot_content_is_409_without_partial_state + test_same_id_different_metadata_is_409 + test_feed_row_conflict_without_receipt_is_409 | Coverage: COVERED
- AC-004 | Task: T-537-102,T-537-103 | Evidence: ConflictTests.test_same_id_different_camera_is_409 | Coverage: COVERED
- AC-005 | Task: T-537-102,T-537-103 | Evidence: AtomicSnapshotTests (failed publish leaves no partial file/tmp and no receipt, retry succeeds; exact bytes published, no tmp) + AtomicWriteBytesTests | Coverage: COVERED
- AC-006 | Task: T-537-102,T-537-103 | Evidence: CrashRepairTests (retry completes feed+receipt after snapshot+registry; retry completes snapshot+feed+receipt after registry-only persist) | Coverage: COVERED
- AC-007 | Task: T-537-103,T-537-105 | Evidence: ConcurrentDuplicateTests.test_concurrent_duplicates_produce_exactly_one_stored_delivery (8 threads) | Coverage: COVERED
- AC-008 | Task: T-537-102 | Evidence: EventFeedMigrationTests (backfill, idempotent re-run, duplicate inventory without deletion, index deferral, index creation on clean history) + degraded fallback in EventReceiptStoreTests | Coverage: COVERED
- AC-009 | Task: T-537-102 | Evidence: ReceiptRetentionTests (only old receipts removed; feed and crossings untouched) | Coverage: COVERED
- AC-010 | Task: T-537-103,T-537-105 | Evidence: DuplicateDeliveryTests.test_person_gate_response_is_preserved_verbatim | Coverage: COVERED
- AC-011 | Task: T-537-103,T-537-105 | Evidence: LegacyResponseCompatibilityTests (payload shape ok-compatible; water camera path unchanged) | Coverage: COVERED
- AC-012 | Task: T-537-103 | Evidence: SweepOrphanTmpTests.test_sweep_cleans_orphan_tmp_and_keeps_everything_else | Coverage: COVERED

## Definition of Done

- [x] Issue/spec/plan/tasks current
- [x] Exact changed-file scope verified (api/app/store.py, api/app/main.py, api/app/analytics.py, tests/test_api_state_transaction.py, tests/test_road_event_delivery.py, specs/537-wave1-event-delivery-receipts/**; config.py untouched — receipt constant lives in store.py)
- [x] Required tests and evidence complete (16 handler + 42 store-level tests; RED run on base 27107db0: 37 behavioral failures / 20 regression-guard passes)
- [ ] CI gate: Required CI green on the exact PR head — orchestrator-owned
- [ ] merge gate: Exact-green-head merge complete — orchestrator-owned
- [ ] state gate: Deployment state resolved — lane-A VPS deploy per the issue #537 Outcome Contract — orchestrator-owned
- [ ] runtime gate: Runtime acceptance resolved — post-deploy external probes recorded in issue #537 — orchestrator-owned
- [x] Deferred work recorded — wave 2 (worker outbox, entrypoint seam, publisher, heartbeat metrics) is a separate PR per the issue #537 delivery plan
- [x] Risks resolved or explicitly accepted — RISK-001..RISK-005 in plan.md Risk profile
- [x] Waivers resolved or current — none
