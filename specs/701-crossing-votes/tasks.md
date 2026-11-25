# Tasks: opt-in N-of-M crossing votes with a transit drift filter

- Spec: specs/701-crossing-votes/spec.md

## Delivery tasks
- [x] Opt-in decision branch in `worker/worker_crossings.py`: read `CROSSING_VOTE_N`/`CROSSING_VOTE_M`/`CROSSING_DRIFT_PX` through `env_str` (unset sentinel) + `float`, validate `1 <= N <= M` with integral values, apply ONE `invalid` flag (parse failure, non-finite, non-integral, N<1, M<1, N>M, negative drift or drift >= 1e12) that switches ALL THREE to `N=M=1`/drift 0, and derive `votes_enabled` from the OFF tuple (no separate flag)
- [x] OFF path preserved verbatim: deadzone adoption, side match, cooldown absorption, direction tie and payload/timing run the pre-change statements and no vote keys are allocated
- [x] ON path inside the existing per-track entry: committed side, source-side anchor (`anchor_x`/`anchor_y`), bounded last-M `votes` and `vote_line` geometry signature; zero observations consume a slot without voting; the Nth destination vote confirms immediately
- [x] Direction computed against the source-side anchor (`left_to_right` iff confirmation centroid is right of the anchor, otherwise `right_to_left`)
- [x] Perpendicular drift filter: `|side(confirm) - side(anchor)| / |line|` in full-frame pixels, rejecting motion mostly along the line and accepting a diagonal transit that meets the threshold once the window is satisfied
- [x] Confirmed transitions re-arm the committed side/anchor and clear consumed votes; cooldown-suppressed stable transitions are absorbed and re-armed so they cannot fire later as stale crossings
- [x] Vote state cleared on track expiry, the VLZ daily reset, a reused track ID after `DETECTION_TRACK_MAX_GAP_SEC`, and a line-geometry change (with the anchor invalidated until a fresh source-side observation)
- [x] Reuse the #696 single crossing construction/durable-acceptance path unchanged; only the direction decision feeds it
- [x] Identical #701 config block in `deploy/worker/ubuntu/worker.env.example` and `deploy/worker/ubuntu/road-worker.env.example` (bounds, pixel semantics, OFF default, invalid-value fallback)
- [x] SDD trio `specs/701-crossing-votes/{spec,plan,tasks}.md` written to satisfy `scripts/ci/validate_sdd.py`
- [x] Production verification: `python3 -m py_compile` on the changed `.py`; `python3 -m ruff check --config scripts/quality/ruff.toml` on the changed `.py`; `python3 scripts/ci/validate_sdd.py`
- [x] Dedicated committed test oracle `tests/test_701_crossing_votes.py` (new oracle) and the admitted #696 scope-guard repair in `tests/test_696_durable_crossing_outbox.py`; focused `pytest tests/test_701_crossing_votes.py -q` → 13 passed / 26 subtests
- [ ] CI green on the #701 PR
- [ ] Merge the #701 PR to main
- [ ] Lane-A Ubuntu worker redeploy on the merged main SHA so the change reaches production (orchestrator-owned authorized chain)

## Completion gate
- `py_compile` exit 0, `ruff check` `All checks passed!` and `python3 scripts/ci/validate_sdd.py` green on this branch
- The committed oracle `tests/test_701_crossing_votes.py` and the admitted #696 scope-guard repair are present and green on the delivered head
- CI green on the #701 PR and the PR merged to main
- Lane-A Ubuntu worker deploy executed in the authorized chain; with default env the crossing counts remain consistent with pre-change behaviour, and an enabled vote/drift configuration behaves per AC-002..AC-005
- Admitted test surface stays limited to `tests/test_701_crossing_votes.py` and the #696 guard repair

