from __future__ import annotations

import ast
import copy
import hashlib
import json
import sqlite3
import tempfile
import time
import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "api" / "app" / "main.py"


class HTTPExceptionStub(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def load_functions(names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"), filename=str(SOURCE))
    selected = []
    found = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            cloned = copy.deepcopy(node)
            cloned.decorator_list = copy.deepcopy(node.decorator_list) if node.name == "open_objects_db" else []
            selected.append(cloned)
            found.add(node.name)
    missing = names - found
    if missing:
        raise AssertionError(f"missing API functions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


def objects_namespace(temp_dir: str) -> dict[str, Any]:
    return {
        "Any": Any, "Dict": Dict, "List": List, "Optional": Optional, "Path": Path,
        "json": json, "hashlib": hashlib, "sqlite3": sqlite3, "contextmanager": contextmanager,
        "uuid": uuid, "HTTPException": HTTPExceptionStub,
        "OBJECT_STATUSES": {"new", "reviewed", "ignored"}, "OBJECTS_RETENTION_LIMIT": 100,
        "OBJECTS_DB_FILE": Path(temp_dir) / "objects.sqlite3",
        "EVENTS_FILE": Path(temp_dir) / "events.json",
        "now_iso": lambda: "2026-08-02T00:00:00+00:00",
    }


OBJECT_FUNCTIONS = {
    "read_json_file", "open_objects_db", "prune_objects_registry", "initialize_objects_db",
    "optional_float", "optional_int", "stable_object_id", "persist_object_event", "import_existing_events",
    "object_row_to_dict", "build_objects_where", "get_cam1_objects", "get_cam1_object",
    "patch_cam1_object", "delete_cam1_object",
}


class ApiContractTests(unittest.TestCase):
    def test_legacy_state_function_remains_self_contained(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "cam1_state.json"
            ns = {
                "json": json, "Any": Any, "Dict": dict, "Path": Path, "STATE_FILE": state_file,
                "datetime": datetime, "time": time, "WORKER_STATE_SCHEMA": "sea_speed_worker_state_v1",
                "TELEMETRY_SCHEMA": "sea_speed_telemetry_v1",
            }
            load_functions({"read_json_file", "default_state", "get_cam1_state"}, ns)
            stale = (datetime.now(timezone.utc) - timedelta(seconds=31)).isoformat()
            state_file.write_text(json.dumps({"updated_at": stale, "worker_online": True}), encoding="utf-8")
            state = ns["get_cam1_state"]()
            self.assertFalse(state["worker_online"])
            self.assertEqual(state["analytics_profile"], "water-v1")
            self.assertEqual(state["domain"], "water")

    def test_objects_registry_migrates_additive_semantic_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = objects_namespace(temp_dir)
            load_functions(OBJECT_FUNCTIONS, ns)
            ns["initialize_objects_db"]()
            ns["persist_object_event"]({
                "event_id": "water-1", "camera_id": "cam1", "created_at": "2026-08-02T10:00:00+00:00",
                "class_name": "vessel", "object_type": "vessel", "model_class": "boat",
                "analytics_profile": "water-v1", "domain": "water", "confidence": 0.91,
            })
            ns["persist_object_event"]({
                "event_id": "road-1", "camera_id": "road1", "created_at": "2026-08-02T11:00:00+00:00",
                "class_name": "car", "object_type": "car", "model_class": "car",
                "analytics_profile": "road-v1", "domain": "road", "confidence": 0.88,
            })
            with ns["open_objects_db"]() as connection:
                columns = {row[1] for row in connection.execute("PRAGMA table_info(objects)")}
                water = connection.execute("SELECT * FROM objects WHERE object_id='water-1'").fetchone()
                road = connection.execute("SELECT * FROM objects WHERE object_id='road-1'").fetchone()
            self.assertTrue({"analytics_profile", "domain", "object_type", "model_class"}.issubset(columns))
            self.assertEqual((water["camera_id"], water["model_class"]), ("cam1", "boat"))
            self.assertEqual((road["camera_id"], road["domain"]), ("road1", "road"))

    def test_objects_registry_initialization_prunes_to_newest_100(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = objects_namespace(temp_dir)
            load_functions(OBJECT_FUNCTIONS, ns)
            ns["initialize_objects_db"]()
            with ns["open_objects_db"]() as connection:
                for index in range(105):
                    object_id = f"seed-{index:03d}"
                    detected_at = f"2026-08-02T10:{index // 60:02d}:{index % 60:02d}+00:00"
                    connection.execute(
                        """INSERT INTO objects (
                            object_id, camera_id, detected_at, class_name, original_event_json,
                            created_at, updated_at
                        ) VALUES (?, 'cam1', ?, 'vessel', '{}', ?, ?)""",
                        (object_id, detected_at, detected_at, detected_at),
                    )
            ns["initialize_objects_db"]()
            with ns["open_objects_db"]() as connection:
                rows = connection.execute(
                    "SELECT object_id FROM objects ORDER BY detected_at DESC, object_id DESC"
                ).fetchall()
            self.assertEqual(len(rows), 100)
            self.assertEqual(rows[0]["object_id"], "seed-104")
            self.assertEqual(rows[-1]["object_id"], "seed-005")

    def test_objects_registry_insert_prunes_to_newest_100(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = objects_namespace(temp_dir)
            load_functions(OBJECT_FUNCTIONS, ns)
            ns["initialize_objects_db"]()
            for index in range(101):
                ns["persist_object_event"]({
                    "event_id": f"event-{index:03d}",
                    "camera_id": "cam1" if index % 2 == 0 else "road1",
                    "created_at": f"2026-08-02T11:{index // 60:02d}:{index % 60:02d}+00:00",
                    "class_name": "vessel" if index % 2 == 0 else "car",
                })
            with ns["open_objects_db"]() as connection:
                rows = connection.execute(
                    "SELECT object_id FROM objects ORDER BY detected_at DESC, object_id DESC"
                ).fetchall()
            self.assertEqual(len(rows), 100)
            self.assertEqual(rows[0]["object_id"], "event-100")
            self.assertEqual(rows[-1]["object_id"], "event-001")
            self.assertNotIn("event-000", {row["object_id"] for row in rows})

    def test_legacy_cam1_objects_remain_camera_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = objects_namespace(temp_dir)
            load_functions(OBJECT_FUNCTIONS, ns)
            ns["initialize_objects_db"]()
            ns["persist_object_event"]({"event_id": "cam", "camera_id": "cam1", "created_at": "x", "class_name": "vessel"})
            ns["persist_object_event"]({"event_id": "road", "camera_id": "road1", "created_at": "y", "class_name": "car"})
            listing = ns["get_cam1_objects"](limit=10)
            self.assertEqual(listing["total"], 1)
            self.assertEqual(listing["objects"][0]["object_id"], "cam")

    def test_legacy_roi_and_speed_line_validation_is_preserved(self) -> None:
        writes: list[tuple[Path, dict[str, Any]]] = []
        ns = {
            "Any": Any, "Dict": dict, "List": list, "Path": Path, "HTTPException": HTTPExceptionStub,
            "DATA_DIR": Path("data"), "STATE_FILE": Path("state.json"), "EVENTS_FILE": Path("events.json"),
            "ROI_FILE": Path("roi.json"), "SPEED_CONFIG_FILE": Path("speed.json"), "SPEED_LINES_FILE": Path("lines.json"),
            "ANALYTICS_IDENTITIES": {
                "cam1": {"analytics_profile": "water-v1", "domain": "water"},
                "road1": {"analytics_profile": "road-v1", "domain": "road"},
            },
            "now_iso": lambda: "x", "write_json_file": lambda path, data: writes.append((path, data)),
        }
        load_functions({
            "clean_points_list", "analytics_identity", "analytics_data_file",
            "post_analytics_roi", "post_analytics_speed_lines", "post_cam1_roi", "post_cam1_speed_lines",
        }, ns)
        with self.assertRaises(HTTPExceptionStub):
            ns["post_cam1_roi"]({"enabled": True, "polygon": [{"x": 1, "y": 2}]})
        roi = ns["post_cam1_roi"]({"enabled": True, "polygon": [{"x": 1.2, "y": 2.7}, {"x": 10, "y": 20}, {"x": "30", "y": "40"}]})
        self.assertEqual(roi["polygon"][0], {"x": 1, "y": 3})
        self.assertEqual(writes[-1][0], Path("roi.json"))
        with self.assertRaises(HTTPExceptionStub):
            ns["post_cam1_speed_lines"]({"enabled": True, "distance_m": 0, "line_a": [], "line_b": []})

    def test_generic_analytics_routes_are_additive_and_road_scoped(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        for marker in (
            '@app.get("/api/analytics/{camera_id}/state")', '@app.post("/api/analytics/{camera_id}/events")',
            '@app.get("/api/analytics/{camera_id}/objects")', '@app.get("/api/objects")',
            '"road1": {"analytics_profile": "road-v1", "domain": "road"}',
            'DATA_DIR / f"{camera_id}_{kind}.json"',
        ):
            self.assertIn(marker, source)
        self.assertIn("def analytics_identity(camera_id", source)
        self.assertIn("Unknown analytics camera", source)

    def test_generic_objects_query_supports_camera_domain_and_profile_filters(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        start = source.index("def build_objects_where(")
        end = source.index("def analytics_identity", start)
        block = source[start:end]
        for marker in ("camera_id", "domain", "analytics_profile", "object_type"):
            self.assertIn(marker, block)
        self.assertIn("OBJECTS_RETENTION_LIMIT = 100", source)
        self.assertIn("def prune_objects_registry", source)

    def test_browser_worker_control_is_fixed_to_water_and_road1(self) -> None:
        source = SOURCE.read_text(encoding="utf-8")
        for marker in (
            '("GET", "/v1/status")', '("POST", "/v1/start")', '("POST", "/v1/stop")',
            '("GET", "/v1/road1/status")', '("POST", "/v1/road1/start")', '("POST", "/v1/road1/stop")',
            '@app.get("/api/worker/control/road1")',
            '@app.post("/api/worker/control/road1/start")',
            '@app.post("/api/worker/control/road1/stop")',
            'require_operator_identity', 'payload["requested_by"] = username',
        ):
            self.assertIn(marker, source)
        self.assertNotIn('/api/worker/control/{', source)
        self.assertNotIn('/v1/{', source)


if __name__ == "__main__":
    unittest.main()
