# Tasks: opt-in N-of-M crossing votes with a transit drift filter

- Spec: specs/701-crossing-votes/spec.md

## Delivery tasks
- [x] Opt-in decision branch in `worker/worker_crossings.py`: read `CROSSING_VOTE_N`/`CROSSING_VOTE_M`/`CROSSING_DRIFT_PX` through `env_float`, validate `1 <= N <= M`, fall back to `N=M=1`/drift 0 on invalid values, and derive `votes_enabled` from the OFF tuple (no separate flag)
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
- [ ] Dedicated committed test oracle in `tests/test_701_*.py` (separate test worker; evidence PENDING)
- [ ] CI green on the #701 PR
- [ ] Merge the #701 PR to main
- [ ] Lane-A Ubuntu worker redeploy on the merged main SHA so the change reaches production (orchestrator-owned authorized chain)

## Completion gate
- `py_compile` exit 0, `ruff check` `All checks passed!` and `python3 scripts/ci/validate_sdd.py` green on this branch
- The dedicated binary test oracle from the separate test worker is present and green on the delivered head
- CI green on the #701 PR and the PR merged to main
- Lane-A Ubuntu worker deploy executed in the authorized chain; with default env the crossing counts remain consistent with pre-change behaviour, and an enabled vote/drift configuration behaves per AC-002..AC-005
- `tests/**` remains owned by the separate test worker; no test file is added or edited by this change

## Requirements traceability
- AC-001 | Task: OFF path executes the pre-change decision statements and allocates no vote keys (worker_crossings.py OFF branch; `votes_enabled` false for 1/1/drift 0) | Evidence: scratch parity oracle `/tmp/opencode/701-parity.py` → `OFF-PARITY PASS scenarios=300 snapped_events_equal` (events, counters, per-track state and pending list identical to base `c14a98a3`); scratch oracle asserts no `votes` key on OFF tracks; committed test oracle PENDING (test worker) | Coverage: COVERED
- AC-002 | Task: jitter robustness via bounded N-of-M votes with source-side reset (worker_crossings.py ON branch, `votes` window) | Evidence: scratch oracle `/tmp/opencode/701-oracle.py` PASS for "jitter produces exactly zero false events" and a later honest transit confirming once; committed test oracle PENDING (test worker) | Coverage: COVERED
- AC-003 | Task: immediate Nth-vote confirmation inside the last-M window; zero observations consume a slot without voting (worker_crossings.py `votes.append(0)` and `votes.count(side) >= vote_n`) | Evidence: scratch oracle PASS "N-of-M confirms on Nth vote" and "zero consumes a slot (not yet counted ...)"; committed test oracle PENDING (test worker) | Coverage: COVERED
- AC-004 | Task: perpendicular drift filter in full-frame pixels between the source-side anchor and the confirmation centroid (worker_crossings.py drift block using `|Δside| / |line|`) | Evidence: scratch oracle PASS "drift rejects shallow crossing then accepts real transit" and "drift accepted direction"; committed test oracle PENDING (test worker) | Coverage: COVERED
- AC-005 | Task: anchor-based direction with the legacy tie rule (worker_crossings.py `direction = ... if cx > anchor_x else ...`) | Evidence: scratch oracle PASS "on direction from source anchor" and "on reverse direction right_to_left"; committed test oracle PENDING (test worker) | Coverage: COVERED
- AC-006 | Task: clearing on expiry/daily reset/reused-ID/geometry change, cooldown re-arm, invalid-config fallback and identical env docs (worker_crossings.py gap/geometry/cooldown blocks; both env examples) | Evidence: scratch oracle PASS "reused id after gap", "geometry change clears vote history", "cooldown absorb does not fire stale votes later", "invalid N>M"/"invalid N/M < 1"; env blocks compared identical; committed test oracle PENDING (test worker) | Coverage: COVERED

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
- Scratch behavioural oracle `/tmp/opencode/701-oracle.py` (outside the repo, AST-extracted crossing functions, controlled env) → every OFF/ON scenario PASS and final line `ALL-701-ORACLE-PASS`.
- Scratch OFF-parity oracle `/tmp/opencode/701-parity.py` (base `c14a98a3` file vs new file, 300 randomized sequences × 40 frames) → `OFF-PARITY PASS scenarios=300 snapped_events_equal`.
- Dedicated committed test oracle `tests/test_701_*.py`: PENDING — the separate test worker owns `tests/**`; no test result is claimed here.
