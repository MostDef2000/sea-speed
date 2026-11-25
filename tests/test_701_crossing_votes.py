"""Issue #701 — N-of-M crossing voting + transit drift filter.

The production side landed with the code worker (``worker/worker_crossings.py``
``update_crossing_counts`` opt-in vote branch with ``CROSSING_VOTE_N`` /
``CROSSING_VOTE_M`` / ``CROSSING_DRIFT_PX``, plus the matching blocks in
``deploy/worker/ubuntu/{worker,road-worker}.env.example``); these tests pin the
OUTCOMES of ``specs/701-crossing-votes/`` — never the mechanism beyond what an
observable requires.

Sections (one class each):

* ``CrossingVoteJitterTests`` — N=3/M=5 with an established source side:
  isolated opposite-side samples spaced BEYOND the cooldown but INSIDE track
  expiry produce ZERO events, and the SAME frames fire repeatedly on the
  embedded pre-#701 path — so the silence is provably voting, not a cooldown
  artifact (a test entirely inside cooldown would be a false RED). One genuine
  transit with three destination votes produces exactly ONE event with the
  right direction, counter and RAM-list sink, and later same-side samples
  never duplicate it.
* ``CrossingDriftFilterTests`` — enough destination votes but insufficient
  perpendicular displacement → ZERO events (the retained votes then confirm
  the moment displacement grows inside the M-window); sufficient displacement
  → exactly ONE. A mostly-parallel transit (hundreds of pixels along the line,
  a dozen pixels across it) never confirms.
* ``CrossingVoteEdgeCaseTests`` — reverse transit direction, a deadzone (zero)
  observation consuming a window slot without voting, track expiry / reused
  ID clearing vote history, and a line-geometry change clearing history.
* ``CrossingOffParityTests`` — a DETERMINISTIC 300-scenario set (seed 701,
  mirroring the code worker's ``/tmp/opencode/701-parity.py`` oracle): the
  shipped OFF path (N=1, M=1, drift=0) must be byte-identical to the embedded
  pre-#701 body — event payloads, counters, class counters, RAM list and final
  track state — and the embedded reference itself is hash-pinned to the base
  commit so the oracle cannot silently drift.
* ``CrossingInvalidConfigTests`` — non-integral, non-finite, non-numeric,
  negative and N>M configuration falls back to OFF (no crash, no vote keys,
  byte-identical to the legacy path) while a VALID N=3 still suppresses —
  proving the fallback is a config decision, not a broken knob.
* ``CrossingVotesScopeGuardTests`` — the working tree / pinned change set
  touches only the admitted #701 surface; forbidden paths are rejected by the
  predicate itself (synthetic offenders), so the guard is proven to bite
  without touching the tree.

Environment: the battery is stdlib-only (``scripts/run_tests.py``), so
``requests``/``numpy`` may be absent; ``ensure_worker_imports()`` stubs only
the names that are genuinely missing (repo precedent:
``tests/test_worker_crossings_module.py:_import_worker_pair``) and never
replaces a real module with a stub. Every assertion reads observable state
(events, counters, the transport-owned RAM list, the track entry) — no
implementation-detail assertion beyond what an outcome requires.

RED spot-check (what fails on base ``c14a98a3c3932b9d18099c6029d5b7cf75fb0102``,
before the production change; measured by running this file against a
``git archive`` of the base):

* Jitter / drift / reverse / deadzone / expiry / line-change — the base has
  NO vote branch at all: it ignores ``CROSSING_VOTE_N``/``_M``/``CROSSING_DRIFT_PX``
  and fires on the first opposite-side observation, so every "zero events so
  far" checkpoint fails with a non-empty event list.
* Invalid config — the control arm (valid ``CROSSING_VOTE_N=3`` must suppress)
  fails on base for the same reason: the base cannot suppress anything.
* OFF parity, the embedded-reference hash pin and the scope guard's
  synthetic-predicate test are deliberately GREEN on base (parity pins that
  the OFF path did NOT change; on base there is no vote branch to change it).
  The scope guard's two change-set tests cannot even run against a
  ``git archive`` extract (no ``.git`` → the fail-closed ``git diff`` raises),
  which is an artifact of the RED harness, not of the base code.

Peer-review coverage (the all-or-nothing config fix): the five combined-knob
invalid-config rows (``{N:abc,M:5,D:45}``, ``{N:3,M:5,D:nan}``,
``{N:2.5,M:5,D:45}``, ``{N:2,M:5,D:-10}``, ``{N:2,M:5,D:1e12}``) were measured
RED against the pre-fix commit ``4f278e7`` — the old PARTIAL fallback kept two
knobs voting — where all five subtests failed while the eight earlier rows
still passed; on the fixed tree all thirteen produce the OFF snapshot. The
diagonal-line drift oracles and the accept-callback-on-vote-path test cover
behaviour the fix did not change (GREEN on the pre-fix commit as well), and
the base-blob reference test is fail-closed by construction, so it also raises
on a ``git archive`` extract (no ``.git``) — a RED-harness artifact.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import random
import subprocess
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = ROOT / "worker"
for _root in (str(ROOT), str(WORKER_DIR)):
    if _root not in sys.path:
        sys.path.insert(0, _root)

# Guarded-optional probes (tests/test_697 idiom): worker/worker_transport.py
# imports requests unconditionally and worker/worker_media.py imports numpy.
# Only genuinely MISSING names are stubbed; a real module is never replaced
# (a real numpy must stay real for the suites that gate on it).
def ensure_worker_imports() -> None:
    import importlib.util

    for name in ("numpy", "requests"):
        if name in sys.modules:
            continue
        try:
            available = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            available = False
        if not available:
            sys.modules[name] = mock.MagicMock(name=name)


ensure_worker_imports()

import worker_kernel  # noqa: E402  repo-local (worker/ on sys.path above)

try:
    from tests.support import worker_source
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import worker_source  # noqa: E402


# ---------------------------------------------------------------------------
# literals: the geometry and the env contracts (written from the issue text,
# never derived from the module under test)
# ---------------------------------------------------------------------------

# Vertical line at x=100 in frame coordinates. side_of_line is the cross
# product -576*(cx-100): POSITIVE left of the line, NEGATIVE right of it, and
# sign_with_deadzone() collapses |value| <= 1 to the deadzone slot 0 — which
# for this line means cx == 100.0 exactly.
VERTICAL_LINE = [(100, 0), (100, 576)]
# Same orientation shifted to x=120: a line-geometry change for the history
# reset scenario (cx=50 stays left, cx=150 stays right of BOTH lines).
LINE_AT_120 = [(120, 0), (120, 576)]

# Literal OFF contract from the issue/env examples: N=1, M=1, drift=0 runs the
# legacy single-frame decision and allocates no vote history.
OFF_ENV = {
    "CROSSING_VOTE_N": "1",
    "CROSSING_VOTE_M": "1",
    "CROSSING_DRIFT_PX": "0",
    "CROSSING_MIN_INTERVAL_SEC": "2",
    "DETECTION_TRACK_MAX_GAP_SEC": "2",
}
# N=3/M=5 with a track expiry raised above the cooldown so samples can be
# spaced BEYOND cooldown (3 s) while the track stays alive (< 8 s) — the
# configuration that makes "zero events" attributable to voting alone.
VOTE_ENV = {
    **OFF_ENV,
    "CROSSING_VOTE_N": "3",
    "CROSSING_VOTE_M": "5",
    "DETECTION_TRACK_MAX_GAP_SEC": "8",
}
DRIFT_ENV = {**VOTE_ENV, "CROSSING_DRIFT_PX": "45"}
DEADZONE_ENV = {**VOTE_ENV, "CROSSING_VOTE_N": "2", "CROSSING_VOTE_M": "2"}
EXPIRY_ENV = {**VOTE_ENV, "DETECTION_TRACK_MAX_GAP_SEC": "2"}

# Verbatim pre-#701 body of worker/worker_crossings.py:update_crossing_counts,
# extracted from the base commit with
#   git show c14a98a3c3932b9d18099c6029d5b7cf75fb0102:worker/worker_crossings.py
#   -> ast.get_source_segment(...) for that FunctionDef
# and pinned below with its sha256 so the parity oracle cannot silently drift:
# the hash is asserted by
# CrossingOffParityTests.test_embedded_legacy_reference_is_byte_identical_to_base.
_LEGACY_UPDATE_SRC = '''def update_crossing_counts(detections, now=None, accept=None):
    """Detect line crossings from tracked centroids.

    Direction is derived from horizontal displacement across the line so that
    left_to_right always means the object moved rightward in frame coordinates.
    A per-track cooldown prevents double counting on centroid wobble.

    ``accept`` (issue #696) is the OPTIONAL synchronous acceptance callback: it
    receives the finished crossing dict once and must return True only after
    durable acceptance. When omitted, the callback bound once through
    set_crossing_accept is used (the Ubuntu contour); when neither exists the
    legacy in-memory list path runs. On a falsy return or a raised exception
    the crossing is NOT committed: the track side, last_cross, counters, the
    returned event and the RAM list stay untouched, so nothing is counted that
    was not durably accepted and the next frame can retry.
    """
    if now is None:
        now = time.time()
    maybe_reset_daily_crossings(now)
    cfg = fetch_crossing_line_config()
    if not cfg.get("enabled") or len(cfg.get("line") or []) != 2:
        prune_crossing_tracks(now)
        return []
    line = cfg["line"]
    cooldown_sec = env_float("CROSSING_MIN_INTERVAL_SEC", 2.0)
    accept_crossing = accept if accept is not None else globals().get("_crossing_accept")
    crossings = []
    for det in detections:
        track_id = det.get("track_id")
        if track_id is None:
            continue
        object_type = str(det.get("object_type") or det.get("class_name") or "object")
        x1, y1, x2, y2 = det["bbox_xyxy"]
        cx = (float(x1) + float(x2)) / 2.0
        cy = (float(y1) + float(y2)) / 2.0
        side = sign_with_deadzone(side_of_line((cx, cy), line))
        state = _crossing_track_sides.get(int(track_id))
        if state is None:
            _crossing_track_sides[int(track_id)] = {"side": side, "cx": cx, "last_seen": now, "last_cross": 0.0}
            continue
        prev_side = int(state.get("side") or 0)
        prev_cx = float(state.get("cx") or cx)
        state["last_seen"] = now
        if side == 0 or prev_side == 0 or side == prev_side:
            state["side"] = side if side != 0 else prev_side
            state["cx"] = cx
            continue
        if now - float(state.get("last_cross", 0.0)) < cooldown_sec:
            state["side"] = side
            state["cx"] = cx
            continue
        direction = "left_to_right" if cx > prev_cx else "right_to_left"
        crossing = {
            "track_id": int(track_id),
            "object_type": object_type,
            "class_name": object_type,
            "direction": direction,
            "confidence": det.get("confidence"),
            "speed_kmh": det.get("speed_kmh"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if accept_crossing is not None:
            # Ubuntu durable seam: accept BEFORE committing the crossing-side
            # transition, last_cross, the counters or the returned event.
            try:
                accepted = bool(accept_crossing(crossing))
                reason = ""
            except Exception as exc:
                accepted = False
                reason = type(exc).__name__
            if not accepted:
                print(
                    f"crossing accept failed track_id={crossing['track_id']}"
                    f" direction={direction} reason={reason or 'rejected'}",
                    flush=True,
                )
                continue
        state["side"] = side
        state["cx"] = cx
        state["last_cross"] = now
        _crossing_counts[direction] = _crossing_counts.get(direction, 0) + 1
        class_counts = _crossings_by_class.setdefault(object_type, {"left_to_right": 0, "right_to_left": 0})
        class_counts[direction] = class_counts.get(direction, 0) + 1
        if accept_crossing is None:
            # Non-Ubuntu caller only: the transport-owned list path. It is NOT
            # an Ubuntu fallback - a bound callback never leaves rows there.
            _crossing_pending_posts.append(crossing)
        crossings.append(crossing)
    prune_crossing_tracks(now)
    return crossings'''
_LEGACY_UPDATE_SHA256 = "8e5434c01454b8f9b0751d13d16d8a5de3542c2a550e814f1225df81b91881e8"

# Helpers the embedded legacy body calls. They are UNCHANGED by #701 (the
# diff touches only update_crossing_counts and the module docstring), so the
# harness extracts them from the current source — parsed ONCE, exec'd into
# every fresh legacy namespace.
_LEGACY_HELPER_NAMES = {
    "maybe_reset_daily_crossings",
    "prune_crossing_tracks",
    "vlz_date",
    "reset_crossing_counts",
}
_LEGACY_HELPER_NODES = None  # lazily extracted (parses the worker sources once)

# Issue #701 scope-guard pins: BASE_SHA is main just before the #701 merge
# and HEAD_SHA is the #701 MERGE COMMIT itself, so the guard verifies the
# fixed, non-empty #701 change set (BASE_SHA..HEAD_SHA) and nothing else —
# never the current branch's later work. This is the documented merge-time
# re-pin: with both ends pinned, a later issue's files can no longer be
# judged against #701's allowlist (the #696 defect). Guard logic unchanged.
BASE_SHA = "c14a98a3c3932b9d18099c6029d5b7cf75fb0102"
HEAD_SHA = "36f28bec2c434dd60e682c5741159ae6c13b7df4"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def load_worker_crossings():
    """Import worker/worker_crossings.py by its runtime name."""
    if str(WORKER_DIR) not in sys.path:
        sys.path.insert(0, str(WORKER_DIR))
    import worker_crossings

    return worker_crossings


def _reset_module_state(mod) -> None:
    """Fresh crossing state: counters, track sides, RAM list, VLZ date, hook."""
    mod.reset_crossing_counts()  # counts, by-class, track sides, RAM list
    mod._crossing_vlz_date = None
    mod.set_crossing_accept(None)


def _line_cfg(line):
    return lambda: {"enabled": True, "line": line}


def _det(track_id, cx, cy=120.0, object_type="car", confidence=0.9, speed_kmh=42.0):
    """One tracked detection whose centroid is exactly (cx, cy)."""
    return {
        "track_id": track_id,
        "bbox_xyxy": (cx - 20.0, cy - 15.0, cx + 20.0, cy + 15.0),
        "object_type": object_type,
        "class_name": object_type,
        "confidence": confidence,
        "speed_kmh": speed_kmh,
    }


_REAL_DATETIME = datetime


class _FrozenDatetime:
    """Module stand-in for ``worker_crossings.datetime`` with a frozen now.

    Both parity arms serialize events with the SAME ``created_at``, so payloads
    can be compared byte for byte instead of field by field.
    """

    @classmethod
    def now(cls, tz=None):
        return _REAL_DATETIME(2026, 11, 25, 12, 0, 0, 424242, tzinfo=tz)

    @classmethod
    def fromtimestamp(cls, timestamp, tz=None):
        return _REAL_DATETIME.fromtimestamp(timestamp, tz)


def _snapshot(events, counts, by_class, ram, state) -> dict:
    """The comparable outcome of one run (both arms use this shape)."""
    return {
        "events": list(events),
        "counts": dict(counts),
        "by_class": {name: dict(values) for name, values in by_class.items()},
        "ram": list(ram),
        "state": {track_id: dict(entry) for track_id, entry in state.items()},
    }


def _legacy_ns(line=VERTICAL_LINE) -> dict:
    """A fresh pre-#701 namespace: shared state + the embedded legacy body."""
    global _LEGACY_HELPER_NODES
    ns = {
        "os": os,
        "time": time,
        "datetime": _FrozenDatetime,
        "timedelta": timedelta,
        "timezone": timezone,
        "print": print,
        "env_float": worker_kernel.env_float,
        "side_of_line": worker_kernel.side_of_line,
        "sign_with_deadzone": worker_kernel.sign_with_deadzone,
        "fetch_crossing_line_config": _line_cfg(line),
        "_crossing_track_sides": {},
        "_crossing_counts": {"left_to_right": 0, "right_to_left": 0},
        "_crossings_by_class": {},
        "_crossing_pending_posts": [],
        "_crossing_vlz_date": None,
        "VLZ_TIMEZONE": timezone(timedelta(hours=10)),
    }
    if _LEGACY_HELPER_NODES is None:
        _LEGACY_HELPER_NODES = worker_source.extract_nodes(_LEGACY_HELPER_NAMES)
    helpers = ast.Module(
        body=[copy.deepcopy(node) for node in _LEGACY_HELPER_NODES], type_ignores=[]
    )
    ast.fix_missing_locations(helpers)
    exec(compile(helpers, str(WORKER_DIR / "worker_crossings.py"), "exec"), ns)
    exec(
        compile(
            _LEGACY_UPDATE_SRC,
            str(WORKER_DIR / "worker_crossings.py") + "@c14a98a3",
            "exec",
        ),
        ns,
    )
    return ns


def _merged_env(env=None) -> dict:
    merged = dict(OFF_ENV)
    merged.update(env or {})
    return merged


def _run_legacy_frames(frames, *, line=VERTICAL_LINE, env=None):
    """Run frames through the embedded pre-#701 body; return (events, ns)."""
    ns = _legacy_ns(line)
    events = []
    with mock.patch.dict(os.environ, _merged_env(env), clear=False):
        for now, detections in frames:
            events.extend(ns["update_crossing_counts"](detections, now=now))
    return events, ns


def _run_real_arm(mod, scenarios, *, line=VERTICAL_LINE, env=None):
    """Every scenario through the SHIPPED module under the OFF env contract."""
    results = []
    with (
        mock.patch.dict(os.environ, _merged_env(env), clear=False),
        mock.patch.object(mod, "fetch_crossing_line_config", _line_cfg(line)),
        mock.patch.object(mod, "datetime", _FrozenDatetime),
    ):
        for frames in scenarios:
            _reset_module_state(mod)
            events = []
            for now, detections in frames:
                events.extend(mod.update_crossing_counts(detections, now=now))
            results.append(
                _snapshot(
                    events,
                    mod._crossing_counts,
                    mod._crossings_by_class,
                    mod._crossing_pending_posts,
                    mod._crossing_track_sides,
                )
            )
    return results


def _run_legacy_arm(scenarios, *, line=VERTICAL_LINE, env=None):
    """Every scenario through the embedded pre-#701 body (fresh ns each)."""
    results = []
    with mock.patch.dict(os.environ, _merged_env(env), clear=False):
        for frames in scenarios:
            events, ns = _run_legacy_frames(frames, line=line, env=env)
            results.append(
                _snapshot(
                    events,
                    ns["_crossing_counts"],
                    ns["_crossings_by_class"],
                    ns["_crossing_pending_posts"],
                    ns["_crossing_track_sides"],
                )
            )
    return results


def _scenarios(count=300, frames=40, seed=701):
    """Deterministic scenario set (seed 701).

    Mirrors the code worker's /tmp/opencode/701-parity.py oracle: two tracks,
    deadzone samples exactly on the line, positions straddling it, and gaps on
    both sides of the cooldown (0.2 s wobble vs 3.0 s) and of the track expiry
    — all generated ONCE and fed to both parity arms.
    """
    rng = random.Random(seed)
    out = []
    for _ in range(count):
        now = 0.0
        sequence = []
        for _ in range(frames):
            now += rng.choice((0.2, 0.2, 0.2, 1.0, 3.0))
            detections = []
            for track_id in (1, 2):
                if rng.random() < 0.15:
                    continue
                x = rng.choice((100.0, 100.0, rng.uniform(20.0, 180.0)))
                y = rng.uniform(20.0, 500.0)
                detections.append(_det(track_id, x, y, rng.choice(("car", "person"))))
            sequence.append((now, detections))
        out.append(sequence)
    return out


class _CrossingVoteTestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_worker_crossings()
        _reset_module_state(self.mod)
        self.addCleanup(_reset_module_state, self.mod)

    def run_frames(self, frames, *, line=VERTICAL_LINE, env=None) -> list:
        """Run (now, detections) frames through the real module; return events.

        State persists across calls within a test (only setUp resets it), so a
        test can checkpoint between phases: ``events += self.run_frames(...)``
        then assert, then feed the next phase.
        """
        events: list = []
        with (
            mock.patch.dict(os.environ, _merged_env(env), clear=False),
            mock.patch.object(self.mod, "fetch_crossing_line_config", _line_cfg(line)),
            mock.patch.object(self.mod, "datetime", _FrozenDatetime),
        ):
            for now, detections in frames:
                events.extend(self.mod.update_crossing_counts(detections, now=now))
        return events

    def assertNoVoteKeys(self) -> None:
        """OFF (and the OFF fallback) allocates no vote history at all."""
        for track_id, state in self.mod._crossing_track_sides.items():
            leaked = {"votes", "vote_line", "anchor_x", "anchor_y"} & set(state)
            self.assertEqual(
                leaked,
                set(),
                f"track {track_id} leaked vote state under OFF: {sorted(leaked)}",
            )


# ---------------------------------------------------------------------------
# 1. jitter: votes absorb isolated opposite-side samples, a real transit fires
# ---------------------------------------------------------------------------


class CrossingVoteJitterTests(_CrossingVoteTestBase):
    def test_jitter_is_absorbed_and_a_genuine_transit_fires_exactly_once(self) -> None:
        """N=3/M=5: jitter → ZERO events; one transit → exactly ONE event.

        Every timestamp sits at least 3 s from the previous confirmation
        window (cooldown is 2 s) and at most 3 s from the previous sample
        (track expiry is 8 s), so neither cooldown nor expiry can explain the
        silence — the embedded pre-#701 path fires repeatedly on the very same
        frames, which is asserted below.
        """
        jitter = [
            (1.0, [_det(7, 50)]),   # establish the source side (left), anchor cx=50
            (2.0, [_det(7, 50)]),   # source-side sample: anchor moves, votes cleared
            (5.0, [_det(7, 150)]),  # isolated opposite sample (3 s later: beyond cooldown)
            (6.0, [_det(7, 50)]),   # back to the source side: votes cleared
            (9.0, [_det(7, 150)]),  # isolated opposite sample
            (10.0, [_det(7, 50)]),
            (13.0, [_det(7, 150)]),
            (14.0, [_det(7, 50)]),
            (17.0, [_det(7, 150)]),  # two in a row: still below N=3
            (18.0, [_det(7, 150)]),
            (19.0, [_det(7, 50)]),   # back to source: window emptied
        ]
        transit = [
            (22.0, [_det(7, 80)]),   # genuine approach on the source side
            (23.0, [_det(7, 120)]),  # destination vote 1
            (24.0, [_det(7, 140)]),  # destination vote 2
            (25.0, [_det(7, 160)]),  # destination vote 3 → confirm
            (26.0, [_det(7, 170)]),  # same side after the transit: no duplicate
            (27.0, [_det(7, 180)]),
            (28.0, [_det(7, 190)]),
            (29.0, [_det(7, 55)]),   # wobble back: 1 of 3 votes → no event
            (30.0, [_det(7, 50)]),   # 2 of 3 votes → still no event
        ]

        events = self.run_frames(jitter, env=VOTE_ENV)
        self.assertEqual(
            events,
            [],
            "N=3 must absorb every isolated opposite-side jitter sample",
        )
        events += self.run_frames(transit, env=VOTE_ENV)

        self.assertEqual(len(events), 1, "exactly one event for one genuine transit")
        self.assertEqual(events[0]["direction"], "left_to_right")
        self.assertEqual(events[0]["track_id"], 7)
        summary = self.mod.crossing_overlay_summary()
        self.assertEqual(
            (summary["left_to_right"], summary["right_to_left"]),
            (1, 0),
            "one left_to_right crossing, no right_to_left crossing",
        )
        self.assertEqual(len(self.mod._crossing_pending_posts), 1)
        self.assertEqual(
            self.mod._crossing_pending_posts[0],
            events[0],
            "the RAM-list sink carries the same single event",
        )
        # The same frames on the pre-#701 path fire repeatedly: the silence
        # above is voting, NOT the cooldown (the false-RED control).
        legacy_events, _ = _run_legacy_frames(jitter + transit, env=VOTE_ENV)
        self.assertGreaterEqual(
            len(legacy_events),
            5,
            "the pre-#701 path must fire during the jitter phase, otherwise "
            "this scenario would be suppressed by the cooldown anyway",
        )
        legacy_during_jitter, _ = _run_legacy_frames(jitter, env=VOTE_ENV)
        self.assertGreaterEqual(len(legacy_during_jitter), 3)


# ---------------------------------------------------------------------------
# 2. drift: votes alone are not enough without perpendicular displacement
# ---------------------------------------------------------------------------


class CrossingDriftFilterTests(_CrossingVoteTestBase):
    def test_insufficient_displacement_suppresses_then_confirms(self) -> None:
        """Enough votes but <45 px across the line → ZERO; then ONE.

        The first five destination observations never drift more than 30 px
        from the source-side anchor (threshold 45 px), so nothing confirms;
        the retained votes confirm the moment displacement reaches 60 px
        INSIDE the M=5 window — if the failed checks had discarded the votes,
        the confirming observation would hold a single vote and stay silent.
        """
        insufficient = [
            (1.0, [_det(7, 90)]),   # source side (left of x=100), anchor cx=90
            (2.0, [_det(7, 90)]),
            (3.0, [_det(7, 105)]),  # destination vote 1: |105-90| = 15 px
            (4.0, [_det(7, 108)]),  # vote 2 (below N=3)
            (5.0, [_det(7, 112)]),  # vote 3: |112-90| = 22 px < 45 → suppressed
            (6.0, [_det(7, 120)]),  # vote 4: 30 px < 45
            (7.0, [_det(7, 114)]),  # vote 5: 24 px < 45 (window now full)
        ]
        sufficient = [
            (8.0, [_det(7, 150)]),  # vote 6: |150-90| = 60 px ≥ 45 → confirm
        ]

        events = self.run_frames(insufficient, env=DRIFT_ENV)
        self.assertEqual(
            events,
            [],
            "five destination votes with <45 px of perpendicular displacement "
            "must not confirm",
        )
        events += self.run_frames(sufficient, env=DRIFT_ENV)
        self.assertEqual(len(events), 1, "sufficient displacement confirms once")
        self.assertEqual(events[0]["direction"], "left_to_right")
        summary = self.mod.crossing_overlay_summary()
        self.assertEqual((summary["left_to_right"], summary["right_to_left"]), (1, 0))

    def test_mostly_parallel_motion_never_confirms(self) -> None:
        """Motion ALONG the line does not drift: hundreds of px of travel,
        a dozen px across the line → ZERO events despite a full vote window."""
        parallel = [
            (1.0, [_det(9, 90, cy=50)]),    # source side, anchor (90, 50)
            (2.0, [_det(9, 90, cy=100)]),
            (3.0, [_det(9, 104, cy=200)]),  # crosses the line, 14 px of drift
            (4.0, [_det(9, 104, cy=300)]),
            (5.0, [_det(9, 104, cy=400)]),  # destination vote 3 → drift 14 < 45
            (6.0, [_det(9, 104, cy=470)]),
            (7.0, [_det(9, 104, cy=500)]),  # window full, drift still 14 px
        ]
        events = self.run_frames(parallel, env=DRIFT_ENV)
        self.assertEqual(
            events,
            [],
            "400 px of mostly-parallel travel must not confirm a 14 px transit",
        )
        summary = self.mod.crossing_overlay_summary()
        self.assertEqual(
            (summary["left_to_right"], summary["right_to_left"]),
            (0, 0),
            "no counter may move for a mostly-parallel transit",
        )

    # Diagonal oracle — every drift test above is axis-aligned, where a wrong
    # |Δx|-based drift is indistinguishable from the real perpendicular one.
    # Line (0,0)-(100,100): side_of_line = 100*(y - x), line_len = 141.42, so
    # the true drift is |Δ(y-x)| * 100 / 141.42 ≈ 0.707 * |Δ(y-x)| (pixels
    # perpendicular to the line) while |Δx| ignores y entirely. Both tests
    # below are built so the two formulas DISAGREE:
    #   * mostly-parallel: Δx from the anchor reaches 90 px (≥ the 45 px
    #     threshold) while the true drift stays 1100/141.42 ≈ 7.8 px → a
    #     |Δx| implementation would wrongly confirm;
    #   * perpendicular: Δx from the anchor is only 7 px (< threshold) while
    #     the true drift is 10300/141.42 ≈ 72.8 px → a |Δx| implementation
    #     would wrongly reject.
    DIAGONAL_LINE = [(0, 0), (100, 100)]

    def test_diagonal_line_rejects_mostly_parallel_motion(self) -> None:
        """Crossing a diagonal mostly ALONG it: enough votes, tiny drift."""
        frames = [
            (1.0, [_det(7, 40, 30)]),    # above the line (y < x): side -1, anchor (40,30)
            (2.0, [_det(7, 40, 30)]),    # source-side: anchor stays (40,30)
            (3.0, [_det(7, 95, 96)]),    # crossed (y > x): destination vote 1
            (4.0, [_det(7, 100, 101)]),  # vote 2
            (5.0, [_det(7, 110, 111)]),  # vote 3 → drift ≈7.8 px < 45 → suppressed
            (6.0, [_det(7, 120, 121)]),  # vote 4
            (7.0, [_det(7, 130, 131)]),  # vote 5: Δx = 90 px, drift still ≈7.8 px
        ]
        events = self.run_frames(frames, line=self.DIAGONAL_LINE, env=DRIFT_ENV)
        self.assertEqual(
            events,
            [],
            "motion mostly along the diagonal must not confirm: the true "
            "perpendicular drift stays below the threshold even though the "
            "travel along the line (and any |Δx| reading of it) exceeds it",
        )
        summary = self.mod.crossing_overlay_summary()
        self.assertEqual((summary["left_to_right"], summary["right_to_left"]), (0, 0))

    def test_diagonal_line_confirms_a_perpendicular_transit(self) -> None:
        """A transit across the diagonal: small Δx, large perpendicular drift."""
        frames = [
            (1.0, [_det(7, 40, 30)]),    # source side (y < x), anchor (40,30)
            (2.0, [_det(7, 40, 30)]),
            (3.0, [_det(7, 45, 120)]),   # destination vote 1: Δx = 5, drift ≈60 px
            (4.0, [_det(7, 46, 130)]),   # vote 2
            (5.0, [_det(7, 47, 140)]),   # vote 3 → drift ≈72.8 px ≥ 45 → confirm
        ]
        events = self.run_frames(frames, line=self.DIAGONAL_LINE, env=DRIFT_ENV)
        self.assertEqual(
            len(events),
            1,
            "a genuinely perpendicular transit across the diagonal must "
            "confirm even though its Δx (7 px) is far below the threshold",
        )
        self.assertEqual(
            events[0]["direction"],
            "left_to_right",
            "direction comes from the source-side anchor: cx 47 > anchor_x 40",
        )
        summary = self.mod.crossing_overlay_summary()
        self.assertEqual((summary["left_to_right"], summary["right_to_left"]), (1, 0))


# ---------------------------------------------------------------------------
# 3. reverse direction, deadzone slot, expiry/reused ID, line change
# ---------------------------------------------------------------------------


class CrossingVoteEdgeCaseTests(_CrossingVoteTestBase):
    def test_reverse_transit_reports_right_to_left(self) -> None:
        """Right-to-left transit: three destination votes → ONE right_to_left."""
        frames = [
            (1.0, [_det(7, 150)]),  # established on the RIGHT of the line
            (2.0, [_det(7, 150)]),
            (3.0, [_det(7, 90)]),   # destination vote 1
            (4.0, [_det(7, 70)]),   # destination vote 2 — still silent (N=3)
            (5.0, [_det(7, 50)]),   # destination vote 3 → confirm
        ]
        events = self.run_frames(frames[:2], env=VOTE_ENV)
        self.assertEqual(events, [], "no event while the track stays source-side")
        events += self.run_frames(frames[2:4], env=VOTE_ENV)
        self.assertEqual(
            events,
            [],
            "two of three destination votes must not confirm (a pre-#701 path "
            "would already have fired on the first one)",
        )
        events += self.run_frames(frames[4:], env=VOTE_ENV)
        self.assertEqual(len(events), 1, "exactly one reverse crossing")
        self.assertEqual(events[0]["direction"], "right_to_left")
        summary = self.mod.crossing_overlay_summary()
        self.assertEqual((summary["left_to_right"], summary["right_to_left"]), (0, 1))

    def test_deadzone_zero_observation_consumes_a_window_slot(self) -> None:
        """A zero (deadzone) observation eats an M=2 slot without voting.

        With N=2/M=2 the sequence destination → zero → destination must NOT
        confirm: if the zero observation did not consume a slot, the window
        would hold two destination votes at that point and confirm. The next
        destination observation completes the window and confirms once.
        """
        frames = [
            (1.0, [_det(7, 50)]),   # established source side
            (2.0, [_det(7, 50)]),
            (3.0, [_det(7, 150)]),  # destination vote 1 (1 of 2)
            (4.0, [_det(7, 100)]),  # exactly on the line → deadzone slot 0
            (5.0, [_det(7, 150)]),  # destination vote 2 — but the zero ate a slot
            (6.0, [_det(7, 150)]),  # window now [dest, dest] → confirm
        ]
        events = self.run_frames(frames[:5], env=DEADZONE_ENV)
        self.assertEqual(
            events,
            [],
            "the zero observation must consume a window slot without voting",
        )
        events += self.run_frames(frames[5:], env=DEADZONE_ENV)
        self.assertEqual(len(events), 1, "the completed window confirms once")
        self.assertEqual(events[0]["direction"], "left_to_right")

    def test_track_expiry_and_reused_id_clear_vote_history(self) -> None:
        """A gap beyond DETECTION_TRACK_MAX_GAP_SEC resets the track entry:
        the two stale destination votes never combine with the re-occupant's
        sample, and the fresh occupant needs a full N of its own."""
        frames = [
            (1.0, [_det(7, 50)]),   # established source side
            (2.0, [_det(7, 50)]),
            (3.0, [_det(7, 150)]),  # stale destination vote 1
            (4.0, [_det(7, 150)]),  # stale destination vote 2
            (7.0, [_det(7, 150)]),  # 3 s gap > 2 s expiry → reused ID, reset
            (8.0, [_det(7, 150)]),  # now source-side for the new occupant
            (9.0, [_det(7, 50)]),   # fresh trip, vote 1
            (10.0, [_det(7, 50)]),  # vote 2
            (11.0, [_det(7, 50)]),  # vote 3 → confirm
        ]
        events = self.run_frames(frames[:5], env=EXPIRY_ENV)
        self.assertEqual(
            events,
            [],
            "the reused ID must not inherit the previous occupant's votes "
            "(they would confirm on this very sample)",
        )
        state = self.mod._crossing_track_sides[7]
        self.assertEqual(state["votes"], [], "vote history cleared on reuse")
        self.assertEqual(state["side"], -1, "the new occupant's own side wins")
        events += self.run_frames(frames[5:], env=EXPIRY_ENV)
        self.assertEqual(
            len(events),
            1,
            "the fresh occupant needs a full N of its own votes",
        )
        self.assertEqual(events[0]["direction"], "right_to_left")

    def test_line_geometry_change_clears_vote_history(self) -> None:
        """A new line invalidates votes AND the old-geometry anchor.

        The first sample after the switch is a destination-side one, so only
        the line-change handling can be what stops it from confirming against
        the stale window (the stale votes plus this sample would reach N with
        the old anchor still valid)."""
        events = self.run_frames(
            [
                (1.0, [_det(7, 50)]),   # line at x=100: established source side
                (2.0, [_det(7, 50)]),
                (3.0, [_det(7, 150)]),  # stale destination vote 1
                (4.0, [_det(7, 150)]),  # stale destination vote 2
            ],
            line=VERTICAL_LINE,
            env=VOTE_ENV,
        )
        self.assertEqual(events, [])

        # Line geometry moves to x=120 between frames.
        events += self.run_frames(
            [(5.0, [_det(7, 150)])], line=LINE_AT_120, env=VOTE_ENV
        )
        self.assertEqual(
            events,
            [],
            "the first sample on the new geometry must not confirm against "
            "the old line's vote window",
        )
        state = self.mod._crossing_track_sides[7]
        self.assertEqual(
            state["vote_line"],
            (120, 0, 120, 576),
            "the track must record the geometry it is voting on",
        )
        self.assertIsNone(state["anchor_x"], "the old-geometry anchor is dropped")
        self.assertEqual(
            len(state["votes"]),
            1,
            "the two stale votes are gone; only the fresh sample remains",
        )

        events += self.run_frames(
            [
                (6.0, [_det(7, 50)]),   # source side of the NEW line: re-arms the anchor
                (7.0, [_det(7, 150)]),  # fresh vote 1
                (8.0, [_det(7, 150)]),  # fresh vote 2
                (9.0, [_det(7, 150)]),  # fresh vote 3 → confirm on the new geometry
            ],
            line=LINE_AT_120,
            env=VOTE_ENV,
        )
        self.assertEqual(len(events), 1, "one crossing on the new geometry")
        self.assertEqual(events[0]["direction"], "left_to_right")

    def test_accept_callback_rejects_the_nth_vote_then_accepts_the_next(self) -> None:
        """The #696 acceptance seam also runs on the ON/vote path.

        The bound callback returns False on the Nth destination vote (the
        frame that would confirm) and True on the next destination frame. A
        rejected acceptance commits NOTHING — source side, ``last_cross`` and
        the vote window stay put so the very next frame retries it — and the
        accepted crossing yields exactly ONE event, with the callback's
        accepted list populated once and no later duplicate. The
        transport-owned RAM list stays EMPTY: a bound callback is never an
        Ubuntu fallback (#696 contract), so the accepted list lives in the
        callback itself.
        """
        calls: list = []
        accepted: list = []

        def accept(crossing):
            calls.append(crossing)
            if len(calls) == 1:
                return False  # the Nth-vote confirmation is rejected
            accepted.append(crossing)
            return True

        self.mod.set_crossing_accept(accept)
        frames = [
            (1.0, [_det(7, 50)]),   # established source side
            (2.0, [_det(7, 50)]),   # anchor
            (3.0, [_det(7, 150)]),  # destination vote 1
            (4.0, [_det(7, 150)]),  # vote 2
            (5.0, [_det(7, 150)]),  # vote 3 → Nth → callback says False
            (6.0, [_det(7, 150)]),  # vote 4 → callback says True → ONE event
            (7.0, [_det(7, 160)]),  # same side after the transit: no duplicate
        ]
        events = self.run_frames(frames[:5], env=VOTE_ENV)
        self.assertEqual(events, [], "a rejected acceptance commits nothing")
        state = self.mod._crossing_track_sides[7]
        self.assertEqual(state["side"], 1, "the source side is kept for the retry")
        self.assertEqual(state["last_cross"], 0.0, "no confirmation was recorded")
        self.assertEqual(
            len(state["votes"]), 3, "the vote window survives the rejection"
        )

        events += self.run_frames(frames[5:], env=VOTE_ENV)
        self.assertEqual(len(events), 1, "exactly one event for one accepted transit")
        self.assertEqual(events[0]["direction"], "left_to_right")
        self.assertEqual(
            len(calls), 2, "the rejected Nth-vote frame and the accepted next frame"
        )
        self.assertEqual(len(accepted), 1, "the accepted list is populated once")
        self.assertEqual(accepted[0], events[0], "the accepted crossing IS the event")
        self.assertEqual(
            self.mod._crossing_pending_posts,
            [],
            "a bound callback never fills the transport-owned RAM list (#696)",
        )
        summary = self.mod.crossing_overlay_summary()
        self.assertEqual(
            (summary["left_to_right"], summary["right_to_left"]),
            (1, 0),
            "one counted crossing, no duplicate",
        )


# ---------------------------------------------------------------------------
# 4. OFF parity: the shipped OFF path is byte-identical to the legacy path
# ---------------------------------------------------------------------------


class CrossingOffParityTests(unittest.TestCase):
    SCENARIOS = 300
    FRAMES = 40
    SEED = 701
    # Lower bound for how often the LEGACY path must fire across the set: the
    # parity claim is worthless if the scenarios never produce crossings.
    MIN_LEGACY_EVENTS = 50

    def test_off_path_is_byte_identical_to_the_legacy_path(self) -> None:
        """Deterministic scenario set: OFF payloads/counts == pre-#701 path.

        Three hundred seeded scenarios (two tracks, deadzone samples on the
        line, gaps on both sides of the cooldown and the track expiry) are fed
        to the SHIPPED module under the literal OFF contract (N=1, M=1,
        drift=0) and to the embedded pre-#701 body; every run's events,
        counters, class counters, RAM list and final track state must serialize
        to the SAME bytes.
        """
        mod = load_worker_crossings()
        scenarios = _scenarios(self.SCENARIOS, self.FRAMES, self.SEED)
        real = _run_real_arm(mod, scenarios)
        legacy = _run_legacy_arm(scenarios)

        self.assertEqual(len(real), self.SCENARIOS)
        self.assertEqual(len(legacy), self.SCENARIOS)
        mismatches = []
        for index, (got, want) in enumerate(zip(real, legacy)):
            got_bytes = json.dumps(got, ensure_ascii=False).encode("utf-8")
            want_bytes = json.dumps(want, ensure_ascii=False).encode("utf-8")
            if got_bytes != want_bytes:
                mismatches.append(
                    {
                        "scenario": index,
                        "shipped": got_bytes[:600].decode("utf-8", "replace"),
                        "legacy": want_bytes[:600].decode("utf-8", "replace"),
                    }
                )
                if len(mismatches) >= 3:
                    break
        self.assertEqual(mismatches, [], f"OFF path diverged from legacy: {mismatches}")

        legacy_events = sum(len(entry["events"]) for entry in legacy)
        self.assertGreaterEqual(
            legacy_events,
            self.MIN_LEGACY_EVENTS,
            "the deterministic set must actually exercise crossings, "
            "otherwise byte-equality would be vacuous",
        )
        shipped_events = sum(len(entry["events"]) for entry in real)
        self.assertEqual(
            shipped_events, legacy_events, "identical event counts, not just shapes"
        )
        # OFF allocates no vote history anywhere in the shipped run.
        for entry in real:
            for track_id, state in entry["state"].items():
                leaked = {"votes", "vote_line", "anchor_x", "anchor_y"} & set(state)
                self.assertEqual(
                    leaked, set(), f"track {track_id} leaked vote state under OFF"
                )

    def test_embedded_legacy_reference_is_byte_identical_to_base(self) -> None:
        """The oracle's reference must stay the base-commit body, verbatim.

        A pinned sha256 of the embedded source (computed from
        ``git show c14a98:worker/worker_crossings.py`` at authoring time) keeps
        the parity comparison honest: editing the reference to match the new
        code would change the hash and fail here.
        """
        digest = hashlib.sha256(_LEGACY_UPDATE_SRC.encode("utf-8")).hexdigest()
        self.assertEqual(
            digest,
            _LEGACY_UPDATE_SHA256,
            "the embedded legacy reference drifted from commit c14a98a3",
        )
        # It must also predate the vote knobs entirely.
        self.assertNotIn("CROSSING_VOTE_N", _LEGACY_UPDATE_SRC)
        self.assertNotIn("CROSSING_VOTE_M", _LEGACY_UPDATE_SRC)
        self.assertNotIn("CROSSING_DRIFT_PX", _LEGACY_UPDATE_SRC)
        self.assertNotIn("votes_enabled", _LEGACY_UPDATE_SRC)

    def test_parity_reference_matches_the_base_blob_via_git(self) -> None:
        """The 300-scenario parity reference is checked against the REAL blob.

        Reads ``worker/worker_crossings.py`` at the base commit through
        ``git show``, extracts the ``update_crossing_counts`` body with the
        AST and compares it byte for byte with the embedded legacy source the
        parity runs use. Fails CLOSED: a missing git binary, a missing object
        or a shallow clone raises with diagnostics instead of silently
        trusting the embedded copy (a reference nobody verified is a
        reference nobody can trust).
        """
        try:
            blob = subprocess.run(
                [
                    "git",
                    "-C",
                    str(ROOT),
                    "show",
                    f"{BASE_SHA}:worker/worker_crossings.py",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except OSError as exc:
            raise AssertionError(
                "cannot run git to read the parity reference blob "
                f"({type(exc).__name__}: {exc}) — failing closed"
            ) from exc
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise AssertionError(
                "cannot read the parity reference blob with "
                f"`git show {BASE_SHA}:worker/worker_crossings.py` rc="
                f"{exc.returncode} ({detail or 'no output'}) — shallow clone or "
                "missing object? Failing closed: the embedded legacy body must "
                "be verified against the real base blob, never assumed."
            ) from exc
        tree = ast.parse(blob.stdout, filename="worker_crossings.py@c14a98a3")
        bodies = [
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "update_crossing_counts"
        ]
        self.assertEqual(
            len(bodies),
            1,
            "the base blob must define update_crossing_counts exactly once",
        )
        blob_source = ast.get_source_segment(blob.stdout, bodies[0])
        self.assertEqual(
            blob_source,
            _LEGACY_UPDATE_SRC,
            "the embedded parity reference differs from the base blob — the "
            "300-scenario comparison would be measuring the wrong baseline",
        )


# ---------------------------------------------------------------------------
# 5. invalid config → OFF, no crash
# ---------------------------------------------------------------------------


class CrossingInvalidConfigTests(_CrossingVoteTestBase):
    INVALID_CONFIGS = (
        ("non-integral N", {"CROSSING_VOTE_N": "2.5", "CROSSING_VOTE_M": "5"}),
        ("non-finite N (nan)", {"CROSSING_VOTE_N": "nan", "CROSSING_VOTE_M": "5"}),
        ("non-finite N (inf)", {"CROSSING_VOTE_N": "inf", "CROSSING_VOTE_M": "5"}),
        ("negative N", {"CROSSING_VOTE_N": "-1", "CROSSING_VOTE_M": "5"}),
        ("N greater than M", {"CROSSING_VOTE_N": "5", "CROSSING_VOTE_M": "2"}),
        ("non-numeric N", {"CROSSING_VOTE_N": "not-a-number"}),
        ("negative drift", {"CROSSING_DRIFT_PX": "-5"}),
        ("non-finite drift", {"CROSSING_DRIFT_PX": "nan"}),
        # Peer-review HIGH gap: rows where ONE bad knob sits beside two valid
        # ones — the exact shape of the old PARTIAL fallback (a parse failure
        # silently fell back to the default N while M/drift kept voting, and a
        # bad drift left N/M enabled). All-or-nothing means every row below
        # resets ALL THREE to OFF: one legacy event, no vote keys, and a byte
        # snapshot identical to the legacy path.
        (
            "unparsable N with valid M and drift",
            {"CROSSING_VOTE_N": "abc", "CROSSING_VOTE_M": "5", "CROSSING_DRIFT_PX": "45"},
        ),
        (
            "non-finite drift with valid N and M",
            {"CROSSING_VOTE_N": "3", "CROSSING_VOTE_M": "5", "CROSSING_DRIFT_PX": "nan"},
        ),
        (
            "non-integral N with valid M and drift",
            {"CROSSING_VOTE_N": "2.5", "CROSSING_VOTE_M": "5", "CROSSING_DRIFT_PX": "45"},
        ),
        (
            "negative drift with valid N and M",
            {"CROSSING_VOTE_N": "2", "CROSSING_VOTE_M": "5", "CROSSING_DRIFT_PX": "-10"},
        ),
        (
            "drift at the 1e12 bound with valid N and M",
            {"CROSSING_VOTE_N": "2", "CROSSING_VOTE_M": "5", "CROSSING_DRIFT_PX": "1e12"},
        ),
    )
    # Three frames: establish on the source side, then one opposite-side
    # observation 3 s later (beyond the 2 s cooldown).
    OFF_FIRING_FRAMES = (
        (1.0, [_det(7, 50)]),
        (2.0, [_det(7, 50)]),
        (3.0, [_det(7, 150)]),
    )

    def test_invalid_config_falls_back_to_off_without_crashing(self) -> None:
        """Every invalid knob → the legacy single-frame decision, no crash.

        The control arm pins that the SAME frames are suppressed by a VALID
        N=3 (so the fallback below is a config decision, not a scenario that
        never fires), and each invalid configuration must then behave exactly
        like the legacy path: one event, no vote keys, byte-identical payload.
        """
        frames = [list(frame) for frame in self.OFF_FIRING_FRAMES]

        # Control: a valid N=3 suppresses this very scenario.
        suppressed = self.run_frames(frames, env=VOTE_ENV)
        self.assertEqual(
            suppressed,
            [],
            "control: a valid N=3 must suppress a single opposite observation",
        )

        legacy_events, legacy_ns = _run_legacy_frames(frames)
        self.assertEqual(
            len(legacy_events),
            1,
            "the legacy path confirms this scenario (it is the OFF contract)",
        )
        legacy_bytes = json.dumps(
            _snapshot(
                legacy_events,
                legacy_ns["_crossing_counts"],
                legacy_ns["_crossings_by_class"],
                legacy_ns["_crossing_pending_posts"],
                legacy_ns["_crossing_track_sides"],
            ),
            ensure_ascii=False,
        ).encode("utf-8")

        for label, overrides in self.INVALID_CONFIGS:
            with self.subTest(config=label):
                _reset_module_state(self.mod)
                events = self.run_frames(frames, env=overrides)
                self.assertEqual(
                    len(events),
                    1,
                    f"{label}: invalid config must fall back to OFF and confirm",
                )
                self.assertEqual(events[0]["direction"], "left_to_right")
                self.assertNoVoteKeys()
                shipped_bytes = json.dumps(
                    _snapshot(
                        events,
                        self.mod._crossing_counts,
                        self.mod._crossings_by_class,
                        self.mod._crossing_pending_posts,
                        self.mod._crossing_track_sides,
                    ),
                    ensure_ascii=False,
                ).encode("utf-8")
                self.assertEqual(
                    shipped_bytes,
                    legacy_bytes,
                    f"{label}: the OFF fallback must be byte-identical to legacy",
                )


# ---------------------------------------------------------------------------
# 6. scope guard — only the admitted #701 surface
# ---------------------------------------------------------------------------


class CrossingVotesScopeGuardTests(unittest.TestCase):
    """The admitted #701 change set, over the pinned BASE_SHA..HEAD_SHA range.

    The pinned range is the Part-A pattern (see BASE_SHA/HEAD_SHA): it cannot
    flag a later issue's legitimate files the way a working-tree-only guard
    did. While #701 is still uncommitted the range is empty and the
    working-tree view is consulted instead (see _changed_paths), so the guard
    is live on this branch too; from the first #701 commit the range carries
    the change set and the status half never runs again.
    """

    ALLOWED_CHANGE_PREFIXES = (
        "tests/",
        "worker/worker_crossings.py",
        "deploy/worker/ubuntu/worker.env.example",
        "deploy/worker/ubuntu/road-worker.env.example",
        "specs/701-crossing-votes/",
    )
    FORBIDDEN_PREFIXES = (
        "api/",
        "worker/worker_outbox.py",
        "worker/ubuntu_worker_entrypoint.py",
        ".github/",
        ".gitlab",
    )

    @classmethod
    def _offenders(cls, paths: list[str]) -> list[str]:
        return [
            path
            for path in paths
            if not any(path.startswith(prefix) for prefix in cls.ALLOWED_CHANGE_PREFIXES)
        ]

    @staticmethod
    def _changed_paths() -> list[str]:
        """The pinned #701 change set (fail-closed on a failing ``git diff``)."""
        try:
            result = subprocess.run(
                ["git", "-C", str(ROOT), "diff", "--name-only", BASE_SHA, HEAD_SHA],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise AssertionError(
                "scope guard cannot read the pinned #701 change set: "
                f"`git diff --name-only {BASE_SHA} {HEAD_SHA}` failed with rc="
                f"{exc.returncode} ({detail or 'no output'}) — shallow clone or "
                "missing object? Failing closed: a guard that cannot read its "
                "pinned range must not pass."
            ) from exc
        paths: set[str] = {
            line.strip().strip('"')
            for line in result.stdout.splitlines()
            if line.strip()
        }
        if paths:
            # Post-commit: the pinned range is the whole change set and later
            # issues' work (committed or not) is outside it by construction.
            return sorted(paths)
        # Pre-commit window only: this branch has no commits yet (HEAD ==
        # BASE_SHA), so the working tree is the only place the #701 change
        # set exists. Never reached again once #701 is committed.
        status = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in status.stdout.splitlines():
            if not line.strip():
                continue
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ")[-1]
            paths.add(path.strip().strip('"'))
        return sorted(paths)

    def test_change_set_touches_only_the_701_surface(self) -> None:
        changed = self._changed_paths()
        offenders = self._offenders(changed)
        self.assertEqual(
            offenders,
            [],
            f"out-of-scope paths in the #701 change set (committed or "
            f"uncommitted): {offenders}",
        )

    def test_no_api_outbox_entrypoint_workflow_or_lockfile_change(self) -> None:
        changed = self._changed_paths()
        for path in changed:
            with self.subTest(path=path):
                self.assertFalse(
                    any(path.startswith(prefix) for prefix in self.FORBIDDEN_PREFIXES),
                    f"forbidden path in the #701 change set: {path}",
                )
                self.assertFalse(
                    path.endswith(".lock") or path.endswith(".lock.txt"),
                    f"lockfile in the #701 change set: {path}",
                )
                self.assertNotIn("package-lock.json", path)
                self.assertNotIn("runtime-lock.json", path)

    def test_scope_predicate_rejects_every_forbidden_path(self) -> None:
        """The guard itself must bite: feed it synthetic offenders.

        Proves the decision logic rejects the forbidden surface without
        touching the working tree (an out-of-scope path cannot be created
        from inside the admitted scope).
        """
        forbidden = [
            "api/app/analytics.py",
            "worker/worker_outbox.py",
            "worker/ubuntu_worker_entrypoint.py",
            ".github/workflows/quality-integration.yml",
            ".gitlab-ci.yml",
            "package-lock.json",
            "runtime-lock.json",
            "api/requirements-api.lock.txt",
            "deploy/vps/deploy.sh",
            "specs/696-durable-crossing-outbox/spec.md",
        ]
        for path in forbidden:
            with self.subTest(path=path):
                self.assertTrue(self._offenders([path]), f"{path} must be rejected")
        admitted = [
            "tests/test_701_crossing_votes.py",
            "worker/worker_crossings.py",
            "deploy/worker/ubuntu/worker.env.example",
            "deploy/worker/ubuntu/road-worker.env.example",
            "specs/701-crossing-votes/spec.md",
        ]
        self.assertEqual(self._offenders(admitted), [], "the admitted surface must pass")


if __name__ == "__main__":
    unittest.main()
