from __future__ import annotations

import ast
import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker" / "hls_motion_yolo_worker_events.py"
API = ROOT / "api" / "app" / "main.py"
PROFILES = ROOT / "worker" / "analytics_profiles.py"


class RoadProfilePersonTests(unittest.TestCase):
    def test_road_v1_class_map_includes_person(self) -> None:
        namespace: dict[str, Any] = {}
        exec(compile(PROFILES.read_text(encoding="utf-8"), str(PROFILES), "exec"), namespace)
        profile = namespace["get_profile"]("road-v1")
        self.assertIn("person", profile.model_classes)
        self.assertEqual(namespace["normalize_model_class"]("person", "road-v1")["object_type"], "person")
        water = namespace["get_profile"]("water-v1")
        self.assertNotIn("person", water.model_classes)


def load_worker_main() -> dict[str, Any]:
    """Extract the main() function body and locate the publication gate."""
    tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return {"node": node}
    raise AssertionError("main() not found in worker")


class WorkerEventGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main_node = load_worker_main()["node"]
        cls.source_lines = WORKER.read_text(encoding="utf-8").splitlines()

    def test_gate_requires_track_and_blocks_person(self) -> None:
        text = "\n".join(self.source_lines)
        self.assertIn(
            'publishable = track_id is not None and best.get("object_type") != "person"',
            text,
        )
        self.assertIn(
            "should_post_event = publishable and speed_ready and not event_already_posted",
            text,
        )
        self.assertIn(
            "should_post_event = publishable and not event_already_posted and legacy_event_ready",
            text,
        )

    def test_gate_sits_inside_main_flow(self) -> None:
        gate = [
            node for node in ast.walk(self.main_node)
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "publishable" for t in node.targets)
        ]
        self.assertEqual(len(gate), 1, "publication gate must exist exactly once in main()")

    def test_speed_formulas_untouched(self) -> None:
        text = "\n".join(self.source_lines)
        for marker in (
            "def update_speed_estimate(det):",
            "kmh_per_px_s",
            "MIN_EVENT_SPEED_PX_PER_SEC",
        ):
            self.assertIn(marker, text)


class ApiPersonGuardTests(unittest.TestCase):
    def _load_post_handler(self, temp_dir: str) -> tuple[dict[str, Any], dict[str, Any]]:
        tree = ast.parse(API.read_text(encoding="utf-8-sig"), filename=str(API))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "post_analytics_event":
                cloned = copy.deepcopy(node)
                cloned.decorator_list = []
                module = ast.Module(body=[cloned], type_ignores=[])
                ast.fix_missing_locations(module)
                class HTTPExceptionStub(Exception):
                    def __init__(self, status_code=None, detail=None, *a, **k):
                        super().__init__(detail or "")
                        self.status_code = status_code
                        self.detail = detail
                ns: dict[str, Any] = {
                    "json": json,
                    "uuid": __import__("uuid"),
                    "Path": Path,
                    "Dict": Dict,
                    "Any": Any,
                    "Optional": type(None),
                    "Form": lambda *a, **k: None,
                    "File": lambda *a, **k: None,
                    "Header": lambda *a, **k: None,
                    "HTTPException": HTTPExceptionStub,
                    "require_auth": lambda token: None,
                    "analytics_identity": lambda camera_id: {
                        "analytics_profile": "road-v1", "domain": "road"
                    },
                    "EVENTS_MEDIA_DIR": Path(temp_dir) / "events",
                    "now_iso": lambda: "2026-08-23T00:00:00+00:00",
                    "persist_object_event": lambda event: (_ for _ in ()).throw(
                        AssertionError("must not persist person events")
                    ),
                    "sweep_events_media": lambda force=False, now=None: 0,
                    "TELEMETRY_SCHEMA": "sea_speed_telemetry_v1",
                    "VEHICLE_EVENT_SCHEMA": "sea_speed_vehicle_event_v1",
                    "WORKER_STATE_SCHEMA": "sea_speed_worker_state_v1",
                }
                exec(compile(module, str(API), "exec"), ns)
                return ns, {}
        raise AssertionError("post_analytics_event not found")

    def test_person_event_ok_without_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns, _ = self._load_post_handler(temp_dir)
            result = asyncio.run(ns["post_analytics_event"](
                camera_id="road1",
                metadata=json.dumps({"event_id": "p1", "object_type": "person"}),
                snapshot=None,
                authorization=None,
            ))
            self.assertEqual(result, {"ok": True, "event": None})

    def _vehicle_regression(self) -> None:
        pass

    def test_vehicle_event_still_persists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns, _ = self._load_post_handler(temp_dir)

            persisted: list[dict[str, Any]] = []
            original = ns["persist_object_event"]

            def spy(event: Dict[str, Any]) -> bool:
                persisted.append(event)
                return True

            ns["persist_object_event"] = spy
            analytics_data_file = lambda camera_id, kind: Path(temp_dir) / f"{camera_id}_{kind}.json"
            ns["analytics_data_file"] = analytics_data_file
            read_json_file = lambda path, default: []
            writes: list[tuple[Path, list]] = []

            def write_json_file(path: Path, data: list) -> None:
                writes.append((path, data))

            ns["read_json_file"] = read_json_file
            ns["write_json_file"] = write_json_file
            (Path(temp_dir) / "events").mkdir(parents=True, exist_ok=True)
            class FakeSnap:
                async def read(self) -> bytes:
                    return b"fakejpg"
            result = asyncio.run(ns["post_analytics_event"](
                camera_id="road1",
                metadata=json.dumps({"event_id": "v1", "object_type": "car"}),
                snapshot=FakeSnap(),
                authorization=None,
            ))
            self.assertTrue(result["ok"])
            self.assertEqual(result["event"]["event_id"], "v1")
            self.assertEqual(len(persisted), 1)
            self.assertEqual(writes[0][1][0]["event_id"], "v1")
            self.assertIn("snapshot_url", result["event"])
            _ = original

    def test_vehicle_event_without_snapshot_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns, _ = self._load_post_handler(temp_dir)
            ns["persist_object_event"] = lambda event: (_ for _ in ()).throw(AssertionError("must not persist"))
            ns["analytics_data_file"] = lambda camera_id, kind: Path(temp_dir) / f"{camera_id}_{kind}.json"
            ns["read_json_file"] = lambda path, default: []
            ns["write_json_file"] = lambda path, data: None
            with self.assertRaises(Exception) as cm:
                asyncio.run(ns["post_analytics_event"](
                    camera_id="road1",
                    metadata=json.dumps({"event_id": "v2", "object_type": "car"}),
                    snapshot=None,
                    authorization=None,
                ))
            self.assertEqual(getattr(cm.exception, "status_code", None), 422)


if __name__ == "__main__":
    unittest.main()
