# Plan — issue #537 wave 1: durable road-event delivery receipts (API)

- Specification: specs/537-wave1-event-delivery-receipts/spec.md
- Issue: #537
- Date: 2026-10-19

## Architecture

Wave 1 lives entirely in the VPS API contour (`api/**`) plus its tests; the
worker outbox is wave 2 and is intentionally untouched here.

- `event_receipts` table (WAL state database, additive-at-boot):
  `event_id TEXT PRIMARY KEY, camera_id, content_hash, snapshot_hash,
  response_event_json, completed_at` + `completed_at` index. Receipts are
  deliberately NOT pruned with the per-camera-capped feed; only the 90-day
  retention sweep touches them.
- `event_feed.event_id` nullable column, backfilled from stored payloads;
  plain UNIQUE index `idx_event_feed_event_id` created only when history is
  conflict-free; duplicate historical ids are inventoried in
  `migration_inventory` and never deleted.
- `store.deliver_event` — one transaction: receipt check → conflict-targeted
  feed insert (`ON CONFLICT(event_id) DO NOTHING`) → per-camera feed cap →
  receipt insert; degraded no-index fallback does an explicit stored-row
  comparison and legacy blind append; `EventDeliveryConflict` aborts the
  transaction with no partial state.
- `store.atomic_write_bytes` — unique same-directory tmp, flush+fsync,
  `os.replace`, directory fsync, tmp removed on failure.
- `store.event_content_fingerprint` — SHA-256 over canonical JSON
  (sorted keys, compact separators) of the normalized event; retry-only
  transport metadata stays external (RETRY_ONLY_FIELDS boundary).
- `store.safe_event_filename` — traversal-safe deterministic filename;
  safe-shaped ids verbatim, anything else falls back to a sha256 digest
  prefix, so verbatim retries rebuild the same snapshot_url.
- `main.post_analytics_event` — ingest sequence per spec FR-004: gates →
  fingerprint → receipt pre-check → `EVENT_INGEST_LOCK` + re-check → atomic
  snapshot publish → registry persist (existing idempotent path, return
  value interpreted as crash-repair, not failure) → `deliver_event` →
  409 on conflict → additive `duplicate` response field.
- `analytics.sweep_events_media` — additionally sweeps orphaned
  `*.tmp` siblings (interrupted atomic writes) with the existing grace
  window; `.jpg` reference semantics unchanged.
- `store.append_event` — populates the nullable `event_id` so the legacy
  blind append participates in the feed's unique identity.

## Decisions

- D-001: Plain UNIQUE index `idx_event_feed_event_id` instead of a partial
  index. A partial index (`WHERE event_id IS NOT NULL`) is not a valid
  conflict target for `INSERT ... ON CONFLICT(event_id)` on SQLite
  (empirically verified on SQLite 3.46.1); the plain form provides both
  mandated properties — non-NULL uniqueness AND conflict-targeted
  DO NOTHING inserts. NULLs-distinct semantics are acceptable because the
  column is backfilled at migration and all new delivery writes set it;
  legacy rows without an event_id remain legal.
