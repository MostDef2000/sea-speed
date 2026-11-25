# Plan: opt-in N-of-M crossing votes with a transit drift filter

- Spec: specs/701-crossing-votes/spec.md

## Architecture

One production module plus two configuration documents; no new module, table,
thread, flag, API contract or transport change.

1. **Decision branch — `worker/worker_crossings.py`.** `update_crossing_counts`
   reads `CROSSING_VOTE_N`, `CROSSING_VOTE_M` and `CROSSING_DRIFT_PX` once per
   call through the already-imported `env_float` (no new top-level import).
   Invalid values fall back to `N=M=1, drift=0`. `votes_enabled` is true only
   when that three-value tuple is not the OFF default. The per-detection path
   splits into:
   - **OFF**: the pre-change statements verbatim — deadzone/side adoption,
     side match, cooldown absorption, `direction = "left_to_right" if cx >
     prev_cx else "right_to_left"` — then falls through to the shared crossing
     construction and #696 acceptance block.
   - **ON**: geometry/gap checks, committed-side adoption, zero-slot voting, the
     bounded last-M `votes` window, immediate confirmation at the Nth
     destination vote, the source-side anchor direction, the perpendicular
     drift test and the cooldown absorption branch. It then falls through to
     the SAME crossing construction and acceptance block — the #696 path is not
     duplicated.
   The shared commit re-arms `anchor_x`/`anchor_y` to the confirmation centroid
   and clears `votes` only when voting is enabled, so the OFF commit is
   byte-identical to the pre-change block.
2. **Per-track state — existing `_crossing_track_sides` entry.** Adds only the
   keys `vote_line`, `votes`, `anchor_x`, `anchor_y`, and only when voting is
   enabled. No new module-level object; the crossing import allowlist and the
   worker's six-name re-export stay untouched. `prune_crossing_tracks` and
   `reset_crossing_counts` already drop the whole entry, so expiry and the
   daily reset clear vote state for free.
3. **Config docs — both Ubuntu env examples.** One identical block documents
   `CROSSING_VOTE_N`, `CROSSING_VOTE_M` (integer, `1 <= N <= M`),
   `CROSSING_DRIFT_PX` (full-frame pixels perpendicular to the line), the OFF
   default and the invalid-value fallback.

## Decisions

- D-701-1 — OFF is expressed by values, not a flag: `N=M=1` and drift 0 keep
  the legacy decision, satisfying the issue's "no separate enabled boolean".
- D-701-2 — vote state lives inside the existing per-track entry. The AST
  extraction harness in `tests/test_line_crossing.py` supplies only the old
  globals and `env_float`, so a module-level vote registry or `env_int` helper
  would fail there; per-track keys and `env_float` are harness-safe.
- D-701-3 — zero observations consume a window slot but never vote. This
  preserves the existing deadzone meaning while letting the operator express a
  tolerance over real observations.
- D-701-4 — confirmation is a window count, not "N consecutive": the Nth
  destination observation inside the last M confirms immediately, so `N < M`
  does not add latency.
- D-701-5 — drift is `|side_of_line(confirm) - side_of_line(anchor)| / |line|`
  because the raw cross product scales with line length; this quantity is the
  net displacement perpendicular to the line in full-frame pixels.
- D-701-6 — a cooldown-suppressed stable transition is absorbed AND re-armed
  (side committed, anchor moved, votes cleared) so its votes can never fire
  later as a stale crossing.
- D-701-7 — after a line-geometry change the old anchor is invalid for the new
  line, so the anchor becomes `None` until a fresh source-side observation
  re-arms it; a transition cannot confirm without an anchor.
- D-701-8 — invalid configuration fails safe to legacy OFF; a typo must never
  silently enable a new counting policy.
- D-701-9 — direction is compared against the anchor x, keeping the legacy tie
  rule (`cx == anchor_x` → `right_to_left`).

## Affected contours

- Ubuntu Worker/relay: `worker/worker_crossings.py` (shared executable
  `worker/**`).
- Configuration documentation: `deploy/worker/ubuntu/worker.env.example`,
  `deploy/worker/ubuntu/road-worker.env.example` (identical block).
- Tests: owned by the separate test worker (`tests/**`); this change writes no
  tests.
- Explicitly unchanged: `worker/worker_outbox.py`,
  `worker/ubuntu_worker_entrypoint.py`, `worker/worker_transport.py`,
  `worker/worker_kernel.py`, `api/**`, schemas, workflows.
