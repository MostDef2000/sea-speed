# Plan: durable crossing delivery through the existing worker outbox

- Spec: specs/696-durable-crossing-outbox/spec.md

## Architecture

Three production files, no new module, database, table, thread or flag.

1. **Acceptance seam — `worker/worker_crossings.py`.** `update_crossing_counts`
   gains an optional synchronous `accept` argument and a module hook bound once
   by `set_crossing_accept(callback)`. The crossing dict is built once, after
   the direction is known and before any state commit. When a callback resolves
   (explicit argument first, then `globals().get("_crossing_accept")`), it is
   invoked BEFORE `state["side"]/["cx"]/["last_cross"]`, `_crossing_counts`,
   `_crossings_by_class` and the `crossings` return list are updated. A falsy
   return or an exception prints one `crossing accept failed track_id=...
   direction=... reason=...` line and continues, leaving the track's previous
   side/cx/last_cross in place so the next frame re-detects and retries. The
   transport-owned `_crossing_pending_posts` append runs only when no callback
   resolves (non-Ubuntu callers); the hook is never used as a fallback on
   Ubuntu, so the list stays empty there.
2. **Ubuntu wiring — `worker/ubuntu_worker_entrypoint.py`.** `_crossing_payload`
   copies the crossing, fills `camera_id` / `analytics_profile` / `domain` with
   the same defaults as `worker_transport.post_crossing`, and assigns the
   stable namespaced `event_id` (`crossing:<camera_id>:<created_at>:<track_id>:
   <direction>`) once, keeping the original `created_at`. `accept_crossing`
   serializes that payload once and calls
   `_ensure_outbox().enqueue_crossing(event_id, metadata_json)` — the SAME
   lazily opened instance the road `post_event` seam uses. `_bind_crossing_
   acceptance()` imports `worker_crossings` function-locally (tolerating
   `ImportError` for the mocked provenance harness, printing a loud `crossing
   durable seam NOT bound: worker_crossings unavailable` diagnostic instead of
   degrading silently) and calls `set_crossing_accept(accept_crossing)` from
   the existing module wiring block. No main-loop or transport change.
3. **Outbox — `worker/worker_outbox.py`.** `enqueue_crossing(event_id,
   metadata_json)` writes the common INSERT with status `crossing_pending` and
   an empty snapshot BLOB; `enqueue(event_id, metadata_json, snapshot_path)` is
   unchanged in signature, snapshot read and `pending` status. `_head_row`
   selects `status IN ('pending', 'crossing_pending')` ordered by the existing
   `id` and returns the status; `_deliver` dispatches on that status:
   `_post_crossing` for crossings, the untouched `_post` for road rows. Crossing
   confirmation requires `{"ok": true, "event_id": <same>}`; permanent 4xx
   (except 408/429) becomes `terminal_error` (retained, counted in
   `accept_errors`), while 5xx, 408/429, transport errors and malformed or
   mismatched acknowledgements retry with the existing bounded backoff. Pending
   metrics include both statuses; crossing log lines are distinct from the road
   success/error lines.

## Decisions

- D-696-1 — reuse, don't duplicate: one `WorkerOutbox` instance, one SQLite
  file, one `outbox_events` table and one publisher daemon thread carry both
  row kinds. A second queue/DB/thread was rejected (operational surface and
  metric duplication with no benefit).
- D-696-2 — new status, no migration: `crossing_pending` lives in the existing
  TEXT `status` column; the road literal stays `pending` so the pre-change
  binary keeps selecting it. The unused snapshot slot is an empty BLOB.
- D-696-3 — dispatch by stored status only: the endpoint is never inferred from
  an empty JPEG or from a user-controlled metadata field (`domain`/profile), so
  a crafted payload cannot redirect a row.
- D-696-4 — crossing HTTP contract: exactly the `worker_transport.post_crossing`
  URL derivation (`SEA_SPEED_API_URL.rsplit("/", 1)[0] + "/crossings"`), Bearer
  `SEA_SPEED_API_TOKEN`, `data={"metadata": ...}`, no file. 200 + `ok: true` +
  matching `event_id` confirms; 409 and permanent 4xx (except 408/429) are
  terminal; 5xx/408/429/transport/malformed/mismatched retry. The road `_post`
  classifications are untouched.
- D-696-5 — no transition flag: a disabled flag would mean continuing to lose
  crossings during the very outage the change protects against. Rollback is a
  lane-A deploy of the previous main SHA; the old binary's `status='pending'`
  selector leaves crossing rows untouched for forward recovery.
