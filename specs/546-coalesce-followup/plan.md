# Plan — #546 wave 2 follow-up: honest post_state coalescing

- Issue: #546
- Specification: specs/546-coalesce-followup/spec.md
- Date: 2026-10-22

## Architecture

Single seam change. `post_state` coalescing on a full `_publish_queue` becomes a
drain with paired `task_done()`; the freshly built state (already the "keep
latest" semantics) is enqueued by the existing code path immediately after. The
producer/consumer protocol is untouched: producers enqueue only
`("state", enriched, overlay_payload)`; `_publish_worker` consumes only
`kind == "state"`; `post_event` never touches this queue (sync poster or durable
outbox, wave-2 path).

## Decisions

- D-546-001 | DELETE the dead kept-block, not REPAIR it. `kept = [x for x in cur if x[0] == "event"]` is provably always empty (no producer emits an `"event"` tag into `_publish_queue`); re-introducing event elements into the coalescing queue would change the publish protocol and the durable-first event path (wave-2 architecture). Smallest complete change wins.
- D-546-002 | Pair `task_done()` with every drained `get_nowait()`. The old code drained items without accounting them, so `unfinished_tasks` grew on every overflow; `queue.join()` semantics require one `task_done()` per consumed item.
- D-546-003 | Behavioral RED→GREEN test pinned on the two observable effects (fresh-state-only queue, balanced accounting) instead of source-text pins (lesson #398: no brittle source-text tests).

## Affected contours

- Ubuntu road worker: `worker/ubuntu_worker_entrypoint.py` `post_state` coalescing seam only (publish path unchanged elsewhere).
- API / VPS contour: none (zero diff; `api/**`, `data/contracts/*` untouched).
- Deploy tooling: none (`deploy/**` untouched); worker runtime update after merge goes through the standard exact-artifacts release pipeline per the standing delegation.

## Validation

- Focused: `python3 -m pytest tests/test_detection_runtime_optimization.py` (14 tests) on the fix head.
- RED authenticity: the new coalescing test must fail on base main @ 18b7c47 (verified via temporary stash of the worker fix).
- Repo gates: `validate_sdd.py` (trio + PR contract), `validate_repo.py`, `check_ubuntu_compatibility.py`, ruff with `scripts/quality/ruff.toml`.

## Runtime feedback

- Post-merge worker deploy runs the full battery inside the release pipeline; acceptance probes on the GPU box (outbox drain, restart drain, 409 retain) recorded on #537 after the exact-SHA deploy.

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-001 | Covers: AC-001, AC-002 | Level: unit | Priority: P1 | Evidence: tests/test_detection_runtime_optimization.py BoundedQueueAndPublishingTests.test_publish_queue_coalescing_drops_stale_and_balances (full-queue coalescing: stale dropped, fresh enqueued, unfinished_tasks balanced; publish thread and HTTP disabled via mocks)
- TEST-002 | Covers: AC-003 | Level: unit | Priority: P1 | Evidence: existing suites (tests/test_worker_transport_module.py, tests/test_detection_runtime_optimization.py) stay green; orchestrator diff inspection confirms the three-path exact changed-file scope

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged | Retry: NO | Rollback: not applicable (no mutation) | Evidence: canonical issue #546 Outcome Contract recorded 2026-10-22 with the follow-up scope; owner approval recorded in the dev chat before the first write
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: unchanged; branch not created | Retry: NO | Rollback: not applicable (no mutation) | Evidence: base 18b7c4790d06e0e018014a5dbe321cbf57e731ec verified clean; branch 546-coalesce-drop-stale created from the exact base
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: uncommitted working tree on the task branch; main untouched | Retry: YES (re-edit in the working tree) | Rollback: discard working-tree changes (git checkout -- . + branch delete) | Evidence: worker/ubuntu_worker_entrypoint.py, tests/test_detection_runtime_optimization.py, specs/546-coalesce-followup/**
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: implementation stays uncommitted; defect reported to the orchestrator | Retry: YES (fix + re-run focused tests) | Rollback: not applicable (no mutation) | Evidence: RED authenticity on base 18b7c47 + GREEN focused run (14 passed) + ruff (scripts/quality/ruff.toml) — outputs recorded in the session log
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: task branch commits rolled back to the branch point; main untouched | Retry: YES (re-commit) | Rollback: git reset to the branch point on the task branch | Evidence: orchestrator-owned commits on 546-coalesce-drop-stale (authorization: issue #546 Outcome Contract)
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: scratch artifacts remain in /tmp/opencode only (sandbox-ephemeral, never in git) | Retry: YES | Rollback: not required (scratch only) | Evidence: RED-check via temporary stash of the worker file; ruff diff artifacts in /tmp/opencode
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: prior evidence cursors remain valid | Retry: YES (re-post evidence comment) | Rollback: not required (additive audit text) | Evidence: issue #546 status comments; PR Change Contract synchronized with the exact diff
- TX-008 | Stage: ROLLBACK | Mutation: POSSIBLE | Failure disposition: CONDITIONAL | State after failure: main unchanged until merge; after merge the revert PR restores the previous coalescing behavior; pending outbox rows are preserved and paused, not dropped (worker-first rollback ordering) | Retry: YES | Rollback: revert per PR | Evidence: rollback = redeploy the previous worker bundle; the revert is worker-first; no API-side rollback is required for this follow-up
