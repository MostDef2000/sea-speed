# Issue #546 — wave 2 follow-up: honest post_state coalescing (drop stale + queue accounting balance)

- Issue: #546
- Status: ACTIVE
- Date: 2026-10-22

## Product outcome

The `_publish_queue` coalescing in `worker/ubuntu_worker_entrypoint.py` `post_state`
honestly implements its documented contract ("drop stale if queue full"): on a full
queue every drained item is stale (the only producer enqueues `("state", ...)` and
`_publish_worker` consumes only `kind == "state"`), so the coalescing block drops
them all and enqueues exactly one fresh state; every drained item receives a paired
`task_done()` so `queue.unfinished_tasks` never accumulates. The wave-2 review
residue (dead `"event"` filter — `kept` was provably always empty because
`post_event` never touches this queue: it degrades to the sync poster or the
durable outbox) and the unbalanced drain (drained items never got `task_done()`,
so `queue.join()` could hang) are removed with the smallest complete change. No
behavioral change for any healthy path: a non-full queue and the fresh-state
enqueue behave byte-identically.

## User scenarios

- Steady-state worker: state publishing is unchanged (non-full queue: enqueue and
  publish as before).
- Burst state updates (queue full): the freshest state wins; stale drained states
  are dropped deterministically and the queue accounting stays balanced, so a
  consumer waiting on `queue.join()` cannot hang on an overflow drain.

## Requirements

- R-546-001: the `post_state` coalescing block must drop all drained items and
  enqueue the freshly built state; no `"event"`-tagged filtering may remain
  (no producer can emit such a tag into `_publish_queue`).
- R-546-002: every drained item must be accounted with a paired `task_done()`
  immediately after its `get_nowait()`.
- R-546-003: protected surfaces stay untouched: `worker/worker_transport.py`,
  `api/**`, `data/contracts/*`, road publication gate code, `post_event` — zero diff.

## Acceptance criteria

- AC-001: with `_publish_queue` filled to capacity by stale state items, a
  `post_state` call leaves the queue with exactly one item carrying the fresh
  metadata (the stale items are all dropped).
- AC-002: the same flow leaves `unfinished_tasks` in a balanced state: after the
  fresh item itself is consumed and acknowledged, `unfinished_tasks == 0`
  (the behavioral test fails on base main @ 18b7c47 and passes on the fix).
- AC-003: `git diff` of the PR touches only `worker/ubuntu_worker_entrypoint.py`,
  `tests/test_detection_runtime_optimization.py`, and
  `specs/546-coalesce-followup/**` — all protected surfaces zero-diff.

## NFR assessment

- NFR-001 | Area: RELIABILITY | Target: overflow coalescing never loses the freshest state and never leaves unbalanced queue accounting (no join() hang) | Validation: behavioral coalescing unit test with a full queue, stale items, fresh-state assert and unfinished_tasks assert | Evidence: tests/test_detection_runtime_optimization.py BoundedQueueAndPublishingTests.test_publish_queue_coalescing_drops_stale_and_balances (RED on base 18b7c47, GREEN on the fix head); focused run 14 passed on the fix head | Status: PASS
- NFR-002 | Area: MAINTAINABILITY | Target: no dead zombie coalescing code remains in the publish seam; the documented contract and the code agree | Validation: direct diff review (dead kept-block removed; comment matches the actual drop-stale semantics) | Evidence: PR diff 546-coalesce-drop-stale; kept = [x for x in cur if x[0] == "event"] block deleted in full | Status: PASS

## Runtime feedback

- First runtime window opens with the post-merge Ubuntu worker deploy (exact SHA, standing delegation): the overflow coalescing path is exercised in production only on state-publish bursts; acceptance probes (outbox drain, restart drain, 409 retain) recorded on #537 remain the runtime evidence for the wave-2 contour, this follow-up adds no new runtime fields.
