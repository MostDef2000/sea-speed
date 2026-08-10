from __future__ import annotations

import ast
import copy
import io
import unittest
from contextlib import redirect_stdout
from fractions import Fraction
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "worker/hls_motion_yolo_worker_events.py"


def load_definitions(names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"), filename=str(SOURCE))
    selected = []
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            selected.append(copy.deepcopy(node))
            found.add(node.name)
    missing = names - found
    if missing:
        raise AssertionError(f"missing worker definitions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


class FakePipe:
    def read(self, _size: int) -> bytes:
        return b""


class FakeProcess:
    def __init__(self) -> None:
        self.stdout = FakePipe()
        self.killed = False

    def kill(self) -> None:
        self.killed = True


class FakeSubprocess:
    PIPE = object()
    calls: list[tuple[list[str], dict[str, Any]]] = []

    @classmethod
    def Popen(cls, cmd: list[str], **kwargs: Any) -> FakeProcess:
        cls.calls.append((list(cmd), dict(kwargs)))
        return FakeProcess()


class FakeCapture:
    entries = 0

    def __init__(self, local: bool = True) -> None:
        self.local = local

    def __enter__(self) -> list[object]:
        type(self).entries += 1
        return []

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class FakeLogging:
    Capture = FakeCapture


class FakeFrame:
    def __init__(self, pts: int, payload: str) -> None:
        self.pts = pts
        self.time_base = Fraction(1, 25)
        self.payload = payload
        self.reformat_calls: list[dict[str, Any]] = []

    def reformat(self, **kwargs: Any) -> "FakeFrame":
        self.reformat_calls.append(dict(kwargs))
        return self

    def to_ndarray(self) -> str:
        return self.payload


class FakeContainer:
    def __init__(self, frames: list[FakeFrame]) -> None:
        self.frames = frames
        self.decode_calls: list[dict[str, int]] = []
        self.closed = False

    def decode(self, **kwargs: int):
        self.decode_calls.append(dict(kwargs))
        return iter(self.frames)

    def close(self) -> None:
        self.closed = True


class FakeAV:
    logging = FakeLogging()
    open_calls: list[tuple[str, str]] = []
    frames: list[FakeFrame] = []
    last_container: FakeContainer | None = None
    fail_open = False

    @classmethod
    def open(cls, url: str, mode: str = "r") -> FakeContainer:
        cls.open_calls.append((url, mode))
        if cls.fail_open:
            raise RuntimeError("credential-bearing fake failure " + url)
        cls.last_container = FakeContainer(list(cls.frames))
        return cls.last_container


class WorkerRtspMediaSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeSubprocess.calls = []
        FakeCapture.entries = 0
        FakeAV.open_calls = []
        FakeAV.frames = []
        FakeAV.last_container = None
        FakeAV.fail_open = False

    def _namespace(self, values: dict[str, str]) -> dict[str, Any]:
        def env_str(name: str, default: str = "") -> str:
            return values.get(name, default)

        def env_int(name: str, default: int) -> int:
            try:
                return int(values.get(name, str(default)))
            except Exception:
                return default

        def env_float(name: str, default: float) -> float:
            try:
                return float(values.get(name, str(default)))
            except Exception:
                return default

        class FakeNumpy:
            uint8 = object()

            @staticmethod
            def frombuffer(_raw: bytes, _dtype: object):
                raise AssertionError("HTTP reader frame conversion was not expected")

        namespace: dict[str, Any] = {
            "env_str": env_str,
            "env_int": env_int,
            "env_float": env_float,
            "urlsplit": urlsplit,
            "subprocess": FakeSubprocess,
            "np": FakeNumpy,
            "time": __import__("time"),
        }
        return load_definitions(
            {
                "_media_input_scheme",
                "safe_media_input_label",
                "media_basic_auth_for_input",
                "read_exact",
                "start_ffmpeg",
                "_frame_time_seconds",
                "FFmpegFrameReader",
                "RtspFrameReader",
                "start_media_reader",
            },
            namespace,
        )

    def test_authenticated_rtsp_stays_in_process_and_out_of_child_argv(self) -> None:
        input_url = "rtsp://camera-user:camera-pass@192.0.2.10:554/Streaming/Channels/101"
        values = {
            "HLS_URL": input_url,
            "FRAME_WIDTH": "704",
            "FRAME_HEIGHT": "576",
            "SAMPLE_FPS": "5",
            "HLS_BASIC_AUTH_BASE64": "legacy-secret",
        }
        FakeAV.frames = [FakeFrame(0, "frame-0")]
        ns = self._namespace(values)

        output = io.StringIO()
        with redirect_stdout(output):
            reader = ns["start_media_reader"](av_module=FakeAV)

        self.assertEqual(FakeSubprocess.calls, [])
        self.assertEqual(FakeAV.open_calls, [(input_url, "r")])
        self.assertEqual(reader.read_frame(), "frame-0")
        self.assertGreaterEqual(FakeCapture.entries, 2)

        logged = output.getvalue()
        self.assertIn("HLS: rtsp://192.0.2.10:554", logged)
        self.assertNotIn("camera-user", logged)
        self.assertNotIn("camera-pass", logged)
        self.assertNotIn("legacy-secret", logged)

    def test_rtsp_reader_preserves_configured_sampling_and_frame_shape(self) -> None:
        values = {
            "HLS_URL": "rtsp://user:pass@192.0.2.10:554/stream",
            "FRAME_WIDTH": "704",
            "FRAME_HEIGHT": "576",
            "SAMPLE_FPS": "5",
        }
        FakeAV.frames = [FakeFrame(index, f"frame-{index}") for index in range(6)]
        ns = self._namespace(values)
        reader = ns["start_media_reader"](av_module=FakeAV)

        self.assertEqual(reader.read_frame(), "frame-0")
        self.assertEqual(reader.read_frame(), "frame-5")
        self.assertEqual(FakeAV.frames[0].reformat_calls[-1], {
            "width": 704,
            "height": 576,
            "format": "bgr24",
        })
        self.assertEqual(FakeAV.frames[5].reformat_calls[-1], {
            "width": 704,
            "height": 576,
            "format": "bgr24",
        })

    def test_rtsp_open_failure_redacts_credentials(self) -> None:
        input_url = "rtsp://camera-user:camera-pass@192.0.2.10:554/stream"
        ns = self._namespace({
            "HLS_URL": input_url,
            "SAMPLE_FPS": "5",
        })
        FakeAV.fail_open = True

        with self.assertRaises(RuntimeError) as raised:
            ns["start_media_reader"](av_module=FakeAV)

        message = str(raised.exception)
        self.assertEqual(message, "RTSP media open failed: rtsp://192.0.2.10:554")
        self.assertNotIn("camera-user", message)
        self.assertNotIn("camera-pass", message)

    def test_https_media_keeps_existing_ffmpeg_auth_path(self) -> None:
        input_url = "https://media.example/stream.m3u8"
        values = {
            "HLS_URL": input_url,
            "HLS_BASIC_AUTH_BASE64": "legacy-media-auth",
            "FRAME_WIDTH": "704",
            "FRAME_HEIGHT": "576",
            "SAMPLE_FPS": "5",
        }
        ns = self._namespace(values)

        reader = ns["start_media_reader"](av_module=FakeAV)

        self.assertEqual(FakeAV.open_calls, [])
        self.assertEqual(len(FakeSubprocess.calls), 1)
        cmd = FakeSubprocess.calls[0][0]
        self.assertEqual(cmd[cmd.index("-i") + 1], input_url)
        self.assertIn("-headers", cmd)
        self.assertIn("Authorization: Basic legacy-media-auth\r\n", cmd)
        reader.close()
        self.assertTrue(FakeSubprocess.calls[0][1]["stdout"] is FakeSubprocess.PIPE)


if __name__ == "__main__":
    unittest.main()
