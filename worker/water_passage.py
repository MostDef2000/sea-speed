"""Bounded Water passage tracking and pluggable speed-measurement strategies."""
from __future__ import annotations

import math
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Deque, Dict, Iterable, List, Optional, Sequence, Tuple

Point = Tuple[float, float]
Line = Tuple[Point, Point]


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(float(ts), timezone.utc).isoformat()


def _line(raw: object) -> Optional[Line]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        return None
    points: List[Point] = []
    for value in raw:
        if isinstance(value, dict):
            x, y = value.get("x"), value.get("y")
        elif isinstance(value, (list, tuple)) and len(value) == 2:
            x, y = value
        else:
            return None
        try:
            points.append((float(x), float(y)))
        except (TypeError, ValueError):
            return None
    return (points[0], points[1])


def _side(line: Line, point: Point) -> float:
    (x1, y1), (x2, y2) = line
    x, y = point
    return (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)


def _within(value: float, low: float, high: float, eps: float = 1e-9) -> bool:
    return min(low, high) - eps <= value <= max(low, high) + eps


def _segments_intersect(a: Point, b: Point, line: Line) -> bool:
    c, d = line
    s1, s2 = _side(line, a), _side(line, b)
    if s1 == 0.0 and _within(a[0], c[0], d[0]) and _within(a[1], c[1], d[1]):
        return True
    if s2 == 0.0 and _within(b[0], c[0], d[0]) and _within(b[1], c[1], d[1]):
        return True
    if s1 * s2 > 0:
        return False
    t1 = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    t2 = (b[0] - a[0]) * (d[1] - a[1]) - (b[1] - a[1]) * (d[0] - a[0])
    return t1 * t2 <= 0


def _crossing_ts(previous: "Observation", current: "Observation", line: Line) -> float:
    s0 = abs(_side(line, previous.anchor))
    s1 = abs(_side(line, current.anchor))
    denom = s0 + s1
    ratio = 0.5 if denom <= 1e-9 else s0 / denom
    ratio = max(0.0, min(1.0, ratio))
    return previous.ts + (current.ts - previous.ts) * ratio


@dataclass(frozen=True)
class Observation:
    ts: float
    track_id: int
    anchor_x: float
    anchor_y: float
    bbox: Tuple[float, float, float, float]
    confidence: float

    @property
    def anchor(self) -> Point:
        return (self.anchor_x, self.anchor_y)


@dataclass(frozen=True)
class MeasurementResult:
    speed_status: str = "unknown"
    speed_kmh: Optional[float] = None
    speed_method: str = "unknown"
    direction: Optional[str] = None
    measurement_meta: Dict[str, object] = field(default_factory=dict)


class SpeedEstimator:
    """Strategy boundary for passage speed measurement."""

    method = "unknown"

    def update(self, observation: Observation) -> MeasurementResult:
        raise NotImplementedError

    def finalize(self) -> MeasurementResult:
        return MeasurementResult(speed_status="incomplete", speed_method=self.method)


class TwoGateSpeedEstimator(SpeedEstimator):
    method = "two_gate"

    def __init__(self, line_a: object, line_b: object, distance_m: float, enabled: bool = True):
        self.line_a = _line(line_a)
        self.line_b = _line(line_b)
        try:
            self.distance_m = float(distance_m)
        except (TypeError, ValueError):
            self.distance_m = 0.0
        self.enabled = bool(enabled) and self.line_a is not None and self.line_b is not None and self.distance_m > 0
        self.previous: Optional[Observation] = None
        self.first_line: Optional[str] = None
        self.first_ts: Optional[float] = None
        self.samples_used = 0
        self.result = MeasurementResult(speed_method=self.method)

    def _meta(self, second_line: Optional[str] = None, second_ts: Optional[float] = None) -> Dict[str, object]:
        meta: Dict[str, object] = {
            "distance_m": round(self.distance_m, 3),
            "samples_used": self.samples_used,
        }
        if self.first_line and self.first_ts is not None:
            meta[f"gate_{self.first_line.lower()}_ts"] = round(self.first_ts, 6)
        if second_line and second_ts is not None:
            meta[f"gate_{second_line.lower()}_ts"] = round(second_ts, 6)
        return meta

    def update(self, observation: Observation) -> MeasurementResult:
        self.samples_used += 1
        if not self.enabled:
            self.previous = observation
            self.result = MeasurementResult(
                speed_status="unknown",
                speed_method=self.method,
                measurement_meta={"enabled": False, "samples_used": self.samples_used},
            )
            return self.result
        if self.result.speed_status == "measured":
            self.previous = observation
            return self.result
        crossings: List[Tuple[float, str]] = []
        if self.previous is not None:
            for name, line in (("A", self.line_a), ("B", self.line_b)):
                if line is not None and _segments_intersect(self.previous.anchor, observation.anchor, line):
                    crossings.append((_crossing_ts(self.previous, observation, line), name))
        self.previous = observation
        for crossing_ts, name in sorted(crossings):
            if self.first_line is None:
                self.first_line = name
                self.first_ts = crossing_ts
                continue
            if name == self.first_line or self.first_ts is None or crossing_ts <= self.first_ts:
                continue
            elapsed = crossing_ts - self.first_ts
            if elapsed <= 0:
                continue
            speed_kmh = round((self.distance_m / elapsed) * 3.6, 2)
            direction = f"{self.first_line}->{name}"
            self.result = MeasurementResult(
                speed_status="measured",
                speed_kmh=speed_kmh,
                speed_method=self.method,
                direction=direction,
                measurement_meta={
                    **self._meta(name, crossing_ts),
                    "travel_time_sec": round(elapsed, 6),
                },
            )
            return self.result
        self.result = MeasurementResult(
            speed_status="measuring",
            speed_method=self.method,
            direction=None,
            measurement_meta=self._meta(),
        )
        return self.result

    def finalize(self) -> MeasurementResult:
        if self.result.speed_status == "measured":
            return self.result
        status = "incomplete" if self.enabled and self.samples_used else "unknown"
        self.result = MeasurementResult(
            speed_status=status,
            speed_method=self.method,
            measurement_meta=self._meta(),
        )
        return self.result


