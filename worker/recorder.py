#!/usr/bin/env python3
"""Opt-in recorder of ORIGINAL encoded HLS segments (issue #699).

The recorder is a separate child process of the Ubuntu worker entrypoint. It
fetches the playlist named by ``SEA_SPEED_RECORDER_HLS_URL``, downloads every
playlist-referenced media segment (and the ``#EXT-X-MAP`` init object) as
ORIGINAL BYTES, spools one object at a time and rsyncs it to the provisioned
dacha destination through the restricted ``rrsync`` endpoint. There is no
ffmpeg remux, no decoded frame and no RTSP packet capture.

Default OFF. Every failure is contained: a missing URL/key, a broken spool or
a failed rsync only disables or gaps the recording; the main worker ingest is a
different process and is never piped, waited on or backpressured from here.
"""

from __future__ import annotations

import hashlib
import http.client
import math
import os
import re
import shlex
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from pathlib import Path

from worker_kernel import env_float, env_int, env_str, media_basic_auth_for_input, safe_media_input_label

DEFAULT_DESTINATION = "root@10.123.239.127:/mnt/fleet-backup/sea-speed/"
DEFAULT_CREDENTIAL_PATH = Path("/run/credentials/recorder_ed25519")
_USER_AGENT = "sea-speed-recorder/1 (issue #699)"
_CHUNK_BYTES = 1024 * 1024
_PLAYLIST_MAX_BYTES = 4 * 1024 * 1024
_URI_RE = re.compile(r'URI="([^"]+)"')
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")

_ACTIVE_RSYNC: subprocess.Popen | None = None


class RecorderError(RuntimeError):
    """A bounded recorder configuration/runtime failure."""


class SpoolSpaceLow(RecorderError):
    """The local spool filesystem is below the configured free-space floor."""


class RecorderConfig:
    """Recorder settings read once from the service environment."""

    def __init__(self) -> None:
        self.enabled = False
        self.hls_url = ""
        self.camera_id = "cam1"
        self.spool_dir = Path("recorder-spool")
        self.destination = DEFAULT_DESTINATION
        self.key_path = DEFAULT_CREDENTIAL_PATH
        self.poll_sec = 2.0
        self.object_max_bytes = 64 * 1024 * 1024
        self.min_free_bytes = 12 * 1024 * 1024 * 1024
        self.http_timeout_sec = 30.0
        self.rsync_timeout_sec = 60.0
        self.rsync_retries = 3
        self.rsync_backoff_sec = 5.0

    @classmethod
    def from_env(cls) -> "RecorderConfig":
        raw_enabled = os.environ.get("SEA_SPEED_RECORDER_ENABLED", "0").strip()
        if raw_enabled not in {"0", "1"}:
            raise RecorderError("SEA_SPEED_RECORDER_ENABLED must be 0 or 1")
        config = cls()
        config.enabled = raw_enabled == "1"
        if not config.enabled:
            return config

        hls_url = env_str("SEA_SPEED_RECORDER_HLS_URL", "").strip()
        if not hls_url:
            raise RecorderError("SEA_SPEED_RECORDER_HLS_URL is required when the recorder is enabled")
        _origin(hls_url)  # raises RecorderError for RTSP/relative sources
        config.hls_url = hls_url
        config.camera_id = env_str("CAMERA_ID", "cam1").strip() or "cam1"
        config.spool_dir = Path(
            env_str("SEA_SPEED_RECORDER_SPOOL_DIR", "recorder-spool").strip() or "recorder-spool"
        )
        config.destination = _directory_destination(
            env_str("SEA_SPEED_RECORDER_DESTINATION", DEFAULT_DESTINATION)
        )
        config.key_path = _credential_path()
        config.poll_sec = _bounded_float("SEA_SPEED_RECORDER_POLL_SEC", 2.0, 0.5, 30.0)
        config.object_max_bytes = _bounded_int(
            "SEA_SPEED_RECORDER_OBJECT_MAX_BYTES", 64 * 1024 * 1024, 1024 * 1024, 512 * 1024 * 1024
        )
        config.min_free_bytes = _bounded_int(
            "SEA_SPEED_RECORDER_MIN_FREE_BYTES", 12 * 1024 * 1024 * 1024, 0, 1024 * 1024 * 1024 * 1024
        )
        config.http_timeout_sec = _bounded_float(
            "SEA_SPEED_RECORDER_HTTP_TIMEOUT_SEC", 30.0, 1.0, 600.0
        )
        config.rsync_timeout_sec = _bounded_float(
            "SEA_SPEED_RECORDER_RSYNC_TIMEOUT_SEC", 60.0, 1.0, 3600.0
        )
        config.rsync_retries = _bounded_int("SEA_SPEED_RECORDER_RSYNC_RETRIES", 3, 1, 20)
        config.rsync_backoff_sec = _bounded_float(
            "SEA_SPEED_RECORDER_RSYNC_BACKOFF_SEC", 5.0, 0.0, 300.0
        )
        return config


