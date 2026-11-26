"""Issue #699 REC indicator — witness freshness, no-false-REC, state
enrichment, ingest parity and scope guard.

The production side (``RECORDING_WITNESS_FRESHNESS_SEC`` /
``recording_witness_path`` / ``write_recording_witness`` in
``worker/recorder.py``, the witness write inside ``_finalize`` in
``worker/recorder_rtsp.py``, and ``recording_last_success_at`` /
``_with_recording_state`` in ``worker/worker_transport.py``) landed with the
code worker; these tests pin the OUTCOMES from ``specs/699-rec-indicator``
AC-001..AC-009 with literal expectations written from the spec text, never
derived from the implementation.

Sections (one class each):

* ``RecordingWitnessFreshnessTests`` — AC-007/AC-008/AC-009 (R-5): the
  freshness matrix of ``recording_last_success_at()``: a fresh witness returns
  the exact ISO string it holds; 29.9 s old still returns it and exactly
  30.0 s old returns null (both measured on a frozen clock); expired, future,
  wrong-camera, corrupt-JSON, non-object, non-string, naive-timestamp,
  unreadable and missing witnesses all return null; a leftover fresh witness
  with ``SEA_SPEED_RECORDER_ENABLED=0`` returns null.
* ``RecordingWitnessWriteTests`` / ``RtspRecordingWitnessWriteTests`` —
  AC-001..AC-006 (R-1/R-2): NO FALSE REC. A disabled recorder, a process that
  only cycles on a malformed playlist, an init-only HLS cycle, a failed upload
  and an empty/over-cap RTSP clip write NO witness; a successful completed HLS
  segment and a successful nonempty finalized RTSP clip write exactly
  ``<camera>-recording-witness.json`` with ``camera_id`` and a fresh UTC ISO
  ``last_success_at``. The init object itself never writes one.
* ``StateEnrichmentTests`` — AC-005/AC-006 + R-4/R-6: ``post_state`` carries
  ``recording_last_success_at`` on all three post paths (normal overlay,
  conformance metadata-only, recovery metadata-only), never mutates the
  caller's dict, replaces a stale prior value with the fresh value or an
  explicit null, keeps posting when the witness read fails, and the transport
  top-level import allowlist still holds (no new top-level imports).
* ``RecIngestParityTests`` — the deterministic reader argv and the raw frame
  bytes are identical across REC states (unset / off / on / failing).
* ``RecIndicatorScopeGuardTests`` — pinned BASE → ``HEAD`` UNION working
  tree, fail-closed: allowed = ``tests/`` + the three admitted worker files +
  the two Ubuntu env examples + ``specs/699-rec-indicator/`` +
  ``scripts/ci/validate_sdd.py`` (grandfather entry only) + the six
  REC-badge frontend files (amended in-tree by the spawning session after the
  work order was issued — see the allowlist comment); forbidden =
  ``api/``, ``worker/hls_motion_yolo_worker_events.py``, ``.github/``,
  lockfiles, and every path outside the allowlist (so any OTHER frontend path
  still fails the guard).

Environment: stdlib-only top-level imports (battery import-hygiene scan);
numpy/requests probed guarded-optional (tests/test_697 idiom). No private
media, no real credentials, no network beyond loopback.

RED spot-check (what fails on base ``ff82e19``, before the production
change; measured by running this file against a clone of base with these
tests copied in):

* Freshness — base ``worker/worker_transport.py`` has no
  ``recording_last_success_at``: every freshness test errors with
  AttributeError.
* No-false-REC — base ``worker/recorder.py`` has no
  ``write_recording_witness``/``recording_witness_path`` and never writes a
  witness, so the successful-segment test fails on the missing file, and
  base ``worker/recorder_rtsp.py`` never writes one either, so the
  successful-clip test fails on the missing file.
* Enrichment — base ``post_state`` posts the caller dict verbatim: the
  ``recording_last_success_at`` key assertions fail and
  ``worker_transport.recording_last_success_at`` does not exist.
* Deliberate GREEN-on-base regression pins (the #696/#699 convention): the
  ingest-parity tests, the scope guard, the import-allowlist pin and the
  witness-ABSENCE cases (disabled / init-only / malformed playlist / empty
  and over-cap clips) — the reader substrate and the guard inputs exist at
  base and no witness writer exists there either; they are not change
  oracles.
"""

from __future__ import annotations

import ast
import contextlib
import fnmatch
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = ROOT / "worker"
for _root in (str(ROOT), str(WORKER_DIR)):
    if _root not in sys.path:
        sys.path.insert(0, _root)

