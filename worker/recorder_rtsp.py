#!/usr/bin/env python3
"""Opt-in RTSP stream-copy recorder arm (issue #699b).

Extends the #699 recorder with an RTSP source. FFmpeg runs as a grandchild
inside the recorder's process group (the Ubuntu entrypoint spawns the recorder
with ``start_new_session=True``) and stream-copies the original encoded video
(``-c:v copy``) into 2-second segmented Matroska objects. Each object that is
provably complete is atomically renamed and delivered through the shared
bounded rsync operation. There is no decode, no re-encode and no RTP packet
capture: the ordered coded picture data is preserved, not the RTP wire bytes.

The module is imported lazily by ``worker/recorder.py`` only when
``SEA_SPEED_RECORDER_SOURCE_TYPE=rtsp``. Credential-free relay inputs are
passed on argv; a credential-bearing direct Camera 1 URL is written to a fresh
0600 ffconcat file in the private service tmp so the camera password never
appears in ``/proc/<pid>/cmdline`` or in logs. Direct Camera 1 transport
follows ``CAMERA1_RTSP_TRANSPORT`` (default udp; the camera rejects TCP SETUP
with 461 Unsupported Transport); credential-free relay reads always use tcp.
"""

from __future__ import annotations

import os
import re
import resource
import shutil
import subprocess
import tempfile
import time
import urllib.parse
from pathlib import Path

from worker_kernel import safe_media_input_label

from recorder import RecorderConfig, RecorderError, SpoolSpaceLow, bounded_upload

_SEGMENT_SECONDS = 2
_SEGMENT_FILENAME = "clip.mkv.part"
_SEGMENT_PATTERN = "%09d/" + _SEGMENT_FILENAME
_SEGMENT_DIR_RE = re.compile(r"^\d{9}$")
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
_SCAN_SEC = 0.2
_NO_SEGMENT_DEADLINE_SEC = 30.0
_TERMINATE_GRACE_SEC = 5.0
_MAX_BACKOFF_SEC = 30.0
_SLOT_COUNT = 2
_RTSP_TRANSPORTS = ("udp", "tcp", "automatic")
_FFMPEG = "ffmpeg"


def _is_credential_bearing(url: str) -> bool:
    """True when the RTSP URL authenticates against the physical camera directly."""
    try:
        return urllib.parse.urlsplit(url).username is not None
    except ValueError:
        return False


def validate_source(url: str) -> None:
    """Require an absolute rtsp:// URL with a host; reject control characters."""
    if not url:
        raise RecorderError("recorder RTSP source is required (HLS_URL)")
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in url):
        raise RecorderError("recorder RTSP source contains control characters")
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError as exc:
        raise RecorderError(f"invalid recorder RTSP source: {exc}") from None
    if parsed.scheme.lower() != "rtsp" or not parsed.hostname:
        raise RecorderError(
            "recorder RTSP source must be an absolute rtsp:// URL with a host"
        )


def rtsp_transport(url: str) -> str:
    """Resolve the RTSP transport with the existing Camera 1 semantics."""
    if not _is_credential_bearing(url):
        return "tcp"
    transport = os.environ.get("CAMERA1_RTSP_TRANSPORT", "udp").strip().lower() or "udp"
    if transport not in _RTSP_TRANSPORTS:
        raise RecorderError("CAMERA1_RTSP_TRANSPORT must be one of: udp, tcp, automatic")
    return transport


def _validate_ffconcat_url(url: str) -> None:
    """Reject characters the ffconcat ``file`` directive cannot carry safely."""
    if "'" in url or "\\" in url:
        raise RecorderError(
            "recorder RTSP source contains characters unsupported by ffconcat"
        )


