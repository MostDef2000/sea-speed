"""Issue #699: opt-in recorder of ORIGINAL encoded HLS segments to dacha.

The production side (``worker/recorder.py``) landed with the code worker;
these tests pin the OUTCOMES from AC-001..AC-005 with literal expectations
written from the issue/spec text, never derived from the implementation.

Sections (one class each):

* ``RecorderByteIdentityOracleTests`` — AC-002: the primary oracle. A local
  HTTP fixture serves a playlist (``#EXT-X-MAP`` init + three ``#EXTINF``
  segments, ``#EXT-X-MEDIA-SEQUENCE:7``) with known binary bytes; the REAL
  ``worker/recorder.py`` child process runs against it with a fake ``rsync``
  on ``PATH`` that copies each completed object into a temp dir. Delivered
  init + segment bytes must be byte-identical (SHA-256 AND length) to the
  fixture objects, delivered in playlist order (init → seg0 → seg1 → seg2),
  with no duplicate deliveries, no re-encode and an empty spool afterwards.
* ``RecorderDisabledZeroIoTests`` — AC-001: with
  ``SEA_SPEED_RECORDER_ENABLED=0`` the recorder child exits 0 without a
  single HTTP request, rsync call or spool file even when URL/key/destination
  are fully configured; the malformed flag (``"true"``) refuses with rc 2.
  Also the ingest-parity half: the entrypoint reader argv and the raw frame
  bytes a deterministic fake reader child produces are byte-identical across
  recorder-flag states (unset / ``0`` / ``1``) — the recorder never touches
  the ingest path.
* ``RecorderSourceRejectionTests`` — AC-003: RTSP and relative (non
  HTTP(S)) sources are refused with the literal message, the enabled-without
  URL and malformed-flag configs refuse, a cross-origin redirect raises and
  origin B receives ZERO requests (no credential forwarded), a same-origin
  redirect is followed, and a malformed playlist parses without a crash
  (both the pure parser literals and a live recorder child that keeps
  cycling without delivering anything).
* ``RecorderBoundsTests`` — AC-004/AC-005: default 64 MiB object cap and
  12 GiB floor pinned as literals; a declared ``Content-Length`` of
  64 MiB + 1 is rejected before any body transfer (no ``.part``, no dest);
  a streamed body over a small cap is rejected mid-stream with ``.part``
  cleanup; reads are chunked (every transport read ≤ 1 MiB, never whole
  object in one read); a stalled body raises within the per-object deadline
  bounded time with no partial file; a free-space floor above actual free
  raises ``SpoolSpaceLow`` BEFORE any HTTP request; a hung fake rsync is
  killed within the bounded rsync timeout and ``upload`` returns False;
  failing rsync burns exactly the configured retry budget, counts gaps and
  resumes capturing later objects (AC-005 discard-and-gap + resume).
* ``RecorderCredentialTests`` — AC-006/R-8: key resolution only from
  ``$CREDENTIALS_DIRECTORY/recorder_ed25519`` or
  ``/run/credentials/recorder_ed25519`` (literal default), never any
  ``/home`` path (behavioural across env variants + source pin); a missing
  key disables recording with rc 2, no traceback, no HTTP, no spool.

Environment: stdlib-only top-level imports (battery import-hygiene scan);
numpy/requests are probed guarded-optional because CI's battery is
stdlib+pyyaml (tests/test_696 idiom). No private media, no real credentials
(all keys are fake temp files), no network beyond loopback.

RED spot-check (what fails on base ``a66b5a8``, before the production
change; measured against a ``git archive`` of base):

* ``worker/recorder.py`` does not exist at base, so the byte-identity
  (missing-script assert), zero-I/O (rc 2 from ``can't open file``),
  malformed-flag, malformed-playlist-child and missing-key children fail,
  and every in-process helper test errors with
  ``ModuleNotFoundError: No module named 'recorder'``.
* The two ingest-parity tests (reader argv / frame bytes) are deliberate
  GREEN-on-base regression pins (the #696 convention): the reader substrate
  exists at base and the recorder flag cannot change it before or after —
  they prove the recorder never touches ingest, they are not a change
  oracle.
* The packaging and scope-guard tests live in
  ``tests/test_699_recorder_lifecycle.py`` (inventory lacks
  ``worker/recorder.py`` at base; entrypoint lifecycle hooks absent).
"""

from __future__ import annotations

import contextlib
import hashlib
import http.server
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = ROOT / "worker"
RECORDER_SCRIPT = WORKER_DIR / "recorder.py"
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

# ---------------------------------------------------------------------------
# Literals: the oracle. Written from the issue/spec text FIRST — never
# derived from the module under test.
# ---------------------------------------------------------------------------

# Original ENCODED bytes: arbitrary binary (invalid UTF-8, TS sync bytes,
# mp4 ftyp box) so any re-encode/remux/decode would change them.
INIT_BYTES = b"\x00\x00\x00\x1cftypiso5\x00\x00\x00\x00iso5avc1" + bytes(
    range(64)
)
SEG0_BYTES = b"\x47" + bytes(range(256)) * 4 + b"\xff\xd9"
SEG1_BYTES = b"\x47\x40" + b"original-encoded-bytes-seg1\xff\xfe\x00" * 20
SEG2_BYTES = b"\x00\x00\x01\xb0seg2-payload\xc0\xde\xad\xbe\xef" * 3

PLAYLIST_1 = (
    b"#EXTM3U\n"
    b"#EXT-X-VERSION:7\n"
    b"#EXT-X-MEDIA-SEQUENCE:7\n"
    b'#EXT-X-MAP:URI="init.mp4"\n'
    b"#EXTINF:2.000,\n"
    b"seg0.ts\n"
    b"#EXTINF:2.000,\n"
    b"seg1.ts\n"
    b"#EXTINF:2.000,\n"
    b"seg2.ts\n"
    b"#EXT-X-ENDLIST\n"
)

# Cycle-2 playlist with the media sequence where the cursor stopped (7..9
# captured -> next is 10): a NEW object arrives with no gap.
PLAYLIST_RESUME = (
    b"#EXTM3U\n"
    b"#EXT-X-VERSION:7\n"
    b"#EXT-X-MEDIA-SEQUENCE:10\n"
    b'#EXT-X-MAP:URI="init.mp4"\n'
    b"#EXTINF:2.000,\n"
    b"seg3.ts\n"
    b"#EXT-X-ENDLIST\n"
)

