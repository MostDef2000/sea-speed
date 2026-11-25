"""Sea Speed worker crossing-domain module (issue #397, wave 6).

Crossing analytics moved VERBATIM (move-only refactor, byte-identical
bodies) from hls_motion_yolo_worker_events.py: the crossing counters and
track-side maps (_crossing_track_sides/_crossing_counts/_crossings_by_class),
the VLZ (UTC+10) daily-reset state (VLZ_TIMEZONE/_crossing_vlz_date) and the
six crossing functions (vlz_date, reset_crossing_counts,
maybe_reset_daily_crossings, prune_crossing_tracks, update_crossing_counts,
crossing_overlay_summary).

Object-identity coupling with worker_transport: _crossing_line_cache and
_crossing_pending_posts are transport-OWNED objects (their defining literals
stay in worker_transport.py); this module imports them and every access is
an IN-PLACE mutation (.clear/.append/.get) or a read - nothing here may
rebind them, so the wave-4/5 identity contract holds unchanged and the
ImportFrom in this module keeps ONE object visible everywhere.

_crossing_vlz_date moved WITH its sole rebinder maybe_reset_daily_crossings
(the only ast.Global naming it sits in that def) - the pair must never be
split apart; the rebinding/rebinder-coupling guards live in
tests/test_worker_crossings_module.py.

Import policy (guarded by tests/test_worker_crossings_module.py): top-level
imports are limited to time, datetime and the repo-pure siblings
worker_kernel (env_float, side_of_line, sign_with_deadzone) and
worker_transport (the two shared crossing objects + fetch_crossing_line_config).
NO cv2/numpy/ultralytics/av, NO subprocess/socket, NO requests/json - the
crossing layer is offline except through the transport fetcher.

Issue #696 durable acceptance seam: update_crossing_counts takes an OPTIONAL
synchronous acceptance callback (explicit ``accept=`` argument, or the module
hook bound once by the Ubuntu entrypoint via set_crossing_accept). When a
callback is bound, a detected crossing is accepted durably BEFORE this module
commits anything: the track-side transition, last_cross, the counters, the
returned event and the in-memory post list are all untouched unless the
callback returns True. A falsy return or an exception is surfaced on stdout
and the crossing is dropped uncounted (the track keeps its previous side, so
the next frame can retry). The list path stays for non-Ubuntu callers only
and is never used as an Ubuntu fallback.

Issue #701 opt-in N-of-M voting + transit drift filter: the per-track state
can additionally carry the committed side, a source-side centroid anchor and
a bounded last-M side history (``votes``/``anchor_x``/``anchor_y``/
``vote_line``). A side transition is confirmed only after N observations on
the destination side within the last M observations (1 <= N <= M); zero
(deadzone) observations consume a window slot without voting, the Nth vote
confirms immediately, and direction is computed against the source-side
anchor. ``CROSSING_DRIFT_PX`` sets the minimum NET DISPLACEMENT PERPENDICULAR
TO THE CONFIGURED LINE, in full-frame pixels, between the last trusted
source-side centroid and the confirmation centroid. N=M=1 with drift disabled
is the OFF state: the legacy single-frame decision runs unchanged and no vote
history is allocated. Vote state is dropped with the track entry (expiry,
daily reset, reused track ID after a gap) and on line-geometry changes.
"""

import time
from datetime import datetime, timedelta, timezone

from worker_kernel import env_float, side_of_line, sign_with_deadzone
from worker_transport import _crossing_line_cache, _crossing_pending_posts, fetch_crossing_line_config


_crossing_track_sides = {}
_crossing_counts = {"left_to_right": 0, "right_to_left": 0}
_crossings_by_class = {}
VLZ_TIMEZONE = timezone(timedelta(hours=10))
_crossing_vlz_date = None
# Issue #696: the Ubuntu entrypoint binds ONE optional synchronous acceptance
# callback here (set_crossing_accept) at wiring time; every other caller leaves
# it None and keeps the in-memory list path.
_crossing_accept = None


def set_crossing_accept(callback):
    """Bind (or clear, with None) the Ubuntu durable-acceptance callback.

    ``callback`` receives the finished crossing dict once and must return True
    only after the crossing was durably accepted. A falsy return or a raised
    exception means the crossing was NOT accepted: update_crossing_counts then
    leaves the track side, last_cross, counters, returned event and the RAM
    list untouched (and prints the failure), so nothing is reported accepted
    that was not persisted.
    """
    global _crossing_accept
    _crossing_accept = callback


def vlz_date(now=None):
    if now is None:
        now = time.time()
    return datetime.fromtimestamp(now, VLZ_TIMEZONE).date()