- SDD: `specs/701-crossing-votes/` (this trio).

## Validation

Observed in this change (commands run from the repo root):

- `python3 -m py_compile worker/worker_crossings.py` → exit 0.
- `python3 -m ruff check --config scripts/quality/ruff.toml
  worker/worker_crossings.py` → `All checks passed!`.
- `python3 scripts/ci/validate_sdd.py` → `Sea Speed SDD validation passed`
  (exit 0).
- Scratch behavioural oracle `/tmp/opencode/701-oracle.py` (outside the repo,
  AST-extracted functions, controlled env): OFF parity scenarios and ON
  N-of-M/zero-slot/drift/reverse/cooldown/gap/geometry/invalid-config/accept
  scenarios all PASS, ends with `ALL-701-ORACLE-PASS`.
- Scratch OFF-parity oracle `/tmp/opencode/701-parity.py`: 300 randomized
  frame sequences (40 frames each) compared between the base `c14a98a3`
  `worker_crossings.py` and the new file → `OFF-PARITY PASS
  scenarios=300 snapped_events_equal`.
- Dedicated committed test oracle: PENDING — the separate test worker owns
  `tests/**` and will supply the binary coverage.

## Risk profile
- Risk profile: REQUIRED
- RISK-001 | Category: DATA | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: an enabled vote window can delay or suppress a genuine fast crossing if N/M are misconfigured; documented bounds `1 <= N <= M`, immediate Nth-vote confirmation and the OFF default keep the exposure operator-controlled | Validation: `tests/test_701_*.py` (test worker; evidence PENDING) covers jitter/honest-transit confirmation; scratch oracle shows confirm on the Nth vote without waiting for M | Residual risk: ACCEPTED — a too-large M relative to SAMPLE_FPS can starve a very fast transit; operators size it per profile | Owner: delivery orchestrator | Status: ACCEPTED
- RISK-002 | Category: TECH | Probability: 2 | Impact: 3 | Score: 6 | Mitigation: stale vote/anchor state could fire a crossing after an ID reuse, expiry, daily reset or line edit; state is kept inside the per-track entry, cleared on gap reuse/geometry change, and removed with the entry on prune/reset; cooldown suppression re-arms and clears | Validation: scratch oracle gap/geometry/cooldown scenarios PASS; committed tests PENDING | Residual risk: low — the only remaining anchor-less state deliberately refuses to confirm until a fresh source-side observation | Owner: delivery orchestrator | Status: MITIGATED
- RISK-003 | Category: OPS | Probability: 2 | Impact: 2 | Score: 4 | Mitigation: invalid configuration (non-numeric, N<1, M<1, N>M, negative/non-finite drift) falls back to legacy OFF and the worker keeps running; both Ubuntu env examples document the identical block | Validation: scratch oracle invalid-config scenarios PASS; env blocks compared identical; `py_compile`/`ruff` green | Residual risk: low — a typo degrades to the old behaviour instead of failing or silently enabling voting | Owner: delivery orchestrator | Status: MITIGATED
- RISK-004 | Category: PERF | Probability: 1 | Impact: 2 | Score: 2 | Mitigation: the ON path holds only a bounded last-M list per active track and counts it per frame; the OFF path allocates nothing extra and the per-track entry keeps its original four keys | Validation: OFF-parity oracle shows identical state dictionaries; ON state inspection shows the bounded list | Residual risk: low — M is operator-bounded and typical windows are single digits | Owner: delivery orchestrator | Status: ACCEPTED

## Test design
- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: committed oracle `tests/test_701_*.py` (test worker; evidence PENDING) asserts the default 1/1/drift-0 path equals the legacy events/counters/state and allocates no vote keys; scratch parity oracle `/tmp/opencode/701-parity.py` → `OFF-PARITY PASS scenarios=300 snapped_events_equal`
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P0 | Evidence: committed oracle `tests/test_701_*.py` (test worker; evidence PENDING) covers a jittering transit yielding exactly one event and source-side returns discarding partial votes; scratch oracle PASS
- TEST-003 | Covers: AC-003 | Level: unit | Priority: P0 | Evidence: committed oracle `tests/test_701_*.py` (test worker; evidence PENDING) covers Nth-vote immediate confirmation and a zero observation consuming a slot; scratch oracle PASS
- TEST-004 | Covers: AC-004 | Level: unit | Priority: P0 | Evidence: committed oracle `tests/test_701_*.py` (test worker; evidence PENDING) covers perpendicular drift rejection and diagonal-transit acceptance; scratch oracle PASS
- TEST-005 | Covers: AC-005 | Level: unit | Priority: P1 | Evidence: committed oracle `tests/test_701_*.py` (test worker; evidence PENDING) covers anchor-based direction including the `right_to_left` reverse and the tie rule; scratch oracle PASS
- TEST-006 | Covers: AC-006 | Level: unit | Priority: P1 | Evidence: committed oracle `tests/test_701_*.py` (test worker; evidence PENDING) covers expiry/daily-reset/reused-ID/geometry clearing, cooldown re-arming and invalid-config fallback; scratch oracle PASS; env blocks compared identical