def _bounded_float(name: str, default: float, low: float, high: float) -> float:
    value = env_float(name, default)
    if not math.isfinite(value):
        value = default
    return min(high, max(low, value))


def _bounded_int(name: str, default: int, low: int, high: int) -> int:
    value = env_int(name, default)
    return min(high, max(low, value))


def _credential_path() -> Path:
    """Resolve the LoadCredential key, never from /home.

    systemd exposes ``LoadCredential`` through ``$CREDENTIALS_DIRECTORY``. The
    work-order path is also accepted directly so a hand-provisioned unit keeps
    working. The first existing readable candidate wins.
    """
    candidates: list[Path] = []
    directory = os.environ.get("CREDENTIALS_DIRECTORY", "").strip()
    if directory:
        candidates.append(Path(directory) / "recorder_ed25519")
    candidates.append(DEFAULT_CREDENTIAL_PATH)
    for candidate in candidates:
        if candidate.is_file() and os.access(candidate, os.R_OK):
            return candidate
    return candidates[0]


def _directory_destination(value: str) -> str:
    value = value.strip() or DEFAULT_DESTINATION
    if value.endswith("/") or value.endswith(":"):
        return value
    return value + "/"


def _origin(url: str) -> tuple[str, str, int]:
    try:
        parsed = urllib.parse.urlsplit(url)
        scheme = parsed.scheme.lower()
        host = parsed.hostname or ""
        port = parsed.port
    except ValueError as exc:
        raise RecorderError(f"invalid recorder source URL: {exc}") from None
    if scheme not in {"http", "https"} or not host:
        raise RecorderError("recorder source must be an explicit HTTP(S) URL; RTSP is not supported")
    return (scheme, host.lower(), port or (443 if scheme == "https" else 80))


def _safe_basename(uri: str) -> str:
    try:
        name = Path(urllib.parse.urlsplit(uri).path).name
    except Exception:
        return ""
    name = _SAFE_NAME_RE.sub("_", name).strip("._")
    return name[:96]


class _RecentKeys:
    """Bounded in-process memory of already captured object identities."""

    def __init__(self, limit: int = 4096) -> None:
        self._limit = limit
        self._order: deque = deque()
        self._set: set = set()

    def __contains__(self, key: object) -> bool:
        return key in self._set

    def add(self, key: object) -> None:
        if key in self._set:
            return
        if len(self._order) >= self._limit:
            self._set.discard(self._order.popleft())
        self._order.append(key)
        self._set.add(key)