- D-696-6 — at-least-once, not end-to-end idempotent: stable event IDs make
  replays identifiable, but the API has no receipt/dedup contract, so a crash
  between the API insert and the local ack can duplicate one crossing. Closing
  that window would change the API contract (out of scope per the issue).
- D-696-7 — shared FIFO head-of-line accepted: a retrying crossing delays later
  road rows by at most the current backoff interval (cap 60s); heartbeat
  `pending`/`oldest` expose it. This is an ordering consequence of one outbox,
  not a road wire-semantics change.
- D-696-8 — harness-safe wiring: the callback hook is read with
  `globals().get("_crossing_accept")` (the AST-extract harness namespace has no
  new globals), and the entrypoint import of `worker_crossings` is
  function-local with only `ImportError` tolerated (provenance tests load the
  entrypoint against a mocked worker without the worker dir on `sys.path`).

## Affected contours

- Ubuntu Worker/relay: `worker/worker_outbox.py`, `worker/worker_crossings.py`,
  `worker/ubuntu_worker_entrypoint.py` (shared executable `worker/**`).
- VPS: none.
- Tests: `tests/test_696_durable_crossing_outbox.py` (10 tests / 15 subtests),
  committed on this branch with the production code.
- Explicitly unchanged: `api/**` (no contract change), `deploy/**`,
  `worker/worker_transport.py` (URL derivation mirrored, not imported), the
  worker main loop, the road `_post` and `post_event` seams, and the
  `_crossing_pending_posts` list path for non-Ubuntu callers.
- SDD: `specs/696-durable-crossing-outbox/` (this trio).

## Validation

Observed in this change (commands run from the repo root):

- `python3 -m py_compile worker/worker_outbox.py worker/worker_crossings.py
  worker/ubuntu_worker_entrypoint.py` → exit 0.
- `python3 -m ruff check --config scripts/quality/ruff.toml
  worker/worker_outbox.py worker/worker_crossings.py
  worker/ubuntu_worker_entrypoint.py` → `All checks passed!`.
- `python3 -m unittest tests.test_line_crossing
  tests.test_worker_crossings_module tests.test_ubuntu_worker_runtime_provenance`
  → `Ran 64 tests ... OK`.
- `python3 -m unittest tests.test_worker_outbox_module
  tests.test_worker_outbox_delivery` → `Ran 33 tests ... OK`.
- Scratch behavioural oracle (`/tmp/opencode/696-smoke.py`, outside the repo):
  failing callback → 0 counted, empty list, retried and counted once on the
  next frame; hook binding and legacy list path; `crossing_pending` row with
  empty BLOB; confirmed ack deletes; mismatched `event_id` retries; 400 →
  `terminal_error` retained; 503 → still `crossing_pending`; road row still
  `pending`; single `id`-ordered FIFO across both statuses. Output:
  `CROSSING SEAM OK` / `OUTBOX CROSSING OK`.
- `python3 scripts/ci/validate_sdd.py` → `Sea Speed SDD validation passed`
  (exit 0).
