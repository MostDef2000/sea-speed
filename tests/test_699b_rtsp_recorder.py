"""Issue #699b: RTSP stream-copy recorder — identity oracle, config, transport, bounds.

The production side (``worker/recorder_rtsp.py`` and the
``SEA_SPEED_RECORDER_SOURCE_TYPE`` selector in ``worker/recorder.py``) landed
with the code worker; these tests pin the OUTCOMES from the #699b spec
(``specs/699-rtsp-recorder/spec.md``) with literal expectations written from
the issue/spec text, never derived from the implementation.

Sections (one class each):

* ``StreamCopyIdentityOracleTests`` — the primary oracle (spec "Identity
  contract"): a committed deterministic closed-GOP H.264 fixture (8 s @ 25 fps,
  IDR every 25 frames, 2 B-frames, 200 coded pictures / 8 IDRs) is fed through
  the REAL production output argv and the real spool/upload path — only the
  input side of argv is substituted with the fixture (the RTSP protocol
  options cannot apply to a file input; the output argv from ``-map 0:v:0`` on
  is byte-exact production, asserted against the relay literal). The delivered
  Matroska clips are then demuxed INDEPENDENTLY (ffmpeg raw Annex-B
  extraction) and the ORDERED CODED PICTURE NAL bytes/counts must equal the
  source across all cuts (Annex-B vs length framing normalized by
  construction), parameter sets must be carried by every clip, relative
  presentation timing must match the source at each cut, and each clip must
  decode in a fresh process. Negative controls: an altered payload byte, a
  dropped NAL and an accidental re-encode MUST fail the oracle. No whole-file
  hash is used as the only proof (Matroska headers carry dates).
* ``RtspConfigSelectorTests`` — selector/config: ``ENABLED=0`` returns before
  validation/import/I/O for BOTH source types (no ffmpeg, no rsync, no spool);
  default source type ``hls``; explicit ``rtsp`` reads the existing ``HLS_URL``
  only (no fallback to ``SEA_SPEED_RECORDER_HLS_URL``); the RTSP URL must be
  an absolute ``rtsp://`` URL with a host; unknown selector values refuse.
* ``RtspTransportTests`` — relay argv pins ``-rtsp_transport tcp`` + bounded
  timeout/probe options and the exact stream-copy/segment tail; the direct
  camera path writes a fresh 0600 ffconcat in the private temp (never the
  spool), transport follows ``CAMERA1_RTSP_TRANSPORT`` (udp default, TCP never
  forced), the manifest is removed after the capture attempt, and a synthetic
  credential canary never reaches argv, logs or uploaded metadata.
* ``RtspBoundsFailureTests`` — 30 s no-segment deadline, RLIMIT_FSIZE on the
  ffmpeg child only, 64 MiB per-object cap (whole object incl. trailer), 12
  GiB floor, two-slot spool with the rollover completion witness, missing
  parent dirs fail closed, stalled/failed rsync bounded with counted gaps,
  crash cleanup, process-group inheritance for the ffmpeg grandchild, and gap
  vs outage counted separately.
* ``RtspIngestParityTests`` — ingest parity: the entrypoint reader argv and
  the raw frame bytes a deterministic fake reader child produces are identical
  across recorder states (unset / 0 / hls / rtsp-failing / rtsp-ok), reusing
  the tests/test_699_recorder baseline pattern.

Environment: stdlib-only top-level imports (battery import-hygiene scan).
The identity class needs a real ``ffmpeg`` on PATH (``shutil.which``) and
skips with a named reason when absent; every other class runs without ffmpeg
(fake ``ffmpeg``/``rsync`` executables on PATH record any invocation). No
private media (the fixture is synthetic ``testsrc2`` bytes committed as
base64), no real credentials (all keys/URLs are synthetic canaries), no
network beyond loopback-free local spawns.

RED spot-check (what fails on base ``c689947``, before the #699b production
change; measured against a ``git archive`` of base with these test files
copied in):

* ``worker/recorder_rtsp.py`` does not exist at base, so every in-process
  helper test errors with ``ModuleNotFoundError: No module named
  'recorder_rtsp'`` and the identity class errors in ``setUpClass``.
* ``worker/recorder.py`` at base has no selector: ``RecorderConfig`` has no
  ``source_type`` attribute (AttributeError), ``SEA_SPEED_RECORDER_SOURCE_TYPE
  =bogus`` is silently ignored, and ``rtsp`` never reads ``HLS_URL`` (the
  invalid-URL child test times out instead of exiting rc 2).
* The env examples at base carry no ``SEA_SPEED_RECORDER_SOURCE_TYPE`` line
  and the exact-artifact inventories contain no ``worker/recorder_rtsp.py``
  entry (tests/test_699_recorder_lifecycle.py).
* Deliberate GREEN-on-base regression pins (the #696/#699 convention): the
  ingest-parity tests (reader argv / frame bytes), the ``ENABLED=0``
  zero-I/O child test and the disabled-before-import short-circuit — the
  reader substrate and the disabled short-circuit exist at base and must not
  change; they prove the recorder never touches ingest, they are not a change
  oracle.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import importlib.util
import io
import os
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = ROOT / "worker"
RECORDER_SCRIPT = WORKER_DIR / "recorder.py"
ENTRYPOINT = WORKER_DIR / "ubuntu_worker_entrypoint.py"
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

# The identity oracle needs a real ffmpeg (demux/decode/production spawn).
FFMPEG = shutil.which("ffmpeg")

# ---------------------------------------------------------------------------
# Literals: the oracle. Written from the issue/spec text FIRST — never
# derived from the module under test.
# ---------------------------------------------------------------------------

DISABLED_OUTPUT = "recorder disabled (SEA_SPEED_RECORDER_ENABLED=0)"
RELAY_URL = "rtsp://relay.example.internal/stream"
DIRECT_URL = "rtsp://camera_user:camera_pass@10.123.239.5:554/stream1"
CANARY_SECRET = "CanaryPassw0rd77"
CANARY_USER = "svc_canary_user"
CANARY_URL = f"rtsp://{CANARY_USER}:{CANARY_SECRET}@10.0.0.5:554/stream"
CANARY_LABEL = "rtsp://10.0.0.5:554"  # safe_media_input_label output (no userinfo)

DEFAULT_OBJECT_MAX_BYTES = 67108864  # 64 MiB (spec R-5)
DEFAULT_MIN_FREE_BYTES = 12884901888  # 12 GiB (spec R-5)
NO_SEGMENT_DEADLINE_SEC = 30.0  # spec R-8
SLOT_COUNT = 2  # spec R-6: two 64 MiB slots per camera
SEGMENT_SECONDS = 2  # spec R-4: 2-second segmented Matroska

# Fixture: synthetic testsrc2, closed GOP, committed as base64 (no private
# media). Generated once with:
#   ffmpeg -f lavfi -i testsrc2=size=64x64:rate=25:duration=8 \
#     -c:v libx264 -preset medium -crf 32 -g 25 -keyint_min 25 \
#     -sc_threshold 0 -bf 2 -pix_fmt yuv420p -x264-params open-gop=0 \
#     -f matroska fixture.mkv
FIXTURE_SHA256 = "bac7864193cbf5d9132643747ef2374db16905b144b74756d38eda8445732ec7"
FIXTURE_BYTES = 30908
FIXTURE_VCL_NALS = 200  # 8 s * 25 fps, one slice per frame
FIXTURE_IDR_NALS = 8  # IDR every 25 frames (closed GOP)
FIXTURE_FRAMES = 200
CLIP_COUNT = 4  # 8 s / 2 s segment target, cuts on the 1 s IDR grid
CLIP_VCL_NALS = 50  # 2 s * 25 fps per delivered clip

FIXTURE_B64 = (
    "GkXfo6NChoEBQveBAULygQRC84EIQoKIbWF0cm9za2FCh4EEQoWBAhhTgGcBAAAAAAB4iBFNm3TA"
    "v4QbEPLvTbuLU6uEFUmpZlOsgaFNu4tTq4QWVK5rU6yB7027jFOrhBJUw2dTrIIBhU27jFOrhBxT"
    "u2tTrIJ36ewBAAAAAAAAUwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAFUmpZsm/hNUBB8gq17GD"
    "D0JATYCMTGF2ZjYxLjEuMTAwV0GMTGF2ZjYxLjEuMTAwc6SQSfX2ZEF0Dsys2laisrSPmkSJiEC/"
    "QAAAAAAAFlSua0CQv4Qg0F/yrgEAAAAAAACB14EBc8WI0Eo+rF7UmKecgQAitZyDdW5kiIEAho9W"
    "X01QRUc0L0lTTy9BVkODgQEj44OEAmJaAOCJsIFAuoFAmoECVe6BAOwBAAAAAAAAAgAAY6KtAWQA"
    "Cv/hABhnZAAKrNlEJsBEAAADAAQAAAMAyDxIllgBAAZo6+GSyLD9+PgAElTDZ0CBv4TJYIeYc3Of"
    "Y8CAZ8iZRaOHRU5DT0RFUkSHjExhdmY2MS4xLjEwMHNz1mPAi2PFiNBKPqxe1JinZ8ihRaOHRU5D"
    "T0RFUkSHlExhdmM2MS4zLjEwMCBsaWJ4MjY0Z8ihRaOIRFVSQVRJT05Eh5MwMDowMDowOC4wMDAw"
    "MDAwMDAAH0O2dV39v4TLk69y54EAo0WMgQAAgAAAAqwGBf//qNxF6b3m2Ui3lizYINkj7u94MjY0"
    "IC0gY29yZSAxNjQgcjMxOTEgNDYxM2FjMyAtIEguMjY0L01QRUctNCBBVkMgY29kZWMgLSBDb3B5"
    "bGVmdCAyMDAzLTIwMjQgLSBodHRwOi8vd3d3LnZpZGVvbGFuLm9yZy94MjY0Lmh0bWwgLSBvcHRp"
    "b25zOiBjYWJhYz0xIHJlZj0zIGRlYmxvY2s9MTowOjAgYW5hbHlzZT0weDM6MHgxMTMgbWU9aGV4"
    "IHN1Ym1lPTcgcHN5PTEgcHN5X3JkPTEuMDA6MC4wMCBtaXhlZF9yZWY9MSBtZV9yYW5nZT0xNiBj"
    "aHJvbWFfbWU9MSB0cmVsbGlzPTEgOHg4ZGN0PTEgY3FtPTAgZGVhZHpvbmU9MjEsMTEgZmFzdF9w"
    "c2tpcD0xIGNocm9tYV9xcF9vZmZzZXQ9LTIgdGhyZWFkcz0yIGxvb2thaGVhZF90aHJlYWRzPTEg"
    "c2xpY2VkX3RocmVhZHM9MCBucj0wIGRlY2ltYXRlPTEgaW50ZXJsYWNlZD0wIGJsdXJheV9jb21w"
    "YXQ9MCBjb25zdHJhaW5lZF9pbnRyYT0wIGJmcmFtZXM9MiBiX3B5cmFtaWQ9MiBiX2FkYXB0PTEg"
    "Yl9iaWFzPTAgZGlyZWN0PTEgd2VpZ2h0Yj0xIG9wZW5fZ29wPTAgd2VpZ2h0cD0yIGtleWludD0y"
    "NSBrZXlpbnRfbWluPTEzIHNjZW5lY3V0PTAgaW50cmFfcmVmcmVzaD0wIHJjX2xvb2thaGVhZD0y"
    "NSByYz1jcmYgbWJ0cmVlPTEgY3JmPTMyLjAgcWNvbXA9MC42MCBxcG1pbj0wIHFwbWF4PTY5IHFw"
    "c3RlcD00IGlwX3JhdGlvPTEuNDAgYXE9MToxLjAwAIAAAALUZYiEAN/Z+7pvkap1akGF34lD5C8T"
    "Dkrs85J4YlZqJ5d6032RdN3KcZLhc7f3KIzDbnzTumP8yRaOxsgFHrSrxTdppb8WCnUFc0oZFsDK"
    "KXB/6e5BJ9jCAmPLHyT/9lMaAikwiOICkluu2/xoXqilgPOIsXQIk8wpNsLk4TZO22SDyzACaCIm"
    "zKD6axGLQHQq8pYfCvaTcO0Mrgl5DriL7GIzJ/z17UW0AaonnhBZh7e6+8wSPD0ti6x4mk9hdYl8"
    "2Fu5lzrNI8velHMp+dgTlLQQwxBVdqx3G/aZWT0H8fMFF5NZlZ/xJIRcsXl31v900gpwU9s151JD"
    "XvlJF318CizRNntJ2F7binDTuwG+wvqAlMZEOcwreg9JshFFUNTAShnBcn/5IzOnrWkURLaBIld+"
    "s6X/G55Ggwi54RBS3uBCot6eoUhCm49F4rUFlt0wc0l/LLlT0NbtFQpw/Ykvo1dEZmw+P+0GcrUm"
    "lSHO8IEo2EiQnHdFQiKfn7qQRdC73r8BBORuSjbal1+mUiS9cKtenLZeyMbaAHSfZP8J8KtI3pKl"
    "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"
    "WLeL94EB8YJa4vCCDfg="
)


def expected_relay_argv(session_dir: Path) -> list[str]:
    """The exact production relay argv (spec R-4/R-7), written from spec."""
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-nostats",
        "-loglevel",
        "error",
        "-xerror",
        "-rtsp_transport",
        "tcp",
        "-timeout",
        "5000000",
        "-analyzeduration",
        "5000000",
        "-probesize",
        "5000000",
        "-i",
        RELAY_URL,
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        "-c:v",
        "copy",
        "-map_metadata",
        "-1",
        "-map_chapters",
        "-1",
        "-f",
        "segment",
        "-reference_stream",
        "v:0",
        "-segment_time",
        str(SEGMENT_SECONDS),
        "-segment_format",
        "matroska",
        "-individual_header_trailer",
        "1",
        "-break_non_keyframes",
        "0",
        "-reset_timestamps",
        "1",
        str(session_dir / "%09d/clip.mkv.part"),
    ]


# Output tail index inside the relay argv (head 7 + relay source 10).
RELAY_TAIL_INDEX = 17


# ---------------------------------------------------------------------------
# Module loaders (lazy so a missing module fails the individual test that
# needs it instead of erroring the whole file at collection — base RED).
# ---------------------------------------------------------------------------


def load_recorder():
    import recorder

    return recorder


def load_recorder_rtsp():
    import recorder_rtsp

    return recorder_rtsp


def load_entrypoint():
    """Load the Ubuntu entrypoint the provenance way (tests/test_696).

    Only the heavy runtime worker module is stubbed; numpy/requests are
    guarded-optional (battery guard idiom).
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
    runtime_worker.env_str = lambda name, default="": os.environ.get(name, default)
    runtime_worker.env_int = lambda name, default=0: int(
        os.environ.get(name, default)
    )
    runtime_worker.env_float = lambda name, default=0.0: float(
        os.environ.get(name, default)
    )
    runtime_worker.safe_media_input_label = lambda url: "<configured>"
    spec = importlib.util.spec_from_file_location(
        "ubuntu_worker_entrypoint_699b_parity", ENTRYPOINT
    )
    module = importlib.util.module_from_spec(spec)
    # Single-key management, NOT mock.patch.dict(sys.modules): patch.dict
    # restores the WHOLE dict on exit, evicting numpy imported during exec
    # (the tests/test_696 docstring warning).
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


