# Plan — Issue #633 water page stream reconnect retries indefinitely

- Issue: #633
- Specification: specs/633-water-stream-infinite-reconnect/spec.md

## Architecture

One-line change in `frontend/sea-speed/main.js` plus a structural test
class in `tests/test_frontend_contract.py`:

- `scheduleStreamReconnect`: the exhaustion early-return branch is removed;
  the delay becomes
  `STREAM_RETRY_DELAYS_MS[Math.min(reconnectAttempt,STREAM_RETRY_DELAYS_MS.length-1)]`
  — the exact expression of road/main.js `scheduleReconnect` (line 37);
  status/log strings drop the "/4" denominator. The retry loop stays live
  by construction: every path that previously terminated now re-schedules
  the reconnect timer; `markStreamOnline` (line 64) and `disconnectStream`
  (line 72) already reset `reconnectAttempt=0`, so successful sessions
  reset the ladder.
- The test class follows the repo's structural pattern
  (`StreamRetryLadderStructuralTests`): read the page HTML + connected
  local external scripts (comment-stripped) and assert on source text —
  the repo has no JS test infrastructure (vanilla JS, no package.json).

## Decisions

- D-1: mirror the road page instead of raising the attempt cap — the road
  page has run infinite-retry in production without pathology (delay caps
  at 8s, success resets the counter), and the owner confirmed the water
  page must behave like the road. Rejected: raising the cap to N>4 (the
  incident class — any transient longer than the ladder — survives);
  exponential backoff without a cap (unbounded delay is worse than a
  capped 8s).
- D-2: structural Python test instead of JS unit tests — no JS test
  infrastructure exists in the repo; the established frontend-semantics
  pattern is Python structural tests over live source.
- D-3: status/log strings drop the "/4" denominator — with unbounded
  attempts a fixed denominator is misleading; the bare attempt counter
  keeps long outages visible.

## Affected contours

- `frontend/sea-speed/main.js` → VPS front contour (served by nginx from
  the release tarball; rides the deploy-vps.yml run of the merged main
  SHA).
- `tests/test_frontend_contract.py` → no runtime contour (CI only).
- No worker, API, schema, contract, or workflow surface.

## Risk profile

- Risk profile: NOT REQUIRED

## Test design

- TEST-001 | Covers: AC-001 | Level: unit | Priority: P0 | Evidence: tests/test_frontend_contract.py StreamReconnectSemanticsStructuralTests — test_water_reconnect_caps_the_delay_index_at_the_last_ladder_rung and test_water_reconnect_has_no_terminal_exhaustion assert the fixed semantics on comment-stripped live source; RED authenticity observed on base 8e8a77f (2 failed / 1 passed, stash probe, tree restored)
- TEST-002 | Covers: AC-002 | Level: unit | Priority: P1 | Evidence: same class — test_road_reconnect_keeps_its_delay_index_cap guards the road page's Math.min cap that the water fix aligns with
- TEST-003 | Covers: AC-003 | Level: integration | Priority: P1 | Evidence: full battery + pytest focused run + node --check + validate_sdd observed in the Validation section; git diff scope limited to main.js, the test file and this trio

## Correct-course check

- Trigger: NONE
- Issue impact: NONE
- Specification impact: NONE
- Plan impact: NONE
- Tasks impact: NONE
- Authorization impact: NONE
- Follow-up: NONE

## Deployment transaction audit

VPS-only rollout (one served frontend file + test surface); no worker, no
API, no schema.

- TX-001 | Stage: ADMISSION | Mutation: NO | Failure disposition: FATAL | State after failure: no change lands | Retry: correct authorization/scope evidence then re-enter | Rollback: NOT REQUIRED before mutation | Evidence: owner `commit approved` (2026-11-10, #633 scope, one-key-whole-chain), base 8e8a77f
- TX-002 | Stage: PRE-MUTATION | Mutation: NO | Failure disposition: FATAL | State after failure: PR not mergeable | Retry: fix CI/validator failures on the branch | Rollback: NOT REQUIRED | Evidence: CI green on exact head, validate_sdd + validate_change_contract green
- TX-003 | Stage: MUTATION | Mutation: YES | Failure disposition: FATAL | State after failure: merge incomplete or CI red | Retry: only with green CI on the exact head | Rollback: revert the merge commit | Evidence: squash merge record
- TX-004 | Stage: VERIFICATION | Mutation: NO | Failure disposition: FATAL | State after failure: candidate not accepted | Retry: resolve probe failures before dispatch | Rollback: NOT REQUIRED | Evidence: CI green on exact head, validators green
- TX-005 | Stage: STATE-COMMIT | Mutation: YES | Failure disposition: FATAL | State after failure: previous deploy behavior remains | Retry: re-dispatch deploy-vps.yml after fixing | Rollback: redeploy previous main SHA via deploy-vps.yml | Evidence: deploy-vps.yml run on the merged main SHA (full 40-hex), acceptance probes after
- TX-006 | Stage: HOUSEKEEPING | Mutation: POSSIBLE | Failure disposition: BEST-EFFORT | State after failure: verified runtime remains valid while stale release cleanup may remain pending | Retry: clean stale non-current/non-previous releases independently | Rollback: NOT REQUIRED solely for stale cleanup failure | Evidence: warning-only pruning behavior already regression-protected
- TX-007 | Stage: EVIDENCE | Mutation: NO | Failure disposition: CONDITIONAL | State after failure: deployed runtime may be healthy but acceptance incomplete | Retry: replay the #633 probes without redeployment when the deployed SHA is unchanged | Rollback: decide from actual served bytes, not evidence alone | Evidence: deployed main.js contains the Math.min cap (public URL probe) + cam1 playlist liveness + deploy run record
- TX-008 | Stage: ROLLBACK | Mutation: YES | Failure disposition: FATAL | State after failure: if the previous deployed release cannot be restored or verified, stop automated mutation and recover actual VPS state | Retry: read current/previous/runtime evidence before any new mutation | Rollback: no guessed secondary target; use the protected previous deployed release | Evidence: existing VPS rollback logs and verified origin/public health

## Validation

- RED authenticity (new tests against base main.js): OBSERVED — stash
  probe on base 8e8a77f: `FAILED (failures=2)` — the delay-index-cap
  assertion and the no-terminal-exhaustion assertion fail on the base
  source (which contains `HLS reconnect exhausted` and the uncapped
  index); the road-guard test passes on base (road unchanged). Working
  tree restored after the probe (git diff --stat = 2 files).
- Focused run after the fix `python3 -m pytest
  tests/test_frontend_contract.py -q`: OBSERVED — 28 passed + 6 subtests.
- Full battery: `python3 -m unittest discover -s tests -p "test_*.py"` →
  recorded in tasks.md Completion gate (1429 OK, skipped=2).
- `node --check frontend/sea-speed/main.js`: OBSERVED — clean exit.
- validate_sdd: recorded in tasks.md Completion gate.

## Runtime feedback

- RF-001: after merge → deploy-vps.yml dispatch (full merged-main SHA) →
  the fixed main.js rides the release tarball; acceptance probes verify
  the deployed main.js contains `Math.min(reconnectAttempt` and the cam1
  playlist stays live.
- RF-002: rollback for the front = redeploy previous main SHA; the fix is
  rollback-safe by construction (one served file, no state surface),
  pinned by the structural tests and the peer's call-site trace.