- Dedicated oracle: `pytest tests/test_696_durable_crossing_outbox.py -q` →
  10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`); RED on the base archive `172e938b` → 8 failed /
  2 passed; clean-tree `pytest tests/ -q` → 1735 passed / 2 skipped /
  947 subtests / 0 failed; ruff and `python3 scripts/ci/validate_sdd.py` PASS.

## Runtime feedback

- Pre-change behaviour: crossings were appended to `_crossing_pending_posts` and
  posted by `flush_crossing_posts`; an API outage, transport error or restart
  dropped the crossing with no local record.
- The acceptance ordering matters operationally: committing the track side
  before persistence would lose the crossing permanently (the same side would
  never cross again), so the callback must run first and a failure must keep the
  previous side; this is what makes the next frame retry.
- Existing invariants discovered and preserved: the crossings module's import
  allowlist, the worker's exact six-name re-export block, the AST-extract
  harness namespace, the provenance harness's mocked entrypoint import, the
  outbox import allowlist and the road row's `pending` literal.
- No production observation yet: the behaviour lands with the lane-A Ubuntu
  worker deploy; runtime acceptance is resolved in the delivery chain.

## Risk profile
- Risk profile: REQUIRED
- RISK-001 | Category: DATA | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: at-least-once duplicate window — a crash between the API insert and the local acknowledgement redelivers the same crossing (same stable `crossing:<camera>:<created_at>:<track>:<direction>` id); the window and the missing server dedup are documented in the spec because the API contract is out of scope | Validation: kill-before-send crash-replay oracle in `tests/test_696_durable_crossing_outbox.py` (focused `pytest tests/test_696_durable_crossing_outbox.py -q` → 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`); confirmed ack deletes, mismatched ack retries with the row retained) | Residual risk: ACCEPTED — one identifiable duplicate per crash-in-window; operators can reconcile by event_id | Owner: delivery orchestrator | Status: ACCEPTED
- RISK-002 | Category: DATA | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: persistence failure must not count or advance — the Ubuntu callback runs before the track-side transition, `last_cross`, counters and returned event; on a falsy return/exception the previous side is kept so the next frame retries, and the failure is printed | Validation: `tests/test_696_durable_crossing_outbox.py` (focused pytest 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`)) — rejected and raising callbacks leave the counters and RAM list untouched, then one accepted retry counts exactly once | Residual risk: low — repeated persistence failure logs once per crossing attempt and loses nothing already stored | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 4 | Score: 8 | Mitigation: shared FIFO head-of-line — a retrying crossing can delay later road rows; bounded by the existing backoff (base 1s, x2, cap 60s) and exposed through heartbeat `pending`/`oldest`; rollback is a lane-A deploy of the previous main SHA (no flag), and the old binary leaves crossing rows untouched | Validation: `_head_row` single `id`-ordered selection over both statuses; existing outbox backoff/metrics suite green; rollback isolation reasoned from the unchanged `status='pending'` road selector | Residual risk: ACCEPTED — worst-case road delay is one backoff interval while a crossing is unconfirmed | Owner: delivery orchestrator | Status: ACCEPTED
- RISK-004 | Category: TECH | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: harness and module-invariant drift — the hook is read via `globals().get`, the setter stays out of the worker re-export list, the entrypoint import is function-local with only ImportError tolerated, and no new top-level imports enter either worker module | Validation: existing `tests.test_worker_crossings_module` (import allowlist, exact re-export set, rebinding guards), `tests.test_ubuntu_worker_runtime_provenance` (mocked entrypoint import) and `tests.test_worker_outbox_module` (outbox allowlist) all green | Residual risk: low — the pinned structural suites fail loudly on drift | Owner: delivery orchestrator | Status: MITIGATED
- RISK-005 | Category: SEC | Probability: 1 | Impact: 3 | Score: 3 | Mitigation: payload/log hygiene — crossing metadata carries only domain fields already posted today plus the frozen identity; the bearer token is read from the environment and never logged; permanent auth 4xx keeps the row retained (`terminal_error`) instead of dropping crossing data; the operator re-drive path is documented in the spec (clear the retained row via the documented `SEA_SPEED_OUTBOX_DB` SQLite path after fixing credentials/config, then the crossing must be re-detected — no automatic re-drive, no new tooling) | Validation: `_post_crossing` mirrors the existing `post_crossing` data layout (metadata only, no file); new log lines contain event_id/direction/reason, no headers/token; focused oracle and ruff/py_compile green | Residual risk: low — an auth 4xx makes crossings terminal until an operator intervenes and re-detects the crossing; rows are retained, never silently dropped | Owner: delivery orchestrator | Status: MITIGATED

## Test design
- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: `tests/test_696_durable_crossing_outbox.py` (focused `pytest tests/test_696_durable_crossing_outbox.py -q` → 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`); RED on the base archive `172e938b` → 8 failed / 2 passed): a bound callback + one crossing produces a `crossing_pending` row with an empty BLOB, a stable namespaced event_id and frozen created_at/camera/profile/domain before the counter increments, while `_crossing_pending_posts` stays empty
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: `tests/test_696_durable_crossing_outbox.py` (focused pytest 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`)): rejecting and raising callbacks leave counters, track side, last_cross, the returned list and the RAM list untouched, print the failure line, and the next frame retries and counts exactly once
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P0 | Evidence: `tests/test_696_durable_crossing_outbox.py` (focused pytest 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`)): kill the publisher before send, reopen the same outbox, and the row is selected by `crossing_pending` and posted with byte-identical metadata and the same event_id
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: `tests/test_696_durable_crossing_outbox.py` (focused pytest 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`)): URL derivation equals `state_url.rsplit("/", 1)[0] + "/crossings"`, metadata-only layout, `ok:true` + matching event_id confirms/deletes, permanent 4xx → terminal_error retained, 5xx/408/429/transport/malformed/mismatched → retry, road `_post` classifications unchanged
- TEST-005 | Covers: AC-005 | Level: integration | Priority: P0 | Evidence: `tests/test_696_durable_crossing_outbox.py` (focused pytest 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`)): a `status='pending'`-only selector leaves crossing rows untouched (rollback isolation), no crossing reaches `/events`, pending metrics count both statuses, one `id` order interleaves both kinds, and a no-callback caller still appends to `_crossing_pending_posts`

