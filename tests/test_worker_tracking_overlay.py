from __future__ import annotations

import ast
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

try:
    from tests.support import worker_source
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import worker_source


def load_functions(names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    # 398-wave-a: shared AST-slice+exec harness (was a private duplicate pinned
    # to one path) — tests/support/worker_source.py resolves the worker source
    # so the #397 decomposition can move functions between files.
    return worker_source.load_functions(names, namespace)


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
        # 398-wave-a: converted from source-text pin (was L205-211) — now
        # behavioral: the profiled detector path must (a) strip the
        # ANALYTICS_PROFILE env value before profile lookup, (b) map model
        # classes through normalize_model_class(model_class, profile.name),
        # and (c) feed tracker/confidence/image-size defaults from the profile
        # into model.track, instead of pinning those behaviors to literal
        # source lines.
        received_profile_names: list[str] = []

        class Profile:
            name = "water-v1"
            confidence = 0.15
            image_size = 960
            tracker = "profile-tracker.yaml"

        profile = Profile()

        def get_profile(name: str) -> Profile:
            received_profile_names.append(name)
            if name == "water-v1":
                return profile
            raise ValueError(name)

        def normalize_model_class(model_class: str, profile_name: str) -> dict[str, Any] | None:
            if profile_name != "water-v1" or model_class != "boat":
                return None
            return {
                "analytics_profile": "water-v1",
                "domain": "water",
                "object_type": "vessel",
                "model_class": "boat",
                "class_name": "vessel",
            }

        class ProfiledResult:
            names = {2: "boat"}
            boxes = FakeBoxes()

        class ProfiledModel(FakeModel):
            def track(self, _frame: object, **kwargs: Any) -> list[Any]:  # type: ignore[override]
                self.calls.append(kwargs)
                return [ProfiledResult()]

        ns: dict[str, Any] = {
            "env_float": lambda _name, default: default,
            "env_int": lambda _name, default: default,
            # whitespace-padded ANALYTICS_PROFILE proves the env value is
            # .strip()ed before profile lookup (was the
            # `profile_name = env_str(...).strip()` pin); every other read
            # falls through to its default so profile values flow through.
            "env_str": lambda name, default="": " water-v1 " if name == "ANALYTICS_PROFILE" else default,
            "get_profile": get_profile,
            "normalize_model_class": normalize_model_class,
            "VEHICLE_CLASSES": {"car", "truck", "bus", "motorcycle", "bicycle"},
        }
        load_functions({"detect_vehicles"}, ns)
        model = ProfiledModel()
        detections = ns["detect_vehicles"](model, object())
        self.assertEqual(received_profile_names, ["water-v1"], "ANALYTICS_PROFILE must be stripped before profile lookup")
        self.assertTrue(model.calls[0]["persist"])
        self.assertEqual(model.calls[0]["tracker"], profile.tracker, "tracker default must come from the profile")
        self.assertEqual(model.calls[0]["conf"], 0.15, "confidence default must come from the profile")
        self.assertEqual(model.calls[0]["imgsz"], 960, "image-size default must come from the profile")
        self.assertEqual(len(detections), 1)
        self.assertEqual(detections[0]["class_name"], "vessel")
        self.assertEqual(detections[0]["model_class"], "boat")
        self.assertEqual(detections[0]["object_type"], "vessel")

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
        # 398-wave-a: converted from source-text pin (was L240-247) — the
        # label backdrop must be blended translucently: the label layer is a
        # copy of the frame, blended via cv2.addWeighted with an opacity
        # resolved from overlay_label_opacity().
        draw = worker_source.function_node("draw_overlay")
        self.assertTrue(
            any(
                worker_source.dump(a.value) == worker_source.expr_dump("out.copy()")
                for a in worker_source.find_assignments(draw, "label_layer")
            ),
            "the label layer must be a copy of the rendered frame",
        )
        self.assertTrue(worker_source.method_calls(draw, "cv2", "addWeighted"), "the label layer must be blended via cv2.addWeighted")
        opacity_assigns = worker_source.find_assignments(draw, "opacity")
        self.assertTrue(
            any(worker_source.dump(a.value) == worker_source.expr_dump("overlay_label_opacity()") for a in opacity_assigns),
            "label opacity must come from overlay_label_opacity()",
        )

    def test_water_live_speed_is_owned_by_passage_state(self) -> None:
        # 398-wave-a: converted from source-text pin (was L249-263) — inside
        # main(): the calibrated line-speed telemetry is computed per detection
        # BEFORE the passage engine consumes the detections, the passage owns
        # the published live speed fields (speed_kmh/speed_source read from
        # the passage result), the retired instant-speed injection stays
        # removed, and update_speed_lines_estimate keeps the
        # speed_sample_fresh flag (False default, True on fresh samples).
        main_node = worker_source.function_node("main")
        ingress_nodes = worker_source.find_stmt(main_node, 'det["_line_speed_info"] = update_speed_lines_estimate(det)')
        self.assertTrue(ingress_nodes, "water path must compute calibrated line-speed telemetry per detection")
        passage_nodes = worker_source.find_stmt(main_node, "passage_updates = passage_engine.update(detections, now)")
        self.assertTrue(passage_nodes, "the passage engine must own the live speed state")
        self.assertLess(
            min(node.lineno for node in ingress_nodes),
            min(node.lineno for node in worker_source.find_stmt(main_node, "passage_updates = passage_engine.update(detections, now)")),
            "calibrated telemetry must be computed before the passage engine update",
        )
        self.assertTrue(
            worker_source.find_stmt(main_node, 'det["speed_kmh"] = passage.get("speed_kmh")'),
            "live speed_kmh must be owned by the passage state",
        )
        self.assertTrue(
            worker_source.find_stmt(main_node, 'det["speed_source"] = passage.get("speed_method")'),
            "live speed_source must be owned by the passage state",
        )
        self.assertEqual(
            worker_source.find_stmt(main_node, '_det["speed_kmh"] = _inst'),
            [],
            "the retired instant-speed injection must stay removed",
        )
        estimate_node = worker_source.function_node("update_speed_lines_estimate")
        fresh_defaults = [
            node
            for node in ast.walk(estimate_node)
            if isinstance(node, ast.Dict)
            and any(
                isinstance(key, ast.Constant)
                and key.value == "speed_sample_fresh"
                and isinstance(value, ast.Constant)
                and value.value is False
                for key, value in zip(node.keys, node.values)
            )
        ]
        self.assertTrue(fresh_defaults, "speed_sample_fresh must default to False in the speed info payload")
        self.assertTrue(
            worker_source.find_stmt(estimate_node, 'info["speed_sample_fresh"] = True'),
            "speed_sample_fresh must flip to True for fresh samples",
        )


if __name__ == "__main__":
    unittest.main()
