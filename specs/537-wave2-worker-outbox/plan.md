# Plan — issue #537 wave 2: worker durable outbox (worker)

- Specification: specs/537-wave2-worker-outbox/spec.md
- Issue: #537
- Date: 2026-10-21

## Architecture

Wave 2 lives in the Ubuntu worker/relay contour plus its convergence lists and
tests; the VPS API is untouched (wave-1 receipts are merged and define the
server contract this wave consumes).

- `worker/worker_outbox.py` (new): SQLite WAL outbox for the road event
  contour. Rows hold the event_id, camera_id, byte-verbatim metadata JSON
  string and snapshot JPEG bytes as a BLOB plus bookkeeping (creation time,
  last attempt, per-row error counters). Schema init is EXPLICIT at outbox
  open — never lazily from a publisher-thread path (wave-1 "lazy migration"
  gotcha, KB INFRASTRUCTURE.md gotcha #34). Single database file for the road
  contour, default `shared/road-runtime/road-worker-outbox.sqlite3` alongside
  the road heartbeat, override `SEA_SPEED_OUTBOX_DB`.
- Accept path (entrypoint seam): `post_event` enriches metadata exactly as
  today, reads the snapshot JPEG bytes at enqueue time (file-based snapshots
  rotate later) and persists metadata + bytes in ONE transaction; True is
  returned only after durable acceptance. Disk-full/SQLite write failure
  returns False (fail-closed, worker keeps its file-based behavior). The
  in-memory event queue (maxsize 32, consumer swallows exceptions) is retired
  from the event path — the outbox is the durable queue.
- Publisher: single daemon thread delivering rows FIFO; bounded exponential
  backoff (base 1s, factor ×2, cap 60s) with jitter from an injectable seeded
  RNG (deterministic tests); NO attempt-based discard; on worker start the
  outbox is reopened and pending rows are published with no new detections
  (restart recovery).
- HTTP client: the outbox posts with its own requests-based client
  (`worker/worker_transport.py` untouched/protected — it does not expose the
  response body): same URL derivation (`SEA_SPEED_API_URL` →
  `/api/analytics/{camera_id}/events`), Bearer `SEA_SPEED_API_TOKEN`, multipart
  `metadata` (byte-verbatim JSON string) + `snapshot` file. Response handling
  per spec FR-007 (200 confirm → delete-on-confirm; 200 `duplicate=true` →
  confirmed; 200 `{"ok": true, "event": null}` → terminal success; 409 →
  terminal accept-error, counter + retained row; anything else → send error,
  retry with backoff).
- Heartbeat metrics (additive only): worker stdout markers for pending count,
  oldest-unconfirmed age, send errors, retries, accept errors, last confirmed;
  `deploy/worker/ubuntu/observed-worker-runner.py` gains additive
  `record_line` branches + state keys; `deploy/worker/ubuntu/check-worker-health.py`
  gains additive report fields; `schema_version` stays 1
  (`verify-runtime-progression.py` and
  `tests/test_ubuntu_worker_observability.py:178-182` keep passing).
- Convergence lists: `scripts/worker/check_ubuntu_compatibility.py`
  `MODULE_SOURCES` union gains `worker/worker_outbox.py` (count pins 8→9 in the
  five module tests); the fail-closed installer/artifact lists gain
  `worker/worker_outbox.py` together (`deploy/worker/ubuntu/install-systemd.sh`,
  `scripts/quality/build_exact_artifacts.py`,
  `scripts/quality/validate_exact_artifacts.py`, `scripts/ci/validate_repo.py`);
  `scripts/ci/validate_sdd.py` grandfathered prefix-collision set gains the
  "537" wave set (second `537-*` spec directory).

## Decisions

- D-101: `worker_outbox.py` joins the Ubuntu compatibility gate
  `MODULE_SOURCES` union (`scripts/worker/check_ubuntu_compatibility.py:26-35`)
  → five count pins 8→9 (`tests/test_worker_transport_module.py:371-375`,
  `tests/test_worker_crossings_module.py:476`,
  `tests/test_worker_live_module.py:536`,
  `tests/test_worker_tracking_module.py:495`,
  `tests/test_worker_roi_module.py:632`) and the union gains
  `worker/worker_outbox.py`. Established wave pattern (#397 waves 4-9).
- D-102: `worker_outbox.py` issues its own HTTP post;
  `worker/worker_transport.py` stays untouched/protected (consume only — it
  does not expose the response body, which the outbox needs to discriminate
  confirm / duplicate / person-filter / 409). Import policy for the new
  module: stdlib (json, time, pathlib, hashlib, sqlite3, threading) + requests
  only — declared in the module docstring per the guarded-import test
  convention used by the worker_*.py modules (e.g. the transport allowlist
  docstring guarded by `tests/test_worker_transport_module.py`). requests is
   already a pinned runtime dependency (`requirements-runtime.txt`,
   `runtime-lock.json`) — no new dependency. Amended (orchestrator ruling,
   2026-10-21): the implemented allowlist is stdlib json, time, pathlib,
   hashlib, sqlite3, threading, os, random + guarded requests — `os` is
   required for the `SEA_SPEED_OUTBOX_DB` override and the FR-006
   URL/token env derivation, `random` for the FR-005 default jitter source.
- D-103: outbox DB is a single SQLite file for the road contour, default
  `shared/road-runtime/road-worker-outbox.sqlite3` alongside the road
  heartbeat, overridable via `SEA_SPEED_OUTBOX_DB`; schema init is EXPLICIT at
  outbox open (never lazily from a publisher-thread path — wave-1 "lazy
  migration" gotcha, KB INFRASTRUCTURE.md gotcha #34); WAL mode; rows deleted
  on confirmed delivery (delete-on-confirm; the server keeps 90-day receipts,
  so local copies are not needed after confirmation).
- D-104: publisher backoff: base 1s, factor ×2, cap 60s, jitter; jitter must
  be injectable (seeded RNG) so tests are deterministic; NO attempt-based
  discard; 409 treated as terminal accept-error (counter + oldest-unconfirmed
  continues to reflect undelivered rows), not retried and not dropped silently.
- D-105: heartbeat metrics additive only: pending count, oldest-unconfirmed
  age, send errors, retries, accept errors, last confirmed — surfaced via
  worker stdout markers parsed by `observed-worker-runner.py` (additive
  `record_line` branches + state keys) and additive report fields in
  `check-worker-health.py`; `schema_version` 1 consumers
  (`verify-runtime-progression.py`,
  `tests/test_ubuntu_worker_observability.py:178-182`) must keep passing.
- D-106: entrypoint seam semantics change: `post_event` returns True only
  after durable outbox acceptance (metadata + snapshot bytes persisted);
  disk-full/SQLite write failure → seam returns False (fail-closed, worker
  keeps file-based behavior); enqueue-full no longer applies on the event path
  (the outbox is the durable queue; the in-memory queue is retired from the
  event path) while post_state coalescing, water passage posting, crossing
  queue and live envelopes are protected/out of scope and keep working
  unchanged.
- D-107: sync publish mode (`_is_sync_publish`, `SEA_SPEED_SYNC_PUBLISH`)
  keeps passthrough semantics (`tests/test_ubuntu_worker_runtime_provenance.py`
  pins).
- D-108: installer/artifact fail-closed lists gain `worker/worker_outbox.py`
  together: `deploy/worker/ubuntu/install-systemd.sh`,
  `scripts/quality/build_exact_artifacts.py`,
  `scripts/quality/validate_exact_artifacts.py`, `scripts/ci/validate_repo.py`
  — no artifact build or validator can silently drop the new module.
- D-109: snapshot bytes are captured at enqueue/acceptance time (JPEG read
  from the file-based snapshot before rotation can reclaim it) and stored as a
  BLOB; retries re-post the stored metadata JSON string and bytes verbatim so
  the server content fingerprint (SHA-256 of canonical normalized event JSON
  including camera_id/snapshot_url/created_at) is stable — verbatim retries
  collapse via receipts and never 409.
- D-110: the 409-person-filter nuance: `{"ok": true, "event": null}` for
  person-filtered road events is TERMINAL SUCCESS with nothing persisted
  server-side — the outbox deletes the row (nothing left to confirm) instead
  of treating it as an error.
- D-111: DEF-1 record (in-wave defect, discovered by the new fault-injection
  suite and fixed in-wave before PR): the lifetime heartbeat metric
  `outbox_retries_total` did not increment on successful re-deliveries (the
  confirmed branch of `_deliver` discarded the computed `new_retries`) nor on
  409-terminal re-deliveries (the terminal branch). Fixed with a guarded
  `if is_retry: _meta_increment("outbox_retries_total")` in both branches
  (+2 lines each, inside the existing per-delivery transaction;
  worker/worker_outbox.py:388-389 confirmed, :400-401 terminal at head
  8a51a07 — shifted by the D-112 fix commit). Pinned by
  tests `test_confirmed_retry_increments_lifetime_retries_metric` and
  `test_terminal_409_on_redelivery_increments_lifetime_retries_metric`
  (RED→GREEN verified: 1 failed / 20 passed and 1 failed / 21 passed against
  the pre-fix tree; both GREEN in the current tree). Correct-course Trigger
  stays NONE: the defect was found and remediated in-wave before PR with no
  scope/spec/plan change — the metric was already in scope as one of the
  FR-008 heartbeat fields.
- D-112: pre-merge validator REJECT resolved (both findings confirmed
  against the code; fix commit 8a51a07): (a) the outbox connection ran
  `PRAGMA synchronous=NORMAL`, which in WAL mode does not guarantee
  per-commit durability across power loss — spec user scenario 2 names power
  among the restart scenarios and AC-001 requires durable-before-report —
  switched to `PRAGMA synchronous=FULL` (fsync per commit; the enqueue rate
  is low, so correctness over throughput); (b) `_backoff_delay` evaluated
  the exponential factor BEFORE the 60s cap, so attempts-1 >= 1024 raised
  OverflowError — reachable during a long outage because the publisher
  retries indefinitely by design (no attempt-based discard) — the exponent
  is now clamped via `_BACKOFF_EXPONENT_CAP = 6` before the power, keeping
  the 1/2/4/8/16/32/60 envelope exact and unchanged. Both fixes pinned
  RED→GREEN: `test_pragma_synchronous_is_full_for_power_loss_durability`
  (tests/test_worker_outbox_module.py) and
  `test_backoff_survives_extreme_attempt_counts_without_overflow`
  (tests/test_worker_outbox_delivery.py).

## Affected contours

- Ubuntu worker/relay (`worker/**`, `deploy/worker/ubuntu/**`):
  `worker/worker_outbox.py` (new), `worker/ubuntu_worker_entrypoint.py` (seam),
  `deploy/worker/ubuntu/observed-worker-runner.py` +
  `deploy/worker/ubuntu/check-worker-health.py` (additive metrics),
  `deploy/worker/ubuntu/install-systemd.sh` (fail-closed list);
  `scripts/worker/check_ubuntu_compatibility.py`;
  `scripts/quality/build_exact_artifacts.py`,
  `scripts/quality/validate_exact_artifacts.py`; `scripts/ci/validate_repo.py`,
  `scripts/ci/validate_sdd.py` (grandfathered "537" prefix collision set);
  tests: new worker-outbox fault-injection suites + the five module count-pin
  suites 8→9; SDD trio.
- VPS (`api/**`): NOT REQUIRED — wave-1 receipts merged; the API contract is
  unchanged (200 `duplicate:true`, 409 conflicts, `{"ok": true, "event": null}`
  person-filter are already server behavior).
- Windows worker: retired, not applicable.

## Validation

- Focused suites: `python3 -m pytest tests/test_worker_outbox_delivery.py
  tests/test_worker_outbox_module.py -q` → 32 passed (23 + 9, incl. the two
  D-112 pins; observed on head 8a51a07).
- RED authenticity (executed): three neutralization shims — 409-terminal
  handling, backoff envelope, durable enqueue — and five fix-simulation
  shims, each FAIL under the shim and PASS without it; the two DEF-1 pins
  ran RED against the pre-fix tree (1 failed / 20 passed and 1 failed /
  21 passed observed) and are GREEN after the in-wave fix (D-111); the two
  D-112 pins ran RED→GREEN against the pre-8a51a07 tree (fix commit
  8a51a07).
- Regression guard: the five worker module-pin suites (count pins 9) and the
  protected-surface suites (tests/test_road_event_hygiene.py,
  tests/test_398_wave_a_demo.py, tests/test_api_contract.py,
  tests/test_ubuntu_worker_runtime_provenance.py,
  tests/test_ubuntu_worker_observability.py) run unmodified — 82 passed /
  6 subtests observed 2026-10-21; re-run green with the final battery on
  head 8a51a07 (below).
- Full battery (observed on head 8a51a07, orchestrator-observed; recorded in
  issue #537): 145 passed + 6 subtests across 14 suites;
  `ruff check --config scripts/quality/ruff.toml .` clean;
  `python3 scripts/ci/validate_sdd.py` green (repo-wide + PR-fixture event);
  `python3 scripts/ci/validate_repo.py` green (772 files); compatibility
  gate compatible=True; functional probe all-probes-OK; all 8 PR checks
  green on the exact head (CI runs 39468294685, 39468294700; Repository
  validation includes Change Contract validation on the exact diff).
- SDD-stage check (this order): `python3 scripts/ci/validate_sdd.py` repo-wide
  green after adding the grandfathered "537" prefix collision set to
  `scripts/ci/validate_sdd.py` (re-verified 2026-10-21 at reconciliation).

## Runtime feedback

- Pending: post-deploy probes are recorded in issue #537 after the lane-A
  Ubuntu worker/relay deploy (outage→recovery delivery, restart recovery,
  duplicate collapse, 409 visibility, heartbeat fields).

## Risk profile

- Risk profile: REQUIRED

- RISK-001 | Category: DATA | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: WAL mode plus explicit schema init at outbox open; a failed/corrupt open or disk-full write fails closed at the seam (`post_event` returns False, worker keeps file-based behavior) and never reports durable acceptance; DB path overridable via SEA_SPEED_OUTBOX_DB for operator recovery | Validation: disk-full and open-failure fault-injection tests (TEST-005) + restart recovery (TEST-004) | Residual risk: a corrupted outbox database requires operator intervention (SEA_SPEED_OUTBOX_DB override or archive+recreate); fail-closed acceptance bounds the loss window to the corruption window | Owner: delivery orchestrator | Status: MITIGATED
- RISK-002 | Category: DATA | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: schema init is EXPLICIT at outbox open and never lazily from a publisher-thread path (wave-1 "lazy migration" gotcha, KB INFRASTRUCTURE.md gotcha #34); init-at-open is a dedicated test case, restart recovery reuses the same open path | Validation: init-at-open + restart recovery tests (TEST-001, TEST-004) | Residual risk: none known | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 3 | Impact: 3 | Score: 9 | Mitigation: single publisher thread with bounded exponential backoff (base 1s, factor ×2, cap 60s, seeded jitter) — no per-event retry threads, no attempt-based discard; steady-state retry load during a prolonged outage is one attempt per 60s for the head row | Validation: backoff-bounds fault-injection test (TEST-006) | Residual risk: bounded retry load (head row retried at most once per 60s) for the duration of an outage | Owner: delivery orchestrator | Status: MITIGATED
- RISK-004 | Category: DATA | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: 409 is a terminal accept-error — never retried, never dropped silently; the accept-error counter plus the retained row keep it visible via heartbeat metrics (pending count, oldest-unconfirmed age, accept errors) | Validation: 409 fault-injection test (TEST-007) + heartbeat metric tests (TEST-009) | Residual risk: resolving a 409 row requires operator action by design (loud, not silent); the row ages in oldest-unconfirmed until then | Owner: delivery orchestrator | Status: MITIGATED
- RISK-005 | Category: OPS | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: heartbeat metrics are additive only — new record_line branches + state keys + report fields, schema_version stays 1; verify-runtime-progression.py and tests/test_ubuntu_worker_observability.py:178-182 must keep passing | Validation: observability + provenance suites (TEST-009, TEST-012) | Residual risk: none known | Owner: delivery orchestrator | Status: MITIGATED
- RISK-006 | Category: TECH | Probability: 2 | Impact: 5 | Score: 10 | Mitigation: road publication gate latch, event_id composition, worker_transport.py and the string pins are untouched; the joined-worker-source string pins are monotone under file addition (tests/support/worker_source.py join); sync-publish passthrough preserved; existing suites run unmodified as the regression guard | Validation: full pytest incl. tests/test_road_event_hygiene.py, tests/test_398_wave_a_demo.py, tests/test_api_contract.py, tests/test_ubuntu_worker_runtime_provenance.py (TEST-012) | Residual risk: none known | Owner: delivery orchestrator | Status: MITIGATED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_worker_outbox_delivery.py OutboxDurabilityTests.test_enqueue_persists_metadata_and_snapshot_before_returning_true + EntrypointSeamTests.test_post_event_returns_true_only_after_durable_persistence (metadata + snapshot BLOB readable from an independent connection; crash right after acceptance still finds the exact row)
- TEST-002 | Covers: AC-002 | Level: integration | Priority: P0 | Evidence: tests/test_worker_outbox_delivery.py OutboxFaultInjectionTests.test_outage_keeps_rows_pending_and_recovery_delivers_all_fifo (3 connection errors, rows stay pending, FIFO byte-verbatim delivery after recovery, delete-on-confirm, lifetime counters survive)
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P0 | Evidence: tests/test_worker_outbox_delivery.py OutboxFaultInjectionTests.test_duplicate_redelivery_is_confirmed_and_row_deleted (byte-verbatim redelivery answered 200 duplicate=true; row deleted on confirm; no re-post)
- TEST-004 | Covers: AC-004 | Level: integration | Priority: P0 | Evidence: tests/test_worker_outbox_delivery.py OutboxFaultInjectionTests.test_restart_drains_pending_rows_without_new_detections (rows from a closed first instance drained by a fresh instance, no new enqueues)
- TEST-005 | Covers: AC-005 | Level: unit | Priority: P0 | Evidence: tests/test_worker_outbox_delivery.py OutboxDurabilityTests.test_sqlite_write_failure_raises_and_leaves_no_partial_row + test_missing_snapshot_file_raises_oserror_and_leaves_no_row + EntrypointSeamTests.test_post_event_returns_false_when_sqlite_write_fails (disk-full at the seam → False, no accepted claim, no partial row)
- TEST-006 | Covers: AC-006 | Level: unit | Priority: P0 | Evidence: tests/test_worker_outbox_delivery.py OutboxFaultInjectionTests.test_backoff_envelope_is_bounded_exponential_with_zero_jitter (min(60, 2^(n-1)) over 10 attempts) + test_seeded_jitter_is_additive_and_capped_at_sixty_seconds (seeded RNG determinism, 20 attempts) + test_no_attempt_based_discard_after_twelve_failures (row survives 12 send errors, delivered on recovery) + test_backoff_survives_extreme_attempt_counts_without_overflow (D-112: extreme attempt counts stay capped, no OverflowError)
- TEST-007 | Covers: AC-007 | Level: integration | Priority: P0 | Evidence: tests/test_worker_outbox_delivery.py OutboxFaultInjectionTests.test_409_conflict_is_terminal_and_does_not_block_the_queue (retained terminal_error row, never re-posted, accept_errors incremented, oldest-unconfirmed age kept, next event delivered)
- TEST-008 | Covers: AC-008 | Level: integration | Priority: P1 | Evidence: tests/test_worker_outbox_delivery.py OutboxFaultInjectionTests.test_person_filter_ok_event_null_is_terminal_success (row deleted, single POST, zero error counters)
- TEST-009 | Covers: AC-009 | Level: integration | Priority: P0 | Evidence: tests/test_worker_outbox_delivery.py OutboxHeartbeatObservabilityTests (4 tests: real subprocess marker line → six observed-worker-runner.py state keys with schema_version 1; none/noise lines ignored; check-worker-health.py additive report fields; old-shape heartbeat backward compat)
- TEST-010 | Covers: AC-010 | Level: unit | Priority: P0 | Evidence: tests/test_worker_outbox_delivery.py OutboxConvergencePinTests.test_compatibility_gate_union_includes_outbox_with_nine_sources (len(MODULE_SOURCES) == 9, inspect compatible) + the five module count pins reading 9 (tests/test_worker_transport_module.py:372, tests/test_worker_crossings_module.py:477, tests/test_worker_live_module.py:537, tests/test_worker_tracking_module.py:495, tests/test_worker_roi_module.py:632)
- TEST-011 | Covers: AC-011 | Level: unit | Priority: P1 | Evidence: tests/test_worker_outbox_delivery.py OutboxConvergencePinTests.test_installer_and_artifact_lists_include_worker_outbox (install-systemd.sh + build_exact_artifacts.py + validate_exact_artifacts.py + validate_repo.py source-text pins gained worker/worker_outbox.py together)
- TEST-012 | Covers: AC-012 | Level: integration | Priority: P0 | Evidence: protected-surface regression guard — tests/test_road_event_hygiene.py, tests/test_398_wave_a_demo.py, tests/test_api_contract.py, tests/test_ubuntu_worker_runtime_provenance.py, tests/test_ubuntu_worker_observability.py + the five module-pin suites run unmodified (82 passed / 6 subtests, 2026-10-21); re-run green with the final battery on head 8a51a07 (145 passed + 6 subtests across 14 suites)
- TEST-013 | Covers: AC-013 | Level: unit | Priority: P1 | Evidence: tests/test_worker_outbox_delivery.py OutboxFaultInjectionTests.test_retry_posts_identical_metadata_string_and_snapshot_bytes (3 attempts, byte-identical metadata incl. non-ASCII + snapshot bytes, FR-006 multipart/URL/auth shape)

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: not applicable (no mutation) | Evidence: canonical issue #537 Outcome Contract with the wave-2 worker scope recorded 2026-10-21; six-field scope and allowed paths enforced before the first write
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged; branch not created | Retry: NO | Rollback: not applicable (no mutation) | Evidence: base 356872aa83f28927ddf041137854bf63d39d05ff verified clean; branch 537-wave2-worker-outbox created from the exact base
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: uncommitted working tree on the task branch; main untouched | Retry: YES (re-edit in the working tree) | Rollback: discard working-tree changes (`git checkout -- .` + branch delete) | Evidence: worker/worker_outbox.py, worker/ubuntu_worker_entrypoint.py, deploy/worker/ubuntu/observed-worker-runner.py, deploy/worker/ubuntu/check-worker-health.py, deploy/worker/ubuntu/install-systemd.sh, scripts/worker/check_ubuntu_compatibility.py, scripts/quality/build_exact_artifacts.py, scripts/quality/validate_exact_artifacts.py, scripts/ci/validate_repo.py, scripts/ci/validate_sdd.py, the new/updated test suites, this SDD trio
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: implementation stays uncommitted; defect reported to the orchestrator | Retry: YES (fix + re-run battery) | Rollback: not applicable (no mutation) | Evidence: full pytest suite, ruff canon, validate_sdd (repo-wide + PR-fixture event), validate_repo — outputs recorded in issue #537
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: task branch commits rolled back to the branch point; main untouched | Retry: YES (re-commit) | Rollback: `git reset` to the branch point on the task branch | Evidence: orchestrator-owned commits on 537-wave2-worker-outbox (authorization: issue #537 Outcome Contract)
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: scratch artifacts remain in /tmp/opencode only (sandbox-ephemeral, never in git) | Retry: YES | Rollback: not required (scratch only) | Evidence: RED worktree /tmp/opencode/p537-wave2-red added and removed; tool caches redirected to /tmp/opencode/toolcache
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: prior evidence cursors remain valid | Retry: YES (re-post evidence comment) | Rollback: not required (additive audit text) | Evidence: issue #537 status comments; PR Change Contract synchronized with the exact diff
- TX-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: main unchanged until merge; after merge the revert PR restores the previous seam behavior while any pending outbox rows are preserved and paused, not dropped (worker-first ordering; the worker PR reverts before any wave-1 API revert is considered) | Retry: YES | Rollback: revert per PR | Evidence: rollback plan in the issue #537 Outcome Contract (rollback = revert per PR, worker first; pending outbox rows preserved and paused, not dropped)
