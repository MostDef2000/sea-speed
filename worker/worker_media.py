"""Sea Speed worker media layer (issue #397, wave 2).

Reader/media process code moved VERBATIM (move-only refactor, AST-identical
bodies) from hls_motion_yolo_worker_events.py: the ffmpeg HLS reader, the
in-process RTSP reader, their process/frame helpers and the reader seam.

Import policy (guarded by tests/test_worker_media_module.py): top-level
imports are limited to the media allowlist - cv2/numpy/subprocess/os/time/
pathlib/datetime/urllib.parse/typing plus the repo-pure siblings
worker_kernel (env + media-identity helpers) and analytics_profiles (frame
size). `av` stays a LAZY import inside RtspFrameReader (raising a runtime
error when PyAV is absent); hoisting it (or adding ultralytics/requests)
to module level fails the import-allowlist gate.
"""

import subprocess
import time

import numpy as np

from analytics_profiles import get_profile
from worker_kernel import (
    _media_input_scheme,
    env_float,
    env_int,
    env_str,
    media_basic_auth_for_input,
    safe_media_input_label,
)


def _resolve_frame_size() -> tuple[int, int]:
    profile_name = env_str("ANALYTICS_PROFILE", "water-v1")
    try:
        profile = get_profile(profile_name)
        default_w, default_h = int(profile.frame_width), int(profile.frame_height)
    except Exception:
        default_w, default_h = 1920, 1080
    return env_int("FRAME_WIDTH", default_w), env_int("FRAME_HEIGHT", default_h)


def start_ffmpeg():
    hls_url = env_str("HLS_URL")
    if not hls_url:
        raise RuntimeError("HLS_URL is not set")

    try:
        from analytics_profiles import get_profile as _get_profile

        _profile = _get_profile(env_str("ANALYTICS_PROFILE", "water-v1"))
        _default_w, _default_h = int(_profile.frame_width), int(_profile.frame_height)
    except Exception:
        _default_w, _default_h = 1920, 1080
    width = env_int("FRAME_WIDTH", _default_w)
    height = env_int("FRAME_HEIGHT", _default_h)
    sample_fps = env_float("SAMPLE_FPS", 5.0)
    auth = media_basic_auth_for_input(hls_url)

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
    ]

    if auth:
        cmd += [
            "-headers",
            f"Authorization: Basic {auth}\r\n",
        ]

    cmd += [
        "-i",
        hls_url,
        "-vf",
        f"fps={sample_fps},scale={width}:{height}",
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]

    print("Starting FFmpeg HLS reader")
    print(f"HLS: {safe_media_input_label(hls_url)}")
    print(f"Frame: {width}x{height}")
    print(f"Sample FPS: {sample_fps}")

    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=10**8,
    )


def read_exact(pipe, size):
    data = bytearray()
    while len(data) < size:
        chunk = pipe.read(size - len(data))
        if not chunk:
            return None
        data.extend(chunk)
    return bytes(data)


def _frame_time_seconds(frame):
    pts = getattr(frame, "pts", None)
    time_base = getattr(frame, "time_base", None)
    if pts is not None and time_base is not None:
        try:
            return float(pts * time_base)
        except Exception:
            pass
    return time.monotonic()


class FFmpegFrameReader:
    def __init__(self, proc, width, height):
        self.proc = proc
        self.width = width
        self.height = height
        self.frame_size = width * height * 3

    def read_frame(self):
        raw = read_exact(self.proc.stdout, self.frame_size)
        if raw is None:
            return None
        return np.frombuffer(raw, np.uint8).reshape((self.height, self.width, 3))

    def close(self):
        try:
            self.proc.kill()
        except Exception:
            pass


class RtspFrameReader:
    def __init__(self, input_url, width, height, sample_fps, av_module=None):
        if sample_fps <= 0:
            raise RuntimeError("SAMPLE_FPS must be greater than zero")
        if av_module is None:
            try:
                import av as av_module
            except ImportError:
                raise RuntimeError("RTSP input requires the PyAV runtime dependency") from None
        self._av = av_module
        self._input_label = safe_media_input_label(input_url)
        self._width = width
        self._height = height
        self._sample_interval = 1.0 / float(sample_fps)
        self._next_sample_ts = None
        try:
            with self._av.logging.Capture(local=False):
                self._container = self._av.open(input_url, mode="r")
            self._frames = self._container.decode(video=0)
        except Exception:
            raise RuntimeError(f"RTSP media open failed: {self._input_label}") from None

    def read_frame(self):
        while True:
            try:
                with self._av.logging.Capture(local=False):
                    frame = next(self._frames)
            except StopIteration:
                return None
            except Exception:
                raise RuntimeError(f"RTSP media read failed: {self._input_label}") from None
            frame_ts = _frame_time_seconds(frame)
            if self._next_sample_ts is None:
                self._next_sample_ts = frame_ts
            if frame_ts + 1e-9 < self._next_sample_ts:
                continue
            while self._next_sample_ts <= frame_ts + 1e-9:
                self._next_sample_ts += self._sample_interval
            try:
                return frame.reformat(width=self._width, height=self._height, format="bgr24").to_ndarray()
            except Exception:
                raise RuntimeError(f"RTSP frame conversion failed: {self._input_label}") from None

    def close(self):
        try:
            self._container.close()
        except Exception:
            pass


def start_media_reader(av_module=None):
    input_url = env_str("HLS_URL")
    if not input_url:
        raise RuntimeError("HLS_URL is not set")
    width, height = _resolve_frame_size()
    sample_fps = env_float("SAMPLE_FPS", 5.0)
    if _media_input_scheme(input_url) == "rtsp":
        print("Starting in-process RTSP reader")
        print(f"HLS: {safe_media_input_label(input_url)}")
        print(f"Frame: {width}x{height}")
        print(f"Sample FPS: {sample_fps}")
        return RtspFrameReader(input_url, width, height, sample_fps, av_module=av_module)
    return FFmpegFrameReader(start_ffmpeg(), width, height)