## Requirements traceability
- AC-001 | Task: OFF path executes the pre-change decision statements and allocates no vote keys (worker_crossings.py OFF branch; `votes_enabled` false for 1/1/drift 0) | Evidence: `tests/test_701_crossing_votes.py` parity asserts the hash-pinned pre-#701 body matches the shipped OFF path over 300 scenarios / 2054 events / `byte_identical=True`; focused pytest → 13 passed / 26 subtests; scratch parity `OFF-PARITY PASS scenarios=300 snapped_events_equal` | Coverage: COVERED
- AC-002 | Task: jitter robustness via bounded N-of-M votes with source-side reset (worker_crossings.py ON branch, `votes` window) | Evidence: `tests/test_701_crossing_votes.py` jitter class (zero events during jitter, exactly one on a genuine transit); focused pytest 13 passed / 26 subtests | Coverage: COVERED
- AC-003 | Task: immediate Nth-vote confirmation inside the last-M window; zero observations consume a slot without voting (worker_crossings.py `votes.append(0)` and `votes.count(side) >= vote_n`) | Evidence: `tests/test_701_crossing_votes.py` N-of-M, zero-slot and reverse-transit cases; focused pytest 13 passed / 26 subtests | Coverage: COVERED
- AC-004 | Task: perpendicular drift filter in full-frame pixels between the source-side anchor and the confirmation centroid (worker_crossings.py drift block using `|Δside| / |line|`) | Evidence: `tests/test_701_crossing_votes.py` drift class (insufficient → 0 events, sufficient → exactly 1, mostly-parallel never confirms); focused pytest 13 passed / 26 subtests | Coverage: COVERED
- AC-005 | Task: anchor-based direction with the legacy tie rule (worker_crossings.py `direction = ... if cx > anchor_x else ...`) | Evidence: `tests/test_701_crossing_votes.py` reverse-direction case; focused pytest 13 passed / 26 subtests | Coverage: COVERED
- AC-006 | Task: clearing on expiry/daily reset/reused-ID/geometry change, cooldown re-arm, all-or-nothing invalid-config fallback and identical env docs (worker_crossings.py gap/geometry/cooldown/config blocks; both env examples) | Evidence: `tests/test_701_crossing_votes.py` expiry/reused-ID/geometry/invalid-config cases green (focused pytest 13 passed / 26 subtests, including `N=abc` with valid M/drift); scratch probe confirms OFF with no vote keys; env blocks compared identical | Coverage: COVERED

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

- `python3 -m py_compile worker/worker_crossings.py` → exit 0 (no output).
- `python3 -m ruff check --config scripts/quality/ruff.toml worker/worker_crossings.py` → `All checks passed!`.
- `python3 scripts/ci/validate_sdd.py` → `Sea Speed SDD validation passed` (exit 0).
- Focused oracle: `pytest tests/test_701_crossing_votes.py -q` → `13 passed, 26 subtests passed`.
- Shared run `pytest tests/test_701_crossing_votes.py tests/test_696_durable_crossing_outbox.py tests/test_line_crossing.py tests/test_worker_crossings_module.py -q` → `82 passed, 41 subtests passed`.
- Clean-tree full battery on the delivered head: 1748 passed / 2 skipped / 980 subtests / 0 failed. RED on the base archive `c14a98a3` → 10 failed / 3 passed.
- OFF parity: 300 scenarios, 2054 events, `byte_identical=True` (embedded pre-#701 body hash-pinned to base `c14a98a3`).
- Local re-run with the peer-review fixes uncommitted: `4 failed, 1744 passed, 2 skipped, 986 subtests passed`; the 4 failures are pre-existing working-tree scope guards (`test_685`, `test_687`, `test_697`, `test_700`) that flag any uncommitted later-issue file, not this change; the admitted #701/#696/line-crossing/module suites are green (82 passed / 41 subtests).
- Scratch behavioural oracle `/tmp/opencode/701-oracle.py` → `ALL-701-ORACLE-PASS`; scratch parity oracle `/tmp/opencode/701-parity.py` → `OFF-PARITY PASS scenarios=300 snapped_events_equal`.
- Peer-review config probe: `CROSSING_VOTE_N=abc` with valid `CROSSING_VOTE_M=5`/`CROSSING_DRIFT_PX=45` → legacy event fires and no vote keys allocated; a valid `N=2` with the same M/drift suppresses the single opposite frame.
- #701 env blocks in both example files compared → identical.