## Deployment transaction audit
- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged; worker source unchanged | Retry: N/A | Rollback: N/A | Evidence: Change Contract plus `python3 scripts/ci/validate_sdd.py` on the #701 PR
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: Ubuntu worker still runs the previous exact-release artifacts | Retry: N/A | Rollback: N/A | Evidence: `py_compile` and `ruff` green; scratch parity oracle green; no schema or dependency change
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: the lane-A exact-release install fails closed before activation; the previous release keeps running | Retry: Re-dispatch the deploy workflow on the same merged SHA | Rollback: Revert the merge commit and redeploy the previous main SHA `c14a98a3c3932b9d18099c6029d5b7cf75fb0102` | Evidence: `deploy/worker/ubuntu/deploy-authorized.sh` exact-release transaction (unchanged by this PR)
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not merged | Retry: Re-run the gates | Rollback: N/A | Evidence: `py_compile` exit 0; `ruff` `All checks passed!`; scratch oracles `ALL-701-ORACLE-PASS` and `OFF-PARITY PASS`; committed test oracle PENDING (test worker)
- TX-005 | Stage: STATE-COMMIT | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: merge commit recorded in git | Retry: Re-merge | Rollback: Revert the merge commit | Evidence: merge commit SHA on main
- TX-006 | Stage: HOUSEKEEPING | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: JOURNAL entry pending | Retry: Re-record | Rollback: N/A | Evidence: JOURNAL.md entry in the delivery chain
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: BEST-EFFORT | State after failure: runtime acceptance probe output missing | Retry: Re-run the probe | Rollback: N/A | Evidence: on-host worker journal shows crossings still posted after the lane-A deploy; the crossing summary remains consistent (defaults keep legacy counting)
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: N/A — rollback is the recovery path itself | Retry: N/A | Rollback: redeploy the previous main SHA `c14a98a3c3932b9d18099c6029d5b7cf75fb0102`; the defaults in the previous env keep the legacy decision, and removing the new env variables restores it explicitly | Evidence: previous main SHA `c14a98a3c3932b9d18099c6029d5b7cf75fb0102`

## Correct-course check
- Trigger: NONE
- Issue impact: none — the work order matches issue #701 (opt-in N-of-M votes plus transit drift filter)
- Specification impact: none — the locked design (off-by-values, per-track vote state, anchor direction, perpendicular-pixel drift, clearing rules, dual env docs) is implemented as specified
- Plan impact: none — the harness constraints (no `env_int`, no new module globals, pinned import allowlist) were resolved inside the admitted path and recorded in Runtime feedback
- Tasks impact: none — production code, env docs and SDD were executed as written; tests remain with the separate test worker
- Authorization impact: NONE (bounded worker work order from the delivery orchestrator on branch `agent/wave9-701-crossing-votes`; the orchestrator owns the Git lifecycle)
- Follow-up: committed binary test oracle and the lane-A Ubuntu worker deploy happen in the authorized delivery chain after merge (test worker / orchestrator owned)

## Runtime feedback

- Pre-change behaviour: a single side flip (cooldown permitting) counted a
  crossing; jitter and mostly-parallel motion could produce false or duplicate
  counts, and direction came from the immediately preceding centroid.
- The OFF path must remain the pre-change code, not a "cleaner" rewrite: the
  parity oracle compares the base and new files on 300 randomized sequences and
  asserts identical events, counters, per-track state and pending list.
- `side_of_line` is a cross product scaled by line length; drift divides the
  side-value difference by the line length to obtain perpendicular pixels.
- The AST extraction harness in `tests/test_line_crossing.py` supplies a fixed
  stub namespace without `env_int` and without new globals; the implementation
  therefore reads config with `env_float` and stores vote state only inside the
  per-track entry.
- No production observation yet: the change ships with the lane-A Ubuntu
  worker deploy; runtime acceptance is resolved in the delivery chain.
