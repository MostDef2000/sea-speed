#!/usr/bin/env python3
"""Ubuntu worker entrypoint with bounded FFmpeg RTSP ingestion."""
from __future__ import annotations

import os
import select
import subprocess
import time
from urllib.parse import urlsplit

import numpy as np

import hls_motion_yolo_worker_events as worker


_ORIGINAL_START_MEDIA_READER = worker.start_media_reader


def _media_scheme(input_url: str) -> str:
    try:
        return urlsplit(input_url).scheme.lower()
    except Exception:
        return ""


def _spawn_rtsp_ffmpeg(
    input_url: str,
    width: int,
    height: int,
    sample_fps: float,
) -> subprocess.Popen:
    if sample_fps <= 0:
        raise RuntimeError("SAMPLE_FPS must be greater than zero")

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-rtsp_transport",
        "tcp",
        "-i",
        input_url,
        "-an",
        "-sn",
        "-dn",
        "-vf",
        f"fps={sample_fps},scale={width}:{height}",
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]

    print("Starting bounded FFmpeg RTSP reader")
    print(f"HLS: {worker.safe_media_input_label(input_url)}")
    print(f"Frame: {width}x{height}")
    print(f"Sample FPS: {sample_fps}")

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
        close_fds=True,
    )


class ResilientFFmpegRtspReader:
    def __init__(self, input_url: str, width: int, height: int, sample_fps: float):
        self.input_url = input_url
        self.input_label = worker.safe_media_input_label(input_url)
        self.width = width
        self.height = height
        self.sample_fps = sample_fps
        self.frame_size = width * height * 3
        self.frame_timeout_sec = max(
            1.0,
            worker.env_float("RTSP_FRAME_TIMEOUT_SEC", 12.0),
        )
        self.restart_limit = max(
            1,
            worker.env_int("RTSP_READER_MAX_RESTARTS", 3),
        )
        self.restart_backoff_sec = max(
            0.0,
            worker.env_float("RTSP_READER_RESTART_BACKOFF_SEC", 1.0),
        )
        self.proc = self._spawn()

    def _spawn(self):
        return _spawn_rtsp_ffmpeg(
            self.input_url,
            self.width,
            self.height,
            self.sample_fps,
        )

    def _stop_process(self) -> None:
        proc = self.proc
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=2.0)
        except Exception:
            pass

    def _restart(self, attempt: int, reason: str) -> None:
        print(
            f"RTSP reader restart attempt={attempt}/{self.restart_limit} "
            f"reason={reason} source={self.input_label}"
        )
        self._stop_process()
        if self.restart_backoff_sec:
            time.sleep(self.restart_backoff_sec)
        self.proc = self._spawn()

    def _read_exact_bounded(self) -> bytes:
        if self.proc is None or self.proc.stdout is None:
            raise EOFError("ffmpeg stdout unavailable")

        fd = self.proc.stdout.fileno()
        data = bytearray()
        deadline = time.monotonic() + self.frame_timeout_sec

        while len(data) < self.frame_size:
            if self.proc.poll() is not None:
                raise EOFError("ffmpeg exited")

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("frame timeout")

            ready, _, _ = select.select([fd], [], [], remaining)
            if not ready:
                raise TimeoutError("frame timeout")

            chunk = os.read(fd, min(1024 * 1024, self.frame_size - len(data)))
            if not chunk:
                raise EOFError("ffmpeg stream ended")
            data.extend(chunk)

        return bytes(data)

    def read_frame(self):
        for attempt in range(self.restart_limit + 1):
            try:
                raw = self._read_exact_bounded()
                return np.frombuffer(raw, np.uint8).reshape(
                    (self.height, self.width, 3)
                )
            except (TimeoutError, EOFError, OSError) as exc:
                if attempt >= self.restart_limit:
                    raise RuntimeError(
                        f"RTSP FFmpeg reader exhausted restart budget: {self.input_label}"
                    ) from None
                self._restart(attempt + 1, type(exc).__name__)

        raise RuntimeError(
            f"RTSP FFmpeg reader exhausted restart budget: {self.input_label}"
        )

    def close(self) -> None:
        self._stop_process()


def start_media_reader(av_module=None):
    input_url = worker.env_str("HLS_URL")
    if not input_url:
        raise RuntimeError("HLS_URL is not set")

    if _media_scheme(input_url) != "rtsp":
        return _ORIGINAL_START_MEDIA_READER(av_module=av_module)

    width = worker.env_int("FRAME_WIDTH", 704)
    height = worker.env_int("FRAME_HEIGHT", 576)
    sample_fps = worker.env_float("SAMPLE_FPS", 5.0)
    return ResilientFFmpegRtspReader(input_url, width, height, sample_fps)


worker.start_media_reader = start_media_reader


if __name__ == "__main__":
    worker.main()