def write_ffconcat(url: str, transport: str) -> Path:
    """Write a fresh 0600 ffconcat input file in the private service tmp.

    ``mkstemp`` creates the file 0600 in ``tempfile.gettempdir()`` (the
    systemd PrivateTmp tmpfs), never in the spool or at the ingest path. The
    ``option`` directive applies to the preceding ``file`` entry (concatdec
    NEEDS_FILE), so it follows the URL line.
    """
    _validate_ffconcat_url(url)
    fd, name = tempfile.mkstemp(prefix="sea-speed-recorder-rtsp-", suffix=".ffconcat")
    path = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("ffconcat version 1.0\n")
            handle.write(f"file '{url}'\n")
            handle.write(f"option rtsp_transport {transport}\n")
    except BaseException:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    return path


def build_ffmpeg_args(
    config: RecorderConfig, session_dir: Path, ffconcat_path: Path | None
) -> list[str]:
    """Build the exact stream-copy/segment argv for the RTSP arm."""
    head = [_FFMPEG, "-hide_banner", "-nostdin", "-nostats", "-loglevel", "error", "-xerror"]
    if ffconcat_path is not None:
        source = [
            "-f",
            "concat",
            "-safe",
            "0",
            "-protocol_whitelist",
            "file,rtsp,tcp,udp,rtp",
            "-i",
            str(ffconcat_path),
        ]
    else:
        source = [
            "-rtsp_transport",
            "tcp",
            "-timeout",
            "5000000",
            "-analyzeduration",
            "5000000",
            "-probesize",
            "5000000",
            "-i",
            config.rtsp_url,
        ]
    tail = [
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
        str(_SEGMENT_SECONDS),
        "-segment_format",
        "matroska",
        "-individual_header_trailer",
        "1",
        "-break_non_keyframes",
        "0",
        "-reset_timestamps",
        "1",
        str(session_dir / _SEGMENT_PATTERN),
    ]
    return head + source + tail


def _fsize_limiter(limit: int):
    """Apply RLIMIT_FSIZE to the ffmpeg child only (per-object bound)."""

    def _apply() -> None:
        try:
            resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
        except (ValueError, OSError):
            pass

    return _apply


def _terminate(process: subprocess.Popen) -> None:
    """Bounded SIGTERM/SIGKILL termination and reaping of the ffmpeg child."""
    if process.poll() is not None:
        return
    try:
        process.terminate()
    except OSError:
        pass
    try:
        process.wait(timeout=_TERMINATE_GRACE_SEC)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        process.kill()
    except OSError:
        pass
    try:
        process.wait(timeout=_TERMINATE_GRACE_SEC)
    except (subprocess.TimeoutExpired, OSError):
        pass


def _backoff(poll_sec: float, failures: int) -> float:
    base = poll_sec if poll_sec > 0 else 2.0
    return min(_MAX_BACKOFF_SEC, base * (2 ** min(max(failures - 1, 0), 4)))


