#!/usr/bin/env python3
"""Persistent decoder CPU baseline + keyframe/Range prototype (issue #703).

This is an on-demand, stdlib-only measurement tool. It never accepts a target
URL: it generates (or loads) one local encoded HLS timeline, serves it from a
disposable 127.0.0.1 origin, and measures two arms against that same timeline.

Arm A - persistent reader baseline
  A real ffmpeg subprocess with the production HLS reader flags
  (worker/worker_media.py: ``-i URL -vf fps=N,scale=WxH -pix_fmt bgr24 -f
  rawvideo pipe:1``) decodes a wall-clock-paced live HLS playlist while a
  consumer drains every complete raw frame. CPU is sampled from /proc for the
  decoder process and separately for the sampling pipeline.

Arm B - keyframe/Range prototype
  The latest complete segment is fetched with ``Range: bytes=0-511999``
  (500 KiB by default), the 206 + Content-Range answer is validated strictly,
  and a fresh ffmpeg process decodes one keyframe from the capped bytes.
  Repeated process startup and polling are part of the measured cost.

The report is bound to ``--tested-sha`` (full 40-hex). Without it the report is
marked UNBOUND and never claims a pass. A generated moving-pattern fixture
tests accounting and Range mechanics only: without an approved representative
source and labeled events the full outcome stays UNMEASURED and no adoption is
recommended.

Scope boundaries: measurement only. No production reader is replaced, no
transport/relay is introduced, and no production host is contacted.

Usage (frozen evidence run)::

    python3 scripts/worker/decoder_grab_baseline.py \
      --tested-sha "$(git rev-parse HEAD)" \
      --output /tmp/opencode/703-baseline/report.json

No third-party import. Linux /proc is required for CPU accounting; where it is
unavailable the affected metric is reported as null with a reason.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import os
import platform
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SEGMENT_RE = re.compile(r"^/seg(\d{5})\.ts$")

PROFILE_FPS = {"water": 5.0, "road": 10.0}
FRAME_WIDTH = 1920
FRAME_HEIGHT = 1080
FRAME_BYTES = FRAME_WIDTH * FRAME_HEIGHT * 3

FROZEN = {
    "profiles": ["water", "road"],
    "source_seconds": 210.0,
    "segment_seconds": 2.0,
    "source_fps": 10.0,
    "source_width": 1920,
    "source_height": 1080,
    "source_bitrate_kbps": 2500,
    "source_gop_seconds": 2.0,
    "source_motion": "synthetic testsrc2 moving pattern",
    "warmup_seconds": 10.0,
    "windows": 3,
    "window_seconds": 60.0,
    "poll_seconds": 1.0,
    "range_bytes": 500 * 1024,
    "playlist_window_segments": 6,
    "stall_seconds": 3.5,
    "frame_yield_min": 0.90,
    "prototype_cpu_ratio_max": 0.50,
    "prototype_frame_ready_p95_ms_max": 3000.0,
    "prototype_failures_max": 0,
}

READER_MODE = "hls-persistent-rawvideo"
PROTOTYPE_MODE = "hls-range-first-keyframe"


def _round(value, digits=6):
    if value is None:
        return None
    return round(float(value), digits)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint_source(catalog: "SegmentCatalog") -> str:
    """Stable sha256 over the playlist text and every segment payload."""
    digest = hashlib.sha256()
    digest.update(catalog.playlist_fingerprint.encode("utf-8"))
    for segment in catalog.segments:
        digest.update(segment.path.name.encode("utf-8"))
        digest.update(sha256_file(segment.path).encode("ascii"))
    return digest.hexdigest()


def parse_playlist(text: str) -> dict:
    """Parse the minimal HLS attributes this harness needs."""
    media_sequence = 0
    target_duration = None
    duration = None
    uris = []
    durations = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXT-X-MEDIA-SEQUENCE:"):
            try:
                media_sequence = int(line.split(":", 1)[1])
            except ValueError:
                media_sequence = 0
        elif line.startswith("#EXT-X-TARGETDURATION:"):
            try:
                target_duration = float(line.split(":", 1)[1])
            except ValueError:
                target_duration = None
        elif line.startswith("#EXTINF:"):
            value = line.split(":", 1)[1].split(",", 1)[0]
            try:
                duration = float(value)
            except ValueError:
                duration = None
            if duration is not None:
                durations.append(duration)
        elif not line.startswith("#"):
            uris.append(line)
    if duration is None and durations:
        duration = durations[-1]
    return {
        "media_sequence": media_sequence,
        "target_duration": target_duration,
        "uris": uris,
        "durations": durations,
    }


def parse_content_range(value: str | None) -> dict | None:
    """Parse ``bytes start-end/total`` or ``bytes */total``; None if malformed."""
    if not value:
        return None
    match = re.fullmatch(r"bytes\s+(\d+)-(\d+)/(\d+)", value.strip())
    if match:
        start, end, total = (int(part) for part in match.groups())
        if start > end or end >= total:
            return None
        return {"start": start, "end": end, "total": total}
    match = re.fullmatch(r"bytes\s+\*/(\d+)", value.strip())
    if match:
        return {"start": None, "end": None, "total": int(match.group(1))}
    return None


def evaluate_range_response(
    status: int,
    content_range: str | None,
    content_length: str | None,
    body_len: int,
    total: int,
    requested_start: int,
    requested_end: int,
) -> dict:
    """Strictly validate one Range answer. Every ignored header is a failure."""
    failures = []
    expected_len = requested_end - requested_start + 1
    if status != 206:
        failures.append(f"range_not_honored_status_{status}")
    parsed = parse_content_range(content_range)
    if parsed is None:
        failures.append("content_range_missing_or_malformed")
    else:
        if parsed["start"] != requested_start or parsed["end"] != requested_end:
            failures.append("content_range_span_mismatch")
        if parsed["total"] != total:
            failures.append("content_range_total_mismatch")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError:
            declared = -1
        if declared != expected_len:
            failures.append("content_length_mismatch")
    else:
        failures.append("content_length_missing")
    if body_len != expected_len:
        failures.append(f"body_length_{body_len}_expected_{expected_len}")
    return {
        "status": status,
        "content_range": content_range,
        "content_length": content_length,
        "requested": {"start": requested_start, "end": requested_end},
        "body_len": body_len,
        "total": total,
        "ok": not failures,
        "failures": failures,
    }


def percentile(values, p: float):
    """Nearest-rank percentile (1..100)."""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100.0 * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def binding_for_sha(sha: str | None) -> str:
    return "BOUND" if sha and FULL_SHA_RE.fullmatch(sha.strip()) else "UNBOUND"


def read_proc_cpu(pid: int) -> float | None:
    """utime+stime in seconds from /proc/<pid>/stat, or None."""
    try:
        stat = Path(f"/proc/{int(pid)}/stat").read_text()
    except (OSError, ValueError):
        return None
    try:
        fields = stat[stat.rindex(")") + 2 :].split()
        ticks = int(fields[11]) + int(fields[12])
    except (ValueError, IndexError):
        return None
    try:
        hz = os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError):
        hz = 100
    return ticks / float(hz)


def proc_mem_mib(pid: int):
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return round(int(line.split()[1]) / 1024.0, 2)
    except (OSError, ValueError, IndexError):
        return None
    return None


def cgroup_cpu_quota() -> dict:
    for candidate in ("/sys/fs/cgroup/cpu.max", "/sys/fs/cgroup/cpu/cpu.cfs_quota_us"):
        path = Path(candidate)
        if not path.is_file():
            continue
        try:
            text = path.read_text().strip()
        except OSError:
            continue
        try:
            if candidate.endswith("cpu.max"):
                quota_text, period_text = text.split()[:2]
                if quota_text == "max":
                    return {"limit": "unlimited", "source": candidate}
                return {
                    "quota_us": int(quota_text),
                    "period_us": int(period_text),
                    "limit_cores": round(int(quota_text) / int(period_text), 3),
                    "source": candidate,
                }
            quota = int(text)
            if quota <= 0:
                return {"limit": "unlimited", "source": candidate}
            return {"quota_us": quota, "period_us": 100000, "limit_cores": round(quota / 100000.0, 3), "source": candidate}
        except (OSError, ValueError):
            continue
    return {"limit": "unknown", "source": "unavailable"}


def cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text().splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def runtime_identity(ffmpeg_path: str) -> dict:
    try:
        version = subprocess.run(
            [ffmpeg_path, "-version"], capture_output=True, text=True, timeout=10, check=False
        )
        build = version.stdout.splitlines()[0] if version.stdout else "unknown"
    except (OSError, subprocess.SubprocessError):
        build = "unavailable"
    return {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "logical_cpus": os.cpu_count(),
        "cpu_model": cpu_model(),
        "cgroup_cpu": cgroup_cpu_quota(),
        "ffmpeg_build": build,
        "ffmpeg_decode_mode": "software",  # no hardware decode flag is passed
    }


class Segment:
    __slots__ = ("index", "path", "duration", "size", "start", "suffix")

    def __init__(self, index: int, path: Path, duration: float, start: float):
        self.index = index
        self.path = path
        self.duration = duration
        self.start = start
        self.size = path.stat().st_size
        self.suffix = path.suffix.lower()


class SegmentCatalog:
    def __init__(self, source_dir: Path):
        playlist_path = source_dir / "source.m3u8"
        self.playlist_fingerprint = sha256_file(playlist_path)
        parsed = parse_playlist(playlist_path.read_text())
        self.target_duration = parsed["target_duration"]
        segments = []
        cursor = 0.0
        for index, uri in enumerate(parsed["uris"]):
            name = uri.split("/")[-1]
            if not name.endswith((".ts", ".m4s", ".mp4")):
                raise ValueError(f"unsupported segment format: {name}")
            path = source_dir / name
            if not path.is_file():
                raise ValueError(f"playlist references a missing segment: {name}")
            duration = parsed["durations"][index] if index < len(parsed["durations"]) else FROZEN["segment_seconds"]
            segments.append(Segment(index, path, duration, cursor))
            cursor += duration
        if not segments:
            raise ValueError("source playlist contains no segments")
        self.segments = segments
        self.total_duration = cursor
        self.epoch = time.monotonic()
        self._lock = threading.Lock()

    def reset_epoch(self) -> None:
        with self._lock:
            self.epoch = time.monotonic()

    def available_count(self, now: float | None = None) -> int:
        with self._lock:
            epoch = self.epoch
        elapsed = (time.monotonic() if now is None else now) - epoch
        count = 0
        for segment in self.segments:
            if segment.start <= elapsed:
                count += 1
            else:
                break
        return count

    def available_at(self, index: int) -> float:
        with self._lock:
            epoch = self.epoch
        return epoch + self.segments[index].start

    def playlist_text(self, now: float | None = None, window: int = 6) -> str:
        available = self.available_count(now)
        media_sequence = max(0, available - window)
        target = int(math.ceil(self.target_duration or FROZEN["segment_seconds"]))
        lines = [
            "#EXTM3U",
            "#EXT-X-VERSION:3",
            f"#EXT-X-TARGETDURATION:{target}",
            f"#EXT-X-MEDIA-SEQUENCE:{media_sequence}",
            "#EXT-X-DISCONTINUITY-SEQUENCE:0",
        ]
        for segment in self.segments[media_sequence:available]:
            lines.append(f"#EXTINF:{segment.duration:.3f},")
            lines.append(f"/{segment.path.name}")
        if available >= len(self.segments):
            lines.append("#EXT-X-ENDLIST")
        return "\n".join(lines) + "\n"


def parse_range_header(value: str, total: int):
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value.strip())
    if not match:
        return None
    start_text, end_text = match.groups()
    if not start_text and not end_text:
        return None
    if not start_text:
        suffix = int(end_text)
        if suffix <= 0:
            return None
        start = max(0, total - suffix)
        end = total - 1
    else:
        start = int(start_text)
        end = int(end_text) if end_text else total - 1
    if start >= total:
        return None
    end = min(end, total - 1)
    if start > end:
        return None
    return start, end


class OriginHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # keep the run quiet
        return

    def _send(self, status: int, body: bytes, headers: dict):
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        catalog: SegmentCatalog = self.server.catalog  # type: ignore[attr-defined]
        window = self.server.window  # type: ignore[attr-defined]
        if self.path.split("?", 1)[0] in ("/live.m3u8", "/source.m3u8"):
            body = catalog.playlist_text(window=window).encode("utf-8")
            self._send(
                200,
                body,
                {
                    "Content-Type": "application/vnd.apple.mpegurl",
                    "Cache-Control": "no-store",
                    "Accept-Ranges": "none",
                },
            )
            return
        match = SEGMENT_RE.fullmatch(self.path.split("?", 1)[0])
        if not match:
            self._send(404, b"not found", {"Content-Type": "text/plain"})
            return
        index = int(match.group(1))
        if index >= len(catalog.segments):
            self._send(404, b"segment not published", {"Content-Type": "text/plain"})
            return
        segment = catalog.segments[index]
        wait = catalog.available_at(index) - time.monotonic()
        if wait > 0:
            if wait > 10:
                self._send(503, b"segment not available", {"Content-Type": "text/plain"})
                return
            time.sleep(wait)
        total = segment.size
        range_header = self.headers.get("Range")
        if range_header:
            parsed = parse_range_header(range_header, total)
            if parsed is None:
                self._send(
                    416,
                    b"range not satisfiable",
                    {"Content-Range": f"bytes */{total}", "Content-Type": "text/plain", "Accept-Ranges": "bytes"},
                )
                return
            start, end = parsed
            with segment.path.open("rb") as handle:
                handle.seek(start)
                body = handle.read(end - start + 1)
            self._send(
                206,
                body,
                {
                    "Content-Type": "video/mp2t" if segment.suffix == ".ts" else "video/mp4",
                    "Accept-Ranges": "bytes",
                    "Content-Range": f"bytes {start}-{end}/{total}",
                    "Cache-Control": "no-store",
                },
            )
            return
        body = segment.path.read_bytes()
        self._send(
            200,
            body,
            {
                "Content-Type": "video/mp2t" if segment.suffix == ".ts" else "video/mp4",
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-store",
            },
        )


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # ffmpeg closes HTTP connections abruptly in normal operation.
        return


class Origin:
    """Disposable loopback HLS origin; binds an ephemeral 127.0.0.1 port."""

    def __init__(self, catalog: SegmentCatalog, window: int):
        self.catalog = catalog
        self.server = QuietThreadingHTTPServer(("127.0.0.1", 0), OriginHandler)
        self.server.daemon_threads = True
        self.server.catalog = catalog  # type: ignore[attr-defined]
        self.server.window = window  # type: ignore[attr-defined]
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, name="origin", daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.server.shutdown()
        self.server.server_close()
        return False

    def playlist(self, timeout: float = 5.0) -> str:
        body, status = self._get("/live.m3u8", timeout=timeout)
        if status != 200:
            raise RuntimeError(f"playlist status {status}")
        return body.decode("utf-8", "replace")

    def segment(self, index: int, start: int, end: int, timeout: float = 10.0) -> dict:
        body, status, headers = self._get(
            f"/seg{index:05d}.ts",
            headers={"Range": f"bytes={start}-{end}", "Cache-Control": "no-cache"},
            timeout=timeout,
            with_headers=True,
        )
        return {
            "status": status,
            "headers": {name.lower(): value for name, value in headers.items()},
            "body": body,
        }

    def _get(self, path: str, headers: dict | None = None, timeout: float = 5.0, with_headers: bool = False):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            connection.request("GET", path, headers=headers or {})
            response = connection.getresponse()
            body = response.read()
            if with_headers:
                return body, response.status, dict(response.getheaders())
            return body, response.status
        finally:
            connection.close()


def generate_source(ffmpeg_path: str, out_dir: Path, seconds: float) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={FROZEN['source_width']}x{FROZEN['source_height']}:rate={FROZEN['source_fps']}",
        "-t",
        f"{seconds:.3f}",
        "-c:v",
        "libx264",
        "-preset",
        "ultrafast",
        "-tune",
        "zerolatency",
        "-g",
        str(int(FROZEN["source_fps"] * FROZEN["source_gop_seconds"])),
        "-keyint_min",
        str(int(FROZEN["source_fps"] * FROZEN["source_gop_seconds"])),
        "-sc_threshold",
        "0",
        "-force_key_frames",
        f"expr:gte(t,n_forced*{FROZEN['source_gop_seconds']})",
        "-pix_fmt",
        "yuv420p",
        "-b:v",
        f"{FROZEN['source_bitrate_kbps']}k",
        "-maxrate",
        f"{FROZEN['source_bitrate_kbps']}k",
        "-bufsize",
        f"{FROZEN['source_bitrate_kbps'] * 2}k",
        "-f",
        "hls",
        "-hls_time",
        f"{FROZEN['segment_seconds']}",
        "-hls_list_size",
        "0",
        "-hls_segment_type",
        "mpegts",
        "-hls_flags",
        "independent_segments",
        "-hls_segment_filename",
        str(out_dir / "seg%05d.ts"),
        str(out_dir / "source.m3u8"),
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=max(120.0, seconds * 2), check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"ffmpeg source generation failed: {completed.stderr.strip()[-800:]}")
    if not (out_dir / "source.m3u8").is_file():
        raise RuntimeError("ffmpeg source generation produced no playlist")


class FrameDrain(threading.Thread):
    """Drain complete raw frames from the decoder's stdout pipe."""

    def __init__(self, proc: subprocess.Popen, frame_bytes: int):
        super().__init__(name="frame-drain", daemon=True)
        self.proc = proc
        self.frame_bytes = frame_bytes
        self.stop = threading.Event()
        self.timestamps: list[float] = []
        self.error: str | None = None

    def run(self):
        stream = self.proc.stdout
        if stream is None:
            self.error = "decoder stdout unavailable"
            return
        fd = stream.fileno()
        buffer = bytearray(self.frame_bytes)
        view = memoryview(buffer)
        try:
            while not self.stop.is_set():
                filled = 0
                while filled < self.frame_bytes:
                    chunk = os.readv(fd, [view[filled:]])
                    if not chunk:
                        if filled:
                            self.error = f"short frame: {filled}/{self.frame_bytes}"
                        return
                    filled += chunk
                self.timestamps.append(time.monotonic())
        except OSError as exc:
            self.error = f"decoder pipe read failed: {exc}"


