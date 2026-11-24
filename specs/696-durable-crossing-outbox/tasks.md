# Tasks: durable crossing delivery through the existing worker outbox

- Spec: specs/696-durable-crossing-outbox/spec.md

## Delivery tasks
- [x] Crossing acceptance seam: `worker/worker_crossings.py` — `update_crossing_counts(detections, now=None, accept=None)` plus the module hook `set_crossing_accept`; the crossing dict is built once; a resolved callback runs before the track side, `last_cross`, counters and returned event; a falsy return/exception prints `crossing accept failed ...` and commits nothing; the `_crossing_pending_posts` append remains only for callers with no callback
- [x] Ubuntu wiring: `worker/ubuntu_worker_entrypoint.py` — `_crossing_payload` freezes the stable namespaced `crossing:<camera_id>:<created_at>:<track_id>:<direction>` event ID and the camera/profile/domain identity once; `accept_crossing` enqueues through the SAME `_ensure_outbox()` instance via `enqueue_crossing`; `_bind_crossing_acceptance()` (function-local guarded import) is called from the existing wiring block
- [x] Shared outbox: `worker/worker_outbox.py` — `crossing_pending` row status (existing TEXT column, no migration), `enqueue_crossing` with an empty snapshot BLOB, only the common INSERT factored (road `enqueue` signature/snapshot/`pending` intact), both pending statuses selected by `id`, pending metrics include both, dispatch by stored status, `terminal_error` reused for terminal rejection
- [x] Crossing delivery: `_post_crossing` derives the URL exactly as `worker_transport.post_crossing`, sends Bearer + metadata only, confirms only `ok: true` with a matching `event_id`; permanent 4xx (except 408/429) → terminal, 5xx/408/429/transport/malformed/mismatched → retry; distinct crossing log lines; road `_post` untouched
- [x] No new flag: rollback is a lane-A deploy of the previous main SHA; the old binary selects only `status='pending'` and leaves crossing rows untouched for forward recovery
- [x] SDD trio `specs/696-durable-crossing-outbox/{spec,plan,tasks}.md` written per `scripts/ci/validate_sdd.py` (Gherkin scenarios, at-least-once semantics, shared-FIFO consequence, NFR/RISK/TEST rows, correct-course check, deployment transaction audit)
- [x] Production verification: `python3 -m py_compile` on all changed `.py` (exit 0); `python3 -m ruff check --config scripts/quality/ruff.toml` on all changed `.py` (`All checks passed!`); `python3 scripts/ci/validate_sdd.py` green
- [x] Regression check: `tests.test_line_crossing`, `tests.test_worker_crossings_module`, `tests.test_ubuntu_worker_runtime_provenance` → 64 tests OK; `tests.test_worker_outbox_module`, `tests.test_worker_outbox_delivery` → 33 tests OK
- [x] Dedicated oracle `tests/test_696_durable_crossing_outbox.py` (10 tests, committed on this branch): crossing seam, crash replay, terminal-vs-retry matrix and rollback isolation — focused `pytest tests/test_696_durable_crossing_outbox.py -q` → 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`), RED on the base archive `172e938b` → 8 failed / 2 passed
- [ ] CI green on the #696 PR
- [ ] Merge the #696 PR to main
- [ ] Lane-A Ubuntu worker redeploy on the merged main SHA so the changes reach production (orchestrator-owned authorized chain)

## Completion gate
- CI green on the #696 PR
- PR merged to main
- Lane-A Ubuntu worker deploy executed in the authorized chain; on restart a pre-existing `crossing_pending` row is delivered rather than lost, new crossings are counted only after durable acceptance, and the crossing endpoint acknowledgement matches `event_id`
- Dedicated oracles for AC-001..AC-005 are present in `tests/test_696_durable_crossing_outbox.py` and green on this branch (focused pytest 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`)); the merged head keeps that result plus the CI green gate above