# Guarded-optional probes (tests/test_697 idiom): CI's battery is stdlib+
# pyyaml; only genuinely missing names are stubbed, a real module stays real.
for _heavy in ("numpy", "requests"):
    if _heavy not in sys.modules:
        try:
            __import__(_heavy)  # noqa: F401  guarded-optional probe
        except ModuleNotFoundError:
            sys.modules[_heavy] = mock.MagicMock()

from tests.test_699_recorder import (  # noqa: E402  (repo-local tests/)
    INIT_BYTES,
    MALFORMED_PLAYLIST,
    RECORDER_SCRIPT,
    RecorderTestBase,
    drive_recorder_cycles,
    load_recorder,
)
from tests.test_699b_rtsp_recorder import (  # noqa: E402  (repo-local tests/)
    RtspRecorderTestBase,
    load_entrypoint,
)

import worker_transport  # noqa: E402  (repo-local worker/)

# ---------------------------------------------------------------------------
# Literals: the oracle. Written from specs/699-rec-indicator FIRST — never
# derived from the module under test.
# ---------------------------------------------------------------------------

CAMERA_ID = "cam1"
WITNESS_SUFFIX = "-recording-witness.json"
FRESHNESS_SEC = 30.0  # spec R-5: fixed evidence window, not a setting
FRESH_BOUNDARY_SEC = 29.9  # AC-007: still fresh
EXPIRED_SEC = 31.0  # AC-007: past the window
FUTURE_SEC = 60.0  # AC-007: a future timestamp is never fresh

# AC-002: an EXT-X-MAP init object and nothing else.
INIT_ONLY_PLAYLIST = (
    b"#EXTM3U\n"
    b"#EXT-X-VERSION:7\n"
    b"#EXT-X-MEDIA-SEQUENCE:7\n"
    b'#EXT-X-MAP:URI="init.mp4"\n'
    b"#EXT-X-ENDLIST\n"
)

# Top-level import allowlist for worker_transport (the transport module's own
# documented policy, mirrored by tests/test_worker_transport_module.py):
# requests + json/time/pathlib + the repo-pure siblings. NOT included:
# datetime/re (the REC reader imports both FUNCTION-LOCALLY on purpose).
TRANSPORT_IMPORT_ALLOWLIST = frozenset(
    {"json", "pathlib", "requests", "time", "worker_kernel", "worker_media"}
)

# Issue #699 REC-indicator scope-guard pins.
BASE_SHA = "ff82e199fe3ab18d6d585a9ef2c60cd43613d606"
HEAD_REF = "HEAD"

ALLOWED_CHANGE_PREFIXES = (
    "tests/",
    "worker/recorder.py",
    "worker/recorder_rtsp.py",
    "worker/worker_transport.py",
    "deploy/worker/ubuntu/*.env.example",
    "specs/699-rec-indicator/",
    # REC badge on all three operator pages (MIXED contour, owner-approved).
    "frontend/sea-speed/index.html",
    "frontend/sea-speed/main.js",
    "frontend/sea-speed/road/index.html",
    "frontend/sea-speed/road/main.js",
    "frontend/sea-speed/cameras/index.html",
    "frontend/sea-speed/cameras/cameras.js",
    # Grandfather entry only: the #699 prefix-collision row for this spec.
    "scripts/ci/validate_sdd.py",
)
FORBIDDEN_CHANGE_PREFIXES = (
    "api/",
    "worker/hls_motion_yolo_worker_events.py",
    ".github/",
    ".gitlab",
)
FORBIDDEN_LOCKFILE_NAMES = ("package-lock.json", "runtime-lock.json")
FORBIDDEN_LOCKFILE_SUFFIXES = (".lock", ".lock.txt")


def witness_files(root: Path) -> list:
    """Every REC witness under ``root``, sorted by file name."""
    return sorted(path.name for path in root.rglob(f"*{WITNESS_SUFFIX}"))