def reader_command(ffmpeg_path: str, url: str, fps: float) -> list[str]:
    """Production-equivalent HLS reader flags (worker/worker_media.py:42-94)."""
    return [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "warning",
        "-i",
        url,
        "-vf",
        f"fps={fps:g},scale={FRAME_WIDTH}:{FRAME_HEIGHT}",
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]


def drain_stderr(proc: subprocess.Popen, sink: list[str]) -> None:
    stream = proc.stderr
    if stream is None:
        return
    try:
        for raw in iter(stream.readline, b""):
            sink.append(raw.decode("utf-8", "replace").rstrip())
            if len(sink) > 16:
                del sink[0]
    except Exception:
        pass


def run_baseline(
    ffmpeg_path: str,
    origin: Origin,
    profile: str,
    window_seconds: float,
    windows: int,
    warmup_seconds: float,
) -> dict:
    fps = PROFILE_FPS[profile]
    origin.catalog.reset_epoch()
    if not origin.catalog.segments:
        return {"status": "NOT EXECUTED", "reason": "source catalog is empty"}
    url = f"http://127.0.0.1:{origin.port}/live.m3u8"
    command = reader_command(ffmpeg_path, url, fps)
    stderr_tail: list[str] = []
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
    threading.Thread(target=drain_stderr, args=(proc, stderr_tail), name="decoder-stderr", daemon=True).start()
    drain = FrameDrain(proc, FRAME_BYTES)
    drain.start()
    result = {
        "status": "FAILED",
        "profile": profile,
        "mode": READER_MODE,
        "command": command,
        "warmup_seconds": warmup_seconds,
        "window_seconds": window_seconds,
        "windows": [],
        "decoder_cpu_s_per_s": None,
        "pipeline_cpu_s_per_s": None,
        "total_arm_cpu_s_per_s": None,
        "frames_delivered": 0,
        "frame_yield": None,
        "stalls": None,
        "misses": None,
        "rss_mib": None,
        "notes": [
            "live HLS timeline paced by the loopback origin; no -re/fast-seek flag",
            "consumer drains complete raw frames; no unpaced file decode",
        ],
    }
    try:
        time.sleep(warmup_seconds)
        if proc.poll() is not None:
            result["decoder_exit_code"] = proc.poll()
            result["reason"] = f"decoder exited during warm-up (code {proc.poll()}): {' | '.join(stderr_tail[-3:])}"
            return result
        if not drain.timestamps:
            detail = f": {drain.error}" if drain.error else ""
            result["reason"] = f"decoder produced no frames during warm-up{detail}"
            return result

        window_rows = []
        for index in range(windows):
            cpu_start = read_proc_cpu(proc.pid)
            self_start = read_proc_cpu(os.getpid())
            t_start = time.monotonic()
            frame_start = len(drain.timestamps)
            time.sleep(window_seconds)
            t_end = time.monotonic()
            frame_end = len(drain.timestamps)
            cpu_end = read_proc_cpu(proc.pid)
            self_end = read_proc_cpu(os.getpid())
            if proc.poll() is not None:
                result["decoder_exit_code"] = proc.poll()
                result["reason"] = f"decoder exited during window {index} (code {proc.poll()}): {' | '.join(stderr_tail[-3:])}"
                window_rows.append({"index": index, "status": "FAILED", "reason": result["reason"]})
                break
            elapsed = t_end - t_start
            decoder_cpu = None if cpu_start is None or cpu_end is None else max(0.0, cpu_end - cpu_start)
            pipeline_cpu = None if self_start is None or self_end is None else max(0.0, self_end - self_start)
            delivered = frame_end - frame_start
            expected = fps * elapsed
            stamps = drain.timestamps[frame_start:frame_end]
            gaps = [b - a for a, b in zip(stamps, stamps[1:])]
            stalls = sum(1 for gap in gaps if gap > FROZEN["stall_seconds"])
            window_rows.append(
                {
                    "index": index,
                    "status": "MEASURED",
                    "elapsed_seconds": _round(elapsed, 3),
                    "frames_delivered": delivered,
                    "expected_frames": _round(expected, 1),
                    "delivered_fps": _round(delivered / elapsed, 3),
                    "frame_yield": _round(delivered / expected, 4) if expected else None,
                    "misses": max(0, int(round(expected - delivered))),
                    "stalls": stalls,
                    "max_frame_gap_seconds": _round(max(gaps), 4) if gaps else None,
                    "decoder_cpu_seconds": _round(decoder_cpu),
                    "decoder_cpu_s_per_s": _round(decoder_cpu / elapsed, 6) if decoder_cpu is not None else None,
                    "pipeline_cpu_seconds": _round(pipeline_cpu),
                    "pipeline_cpu_s_per_s": _round(pipeline_cpu / elapsed, 6) if pipeline_cpu is not None else None,
                    "total_arm_cpu_s_per_s": _round((decoder_cpu + pipeline_cpu) / elapsed, 6)
                    if decoder_cpu is not None and pipeline_cpu is not None
                    else None,
                    "rss_mib": proc_mem_mib(proc.pid),
                }
            )
        result["windows"] = window_rows
        measured = [row for row in window_rows if row["status"] == "MEASURED"]
        if not measured:
            result["status"] = "NOT EXECUTED"
            result.setdefault("reason", "no measured baseline window")
            return result
        total_elapsed = sum(row["elapsed_seconds"] for row in measured)
        total_frames = sum(row["frames_delivered"] for row in measured)
        decoder = sum(row["decoder_cpu_seconds"] or 0.0 for row in measured)
        pipeline = sum(row["pipeline_cpu_seconds"] or 0.0 for row in measured)
        result.update(
            {
                "status": "MEASURED" if len(measured) == windows else "PARTIAL",
                "decoder_cpu_s_per_s": _round(decoder / total_elapsed, 6),
                "pipeline_cpu_s_per_s": _round(pipeline / total_elapsed, 6),
                "total_arm_cpu_s_per_s": _round((decoder + pipeline) / total_elapsed, 6),
                "frames_delivered": total_frames,
                "frame_yield": _round(total_frames / (fps * total_elapsed), 4),
                "stalls": sum(row["stalls"] for row in measured),
                "misses": sum(row["misses"] for row in measured),
                "rss_mib": proc_mem_mib(proc.pid),
            }
        )
        window_yields = [row["frame_yield"] for row in measured if row["frame_yield"] is not None]
        yield_ok = bool(window_yields) and all(value >= FROZEN["frame_yield_min"] for value in window_yields)
        result["verdict"] = "MEASURED" if yield_ok else "INVALID"
        if not yield_ok:
            result["reason"] = (
                f"a window frame yield fell below {FROZEN['frame_yield_min']}: {window_yields}"
            )
        return result
    finally:
        drain.stop.set()
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        except OSError:
            pass
        drain.join(timeout=5)


