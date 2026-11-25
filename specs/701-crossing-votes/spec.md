# Spec: #701 — opt-in N-of-M crossing votes with a transit drift filter

- Issue: #701
- Specification: `specs/701-crossing-votes/spec.md`
- Authorization: wave-9 worker admission (issue #701), branch
  `agent/wave9-701-crossing-votes`, base
  `c14a98a3c3932b9d18099c6029d5b7cf75fb0102`.
- Related: #397 wave 6 (crossing module), #696 (durable crossing acceptance).
- Admitted surface: production code `worker/worker_crossings.py`; config docs
  `deploy/worker/ubuntu/worker.env.example` and
  `deploy/worker/ubuntu/road-worker.env.example`; the new oracle
  `tests/test_701_crossing_votes.py`; the necessary cross-issue guard repair in
  `tests/test_696_durable_crossing_outbox.py`; this SDD trio.
- Test admission: `tests/test_696_durable_crossing_outbox.py` is admitted for
  exactly one repair — its scope guard compared the working tree against an
  unpinned base and so false-positived on every later issue; the guard is now
  pinned to its own committed change range. No #696 production behaviour
  changed.

## Product outcome

The line-crossing counter currently decides a crossing from two consecutive
tracked centroids: `side` flips once and the event is counted (subject only to
a per-track cooldown). A jittering centroid, or motion that runs mostly parallel
to the configured line, can therefore produce a false or duplicated crossing,
and direction is taken from the immediately preceding destination frame.

This change adds an opt-in N-of-M vote window and a perpendicular transit drift
filter inside the existing per-track crossing state. The default configuration
(`N=1`, `M=1`, drift `0`) is the OFF state: the legacy decision code runs
unchanged and no new state is allocated. When enabled, a side transition is
confirmed only after N destination-side observations inside the last M
observations, the Nth vote confirms immediately (no wait for the rest of the
window), direction is computed against the last trusted source-side centroid
anchor, and `CROSSING_DRIFT_PX` rejects motion whose NET DISPLACEMENT
PERPENDICULAR TO THE CONFIGURED LINE, in full-frame pixels, between that
source-side centroid and the confirmation centroid is below the threshold.
The single crossing construction/durable-acceptance path from #696 is reused
unchanged; the vote decision only replaces the legacy flip decision.

## User scenarios

Feature: opt-in N-of-M crossing votes with a transit drift filter

  Rule: the default configuration keeps the legacy decision

    Scenario: default configuration is the OFF state
      Given CROSSING_VOTE_N=1, CROSSING_VOTE_M=1 and CROSSING_DRIFT_PX=0
      When a tracked object's centroid moves across the configured line
      Then the legacy single-frame decision runs unchanged
      And the crossing payload, timing, direction ties, deadzone handling and
        cooldown behaviour are identical to the pre-change worker
      And no vote history is allocated for any track

  Rule: a jittering track yields exactly one event

    Scenario: jittery transit through the line
      Given CROSSING_VOTE_N=2 and CROSSING_VOTE_M=3
      And a track approaches the line from the source side
      When its centroid jitters across the line (right, left, right, right)
      Then exactly one crossing event is emitted for that track
      And returning to the source side discards the partial votes so the
        wobble cannot accumulate into a second event

  Rule: an honest transit confirms on the Nth vote without waiting for M

    Scenario: clean transit with N smaller than M
      Given CROSSING_VOTE_N=2 and CROSSING_VOTE_M=5 and CROSSING_DRIFT_PX=0
      When two consecutive destination-side observations occur
      Then the crossing is confirmed on the second observation
      And the event is not delayed until five observations have elapsed

    Scenario: a deadzone observation consumes a window slot without voting
      Given CROSSING_VOTE_N=2 and CROSSING_VOTE_M=2
      When the destination observation sequence is right, zero, right
      Then the vote count for the destination side is one
      And no event is emitted until one more destination-side observation

  Rule: motion mostly along the line is rejected by the drift filter

    Scenario: shallow crossing is rejected, then a real transit is accepted
      Given CROSSING_DRIFT_PX=50
      And the last trusted source-side centroid is 5 px before the line
      When the centroid reaches 5 px past the line
      Then no event is emitted because the perpendicular net displacement
        (10 px) is below 50 px
      When the centroid continues to 65 px past the line
      Then the event is emitted because the perpendicular net displacement
        (70 px) is at least 50 px

    Scenario: a valid diagonal transit is not rejected
      Given CROSSING_DRIFT_PX=20
      And a diagonal transit whose perpendicular net displacement exceeds 20 px
      Then the event is emitted without waiting for extra frames beyond the
        vote window

  Rule: direction is derived from the source-side anchor

    Scenario: reverse direction
      Given the committed side is the right side of the line
      When N destination-side observations occur on the left side
      Then the emitted direction is right_to_left
      And a centroid tie between the anchor and the confirmation resolves to
        right_to_left exactly as the legacy tie does

  Rule: invalid configuration fails safe

    Scenario Outline: invalid vote/drift values fall back to OFF
      Given CROSSING_VOTE_N=<n>, CROSSING_VOTE_M=<m> and CROSSING_DRIFT_PX=<d>
      When a crossing decision runs
      Then the configuration is treated as N=M=1 and drift 0
      And the legacy decision code runs unchanged

      Examples:
        | n | m | d    |
        | 3 | 2 | 0    |
        | 0 | 0 | 0    |
        | 2.5 | 5 | 0  |
        | 1 | 5 | abc  |
        | 2 | 5 | -10  |
        | 2 | 5 | inf  |
        | 2 | 5 | 1e12 |

  Rule: vote state never outlives its track or line geometry

    Scenario: reused track id after a gap
      Given a track accrued one destination-side vote
      And the track id disappears for longer than DETECTION_TRACK_MAX_GAP_SEC
      When the same track id is observed again
      Then its vote history and source-side anchor are discarded
      And no crossing is confirmed from the pre-gap votes

    Scenario: line geometry change
      Given a track accrued destination-side votes for one line
      When the configured line endpoints change
      Then the vote history and old-geometry anchor are discarded

    Scenario: track expiry and the daily reset
      Given vote state exists for a track
      When the track expires or the VLZ daily reset runs
      Then the whole per-track entry (including its votes) is dropped

## Requirements

1. `worker/worker_crossings.py` — keep the existing per-track entry and add the
   opt-in branch AFTER the centroid/side computation and BEFORE the legacy
   flip/cooldown mutations. The crossing dict construction and the #696 durable
   acceptance callback remain one shared path; the vote logic only selects the
   direction that path consumes.
2. OFF state is `CROSSING_VOTE_N=1`, `CROSSING_VOTE_M=1` and
   `CROSSING_DRIFT_PX=0`; there is no separate enabled flag. On the OFF path the
   pre-change decision statements execute unchanged (deadzone adoption, side
   match, cooldown absorption, direction tie, payload and timing) and no vote
   keys are created on any track entry.
3. ON state keeps, inside the existing per-track entry: the committed side, a
   source-side centroid anchor (`anchor_x`/`anchor_y`), a bounded last-M side
   history (`votes`) and the geometry signature (`vote_line`). A zero
   (deadzone) side appends a non-voting slot to the window; N destination-side
   votes inside the window confirm the transition, so the Nth vote confirms
   immediately rather than waiting for M further frames.
4. Direction is computed against the source-side anchor, not the immediately
   preceding destination frame: `left_to_right` when the confirmation centroid
   is right of the anchor, otherwise `right_to_left` (the legacy tie choice).
5. `CROSSING_DRIFT_PX` is the minimum NET DISPLACEMENT PERPENDICULAR TO THE
   CONFIGURED LINE, in FULL-FRAME PIXELS, between the last trusted source-side
   centroid and the confirmation centroid. It is computed as the absolute
   difference of the two `side_of_line` cross products divided by the line
   length (the raw cross product scales with line length and is never used as
   pixels). Motion mostly along the line is rejected; a diagonal transit whose
   perpendicular displacement meets the threshold is accepted without extra
   frames beyond the vote window.
6. A confirmed transition re-arms the committed side, moves the anchor to the
   confirmation centroid and clears the consumed votes. A stable transition
   suppressed by the existing cooldown is absorbed silently AND re-armed with
   cleared votes, so it cannot fire later as a stale crossing when the cooldown
   expires.
7. Vote state is cleared on track expiry (`prune_crossing_tracks`), the VLZ
   daily reset (`reset_crossing_counts`), a reused track ID after a gap longer
   than `DETECTION_TRACK_MAX_GAP_SEC`, and a line-geometry change (endpoint
   signature change). After a geometry change the old anchor is invalid, so a
   fresh source-side observation must re-arm it before a transition can
   confirm.
8. `deploy/worker/ubuntu/worker.env.example` and
   `deploy/worker/ubuntu/road-worker.env.example` carry an IDENTICAL block
   documenting the three variables, the `1 <= N <= M` integer bounds, the
   pixels meaning of drift, the OFF default, and the invalid-value fallback.
9. Invalid configuration (non-numeric or non-integral values, N < 1, M < 1,
   N > M, negative or non-finite drift, or a finite drift >= 1e12) is applied
   as ONE unit: ALL THREE values switch to the legacy OFF state (N=M=1,
   drift 0) and the worker keeps processing crossings with the old decision
   code. An unset variable keeps its documented default; only a set-but-invalid
   value invalidates the whole configuration.
10. No new top-level import MODULE enters the crossing module (the import
    allowlist stays `time`, `datetime`, `worker_kernel`, `worker_transport`);
    config is read through `env_str` (unset sentinel) and `float`, both from the
    already-allowed surface. No API, outbox, transport, entrypoint or schema
    change.

## Acceptance criteria

- AC-001: With `CROSSING_VOTE_N=1`, `CROSSING_VOTE_M=1` and
  `CROSSING_DRIFT_PX=0`, the legacy decision executes unchanged (same events,
  counters, track state, direction ties, deadzone adoption, cooldown
  absorption and payload) and no vote keys are allocated on any track entry.
- AC-002: With voting enabled, a jittering track that genuinely transits once
  emits exactly one event; returning to the source side discards partial votes
  so wobble cannot accumulate into a second event.
- AC-003: A transition confirms on the Nth destination-side observation inside
  the last M observations without waiting for M frames; a zero (deadzone)
  observation consumes a window slot without voting for either side.
- AC-004: The drift filter rejects motion whose perpendicular net displacement
  in full-frame pixels between the last trusted source-side centroid and the
  confirmation centroid is below `CROSSING_DRIFT_PX`, while accepting a
  diagonal transit whose perpendicular displacement meets the threshold.
- AC-005: Direction is computed from the source-side anchor
  (`left_to_right` iff the confirmation centroid is right of the anchor;
  ties resolve to `right_to_left`), producing the correct reverse
  (`right_to_left`) crossing.
- AC-006: Vote history is cleared on track expiry, the daily reset, a reused
  track ID after a gap, and a line-geometry change; a cooldown-suppressed
  stable transition is absorbed and re-armed so it cannot fire as a stale
  crossing; any invalid configuration (including a finite drift `>= 1e12`)
  switches all three values to the legacy OFF state as one unit; both env
  examples document the identical block.

## Runtime feedback

- Pre-change behaviour: one side flip (plus cooldown) counted a crossing and
  direction came from the immediately preceding centroid, so jitter and
  mostly-parallel motion could produce false or duplicated counts.
- Constraint discovered: `tests/test_line_crossing.py` execs AST-extracted
  crossing functions into a stub namespace that supplies `env_str`/`env_float`
  but no new module globals, so config is read through those helpers and all
  vote state lives inside the existing per-track entry (no new module-level
  object).
- Constraint discovered: `tests/test_worker_crossings_module.py` pins the
  crossing top-level import MODULES (`worker_kernel`/`worker_transport`) and
  the worker's exact six-name re-export set; the config reader adds the
  `env_str` alias from the already-allowed `worker_kernel` module and no
  exported definition.
- Peer-review finding fixed: `env_float` returns its default on a parse
  failure, which silently turned `CROSSING_VOTE_N=abc` into 1 while a valid M
  or drift kept voting on, and an invalid value reset only part of the tuple.
  The reader now distinguishes unset (an `env_str` sentinel) from unparsable
  and applies ONE `invalid` flag to all three values.
- Constraint discovered: `side_of_line` returns a cross product that scales
  with line length, so drift is `|side(B) - side(A)| / |line|`, not a raw side
  difference.
- No production observation yet: behaviour lands with the lane-A Ubuntu worker
  deploy; runtime acceptance is resolved in the delivery chain.

## NFR assessment

- NFR-001 | Area: Functional correctness | Target: N-of-M voting confirms on the Nth destination vote inside M observations, zero consumes a slot without voting, a jittering transit emits exactly one event, and every invalid config tuple falls back to OFF as one unit | Validation: `tests/test_701_crossing_votes.py` (committed new oracle) plus the scratch `/tmp/opencode/701-oracle.py`; focused `pytest tests/test_701_crossing_votes.py -q` | Evidence: focused pytest → 13 passed / 26 subtests; shared 701+#696+line-crossing+module run → 82 passed / 41 subtests; clean-tree battery → 1748 passed / 2 skipped / 980 subtests / 0 failed; RED on the base archive `c14a98a3` → 10 failed / 3 passed; scratch oracle `ALL-701-ORACLE-PASS` | Status: PASS
- NFR-002 | Area: Compatibility | Target: the default 1/1/drift-0 configuration is behaviourally byte-identical to the pre-change worker and allocates no vote history | Validation: `tests/test_701_crossing_votes.py` embeds the pre-#701 body (hash-pinned to base `c14a98a3`) and runs 300 deterministic scenarios against the shipped OFF path, plus the scratch parity oracle | Evidence: parity 300 scenarios / 2054 events / `byte_identical=True`; OFF tracks have no vote keys; scratch `OFF-PARITY PASS scenarios=300 snapped_events_equal` | Status: PASS
- NFR-003 | Area: Operability | Target: both Ubuntu env examples document the same block with integer bounds `1 <= N <= M`, perpendicular-pixel drift semantics, the OFF default, the all-or-nothing invalid fallback and the finite drift `>= 1e12` upper bound; no new top-level import module or module global | Validation: byte-identical documentation block in both files; crossing import allowlist (same modules) and six-name worker re-export unchanged; `ruff`/`py_compile`/`validate_sdd` green | Evidence: both files carry the identical #701 block; `py_compile` exit 0; `ruff check` `All checks passed!`; `python3 scripts/ci/validate_sdd.py` → `Sea Speed SDD validation passed` | Status: PASS
- NFR-004 | Area: Performance | Target: the ON path keeps only a bounded last-M list per active track and a constant-time count; the OFF path allocates nothing extra | Validation: `votes` is capped with a single slice delete at M; OFF tracks carry only the four legacy keys; per-frame work stays O(M) with M operator-bounded | Evidence: parity oracle shows identical OFF state dictionaries; ON state inspection in the scratch oracle shows the bounded `votes` list and the anchor/geometry keys | Status: PASS