# Cycle-2 playlist: the media sequence ADVANCES past the three uncaptured
# positions (7..9 captured; next is 10) — 12 means a literal gap of 2.
PLAYLIST_2 = (
    b"#EXTM3U\n"
    b"#EXT-X-VERSION:7\n"
    b"#EXT-X-MEDIA-SEQUENCE:12\n"
    b'#EXT-X-MAP:URI="init.mp4"\n'
    b"#EXTINF:2.000,\n"
    b"seg3.ts\n"
    b"#EXT-X-ENDLIST\n"
)
SEG3_BYTES = b"\x47seg3-later-object\xff\x00\x11" * 7

MALFORMED_PLAYLIST = b"\x80\xff not a playlist at all\n#EXTINF\n"

FIXTURE_TABLE = {
    "/live/playlist.m3u8": PLAYLIST_1,
    "/live/init.mp4": INIT_BYTES,
    "/live/seg0.ts": SEG0_BYTES,
    "/live/seg1.ts": SEG1_BYTES,
    "/live/seg2.ts": SEG2_BYTES,
    "/live/seg3.ts": SEG3_BYTES,
}

# Fixture-object identity key -> expected bytes (sha + length oracle).
FIXTURE_OBJECTS = {
    "init": INIT_BYTES,
    "seg0": SEG0_BYTES,
    "seg1": SEG1_BYTES,
    "seg2": SEG2_BYTES,
    "seg3": SEG3_BYTES,
}

# Literal delivery order demanded by AC-002: init first, then playlist order.
EXPECTED_DELIVERY_ORDER = ["init", "seg0", "seg1", "seg2"]

DEFAULT_OBJECT_MAX_BYTES = 67108864  # 64 MiB (spec R-5)
DEFAULT_MIN_FREE_BYTES = 12884901888  # 12 GiB (spec R-5)
CLAMPED_MIN_FREE_BYTES = 1099511627776  # env upper bound: 1 TiB
CLAMPED_OBJECT_MAX_BYTES = 536870912  # env upper bound: 512 MiB
CHUNK_BYTES_LIMIT = 1024 * 1024  # spec R-5: reads are chunked

OBJECT_OVER_CAP_MESSAGE = "object exceeds the bounded object size"
RTSP_REJECTION_MESSAGE = "recorder source must be an explicit HTTP(S) URL"
DISABLED_OUTPUT = "recorder disabled (SEA_SPEED_RECORDER_ENABLED=0)"

WAIT_OBJECTS_SEC = 20.0


def load_recorder():
    """Import ``worker/recorder.py`` by its runtime name (worker/ on path).

    Lazy so a missing module (base archive RED) fails the individual test
    that needs it instead of erroring the whole file at collection.
    """
    if str(WORKER_DIR) not in sys.path:
        sys.path.insert(0, str(WORKER_DIR))
    import recorder

    return recorder


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class _CycleDone(Exception):
    """Raised from the patched poll-sleep to end ``HlsRecorder.run()``."""


def drive_recorder_cycles(rec, cycles: int, between=None) -> str:
    """Run exactly ``cycles`` recorder poll cycles, then stop.

    ``run()`` sleeps once per completed cycle (outside its try/except), so
    patching the recorder module's ``time.sleep`` to raise a non-caught
    sentinel after N calls yields deterministic single-/multi-cycle drives.
    ``between(completed)`` fires after each completed cycle except the last
    (used to mutate the fixture playlist mid-run — the media-sequence cursor
    lives inside one ``run()`` call).
    """
    remaining = {"n": cycles}
    out = io.StringIO()
    module = load_recorder()

    def _sleep(_seconds: float) -> None:
        remaining["n"] -= 1
        if between is not None and remaining["n"] > 0:
            between(cycles - remaining["n"])
        if remaining["n"] <= 0:
            raise _CycleDone()

    with mock.patch.object(module.time, "sleep", side_effect=_sleep):
        with contextlib.redirect_stdout(out):
            try:
                rec.run()
            except _CycleDone:
                pass
            else:  # pragma: no cover - run() must not return on its own
                raise AssertionError("recorder run() returned before the cycle stop")
    return out.getvalue()


# ---------------------------------------------------------------------------
# Fixture HTTP server + fake rsync helpers
# ---------------------------------------------------------------------------


class _HlsServer:
    """Loopback HTTP server over a mutable path->bytes table."""

    def __init__(self, table: dict) -> None:
        self.table = dict(table)
        self.hits: list[str] = []
        outer = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                outer.hits.append(self.path)
                body = outer.table.get(self.path)
                if body is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    @property
    def playlist_url(self) -> str:
        return f"{self.base}/live/playlist.m3u8"

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()


def fake_rsync_script() -> str:
    """Fake ``rsync``: mode file controls ok / fail / hang; logs every call."""
    return (
        "#!/usr/bin/env python3\n"
        "import os, shutil, sys, time\n"
        "src = sys.argv[-2]\n"
        "mode_path = os.environ['FAKE_RSYNC_MODE']\n"
        "mode = open(mode_path).read().strip() if os.path.exists(mode_path) else 'ok'\n"
        "with open(os.environ['FAKE_RSYNC_LOG'], 'a') as f:\n"
        "    f.write(os.path.basename(src) + '\\n')\n"
        "if mode == 'hang':\n"
        "    open(os.environ['FAKE_RSYNC_PID'], 'w').write(str(os.getpid()))\n"
        "    time.sleep(300)\n"
        "    sys.exit(0)\n"
        "if mode == 'fail':\n"
        "    sys.stderr.write('fake rsync: receiver refused\\n')\n"
        "    sys.exit(1)\n"
        "shutil.copyfile(src, os.path.join(os.environ['FAKE_RSYNC_DEST'], os.path.basename(src)))\n"
        "sys.exit(0)\n"
    )


