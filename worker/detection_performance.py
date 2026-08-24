"""Detection performance telemetry helpers for bounded Worker pipeline.

Provides lightweight stage timing, effective FPS, frame-age and p95 without external deps.
"""
from __future__ import annotations

import collections
import time
from dataclasses import dataclass, field


@dataclass
class StageTimers:
    decode_ms: float = 0.0
    inference_ms: float = 0.0
    jpeg_ms: float = 0.0
    http_ms: float = 0.0


@dataclass
class PerformanceTracker:
    window_sec: float = 5.0
    _times: collections.deque = field(default_factory=lambda: collections.deque())
    _decoded_times: collections.deque = field(default_factory=lambda: collections.deque())
    _inferred_times: collections.deque = field(default_factory=lambda: collections.deque())
    _inference_ms: collections.deque = field(default_factory=lambda: collections.deque(maxlen=100))
    _frame_ages_ms: collections.deque = field(default_factory=lambda: collections.deque(maxlen=100))
    _dropped: int = 0
    _published: int = 0

    def record_decoded(self, *, ingest_mono: float) -> None:
        now = time.monotonic()
        self._decoded_times.append(now)
        cutoff = now - self.window_sec
        while self._decoded_times and self._decoded_times[0] < cutoff:
            self._decoded_times.popleft()

    def record_inferred(self, *, ingest_mono: float, inference_ms: float, frame_age_ms: float) -> None:
        now = ingest_mono if ingest_mono else time.monotonic()
        # use wall time for window but ingest for age consistency
        wall = time.monotonic()
        self._inferred_times.append(wall)
        self._times.append(wall)
        self._inference_ms.append(float(inference_ms))
        self._frame_ages_ms.append(float(frame_age_ms))
        cutoff = wall - self.window_sec
        while self._inferred_times and self._inferred_times[0] < cutoff:
            self._inferred_times.popleft()
        while self._times and self._times[0] < cutoff:
            self._times.popleft()

    def record_published(self) -> None:
        self._published += 1

    def record_frame(self, *, ingest_mono: float, inference_ms: float, frame_age_ms: float) -> None:
        # backward-compat: treat as inferred completion; decoded path should call record_decoded separately
        if inference_ms:
            self.record_inferred(ingest_mono=ingest_mono, inference_ms=inference_ms, frame_age_ms=frame_age_ms)
        else:
            self.record_decoded(ingest_mono=ingest_mono)

    def record_dropped(self, count: int = 1) -> None:
        self._dropped += int(count)

    def effective_fps(self) -> float:
        src = self._inferred_times if self._inferred_times else self._times
        if not src:
            return 0.0
        if len(src) < 2:
            return 0.0
        span = src[-1] - src[0]
        if span <= 0:
            return 0.0
        return (len(src) - 1) / span

    def decoded_fps(self) -> float:
        if len(self._decoded_times) < 2:
            return 0.0
        span = self._decoded_times[-1] - self._decoded_times[0]
        return (len(self._decoded_times) - 1) / span if span > 0 else 0.0

    def p95_inference_ms(self) -> float:
        if not self._inference_ms:
            return 0.0
        vals = sorted(self._inference_ms)
        idx = int(0.95 * (len(vals) - 1))
        return float(vals[idx])

    def avg_frame_age_ms(self) -> float:
        if not self._frame_ages_ms:
            return 0.0
        return float(sum(self._frame_ages_ms) / len(self._frame_ages_ms))

    def snapshot(self) -> dict[str, float]:
        return {
            "effective_fps": float(self.effective_fps()),
            "decoded_fps": float(self.decoded_fps()),
            "p95_inference_ms": float(self.p95_inference_ms()),
            "avg_frame_age_ms": float(self.avg_frame_age_ms()),
            "dropped": float(self._dropped),
            "published": float(self._published),
        }

    @staticmethod
    def check_parity_within_tolerance(a_xyxy: list[int], b_xyxy: list[int], tol: int = 1) -> bool:
        if len(a_xyxy) != 4 or len(b_xyxy) != 4:
            return False
        return all(abs(int(a) - int(b)) <= tol for a, b in zip(a_xyxy, b_xyxy))
