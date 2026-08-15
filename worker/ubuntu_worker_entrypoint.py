#!/usr/bin/env python3
"""Ubuntu worker entrypoint with bounded media and AI execution boundaries."""
from __future__ import annotations

import json
import os
import select
import struct
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import numpy as np

import hls_motion_yolo_worker_events as worker


_ORIGINAL_START_MEDIA_READER = worker.start_media_reader
_LENGTH = struct.Struct("!I")


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


class BoundedYoloSupervisor:
    def __init__(self) -> None:
        self.model_name = worker.env_str("MODEL_NAME", "yolo11s.pt")
        self.tracker = worker.env_str("YOLO_TRACKER", "bytetrack.yaml").strip() or "bytetrack.yaml"
        self.image_size = worker.env_int("YOLO_IMAGE_SIZE", 960)
        self.confidence = worker.env_float("YOLO_CONFIDENCE", 0.25)
        self.device = worker.env_str("YOLO_DEVICE", "0").strip() or "0"
        self.timeout_sec = max(1.0, worker.env_float("AI_INFERENCE_TIMEOUT_SEC", 12.0))
        self.startup_timeout_sec = max(
            self.timeout_sec,
            worker.env_float("AI_INFERENCE_STARTUP_TIMEOUT_SEC", 35.0),
        )
        self.backoff_sec = max(0.0, worker.env_float("AI_INFERENCE_BACKOFF_SEC", 5.0))
        self.child_path = Path(__file__).with_name("ubuntu_ai_inference_worker.py")
        self.proc: subprocess.Popen | None = None
        self.degraded_until = 0.0
        self._spawn("startup")

    def _spawn(self, reason: str) -> None:
        self.close()
        if not self.child_path.is_file():
            raise RuntimeError(f"AI inference child missing: {self.child_path}")
        self.proc = subprocess.Popen(
            [
                sys.executable,
                str(self.child_path),
                "--model",
                self.model_name,
                "--tracker",
                self.tracker,
                "--image-size",
                str(self.image_size),
                "--confidence",
                str(self.confidence),
                "--device",
                self.device,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            bufsize=0,
            close_fds=True,
        )
        print(f"AI inference child restart reason={reason} device={self.device}")

    def close(self) -> None:
        proc = self.proc
        self.proc = None
        if proc is None:
            return
        try:
            if proc.poll() is None:
                proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=3.0)
        except Exception:
            pass

    def _read_exact_bounded(self, size: int, deadline: float) -> bytes:
        proc = self.proc
        if proc is None or proc.stdout is None:
            raise EOFError("AI inference stdout unavailable")
        fd = proc.stdout.fileno()
        data = bytearray()
        while len(data) < size:
            if proc.poll() is not None:
                raise EOFError("AI inference child exited")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("AI inference timeout")
            ready, _, _ = select.select([fd], [], [], remaining)
            if not ready:
                raise TimeoutError("AI inference timeout")
            chunk = os.read(fd, size - len(data))
            if not chunk:
                raise EOFError("AI inference protocol ended")
            data.extend(chunk)
        return bytes(data)

    def _roundtrip(self, frame: np.ndarray, timeout_sec: float) -> list[dict[str, object]]:
        proc = self.proc
        if proc is None or proc.stdin is None:
            raise EOFError("AI inference stdin unavailable")
        if frame.ndim != 3 or frame.shape[2] != 3 or frame.dtype != np.uint8:
            raise ValueError("AI inference frame must be uint8 HxWx3")

        contiguous = np.ascontiguousarray(frame)
        raw = contiguous.tobytes()
        header = json.dumps(
            {
                "width": int(contiguous.shape[1]),
                "height": int(contiguous.shape[0]),
                "channels": 3,
                "frame_size": len(raw),
            },
            separators=(",", ":"),
        ).encode("utf-8")
        proc.stdin.write(_LENGTH.pack(len(header)))
        proc.stdin.write(header)
        proc.stdin.write(raw)
        proc.stdin.flush()

        deadline = time.monotonic() + timeout_sec
        response_size = _LENGTH.unpack(
            self._read_exact_bounded(_LENGTH.size, deadline)
        )[0]
        if response_size <= 0 or response_size > 4 * 1024 * 1024:
            raise RuntimeError("invalid AI inference response size")
        payload = json.loads(
            self._read_exact_bounded(response_size, deadline).decode("utf-8")
        )
        if not isinstance(payload, dict) or payload.get("ok") is not True:
            error = payload.get("error") if isinstance(payload, dict) else "invalid_response"
            raise RuntimeError(f"AI inference child error: {error}")
        detections = payload.get("detections")
        if not isinstance(detections, list):
            raise RuntimeError("AI inference detections response is invalid")
        return detections

    def startup_self_test(self) -> None:
        height = worker.env_int("FRAME_HEIGHT", 576)
        width = worker.env_int("FRAME_WIDTH", 704)
        first = np.zeros((height, width, 3), dtype=np.uint8)
        second = first.copy()
        y1 = max(0, height // 3)
        y2 = min(height, y1 + max(8, height // 10))
        x1 = max(0, width // 3)
        x2 = min(width, x1 + max(8, width // 10))
        second[y1:y2, x1:x2] = 255

        for sequence, frame in enumerate((first, second), start=1):
            detections = self._roundtrip(frame, self.startup_timeout_sec)
            print(
                f"AI inference self-test ok sequence={sequence}/2 "
                f"detections={len(detections)} device={self.device}"
            )

        self._spawn("post_self_test_tracker_reset")
        print("AI inference ready self_test_sequence=2")

    def detect(self, frame: np.ndarray) -> list[dict[str, object]]:
        if time.monotonic() < self.degraded_until:
            return []
        try:
            detections = self._roundtrip(frame, self.timeout_sec)
            print(f"AI inference ok detections={len(detections)}")
            return detections
        except (TimeoutError, EOFError, OSError, RuntimeError, ValueError) as exc:
            print(f"AI inference degraded reason={type(exc).__name__}")
            try:
                self._spawn(type(exc).__name__)
            except Exception as restart_exc:
                print(f"AI inference degraded reason=restart_{type(restart_exc).__name__}")
            self.degraded_until = time.monotonic() + self.backoff_sec
            return []


class _ModelSentinel:
    def __init__(self, _model_name: str):
        pass


_supervisor: BoundedYoloSupervisor | None = None


def supervised_detect_vehicles(_model, frame):
    if _supervisor is None:
        raise RuntimeError("AI inference supervisor is not initialized")
    return _supervisor.detect(frame)


worker.start_media_reader = start_media_reader
worker.YOLO = _ModelSentinel
worker.detect_vehicles = supervised_detect_vehicles


if __name__ == "__main__":
    try:
        _supervisor = BoundedYoloSupervisor()
        _supervisor.startup_self_test()
        worker.main()
    finally:
        if _supervisor is not None:
            _supervisor.close()