# ---------------------------------------------------------------------------
# Independent demux helpers (the oracle's own tooling — never the module
# under test). Annex-B extraction normalizes container framing by
# construction: every clip and the source are dumped to the same raw
# Annex-B stream, then split into NAL payloads without start codes.
# ---------------------------------------------------------------------------


def _annexb(path: Path) -> bytes:
    result = subprocess.run(
        [
            FFMPEG,
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-c",
            "copy",
            "-f",
            "h264",
            "-",
        ],
        capture_output=True,
        check=True,
    )
    return result.stdout


def _split_nals(data: bytes) -> list[bytes]:
    """Split an Annex-B stream into NAL payloads (start codes stripped)."""
    positions: list[int] = []
    for match in re.finditer(b"\x00\x00\x01", data):
        start = match.start()
        if start > 0 and data[start - 1] == 0:
            start -= 1
        positions.append(start)
    positions.append(len(data))
    nals: list[bytes] = []
    for begin, end in zip(positions, positions[1:]):
        start_code = 4 if data[begin : begin + 4] == b"\x00\x00\x00\x01" else 3
        nals.append(data[begin + start_code : end])
    return nals


def _vcl(nals: list[bytes]) -> list[bytes]:
    """Ordered coded picture NALs (VCL types 1 and 5)."""
    return [nal for nal in nals if (nal[0] & 0x1F) in (1, 5)]


_SHOWINFO_RE = re.compile(
    r"n:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:([0-9.]+).*?iskey:(\d)\s+type:([A-Z])"
)