class RecorderTestBase(unittest.TestCase):
    """Shared temp dir, fake-rsync PATH injection and env hygiene."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="test699-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.bin_dir = self.tmp / "bin"
        self.dest_dir = self.tmp / "dest"
        self.spool_dir = self.tmp / "spool"
        self.creds_dir = self.tmp / "creds"
        self.rsync_log = self.tmp / "rsync.log"
        self.rsync_mode = self.tmp / "rsync.mode"
        self.rsync_pid = self.tmp / "rsync.pid"
        for directory in (self.bin_dir, self.dest_dir, self.creds_dir):
            directory.mkdir(parents=True)
        fake = self.bin_dir / "rsync"
        fake.write_text(fake_rsync_script(), encoding="utf-8")
        fake.chmod(0o755)
        # In-process recorder drives run rsync in THIS process, so the fake
        # rsync needs its control env here too (children get it via
        # child_env). patch.dict restores the ambient environment on exit.
        self._rsync_env = mock.patch.dict(
            os.environ,
            {
                "PATH": f"{self.bin_dir}:{os.environ.get('PATH', '')}",
                "FAKE_RSYNC_DEST": str(self.dest_dir),
                "FAKE_RSYNC_LOG": str(self.rsync_log),
                "FAKE_RSYNC_MODE": str(self.rsync_mode),
                "FAKE_RSYNC_PID": str(self.rsync_pid),
            },
        )
        self._rsync_env.start()
        self.addCleanup(self._rsync_env.stop)
        self.servers: list[_HlsServer] = []

    def tearDown(self) -> None:
        for server in self.servers:
            server.stop()

    def start_hls_server(self, table: dict | None = None) -> _HlsServer:
        server = _HlsServer(FIXTURE_TABLE if table is None else table)
        self.servers.append(server)
        return server

    def set_rsync_mode(self, mode: str) -> None:
        self.rsync_mode.write_text(mode, encoding="utf-8")

    def rsync_calls(self) -> list[str]:
        if not self.rsync_log.exists():
            return []
        return [line for line in self.rsync_log.read_text().splitlines() if line]

    def child_env(self, **overrides: str) -> dict:
        """Recorder child env: no ambient recorder/credential/auth leakage."""
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SEA_SPEED_RECORDER_")
            and key
            not in (
                "CREDENTIALS_DIRECTORY",
                "HLS_MEDIA_BASIC_AUTH_BASE64",
                "HLS_BASIC_AUTH_BASE64",
            )
        }
        env.update(
            {
                "PATH": f"{self.bin_dir}:{env.get('PATH', '')}",
                "SEA_SPEED_RECORDER_SPOOL_DIR": str(self.spool_dir),
                "SEA_SPEED_RECORDER_DESTINATION": str(self.dest_dir),
                "SEA_SPEED_RECORDER_POLL_SEC": "0.5",
                "SEA_SPEED_RECORDER_MIN_FREE_BYTES": "0",
                "SEA_SPEED_RECORDER_RSYNC_BACKOFF_SEC": "0",
                "SEA_SPEED_RECORDER_RSYNC_RETRIES": "2",
                "FAKE_RSYNC_DEST": str(self.dest_dir),
                "FAKE_RSYNC_LOG": str(self.rsync_log),
                "FAKE_RSYNC_MODE": str(self.rsync_mode),
                "FAKE_RSYNC_PID": str(self.rsync_pid),
                "CREDENTIALS_DIRECTORY": str(self.creds_dir),
            }
        )
        (self.creds_dir / "recorder_ed25519").write_text(
            "fake-test-key-not-a-secret\n", encoding="utf-8"
        )
        env.update(overrides)
        return env

    def spawn_recorder(self, env: dict) -> subprocess.Popen:
        self.assertTrue(
            RECORDER_SCRIPT.is_file(),
            f"recorder script missing: {RECORDER_SCRIPT} (issue #699 production file)",
        )
        return subprocess.Popen(
            [sys.executable, str(RECORDER_SCRIPT)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def stop_recorder(self, proc: subprocess.Popen) -> str:
        """SIGTERM the recorder child and return its combined output.

        Idempotent: cleanup and the test body may both stop the same child.
        """
        cached = getattr(proc, "_test699_output", None)
        if cached is not None:
            return cached
        if proc.poll() is None:
            proc.terminate()
        out, _ = proc.communicate(timeout=15)
        output = out or ""
        proc._test699_output = output
        return output

    def wait_for_deliveries(self, count: int) -> bool:
        deadline = time.monotonic() + WAIT_OBJECTS_SEC
        while time.monotonic() < deadline:
            if len(list(self.dest_dir.iterdir())) >= count:
                return True
            time.sleep(0.1)
        return False


# ---------------------------------------------------------------------------
# 1. Byte-identity oracle (AC-002)
# ---------------------------------------------------------------------------


class RecorderByteIdentityOracleTests(RecorderTestBase):
    """Every delivered object is byte-identical to the fixture source."""

    def test_delivered_init_and_segments_are_byte_identical_in_playlist_order(
        self,
    ) -> None:
        server = self.start_hls_server()
        env = self.child_env(
            SEA_SPEED_RECORDER_ENABLED="1",
            SEA_SPEED_RECORDER_HLS_URL=server.playlist_url,
        )
        proc = self.spawn_recorder(env)
        self.addCleanup(self.stop_recorder, proc)
        delivered = self.wait_for_deliveries(len(EXPECTED_DELIVERY_ORDER))
        if not delivered:
            # Stop the child FIRST (stdout EOF), then read its output — an
            # eager stdout.read() here would block while the child runs.
            early_out = self.stop_recorder(proc)
            self.fail(
                "recorder delivered no objects within the bounded wait; "
                f"output:\n{early_out}"
            )
        # One full poll after the last delivery: a duplicate would appear.
        time.sleep(1.0)
        out = self.stop_recorder(proc)

        delivered = sorted(path.name for path in self.dest_dir.iterdir())
        self.assertEqual(
            len(delivered),
            len(EXPECTED_DELIVERY_ORDER),
            f"expected exactly one delivery per fixture object, got {delivered}",
        )

        # SHA-256 AND length identity for every delivered object.
        identified: dict[str, bytes] = {}
        for name in delivered:
            data = (self.dest_dir / name).read_bytes()
            matches = [
                key
                for key, expected in FIXTURE_OBJECTS.items()
                if sha256_hex(expected) == sha256_hex(data)
                and len(expected) == len(data)
            ]
            self.assertEqual(
                len(matches),
                1,
                f"delivered {name} ({len(data)} bytes) matches fixture objects "
                f"{matches} — bytes were transformed (re-encode/remux forbidden)",
            )
            identified[name] = data
        # Every expected object accounted for, none extra.
        expected_delivered = {
            key: FIXTURE_OBJECTS[key] for key in EXPECTED_DELIVERY_ORDER
        }
        self.assertEqual(
            sorted(identified),
            sorted(delivered),
        )
        self.assertEqual(
            {sha256_hex(v) for v in identified.values()},
            {sha256_hex(v) for v in expected_delivered.values()},
        )

        # Delivery ORDER: rsync log order maps to init -> seg0 -> seg1 -> seg2.
        calls = self.rsync_calls()
        self.assertEqual(
            len(calls),
            len(EXPECTED_DELIVERY_ORDER),
            f"expected one rsync call per object, got {calls}",
        )
        order = []
        for name in calls:
            data = (self.dest_dir / name).read_bytes()
            order.append(
                next(
                    key
                    for key, expected in FIXTURE_OBJECTS.items()
                    if sha256_hex(expected) == sha256_hex(data)
                )
            )
        self.assertEqual(
            order,
            EXPECTED_DELIVERY_ORDER,
            "objects must be delivered in playlist order (init first)",
        )

        # Original bytes logged with their exact sizes; spool cleaned after.
        self.assertEqual(out.count("recorder object ok"), 4)
        self.assertIn(f"bytes={len(INIT_BYTES)}", out)
        self.assertIn(f"bytes={len(SEG0_BYTES)}", out)
        self.assertIn(f"bytes={len(SEG1_BYTES)}", out)
        self.assertIn(f"bytes={len(SEG2_BYTES)}", out)
        self.assertTrue(self.spool_dir.exists())
        self.assertEqual(
            list(self.spool_dir.iterdir()),
            [],
            "spool must be empty after upload attempts (objects deleted)",
        )
        self.assertNotIn("Traceback", out)


# ---------------------------------------------------------------------------
# 2. OFF = zero I/O + ingest parity (AC-001)
# ---------------------------------------------------------------------------


class RecorderDisabledZeroIoTests(RecorderTestBase):
    """Disabled means zero recorder I/O and byte-identical ingest."""

    def test_disabled_child_makes_no_http_rsync_or_spool_io(self) -> None:
        server = self.start_hls_server()
        env = self.child_env(
            SEA_SPEED_RECORDER_ENABLED="0",
            SEA_SPEED_RECORDER_HLS_URL=server.playlist_url,
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
        self.assertIn(DISABLED_OUTPUT, out)
        self.assertEqual(
            server.hits,
            [],
            f"disabled recorder must not fetch anything, got {server.hits}",
        )
        self.assertEqual(self.rsync_calls(), [], "disabled recorder must not rsync")
        self.assertFalse(
            self.spool_dir.exists(),
            "disabled recorder must not create the spool directory",
        )

    def test_malformed_flag_refuses_with_rc2_without_io(self) -> None:
        server = self.start_hls_server()
        env = self.child_env(
            SEA_SPEED_RECORDER_ENABLED="true",
            SEA_SPEED_RECORDER_HLS_URL=server.playlist_url,
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

        self.assertEqual(proc.returncode, 2, out)
        self.assertIn("recorder disabled config_error=", out)
        self.assertIn("SEA_SPEED_RECORDER_ENABLED must be 0 or 1", out)
        self.assertNotIn("Traceback", out)
        self.assertEqual(server.hits, [])
        self.assertEqual(self.rsync_calls(), [])

    # -- ingest parity: reader args + frame bytes on deterministic input ---

    @staticmethod
    def load_entrypoint():
        """Load the Ubuntu entrypoint the provenance way (tests/test_696).

        Only the heavy runtime worker module is stubbed; numpy/requests are
        stubbed only when genuinely absent (battery guard idiom).
        """
        for name in ("numpy", "requests"):
            if name in sys.modules:
                continue
            try:
                available = importlib.util.find_spec(name) is not None
            except (ImportError, ValueError):
                available = False
            if not available:
                sys.modules[name] = mock.MagicMock(name=name)
        runtime_worker = types.ModuleType("hls_motion_yolo_worker_events")
        runtime_worker.start_media_reader = lambda av_module=None: None
        runtime_worker.post_state = lambda metadata, overlay_path: True
        runtime_worker.post_event = lambda metadata, snapshot_path: True
        runtime_worker.env_str = lambda name, default="": os.environ.get(
            name, default
        )
        runtime_worker.env_int = lambda name, default=0: int(
            os.environ.get(name, default)
        )
        runtime_worker.env_float = lambda name, default=0.0: float(
            os.environ.get(name, default)
        )
        runtime_worker.safe_media_input_label = lambda url: "<configured>"
        spec = importlib.util.spec_from_file_location(
            "ubuntu_worker_entrypoint_699_oracle",
            ROOT / "worker" / "ubuntu_worker_entrypoint.py",
        )
        module = importlib.util.module_from_spec(spec)
        # Single-key management, NOT mock.patch.dict(sys.modules): patch.dict
        # restores the WHOLE dict on exit, evicting numpy imported during
        # exec — a later re-import dies with "cannot load module more than
        # once per process" (the tests/test_696 docstring warning).
        previous = sys.modules.get("hls_motion_yolo_worker_events")
        sys.modules["hls_motion_yolo_worker_events"] = runtime_worker
        try:
            spec.loader.exec_module(module)
        finally:
            if previous is None:
                sys.modules.pop("hls_motion_yolo_worker_events", None)
            else:
                sys.modules["hls_motion_yolo_worker_events"] = previous
        return module

    @staticmethod
    def _flag_env(flag_state: dict) -> dict:
        """Env update for a recorder-flag state; ``None`` means 'absent'."""
        return {
            key: value
            for key, value in flag_state.items()
            if value is not None
        }

    @staticmethod
    def _clear_recorder_keys() -> None:
        for key in [k for k in os.environ if k.startswith("SEA_SPEED_RECORDER_")]:
            del os.environ[key]

    def _reader_argv(self, flag_state: dict) -> list:
        """Capture the real ffmpeg argv the entrypoint would spawn."""
        entry = self.load_entrypoint()
        with mock.patch.dict(os.environ, self._flag_env(flag_state), clear=False):
            self._clear_recorder_keys()
            if flag_state.get("SEA_SPEED_RECORDER_ENABLED") is not None:
                os.environ["SEA_SPEED_RECORDER_ENABLED"] = str(
                    flag_state["SEA_SPEED_RECORDER_ENABLED"]
                )
            with mock.patch.object(entry.subprocess, "Popen") as popen:
                popen.return_value = mock.Mock(stderr=None)
                entry._spawn_rtsp_ffmpeg("rtsp://192.0.2.10/stream", 640, 360, 5.0)
        return list(popen.call_args[0][0])

    def test_reader_argv_identical_across_recorder_flag_states(self) -> None:
        unset = self._reader_argv({"SEA_SPEED_RECORDER_ENABLED": None})
        off = self._reader_argv({"SEA_SPEED_RECORDER_ENABLED": "0"})
        on = self._reader_argv({"SEA_SPEED_RECORDER_ENABLED": "1"})

        self.assertEqual(unset, off, "recorder OFF must not change reader args")
        self.assertEqual(unset, on, "recorder ON must not change reader args")
        # Sanity: the captured argv really is the bounded ffmpeg reader.
        self.assertEqual(unset[0], "ffmpeg")
        self.assertIn("-nostdin", unset)
        self.assertIn("-rtsp_transport", unset)

    FRAME_W = 16
    FRAME_H = 16
    FRAME_BYTES = bytes(
        (index * 31 + 7) % 256 for index in range(FRAME_W * FRAME_H * 3)
    )

    def _raw_frame_bytes(self, flag_state: dict) -> bytes:
        """Drive the real reader's bounded read over a deterministic child."""
        entry = self.load_entrypoint()
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

        with mock.patch.dict(os.environ, self._flag_env(flag_state), clear=False):
            self._clear_recorder_keys()
            if flag_state.get("SEA_SPEED_RECORDER_ENABLED") is not None:
                os.environ["SEA_SPEED_RECORDER_ENABLED"] = str(
                    flag_state["SEA_SPEED_RECORDER_ENABLED"]
                )
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

    def test_frame_bytes_identical_across_recorder_flag_states(self) -> None:
        unset = self._raw_frame_bytes({"SEA_SPEED_RECORDER_ENABLED": None})
        off = self._raw_frame_bytes({"SEA_SPEED_RECORDER_ENABLED": "0"})
        on = self._raw_frame_bytes({"SEA_SPEED_RECORDER_ENABLED": "1"})

        self.assertEqual(len(unset), self.FRAME_W * self.FRAME_H * 3)
        self.assertEqual(
            unset,
            self.FRAME_BYTES,
            "deterministic reader must yield the exact fixture bytes",
        )
        self.assertEqual(unset, off, "recorder OFF must not change frame bytes")
        self.assertEqual(unset, on, "recorder ON must not change frame bytes")


