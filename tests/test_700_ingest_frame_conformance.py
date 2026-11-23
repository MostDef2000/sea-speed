"""Issue #700: ingest frame conformance — black/slate/freeze detection.

The production side (``FrameConformanceDetector`` +
``build_frame_conformance_state`` in ``worker/hls_motion_yolo_worker_events.py``
and the metadata-only ``post_state(metadata, overlay_path=None)`` in
``worker/worker_transport.py``) landed with the code worker; these tests pin
the OUTCOMES, never the mechanism beyond what an observable requires.

Sections (one class each):

* ``FrameConformanceDetectorOracleTests`` — deterministic in-memory uint8 BGR
  frames and an injected monotonic clock against LITERAL expectations written
  from the issue text (``black_frame``/``slate_frame``/``frozen_frame``/None),
  including negative controls (dark noisy night, changing texture, a long gap
  between different frames) and the flag-off pass-through.
* ``FrameConformanceTransitionDiagnosticsTests`` — the typed diagnostic line
  is emitted on entry and on a reason change, NOT on every frame, and the
  recovery line carries no old reason.
* ``FrameConformanceStateMetadataTests`` — ``build_frame_conformance_state``
  is metadata-only: ``frame_conforming``/``unknown_reason``/``frame_no`` and
  NO ``overlay_rev``; recovery has no reason.
* ``TransportMetadataOnlyPostTests`` — ``post_state(..., None)`` performs a
  POST with no file part and never opens a path; the overlay behaviour is
  unchanged when a path is provided.
* ``IngestLoopFrameConformanceTests`` — drives the REAL ``main()`` ingest
  loop with a finite reader on both analytics profiles and spies every
  downstream publication: rejected frames emit state/diagnostics only (no
  inference, crossing, passage, event or live publication), the heartbeat
  continues, no stale ``overlay_rev`` is posted, and the next good frame
  resumes the full pipeline.
* ``IngestFrameConformanceScopeGuardTests`` — the working tree touches only
  the admitted #700 surface (modelled on tests/test_697 ScopeGuardTests).

Environment: the battery has no numpy/cv2/ultralytics/av/requests (CI
installs the API lock only), so the heavy modules are stubbed at import when
absent — exactly as the code worker's smoke did — and the frame-oracle
classes run only when REAL numpy is importable (a MagicMock numpy left by an
earlier test does not count). cv2 is NEVER a skip reason: it is stubbed.

RED spot-check (what fails on base de883e83, before the production change;
measured by running this file against a ``git archive`` of base):

* Detector oracle — base has no ``FrameConformanceDetector`` at all, so every
  oracle/diagnostics test errors with AttributeError at ``_detector()``.
* State metadata — base has no ``build_frame_conformance_state``; those tests
  error with AttributeError.
* Transport — base ``post_state(metadata, overlay_path)`` has no default and
  unconditionally ``open(overlay_path)``: ``post_state(meta, None)`` opens
  ``None`` (TypeError swallowed -> returns False, never POSTs), so the
  ``assertTrue(ok)``/``open_mock.assert_not_called()``/``post.call_count``
  assertions all fail; the one-arg call errors (missing positional).
* Integration — base ``main()`` has no conformance gate, so the black/slate
  frames flow through the full pipeline: detect_vehicles is called for every
  frame (4 vs 2), the state posts are all overlay posts with no
  ``unknown_reason`` (length/field assertions fail) and stdout lacks the
  conformance diagnostics.
* Scope guard — keeps (passes on a clean tree, fails if an out-of-scope path
  appears in the working tree).
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from contextlib import ExitStack, redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "worker") not in sys.path:
    sys.path.insert(0, str(ROOT / "worker"))

# Guarded-optional probes (tests/test_697 idiom; run_tests.py import hygiene
# marks imports under a ModuleNotFoundError handler as guarded-optional).
# The frame oracle needs REAL numpy arrays, so a MagicMock numpy (installed by
# an earlier test when CI lacks numpy) must NOT satisfy the gate.
try:
    import numpy as np  # noqa: F401  guarded-optional probe (CI has no numpy)
except ModuleNotFoundError:
    np = None  # type: ignore[assignment]
    sys.modules["numpy"] = mock.MagicMock()
HAS_REAL_NUMPY = np is not None and isinstance(getattr(np, "ndarray", None), type)

for _heavy in ("cv2", "ultralytics", "av", "requests"):
    if _heavy not in sys.modules:
        try:
            __import__(_heavy)  # noqa: F401  guarded-optional probe
        except ModuleNotFoundError:
            sys.modules[_heavy] = mock.MagicMock()

import analytics_profiles as profiles  # noqa: E402  (repo-local worker/)
import hls_motion_yolo_worker_events as worker  # noqa: E402  (repo-local worker/)
import worker_transport  # noqa: E402  (repo-local worker/)

# ---------------------------------------------------------------------------
# Literals: the oracle. Written from the issue text FIRST — never derived
# from the module under test.
# ---------------------------------------------------------------------------

BLACK = "black_frame"
SLATE = "slate_frame"
FROZEN = "frozen_frame"

FRAME_H = 120
FRAME_W = 240  # 12 sample columns x 20 px: bar edges align with the grid
SAMPLE_COLS = 12


def _detector(enabled: str = "1", **overrides: str) -> "worker.FrameConformanceDetector":
    """Construct the detector with ONLY the frame-conformance env set.

    Thresholds are read once at construction, so the ambient environment must
    not leak overrides into the literal expectations below.
    """
    with mock.patch.dict(os.environ, {}, clear=False):
        for key in [k for k in os.environ if k.startswith("FRAME_CONFORMANCE_")]:
            del os.environ[key]
        os.environ["FRAME_CONFORMANCE_ENABLED"] = enabled
        for key, value in overrides.items():
            os.environ[key] = value
        return worker.FrameConformanceDetector()


def _zeros_frame():
    return np.zeros((FRAME_H, FRAME_W, 3), np.uint8)


def _night_frame(seed: int = 7):
    """Dark noisy night scene: low mean luma (passes the black mean gate)
    but high within-cell contrast and sparse bright lights that must VETO a
    black classification. Negative control — must classify as conforming."""
    rng = np.random.default_rng(seed)
    frame = rng.integers(0, 16, size=(FRAME_H, FRAME_W, 3), dtype=np.uint8)
    frame[10:14, 20:28] = 180  # sparse lights
    return frame


def _bars_frame():
    """Saturated vertical bars: every sample column exactly one saturated
    colour (stripe width == column width), so column uniformity, ordered
    transitions and full-frame saturation all hold."""
    frame = np.zeros((FRAME_H, FRAME_W, 3), np.uint8)
    red = (0, 0, 255)  # BGR
    blue = (255, 0, 0)
    stripe = FRAME_W // SAMPLE_COLS
    for col in range(SAMPLE_COLS):
        frame[:, col * stripe : (col + 1) * stripe] = red if col % 2 == 0 else blue
    return frame


def _texture_frame(seed: int):
    """Bright normal texture: neither black (bright, high mean) nor slate
    (columns statistically identical, no ordered transitions)."""
    rng = np.random.default_rng(seed)
    return rng.integers(60, 200, size=(FRAME_H, FRAME_W, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# 1. Detector oracle — literal expectations with an injected clock.
# ---------------------------------------------------------------------------


@unittest.skipUnless(HAS_REAL_NUMPY, "real numpy required for the uint8 BGR frame oracle (CI battery has no numpy)")
class FrameConformanceDetectorOracleTests(unittest.TestCase):
    def test_zero_frame_is_black(self) -> None:
        det = _detector()
        result = det.evaluate(_zeros_frame(), 1, 0.0)
        self.assertFalse(result.conforming)
        self.assertEqual(result.reason, BLACK)
        self.assertTrue(result.enabled)
        self.assertTrue(result.transition)  # entry into rejection
        self.assertFalse(result.recovered)

    def test_dark_noisy_night_frame_is_conforming(self) -> None:
        # Negative control: the mean gate alone would accept this frame as
        # black (mean luma <= 16); the bright-pixel/contrast veto must win.
        det = _detector()
        result = det.evaluate(_night_frame(), 1, 0.0)
        self.assertTrue(result.conforming)
        self.assertIsNone(result.reason)
        self.assertLessEqual(result.detail["mean_luma"], 16.0)

    def test_saturated_bars_frame_is_slate(self) -> None:
        det = _detector()
        result = det.evaluate(_bars_frame(), 1, 0.0)
        self.assertFalse(result.conforming)
        self.assertEqual(result.reason, SLATE)
        self.assertTrue(result.transition)
        self.assertFalse(result.recovered)

    def test_repeated_texture_freezes_exactly_at_the_confirm_window(self) -> None:
        det = _detector()
        frame = _texture_frame(11)
        stamp = 0.0
        for frame_no in range(8):  # min consecutive frames reached
            result = det.evaluate(frame, frame_no, stamp)
            self.assertIsNone(result.reason)
            stamp += 0.1
        # Identical frames but still SHORT of the 10 s confirm window.
        result = det.evaluate(frame, 9, 4.0)
        self.assertIsNone(result.reason)
        # Exactly at the confirm window -> frozen.
        result = det.evaluate(frame, 10, 10.0)
        self.assertFalse(result.conforming)
        self.assertEqual(result.reason, FROZEN)
        self.assertTrue(result.transition)
        self.assertFalse(result.recovered)

    def test_changing_texture_is_not_frozen(self) -> None:
        det = _detector()
        self.assertIsNone(det.evaluate(_texture_frame(11), 1, 0.0).reason)
        self.assertIsNone(det.evaluate(_texture_frame(12), 2, 1.0).reason)

    def test_long_gap_between_different_frames_is_not_frozen(self) -> None:
        # A huge elapsed gap alone must never freeze: the frames differ, so
        # the reference restarts instead of accumulating duration.
        det = _detector()
        self.assertIsNone(det.evaluate(_texture_frame(11), 1, 0.0).reason)
        result = det.evaluate(_texture_frame(13), 2, 500.0)
        self.assertTrue(result.conforming)
        self.assertIsNone(result.reason)

    def test_recovery_is_a_recovered_transition_back_to_conforming(self) -> None:
        det = _detector()
        first = det.evaluate(_zeros_frame(), 1, 0.0)
        self.assertEqual(first.reason, BLACK)
        self.assertTrue(first.transition)
        self.assertFalse(first.recovered)
        repeat = det.evaluate(_zeros_frame(), 2, 0.5)
        self.assertEqual(repeat.reason, BLACK)
        self.assertFalse(repeat.transition)  # no re-entry while still black
        good = det.evaluate(_texture_frame(11), 3, 1.0)
        self.assertTrue(good.conforming)
        self.assertIsNone(good.reason)
        self.assertTrue(good.transition)
        self.assertTrue(good.recovered)

    def test_flag_off_keeps_the_detector_inactive(self) -> None:
        det = _detector(enabled="0")
        result = det.evaluate(_zeros_frame(), 1, 0.0)
        self.assertFalse(result.enabled)
        self.assertTrue(result.conforming)  # a black frame stays conforming
        self.assertIsNone(result.reason)
        self.assertFalse(result.transition)
        self.assertFalse(result.recovered)
        buf = io.StringIO()
        with redirect_stdout(buf):
            det.log_startup()
        self.assertIn("FRAME_CONFORMANCE_ENABLED=0", buf.getvalue())


# ---------------------------------------------------------------------------
# 2. Transition diagnostics — printed once per transition, not per frame.
# ---------------------------------------------------------------------------


@unittest.skipUnless(HAS_REAL_NUMPY, "real numpy required for the uint8 BGR frame oracle (CI battery has no numpy)")
class FrameConformanceTransitionDiagnosticsTests(unittest.TestCase):
    def test_diagnostic_on_entry_and_reason_change_only_and_recovery(self) -> None:
        det = _detector()
        buf = io.StringIO()
        with redirect_stdout(buf):
            det.evaluate(_texture_frame(11), 1, 0.0)   # conforming start: silent
            det.evaluate(_zeros_frame(), 2, 0.5)        # entry: diagnostic
            det.evaluate(_zeros_frame(), 3, 1.0)        # same reason: silent
            det.evaluate(_bars_frame(), 4, 1.5)         # reason change: diagnostic
            det.evaluate(_bars_frame(), 5, 2.0)         # same reason: silent
            det.evaluate(_texture_frame(11), 6, 2.5)    # recovery: diagnostic
        lines = [
            line for line in buf.getvalue().splitlines()
            if line.startswith("Frame conformance:")
        ]
        self.assertEqual(len(lines), 3, lines)
        self.assertIn("frame_no=2 conforming=false reason=black_frame", lines[0])
        self.assertIn("frame_no=4 conforming=false reason=slate_frame", lines[1])
        self.assertIn("frame_no=6 conforming=true reason=none", lines[2])
        # The recovery diagnostic must not carry the old reason.
        self.assertNotIn(BLACK, lines[2])
        self.assertNotIn(SLATE, lines[2])


# ---------------------------------------------------------------------------
# 3. State metadata — metadata-only, typed reason, no overlay revision.
# ---------------------------------------------------------------------------


class FrameConformanceStateMetadataTests(unittest.TestCase):
    def _profile(self):
        return profiles.get_profile("road-v1")

    def test_rejected_state_is_metadata_only_with_typed_reason(self) -> None:
        state = worker.build_frame_conformance_state(
            7, self._profile(), BLACK, {"mean_luma": 0.0}, frame=None
        )
        self.assertFalse(state["frame_conforming"])
        self.assertEqual(state["unknown_reason"], BLACK)
        self.assertEqual(state["frame_no"], 7)
        self.assertNotIn("overlay_rev", state)
        self.assertIn(BLACK, state["message"])
        self.assertEqual(state["frame_conformance_detail"], {"mean_luma": 0.0})
        self.assertTrue(state["worker_online"])

    def test_recovery_state_has_no_reason_and_no_overlay_rev(self) -> None:
        state = worker.build_frame_conformance_state(8, self._profile(), None, {}, frame=None)
        self.assertTrue(state["frame_conforming"])
        self.assertNotIn("unknown_reason", state)
        self.assertNotIn("overlay_rev", state)

    def test_state_carries_frame_geometry_when_a_frame_is_supplied(self) -> None:
        frame = types.SimpleNamespace(shape=(FRAME_H, FRAME_W, 3))
        state = worker.build_frame_conformance_state(9, self._profile(), SLATE, {}, frame=frame)
        self.assertEqual(state["frame_width"], FRAME_W)
        self.assertEqual(state["frame_height"], FRAME_H)
        self.assertNotIn("overlay_rev", state)

    def test_worker_vocabulary_matches_the_written_literals(self) -> None:
        # The vocabulary is loaded by file path from api/app/unknown_reason.py;
        # the worker's constants must be exactly the reserved literals.
        self.assertEqual(worker.BLACK_FRAME, BLACK)
        self.assertEqual(worker.SLATE_FRAME, SLATE)
        self.assertEqual(worker.FROZEN_FRAME, FROZEN)


# ---------------------------------------------------------------------------
# 4. Transport — metadata-only POST vs. the unchanged overlay POST.
# ---------------------------------------------------------------------------


class TransportMetadataOnlyPostTests(unittest.TestCase):
    def _env(self):
        return mock.patch.dict(
            os.environ,
            {"SEA_SPEED_API_URL": "http://api.test/state", "SEA_SPEED_API_TOKEN": "test-token"},
        )

    def _response(self):
        return types.SimpleNamespace(status_code=200, text="")

    def test_metadata_only_post_never_opens_a_path_and_sends_no_file_part(self) -> None:
        with self._env(), mock.patch.object(
            worker_transport.requests, "post", return_value=self._response()
        ) as post, mock.patch("builtins.open") as open_mock:
            ok_none = worker_transport.post_state({"frame_no": 5}, None)
            ok_default = worker_transport.post_state({"frame_no": 6})
        self.assertTrue(ok_none)
        self.assertTrue(ok_default)
        open_mock.assert_not_called()
        self.assertEqual(post.call_count, 2)
        for call in post.call_args_list:
            kwargs = call.kwargs
            self.assertNotIn("files", kwargs)
            self.assertEqual(kwargs["timeout"], 10)
            self.assertEqual(kwargs["headers"], {"Authorization": "Bearer test-token"})
        metadata = json.loads(post.call_args_list[0].kwargs["data"]["metadata"])
        self.assertEqual(metadata, {"frame_no": 5})

    def test_overlay_post_keeps_the_file_part_behaviour(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            overlay = Path(td) / "latest_overlay.jpg"
            overlay.write_bytes(b"\xff\xd8probe\xff\xd9")
            with self._env(), mock.patch.object(
                worker_transport.requests, "post", return_value=self._response()
            ) as post, mock.patch("builtins.open", wraps=open) as open_mock:
                ok = worker_transport.post_state({"frame_no": 7}, overlay)
        self.assertTrue(ok)
        self.assertEqual(post.call_count, 1)
        kwargs = post.call_args.kwargs
        self.assertIn("files", kwargs)
        self.assertEqual(kwargs["files"]["overlay"][0], "overlay.jpg")
        open_mock.assert_called_once_with(overlay, "rb")


# ---------------------------------------------------------------------------
# 5. Integration — the real ingest loop, both profiles, spy downstream.
# ---------------------------------------------------------------------------


class _FiniteReader:
    def __init__(self, frames):
        self._frames = list(frames)
        self.closed = False

    def read_frame(self):
        return self._frames.pop(0) if self._frames else None

    def close(self):
        self.closed = True


class _FakeClock:
    """Monotonic-ish clock: every time() call advances one second, which
    guarantees the state heartbeat interval elapses between frames."""

    def __init__(self):
        self.value = 1000.0

    def time(self):
        self.value += 1.0
        return self.value

    def monotonic(self):
        return self.value


class _FakeMotionDetector:
    def __init__(self):
        pass

    def process(self, frame):
        return True, 12.0, []

    def is_ai_active(self):
        return True


def _run_main(frames, profile_name: str):
    """Drive the real worker.main() over a finite reader with every
    downstream publication spied. Returns the recorded observations."""
    reader = _FiniteReader(frames)
    clock = _FakeClock()
    state_calls = []
    spies = {
        "detect": [], "live": [], "recall": [], "crossing": [],
        "flush": [], "draw": [], "event": [], "passage": [],
    }

    def post_state_spy(metadata, overlay_path=None):
        state_calls.append((dict(metadata), overlay_path))
        return True

    def detect_spy(model, frame, diagnostics=None):
        spies["detect"].append(frame)
        return []

    def live_spy(envelope):
        spies["live"].append(envelope)
        return True

    def draw_spy(**kwargs):
        spies["draw"].append(kwargs)
        return kwargs["frame"]

    def event_spy(event, snapshot_path):
        spies["event"].append(event)
        return True

    def passage_spy(passage, snapshot_path):
        spies["passage"].append(passage)
        return True

    def flush_spy():
        spies["flush"].append(1)

    def crossing_spy(detections, now):
        spies["crossing"].append(now)

    def recall_spy(frame_no, raw, roi_points, detections, profile):
        spies["recall"].append(frame_no)

    env = {
        "ANALYTICS_PROFILE": profile_name,
        "CAMERA_ID": "cam700_test",
        "FRAME_CONFORMANCE_ENABLED": "1",
        "STATE_POST_INTERVAL_SEC": "1.0",
        "MOTION_GATE_MODE": "gated",
        "SEA_SPEED_SOURCE_COMMIT": "sha-test",
    }
    stdout = io.StringIO()
    with ExitStack() as stack:
        stack.enter_context(mock.patch.dict(os.environ, {}, clear=False))
        for key in [k for k in os.environ if k.startswith("FRAME_CONFORMANCE_")]:
            del os.environ[key]
        os.environ.update(env)
        stack.enter_context(mock.patch.object(worker, "time", clock))
        stack.enter_context(mock.patch.object(worker, "YOLO", lambda name: mock.MagicMock()))
        stack.enter_context(
            mock.patch.object(worker, "start_media_reader", lambda av_module=None: reader)
        )
        stack.enter_context(mock.patch.object(worker, "post_state", post_state_spy))
        stack.enter_context(mock.patch.object(worker, "post_live_envelope", live_spy))
        stack.enter_context(mock.patch.object(worker, "detect_vehicles", detect_spy))
        stack.enter_context(mock.patch.object(worker, "draw_overlay", draw_spy))
        stack.enter_context(
            mock.patch.object(
                worker, "prepare_roi_processing_frame",
                lambda frame, motion_detector: (frame, []),
            )
        )
        stack.enter_context(mock.patch.object(worker, "MotionDetector", _FakeMotionDetector))
        stack.enter_context(mock.patch.object(worker, "post_event", event_spy))
        stack.enter_context(mock.patch.object(worker, "post_passage", passage_spy))
        stack.enter_context(mock.patch.object(worker, "flush_crossing_posts", flush_spy))
        stack.enter_context(mock.patch.object(worker, "update_crossing_counts", crossing_spy))
        stack.enter_context(
            mock.patch.object(worker, "maybe_emit_water_recall_diagnostics", recall_spy)
        )
        stack.enter_context(mock.patch.object(worker, "fetch_speed_lines_config", lambda: {}))
        with redirect_stdout(stdout):
            worker.main()
    return types.SimpleNamespace(
        reader=reader, state_calls=state_calls, spies=spies, stdout=stdout.getvalue()
    )


@unittest.skipUnless(HAS_REAL_NUMPY, "real numpy required for the uint8 BGR frame oracle (CI battery has no numpy)")
class IngestLoopFrameConformanceTests(unittest.TestCase):
    def test_road_rejects_black_frames_publications_and_resumes(self) -> None:
        good1, black1, black2, good2 = (
            _texture_frame(21), _zeros_frame(), _zeros_frame(), _texture_frame(22)
        )
        drive = _run_main([good1, black1, black2, good2], "road-v1")

        self.assertTrue(drive.reader.closed)
        self.assertEqual(len(drive.state_calls), 5, drive.state_calls)
        full1, rejected1, rejected2, recovered, full2 = drive.state_calls

        # Good frame: normal overlay-bearing state.
        self.assertIsNotNone(full1[1])
        self.assertTrue(full1[0]["frame_conforming"])
        self.assertEqual(full1[0]["frame_no"], 1)
        self.assertEqual(full1[0]["overlay_rev"], 1)
        self.assertNotIn("unknown_reason", full1[0])

        # Rejected frames: metadata-only heartbeat with the typed reason,
        # a fresh frame_no, and NO overlay revision (no stale revision).
        for call, frame_no in ((rejected1, 2), (rejected2, 3)):
            metadata, overlay_path = call
            self.assertIsNone(overlay_path)
            self.assertFalse(metadata["frame_conforming"])
            self.assertEqual(metadata["unknown_reason"], BLACK)
            self.assertEqual(metadata["frame_no"], frame_no)
            self.assertNotIn("overlay_rev", metadata)

        # Recovery: metadata-only, conforming, no reason, no revision.
        recovered_metadata, recovered_overlay = recovered
        self.assertIsNone(recovered_overlay)
        self.assertTrue(recovered_metadata["frame_conforming"])
        self.assertNotIn("unknown_reason", recovered_metadata)
        self.assertNotIn("overlay_rev", recovered_metadata)
        self.assertEqual(recovered_metadata["frame_no"], 4)

        # Next good frame: full pipeline resumes with a FRESH overlay rev.
        self.assertIsNotNone(full2[1])
        self.assertTrue(full2[0]["frame_conforming"])
        self.assertEqual(full2[0]["frame_no"], 4)
        self.assertEqual(full2[0]["overlay_rev"], 4)
        self.assertNotIn("unknown_reason", full2[0])

        # No inference / crossing / passage / event / live from rejected frames.
        self.assertEqual(len(drive.spies["detect"]), 2)
        self.assertIs(drive.spies["detect"][0], good1)
        self.assertIs(drive.spies["detect"][1], good2)
        self.assertEqual(len(drive.spies["live"]), 2)
        self.assertEqual(len(drive.spies["crossing"]), 2)
        self.assertEqual(len(drive.spies["flush"]), 2)
        self.assertEqual(len(drive.spies["draw"]), 2)
        self.assertEqual(drive.spies["event"], [])
        self.assertEqual(drive.spies["passage"], [])
        self.assertEqual(drive.spies["recall"], [])

        # Typed diagnostics and state posts are on stdout.
        out = drive.stdout
        self.assertIn("Frame conformance: frame_no=2 conforming=false reason=black_frame", out)
        self.assertIn("Frame conformance: frame_no=4 conforming=true reason=none", out)
        self.assertNotIn("Frame conformance: frame_no=3 conforming", out)
        self.assertIn("POST state ok frame_conforming=false reason=black_frame frame_no=2", out)
        self.assertIn("POST state ok frame_conforming=true frame_no=4", out)

    def test_water_rejects_slate_frame_publications_and_resumes(self) -> None:
        good1, slate, good2 = (
            _texture_frame(31), _bars_frame(), _texture_frame(32)
        )
        drive = _run_main([good1, slate, good2], "water-v1")

        self.assertTrue(drive.reader.closed)
        self.assertEqual(len(drive.state_calls), 4, drive.state_calls)
        full1, rejected, recovered, full2 = drive.state_calls

        self.assertIsNotNone(full1[1])
        self.assertTrue(full1[0]["frame_conforming"])
        self.assertEqual(full1[0]["frame_no"], 1)
        self.assertEqual(full1[0]["overlay_rev"], 1)

        rejected_metadata, rejected_overlay = rejected
        self.assertIsNone(rejected_overlay)
        self.assertFalse(rejected_metadata["frame_conforming"])
        self.assertEqual(rejected_metadata["unknown_reason"], SLATE)
        self.assertEqual(rejected_metadata["frame_no"], 2)
        self.assertNotIn("overlay_rev", rejected_metadata)

        recovered_metadata, recovered_overlay = recovered
        self.assertIsNone(recovered_overlay)
        self.assertTrue(recovered_metadata["frame_conforming"])
        self.assertNotIn("unknown_reason", recovered_metadata)
        self.assertNotIn("overlay_rev", recovered_metadata)
        self.assertEqual(recovered_metadata["frame_no"], 3)

        self.assertIsNotNone(full2[1])
        self.assertTrue(full2[0]["frame_conforming"])
        self.assertEqual(full2[0]["overlay_rev"], 3)

        # Rejected frame published no inference/live/passage/event output;
        # recall diagnostics ran only on the two good frames.
        self.assertEqual(len(drive.spies["detect"]), 2)
        self.assertIs(drive.spies["detect"][0], good1)
        self.assertIs(drive.spies["detect"][1], good2)
        self.assertEqual(len(drive.spies["live"]), 2)
        self.assertEqual(drive.spies["recall"], [1, 3])
        self.assertEqual(drive.spies["event"], [])
        self.assertEqual(drive.spies["passage"], [])

        out = drive.stdout
        self.assertIn("Frame conformance: frame_no=2 conforming=false reason=slate_frame", out)
        self.assertIn("Frame conformance: frame_no=3 conforming=true reason=none", out)
        self.assertIn("POST state ok frame_conforming=false reason=slate_frame frame_no=2", out)
        self.assertIn("POST state ok frame_conforming=true frame_no=3", out)


# ---------------------------------------------------------------------------
# 6. Scope guard — only the admitted #700 surface, no API/workflow/lockfile.
# ---------------------------------------------------------------------------


class IngestFrameConformanceScopeGuardTests(unittest.TestCase):
    """No API/workflow/lockfile change; only the admitted production paths."""

    ALLOWED_CHANGE_PREFIXES = (
        "tests/",
        "worker/hls_motion_yolo_worker_events.py",
        "worker/worker_transport.py",
        "deploy/worker/ubuntu/worker.env.example",
        "deploy/worker/ubuntu/road-worker.env.example",
        "specs/700-ingest-frame-conformance/",
    )
    FORBIDDEN_PREFIXES = (".github/", ".gitlab", "api/")

    def _changed_paths(self) -> list[str]:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=all"],
            capture_output=True,
            text=True,
            check=True,
        )
        paths: list[str] = []
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ")[-1]
            paths.append(path.strip().strip('"'))
        return paths

    def test_working_tree_touches_only_the_700_surface_and_tests(self) -> None:
        changed = self._changed_paths()
        offenders = [
            path
            for path in changed
            if not any(path.startswith(prefix) for prefix in self.ALLOWED_CHANGE_PREFIXES)
        ]
        self.assertEqual(
            offenders,
            [],
            f"out-of-scope working-tree changes (issue #700 surface only): {offenders}",
        )

    def test_no_workflow_lockfile_or_api_change(self) -> None:
        changed = self._changed_paths()
        for path in changed:
            with self.subTest(path=path):
                self.assertFalse(
                    any(path.startswith(prefix) for prefix in self.FORBIDDEN_PREFIXES),
                    f"forbidden path changed: {path}",
                )
                self.assertFalse(
                    path.endswith(".lock") or path.endswith(".lock.txt"),
                    f"lockfile changed: {path}",
                )
                self.assertNotIn("package-lock.json", path)
                self.assertNotIn("runtime-lock.json", path)


if __name__ == "__main__":
    unittest.main()