def read_witness(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def assert_fresh_utc_iso(test: unittest.TestCase, payload: dict) -> None:
    """``last_success_at`` is a past, in-window UTC ISO timestamp (R-2/R-5)."""
    test.assertEqual(payload["camera_id"], CAMERA_ID)
    success = datetime.fromisoformat(payload["last_success_at"])
    test.assertIsNotNone(
        success.tzinfo, "last_success_at must carry a UTC offset (ISO, aware)"
    )
    age = (datetime.now(timezone.utc) - success).total_seconds()
    test.assertGreaterEqual(age, 0.0, "last_success_at must not be in the future")
    test.assertLess(
        age,
        FRESHNESS_SEC,
        "a just-written witness must be inside the 30 s window",
    )


@contextlib.contextmanager
def frozen_utc_now(moment: datetime):
    """Freeze ``datetime.now(tz)`` for the AC-007 boundary measurements."""
    real = datetime

    class _Frozen(real):
        @classmethod
        def now(cls, tz=None):
            return moment if tz is None else moment.astimezone(tz)

    with mock.patch("datetime.datetime", _Frozen):
        yield


# ---------------------------------------------------------------------------
# 1. Witness freshness matrix (AC-007 / AC-008 / AC-009, spec R-5)
# ---------------------------------------------------------------------------


class RecordingWitnessFreshnessTests(unittest.TestCase):
    """``recording_last_success_at()``: fresh → ISO string, everything else → None."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="test699-rec-")
        self.addCleanup(tmp.cleanup)
        self.spool = Path(tmp.name) / "spool"
        self.spool.mkdir(parents=True)

    def _env(self, **overrides: str):
        values = {
            "SEA_SPEED_RECORDER_ENABLED": "1",
            "SEA_SPEED_RECORDER_SPOOL_DIR": str(self.spool),
            "CAMERA_ID": CAMERA_ID,
        }
        values.update(overrides)
        return mock.patch.dict(os.environ, values)

    def _write(self, payload, *, camera: str = CAMERA_ID, raw: str | None = None) -> Path:
        path = self.spool / f"{camera}{WITNESS_SUFFIX}"
        text = (
            raw
            if raw is not None
            else json.dumps(payload, sort_keys=True, separators=(",", ":"))
        )
        path.write_text(text, encoding="utf-8")
        return path

    @staticmethod
    def _payload(age_sec: float, camera: str = CAMERA_ID) -> dict:
        moment = datetime.now(timezone.utc) - timedelta(seconds=age_sec)
        return {"camera_id": camera, "last_success_at": moment.isoformat()}

    def test_fresh_witness_returns_the_exact_iso_string(self) -> None:
        payload = self._payload(1.0)
        self._write(payload)
        with self._env():
            self.assertEqual(
                worker_transport.recording_last_success_at(),
                payload["last_success_at"],
                "a fresh witness must report its own timestamp verbatim",
            )

    def test_witness_29_9_seconds_old_is_still_fresh(self) -> None:
        moment = datetime(2026, 11, 26, 12, 0, 0, tzinfo=timezone.utc)
        timestamp = (moment - timedelta(seconds=FRESH_BOUNDARY_SEC)).isoformat()
        self._write({"camera_id": CAMERA_ID, "last_success_at": timestamp})
        with self._env(), frozen_utc_now(moment):
            self.assertEqual(
                worker_transport.recording_last_success_at(),
                timestamp,
                "AC-007: 29.9 s old is still inside the window",
            )

    def test_witness_exactly_30_seconds_old_is_null(self) -> None:
        moment = datetime(2026, 11, 26, 12, 0, 0, tzinfo=timezone.utc)
        timestamp = (moment - timedelta(seconds=FRESHNESS_SEC)).isoformat()
        self._write({"camera_id": CAMERA_ID, "last_success_at": timestamp})
        with self._env(), frozen_utc_now(moment):
            self.assertIsNone(
                worker_transport.recording_last_success_at(),
                "AC-007: exactly 30 s old is already outside the window",
            )

    def test_expired_witness_is_null(self) -> None:
        self._write(self._payload(EXPIRED_SEC))
        with self._env():
            self.assertIsNone(worker_transport.recording_last_success_at())

    def test_future_timestamp_is_null(self) -> None:
        self._write(self._payload(-FUTURE_SEC))
        with self._env():
            self.assertIsNone(
                worker_transport.recording_last_success_at(),
                "AC-007: a future timestamp is never fresh evidence",
            )

    def test_wrong_camera_witness_is_null(self) -> None:
        # The file sits at cam1's path but claims another camera.
        self._write(self._payload(1.0, camera="cam2"))
        with self._env():
            self.assertIsNone(worker_transport.recording_last_success_at())

    def test_corrupt_json_is_null(self) -> None:
        self._write(None, raw="{not json")
        with self._env():
            self.assertIsNone(worker_transport.recording_last_success_at())

    def test_missing_witness_is_null(self) -> None:
        with self._env():
            self.assertIsNone(worker_transport.recording_last_success_at())

    def test_leftover_fresh_witness_with_recording_disabled_is_null(self) -> None:
        # AC-009: a valid fresh witness left over from a previous enabled run.
        self._write(self._payload(1.0))
        with self._env(SEA_SPEED_RECORDER_ENABLED="0"):
            self.assertIsNone(worker_transport.recording_last_success_at())

    def test_unusable_payload_shapes_are_null(self) -> None:
        cases = {
            "json array": "[1, 2, 3]",
            "json string": '"cam1"',
            "missing timestamp": json.dumps({"camera_id": CAMERA_ID}),
            "non-string timestamp": json.dumps(
                {"camera_id": CAMERA_ID, "last_success_at": 1700000000}
            ),
            "naive timestamp": json.dumps(
                {"camera_id": CAMERA_ID, "last_success_at": "2026-11-26T12:00:00"}
            ),
        }
        for label, raw in cases.items():
            with self.subTest(shape=label):
                for stale in self.spool.glob(f"*{WITNESS_SUFFIX}"):
                    stale.unlink()
                self._write(None, raw=raw)
                with self._env():
                    self.assertIsNone(worker_transport.recording_last_success_at())

    def test_unreadable_witness_is_null(self) -> None:
        # The witness path exists but cannot be read as a file.
        (self.spool / f"{CAMERA_ID}{WITNESS_SUFFIX}").mkdir()
        with self._env():
            self.assertIsNone(worker_transport.recording_last_success_at())


# ---------------------------------------------------------------------------
# 2. NO FALSE REC — the witness is written only by a successful completed
#    segment (AC-001..AC-006, spec R-1/R-2)
# ---------------------------------------------------------------------------


class RecordingWitnessWriteTests(RecorderTestBase):
    """HLS arm: init objects, failed uploads and idle cycles write nothing."""

    def _hls_config(self, server):
        rec = load_recorder()
        key = self.tmp / "key"
        key.write_text("fake-test-key-not-a-secret\n", encoding="utf-8")
        config = rec.RecorderConfig()
        config.hls_url = server.playlist_url
        config.key_path = key
        config.spool_dir = self.spool_dir
        config.min_free_bytes = 0  # the floor has its own dedicated tests
        config.destination = f"{self.dest_dir}/"
        config.poll_sec = 0.5
        config.rsync_retries = 2
        config.rsync_backoff_sec = 0.0
        config.rsync_timeout_sec = 5.0
        return config

    def test_successful_completed_segment_writes_the_witness(self) -> None:
        server = self.start_hls_server()
        self.set_rsync_mode("ok")
        instance = load_recorder().HlsRecorder(self._hls_config(server))
        out = drive_recorder_cycles(instance, cycles=1)
        self.assertIn("recorder object ok", out)
        self.assertEqual(
            sorted(path.name for path in self.spool_dir.iterdir()),
            [f"{CAMERA_ID}{WITNESS_SUFFIX}"],
            "after delivery the spool must hold exactly the REC witness",
        )
        payload = read_witness(self.spool_dir / f"{CAMERA_ID}{WITNESS_SUFFIX}")
        assert_fresh_utc_iso(self, payload)

    def test_init_only_cycle_delivers_the_init_and_writes_no_witness(self) -> None:
        server = self.start_hls_server(
            {
                "/live/playlist.m3u8": INIT_ONLY_PLAYLIST,
                "/live/init.mp4": INIT_BYTES,
            }
        )
        self.set_rsync_mode("ok")
        instance = load_recorder().HlsRecorder(self._hls_config(server))
        out = drive_recorder_cycles(instance, cycles=1)
        self.assertIn("recorder object ok", out, "the init object must be delivered")
        calls = self.rsync_calls()
        self.assertEqual(len(calls), 1, f"only the init object is delivered: {calls}")
        self.assertIn("-init-", calls[0])
        self.assertEqual(
            witness_files(self.tmp),
            [],
            "AC-002: an init/EXT-X-MAP object must not write a witness",
        )

    def test_failed_upload_writes_no_witness(self) -> None:
        server = self.start_hls_server()
        self.set_rsync_mode("fail")
        instance = load_recorder().HlsRecorder(self._hls_config(server))
        out = drive_recorder_cycles(instance, cycles=1)
        self.assertEqual(out.count("reason=upload_failed"), 4)
        self.assertEqual(instance.captured_count, 0)
        self.assertEqual(
            witness_files(self.tmp),
            [],
            "AC-004: a failed upload must not write a witness",
        )

    def test_cycle_without_any_delivery_writes_no_witness(self) -> None:
        # The recorder process exists and keeps cycling, but nothing lands.
        server = self.start_hls_server(
            {"/live/playlist.m3u8": MALFORMED_PLAYLIST}
        )
        self.set_rsync_mode("ok")
        instance = load_recorder().HlsRecorder(self._hls_config(server))
        out = drive_recorder_cycles(instance, cycles=1)
        self.assertNotIn("recorder object ok", out)
        self.assertEqual(self.rsync_calls(), [])
        self.assertEqual(
            witness_files(self.tmp),
            [],
            "a running-but-undelivering recorder must not write a witness",
        )

    def test_disabled_recorder_child_writes_no_witness(self) -> None:
        server = self.start_hls_server()
        env = self.child_env(
            SEA_SPEED_RECORDER_ENABLED="0",
            SEA_SPEED_RECORDER_HLS_URL=server.playlist_url,
            CAMERA_ID=CAMERA_ID,
        )
        proc = subprocess.Popen(
            [sys.executable, str(RECORDER_SCRIPT)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        out, _ = proc.communicate(timeout=15)
        out = out or ""
        self.assertEqual(proc.returncode, 0, out)
        self.assertEqual(
            witness_files(self.tmp),
            [],
            "AC-001: a disabled recorder must not write a witness",
        )


class RtspRecordingWitnessWriteTests(RtspRecorderTestBase):
    """RTSP arm: only a successful nonempty finalized clip writes a witness."""

    def test_successful_finalized_clip_writes_the_witness(self) -> None:
        instance = self._fresh_instance(self.make_config())
        self._plant_part(instance, 1, b"\x1aE\xdf\xa3" + b"clip-bytes" * 64)
        instance._finalize(1)
        self.assertEqual(instance.captured_count, 1)
        self.assertEqual(
            witness_files(self.spool_dir),
            [f"{CAMERA_ID}{WITNESS_SUFFIX}"],
        )
        payload = read_witness(self.spool_dir / f"{CAMERA_ID}{WITNESS_SUFFIX}")
        assert_fresh_utc_iso(self, payload)

    def test_empty_finalized_clip_is_discarded_without_a_witness(self) -> None:
        instance = self._fresh_instance(self.make_config())
        self._plant_part(instance, 1, b"")
        instance._finalize(1)
        self.assertEqual(instance.captured_count, 0)
        self.assertEqual(instance.gap_count, 1)
        self.assertEqual(
            witness_files(self.tmp),
            [],
            "AC-003: an empty finalized clip must not write a witness",
        )

    def test_over_cap_finalized_clip_is_discarded_without_a_witness(self) -> None:
        instance = self._fresh_instance(self.make_config(object_max_bytes=1024))
        self._plant_part(instance, 1, b"S" * 2048)
        instance._finalize(1)
        self.assertEqual(instance.captured_count, 0)
        self.assertEqual(instance.gap_count, 1)
        self.assertEqual(
            witness_files(self.tmp),
            [],
            "AC-003: an over-cap finalized clip must not write a witness",
        )

    def test_failed_clip_upload_writes_no_witness(self) -> None:
        self.set_rsync_mode("fail")
        instance = self._fresh_instance(self.make_config())
        self._plant_part(instance, 1, b"\x1aE\xdf\xa3" + b"clip-bytes" * 64)
        instance._finalize(1)
        self.assertEqual(instance.captured_count, 0)
        self.assertEqual(instance.gap_count, 1)
        self.assertEqual(
            witness_files(self.tmp),
            [],
            "AC-004: a failed clip upload must not write a witness",
        )


# ---------------------------------------------------------------------------
# 3. State enrichment on every post path (spec R-4/R-6)
# ---------------------------------------------------------------------------


class StateEnrichmentTests(unittest.TestCase):
    """``post_state`` always carries ``recording_last_success_at`` on a COPY."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="test699-rec-state-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.spool = self.tmp / "spool"
        self.spool.mkdir()
        self.overlay = self.tmp / "latest_overlay.jpg"
        self.overlay.write_bytes(b"\xff\xd8probe\xff\xd9")

    def _env(self, **overrides: str):
        values = {
            "SEA_SPEED_API_URL": "http://api.test/state",
            "SEA_SPEED_API_TOKEN": "test-token",
            "SEA_SPEED_RECORDER_ENABLED": "1",
            "SEA_SPEED_RECORDER_SPOOL_DIR": str(self.spool),
            "CAMERA_ID": CAMERA_ID,
        }
        values.update(overrides)
        return mock.patch.dict(os.environ, values)

    @staticmethod
    def _response():
        return types.SimpleNamespace(status_code=200, text="")

    @staticmethod
    def _posted(post) -> dict:
        return json.loads(post.call_args.kwargs["data"]["metadata"])

    def _write_witness(self, age_sec: float = 1.0) -> str:
        timestamp = (datetime.now(timezone.utc) - timedelta(seconds=age_sec)).isoformat()
        (self.spool / f"{CAMERA_ID}{WITNESS_SUFFIX}").write_text(
            json.dumps(
                {"camera_id": CAMERA_ID, "last_success_at": timestamp},
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        return timestamp

    def _paths(self):
        """The three production post paths: normal, conformance, recovery."""
        return [
            (
                "normal-overlay",
                {"frame_no": 5, "overlay_rev": 5, "worker_online": True},
                self.overlay,
            ),
            (
                "conformance-metadata-only",
                {
                    "frame_no": 5,
                    "frame_conforming": False,
                    "unknown_reason": "black_frame",
                    "worker_online": True,
                },
                None,
            ),
            (
                "recovery-metadata-only",
                {"frame_no": 6, "frame_conforming": True, "worker_online": True},
                None,
            ),
        ]

    def _post_all_paths(self):
        """Post through all three paths; return (label, metadata, posted)."""
        results = []
        with self._env(), mock.patch.object(
            worker_transport.requests, "post", return_value=self._response()
        ) as post:
            for label, metadata, overlay in self._paths():
                self.assertTrue(
                    worker_transport.post_state(metadata, overlay),
                    f"{label} post must succeed",
                )
                results.append((label, metadata, self._posted(post)))
        return results

    def test_every_post_path_carries_an_explicit_null_without_a_witness(self) -> None:
        for label, metadata, posted in self._post_all_paths():
            with self.subTest(path=label):
                self.assertIn("recording_last_success_at", posted)
                self.assertIsNone(posted["recording_last_success_at"])
                self.assertEqual(
                    set(posted),
                    set(metadata) | {"recording_last_success_at"},
                    "the field is ADDED, no other key changes",
                )

    def test_every_post_path_carries_the_fresh_timestamp(self) -> None:
        timestamp = self._write_witness()
        for label, metadata, posted in self._post_all_paths():
            with self.subTest(path=label):
                self.assertEqual(posted["recording_last_success_at"], timestamp)

    def test_caller_payload_is_never_mutated(self) -> None:
        payload = {"frame_no": 5}
        with self._env(), mock.patch.object(
            worker_transport.requests, "post", return_value=self._response()
        ) as post:
            self.assertTrue(worker_transport.post_state(payload, None))
        self.assertEqual(
            payload,
            {"frame_no": 5},
            "R-4: the reporter must enrich a copy, never the caller's dict",
        )
        self.assertEqual(
            self._posted(post),
            {"frame_no": 5, "recording_last_success_at": None},
        )

    def test_explicit_null_replaces_a_stale_prior_value(self) -> None:
        # A metadata-only API merge must CLEAR a prior witness, not keep it.
        payload = {
            "frame_no": 5,
            "recording_last_success_at": "2020-01-01T00:00:00+00:00",
        }
        with self._env(), mock.patch.object(
            worker_transport.requests, "post", return_value=self._response()
        ) as post:
            self.assertTrue(worker_transport.post_state(payload, None))
        self.assertEqual(
            self._posted(post),
            {"frame_no": 5, "recording_last_success_at": None},
        )

    def test_fresh_timestamp_replaces_a_stale_prior_value(self) -> None:
        timestamp = self._write_witness()
        payload = {
            "frame_no": 5,
            "recording_last_success_at": "2020-01-01T00:00:00+00:00",
        }
        with self._env(), mock.patch.object(
            worker_transport.requests, "post", return_value=self._response()
        ) as post:
            self.assertTrue(worker_transport.post_state(payload, None))
        self.assertEqual(
            self._posted(post),
            {"frame_no": 5, "recording_last_success_at": timestamp},
        )

    def test_witness_read_failure_does_not_suppress_the_post(self) -> None:
        # R-6: a witness read failure must never stop analytics.
        (self.spool / f"{CAMERA_ID}{WITNESS_SUFFIX}").mkdir()
        with self._env(), mock.patch.object(
            worker_transport.requests, "post", return_value=self._response()
        ) as post:
            self.assertTrue(worker_transport.post_state({"frame_no": 5}, None))
        self.assertIsNone(self._posted(post)["recording_last_success_at"])

    def test_transport_top_level_imports_stay_within_the_allowlist(self) -> None:
        source = (WORKER_DIR / "worker_transport.py").read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename="worker_transport.py")
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertEqual(
            sorted(imported - TRANSPORT_IMPORT_ALLOWLIST),
            [],
            "worker_transport gained a top-level import outside the allowlist",
        )
        # The REC reader imports both FUNCTION-LOCALLY; they must not creep up.
        self.assertNotIn("datetime", imported)
        self.assertNotIn("re", imported)


# ---------------------------------------------------------------------------
# 4. Ingest parity — the REC indicator never touches the reader
# ---------------------------------------------------------------------------


class RecIngestParityTests(unittest.TestCase):
    FRAME_W = 16
    FRAME_H = 16
    FRAME_BYTES = bytes(
        (index * 31 + 7) % 256 for index in range(FRAME_W * FRAME_H * 3)
    )

    REC_STATES = (
        ("unset", {}),
        ("off", {"SEA_SPEED_RECORDER_ENABLED": "0"}),
        (
            "on",
            {
                "SEA_SPEED_RECORDER_ENABLED": "1",
                "SEA_SPEED_RECORDER_HLS_URL": "http://127.0.0.1:1/playlist.m3u8",
            },
        ),
        # Enabled without a source URL: the recorder refuses this config.
        ("failing", {"SEA_SPEED_RECORDER_ENABLED": "1"}),
    )

    @contextlib.contextmanager
    def _recorder_state(self, state: dict):
        with mock.patch.dict(os.environ, {}, clear=False):
            for key in [k for k in os.environ if k.startswith("SEA_SPEED_RECORDER_")]:
                del os.environ[key]
            for key, value in state.items():
                os.environ[key] = value
            yield

    def _reader_argv(self, state: dict) -> list:
        """Capture the real ffmpeg argv the entrypoint would spawn."""
        entry = load_entrypoint()
        with self._recorder_state(state):
            with mock.patch.object(entry.subprocess, "Popen") as popen:
                popen.return_value = mock.Mock(stderr=None)
                entry._spawn_rtsp_ffmpeg("rtsp://192.0.2.10/stream", 640, 360, 5.0)
        return list(popen.call_args[0][0])

    def _raw_frame_bytes(self, state: dict) -> bytes:
        """Drive the real reader's bounded read over a deterministic child."""
        entry = load_entrypoint()
        code = (
            "import sys, time\n"
            f"sys.stdout.buffer.write({self.FRAME_BYTES!r})\n"
            "sys.stdout.buffer.flush()\n"
            "time.sleep(300)\n"
        )

        def _fake_spawn(url, width, height, sample_fps):
            return subprocess.Popen(
                [sys.executable, "-c", code],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )

        with self._recorder_state(state):
            with mock.patch.object(
                entry, "_spawn_rtsp_ffmpeg", side_effect=_fake_spawn
            ):
                reader = entry.ResilientFFmpegRtspReader(
                    "rtsp://192.0.2.10/stream", self.FRAME_W, self.FRAME_H, 5.0
                )
                try:
                    return reader._read_exact_bounded()
                finally:
                    reader.close()
                    proc = reader.proc
                    if proc is not None and proc.stdout is not None:
                        proc.stdout.close()

    def test_reader_argv_identical_across_rec_states(self) -> None:
        argvs = {
            name: self._reader_argv(state) for name, state in self.REC_STATES
        }
        baseline = argvs["unset"]
        for name, argv in argvs.items():
            self.assertEqual(
                argv, baseline, f"REC state {name} must not change reader args"
            )
        self.assertEqual(baseline[0], "ffmpeg")
        self.assertIn("-nostdin", baseline)
        self.assertIn("-rtsp_transport", baseline)

    def test_frame_bytes_identical_across_rec_states(self) -> None:
        bytes_by_state = {
            name: self._raw_frame_bytes(state) for name, state in self.REC_STATES
        }
        baseline = bytes_by_state["unset"]
        self.assertEqual(len(baseline), self.FRAME_W * self.FRAME_H * 3)
        self.assertEqual(
            baseline,
            self.FRAME_BYTES,
            "deterministic reader must yield the exact fixture bytes",
        )
        for name, data in bytes_by_state.items():
            self.assertEqual(
                data,
                baseline,
                f"REC state {name} must not change the reader's frame bytes",
            )

    def test_the_failing_state_is_a_real_recorder_config_error(self) -> None:
        # Proves the "failing" parity state really is a failing REC config.
        rec = load_recorder()
        with self._recorder_state({"SEA_SPEED_RECORDER_ENABLED": "1"}):
            with self.assertRaises(rec.RecorderError):
                rec.RecorderConfig.from_env()


# ---------------------------------------------------------------------------
# 5. Scope guard (pinned BASE → HEAD UNION working tree, fail-closed)
# ---------------------------------------------------------------------------


class RecIndicatorScopeGuardTests(unittest.TestCase):
    """The admitted #699 REC-indicator change set; fail-closed on git errors."""

    ALLOWED_CHANGE_PREFIXES = ALLOWED_CHANGE_PREFIXES
    FORBIDDEN_CHANGE_PREFIXES = FORBIDDEN_CHANGE_PREFIXES

    @staticmethod
    def _run_git(arguments: list) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(ROOT), *arguments],
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, OSError) as exc:
            detail = getattr(exc, "stderr", None) or str(exc)
            raise AssertionError(
                "scope guard cannot read the #699 REC change set: "
                f"`git {' '.join(arguments)}` failed ({str(detail).strip()}) "
                "— Failing closed: a guard that cannot read its inputs must "
                "not pass."
            ) from exc
        return result.stdout

    @classmethod
    def _changed_paths(cls) -> list:
        # Half A: the pinned BASE → HEAD range.
        diff = cls._run_git(["diff", "--name-only", BASE_SHA, HEAD_REF])
        paths = {
            line.strip().strip('"')
            for line in diff.splitlines()
            if line.strip()
        }
        # Half B: the working tree (uncommitted production + tests).
        status = cls._run_git(
            ["status", "--porcelain", "--untracked-files=all"]
        )
        for line in status.splitlines():
            if not line.strip():
                continue
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ")[-1]
            paths.add(path.strip().strip('"'))
        return sorted(paths)

    @classmethod
    def _matches(cls, path: str, patterns: tuple) -> bool:
        for pattern in patterns:
            if "*" in pattern:
                if fnmatch.fnmatch(path, pattern):
                    return True
            elif path.startswith(pattern):
                return True
        return False

    @classmethod
    def _offenders(cls, paths: list) -> list:
        return [
            path
            for path in paths
            if not cls._matches(path, cls.ALLOWED_CHANGE_PREFIXES)
        ]

    @staticmethod
    def _is_lockfile(path: str) -> bool:
        name = Path(path).name
        return name in FORBIDDEN_LOCKFILE_NAMES or any(
            name.endswith(suffix) for suffix in FORBIDDEN_LOCKFILE_SUFFIXES
        )

    def test_pinned_base_resolves(self) -> None:
        resolved = self._run_git(["rev-parse", "--verify", f"{BASE_SHA}^{{commit}}"])
        self.assertEqual(resolved.strip(), BASE_SHA)

    def test_change_set_touches_only_the_rec_indicator_surface(self) -> None:
        changed = self._changed_paths()
        offenders = self._offenders(changed)
        self.assertEqual(
            offenders,
            [],
            f"out-of-scope paths in the #699 REC change set "
            f"(pinned BASE → HEAD UNION working tree): {offenders}",
        )

    def test_no_forbidden_api_frontend_workflow_or_lockfile_change(self) -> None:
        for path in self._changed_paths():
            with self.subTest(path=path):
                for prefix in self.FORBIDDEN_CHANGE_PREFIXES:
                    self.assertFalse(
                        path.startswith(prefix),
                        f"forbidden path changed: {path}",
                    )
                self.assertFalse(
                    self._is_lockfile(path),
                    f"lockfile changed: {path}",
                )

    def test_git_read_failure_fails_closed(self) -> None:
        with self.assertRaises(AssertionError):
            self._run_git(
                [
                    "diff",
                    "--name-only",
                    "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
                    HEAD_REF,
                ]
            )

    # -- synthetic predicate proofs (green on base and change alike) -------

    def test_predicate_rejects_out_of_scope_paths(self) -> None:
        rejected = [
            "api/app/main.py",
            "frontend/sea-speed/objects/index.html",
            "frontend/root/index.html",
            "worker/hls_motion_yolo_worker_events.py",
            ".github/workflows/quality-integration.yml",
            "package-lock.json",
            "requirements.lock.txt",
            "worker/hls_motion_yolo_worker_events.py.bak",
        ]
        for path in rejected:
            with self.subTest(path=path):
                allowed = self._matches(path, self.ALLOWED_CHANGE_PREFIXES)
                forbidden = self._matches(path, self.FORBIDDEN_CHANGE_PREFIXES)
                self.assertFalse(
                    allowed and not forbidden and not self._is_lockfile(path),
                    f"guard must reject {path}",
                )

    def test_predicate_accepts_admitted_paths(self) -> None:
        admitted = [
            "tests/test_rec_indicator_state.py",
            "tests/test_699_recorder.py",
            "tests/test_700_ingest_frame_conformance.py",
            "worker/recorder.py",
            "worker/recorder_rtsp.py",
            "worker/worker_transport.py",
            "deploy/worker/ubuntu/worker.env.example",
            "deploy/worker/ubuntu/road-worker.env.example",
            "specs/699-rec-indicator/spec.md",
            "specs/699-rec-indicator/plan.md",
            "specs/699-rec-indicator/tasks.md",
            "scripts/ci/validate_sdd.py",
        ]
        for path in admitted:
            with self.subTest(path=path):
                self.assertTrue(
                    self._matches(path, self.ALLOWED_CHANGE_PREFIXES),
                    f"admitted path wrongly rejected: {path}",
                )
                self.assertFalse(
                    self._matches(path, self.FORBIDDEN_CHANGE_PREFIXES),
                    f"admitted path wrongly forbidden: {path}",
                )


if __name__ == "__main__":
    unittest.main()