- D-002: Receipts outlive feed pruning and are retained 90 days (owner
  decision, issue #537 Outcome Contract, 2026-10-19). Residual risk: a
  retry arriving more than 90 days after the completed delivery finds no
  receipt and is treated as new; the feed's unique event_id index still
  prevents a duplicate row while the capped original row survives.
  Documented in spec and code; explicitly accepted.
- D-003: A receipt hit does NOT reinsert the pruned feed row — the feed
  stays a bounded recent-history view; the receipt is the durable
  completion record (design §3).
- D-004: The registry persist return value is treated as crash-repair
  input, not failure. The previous behavior raised 422
  "snapshot is required" when the registry reported an existing identity —
  misleading UX for what is actually a duplicate/completed delivery; the
  corrected path completes the missing feed/receipt pieces instead. The
  422 pin itself is preserved verbatim for the genuinely missing-snapshot
  case.
- D-005: Content/camera conflicts return 409 via
  `store.EventDeliveryConflict` conversion in the handler; the conflict
  aborts the store transaction so no partial state is committed and the
  delivery stays worker-visible as unconfirmed.
- D-006: Receipt retention pruning runs inline per successful
  non-duplicate delivery (`prune_event_receipts`) instead of a background
  thread: one indexed DELETE on `completed_at`, no scheduler surface, no
  new runtime component in wave 1.
- D-007: Same-ID ingestion is serialized per process via a module-level
  `EVENT_INGEST_LOCK` with a receipt re-check inside the lock; residual
  cross-process races are settled by the receipt check plus the feed's
  unique index inside the single `deliver_event` transaction.

## Affected contours

- VPS (`api/**`): `api/app/store.py`, `api/app/main.py`,
  `api/app/analytics.py`; tests `tests/test_api_state_transaction.py`,
  `tests/test_road_event_delivery.py` (new); SDD trio.
- Ubuntu worker/relay update: NOT REQUIRED for wave 1 (old worker + new API
  are compatible: the additive `duplicate` response field is ignored by the
  existing success-print parsing; responses remain HTTP 200 `ok`).
- Windows worker: retired, not applicable.

## Validation

- Focused suites: `python3 -m pytest tests/test_road_event_delivery.py
  tests/test_api_state_transaction.py -q` → 57 passed / 1 skipped.
- RED authenticity: both suites executed against base `27107db0` in a
  detached worktree → 37 behavioral failures / 20 pre-existing passes;
  per-test reasons verified behavioral (no duplicate field, 422≠409,
  base reuses the 422 detail on retry, thread 422s, sweep not cleaning tmp,
  AttributeErrors for new capability).
- Full battery (recorded in issue #537): `python3 -m pytest tests/ -q`,
  `ruff check --config scripts/quality/ruff.toml .`,
  `python3 scripts/ci/validate_sdd.py` (repo-wide + PR-fixture event),
  `python3 scripts/ci/validate_repo.py`.

## Runtime feedback

- Post-deploy probes are recorded in issue #537 after the lane-A VPS
  deploy: duplicate delivery collapsed, receipt answered after feed
  pruning, migration over the live database, 409 conflict visibility.

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: DATA | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: additive-at-boot migration inventories duplicate historical event_ids and never deletes/rewrites retained history; unique index deferred on degraded databases; explicit stored-row fallback keeps duplicate gating active | Validation: EventFeedMigrationTests (backfill, idempotent re-run, inventory, index deferral) | Residual risk: degraded databases run without the feed unique index until history is reconciled | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: DATA | Probability: 1 | Impact: 4 | Score: 4 | Mitigation: 90-day retention documented in code, spec and issue Outcome Contract; feed unique index still gates duplicates while the original row survives | Validation: ReceiptRetentionTests | Residual risk: a retry arriving more than 90 days after completion is treated as a new delivery | Owner: product owner (accepted 2026-10-19) | Status: ACCEPTED
- RISK-003 | Category: TECH | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: plain UNIQUE index chosen over partial index after empirical verification of the ON CONFLICT conflict-target constraint; covered by store-level tests | Validation: EventReceiptStoreTests unique-index cases | Residual risk: none known | Owner: delivery orchestrator | Status: MITIGATED
- RISK-004 | Category: PERF | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: per-delivery work is one indexed receipt lookup + one indexed insert; prune is one indexed DELETE; no background scheduler | Validation: full suite; ingest-path code review | Residual risk: WAL growth proportional to delivered events (bounded by retention) | Owner: delivery orchestrator | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: delivery plan orders API-first (this PR) before the wave-2 worker outbox; old worker + new API are compatible (additive duplicate field, unchanged 200 ok shape) | Validation: legacy-response compatibility + water-path tests; issue #537 Outcome Contract rollout plan | Residual risk: none in wave 1 (worker retry behavior does not exist yet) | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: integration | Priority: P0 | Evidence: tests/test_road_event_delivery.py DuplicateDeliveryTests (stored success, single registry object) + EventReceiptStoreTests
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: DuplicateAfterPruneTests.test_receipt_prevents_reinsertion_after_feed_pruning
- TEST-003 | Covers: AC-003, AC-004 | Level: integration | Priority: P0 | Evidence: ConflictTests (content, metadata, camera, feed-row-without-receipt → 409, no partial state)
- TEST-004 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: AtomicSnapshotTests + AtomicWriteBytesTests (failed replace/fsync, no tmp, retry succeeds)
- TEST-005 | Covers: AC-006 | Level: integration | Priority: P0 | Evidence: CrashRepairTests (both crash directions complete missing pieces)
- TEST-006 | Covers: AC-007 | Level: integration | Priority: P1 | Evidence: ConcurrentDuplicateTests (8 threads, exactly one stored)
- TEST-007 | Covers: AC-008 | Level: integration | Priority: P0 | Evidence: EventFeedMigrationTests (backfill, idempotency, inventory without deletion, index creation/deferral, degraded fallback)
- TEST-008 | Covers: AC-009 | Level: unit | Priority: P1 | Evidence: ReceiptRetentionTests (only old receipts removed; feed/crossings untouched)
- TEST-009 | Covers: AC-010, AC-011 | Level: integration | Priority: P1 | Evidence: DuplicateDeliveryTests.test_person_gate_response_is_preserved_verbatim; LegacyResponseCompatibilityTests (payload shape, water camera path)
- TEST-010 | Covers: AC-012 | Level: unit | Priority: P2 | Evidence: SweepOrphanTmpTests + sweep assertions in test_api_state_transaction.py
- TEST-011 | Covers: AC-001..AC-012 | Level: integration | Priority: P0 | Evidence: RED authenticity run on base 27107db0 (37 behavioral failures, 20 regression-guard passes)

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: not applicable (no mutation) | Evidence: canonical issue #537 Outcome Contract with owner OUTCOME APPROVED recorded 2026-10-19; six-field scope and allowed paths enforced before the first write
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged; branch not created | Retry: NO | Rollback: not applicable (no mutation) | Evidence: base 27107db05da44e57b8b6a63139f1ee4c322ceaae verified clean; branch 537-wave1-event-delivery-receipts created from the exact base
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: uncommitted working tree on the task branch; main untouched | Retry: YES (re-edit in the working tree) | Rollback: discard working-tree changes (`git checkout -- .` + branch delete) | Evidence: api/app/store.py, api/app/main.py, api/app/analytics.py, tests/test_api_state_transaction.py, tests/test_road_event_delivery.py, this SDD trio
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: implementation stays uncommitted; defect reported to the orchestrator | Retry: YES (fix + re-run battery) | Rollback: not applicable (no mutation) | Evidence: full pytest suite, ruff canon, validate_sdd (repo-wide + PR-fixture event), validate_repo — outputs recorded in issue #537
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: task branch commits rolled back to the branch point; main untouched | Retry: YES (re-commit) | Rollback: `git reset` to the branch point on the task branch | Evidence: orchestrator-owned commits on 537-wave1-event-delivery-receipts (authorization: issue #537 Outcome Contract, OUTCOME APPROVED 2026-10-19)
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: scratch artifacts remain in /tmp/opencode only (sandbox-ephemeral, never in git) | Retry: YES | Rollback: not required (scratch only) | Evidence: RED worktree /tmp/opencode/p537-red added and removed; tool caches redirected to /tmp/opencode/toolcache
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: prior evidence cursors remain valid | Retry: YES (re-post evidence comment) | Rollback: not required (additive audit text) | Evidence: issue #537 status comments; PR Change Contract synchronized with the exact diff
- TX-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: main unchanged until merge; after merge the revert PR restores the previous behavior while receipts and additive columns are preserved | Retry: YES | Rollback: revert per PR (worker-first ordering applies only from wave 2; wave-1 rollback retains API dedupe safely because the old worker never retries) | Evidence: rollback plan in the issue #537 Outcome Contract