def build_two_gate_estimator(config: Dict[str, object]) -> SpeedEstimator:
    return TwoGateSpeedEstimator(
        line_a=config.get("line_a"),
        line_b=config.get("line_b"),
        distance_m=float(config.get("distance_m") or 0.0),
        enabled=bool(config.get("enabled")),
    )


def default_passage_id(ts: float) -> str:
    stamp = datetime.fromtimestamp(ts, timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"P-{stamp}-{uuid.uuid4().hex[:8]}"


@dataclass
class _PassageState:
    passage_id: str
    started_at: float
    last_seen_at: float
    estimator: SpeedEstimator
    observations: Deque[Observation]
    track_fragments: List[int] = field(default_factory=list)
    last_anchor: Optional[Point] = None
    status: str = "tracking"
    completed_at: Optional[float] = None
    confidence: float = 0.0
    best_snapshot_score: float = -1.0
    measurement: MeasurementResult = field(default_factory=MeasurementResult)


class WaterPassageEngine:
    """Bounded active-passage state independent from persistent storage."""

    def __init__(
        self,
        estimator_factory: Callable[[], SpeedEstimator],
        *,
        id_factory: Callable[[float], str] = default_passage_id,
        stitch_window_sec: float = 3.0,
        stitch_distance_px: float = 120.0,
        passage_end_gap_sec: float = 8.0,
        max_observations: int = 256,
        max_active_passages: int = 32,
        snapshot_improvement_ratio: float = 1.15,
    ):
        self.estimator_factory = estimator_factory
        self.id_factory = id_factory
        self.stitch_window_sec = max(0.1, float(stitch_window_sec))
        self.stitch_distance_px = max(1.0, float(stitch_distance_px))
        self.passage_end_gap_sec = max(self.stitch_window_sec, float(passage_end_gap_sec))
        self.max_observations = max(8, int(max_observations))
        self.max_active_passages = max(1, int(max_active_passages))
        self.snapshot_improvement_ratio = max(1.0, float(snapshot_improvement_ratio))
        self._active: Dict[str, _PassageState] = {}
        self._track_to_passage: Dict[int, str] = {}

    @property
    def active_count(self) -> int:
        return len(self._active)

    def _public(self, state: _PassageState) -> Dict[str, object]:
        return {
            "passage_id": state.passage_id,
            "camera_id": "cam1",
            "class_name": "vessel",
            "status": state.status,
            "started_at": _iso(state.started_at),
            "last_seen_at": _iso(state.last_seen_at),
            "completed_at": _iso(state.completed_at) if state.completed_at is not None else None,
            "track_fragments": list(state.track_fragments),
            "confidence": round(state.confidence, 6),
            "vessel_id": None,
            "speed_status": state.measurement.speed_status,
            "speed_kmh": state.measurement.speed_kmh,
            "speed_method": state.measurement.speed_method,
            "direction": state.measurement.direction,
            "measurement_meta": dict(state.measurement.measurement_meta),
            "observation_count": len(state.observations),
            "snapshot_score": round(max(0.0, state.best_snapshot_score), 6),
        }

    def _finalize(self, passage_id: str, ts: float) -> Dict[str, object]:
        state = self._active.pop(passage_id)
        state.measurement = state.estimator.finalize()
        state.status = "completed"
        state.completed_at = max(float(ts), state.last_seen_at)
        for track_id in list(state.track_fragments):
            if self._track_to_passage.get(track_id) == passage_id:
                self._track_to_passage.pop(track_id, None)
        return {"passage": self._public(state), "snapshot_candidate": False, "observed_track_ids": []}

    def _finalize_stale(self, ts: float, claimed: Iterable[str] = ()) -> List[Dict[str, object]]:
        claimed_ids = set(claimed)
        stale = [
            passage_id
            for passage_id, state in self._active.items()
            if passage_id not in claimed_ids and ts - state.last_seen_at > self.passage_end_gap_sec
        ]
        stale.sort(key=lambda passage_id: (self._active[passage_id].last_seen_at, passage_id))
        return [self._finalize(passage_id, ts) for passage_id in stale]

    def _ensure_capacity(self, ts: float, claimed: set[str]) -> List[Dict[str, object]]:
        if len(self._active) < self.max_active_passages:
            return []
        candidates = [state for state in self._active.values() if state.passage_id not in claimed]
        if not candidates:
            return []
        oldest = min(candidates, key=lambda state: (state.last_seen_at, state.passage_id))
        return [self._finalize(oldest.passage_id, ts)]

    def _resolve(self, track_id: int, anchor: Point, ts: float, claimed: set[str]) -> Tuple[_PassageState, bool, List[Dict[str, object]]]:
        passage_id = self._track_to_passage.get(track_id)
        if passage_id in self._active:
            return self._active[passage_id], False, []
        candidates: List[Tuple[float, _PassageState]] = []
        for state in self._active.values():
            if state.passage_id in claimed or state.last_anchor is None:
                continue
            gap = ts - state.last_seen_at
            if gap < 0 or gap > self.stitch_window_sec:
                continue
            distance = math.dist(anchor, state.last_anchor)
            if distance <= self.stitch_distance_px:
                candidates.append((distance, state))
        if candidates:
            _distance, state = min(candidates, key=lambda item: (item[0], item[1].last_seen_at, item[1].passage_id))
            if track_id not in state.track_fragments:
                state.track_fragments.append(track_id)
            self._track_to_passage[track_id] = state.passage_id
            return state, True, []
        finalized = self._ensure_capacity(ts, claimed)
        passage_id = self.id_factory(ts)
        state = _PassageState(
            passage_id=passage_id,
            started_at=ts,
            last_seen_at=ts,
            estimator=self.estimator_factory(),
            observations=deque(maxlen=self.max_observations),
            track_fragments=[track_id],
        )
        self._active[passage_id] = state
        self._track_to_passage[track_id] = passage_id
        return state, True, finalized

    def update(self, detections: Sequence[Dict[str, object]], ts: Optional[float] = None) -> List[Dict[str, object]]:
        now = time.time() if ts is None else float(ts)
        updates: List[Dict[str, object]] = []
        claimed: set[str] = set()
        observed_by_passage: Dict[str, List[int]] = {}
        snapshot_candidates: Dict[str, bool] = {}
        det_by_passage: Dict[str, Dict[str, object]] = {}
        updates.extend(self._finalize_stale(now))
        for det in detections:
            if det.get("class_name") != "vessel" or det.get("track_id") is None:
                continue
            try:
                track_id = int(det["track_id"])
                x1, y1, x2, y2 = [float(value) for value in det["bbox_xyxy"]]
                confidence = float(det.get("confidence") or 0.0)
            except (TypeError, ValueError, KeyError):
                continue
            anchor = ((x1 + x2) / 2.0, y2)
            state, _binding_changed, finalized = self._resolve(track_id, anchor, now, claimed)
            updates.extend(finalized)
            claimed.add(state.passage_id)
            observed_by_passage.setdefault(state.passage_id, []).append(track_id)
            observation = Observation(
                ts=now,
                track_id=track_id,
                anchor_x=anchor[0],
                anchor_y=anchor[1],
                bbox=(x1, y1, x2, y2),
                confidence=confidence,
            )
            state.observations.append(observation)
            state.last_seen_at = now
            state.last_anchor = anchor
            state.confidence = max(state.confidence, confidence)
            state.measurement = state.estimator.update(observation)
            state.status = "measured" if state.measurement.speed_status == "measured" else "measuring"
            area = max(1.0, (x2 - x1) * (y2 - y1))
            snapshot_score = confidence * area
            is_better = state.best_snapshot_score < 0 or snapshot_score >= state.best_snapshot_score * self.snapshot_improvement_ratio
            if is_better:
                state.best_snapshot_score = snapshot_score
                snapshot_candidates[state.passage_id] = True
                det_by_passage[state.passage_id] = det
            else:
                snapshot_candidates.setdefault(state.passage_id, False)
                det_by_passage.setdefault(state.passage_id, det)
        for passage_id in sorted(observed_by_passage):
            state = self._active.get(passage_id)
            if state is None:
                continue
            passage = self._public(state)
            updates.append({
                "passage": passage,
                "snapshot_candidate": snapshot_candidates.get(passage_id, False),
                "snapshot_detection": det_by_passage.get(passage_id),
                "observed_track_ids": list(observed_by_passage[passage_id]),
            })
        return updates

    def finalize_all(self, ts: Optional[float] = None) -> List[Dict[str, object]]:
        now = time.time() if ts is None else float(ts)
        passage_ids = sorted(self._active, key=lambda passage_id: (self._active[passage_id].last_seen_at, passage_id))
        return [self._finalize(passage_id, now) for passage_id in passage_ids]