def reset_crossing_counts(clear_pending=True):
    _crossing_counts.update({"left_to_right": 0, "right_to_left": 0})
    _crossings_by_class.clear()
    _crossing_track_sides.clear()
    if clear_pending:
        _crossing_pending_posts.clear()


def maybe_reset_daily_crossings(now=None):
    """Reset live crossing counters at 00:00 Asia/Vladivostok (UTC+10)."""
    global _crossing_vlz_date
    today = vlz_date(now)
    if _crossing_vlz_date == today:
        return False
    _crossing_vlz_date = today
    reset_crossing_counts(clear_pending=False)
    return True


def prune_crossing_tracks(now=None):
    if now is None:
        now = time.time()
    max_gap_sec = env_float("DETECTION_TRACK_MAX_GAP_SEC", 2.0)
    for track_id in list(_crossing_track_sides.keys()):
        state = _crossing_track_sides[track_id]
        if now - float(state.get("last_seen", 0.0)) > max_gap_sec:
            _crossing_track_sides.pop(track_id, None)


def update_crossing_counts(detections, now=None, accept=None):
    """Detect line crossings from tracked centroids.

    Direction is derived from horizontal displacement across the line so that
    left_to_right always means the object moved rightward in frame coordinates.
    A per-track cooldown prevents double counting on centroid wobble.

    Issue #701 adds opt-in N-of-M voting and a perpendicular transit drift
    filter (``CROSSING_VOTE_N``/``CROSSING_VOTE_M``/``CROSSING_DRIFT_PX``).
    With the default 1/1 and drift 0 the legacy decision below is executed
    unchanged; otherwise the per-track vote window/anchor decides the
    transition and the shared construction/acceptance block below still
    builds and persists the single crossing event.

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
    # Issue #701 opt-in N-of-M voting + transit drift filter. N=M=1 with drift
    # disabled is the OFF state, so the legacy single-frame decision below runs
    # unchanged and no vote history is allocated. Invalid config (non-numeric or
    # non-integral values, N < 1, M < 1, N > M, negative or non-finite drift)
    # falls back to that same OFF state. env_float is used deliberately: the
    # crossing layer's import allowlist stays {time, datetime, worker_kernel,
    # worker_transport}.
    max_gap_sec = env_float("DETECTION_TRACK_MAX_GAP_SEC", 2.0)
    raw_n = env_float("CROSSING_VOTE_N", 1)
    raw_m = env_float("CROSSING_VOTE_M", 1)
    raw_drift = env_float("CROSSING_DRIFT_PX", 0.0)
    pair_valid = (
        raw_n == raw_n
        and raw_m == raw_m
        and -1e12 < raw_n < 1e12
        and -1e12 < raw_m < 1e12
    )
    vote_n = int(raw_n) if pair_valid else 1
    vote_m = int(raw_m) if pair_valid else 1
    if not pair_valid or vote_n != raw_n or vote_m != raw_m:
        vote_n, vote_m = 1, 1
    if raw_drift != raw_drift or not (-1e12 < raw_drift < 1e12) or raw_drift < 0.0:
        drift_min_px = 0.0
    else:
        drift_min_px = raw_drift
    if vote_n < 1 or vote_m < 1 or vote_n > vote_m:
        vote_n, vote_m = 1, 1
        drift_min_px = 0.0
    votes_enabled = vote_n != 1 or vote_m != 1 or drift_min_px > 0.0
    line_sig = (line[0][0], line[0][1], line[1][0], line[1][1])
    line_dx = float(line[1][0]) - float(line[0][0])
    line_dy = float(line[1][1]) - float(line[0][1])
    # |side_of_line| is a cross product: it scales with line length, so drift
    # (full-frame pixels perpendicular to the line) needs this divisor.
    line_len = (line_dx * line_dx + line_dy * line_dy) ** 0.5
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
            state = {"side": side, "cx": cx, "last_seen": now, "last_cross": 0.0}
            if votes_enabled:
                state["vote_line"] = line_sig
                state["votes"] = []
                state["anchor_x"] = cx if side != 0 else None
                state["anchor_y"] = cy if side != 0 else None
            _crossing_track_sides[int(track_id)] = state
            continue
        if votes_enabled and now - float(state.get("last_seen", 0.0)) > max_gap_sec:
            # Reused track ID after a gap: never inherit stale sides, anchors or
            # vote history from the previous occupant of this ID.
            state = {
                "side": side,
                "cx": cx,
                "last_seen": now,
                "last_cross": 0.0,
                "vote_line": line_sig,
                "votes": [],
                "anchor_x": cx if side != 0 else None,
                "anchor_y": cy if side != 0 else None,
            }
            _crossing_track_sides[int(track_id)] = state
            continue
        prev_side = int(state.get("side") or 0)
        prev_cx = float(state.get("cx") or cx)
        state["last_seen"] = now
        if not votes_enabled:
            # OFF path: the pre-#701 single-frame decision, unchanged.
            if side == 0 or prev_side == 0 or side == prev_side:
                state["side"] = side if side != 0 else prev_side
                state["cx"] = cx
                continue
            if now - float(state.get("last_cross", 0.0)) < cooldown_sec:
                state["side"] = side
                state["cx"] = cx
                continue
            direction = "left_to_right" if cx > prev_cx else "right_to_left"
        else:
            # ON path: commit on N destination-side observations inside the last
            # M observations; zero (deadzone) consumes a slot without voting.
            committed = prev_side
            if state.get("vote_line") != line_sig:
                # Line geometry changed: previous votes and the old-geometry
                # anchor are meaningless for the new line.
                state["vote_line"] = line_sig
                state["votes"] = []
                if side == committed and committed != 0:
                    state["anchor_x"] = cx
                    state["anchor_y"] = cy
                else:
                    state["anchor_x"] = None
                    state["anchor_y"] = None
            votes = state.get("votes")
            if votes is None:
                votes = state["votes"] = []
            if committed == 0:
                # No source side yet: the first decisive observation re-arms it.
                if side != 0:
                    state["side"] = side
                    state["votes"] = []
                    state["anchor_x"] = cx
                    state["anchor_y"] = cy
                state["cx"] = cx
                continue
            if side == 0:
                votes.append(0)
                if len(votes) > vote_m:
                    del votes[: len(votes) - vote_m]
                state["cx"] = cx
                continue
            if side == committed:
                # Trusted source-side observation: move the anchor, drop votes.
                state["anchor_x"] = cx
                state["anchor_y"] = cy
                state["votes"] = []
                state["cx"] = cx
                continue
            votes.append(side)
            if len(votes) > vote_m:
                del votes[: len(votes) - vote_m]
            if votes.count(side) < vote_n:
                state["cx"] = cx
                continue
            anchor_x = state.get("anchor_x")
            anchor_y = state.get("anchor_y")
            if anchor_x is None or anchor_y is None:
                # No trusted source-side centroid on this geometry yet: a
                # direction/drift cannot be derived, so do not confirm.
                state["cx"] = cx
                continue
            reached = True
            if drift_min_px > 0.0 and line_len > 0.0:
                anchor_side = side_of_line((anchor_x, anchor_y), line)
                confirm_side = side_of_line((cx, cy), line)
                if anchor_side is None or confirm_side is None:
                    reached = False
                else:
                    drift_px = abs(float(confirm_side) - float(anchor_side)) / line_len
                    reached = drift_px >= drift_min_px
            if not reached:
                # Motion mostly along the line: keep votes so a continuing
                # transit confirms as soon as the drift threshold is met.
                state["cx"] = cx
                continue
            if now - float(state.get("last_cross", 0.0)) < cooldown_sec:
                # A stable transition inside the cooldown window is absorbed
                # silently (as before) and re-armed, so its votes can never
                # fire later as a stale crossing once the cooldown expires.
                state["side"] = side
                state["cx"] = cx
                state["anchor_x"] = cx
                state["anchor_y"] = cy
                state["votes"] = []
                continue
            direction = "left_to_right" if cx > float(anchor_x) else "right_to_left"
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
        if votes_enabled:
            # Confirmed transition: the destination centroid becomes the new
            # source-side anchor and the consumed votes are cleared.
            state["anchor_x"] = cx
            state["anchor_y"] = cy
            state["votes"] = []
        _crossing_counts[direction] = _crossing_counts.get(direction, 0) + 1
        class_counts = _crossings_by_class.setdefault(object_type, {"left_to_right": 0, "right_to_left": 0})
        class_counts[direction] = class_counts.get(direction, 0) + 1
        if accept_crossing is None:
            # Non-Ubuntu caller only: the transport-owned list path. It is NOT
            # an Ubuntu fallback - a bound callback never leaves rows there.
            _crossing_pending_posts.append(crossing)
        crossings.append(crossing)
    prune_crossing_tracks(now)
    return crossings


def crossing_overlay_summary():
    line = _crossing_line_cache.get("line") or []
    return {
        "left_to_right": _crossing_counts.get("left_to_right", 0),
        "right_to_left": _crossing_counts.get("right_to_left", 0),
        # Copy both mapping levels.  The snapshot is queued asynchronously and
        # must not retain references to live per-class count dictionaries.
        "by_class": {
            class_name: dict(counts)
            for class_name, counts in _crossings_by_class.items()
        },
        "line_enabled": bool(_crossing_line_cache.get("enabled")),
        "line": [list(point) for point in line],
    }