# ---------------------------------------------------------------------------
# 3. Rejections (AC-003)
# ---------------------------------------------------------------------------


class RecorderSourceRejectionTests(RecorderTestBase):
    """Non-HTTP(S) sources, bad configs and cross-origin redirects refuse."""

    def _config_error(self, **env: str):
        rec = load_recorder()
        clean = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SEA_SPEED_RECORDER_")
        }
        clean.update({"SEA_SPEED_RECORDER_ENABLED": "1"})
        clean.update(env)
        with mock.patch.dict(os.environ, clean, clear=True):
            with self.assertRaises(rec.RecorderError) as caught:
                rec.RecorderConfig.from_env()
        return str(caught.exception)

    def test_rtsp_source_is_rejected(self) -> None:
        message = self._config_error(
            SEA_SPEED_RECORDER_HLS_URL="rtsp://camera.example/stream"
        )
        self.assertIn(RTSP_REJECTION_MESSAGE, message)
        self.assertIn("RTSP is not supported", message)

    def test_relative_url_without_explicit_scheme_is_rejected(self) -> None:
        for url in ("/live/playlist.m3u8", "playlist.m3u8"):
            with self.subTest(url=url):
                message = self._config_error(SEA_SPEED_RECORDER_HLS_URL=url)
                self.assertIn(RTSP_REJECTION_MESSAGE, message)

    def test_enabled_without_url_is_rejected(self) -> None:
        message = self._config_error(SEA_SPEED_RECORDER_HLS_URL="")
        self.assertIn(
            "SEA_SPEED_RECORDER_HLS_URL is required when the recorder is enabled",
            message,
        )

    def test_rtsp_main_returns_rc2_without_raising(self) -> None:
        rec = load_recorder()
        clean = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SEA_SPEED_RECORDER_")
        }
        clean["SEA_SPEED_RECORDER_ENABLED"] = "1"
        clean["SEA_SPEED_RECORDER_HLS_URL"] = "rtsp://camera.example/stream"
        out = io.StringIO()
        with mock.patch.dict(os.environ, clean, clear=True):
            with contextlib.redirect_stdout(out):
                rc = rec.main()
        self.assertEqual(rc, 2)
        self.assertIn("recorder disabled config_error=", out.getvalue())

    def test_cross_origin_redirect_refused_and_origin_b_never_hit(self) -> None:
        rec = load_recorder()

        class OriginB(http.server.BaseHTTPRequestHandler):
            hits: list = []

            def log_message(self, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                OriginB.hits.append(self.headers.get("Authorization"))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"#EXTM3U\n")

        server_b = http.server.ThreadingHTTPServer(("127.0.0.1", 0), OriginB)
        threading.Thread(target=server_b.serve_forever, daemon=True).start()
        self.addCleanup(server_b.server_close)
        self.addCleanup(server_b.shutdown)
        port_b = server_b.server_address[1]

        class OriginA(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                self.send_response(302)
                self.send_header(
                    "Location", f"http://127.0.0.1:{port_b}/steal"
                )
                self.end_headers()

        server_a = http.server.ThreadingHTTPServer(("127.0.0.1", 0), OriginA)
        threading.Thread(target=server_a.serve_forever, daemon=True).start()
        self.addCleanup(server_a.server_close)
        self.addCleanup(server_a.shutdown)
        url_a = f"http://127.0.0.1:{server_a.server_address[1]}/playlist.m3u8"

        opener = rec.build_opener()
        with self.assertRaises(HTTPError) as caught:
            rec.fetch_playlist(
                opener, url_a, {"Authorization": "Basic dGVzdDp0ZXN0"}, 5.0
            )
        self.assertEqual(caught.exception.code, 302)
        self.assertEqual(caught.exception.msg, "cross-origin redirect refused")
        self.assertEqual(
            OriginB.hits,
            [],
            "origin B must never be contacted — no credential forwarded",
        )

    def test_same_origin_redirect_is_followed(self) -> None:
        rec = load_recorder()

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                if self.path == "/redir":
                    self.send_response(302)
                    self.send_header("Location", "/real")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", "8")
                self.end_headers()
                self.wfile.write(b"#EXTM3U\n")

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        url = f"http://127.0.0.1:{httpd.server_address[1]}/redir"

        text, final_url = rec.fetch_playlist(rec.build_opener(), url, {}, 5.0)
        self.assertTrue(final_url.endswith("/real"), final_url)
        self.assertTrue(text.startswith("#EXTM3U"), text)

    def test_malformed_playlist_parses_without_crash(self) -> None:
        rec = load_recorder()
        # Literals from spec R-3/AC-003: garbage yields no objects, no raise.
        self.assertEqual(
            rec.parse_playlist(MALFORMED_PLAYLIST.decode("utf-8", "replace")),
            (None, [], 0, False),
        )
        # A malformed sequence tag parses to 0 and still does not crash.
        self.assertEqual(
            rec.parse_playlist("#EXT-X-MEDIA-SEQUENCE:abc\n#EXTINF\n"),
            (None, [], 0, True),
        )
        self.assertEqual(rec.parse_playlist(""), (None, [], 0, False))

    def test_live_recorder_cycles_on_malformed_playlist_without_crash(
        self,
    ) -> None:
        server = self.start_hls_server(
            {"/live/playlist.m3u8": MALFORMED_PLAYLIST}
        )
        env = self.child_env(
            SEA_SPEED_RECORDER_ENABLED="1",
            SEA_SPEED_RECORDER_HLS_URL=server.playlist_url,
        )
        proc = self.spawn_recorder(env)
        self.addCleanup(self.stop_recorder, proc)
        time.sleep(2.0)  # several poll cycles at 0.5 s
        self.assertIsNone(
            proc.poll(),
            "recorder must keep cycling on a malformed playlist, not crash",
        )
        out = self.stop_recorder(proc)
        self.assertNotIn("Traceback", out)
        self.assertGreaterEqual(len(server.hits), 1, "playlist was fetched")
        self.assertEqual(
            self.rsync_calls(),
            [],
            "malformed playlist yields no objects to deliver",
        )
        self.assertEqual(list(self.dest_dir.iterdir()), [])


# ---------------------------------------------------------------------------
# 4. Bounds (AC-004 / AC-005)
# ---------------------------------------------------------------------------


class RecorderBoundsTests(RecorderTestBase):
    """64 MiB cap, 12 GiB floor, deadline, chunked reads, hung receiver."""

    def test_default_bounds_are_pinned_literals(self) -> None:
        rec = load_recorder()
        config = rec.RecorderConfig()
        self.assertEqual(config.object_max_bytes, DEFAULT_OBJECT_MAX_BYTES)
        self.assertEqual(config.min_free_bytes, DEFAULT_MIN_FREE_BYTES)
        self.assertFalse(config.enabled, "recorder must default OFF")

    def test_env_bound_clamps_are_pinned_literals(self) -> None:
        rec = load_recorder()
        clean = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SEA_SPEED_RECORDER_")
        }
        clean.update(
            {
                "SEA_SPEED_RECORDER_ENABLED": "1",
                "SEA_SPEED_RECORDER_HLS_URL": "http://127.0.0.1:1/x.m3u8",
                "SEA_SPEED_RECORDER_MIN_FREE_BYTES": str(10**18),
                "SEA_SPEED_RECORDER_OBJECT_MAX_BYTES": str(10**18),
            }
        )
        with mock.patch.dict(os.environ, clean, clear=True):
            config = rec.RecorderConfig.from_env()
        self.assertEqual(config.min_free_bytes, CLAMPED_MIN_FREE_BYTES)
        self.assertEqual(config.object_max_bytes, CLAMPED_OBJECT_MAX_BYTES)

    def test_declared_content_length_over_64mib_rejected_before_body(
        self,
    ) -> None:
        rec = load_recorder()

        class OverCap(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                self.send_response(200)
                self.send_header(
                    "Content-Length", str(DEFAULT_OBJECT_MAX_BYTES + 1)
                )
                self.end_headers()
                # No body: the cap must reject on the DECLARED length alone.

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), OverCap)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        url = f"http://127.0.0.1:{httpd.server_address[1]}/huge.ts"

        destination = self.tmp / "huge.ts"
        with self.assertRaises(rec.RecorderError) as caught:
            rec.download_object(
                rec.build_opener(),
                url,
                {},
                destination,
                DEFAULT_OBJECT_MAX_BYTES,
                5.0,
            )
        self.assertEqual(str(caught.exception), OBJECT_OVER_CAP_MESSAGE)
        self.assertFalse(destination.exists(), "over-cap object must not land")
        self.assertEqual(
            list(self.tmp.glob("*.part")),
            [],
            "over-cap object must leave no .part file",
        )

    def test_streamed_body_over_cap_rejected_with_part_cleanup(self) -> None:
        rec = load_recorder()
        payload = b"S" * 4096

        class Streamed(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                self.send_response(200)
                # No Content-Length: body delimited by connection close, so
                # the cap must fire mid-stream from accumulated total.
                self.end_headers()
                self.wfile.write(payload)

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Streamed)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        url = f"http://127.0.0.1:{httpd.server_address[1]}/stream.ts"

        destination = self.tmp / "stream.ts"
        with self.assertRaises(rec.RecorderError) as caught:
            rec.download_object(
                rec.build_opener(), url, {}, destination, 1024, 5.0
            )
        self.assertEqual(str(caught.exception), OBJECT_OVER_CAP_MESSAGE)
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.tmp.glob("*.part")), [])

    def test_reads_are_chunked_never_whole_object(self) -> None:
        rec = load_recorder()
        payload = b"C" * (CHUNK_BYTES_LIMIT + 123456)

        class RecordingResponse:
            def __init__(self, data: bytes) -> None:
                self._data = data
                self._offset = 0
                self.reads: list[int] = []
                self.headers: dict = {}

            def read(self, size: int) -> bytes:
                self.reads.append(size)
                chunk = self._data[self._offset : self._offset + size]
                self._offset += len(chunk)
                return chunk

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        response = RecordingResponse(payload)

        class FakeOpener:
            def open(self, request, timeout=None):
                return response

        destination = self.tmp / "chunked.ts"
        total = rec.download_object(
            FakeOpener(),
            "http://example.invalid/chunked.ts",
            {},
            destination,
            len(payload),
            5.0,
        )
        self.assertEqual(total, len(payload))
        self.assertEqual(destination.read_bytes(), payload)
        self.assertGreaterEqual(
            len(response.reads),
            2,
            "a >1 MiB object must take multiple bounded reads",
        )
        self.assertTrue(
            all(size <= CHUNK_BYTES_LIMIT for size in response.reads),
            f"every read must be <= 1 MiB, got {response.reads}",
        )

    def test_stalled_body_raises_within_deadline_and_leaves_no_partial(
        self,
    ) -> None:
        rec = load_recorder()

        class Stall(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args: object) -> None:
                pass

            def do_GET(self) -> None:
                self.send_response(200)
                self.send_header("Content-Length", "100")
                self.end_headers()
                self.wfile.write(b"x" * 10)
                time.sleep(5)

        httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Stall)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        url = f"http://127.0.0.1:{httpd.server_address[1]}/stall.ts"

        destination = self.tmp / "stall.ts"
        started = time.monotonic()
        with self.assertRaises((TimeoutError, OSError)):
            rec.download_object(
                rec.build_opener(), url, {}, destination, DEFAULT_OBJECT_MAX_BYTES, 1.0
            )
        elapsed = time.monotonic() - started
        self.assertLess(
            elapsed, 5.0, "per-object deadline must bound the stalled read"
        )
        self.assertFalse(destination.exists())
        self.assertEqual(list(self.tmp.glob("*.part")), [])

    def test_free_space_floor_stops_before_any_http_request(self) -> None:
        rec = load_recorder()
        self.spool_dir.mkdir()
        free = shutil.disk_usage(self.spool_dir).free
        config = rec.RecorderConfig()
        config.hls_url = "http://127.0.0.1:1/live/playlist.m3u8"
        config.spool_dir = self.spool_dir
        config.min_free_bytes = free + 1  # trips on ANY free space value
        instance = rec.HlsRecorder(config)

        server = self.start_hls_server()
        with self.assertRaises(rec.SpoolSpaceLow):
            instance.capture(f"{server.base}/live/seg0.ts", "seg0.ts")
        self.assertEqual(
            server.hits,
            [],
            "the floor must stop recording BEFORE any HTTP request",
        )
        self.assertEqual(list(self.spool_dir.iterdir()), [])

    def test_hung_receiver_is_killed_within_bounded_rsync_timeout(self) -> None:
        rec = load_recorder()
        self.set_rsync_mode("hang")
        key = self.tmp / "key"
        key.write_text("fake-test-key-not-a-secret\n", encoding="utf-8")
        config = rec.RecorderConfig()
        config.hls_url = "http://127.0.0.1:1/live/playlist.m3u8"
        config.key_path = key
        config.spool_dir = self.spool_dir
        self.spool_dir.mkdir()
        config.destination = f"{self.dest_dir}/"
        config.rsync_retries = 1
        config.rsync_backoff_sec = 0.0
        config.rsync_timeout_sec = 0.1
        instance = rec.HlsRecorder(config)
        object_path = self.tmp / "obj.bin"
        object_path.write_bytes(b"payload-bytes")

        started = time.monotonic()
        ok, detail = instance.upload(object_path)
        elapsed = time.monotonic() - started

        self.assertFalse(ok, "a hung receiver must not report success")
        self.assertEqual(detail, "rsync timeout")
        self.assertGreaterEqual(elapsed, 4.0, "the rsync timeout must apply")
        self.assertLess(
            elapsed, 9.0, "the hung rsync must be killed within the budget"
        )
        # The fake rsync child was actually killed, not left running.
        self.assertTrue(self.rsync_pid.exists(), "fake rsync never started")
        fake_pid = int(self.rsync_pid.read_text())
        deadline = time.monotonic() + 2.0
        alive = True
        while alive and time.monotonic() < deadline:
            try:
                os.kill(fake_pid, 0)
            except ProcessLookupError:
                alive = False
            else:
                time.sleep(0.1)
        self.assertFalse(alive, f"hung fake rsync pid {fake_pid} still alive")

    def test_failing_receiver_burns_exact_retry_budget_then_resumes(
        self,
    ) -> None:
        rec = load_recorder()
        self.set_rsync_mode("fail")
        server = self.start_hls_server()
        key = self.tmp / "key"
        key.write_text("fake-test-key-not-a-secret\n", encoding="utf-8")
        config = rec.RecorderConfig()
        config.hls_url = server.playlist_url
        config.key_path = key
        config.spool_dir = self.spool_dir
        config.min_free_bytes = 0  # the floor has its own dedicated test
        config.destination = f"{self.dest_dir}/"
        config.poll_sec = 0.5
        config.rsync_retries = 3
        config.rsync_backoff_sec = 0.0
        config.rsync_timeout_sec = 5.0
        instance = rec.HlsRecorder(config)

        out = drive_recorder_cycles(instance, cycles=1)
        # init + 3 segments each burned exactly 3 attempts, all discarded.
        self.assertEqual(len(self.rsync_calls()), 4 * 3)
        self.assertEqual(out.count("reason=upload_failed"), 4)
        self.assertEqual(instance.captured_count, 0)
        self.assertEqual(instance.gap_count, 4, "each discard counts a gap")
        self.assertEqual(list(self.spool_dir.iterdir()), [], "spool cleaned")

        # Receiver recovers; a NEW object (cycle 2, sequence continues at
        # 10 — no gap) is captured and delivered.
        self.set_rsync_mode("ok")
        server.table["/live/playlist.m3u8"] = PLAYLIST_RESUME
        out2 = drive_recorder_cycles(instance, cycles=1)
        self.assertEqual(instance.captured_count, 2, out2)
        self.assertEqual(
            instance.gap_count, 4, "resume must not erase counted gaps"
        )
        self.assertIn("recorder object ok", out2)
        delivered = sorted(path.name for path in self.dest_dir.iterdir())
        self.assertEqual(len(delivered), 2, delivered)
        init_delivered = next(name for name in delivered if "-init-" in name)
        self.assertEqual(
            (self.dest_dir / init_delivered).read_bytes(), INIT_BYTES
        )
        seg3_delivered = next(name for name in delivered if "-init-" not in name)
        self.assertEqual(
            (self.dest_dir / seg3_delivered).read_bytes(), SEG3_BYTES
        )

    def test_media_sequence_advance_counts_a_gap(self) -> None:
        rec = load_recorder()
        self.set_rsync_mode("ok")
        server = self.start_hls_server()
        key = self.tmp / "key"
        key.write_text("fake-test-key-not-a-secret\n", encoding="utf-8")
        config = rec.RecorderConfig()
        config.hls_url = server.playlist_url
        config.key_path = key
        config.spool_dir = self.spool_dir
        config.min_free_bytes = 0  # the floor has its own dedicated test
        config.destination = f"{self.dest_dir}/"
        config.poll_sec = 0.5
        config.rsync_retries = 2
        config.rsync_backoff_sec = 0.0
        config.rsync_timeout_sec = 5.0
        instance = rec.HlsRecorder(config)

        drive_recorder_cycles(instance, cycles=1)
        self.assertEqual(instance.captured_count, 4)
        self.assertEqual(instance.gap_count, 0)

        # Sequence jumps 10 -> 12 WITHIN one run(): positions 10 and 11 were
        # never seen, so the second cycle must count a gap of 2.
        out = drive_recorder_cycles(
            instance,
            cycles=2,
            between=lambda completed: server.table.__setitem__(
                "/live/playlist.m3u8", PLAYLIST_2
            ),
        )
        self.assertIn("recorder gap missed=2", out)
        self.assertEqual(instance.gap_count, 2)
        self.assertEqual(instance.captured_count, 5, "later object still captured")