## Requirements traceability
- AC-001 | Task: durable `crossing_pending` row before counting (worker_crossings.py:165-190 acceptance block; entrypoint.py:208-247 payload/enqueue; outbox.py:270-306 enqueue_crossing/_insert_row) | Evidence: `tests/test_696_durable_crossing_outbox.py` — a bound callback + one crossing persists an empty-BLOB `crossing_pending` row with the stable event ID before the counter increments and keeps the RAM list empty; focused pytest 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`) | Coverage: COVERED
- AC-002 | Task: persistence failure never counts/advances/silently posts; failure surfaced and next frame retries (worker_crossings.py:170-187) | Evidence: `tests/test_696_durable_crossing_outbox.py` — rejecting and raising callbacks leave counters, track side, last_cross, returned list and RAM list untouched, print `crossing accept failed ...`, and one accepted retry counts exactly once; focused pytest 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`) | Coverage: COVERED
- AC-003 | Task: at-least-once restart replay from the same outbox with the same event_id and byte-identical metadata (outbox.py:281-306 insert, 421-430 selection, 433-440 dispatch) | Evidence: kill-before-send crash-replay test in `tests/test_696_durable_crossing_outbox.py` (focused pytest 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`)) plus the outbox module/delivery regression suites (33 tests OK) | Coverage: COVERED
- AC-004 | Task: crossing endpoint/ack contract and terminal-vs-retry classification; road `/events` untouched (outbox.py:554-599 `_post_crossing`, 689-694 `_crossings_url`) | Evidence: `tests/test_696_durable_crossing_outbox.py` — exact crossing URL, Bearer header, metadata-only data and no files; 200+match deletes, mismatched event_id retries, 400 → `terminal_error` retained, 503 → still `crossing_pending`; focused pytest 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`) | Coverage: COVERED
- AC-005 | Task: rollback isolation, both-status metrics and one `id`-ordered FIFO, legacy list path for non-Ubuntu callers (outbox.py:308-330 metrics, 421-430 selection; worker_crossings.py:192-196 list gate) | Evidence: `tests/test_696_durable_crossing_outbox.py` — a `status='pending'`-only selector leaves crossing rows untouched, no crossing reaches `/events`, both statuses are counted and interleaved by `id`, and the no-callback caller still appends to `_crossing_pending_posts`; focused pytest 10 passed; subtests 15 on the peer-review 7-path tree and 12 on the clean tree (the scope-guard subtest iterates `git status`) | Coverage: COVERED

## Definition of Done
- Issue/spec/plan/tasks current
- Exact changed-file scope verified
- Required tests and evidence complete
- Required CI green
- Exact-green-head merge complete
- Deployment state resolved
- Runtime acceptance resolved
- Deferred work recorded
- Risks resolved or explicitly accepted
- Waivers resolved or current

## Evidence (observed only)

- `python3 -m py_compile worker/worker_outbox.py worker/worker_crossings.py worker/ubuntu_worker_entrypoint.py` → exit 0 (no output).
- `python3 -m ruff check --config scripts/quality/ruff.toml worker/worker_outbox.py worker/worker_crossings.py worker/ubuntu_worker_entrypoint.py` → `All checks passed!`.
- `python3 -m unittest tests.test_line_crossing tests.test_worker_crossings_module tests.test_ubuntu_worker_runtime_provenance` → `Ran 64 tests ... OK`.
- `python3 -m unittest tests.test_worker_outbox_module tests.test_worker_outbox_delivery` → `Ran 33 tests ... OK`.
- `python3 scripts/ci/validate_sdd.py` → `Sea Speed SDD validation passed` (exit 0).
- Focused oracle (peer-review run on this branch): `pytest tests/test_696_durable_crossing_outbox.py -q` → 10 passed; 15 subtests (7-path tree). Re-run on the current 4-path working tree: `10 passed, 12 subtests passed` — the scope-guard subtest iterates `git status`, so its count follows the dirty-path count. RED before the change: 8 failed / 2 passed on the base archive `172e938b`.
- Clean-tree full battery (peer-review run on this branch): `pytest tests/ -q` → 1735 passed / 2 skipped / 947 subtests / 0 failed.
- Scratch behavioural oracle `/tmp/opencode/696-smoke.py` (outside the repo) → `CROSSING SEAM OK` and `OUTBOX CROSSING OK`.