def _decoded_frames(path: Path) -> list[tuple[float, bool, str]]:
    """Fresh-process decode: (pts_time, iskey, picture type) per frame."""
    result = subprocess.run(
        [
            FFMPEG,
            "-v",
            "info",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-vf",
            "showinfo",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    frames: list[tuple[float, bool, str]] = []
    for line in result.stderr.splitlines():
        if "Parsed_showinfo" not in line:
            continue
        match = _SHOWINFO_RE.search(line)
        if match:
            frames.append(
                (float(match.group(3)), match.group(4) == "1", match.group(5))
            )
    return frames


# ---------------------------------------------------------------------------
# Fake executables (record every invocation; never real media/credentials)
# ---------------------------------------------------------------------------


def fake_rsync_script() -> str:
    """Fake ``rsync``: mode file controls ok / fail / hang; logs every call."""
    return (
        "#!/usr/bin/env python3\n"
        "import os, resource, shutil, sys, time\n"
        "src = sys.argv[-2]\n"
        "rlimit_path = os.environ.get('FAKE_RSYNC_RLIMIT')\n"
        "if rlimit_path:\n"
        "    with open(rlimit_path, 'w') as handle:\n"
        "        handle.write(repr(resource.getrlimit(resource.RLIMIT_FSIZE)))\n"
        "mode_path = os.environ['FAKE_RSYNC_MODE']\n"
        "mode = open(mode_path).read().strip() if os.path.exists(mode_path) else 'ok'\n"
        "with open(os.environ['FAKE_RSYNC_LOG'], 'a') as handle:\n"
        "    handle.write(os.path.basename(src) + '\\n')\n"
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


def fake_ffmpeg_script() -> str:
    """Fake ``ffmpeg``: records its argv and fails — any spawn is a failure."""
    return (
        "#!/usr/bin/env python3\n"
        "import os, sys\n"
        "with open(os.environ['FAKE_FFMPEG_LOG'], 'a') as handle:\n"
        "    handle.write(' '.join(sys.argv[1:]) + '\\n')\n"
        "sys.exit(99)\n"
    )


class _StopAfterStart(Exception):
    """Raised from a stubbed ``_capture_session`` to end ``run()`` early."""


class _StopAfterCycle(Exception):
    """Raised from the patched poll-sleep to end ``RtspRecorder.run()``."""


# ---------------------------------------------------------------------------
# Shared base: temp dirs, fake executables, env hygiene, config builder
# ---------------------------------------------------------------------------


class RtspRecorderTestBase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="test699b-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.bin_dir = self.tmp / "bin"
        self.dest_dir = self.tmp / "dest"
        self.spool_dir = self.tmp / "spool"
        self.creds_dir = self.tmp / "creds"
        for directory in (self.bin_dir, self.dest_dir, self.spool_dir, self.creds_dir):
            directory.mkdir(parents=True)
        self.rsync_log = self.tmp / "rsync.log"
        self.rsync_mode = self.tmp / "rsync.mode"
        self.rsync_pid = self.tmp / "rsync.pid"
        self.rsync_rlimit = self.tmp / "rsync.rlimit"
        self.ffmpeg_log = self.tmp / "ffmpeg.log"
        fake = self.bin_dir / "rsync"
        fake.write_text(fake_rsync_script(), encoding="utf-8")
        fake.chmod(0o755)
        fake_ffmpeg = self.bin_dir / "ffmpeg"
        fake_ffmpeg.write_text(fake_ffmpeg_script(), encoding="utf-8")
        fake_ffmpeg.chmod(0o755)
        # In-process recorder drives run rsync in THIS process, so the fake
        # executables need their control env here too (children get it via
        # child_env). patch.dict restores the ambient environment on exit.
        self._env = mock.patch.dict(
            os.environ,
            {
                "PATH": f"{self.bin_dir}:{os.environ.get('PATH', '')}",
                "FAKE_RSYNC_DEST": str(self.dest_dir),
                "FAKE_RSYNC_LOG": str(self.rsync_log),
                "FAKE_RSYNC_MODE": str(self.rsync_mode),
                "FAKE_RSYNC_PID": str(self.rsync_pid),
                "FAKE_FFMPEG_LOG": str(self.ffmpeg_log),
            },
        )
        self._env.start()
        self.addCleanup(self._env.stop)
        (self.creds_dir / "recorder_ed25519").write_text(
            "fake-test-key-not-a-secret\n", encoding="utf-8"
        )

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _clean_env(**env: str) -> dict:
        """Env without ambient recorder/credential/transport leakage."""
        clean = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SEA_SPEED_RECORDER_")
            and key not in ("HLS_URL", "CREDENTIALS_DIRECTORY", "CAMERA1_RTSP_TRANSPORT")
        }
        clean.update(env)
        return clean

    def child_env(self, **overrides: str) -> dict:
        """Recorder child env: no ambient recorder/credential/auth leakage."""
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SEA_SPEED_RECORDER_")
            and key
            not in (
                "CREDENTIALS_DIRECTORY",
                "HLS_URL",
                "CAMERA1_RTSP_TRANSPORT",
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
                "FAKE_FFMPEG_LOG": str(self.ffmpeg_log),
                "CREDENTIALS_DIRECTORY": str(self.creds_dir),
            }
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

    def rsync_calls(self) -> list[str]:
        if not self.rsync_log.exists():
            return []
        return [line for line in self.rsync_log.read_text().splitlines() if line]

    def set_rsync_mode(self, mode: str) -> None:
        self.rsync_mode.write_text(mode, encoding="utf-8")

    def make_config(self, **overrides):
        """A fully-populated RTSP recorder config over the test temp dirs."""
        config = load_recorder().RecorderConfig()
        config.enabled = True
        config.source_type = "rtsp"
        config.rtsp_url = RELAY_URL
        config.spool_dir = self.spool_dir
        config.destination = f"{self.dest_dir}/"
        config.key_path = self.creds_dir / "recorder_ed25519"
        config.min_free_bytes = 0
        config.poll_sec = 0.5
        config.rsync_retries = 2
        config.rsync_backoff_sec = 0.0
        config.rsync_timeout_sec = 5.0
        for name, value in overrides.items():
            setattr(config, name, value)
        return config

    @staticmethod
    def _plant_part(instance, index: int, data: bytes) -> Path:
        directory = instance.session_dir / f"{index:09d}"
        directory.mkdir(parents=True, exist_ok=True)
        part = directory / "clip.mkv.part"
        part.write_bytes(data)
        return part

    @staticmethod
    def _fresh_instance(config):
        instance = load_recorder_rtsp().RtspRecorder(config)
        instance.session_dir.mkdir(mode=0o700)
        return instance


# ---------------------------------------------------------------------------
# 1. Stream-copy identity oracle (spec "Identity contract")
# ---------------------------------------------------------------------------


@unittest.skipUnless(FFMPEG, "ffmpeg on PATH is required for the identity oracle")
class StreamCopyIdentityOracleTests(unittest.TestCase):
    """Delivered clips preserve the ordered coded picture data of the source."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        rtsp = load_recorder_rtsp()
        rec = load_recorder()
        cls.rtsp = rtsp
        cls.tmp = Path(tempfile.mkdtemp(prefix="test699b-oracle-"))
        cls.bin_dir = cls.tmp / "bin"
        cls.dest_dir = cls.tmp / "dest"
        cls.spool_dir = cls.tmp / "spool"
        cls.creds_dir = cls.tmp / "creds"
        for directory in (cls.bin_dir, cls.dest_dir, cls.spool_dir, cls.creds_dir):
            directory.mkdir(parents=True)
        fake = cls.bin_dir / "rsync"
        fake.write_text(fake_rsync_script(), encoding="utf-8")
        fake.chmod(0o755)
        (cls.creds_dir / "recorder_ed25519").write_text(
            "fake-test-key-not-a-secret\n", encoding="utf-8"
        )
        cls.fixture = cls.tmp / "fixture.mkv"
        cls.fixture.write_bytes(base64.b64decode(FIXTURE_B64))
        cls._env = mock.patch.dict(
            os.environ,
            {
                "PATH": f"{cls.bin_dir}:{os.environ.get('PATH', '')}",
                "FAKE_RSYNC_DEST": str(cls.dest_dir),
                "FAKE_RSYNC_LOG": str(cls.tmp / "rsync.log"),
                "FAKE_RSYNC_MODE": str(cls.tmp / "rsync.mode"),
                "FAKE_RSYNC_PID": str(cls.tmp / "rsync.pid"),
            },
        )
        cls._env.start()

        config = rec.RecorderConfig()
        config.enabled = True
        config.source_type = "rtsp"
        config.rtsp_url = RELAY_URL
        config.spool_dir = cls.spool_dir
        config.destination = f"{cls.dest_dir}/"
        config.key_path = cls.creds_dir / "recorder_ed25519"
        config.min_free_bytes = 0
        config.poll_sec = 0.5
        config.rsync_retries = 2
        config.rsync_backoff_sec = 0.0
        config.rsync_timeout_sec = 10.0
        cls.config = config
        instance = rtsp.RtspRecorder(config)
        instance.session_dir.mkdir(mode=0o700)
        cls.inst = instance

        # Run the PRODUCTION argv; substitute only the input side (the RTSP
        # protocol options cannot apply to a file input). The output argv
        # from "-map" on stays byte-exact production.
        cls.seen_argv: list[list[str]] = []
        cls.ffmpeg_pgid: int | None = None
        real_popen = subprocess.Popen

        def splice(argv, **kwargs):
            cls.seen_argv.append(list(argv))
            if argv[0] != "ffmpeg":
                return real_popen(argv, **kwargs)
            head = argv[:7]
            tail = argv[argv.index("-map") :]
            process = real_popen(head + ["-re", "-i", str(cls.fixture)] + tail, **kwargs)
            cls.ffmpeg_pgid = os.getpgid(process.pid)
            return process

        out = io.StringIO()
        with mock.patch.object(rtsp.subprocess, "Popen", side_effect=splice):
            with contextlib.redirect_stdout(out):
                cls.clean = instance._capture_session()
        cls.pipeline_out = out.getvalue()
        if not cls.clean or instance.captured_count != CLIP_COUNT:
            raise AssertionError(
                "identity pipeline failed: clean="
                f"{cls.clean} captured={instance.captured_count} "
                f"gap={instance.gap_count}\n{cls.pipeline_out}"
            )

        # Independent demux of source and delivered clips.
        cls.src_nals = _split_nals(_annexb(cls.fixture))
        cls.src_vcl = _vcl(cls.src_nals)
        cls.src_frames = _decoded_frames(cls.fixture)
        cls.clips = sorted(path for path in cls.dest_dir.iterdir() if path.suffix == ".mkv")
        cls.clip_nals = [_split_nals(_annexb(path)) for path in cls.clips]
        cls.clip_vcl = [_vcl(nals) for nals in cls.clip_nals]
        cls.clip_frames = [_decoded_frames(path) for path in cls.clips]
        cls.rsync_calls = [
            line
            for line in (cls.tmp / "rsync.log").read_text().splitlines()
            if line
        ]

    @classmethod
    def tearDownClass(cls) -> None:
        cls._env.stop()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # -- fixture structure --------------------------------------------------

    def test_fixture_is_closed_gop_h264_with_multiple_idrs_and_b_frames(self) -> None:
        data = self.fixture.read_bytes()
        self.assertEqual(len(data), FIXTURE_BYTES)
        self.assertEqual(hashlib.sha256(data).hexdigest(), FIXTURE_SHA256)
        self.assertEqual(len(self.src_vcl), FIXTURE_VCL_NALS)
        idr_nals = [nal for nal in self.src_nals if (nal[0] & 0x1F) == 5]
        self.assertEqual(len(idr_nals), FIXTURE_IDR_NALS)
        self.assertGreaterEqual(
            len(idr_nals), 3, "the fixture must contain multiple IDRs"
        )
        self.assertTrue(
            any((nal[0] & 0x1F) == 7 for nal in self.src_nals), "SPS required"
        )
        self.assertTrue(
            any((nal[0] & 0x1F) == 8 for nal in self.src_nals), "PPS required"
        )
        self.assertEqual(len(self.src_frames), FIXTURE_FRAMES)
        self.assertTrue(
            any(kind == "B" for _, _, kind in self.src_frames),
            "the fixture must contain B-frames",
        )
        self.assertEqual(
            sum(1 for _, is_key, _ in self.src_frames if is_key),
            FIXTURE_IDR_NALS,
        )

    # -- the oracle ---------------------------------------------------------

    def test_delivered_clips_preserve_ordered_coded_picture_data_across_cuts(
        self,
    ) -> None:
        self.assertTrue(self.clean, "the production capture must finish cleanly")
        self.assertEqual(len(self.clips), CLIP_COUNT)
        concat = [nal for vcl in self.clip_vcl for nal in vcl]
        self.assertEqual(len(concat), FIXTURE_VCL_NALS)
        self.assertEqual(
            concat,
            self.src_vcl,
            "ordered coded picture NAL bytes must be identical to the source "
            "across every cut (stream copy, no re-encode, no dropped frames)",
        )
        for index, vcl in enumerate(self.clip_vcl):
            self.assertEqual(len(vcl), CLIP_VCL_NALS, f"clip {index} frame count")
            self.assertEqual(
                vcl[0][0] & 0x1F,
                5,
                f"clip {index} must start at an IDR (no mid-GOP cut)",
            )
        # Delivery order == sequence order; one upload per segment.
        self.assertEqual(self.rsync_calls, [path.name for path in self.clips])
        self.assertEqual(
            self.pipeline_out.count("recorder rtsp segment ok"), CLIP_COUNT
        )
        self.assertEqual(self.inst.gap_count, 0)
        self.assertEqual(self.inst.outage_count, 0)
        # The production argv (before input substitution) was the exact
        # relay literal from the spec.
        self.assertEqual(
            self.seen_argv[0], expected_relay_argv(self.inst.session_dir)
        )

    def test_ffmpeg_grandchild_runs_in_the_recorder_process_group(self) -> None:
        # No start_new_session: the entrypoint's killpg reaches ffmpeg.
        self.assertIsNotNone(self.ffmpeg_pgid)
        self.assertEqual(self.ffmpeg_pgid, os.getpgid(0))

    def test_parameter_sets_are_carried_by_every_clip_and_match_the_source(
        self,
    ) -> None:
        src_sps = {nal for nal in self.src_nals if (nal[0] & 0x1F) == 7}
        src_pps = {nal for nal in self.src_nals if (nal[0] & 0x1F) == 8}
        self.assertTrue(src_sps and src_pps)
        for index, nals in enumerate(self.clip_nals):
            sps = {nal for nal in nals if (nal[0] & 0x1F) == 7}
            pps = {nal for nal in nals if (nal[0] & 0x1F) == 8}
            self.assertTrue(sps, f"clip {index} must carry an SPS")
            self.assertTrue(pps, f"clip {index} must carry a PPS")
            self.assertTrue(
                sps <= src_sps, f"clip {index} SPS must match the source SPS"
            )
            self.assertTrue(
                pps <= src_pps, f"clip {index} PPS must match the source PPS"
            )

    def test_relative_presentation_timing_matches_the_source_at_each_cut(
        self,
    ) -> None:
        offset = 0
        for index, (frames, vcl) in enumerate(
            zip(self.clip_frames, self.clip_vcl)
        ):
            self.assertEqual(len(frames), len(vcl))
            window = self.src_frames[offset : offset + len(frames)]
            self.assertEqual(len(window), len(frames))
            clip_relative = [round(pts - frames[0][0], 3) for pts, _, _ in frames]
            source_relative = [
                round(pts - window[0][0], 3) for pts, _, _ in window
            ]
            self.assertEqual(
                clip_relative,
                source_relative,
                f"clip {index} relative presentation timing drifted from the source",
            )
            offset += len(frames)
        self.assertEqual(offset, FIXTURE_FRAMES)

    def test_each_delivered_clip_decodes_in_a_fresh_process(self) -> None:
        for path in [self.fixture, *self.clips]:
            with self.subTest(clip=path.name):
                result = subprocess.run(
                    [FFMPEG, "-v", "error", "-i", str(path), "-f", "null", "-"],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")

    # -- negative controls: the oracle must bite ----------------------------

    def test_negative_control_altered_payload_fails_the_oracle(self) -> None:
        mutated = list(self.src_vcl)
        index = len(mutated) // 2
        nal = mutated[index]
        mutated[index] = nal[:10] + bytes([nal[10] ^ 0xFF]) + nal[11:]
        self.assertNotEqual(mutated, self.src_vcl)
        diffs = [
            position
            for position, (left, right) in enumerate(zip(mutated, self.src_vcl))
            if left != right
        ]
        self.assertEqual(
            diffs, [index], "exactly the flipped NAL may differ (sanity)"
        )
        dropped = self.src_vcl[:10] + self.src_vcl[11:]
        self.assertNotEqual(dropped, self.src_vcl)

    def test_negative_control_reencode_fails_the_oracle(self) -> None:
        probe = subprocess.run(
            [FFMPEG, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
        )
        if "libx264" not in probe.stdout:
            self.skipTest("ffmpeg build has no libx264 encoder for the re-encode control")
        reencoded = self.tmp / "reencoded.mkv"
        subprocess.run(
            [
                FFMPEG,
                "-y",
                "-v",
                "error",
                "-i",
                str(self.fixture),
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-g",
                "25",
                "-bf",
                "2",
                str(reencoded),
            ],
            check=True,
            capture_output=True,
        )
        vcl = _vcl(_split_nals(_annexb(reencoded)))
        self.assertNotEqual(
            vcl,
            self.src_vcl,
            "an accidental re-encode must fail the ordered-NAL oracle",
        )


# ---------------------------------------------------------------------------
# 2. Config / selector (spec R-1/R-2/R-3)
# ---------------------------------------------------------------------------


class RtspConfigSelectorTests(RtspRecorderTestBase):
    def test_disabled_returns_zero_io_for_both_source_types(self) -> None:
        for source_type in ("hls", "rtsp"):
            with self.subTest(source_type=source_type):
                ffmpeg_log = self.tmp / f"ffmpeg-{source_type}.log"
                rsync_log = self.tmp / f"rsync-{source_type}.log"
                spool = self.tmp / f"spool-{source_type}"
                env = self.child_env(
                    SEA_SPEED_RECORDER_ENABLED="0",
                    SEA_SPEED_RECORDER_SOURCE_TYPE=source_type,
                    SEA_SPEED_RECORDER_SPOOL_DIR=str(spool),
                    SEA_SPEED_RECORDER_HLS_URL="http://127.0.0.1:1/playlist.m3u8",
                    HLS_URL="rtsp://relay.example.internal/stream",
                    FAKE_FFMPEG_LOG=str(ffmpeg_log),
                    FAKE_RSYNC_LOG=str(rsync_log),
                )
                proc = self.spawn_recorder(env)
                out, _ = proc.communicate(timeout=15)
                out = out or ""

                self.assertEqual(proc.returncode, 0, out)
                self.assertIn(DISABLED_OUTPUT, out)
                self.assertNotIn("recorder rtsp start", out)
                self.assertNotIn("recorder start ", out)
                self.assertFalse(
                    ffmpeg_log.exists(), "disabled recorder must not spawn ffmpeg"
                )
                self.assertFalse(
                    rsync_log.exists(), "disabled recorder must not rsync"
                )
                self.assertFalse(
                    spool.exists(), "disabled recorder must not create the spool"
                )

    def test_disabled_returns_before_selector_validation(self) -> None:
        rec = load_recorder()
        with mock.patch.dict(
            os.environ,
            self._clean_env(
                SEA_SPEED_RECORDER_ENABLED="0",
                SEA_SPEED_RECORDER_SOURCE_TYPE="bogus",
            ),
            clear=True,
        ):
            config = rec.RecorderConfig.from_env()
        self.assertFalse(config.enabled)
        self.assertEqual(
            config.source_type,
            "hls",
            "the disabled path must return before reading the selector",
        )

    def test_disabled_returns_before_rtsp_module_import(self) -> None:
        rec = load_recorder()
        previous = sys.modules.get("recorder_rtsp")
        sys.modules["recorder_rtsp"] = None  # import would raise ImportError
        try:
            with mock.patch.dict(
                os.environ,
                self._clean_env(
                    SEA_SPEED_RECORDER_ENABLED="0",
                    SEA_SPEED_RECORDER_SOURCE_TYPE="rtsp",
                ),
                clear=True,
            ):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    rc = rec.main()
        finally:
            if previous is None:
                sys.modules.pop("recorder_rtsp", None)
            else:
                sys.modules["recorder_rtsp"] = previous
        self.assertEqual(rc, 0)
        self.assertIn(DISABLED_OUTPUT, out.getvalue())

    def test_default_source_type_is_hls(self) -> None:
        rec = load_recorder()
        with mock.patch.dict(
            os.environ,
            self._clean_env(
                SEA_SPEED_RECORDER_ENABLED="1",
                SEA_SPEED_RECORDER_HLS_URL="http://127.0.0.1:1/playlist.m3u8",
            ),
            clear=True,
        ):
            config = rec.RecorderConfig.from_env()
        self.assertEqual(config.source_type, "hls")
        self.assertEqual(config.hls_url, "http://127.0.0.1:1/playlist.m3u8")
        self.assertEqual(config.rtsp_url, "")

    def test_explicit_rtsp_reads_only_the_existing_hls_url(self) -> None:
        rec = load_recorder()
        with mock.patch.dict(
            os.environ,
            self._clean_env(
                SEA_SPEED_RECORDER_ENABLED="1",
                SEA_SPEED_RECORDER_SOURCE_TYPE="rtsp",
                HLS_URL=RELAY_URL,
                SEA_SPEED_RECORDER_HLS_URL="http://127.0.0.1:1/ignored.m3u8",
            ),
            clear=True,
        ):
            config = rec.RecorderConfig.from_env()
        self.assertEqual(config.source_type, "rtsp")
        self.assertEqual(config.rtsp_url, RELAY_URL)
        self.assertEqual(
            config.hls_url, "", "the rtsp arm must not read the HLS variable"
        )

    def test_rtsp_without_hls_url_fails_closed_without_fallback(self) -> None:
        rec = load_recorder()
        for hls_value in (None, ""):
            with self.subTest(hls_value=hls_value):
                env = self._clean_env(
                    SEA_SPEED_RECORDER_ENABLED="1",
                    SEA_SPEED_RECORDER_SOURCE_TYPE="rtsp",
                    SEA_SPEED_RECORDER_HLS_URL="http://127.0.0.1:1/playlist.m3u8",
                )
                if hls_value is not None:
                    env["HLS_URL"] = hls_value
                with mock.patch.dict(os.environ, env, clear=True):
                    with self.assertRaises(rec.RecorderError) as caught:
                        rec.RecorderConfig.from_env()
                self.assertIn(
                    "HLS_URL is required when SEA_SPEED_RECORDER_SOURCE_TYPE=rtsp",
                    str(caught.exception),
                )

    def test_selector_rejects_unknown_values(self) -> None:
        rec = load_recorder()
        with mock.patch.dict(
            os.environ,
            self._clean_env(
                SEA_SPEED_RECORDER_ENABLED="1",
                SEA_SPEED_RECORDER_SOURCE_TYPE="udp",
                HLS_URL=RELAY_URL,
            ),
            clear=True,
        ):
            with self.assertRaises(rec.RecorderError) as caught:
                rec.RecorderConfig.from_env()
        self.assertIn(
            "SEA_SPEED_RECORDER_SOURCE_TYPE must be hls or rtsp",
            str(caught.exception),
        )

    def test_validate_source_requires_absolute_rtsp_url_with_host(self) -> None:
        rtsp = load_recorder_rtsp()
        rec = load_recorder()
        rtsp.validate_source(RELAY_URL)  # accepted
        rtsp.validate_source("rtsp://10.0.0.5:554/stream1")  # accepted
        rejections = (
            ("", "recorder RTSP source is required (HLS_URL)"),
            ("rtsp://", "must be an absolute rtsp:// URL with a host"),
            ("http://cam.example/stream", "must be an absolute rtsp:// URL with a host"),
            ("/relative/path", "must be an absolute rtsp:// URL with a host"),
            ("rtsp://cam.example/stream\nX", "contains control characters"),
            ("rtsp://cam.example/stream\x07", "contains control characters"),
        )
        for url, message in rejections:
            with self.subTest(url=url):
                with self.assertRaises(rec.RecorderError) as caught:
                    rtsp.validate_source(url)
                self.assertIn(message, str(caught.exception))

    def test_invalid_rtsp_url_disables_recorder_with_rc2(self) -> None:
        never_spool = self.tmp / "never-created-spool"
        env = self.child_env(
            SEA_SPEED_RECORDER_ENABLED="1",
            SEA_SPEED_RECORDER_SOURCE_TYPE="rtsp",
            SEA_SPEED_RECORDER_SPOOL_DIR=str(never_spool),
            HLS_URL="http://127.0.0.1:1/stream",  # not an rtsp:// URL
        )
        proc = self.spawn_recorder(env)
        out, _ = proc.communicate(timeout=20)
        out = out or ""

        self.assertEqual(proc.returncode, 2, out)
        self.assertIn("recorder disabled runtime_error=", out)
        self.assertIn("must be an absolute rtsp:// URL with a host", out)
        self.assertNotIn("Traceback", out)
        self.assertFalse(
            never_spool.exists(), "no spool before source validation passes"
        )
        self.assertEqual(self.rsync_calls(), [])
        self.assertFalse(self.ffmpeg_log.exists())


# ---------------------------------------------------------------------------
# 3. Transport (spec R-4/R-7, "Transport caveat")
# ---------------------------------------------------------------------------


class RtspTransportTests(RtspRecorderTestBase):
    def test_relay_argv_is_the_exact_production_stream_copy_segment_argv(
        self,
    ) -> None:
        rtsp = load_recorder_rtsp()
        session = Path("/spool/cam1-rtsp-20260101T000000Z-4242")
        argv = rtsp.build_ffmpeg_args(self.make_config(), session, None)
        self.assertEqual(argv, expected_relay_argv(session))

    def test_direct_camera_argv_uses_ffconcat_and_keeps_the_output_tail(
        self,
    ) -> None:
        rtsp = load_recorder_rtsp()
        session = Path("/spool/cam1-rtsp-20260101T000000Z-4242")
        ffconcat = Path("/tmp/sea-speed-recorder-rtsp-test.ffconcat")
        direct = rtsp.build_ffmpeg_args(self.make_config(), session, ffconcat)
        relay = rtsp.build_ffmpeg_args(self.make_config(), session, None)
        self.assertEqual(
            direct[:7],
            ["ffmpeg", "-hide_banner", "-nostdin", "-nostats", "-loglevel", "error", "-xerror"],
        )
        self.assertEqual(
            direct[7:15],
            [
                "-f",
                "concat",
                "-safe",
                "0",
                "-protocol_whitelist",
                "file,rtsp,tcp,udp,rtp",
                "-i",
                str(ffconcat),
            ],
        )
        self.assertEqual(
            direct[15:],
            relay[RELAY_TAIL_INDEX:],
            "the output argv must be identical for both source arms",
        )

    def test_ffconcat_manifest_is_0600_in_private_temp_with_literal_content(
        self,
    ) -> None:
        rtsp = load_recorder_rtsp()
        path = rtsp.write_ffconcat(DIRECT_URL, "udp")
        self.addCleanup(path.unlink, True)
        self.assertEqual(
            path.read_text(encoding="utf-8"),
            f"ffconcat version 1.0\nfile '{DIRECT_URL}'\n"
            "option rtsp_transport udp\n",
        )
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent, Path(tempfile.gettempdir()))
        self.assertNotIn(self.spool_dir, path.parents)

    def test_ffconcat_url_rejects_quotes_and_backslashes(self) -> None:
        rtsp = load_recorder_rtsp()
        rec = load_recorder()
        for bad in ("rtsp://cam.example/'stream", "rtsp://cam.example\\stream"):
            with self.subTest(url=bad):
                with self.assertRaises(rec.RecorderError) as caught:
                    rtsp.write_ffconcat(bad, "udp")
                self.assertIn("unsupported by ffconcat", str(caught.exception))

    def test_transport_resolution_matrix(self) -> None:
        rtsp = load_recorder_rtsp()
        rec = load_recorder()
        with mock.patch.dict(os.environ):
            # Credential-free relay: always tcp, the camera env never applies.
            os.environ["CAMERA1_RTSP_TRANSPORT"] = "udp"
            self.assertEqual(rtsp.rtsp_transport(RELAY_URL), "tcp")
            # Direct camera: udp default (TCP never forced), env overrides.
            os.environ.pop("CAMERA1_RTSP_TRANSPORT", None)
            self.assertEqual(rtsp.rtsp_transport(DIRECT_URL), "udp")
            os.environ["CAMERA1_RTSP_TRANSPORT"] = ""
            self.assertEqual(rtsp.rtsp_transport(DIRECT_URL), "udp")
            os.environ["CAMERA1_RTSP_TRANSPORT"] = "tcp"
            self.assertEqual(rtsp.rtsp_transport(DIRECT_URL), "tcp")
            os.environ["CAMERA1_RTSP_TRANSPORT"] = "automatic"
            self.assertEqual(rtsp.rtsp_transport(DIRECT_URL), "automatic")
            os.environ["CAMERA1_RTSP_TRANSPORT"] = "bogus"
            with self.assertRaises(rec.RecorderError) as caught:
                rtsp.rtsp_transport(DIRECT_URL)
            self.assertIn(
                "CAMERA1_RTSP_TRANSPORT must be one of: udp, tcp, automatic",
                str(caught.exception),
            )

    def test_direct_manifest_removed_and_argv_carries_no_credential(self) -> None:
        rtsp = load_recorder_rtsp()
        with mock.patch.dict(os.environ):
            os.environ.pop("CAMERA1_RTSP_TRANSPORT", None)
            config = self.make_config(rtsp_url=CANARY_URL)
            instance = rtsp.RtspRecorder(config)
        self.assertTrue(instance.direct)
        self.assertEqual(
            instance.transport,
            "udp",
            "TCP must never be forced for the direct camera (461 rejection)",
        )
        instance.session_dir.mkdir(mode=0o700)
        captured: dict = {}

        def spawn(argv, **kwargs):
            manifest = Path(argv[argv.index("-i") + 1])
            captured["manifest"] = manifest
            captured["exists"] = manifest.is_file()
            captured["mode"] = manifest.stat().st_mode & 0o777
            captured["in_spool"] = self.spool_dir in manifest.parents
            captured["argv"] = list(argv)
            return mock.Mock(poll=mock.Mock(return_value=0))

        with mock.patch.object(rtsp.subprocess, "Popen", side_effect=spawn):
            clean = instance._capture_session()
        self.assertTrue(clean)
        manifest = captured["manifest"]
        self.assertTrue(captured["exists"], "the ffconcat must exist at spawn")
        self.assertEqual(captured["mode"], 0o600)
        self.assertFalse(captured["in_spool"], "the manifest must never be in the spool")
        self.assertEqual(manifest.parent, Path(tempfile.gettempdir()))
        self.assertFalse(manifest.exists(), "the manifest must be removed on cleanup")
        for element in captured["argv"]:
            self.assertNotIn(CANARY_SECRET, element)
            self.assertNotIn(CANARY_USER, element)

    def test_credential_never_appears_in_recorder_logs(self) -> None:
        rtsp = load_recorder_rtsp()
        with mock.patch.dict(os.environ):
            os.environ.pop("CAMERA1_RTSP_TRANSPORT", None)
            config = self.make_config(rtsp_url=CANARY_URL)
            instance = rtsp.RtspRecorder(config)
        instance._capture_session = mock.Mock(side_effect=_StopAfterStart())
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            with self.assertRaises(_StopAfterStart):
                instance.run()
        log = out.getvalue()
        self.assertIn("recorder rtsp start", log)
        self.assertIn(CANARY_LABEL, log, "only scheme/host may be logged")
        self.assertNotIn(CANARY_SECRET, log)
        self.assertNotIn(CANARY_USER, log)
        self.assertEqual(list(self.spool_dir.iterdir()), [], "session cleaned")

    def test_credential_never_appears_in_uploaded_metadata(self) -> None:
        rtsp = load_recorder_rtsp()
        with mock.patch.dict(os.environ):
            os.environ.pop("CAMERA1_RTSP_TRANSPORT", None)
            config = self.make_config(rtsp_url=CANARY_URL)
            instance = rtsp.RtspRecorder(config)
        instance.session_dir.mkdir(mode=0o700)
        self._plant_part(instance, 0, b"matroska-object-bytes")
        instance._finalize(0)
        self.assertEqual(instance.captured_count, 1)
        delivered = sorted(path.name for path in self.dest_dir.iterdir())
        self.assertEqual(len(delivered), 1)
        self.assertNotIn(CANARY_SECRET, delivered[0])
        self.assertNotIn(CANARY_USER, delivered[0])
        log = self.rsync_log.read_text()
        self.assertNotIn(CANARY_SECRET, log)
        self.assertNotIn(CANARY_USER, log)
        self.assertEqual(log.strip(), delivered[0])


# ---------------------------------------------------------------------------
# 4. Bounds / failure (spec R-5..R-9)
# ---------------------------------------------------------------------------


class RtspBoundsFailureTests(RtspRecorderTestBase):
    def test_bounds_literals_are_pinned(self) -> None:
        rtsp = load_recorder_rtsp()
        rec = load_recorder()
        self.assertEqual(rtsp._NO_SEGMENT_DEADLINE_SEC, NO_SEGMENT_DEADLINE_SEC)
        self.assertEqual(rtsp._SLOT_COUNT, SLOT_COUNT)
        self.assertEqual(rtsp._SEGMENT_SECONDS, SEGMENT_SECONDS)
        config = rec.RecorderConfig()
        self.assertEqual(config.object_max_bytes, DEFAULT_OBJECT_MAX_BYTES)
        self.assertEqual(config.min_free_bytes, DEFAULT_MIN_FREE_BYTES)
        instance = rtsp.RtspRecorder(self.make_config())
        self.assertEqual(
            instance.media_max_bytes,
            SLOT_COUNT * DEFAULT_OBJECT_MAX_BYTES,
            "the spool holds at most two objects per camera",
        )

    def test_no_segment_deadline_terminates_stalled_ffmpeg_and_counts_a_gap(
        self,
    ) -> None:
        rtsp = load_recorder_rtsp()
        instance = self._fresh_instance(self.make_config())
        children: list = []
        real_popen = subprocess.Popen

        def spawn(argv, **kwargs):
            if argv[0] != "ffmpeg":
                return real_popen(argv, **kwargs)
            child = real_popen(
                [sys.executable, "-c", "import time; time.sleep(300)"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            children.append(child)
            return child

        out = io.StringIO()
        started = time.monotonic()
        with mock.patch.object(rtsp, "_NO_SEGMENT_DEADLINE_SEC", 1.0):
            with mock.patch.object(rtsp.subprocess, "Popen", side_effect=spawn):
                with contextlib.redirect_stdout(out):
                    clean = instance._capture_session()
        elapsed = time.monotonic() - started

        self.assertFalse(clean)
        self.assertEqual(instance.gap_count, 1)
        self.assertIn("deadline no segment", out.getvalue())
        self.assertLess(elapsed, 8.0, "the deadline must bound the stall")
        self.assertIsNotNone(children[0].poll(), "ffmpeg must be terminated+reaped")

    def test_ffmpeg_spawn_is_devnull_in_the_recorder_process_group(self) -> None:
        rtsp = load_recorder_rtsp()
        instance = self._fresh_instance(self.make_config())
        captured_kwargs: list[dict] = []
        pgids: list[int] = []
        real_popen = subprocess.Popen

        def spawn(argv, **kwargs):
            if argv[0] != "ffmpeg":
                return real_popen(argv, **kwargs)
            captured_kwargs.append(dict(kwargs))
            child = real_popen(
                [sys.executable, "-c", "import time; time.sleep(300)"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            pgids.append(os.getpgid(child.pid))
            return child

        with mock.patch.object(rtsp, "_NO_SEGMENT_DEADLINE_SEC", 1.0):
            with mock.patch.object(rtsp.subprocess, "Popen", side_effect=spawn):
                instance._capture_session()

        kwargs = captured_kwargs[0]
        self.assertIs(kwargs.get("stdin"), subprocess.DEVNULL)
        self.assertIs(kwargs.get("stdout"), subprocess.DEVNULL)
        self.assertIs(kwargs.get("stderr"), subprocess.DEVNULL)
        self.assertTrue(kwargs.get("close_fds"))
        self.assertFalse(
            kwargs.get("start_new_session"),
            "ffmpeg must stay in the recorder's process group (killpg reaches it)",
        )
        self.assertEqual(pgids[0], os.getpgid(0))

    def test_rlimit_fsize_is_applied_to_the_ffmpeg_child_only(self) -> None:
        rtsp = load_recorder_rtsp()
        instance = self._fresh_instance(self.make_config())
        captured: dict = {}
        real_popen = subprocess.Popen

        def spawn(argv, **kwargs):
            if argv[0] != "ffmpeg":
                return real_popen(argv, **kwargs)
            captured.update(kwargs)
            return mock.Mock(poll=mock.Mock(return_value=0))

        before = resource.getrlimit(resource.RLIMIT_FSIZE)
        with mock.patch.object(rtsp.subprocess, "Popen", side_effect=spawn):
            clean = instance._capture_session()
        after = resource.getrlimit(resource.RLIMIT_FSIZE)
        self.assertTrue(clean)
        self.assertEqual(
            before, after, "the recorder process itself must not be limited"
        )
        limiter = captured.get("preexec_fn")
        self.assertTrue(callable(limiter), "the ffmpeg child must get a limiter")
        probe = subprocess.run(
            [
                sys.executable,
                "-c",
                "import resource; print(resource.getrlimit(resource.RLIMIT_FSIZE))",
            ],
            capture_output=True,
            text=True,
            preexec_fn=limiter,
        )
        self.assertEqual(
            probe.stdout.strip(),
            f"({DEFAULT_OBJECT_MAX_BYTES}, {DEFAULT_OBJECT_MAX_BYTES})",
        )
        # The shared rsync child keeps the default unbounded fsize.
        os.environ["FAKE_RSYNC_RLIMIT"] = str(self.rsync_rlimit)
        self._plant_part(instance, 0, b"bounded-object-bytes")
        instance._finalize(0)
        recorded = self.rsync_rlimit.read_text().strip()
        self.assertEqual(
            recorded,
            repr((resource.RLIM_INFINITY, resource.RLIM_INFINITY)),
            f"rsync must not inherit the ffmpeg fsize cap, got {recorded}",
        )

    def test_object_cap_covers_the_whole_object_including_trailer(self) -> None:
        instance = self._fresh_instance(self.make_config(object_max_bytes=4096))
        out = io.StringIO()
        # Boundary: exactly at the cap — the completed object (trailer
        # included in st_size) is delivered.
        at_cap = self._plant_part(instance, 0, b"A" * 4092 + b"\x1a\x45\xdf\xa3")
        with contextlib.redirect_stdout(out):
            instance._finalize(0)
        self.assertEqual(instance.captured_count, 1)
        self.assertEqual(instance.gap_count, 0)
        self.assertFalse(at_cap.exists(), "the spool object is deleted after upload")
        # One byte over the cap (the trailer pushes it past) — discarded.
        over_cap = self._plant_part(instance, 1, b"B" * 4097)
        with contextlib.redirect_stdout(out):
            instance._finalize(1)
        self.assertEqual(instance.captured_count, 1)
        self.assertEqual(instance.gap_count, 1)
        self.assertFalse(over_cap.exists(), "an over-cap object must be discarded")
        self.assertEqual(len(list(self.dest_dir.iterdir())), 1)
        self.assertIn("reason=size", out.getvalue())

    def test_free_space_floor_discards_the_object_before_upload(self) -> None:
        rec = load_recorder()
        free = shutil.disk_usage(self.spool_dir).free
        instance = self._fresh_instance(
            self.make_config(min_free_bytes=free + 1)
        )
        part = self._plant_part(instance, 0, b"floor-object-bytes")
        with self.assertRaises(rec.SpoolSpaceLow):
            instance._finalize(0)
        self.assertFalse(part.exists())
        self.assertEqual(instance.gap_count, 1)
        self.assertEqual(
            self.rsync_calls(), [], "the floor must stop before any upload"
        )

    def test_two_slot_media_cap_terminates_ffmpeg_and_counts_a_gap(self) -> None:
        rtsp = load_recorder_rtsp()
        instance = self._fresh_instance(self.make_config(object_max_bytes=1024))
        children: list = []
        real_popen = subprocess.Popen

        def spawn(argv, **kwargs):
            if argv[0] != "ffmpeg":
                return real_popen(argv, **kwargs)
            # Plant two objects totalling more than the two-slot cap AFTER
            # the session reset, then keep a live ffmpeg stand-in.
            directory0 = instance.session_dir / "000000000"
            directory2 = instance.session_dir / "000000002"
            directory0.mkdir(parents=True, exist_ok=True)
            directory2.mkdir(parents=True, exist_ok=True)
            (directory0 / "clip.mkv.part").write_bytes(b"A" * 1500)
            (directory2 / "clip.mkv.part").write_bytes(b"B" * 1500)
            child = real_popen(
                [sys.executable, "-c", "import time; time.sleep(300)"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            children.append(child)
            return child

        out = io.StringIO()
        with mock.patch.object(rtsp.subprocess, "Popen", side_effect=spawn):
            with contextlib.redirect_stdout(out):
                clean = instance._capture_session()

        self.assertFalse(clean)
        self.assertEqual(instance.gap_count, 1)
        self.assertIn("media cap exceeded", out.getvalue())
        self.assertIn(f"cap={SLOT_COUNT * 1024}", out.getvalue())
        self.assertIsNotNone(children[0].poll(), "ffmpeg must be terminated")

    def test_rollover_witness_finalizes_closed_object_and_discards_open_tail(
        self,
    ) -> None:
        rtsp = load_recorder_rtsp()
        instance = self._fresh_instance(self.make_config())
        real_popen = subprocess.Popen

        def spawn(argv, **kwargs):
            if argv[0] != "ffmpeg":
                return real_popen(argv, **kwargs)
            # Segment 0 is closed (its successor exists = completion witness);
            # segment 1 is still open when ffmpeg dies with rc=7.
            directory0 = instance.session_dir / "000000000"
            directory1 = instance.session_dir / "000000001"
            directory0.mkdir(parents=True, exist_ok=True)
            directory1.mkdir(parents=True, exist_ok=True)
            (directory0 / "clip.mkv.part").write_bytes(b"closed-segment-bytes")
            (directory1 / "clip.mkv.part").write_bytes(b"open-tail-bytes")
            return real_popen(
                [
                    sys.executable,
                    "-c",
                    "import time, sys; time.sleep(0.6); sys.exit(7)",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

        out = io.StringIO()
        with mock.patch.object(rtsp.subprocess, "Popen", side_effect=spawn):
            with contextlib.redirect_stdout(out):
                clean = instance._capture_session()

        self.assertFalse(clean)
        self.assertEqual(instance.captured_count, 1, "witnessed object delivered")
        self.assertEqual(instance.gap_count, 1, "open tail discarded as a gap")
        delivered = sorted(path.name for path in self.dest_dir.iterdir())
        self.assertEqual(len(delivered), 1, "the open tail must never be delivered")
        self.assertIn("ffmpeg exit rc=7", out.getvalue())

    def test_missing_spool_directory_fails_closed(self) -> None:
        rtsp = load_recorder_rtsp()
        rec = load_recorder()
        config = self.make_config(spool_dir=self.tmp / "no-such-spool")
        instance = rtsp.RtspRecorder(config)
        with self.assertRaises(rec.RecorderError) as caught:
            instance.run()
        self.assertIn("recorder spool directory missing", str(caught.exception))

    def test_missing_session_parent_fails_closed(self) -> None:
        instance = self._fresh_instance(self.make_config())
        shutil.rmtree(instance.session_dir)
        with self.assertRaises(OSError):
            instance._ensure_dir(0)
        self.assertFalse(
            instance.session_dir.exists(),
            "a missing parent chain must never be silently recreated",
        )

    def test_stalled_rsync_is_bounded_and_counts_a_gap(self) -> None:
        self.set_rsync_mode("hang")
        instance = self._fresh_instance(
            self.make_config(rsync_retries=1, rsync_timeout_sec=1.0)
        )
        self._plant_part(instance, 0, b"stalled-object-bytes")
        out = io.StringIO()
        started = time.monotonic()
        with contextlib.redirect_stdout(out):
            instance._finalize(0)
        elapsed = time.monotonic() - started

        self.assertEqual(instance.captured_count, 0)
        self.assertEqual(instance.gap_count, 1)
        self.assertIn("reason=upload_failed", out.getvalue())
        self.assertIn("rsync timeout", out.getvalue())
        self.assertLess(elapsed, 12.0, "the stalled rsync must be killed")
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

    def test_failing_rsync_burns_retry_budget_counts_gap_and_resumes(self) -> None:
        self.set_rsync_mode("fail")
        instance = self._fresh_instance(
            self.make_config(rsync_retries=3, rsync_backoff_sec=0.0)
        )
        self._plant_part(instance, 0, b"first-object-bytes")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            instance._finalize(0)
        self.assertEqual(len(self.rsync_calls()), 3, "exact retry budget")
        self.assertEqual(instance.captured_count, 0)
        self.assertEqual(instance.gap_count, 1)
        self.assertIn("reason=upload_failed", out.getvalue())

        # Receiver recovers; the next object is delivered, gaps stay counted.
        self.set_rsync_mode("ok")
        self._plant_part(instance, 1, b"second-object-bytes")
        with contextlib.redirect_stdout(out):
            instance._finalize(1)
        self.assertEqual(instance.captured_count, 1)
        self.assertEqual(instance.gap_count, 1, "resume must not erase gaps")
        self.assertEqual(len(list(self.dest_dir.iterdir())), 1)

    def test_crash_cleanup_terminates_child_and_removes_manifest_and_session(
        self,
    ) -> None:
        rtsp = load_recorder_rtsp()
        with mock.patch.dict(os.environ):
            os.environ.pop("CAMERA1_RTSP_TRANSPORT", None)
            config = self.make_config(rtsp_url=CANARY_URL)
            instance = rtsp.RtspRecorder(config)
        instance.session_dir.mkdir(mode=0o700)
        (instance.session_dir / "leftover.txt").write_text("x", encoding="utf-8")
        manifest = rtsp.write_ffconcat(CANARY_URL, "udp")
        instance._ffconcat = manifest
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        instance._process = child

        instance._cleanup()

        self.assertIsNotNone(child.poll(), "the ffmpeg child must be reaped")
        self.assertFalse(manifest.exists(), "the ffconcat must be removed")
        self.assertFalse(instance.session_dir.exists(), "the session must be removed")

    def test_gap_and_outage_are_counted_separately(self) -> None:
        rtsp = load_recorder_rtsp()
        real_popen = subprocess.Popen

        # (a) Clean EOF with one over-cap object: a gap WITHOUT an outage.
        # run() creates the session directory itself — do not pre-create it.
        instance = rtsp.RtspRecorder(self.make_config(object_max_bytes=4096))

        def spawn_overcap(argv, **kwargs):
            if argv[0] != "ffmpeg":
                return real_popen(argv, **kwargs)
            directory0 = instance.session_dir / "000000000"
            directory0.mkdir(parents=True, exist_ok=True)
            (directory0 / "clip.mkv.part").write_bytes(b"X" * 4097)
            return mock.Mock(poll=mock.Mock(return_value=0))

        out = io.StringIO()
        with mock.patch.object(rtsp.subprocess, "Popen", side_effect=spawn_overcap):
            with contextlib.redirect_stdout(out):
                instance.run()
        self.assertEqual(instance.gap_count, 1, "the over-cap object is a gap")
        self.assertEqual(instance.outage_count, 0, "a clean cycle is not an outage")
        self.assertEqual(instance.captured_count, 0)
        self.assertIn("reason=size", out.getvalue())
        self.assertEqual(list(self.spool_dir.iterdir()), [], "session cleaned")

        # (b) A failed capture cycle: gap AND outage, counted independently.
        failed = rtsp.RtspRecorder(self.make_config())

        def spawn_failure(argv, **kwargs):
            if argv[0] != "ffmpeg":
                return real_popen(argv, **kwargs)
            return mock.Mock(poll=mock.Mock(return_value=7))

        out = io.StringIO()
        with mock.patch.object(rtsp.subprocess, "Popen", side_effect=spawn_failure):
            with mock.patch.object(
                rtsp.time, "sleep", side_effect=_StopAfterCycle
            ):
                with contextlib.redirect_stdout(out):
                    with self.assertRaises(_StopAfterCycle):
                        failed.run()
        self.assertEqual(failed.gap_count, 1, "the discarded attempt is a gap")
        self.assertEqual(failed.outage_count, 1, "the failed cycle is an outage")
        self.assertIn("ffmpeg exit rc=7", out.getvalue())


# ---------------------------------------------------------------------------
# 5. Ingest parity (baseline pattern from tests/test_699_recorder.py)
# ---------------------------------------------------------------------------


class RtspIngestParityTests(unittest.TestCase):
    FRAME_W = 16
    FRAME_H = 16
    FRAME_BYTES = bytes(
        (index * 31 + 7) % 256 for index in range(FRAME_W * FRAME_H * 3)
    )

    RECORDER_STATES = (
        ("unset", {"SEA_SPEED_RECORDER_ENABLED": None}),
        ("off", {"SEA_SPEED_RECORDER_ENABLED": "0"}),
        (
            "hls-on",
            {
                "SEA_SPEED_RECORDER_ENABLED": "1",
                "SEA_SPEED_RECORDER_SOURCE_TYPE": "hls",
                "SEA_SPEED_RECORDER_HLS_URL": "http://127.0.0.1:1/playlist.m3u8",
            },
        ),
        (
            "rtsp-failing",
            {"SEA_SPEED_RECORDER_ENABLED": "1", "SEA_SPEED_RECORDER_SOURCE_TYPE": "rtsp"},
        ),
        (
            "rtsp-ok",
            {
                "SEA_SPEED_RECORDER_ENABLED": "1",
                "SEA_SPEED_RECORDER_SOURCE_TYPE": "rtsp",
                "HLS_URL": "rtsp://192.0.2.10/stream",
            },
        ),
    )

    @staticmethod
    def _state_env(state: dict) -> dict:
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SEA_SPEED_RECORDER_") and key != "HLS_URL"
        }
        env.update({key: value for key, value in state.items() if value is not None})
        return env

    def _reader_argv(self, state: dict) -> list:
        """Capture the real ffmpeg argv the entrypoint would spawn."""
        entry = load_entrypoint()
        with mock.patch.dict(os.environ, self._state_env(state), clear=True):
            with mock.patch.object(entry.subprocess, "Popen") as popen:
                popen.return_value = mock.Mock(stderr=None)
                entry._spawn_rtsp_ffmpeg("rtsp://192.0.2.10/stream", 640, 360, 5.0)
        return list(popen.call_args[0][0])

    def test_reader_argv_identical_across_recorder_states(self) -> None:
        argvs = {
            name: self._reader_argv(state) for name, state in self.RECORDER_STATES
        }
        baseline = argvs["unset"]
        for name, argv in argvs.items():
            self.assertEqual(
                argv, baseline, f"recorder state {name} must not change reader args"
            )
        # Sanity: the captured argv really is the bounded ffmpeg reader.
        self.assertEqual(baseline[0], "ffmpeg")
        self.assertIn("-nostdin", baseline)
        self.assertIn("-rtsp_transport", baseline)

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

        with mock.patch.dict(os.environ, self._state_env(state), clear=True):
            with mock.patch.object(entry, "_spawn_rtsp_ffmpeg", side_effect=_fake_spawn):
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

    def test_frame_bytes_identical_across_recorder_states(self) -> None:
        bytes_by_state = {
            name: self._raw_frame_bytes(state)
            for name, state in self.RECORDER_STATES
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
                data, baseline, f"recorder state {name} must not change frame bytes"
            )


if __name__ == "__main__":
    unittest.main()