# ---------------------------------------------------------------------------
# 5. Credential path (AC-006 / R-8)
# ---------------------------------------------------------------------------


class RecorderCredentialTests(RecorderTestBase):
    """Key only from LoadCredential surfaces, never /home; missing key = off."""

    def _credential_path(self, **env: str) -> Path:
        rec = load_recorder()
        clean = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SEA_SPEED_RECORDER_")
            and key != "CREDENTIALS_DIRECTORY"
        }
        clean.update(env)
        with mock.patch.dict(os.environ, clean, clear=True):
            return rec._credential_path()

    def test_default_credential_path_is_run_credentials_literal(self) -> None:
        rec = load_recorder()
        self.assertEqual(
            str(rec.DEFAULT_CREDENTIAL_PATH),
            "/run/credentials/recorder_ed25519",
        )

    def test_creds_directory_wins_when_key_present(self) -> None:
        key = self.creds_dir / "recorder_ed25519"
        key.write_text("fake-test-key-not-a-secret\n", encoding="utf-8")
        resolved = self._credential_path(CREDENTIALS_DIRECTORY=str(self.creds_dir))
        self.assertEqual(resolved, key)

    def test_creds_directory_candidate_when_key_absent(self) -> None:
        # First existing candidate wins; with nothing existing the first
        # candidate (the systemd surface) is returned so run() can fail on it.
        resolved = self._credential_path(CREDENTIALS_DIRECTORY=str(self.creds_dir))
        self.assertEqual(resolved, self.creds_dir / "recorder_ed25519")

    def test_unset_creds_directory_falls_back_to_run_credentials(self) -> None:
        resolved = self._credential_path()
        self.assertEqual(
            resolved, Path("/run/credentials/recorder_ed25519")
        )

    def test_resolved_key_never_lives_under_home(self) -> None:
        key = self.creds_dir / "recorder_ed25519"
        key.write_text("fake-test-key-not-a-secret\n", encoding="utf-8")
        variants = [
            {},
            {"CREDENTIALS_DIRECTORY": str(self.creds_dir)},
            {"CREDENTIALS_DIRECTORY": str(self.tmp / "missing")},
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                resolved = self._credential_path(**variant)
                self.assertFalse(
                    str(resolved).startswith("/home"),
                    f"credential path must never be under /home: {resolved}",
                )

    def test_recorder_source_has_no_home_credential_path(self) -> None:
        source = RECORDER_SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn(
            "/home/",
            source,
            "recorder.py must not contain a /home credential path literal",
        )

    def test_missing_key_disables_recording_without_raising(self) -> None:
        server = self.start_hls_server()
        empty_creds = self.tmp / "empty-creds"
        empty_creds.mkdir()
        env = self.child_env(
            SEA_SPEED_RECORDER_ENABLED="1",
            SEA_SPEED_RECORDER_HLS_URL=server.playlist_url,
            CREDENTIALS_DIRECTORY=str(empty_creds),
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

        self.assertEqual(proc.returncode, 2, out)
        self.assertIn("recorder disabled runtime_error=", out)
        self.assertIn("credential missing or unreadable", out)
        self.assertNotIn("Traceback", out, "must disable, not crash")
        self.assertEqual(server.hits, [], "no fetch before the key check")
        self.assertFalse(
            self.spool_dir.exists(),
            "no spool before the key check",
        )
        self.assertEqual(self.rsync_calls(), [])


if __name__ == "__main__":
    unittest.main()