def decode_keyframe(ffmpeg_path: str, data: bytes, profile: str, timeout: float = 15.0) -> dict:
    fps = PROFILE_FPS[profile]
    command = [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-skip_frame",
        "nokey",
        "-i",
        "pipe:0",
        "-frames:v",
        "1",
        "-vf",
        f"fps={fps:g},scale={FRAME_WIDTH}:{FRAME_HEIGHT}",
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    handle = tempfile.NamedTemporaryFile(prefix="decoder-grab-", suffix=".ts", delete=False)
    temp_path = Path(handle.name)
    try:
        handle.write(data)
        handle.close()
        command = [part if part != "pipe:0" else str(temp_path) for part in command]
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            return {"ok": False, "reason": "decode timeout", "command": command}
    finally:
        try:
            temp_path.unlink()
        except OSError:
            pass
    elapsed = time.monotonic() - started
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (after.ru_utime - before.ru_utime) + (after.ru_stime - before.ru_stime)
    ok = proc.returncode == 0 and len(stdout) >= FRAME_BYTES
    return {
        "ok": ok,
        "command": command,
        "returncode": proc.returncode,
        "frames": len(stdout) // FRAME_BYTES,
        "elapsed_seconds": _round(elapsed, 6),
        "child_cpu_seconds": _round(cpu, 6),
        "reason": None if ok else (stderr.decode("utf-8", "replace").strip()[-400:] or "no keyframe decoded"),
    }


def run_prototype(
    ffmpeg_path: str,
    origin: Origin,
    profile: str,
    window_seconds: float,
    windows: int,
    warmup_seconds: float,
    poll_seconds: float,
    range_bytes: int,
) -> dict:
    origin.catalog.reset_epoch()
    result = {
        "status": "FAILED",
        "profile": profile,
        "mode": PROTOTYPE_MODE,
        "range_bytes": range_bytes,
        "poll_seconds": poll_seconds,
        "warmup_seconds": warmup_seconds,
        "window_seconds": window_seconds,
        "windows": [],
        "observations": 0,
        "usable_observations": 0,
        "failures": 0,
        "failure_reasons": {},
        "cpu_s_per_s": None,
        "pipeline_cpu_s_per_s": None,
        "total_arm_cpu_s_per_s": None,
        "frame_ready_latency_ms": {"p50": None, "p95": None, "max": None},
        "detection_latency": "UNMEASURED",
        "latency_kind": "frame_ready (poll start -> decoded keyframe), not detection latency",
        "notes": [
            "latest complete segment only; Range capped before decode",
            "fresh ffmpeg process per new segment; startup and polling included in cost",
            "MPEG-TS carries stream init in-band; an fMP4 segment without a fetched init segment is a missing-init failure",
        ],
    }
    last_sequence = None
    missed_counts = [0] * windows
    failures: "OrderedDict[str, int]" = OrderedDict()
    window_rows = [
        {
            "index": index,
            "status": "MEASURED",
            "observations": 0,
            "usable_observations": 0,
            "failures": 0,
            "child_cpu_seconds": 0.0,
            "latencies_ms": [],
            "segments": [],
        }
        for index in range(windows)
    ]
    run_start = time.monotonic()
    try:
        while True:
            t0 = time.monotonic()
            elapsed = t0 - run_start
            if elapsed >= warmup_seconds + windows * window_seconds:
                break
            try:
                playlist = origin.playlist(timeout=3.0)
                parsed = parse_playlist(playlist)
                if parsed["uris"]:
                    latest = parsed["media_sequence"] + len(parsed["uris"]) - 1
                else:
                    latest = None
            except Exception as exc:
                failures["playlist_fetch_failed"] = failures.get("playlist_fetch_failed", 0) + 1
                result["notes"].append(f"playlist poll failed: {exc}")
                latest = None

            if latest is not None and elapsed >= warmup_seconds:
                index = int((elapsed - warmup_seconds) // window_seconds)
                if index >= windows:
                    index = windows - 1
                row = window_rows[index]
                if last_sequence is None:
                    last_sequence = latest
                if latest > last_sequence:
                    missed = latest - last_sequence - 1
                    if missed > 0:
                        failures["missed_opportunities"] = failures.get("missed_opportunities", 0) + missed
                        missed_counts[index] += missed
                    for sequence in range(last_sequence + 1, latest + 1):
                        segment = origin.catalog.segments[sequence]
                        # MPEG-TS carries init in-band; an fMP4 segment needs a
                        # separate init segment, which this prototype does not
                        # fetch, so it is an explicit missing-init failure.
                        init_in_band = segment.suffix == ".ts"
                        if not init_in_band:
                            failures["missing_init_data"] = failures.get("missing_init_data", 0) + 1
                        total = segment.size
                        end = min(range_bytes, total) - 1
                        t_detect = time.monotonic()
                        try:
                            response = origin.segment(sequence, 0, end)
                        except Exception as exc:
                            failures["segment_fetch_failed"] = failures.get("segment_fetch_failed", 0) + 1
                            result["notes"].append(f"segment {sequence} fetch failed: {exc}")
                            continue
                        body = response["body"]
                        headers = response["headers"]
                        check = evaluate_range_response(
                            response["status"],
                            headers.get("content-range"),
                            headers.get("content-length"),
                            len(body),
                            total,
                            0,
                            end,
                        )
                        if not check["ok"]:
                            for failure in check["failures"]:
                                failures[failure] = failures.get(failure, 0) + 1
                        decode = decode_keyframe(ffmpeg_path, body, profile)
                        if not decode["ok"]:
                            failures["incomplete_keyframe"] = failures.get("incomplete_keyframe", 0) + 1
                        t_frame = time.monotonic()
                        latency_ms = (t_frame - t0) * 1000.0
                        age_ms = (t_detect - origin.catalog.available_at(sequence)) * 1000.0
                        row["observations"] += 1
                        if check["ok"] and decode["ok"]:
                            row["usable_observations"] += 1
                        row["child_cpu_seconds"] += decode.get("child_cpu_seconds") or 0.0
                        row["latencies_ms"].append(latency_ms)
                        row["segments"].append(
                            {
                                "sequence": sequence,
                                "bytes_fetched": len(body),
                                "init_data": "in-band-mpegts" if init_in_band else "missing-fmp4-init",
                                "range_ok": check["ok"],
                                "range_failures": check["failures"],
                                "decode_ok": decode["ok"],
                                "decode_reason": decode["reason"],
                                "latency_ms": _round(latency_ms, 3),
                                "segment_age_at_detect_ms": _round(max(0.0, age_ms), 3),
                            }
                        )
                        row["failures"] = (
                            sum(1 for seg in row["segments"] if not seg["range_ok"] or not seg["decode_ok"])
                            + missed_counts[index]
                        )
                    last_sequence = latest

            sleep_for = poll_seconds - (time.monotonic() - t0)
            if sleep_for > 0:
                time.sleep(sleep_for)

        total_observations = sum(row["observations"] for row in window_rows)
        result["failure_reasons"] = dict(failures)
        result["failures"] = sum(failures.values())
        result["observations"] = total_observations
        result["usable_observations"] = sum(row["usable_observations"] for row in window_rows)
        latencies = [value for row in window_rows for value in row["latencies_ms"]]
        if latencies:
            result["frame_ready_latency_ms"] = {
                "p50": _round(percentile(latencies, 50), 3),
                "p95": _round(percentile(latencies, 95), 3),
                "max": _round(max(latencies), 3),
            }
        # Harness CPU is sampled over the whole prototype arm; process startup
        # CPU is included via RUSAGE_CHILDREN in each decode observation.
        for index, row in enumerate(window_rows):
            segments = row["segments"]
            row["latency_p50_ms"] = _round(percentile([s["latency_ms"] for s in segments], 50), 3) if segments else None
            row["latency_p95_ms"] = _round(percentile([s["latency_ms"] for s in segments], 95), 3) if segments else None
            row["latency_max_ms"] = _round(max(s["latency_ms"] for s in segments), 3) if segments else None
            row["ok"] = bool(segments) and row["failures"] == 0 and row["usable_observations"] > 0
            del row["latencies_ms"]
        result["windows"] = window_rows
        if total_observations == 0:
            result["status"] = "NOT EXECUTED"
            result["reason"] = "zero usable Range/keyframe observations"
            return result
        result["status"] = "MEASURED"
        return result
    finally:
        pass


def measure_prototype_cpu(
    result: dict,
    harness_cpu_before: float | None,
    harness_cpu_after: float | None,
    elapsed: float,
) -> None:
    child = sum(row["child_cpu_seconds"] for row in result["windows"])
    pipeline = None
    if harness_cpu_before is not None and harness_cpu_after is not None:
        pipeline = max(0.0, harness_cpu_after - harness_cpu_before)
    result["child_cpu_seconds"] = _round(child)
    result["pipeline_cpu_s_per_s"] = _round(pipeline / elapsed, 6) if pipeline is not None else None
    result["cpu_s_per_s"] = _round(child / elapsed, 6)
    result["total_arm_cpu_s_per_s"] = (
        _round((child + pipeline) / elapsed, 6) if pipeline is not None else result["cpu_s_per_s"]
    )


def compare_arms(baseline_rows: list[dict], prototype_rows: list[dict]) -> dict:
    comparisons = []
    for base, proto in zip(baseline_rows, prototype_rows):
        entry = {
            "profile": base.get("profile"),
            "baseline_status": base.get("status"),
            "prototype_status": proto.get("status"),
            "baseline_total_cpu_s_per_s": base.get("total_arm_cpu_s_per_s"),
            "prototype_total_cpu_s_per_s": proto.get("total_arm_cpu_s_per_s"),
            "cpu_ratio": None,
            "cpu_ratio_ok": None,
            "prototype_failures": proto.get("failures"),
            "frame_ready_p95_ms": (proto.get("frame_ready_latency_ms") or {}).get("p95"),
            "frame_ready_p95_ok": None,
            "thresholds": {
                "cpu_ratio_max": FROZEN["prototype_cpu_ratio_max"],
                "frame_ready_p95_ms_max": FROZEN["prototype_frame_ready_p95_ms_max"],
                "failures_max": FROZEN["prototype_failures_max"],
            },
        }
        if base.get("total_arm_cpu_s_per_s") and proto.get("total_arm_cpu_s_per_s") is not None:
            entry["cpu_ratio"] = _round(proto["total_arm_cpu_s_per_s"] / base["total_arm_cpu_s_per_s"], 4)
            entry["cpu_ratio_ok"] = entry["cpu_ratio"] <= FROZEN["prototype_cpu_ratio_max"]
        if entry["frame_ready_p95_ms"] is not None:
            entry["frame_ready_p95_ok"] = entry["frame_ready_p95_ms"] <= FROZEN["prototype_frame_ready_p95_ms_max"]
        comparisons.append(entry)
    return {"pairs": comparisons}


def build_decision(report: dict) -> dict:
    reasons = []
    measurement = "RED"
    baseline_rows = report["arms"]["baseline"]
    prototype_rows = report["arms"]["prototype"]
    if not baseline_rows:
        reasons.append("baseline arm did not run")
    if not prototype_rows:
        reasons.append("prototype arm did not run")
    if any(row.get("status") not in ("MEASURED", "PARTIAL") for row in baseline_rows):
        reasons.append("baseline arm did not produce measured windows")
    if any(row.get("status") == "PARTIAL" for row in baseline_rows):
        reasons.append("baseline arm produced fewer than the frozen windows")
    if any(row.get("status") != "MEASURED" for row in prototype_rows):
        reasons.append("prototype arm did not produce usable observations")
    if report.get("not_executed"):
        reasons.append("run reported NOT EXECUTED entries")
    selected_profiles = report.get("profile_selection") or []
    if selected_profiles and len(report.get("comparison", {}).get("pairs", [])) != len(selected_profiles):
        reasons.append("paired comparison does not cover every selected profile")
    if any((row.get("verdict") not in (None, "MEASURED")) for row in baseline_rows):
        reasons.append("baseline frame yield below the frozen validity floor")
    if any(row.get("usable_observations", 0) <= 0 for row in prototype_rows if row.get("status") == "MEASURED"):
        reasons.append("a prototype window has zero usable observations")
    if report["binding"] == "UNBOUND":
        reasons.append("tested SHA is missing or not a full 40-hex commit")

    baseline_ok = bool(baseline_rows) and all(
        row.get("status") in ("MEASURED", "PARTIAL") for row in baseline_rows
    ) and all(row.get("verdict") == "MEASURED" for row in baseline_rows if row.get("status") == "MEASURED")
    prototype_ok = bool(prototype_rows) and all(row.get("status") == "MEASURED" for row in prototype_rows) and all(
        row.get("usable_observations", 0) > 0 for row in prototype_rows
    )
    if not reasons and baseline_ok and prototype_ok:
        measurement = "GREEN"

    comparisons = report["comparison"]["pairs"]
    performance_ok = bool(comparisons) and all(
        entry.get("cpu_ratio_ok") and entry.get("frame_ready_p95_ok") for entry in comparisons
    )
    failures_ok = bool(comparisons) and all(
        (entry.get("prototype_failures") or 0) <= FROZEN["prototype_failures_max"] for entry in comparisons
    )

    full_outcome = report["outcome_scope"]["full_outcome"]
    performance_criteria_met = bool(measurement == "GREEN" and failures_ok and performance_ok)
    if reasons or measurement != "GREEN":
        recommendation = "NO_ADOPTION_RECOMMENDATION — measurement is RED"
    elif full_outcome == "MEASURED" and performance_criteria_met:
        recommendation = "ADOPTION_ELIGIBLE"
    elif full_outcome == "MEASURED":
        recommendation = "DO_NOT_ADOPT — frozen comparison threshold failed"
    elif performance_criteria_met:
        recommendation = "NO_ADOPTION_RECOMMENDATION — full outcome UNMEASURED"
    else:
        recommendation = "NO_ADOPTION_RECOMMENDATION — full outcome UNMEASURED; frozen comparison threshold failed"

    if report["binding"] == "UNBOUND":
        recommendation = "NO_ADOPTION_RECOMMENDATION — report is UNBOUND"

    # Deliberately no PASS token: an unbound or partial run must never look green.
    return {
        "measurement": measurement,
        "recommendation": recommendation,
        "reasons": reasons,
        "full_outcome": full_outcome,
        "performance_criteria_met": performance_criteria_met,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Persistent decoder CPU baseline + keyframe/Range prototype (issue #703).",
        epilog="Measurement tool only: it binds a disposable 127.0.0.1 origin and accepts no target URL.",
    )
    parser.add_argument("--output", required=True, help="JSON report path")
    parser.add_argument("--tested-sha", default="", help="Full 40-hex commit the report is bound to")
    parser.add_argument("--profiles", nargs="+", choices=sorted(PROFILE_FPS), default=list(FROZEN["profiles"]))
    parser.add_argument("--ffmpeg", default=None, help="ffmpeg executable (default: PATH lookup)")
    parser.add_argument("--source-dir", default=None, help="Existing HLS mpegts source directory (source.m3u8 + seg*.ts)")
    parser.add_argument("--source-class", choices=["synthetic", "approved"], default="synthetic",
                        help="synthetic fixture or an approved representative source")
    parser.add_argument("--labeled-events", default=None,
                        help="Optional labeled event file; without it full outcome stays UNMEASURED")
    parser.add_argument("--source-seconds", type=float, default=FROZEN["source_seconds"])
    parser.add_argument("--warmup-seconds", type=float, default=FROZEN["warmup_seconds"])
    parser.add_argument("--window-seconds", type=float, default=FROZEN["window_seconds"])
    parser.add_argument("--windows", type=int, default=FROZEN["windows"])
    parser.add_argument("--poll-seconds", type=float, default=FROZEN["poll_seconds"])
    parser.add_argument("--range-bytes", type=int, default=FROZEN["range_bytes"])
    parser.add_argument("--skip-baseline", action="store_true", help="Investigation only; makes the run non-frozen")
    parser.add_argument("--skip-prototype", action="store_true", help="Investigation only; makes the run non-frozen")
    args = parser.parse_args(argv)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    binding = binding_for_sha(args.tested_sha)
    ffmpeg_path = args.ffmpeg or shutil.which("ffmpeg")
    started = time.monotonic()

    report = {
        "contract": "issue-703-decoder-grab-baseline-v1",
        "issue": 703,
        "tested_sha": args.tested_sha.strip() or "UNBOUND",
        "binding": binding,
        "profile_selection": args.profiles,
        "frozen": FROZEN,
        "runtime": runtime_identity(ffmpeg_path) if ffmpeg_path else {"ffmpeg_build": "unavailable"},
        "source": {
            "class": args.source_class,
            "mode": "loaded" if args.source_dir else "generated",
            "path": None,
            "fingerprint": None,
            "segment_format": "mpegts",
            "codec": "h264",
            "source_fps": FROZEN["source_fps"],
            "resolution": f"{FROZEN['source_width']}x{FROZEN['source_height']}",
            "bitrate_kbps": FROZEN["source_bitrate_kbps"],
            "gop_seconds": FROZEN["source_gop_seconds"],
            "motion": FROZEN["source_motion"] if args.source_class == "synthetic" else "approved source",
            "hls_only": True,
        },
        "outcome_scope": {
            "workload_representativeness": "UNMEASURED",
            "labeled_events": "UNMEASURED",
            "full_outcome": "UNMEASURED",
            "notes": [
                "A generated moving-pattern fixture tests accounting and Range mechanics only.",
                "Without evidence the fixture represents target encoding/load and without detected labeled events the full outcome is UNMEASURED.",
                "Frame-ready latency is not detection latency.",
                "Both arms use HLS; the comparison is HLS-only.",
                "This is measurement only: no production flag, reader replacement or transport change.",
            ],
        },
        "arms": {"baseline": [], "prototype": []},
        "comparison": {"pairs": []},
        "decision": None,
        "not_executed": [],
        "duration_seconds": None,
    }

    if args.labeled_events:
        path = Path(args.labeled_events)
        if path.is_file():
            try:
                count = sum(1 for line in path.read_text().splitlines() if line.strip())
            except OSError:
                count = 0
            report["outcome_scope"]["labeled_events"] = f"present:{count}"
    if args.source_class == "approved":
        # Representativeness still needs an owner-approved provenance record.
        report["outcome_scope"]["workload_representativeness"] = "CLAIMED_BY_OPERATOR"
    if (
        args.source_class == "approved"
        and str(report["outcome_scope"]["labeled_events"]).startswith("present:")
        and int(str(report["outcome_scope"]["labeled_events"]).split(":", 1)[1]) > 0
    ):
        report["outcome_scope"]["full_outcome"] = "MEASURED"

    source_tmp = None
    try:
        if not ffmpeg_path:
            report["not_executed"].append("environment lacks ffmpeg")
        else:
            if args.source_dir:
                source_dir = Path(args.source_dir)
            else:
                source_tmp = Path(tempfile.mkdtemp(prefix="decoder-grab-source-"))
                source_dir = source_tmp
                generate_source(ffmpeg_path, source_dir, args.source_seconds)
            catalog = SegmentCatalog(source_dir)
            report["source"]["path"] = str(source_dir)
            report["source"]["fingerprint"] = fingerprint_source(catalog)
            report["source"]["segment_count"] = len(catalog.segments)
            report["source"]["duration_seconds"] = _round(catalog.total_duration, 3)
            needed = args.warmup_seconds + args.windows * args.window_seconds
            if catalog.total_duration + 1e-6 < needed:
                report["not_executed"].append(
                    f"source duration {catalog.total_duration:.1f}s shorter than frozen need {needed:.1f}s"
                )
                ffmpeg_path = None

        if ffmpeg_path:
            with Origin(catalog, FROZEN["playlist_window_segments"]) as origin:
                if not args.skip_baseline:
                    for profile in args.profiles:
                        report["arms"]["baseline"].append(
                            run_baseline(
                                ffmpeg_path,
                                origin,
                                profile,
                                args.window_seconds,
                                args.windows,
                                args.warmup_seconds,
                            )
                        )
                if not args.skip_prototype:
                    for profile in args.profiles:
                        harness_before = read_proc_cpu(os.getpid())
                        t_before = time.monotonic()
                        row = run_prototype(
                            ffmpeg_path,
                            origin,
                            profile,
                            args.window_seconds,
                            args.windows,
                            args.warmup_seconds,
                            args.poll_seconds,
                            args.range_bytes,
                        )
                        elapsed = time.monotonic() - t_before
                        harness_after = read_proc_cpu(os.getpid())
                        if row.get("status") == "MEASURED":
                            measure_prototype_cpu(row, harness_before, harness_after, elapsed)
                        report["arms"]["prototype"].append(row)
            report["comparison"] = compare_arms(report["arms"]["baseline"], report["arms"]["prototype"])
        else:
            report["not_executed"].append("decoder/prototype arms skipped")
    except Exception as exc:  # noqa: BLE001 - report, never fabricate
        report["not_executed"].append(f"run failed: {type(exc).__name__}: {exc}")
    finally:
        if source_tmp is not None:
            shutil.rmtree(source_tmp, ignore_errors=True)
        report["duration_seconds"] = _round(time.monotonic() - started, 3)
        if report.get("comparison", {}).get("pairs") is None:
            report["comparison"] = {"pairs": []}
        report["decision"] = build_decision(report)
        output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        print(f"report: {output}")
        print(f"binding: {report['binding']} tested_sha={report['tested_sha']}")
        print(f"measurement: {report['decision']['measurement']}")
        print(f"recommendation: {report['decision']['recommendation']}")
        for reason in report["decision"]["reasons"]:
            print(f"  - {reason}")
        for name in report["not_executed"]:
            print(f"NOT EXECUTED: {name}")

    if report["decision"]["measurement"] != "GREEN" or report["decision"]["reasons"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
