from __future__ import annotations

import ast
import copy
import io
import json
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

    def test_recall_diagnostics_sink_does_not_change_detector_result(self) -> None:
        ns: dict[str, Any] = {
            "env_float": lambda _name, default: default,
            "env_int": lambda _name, default: default,
            "env_str": lambda _name, default="": default,
            "VEHICLE_CLASSES": {"car", "truck", "bus", "motorcycle", "bicycle"},
        }
        load_functions({"detect_vehicles"}, ns)
        baseline = ns["detect_vehicles"](FakeModel(), object())
        records: list[dict[str, Any]] = []
        instrumented = ns["detect_vehicles"](FakeModel(), object(), diagnostics=records)
        self.assertEqual(instrumented, baseline)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["model_class"], "car")
        self.assertEqual(records[0]["confidence"], 0.91)
        self.assertEqual(records[0]["bbox_xyxy"], [10, 20, 41, 61])
        self.assertEqual(records[0]["bbox_width_px"], 31)
        self.assertEqual(records[0]["bbox_height_px"], 41)
        self.assertEqual(records[0]["track_id"], 17)
        self.assertTrue(records[0]["track_assigned"])
        self.assertTrue(records[0]["class_mapping_accepted"])

    def test_water_recall_diagnostics_are_bounded_and_stage_explicit(self) -> None:
        class Profile:
            name = "water-v1"
            domain = "water"
            model_name = "models/yolo26x.pt"
            image_size = 960
            confidence = 0.15
            tracker = "bytetrack.yaml"

        values = {
            "WATER_RECALL_DIAGNOSTICS_INTERVAL_SEC": "10",
            "WATER_RECALL_DIAGNOSTICS_MAX_RECORDS": "1",
        }
        ns: dict[str, Any] = {
            "time": type("FakeTime", (), {"monotonic": staticmethod(lambda: 100.0)}),
            "json": json,
            "env_str": lambda name, default="": values.get(name, default),
            "env_int": lambda name, default: int(values.get(name, default)),
            "env_float": lambda name, default: float(values.get(name, default)),
            "water_recall_diagnostics_enabled": lambda: True,
            "detection_inside_road_roi": lambda det, points=None: det["bbox_xyxy"][0] < 50 and len(points or []) >= 3,
            "_WATER_RECALL_DIAGNOSTIC_STATE": {"last_emit_mono": 0.0},
        }
        load_functions({"maybe_emit_water_recall_diagnostics"}, ns)
        raw = [
            {
                "model_class": "boat", "confidence": 0.81, "bbox_xyxy": [10, 20, 40, 60],
                "bbox_width_px": 30, "bbox_height_px": 40, "bbox_area_px": 1200,
                "track_id": 7, "track_assigned": True, "class_mapping_accepted": True, "semantic_class": "vessel",
            },
            {
                "model_class": "car", "confidence": 0.77, "bbox_xyxy": [80, 20, 120, 60],
                "bbox_width_px": 40, "bbox_height_px": 40, "bbox_area_px": 1600,
                "track_id": None, "track_assigned": False, "class_mapping_accepted": False, "semantic_class": None,
            },
        ]
        accepted = [{"track_id": 7, "bbox_xyxy": [10, 20, 40, 60], "class_name": "vessel"}]
        output = io.StringIO()
        with redirect_stdout(output):
            emitted = ns["maybe_emit_water_recall_diagnostics"](42, raw, [(0, 0), (100, 0), (100, 100)], accepted, Profile())
            emitted_again = ns["maybe_emit_water_recall_diagnostics"](43, raw, [(0, 0), (100, 0), (100, 100)], accepted, Profile())
        self.assertTrue(emitted)
        self.assertFalse(emitted_again)
        line = output.getvalue().strip()
        self.assertTrue(line.startswith("WATER_RECALL_DIAGNOSTIC "))
        payload = json.loads(line.split(" ", 1)[1])
        self.assertEqual(payload["schema"], "sea_speed_water_recall_diagnostic_v1")
        self.assertEqual(payload["frame_no"], 42)
        self.assertEqual(payload["detector"]["confidence_threshold"], 0.15)
        self.assertEqual(payload["roi"]["processing_mode"], "masked_before_inference")
        self.assertEqual(payload["roi"]["post_filter"], "bbox_center")
        self.assertEqual(payload["counts"]["post_threshold_raw"], 2)
        self.assertEqual(payload["counts"]["class_mapping_accepted"], 1)
        self.assertEqual(payload["counts"]["track_assigned"], 1)
        self.assertEqual(payload["counts"]["accepted_after_roi"], 1)
        self.assertTrue(payload["records_truncated"])
        self.assertEqual(len(payload["records"]), 1)
        self.assertTrue(payload["records"][0]["roi_center_inside"])
        self.assertTrue(payload["records"][0]["accepted_after_roi"])
        self.assertNotIn("SEA_SPEED_API_TOKEN", line)
        self.assertNotIn("HLS_URL", line)

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

    def test_water_live_speed_is_owned_by_passage_state(self) -> None:
        source = SOURCE.read_text(encoding="utf-8-sig")
        start = source.index("if is_water and passage_engine is not None:")
        end = source.index("crossing_snapshot = crossing_overlay_summary()", start)
        water = source[start:end]
        ingress = 'det["_line_speed_info"] = update_speed_lines_estimate(det)'
        passage_update = "passage_updates = passage_engine.update(detections, now)"
        self.assertIn(ingress, water)
        self.assertIn(passage_update, water)
        self.assertLess(water.index(ingress), water.index(passage_update))
        self.assertIn('det["speed_kmh"] = passage.get("speed_kmh")', water)
        self.assertIn('det["speed_source"] = passage.get("speed_method")', water)
        self.assertNotIn('_det["speed_kmh"] = _inst', water)
        self.assertIn('"speed_sample_fresh": False', source)
        self.assertIn('info["speed_sample_fresh"] = True', source)


if __name__ == "__main__":
    unittest.main()