class RtspRecorder:
    """One stream-copy recorder for one RTSP source."""

    def __init__(self, config: RecorderConfig) -> None:
        self.config = config
        self.source_url = config.rtsp_url
        validate_source(self.source_url)
        self.direct = _is_credential_bearing(self.source_url)
        if self.direct:
            _validate_ffconcat_url(self.source_url)
        self.transport = rtsp_transport(self.source_url)
        self.camera = _SAFE_NAME_RE.sub("_", config.camera_id).strip("._") or "cam1"
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        self.session_stamp = f"{stamp}-{os.getpid()}"
        self.session_dir = config.spool_dir / f"{self.camera}-rtsp-{self.session_stamp}"
        self.media_max_bytes = _SLOT_COUNT * config.object_max_bytes
        self.captured_count = 0
        self.gap_count = 0
        self.outage_count = 0
        self._sequence = 0
        self._process: subprocess.Popen | None = None
        self._ffconcat: Path | None = None

    # -- lifecycle ---------------------------------------------------------

    def run(self) -> None:
        config = self.config
        if not config.key_path.is_file() or not os.access(config.key_path, os.R_OK):
            raise RecorderError(
                f"recorder credential missing or unreadable at {config.key_path}"
            )
        if not config.spool_dir.is_dir():
            # Fail closed: the spool base is provisioned by the service, never
            # auto-created (directories below it are created per session).
            raise RecorderError(
                f"recorder spool directory missing: {config.spool_dir}"
            )
        self._prune_stale_parts()
        try:
            self.session_dir.mkdir(mode=0o700)
        except FileExistsError:
            raise RecorderError(
                f"recorder session directory already exists: {self.session_dir}"
            ) from None
        except FileNotFoundError:
            raise RecorderError(
                f"recorder spool parent missing: {config.spool_dir}"
            ) from None
        print(
            f"recorder rtsp start camera={config.camera_id} "
            f"source={safe_media_input_label(self.source_url)} "
            f"session={self.session_stamp} spool={self.session_dir} "
            f"destination={config.destination}",
            flush=True,
        )
        failures = 0
        try:
            while True:
                try:
                    clean = self._capture_session()
                except SpoolSpaceLow as exc:
                    failures += 1
                    self.outage_count += 1
                    print(
                        f"recorder rtsp spool space low reason={exc} "
                        f"outage={self.outage_count}",
                        flush=True,
                    )
                except (RecorderError, OSError) as exc:
                    failures += 1
                    self.outage_count += 1
                    print(
                        f"recorder rtsp outage reason={type(exc).__name__} "
                        f"detail={str(exc)[:200] or 'none'} outage={self.outage_count}",
                        flush=True,
                    )
                else:
                    if clean:
                        break
                    failures += 1
                    self.outage_count += 1
                time.sleep(_backoff(config.poll_sec, failures))
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        process = self._process
        self._process = None
        if process is not None:
            _terminate(process)
        if self._ffconcat is not None:
            try:
                self._ffconcat.unlink(missing_ok=True)
            except OSError:
                pass
            self._ffconcat = None
        shutil.rmtree(self.session_dir, ignore_errors=True)

    # -- one ffmpeg attempt ------------------------------------------------

    def _capture_session(self) -> bool:
        self._reset_segments()
        self._ffconcat = (
            write_ffconcat(self.source_url, self.transport) if self.direct else None
        )
        process: subprocess.Popen | None = None
        try:
            argv = build_ffmpeg_args(self.config, self.session_dir, self._ffconcat)
            try:
                process = subprocess.Popen(
                    argv,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                    preexec_fn=_fsize_limiter(self.config.object_max_bytes),
                )
            except FileNotFoundError as exc:
                raise RecorderError(f"ffmpeg unavailable: {exc}") from None
            self._process = process
            return self._monitor(process)
        finally:
            self._process = None
            if process is not None:
                _terminate(process)
            if self._ffconcat is not None:
                try:
                    self._ffconcat.unlink(missing_ok=True)
                except OSError:
                    pass
                self._ffconcat = None

    def _monitor(self, process: subprocess.Popen) -> bool:
        pending = 0
        last_completed = time.monotonic()
        while True:
            next_part = self.session_dir / f"{pending + 1:09d}" / _SEGMENT_FILENAME
            if next_part.is_file():
                # Rollover witness: the NEXT segment's file exists, so the
                # current one was closed with its Matroska trailer.
                self._ensure_dir(pending + 2)
                self._finalize(pending)
                pending += 1
                last_completed = time.monotonic()
                continue
            returncode = process.poll()
            if returncode is not None:
                if returncode == 0:
                    # Clean EOF (fixture): the final segment is complete.
                    self._finalize(pending)
                    return True
                self._discard(pending)
                self.gap_count += 1
                print(
                    f"recorder rtsp ffmpeg exit rc={returncode} "
                    f"discarded={self.gap_count}",
                    flush=True,
                )
                return False
            if time.monotonic() - last_completed > _NO_SEGMENT_DEADLINE_SEC:
                _terminate(process)
                self._discard(pending)
                self.gap_count += 1
                print(
                    f"recorder rtsp deadline no segment for "
                    f"{int(_NO_SEGMENT_DEADLINE_SEC)}s discarded={self.gap_count}",
                    flush=True,
                )
                return False
            local_bytes = self._local_media_bytes()
            if local_bytes > self.media_max_bytes:
                _terminate(process)
                self._discard(pending)
                self.gap_count += 1
                print(
                    f"recorder rtsp media cap exceeded bytes={local_bytes} "
                    f"cap={self.media_max_bytes} discarded={self.gap_count}",
                    flush=True,
                )
                return False
            time.sleep(_SCAN_SEC)

    # -- objects -----------------------------------------------------------

    def _reset_segments(self) -> None:
        if not self.session_dir.is_dir():
            raise RecorderError(
                f"recorder session directory missing: {self.session_dir}"
            )
        for child in self.session_dir.iterdir():
            if child.is_dir() and _SEGMENT_DIR_RE.fullmatch(child.name):
                shutil.rmtree(child, ignore_errors=True)
        self._ensure_dir(0)
        self._ensure_dir(1)

    def _ensure_dir(self, index: int) -> Path:
        path = self.session_dir / f"{index:09d}"
        if path.is_dir():
            return path
        # No parents: if the session directory vanished, fail closed instead of
        # silently recreating a missing parent chain.
        path.mkdir(mode=0o700)
        return path

    def _finalize(self, index: int) -> None:
        directory = self.session_dir / f"{index:09d}"
        part = directory / _SEGMENT_FILENAME
        if not part.is_file():
            return
        try:
            size = part.stat().st_size
        except OSError:
            return
        if size <= 0 or size > self.config.object_max_bytes:
            self._unlink(part)
            self.gap_count += 1
            print(
                f"recorder rtsp segment discarded index={index:09d} "
                f"reason=size bytes={size}",
                flush=True,
            )
            return
        try:
            free = shutil.disk_usage(self.config.spool_dir).free
        except OSError as exc:
            self._unlink(part)
            self.gap_count += 1
            raise SpoolSpaceLow(f"free space unknown: {exc}") from None
        if free < self.config.min_free_bytes:
            self._unlink(part)
            self.gap_count += 1
            raise SpoolSpaceLow(f"free={free} floor={self.config.min_free_bytes}")
        self._sequence += 1
        name = f"{self.camera}-{self.session_stamp}-{self._sequence:012d}.mkv"
        final = directory / name
        os.replace(part, final)
        ok, detail = bounded_upload(self.config, final)
        self._unlink(final)
        if ok:
            self.captured_count += 1
            print(f"recorder rtsp segment ok name={name} bytes={size}", flush=True)
        else:
            self.gap_count += 1
            print(
                f"recorder rtsp segment discarded name={name} "
                f"reason=upload_failed detail={detail or 'none'}",
                flush=True,
            )

    def _discard(self, index: int) -> None:
        self._unlink(self.session_dir / f"{index:09d}" / _SEGMENT_FILENAME)

    @staticmethod
    def _unlink(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    def _local_media_bytes(self) -> int:
        total = 0
        try:
            for child in self.session_dir.iterdir():
                if not (child.is_dir() and _SEGMENT_DIR_RE.fullmatch(child.name)):
                    continue
                for entry in child.iterdir():
                    try:
                        total += entry.stat().st_size
                    except OSError:
                        pass
        except OSError:
            return 0
        return total

    def _prune_stale_parts(self) -> None:
        # A crashed prior run can leave at most a couple of bounded .part
        # files inside its own session directories. The spool is single-writer
        # per service, so removing them here is safe.
        for session in self.config.spool_dir.glob("*-rtsp-*"):
            if not session.is_dir():
                continue
            for part in session.glob("*/" + _SEGMENT_FILENAME):
                self._unlink(part)