class _SameOriginRedirect(urllib.request.HTTPRedirectHandler):
    """Allow redirects only within the origin of the request they answer."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urljoin(req.full_url, newurl)
        if _origin(target) != _origin(req.full_url):
            raise urllib.error.HTTPError(
                target, code, "cross-origin redirect refused", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, target)


def build_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_SameOriginRedirect)


def parse_playlist(text: str) -> tuple[str | None, list[str], int, bool]:
    """Return (init URI, segment URIs, media sequence, has media sequence)."""
    init_uri: str | None = None
    segments: list[str] = []
    media_sequence = 0
    has_media_sequence = False
    expect_segment = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            has_media_sequence = True
            try:
                media_sequence = int(line.split(":", 1)[1].strip())
            except ValueError:
                media_sequence = 0
        elif line.startswith("#EXT-X-MAP:"):
            match = _URI_RE.search(line)
            if match:
                init_uri = match.group(1)
        elif line.startswith("#EXTINF"):
            expect_segment = True
        elif line.startswith("#"):
            continue
        elif expect_segment:
            segments.append(line)
            expect_segment = False
    return init_uri, segments, media_sequence, has_media_sequence


def fetch_playlist(
    opener: urllib.request.OpenerDirector,
    url: str,
    headers: dict[str, str],
    timeout_sec: float,
) -> tuple[str, str]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with opener.open(request, timeout=timeout_sec) as response:
        final_url = response.geturl()
        data = response.read(_PLAYLIST_MAX_BYTES + 1)
    if len(data) > _PLAYLIST_MAX_BYTES:
        raise RecorderError("playlist exceeds the bounded playlist size")
    return data.decode("utf-8", "replace"), final_url


def download_object(
    opener: urllib.request.OpenerDirector,
    url: str,
    headers: dict[str, str],
    destination: Path,
    max_bytes: int,
    timeout_sec: float,
) -> int:
    """Stream one object to ``destination`` with a size cap and a deadline."""
    part = destination.with_name(destination.name + ".part")
    part.unlink(missing_ok=True)
    deadline = time.monotonic() + timeout_sec
    total = 0
    try:
        request = urllib.request.Request(url, headers=headers, method="GET")
        with opener.open(request, timeout=timeout_sec) as response:
            declared = response.headers.get("Content-Length", "")
            if declared.isdigit() and int(declared) > max_bytes:
                raise RecorderError("object exceeds the bounded object size")
            with part.open("wb") as handle:
                while True:
                    if time.monotonic() > deadline:
                        raise TimeoutError("object download deadline exceeded")
                    chunk = response.read(_CHUNK_BYTES)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise RecorderError("object exceeds the bounded object size")
                    handle.write(chunk)
        os.replace(part, destination)
        return total
    except BaseException:
        try:
            part.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def rsync_object(
    key_path: Path,
    local_path: Path,
    destination: str,
    timeout_sec: float,
) -> tuple[bool, str]:
    global _ACTIVE_RSYNC
    ssh = "ssh -i {} -o BatchMode=yes -o IdentitiesOnly=yes".format(
        shlex.quote(str(key_path))
    )
    command = [
        "rsync",
        "-a",
        "--timeout",
        str(max(1, int(timeout_sec))),
        "-e",
        ssh,
        str(local_path),
        destination,
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        close_fds=True,
    )
    _ACTIVE_RSYNC = process
    try:
        _, stderr = process.communicate(timeout=timeout_sec + 5.0)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            process.communicate(timeout=5.0)
        except Exception:
            pass
        return False, "rsync timeout"
    except BaseException:
        process.kill()
        try:
            process.communicate(timeout=5.0)
        except Exception:
            pass
        raise
    finally:
        _ACTIVE_RSYNC = None
    detail = stderr.decode("utf-8", "replace").strip()[-400:]
    return process.returncode == 0, detail


class HlsRecorder:
    """One recorder for one camera/source URL."""

    def __init__(self, config: RecorderConfig) -> None:
        self.config = config
        self.source_origin = _origin(config.hls_url)
        self.auth = media_basic_auth_for_input(config.hls_url)
        self.opener = build_opener()
        self.recent = _RecentKeys()
        self.init_seen: set[str] = set()
        self.captured_count = 0
        self.gap_count = 0

    def headers_for(self, url: str) -> dict[str, str]:
        headers = {"User-Agent": _USER_AGENT}
        # Basic auth is attached only to the configured origin. A playlist may
        # legitimately reference a cross-origin CDN object; that object gets no
        # credentials and a cross-origin redirect is refused by the opener.
        if self.auth and _origin(url) == self.source_origin:
            headers["Authorization"] = f"Basic {self.auth}"
        return headers

    def segment_name(self, sequence: int | None, index: int, uri: str) -> str:
        basename = _safe_basename(uri) or "segment"
        if sequence is None:
            tag = hashlib.sha256(uri.encode("utf-8")).hexdigest()[:16]
        else:
            tag = f"{sequence:012d}-{index:04d}"
        return f"{self.config.camera_id}-{tag}-{basename}"

    def init_name(self, uri: str) -> str:
        digest = hashlib.sha256(uri.encode("utf-8")).hexdigest()[:12]
        basename = _safe_basename(uri) or "init"
        return f"{self.config.camera_id}-init-{digest}-{basename}"

    def upload(self, path: Path) -> tuple[bool, str]:
        detail = ""
        for attempt in range(1, self.config.rsync_retries + 1):
            ok, detail = rsync_object(
                self.config.key_path,
                path,
                self.config.destination,
                self.config.rsync_timeout_sec,
            )
            if ok:
                return True, detail
            if attempt < self.config.rsync_retries:
                delay = min(300.0, self.config.rsync_backoff_sec * (2 ** (attempt - 1)))
                if delay:
                    time.sleep(delay)
        return False, detail

    def capture(self, url: str, filename: str) -> bool:
        free = shutil.disk_usage(self.config.spool_dir).free
        if free < self.config.min_free_bytes:
            raise SpoolSpaceLow(
                f"free={free} floor={self.config.min_free_bytes}"
            )
        destination = self.config.spool_dir / filename
        try:
            total = download_object(
                self.opener,
                url,
                self.headers_for(url),
                destination,
                self.config.object_max_bytes,
                self.config.http_timeout_sec,
            )
        except SpoolSpaceLow:
            raise
        except (
            RecorderError,
            urllib.error.URLError,
            http.client.HTTPException,
            TimeoutError,
            OSError,
        ) as exc:
            print(
                f"recorder object discarded name={filename} "
                f"reason=download_{type(exc).__name__}",
                flush=True,
            )
            return False
        try:
            ok, detail = self.upload(destination)
        finally:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass
        if ok:
            print(
                f"recorder object ok name={filename} bytes={total}", flush=True
            )
            return True
        print(
            f"recorder object discarded name={filename} reason=upload_failed "
            f"detail={detail or 'none'}",
            flush=True,
        )
        return False

    def run(self) -> None:
        config = self.config
        if not config.key_path.is_file() or not os.access(config.key_path, os.R_OK):
            raise RecorderError(
                f"recorder credential missing or unreadable at {config.key_path}"
            )
        config.spool_dir.mkdir(parents=True, exist_ok=True)
        _prune_partials(config.spool_dir)
        print(
            f"recorder start camera={config.camera_id} "
            f"source={safe_media_input_label(config.hls_url)} "
            f"spool={config.spool_dir} destination={config.destination}",
            flush=True,
        )
        next_sequence: int | None = None
        failures = 0
        while True:
            try:
                text, final_url = fetch_playlist(
                    self.opener,
                    config.hls_url,
                    self.headers_for(config.hls_url),
                    config.http_timeout_sec,
                )
                init_uri, segments, media_sequence, has_media_sequence = parse_playlist(text)
                if has_media_sequence:
                    if next_sequence is None:
                        next_sequence = media_sequence
                    elif media_sequence + len(segments) <= next_sequence:
                        print(
                            f"recorder playlist cursor reset "
                            f"previous={next_sequence} media_sequence={media_sequence}",
                            flush=True,
                        )
                        next_sequence = media_sequence

                if init_uri:
                    absolute = urllib.parse.urljoin(final_url, init_uri)
                    if absolute not in self.init_seen:
                        ok = self.capture(absolute, self.init_name(absolute))
                        if ok:
                            self.init_seen.add(absolute)
                            self.captured_count += 1
                        else:
                            self.gap_count += 1

                for index, uri in enumerate(segments):
                    absolute = urllib.parse.urljoin(final_url, uri)
                    sequence = media_sequence + index if has_media_sequence else None
                    if sequence is not None:
                        if sequence < next_sequence:
                            continue
                        if sequence > next_sequence:
                            missed = sequence - next_sequence
                            self.gap_count += missed
                            print(
                                f"recorder gap missed={missed} "
                                f"next_sequence={next_sequence} media_sequence={sequence}",
                                flush=True,
                            )
                            next_sequence = sequence
                    key = ("segment", sequence if sequence is not None else absolute)
                    if key in self.recent:
                        if sequence is not None:
                            next_sequence = sequence + 1
                        continue
                    if sequence is not None:
                        next_sequence = sequence + 1
                    self.recent.add(key)
                    if self.capture(absolute, self.segment_name(sequence, index, absolute)):
                        self.captured_count += 1
                    else:
                        self.gap_count += 1
                failures = 0
            except SpoolSpaceLow as exc:
                failures += 1
                print(f"recorder spool space low reason={exc}", flush=True)
            except (
                RecorderError,
                urllib.error.URLError,
                http.client.HTTPException,
                TimeoutError,
                OSError,
            ) as exc:
                failures += 1
                print(
                    f"recorder cycle error reason={type(exc).__name__} "
                    f"detail={str(exc)[:200] or 'none'}",
                    flush=True,
                )
            time.sleep(_next_poll(config.poll_sec, failures))


def _prune_partials(spool_dir: Path) -> None:
    for path in spool_dir.glob("*.part"):
        try:
            path.unlink()
        except OSError:
            pass


def _next_poll(poll_sec: float, failures: int) -> float:
    if failures <= 0:
        return poll_sec
    return min(30.0, poll_sec * (2 ** min(failures, 4)))


def _install_stop_handler() -> None:
    def _stop(signum: int, _frame: object) -> None:
        active = _ACTIVE_RSYNC
        if active is not None and active.poll() is None:
            try:
                active.kill()
            except Exception:
                pass
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)


def main() -> int:
    try:
        config = RecorderConfig.from_env()
    except RecorderError as exc:
        print(f"recorder disabled config_error={exc}", flush=True)
        return 2
    if not config.enabled:
        print("recorder disabled (SEA_SPEED_RECORDER_ENABLED=0)", flush=True)
        return 0
    _install_stop_handler()
    try:
        HlsRecorder(config).run()
    except RecorderError as exc:
        print(f"recorder disabled runtime_error={exc}", flush=True)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
