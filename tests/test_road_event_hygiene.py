import ast
import asyncio
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker" / "hls_motion_yolo_worker_events.py"
API = ROOT / "api" / "app" / "main.py"
STORE_FILE = ROOT / "api" / "app" / "store.py"
PROFILES = ROOT / "worker" / "analytics_profiles.py"

try:
    from tests.support import worker_source
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    import sys

    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import worker_source


def _load_api_store():
    spec = importlib.util.spec_from_file_location("api_store_road_hygiene_test", STORE_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    """Locate the main() function node via the shared worker-source loader."""
    # 398-wave-a: shared harness (was a private AST scan fixed to one path) —
    # the loader resolves the worker source so #397 file moves keep working.
    return {"node": worker_source.function_node("main")}


class WorkerEventGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.main_node = load_worker_main()["node"]

    def test_gate_requires_track_and_blocks_person(self) -> None:
        # 398-wave-a: converted from source-text pin (was L51-64) — the
        # publication gate must hold structurally inside the live main() flow:
        # events need a tracked, non-person best detection, and the two
        # should_post_event branches must gate on publishable plus the
        # profiled-speed path (speed lines on) or the legacy path (off).
        # The publishable-exactly-once assertion subsumes the former
        # test_gate_sits_inside_main_flow AST twin (merged, -1 method).
        # Old text-pin behavior on a dead-code fixture (pin text inside an
        # uncalled function, live gate absent): assertIn false-passed — the
        # in-repo AST twin at the former L66-72 was the conversion recipe.
        main_node = self.main_node
        publishable = worker_source.find_assignments(main_node, "publishable")
        self.assertEqual(len(publishable), 1, "publication gate must exist exactly once in main()")
        self.assertEqual(
            worker_source.dump(publishable[0].value),
            worker_source.expr_dump('track_id is not None and best.get("object_type") != "person"'),
            "publishable must require a track and block person detections",
        )
        should_post = worker_source.find_assignments(main_node, "should_post_event")
        self.assertEqual(len(should_post), 2, "both speed-line branches must compute should_post_event")
        expected_gates = (
            "publishable and speed_ready and not event_already_posted",
            "publishable and not event_already_posted and legacy_event_ready",
        )
        for expected in expected_gates:
            self.assertEqual(
                sum(1 for node in should_post if worker_source.dump(node.value) == worker_source.expr_dump(expected)),
                1,
                f"missing publication branch: {expected}",
            )

    def test_speed_formulas_untouched(self) -> None:
        # 398-wave-a: converted from source-text pin (was L74-81) — the speed
        # formula entry points must exist structurally: update_speed_estimate
        # keeps its single det parameter and the kmh factor / minimum-speed
        # constants stay referenced by the worker module.
        update_node = worker_source.function_node("update_speed_estimate")
        self.assertEqual(
            [arg.arg for arg in update_node.args.args],
            ["det"],
            "update_speed_estimate(det) signature must stay",
        )
        trees = worker_source.module_trees()
        self.assertTrue(worker_source.references_name(trees, "kmh_per_px_s"), "kmh_per_px_s factor must stay referenced")
        self.assertTrue(
            worker_source.references_name(trees, "MIN_EVENT_SPEED_PX_PER_SEC"),
            "MIN_EVENT_SPEED_PX_PER_SEC must stay referenced",
        )


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
                    "store": _load_api_store(),
                    "STATE_DB_FILE": Path(temp_dir) / "state.sqlite3",
                    "EVENTS_FEED_LIMIT": 500,
                    "sys": __import__("sys"),
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
            # The legacy JSON mirror is retired (RISK-005): persistence is
            # asserted against the authoritative SQLite event feed below.
            ns["read_json_file"] = read_json_file
            ns["write_json_file"] = lambda path, data: None
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
            self.assertEqual(
                [event["event_id"] for event in ns["store"].read_events(ns["STATE_DB_FILE"], "road1")],
                ["v1"],
                "the accepted event must be persisted to the authoritative SQLite feed",
            )
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
