from __future__ import annotations

import ast
import copy
import io
import time as real_time
import unittest
import uuid
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "worker/hls_motion_yolo_worker_events.py"


def load_functions(names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"), filename=str(SOURCE))
    selected = []
    found: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            selected.append(copy.deepcopy(node))
            found.add(node.name)
    missing = names - found
    if missing:
        raise AssertionError(f"missing worker functions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


class Scalar:
    def __init__(self, value: float): self.value = value
    def item(self) -> float: return self.value


class XYXY:
    def __init__(self, values: list[float]): self.values = values
    def __getitem__(self, _index: int) -> "XYXY": return self
    def tolist(self) -> list[float]: return list(self.values)


class FakeBox:
    cls = [Scalar(2)]
    conf = [Scalar(0.91)]
    xyxy = XYXY([10.2, 20.4, 40.6, 60.8])


class FakeBoxes(list):
    def __init__(self):
        super().__init__([FakeBox()])
        self.id = [Scalar(17)]


class FakeResult:
    names = {2: "car"}
    boxes = FakeBoxes()


class FakeModel:
    def __init__(self): self.calls: list[dict[str, Any]] = []
    def track(self, _frame: object, **kwargs: Any) -> list[FakeResult]:
        self.calls.append(kwargs)
        return [FakeResult()]


class FakeSubprocess:
    PIPE = object()
    calls: list[tuple[list[str], dict[str, Any]]] = []
    @classmethod
    def Popen(cls, cmd: list[str], **kwargs: Any) -> object:
        cls.calls.append((list(cmd), dict(kwargs)))
        return object()


class WorkerTrackingOverlayTests(unittest.TestCase):
    def test_rtsp_input_is_redacted_and_no_legacy_header_is_attached(self) -> None:
        input_url = "rtsp://camera-user:camera-pass@192.0.2.10:554/Streaming/Channels/101?token=query-secret#fragment-secret"
        values = {"HLS_URL": input_url, "HLS_BASIC_AUTH_BASE64": "legacy-secret"}
        ns: dict[str, Any] = {
            "env_str": lambda name, default="": values.get(name, default),
            "env_int": lambda _name, default: default,
            "env_float": lambda _name, default: default,
            "urlsplit": urlsplit,
            "subprocess": FakeSubprocess,
        }
        FakeSubprocess.calls = []
        load_functions({"_media_input_scheme", "safe_media_input_label", "media_basic_auth_for_input", "start_ffmpeg"}, ns)
        output = io.StringIO()
        with redirect_stdout(output): ns["start_ffmpeg"]()
        cmd = FakeSubprocess.calls[0][0]
        self.assertEqual(cmd[cmd.index("-i") + 1], input_url)
        self.assertNotIn("-headers", cmd)
        logged = output.getvalue()
        self.assertIn("HLS: rtsp://192.0.2.10:554", logged)
        for secret in ("camera-user", "camera-pass", "query-secret", "fragment-secret", "legacy-secret"):
            self.assertNotIn(secret, logged)

    def test_legacy_no_profile_bytetrack_contract_remains_compatible(self) -> None:
        ns: dict[str, Any] = {
            "env_float": lambda _name, default: default,
            "env_int": lambda _name, default: default,
            "env_str": lambda _name, default="": default,
            "VEHICLE_CLASSES": {"car", "truck", "bus", "motorcycle", "bicycle"},
        }
        load_functions({"detect_vehicles"}, ns)
        model = FakeModel()
        detections = ns["detect_vehicles"](model, object())
        self.assertTrue(model.calls[0]["persist"])
        self.assertEqual(model.calls[0]["tracker"], "bytetrack.yaml")
        self.assertEqual(model.calls[0]["conf"], 0.25)
        self.assertEqual(detections[0]["track_id"], 17)
        self.assertEqual(detections[0]["bbox_xyxy"], [10, 20, 41, 61])
        self.assertEqual(detections[0]["class_name"], "car")

    def test_profiled_detector_normalizes_water_boat_to_vessel(self) -> None:
        source = SOURCE.read_text(encoding="utf-8-sig")
        self.assertIn('profile_name = env_str("ANALYTICS_PROFILE", "").strip()', source)
        self.assertIn("normalize_model_class(model_class, profile.name)", source)
        self.assertIn('confidence_default = profile.confidence', source)
        self.assertIn('image_size_default = profile.image_size', source)
        self.assertIn('tracker_default = profile.tracker', source)

    def test_overlay_label_contains_id_and_speed_or_pending_marker(self) -> None:
        ns = load_functions({"format_detection_label"}, {})
        ready = ns["format_detection_label"]({"track_id": 23, "class_name": "vessel", "confidence": 0.874, "speed_kmh": 31.4})
        pending = ns["format_detection_label"]({"track_id": 24, "class_name": "truck", "confidence": 0.8, "speed_kmh": None})
        self.assertEqual(ready, "ID 23 | vessel 0.87 | 31.4 km/h")
        self.assertEqual(pending, "ID 24 | truck 0.80 | speed: --")

    def test_profiled_event_keeps_model_and_domain_semantics(self) -> None:
        ns: dict[str, Any] = {
            "fetch_speed_config": lambda: {"enabled": False, "kmh_per_px_s": 0.0},
            "time": real_time,
            "uuid": uuid,
            "now_iso": lambda: datetime.now(timezone.utc).isoformat(),
            "env_str": lambda name, default="": default,
        }
        load_functions({"convert_px_s_to_kmh", "build_event"}, ns)
        event = ns["build_event"]({
            "track_id": 31, "class_name": "vessel", "object_type": "vessel", "model_class": "boat",
            "analytics_profile": "water-v1", "domain": "water", "confidence": 0.9,
            "bbox_xyxy": [1, 2, 3, 4], "speed_kmh": 24.0, "speed_source": "detection_first_calibrated",
        }, 10, {}, {"speed_ready": True, "speed_kmh": 24.0, "speed_source": "detection_first_calibrated"})
        self.assertEqual(event["analytics_profile"], "water-v1")
        self.assertEqual(event["domain"], "water")
        self.assertEqual(event["object_type"], "vessel")
        self.assertEqual(event["model_class"], "boat")
        self.assertEqual(event["class_name"], "vessel")

    def test_overlay_uses_translucent_blending(self) -> None:
        source = SOURCE.read_text(encoding="utf-8-sig")
        start = source.index("def draw_overlay(")
        end = source.index("def post_state(", start)
        draw = source[start:end]
        self.assertIn("label_layer = out.copy()", draw)
        self.assertIn("cv2.addWeighted(", draw)
        self.assertIn("opacity = overlay_label_opacity()", draw)


if __name__ == "__main__":
    unittest.main()