## Deployment transaction audit
- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged; no worker artifact changed | Retry: N/A | Rollback: N/A | Evidence: Change Contract and `python3 scripts/ci/validate_sdd.py` green on the #696 PR
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: Ubuntu worker still running the previous exact-release artifacts; no outbox file touched | Retry: N/A | Rollback: N/A | Evidence: py_compile/ruff on the three worker files, existing worker/outbox/crossings suites green, exact-artifact lists already contain all three files
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: the lane-A exact-release install fails closed before activation; the previous release keeps running; the outbox SQLite file is never rewritten by the install | Retry: Re-dispatch the deploy workflow on the same merged SHA | Rollback: Revert the merge commit and redeploy the previous main SHA `172e938b43ad791bcc968e1ea9795e10c98be9ab` | Evidence: `deploy/worker/ubuntu/deploy-authorized.sh` exact-release transaction (unchanged by this PR)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged | Retry: Re-run the gates | Rollback: N/A | Evidence: py_compile exit 0; ruff `All checks passed!`; unittest 64 tests OK + 33 tests OK; scratch oracle `CROSSING SEAM OK` / `OUTBOX CROSSING OK`; focused `pytest tests/test_696_durable_crossing_outbox.py -q` → 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`); clean-tree `pytest tests/ -q` → 1735 passed / 2 skipped / 947 subtests / 0 failed
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: merge commit recorded in git | Retry: Re-merge | Rollback: Revert the merge commit | Evidence: merge commit SHA on main
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: JOURNAL entry pending | Retry: Re-record | Rollback: N/A | Evidence: JOURNAL.md entry in the delivery chain
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime acceptance probe output missing | Retry: Re-run the probe | Rollback: N/A | Evidence: on-host worker journal shows `POST crossing ok event_id=...` after the lane-A deploy and the crossing is visible through the camera crossing summary
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: N/A — rollback is the recovery path itself | Retry: N/A | Rollback: redeploy the previous main SHA `172e938b43ad791bcc968e1ea9795e10c98be9ab`; the previous binary selects only `status='pending'`, so crossing rows stay untouched for forward recovery | Evidence: previous main SHA `172e938b43ad791bcc968e1ea9795e10c98be9ab`

## Correct-course check
- Trigger: NONE
- Issue impact: none — the work order matches issue #696 (durable crossing delivery through the existing outbox)
- Specification impact: none — the architect's acceptance seam, reuse, status, endpoint, flag and semantics decisions are implemented as specified
- Plan impact: none — the constraint discoveries (harness hook lookup, guarded entrypoint import, pinned re-export/import lists) were resolved inside the admitted paths and are recorded in Runtime feedback
- Tasks impact: none — delivery tasks executed as written; the dedicated oracle `tests/test_696_durable_crossing_outbox.py` is committed on the same branch and green
- Authorization impact: NONE (bounded worker work order from the delivery orchestrator on branch `agent/wave9-696-durable-crossing-outbox`; the orchestrator owns the Git lifecycle)
- Follow-up: none in this change; the lane-A Ubuntu worker deploy that ships these files happens in the authorized delivery chain after merge (orchestrator-owned)

## Test evidence summary
- Production gates observed in this change: py_compile exit 0 on all three worker files; ruff `All checks passed!`; `python3 scripts/ci/validate_sdd.py` green.
- Regression: `tests.test_line_crossing` + `tests.test_worker_crossings_module` + `tests.test_ubuntu_worker_runtime_provenance` → 64 tests OK; `tests.test_worker_outbox_module` + `tests.test_worker_outbox_delivery` → 33 tests OK.
- Scratch behavioural oracle (`/tmp/opencode/696-smoke.py`, outside the repo): `CROSSING SEAM OK` and `OUTBOX CROSSING OK`.
- Dedicated oracle: `pytest tests/test_696_durable_crossing_outbox.py -q` → 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`) (RED before the change: 8 failed / 2 passed on the base archive `172e938b`); clean-tree `pytest tests/ -q` → 1735 passed / 2 skipped / 947 subtests / 0 failed.
