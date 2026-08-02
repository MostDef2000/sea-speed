from __future__ import annotations

import ast
import hashlib
import copy
from contextlib import contextmanager
import json
import os
import re
import sqlite3
import tempfile
import time
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "api/app/main.py"


class HTTPExceptionStub(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def load_functions(names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"), filename=str(SOURCE))
    selected = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            cloned = copy.deepcopy(node)
            cloned.decorator_list = copy.deepcopy(node.decorator_list) if node.name == "open_objects_db" else []
            selected.append(cloned)
    missing = names - {node.name for node in selected}
    if missing:
        raise AssertionError(f"missing API functions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


def objects_namespace(temp_dir: str) -> dict[str, Any]:
    return {
        "Any": Any,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "Path": Path,
        "json": json,
        "hashlib": hashlib,
        "sqlite3": sqlite3,
        "contextmanager": contextmanager,
        "uuid": uuid,
        "HTTPException": HTTPExceptionStub,
        "OBJECT_STATUSES": {"new", "reviewed", "ignored"},
        "OBJECTS_DB_FILE": Path(temp_dir) / "objects.sqlite3",
        "EVENTS_FILE": Path(temp_dir) / "events.json",
        "now_iso": lambda: "2026-08-02T00:00:00+00:00",
    }


OBJECT_FUNCTIONS = {
    "read_json_file",
    "open_objects_db",
    "initialize_objects_db",
    "optional_float",
    "optional_int",
    "stable_object_id",
    "persist_object_event",
    "import_existing_events",
    "object_row_to_dict",
    "build_objects_where",
    "get_cam1_objects",
    "get_cam1_object",
    "patch_cam1_object",
    "delete_cam1_object",
}


class ApiContractTests(unittest.TestCase):
    def test_atomic_json_round_trip_and_invalid_fallback(self) -> None:
        ns = load_functions({"read_json_file", "write_json_file"}, {"json": json, "Any": Any})
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            payload = {"frame_no": 42, "worker_online": True}
            ns["write_json_file"](path, payload)
            self.assertEqual(ns["read_json_file"](path, {}), payload)
            self.assertFalse(path.with_suffix(".json.tmp").exists())
            path.write_text("{broken", encoding="utf-8")
            self.assertEqual(ns["read_json_file"](path, {"safe": True}), {"safe": True})

    def test_auth_fails_closed_and_accepts_exact_bearer(self) -> None:
        ns = load_functions(
            {"require_auth"},
            {"Optional": Any, "HTTPException": HTTPExceptionStub, "API_TOKEN": ""},
        )
        with self.assertRaises(HTTPExceptionStub) as missing:
            ns["require_auth"](None)
        self.assertEqual(missing.exception.status_code, 500)

        ns["API_TOKEN"] = "test-token"
        with self.assertRaises(HTTPExceptionStub) as forbidden:
            ns["require_auth"]("Bearer wrong")
        self.assertEqual(forbidden.exception.status_code, 403)
        ns["require_auth"]("Bearer test-token")

    def test_deployed_source_commit_is_non_secret_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            marker = Path(temp_dir) / "current-release"
            marker.write_text("a" * 40 + "\n", encoding="utf-8")
            previous = os.environ.pop("SEA_SPEED_SOURCE_COMMIT", None)
            try:
                ns = load_functions(
                    {"deployed_source_commit"},
                    {
                        "os": os,
                        "SHA_RE": re.compile(r"^[0-9a-fA-F]{40}$"),
                        "DEPLOYED_COMMIT_FILE": marker,
                    },
                )
                self.assertEqual(ns["deployed_source_commit"](), "a" * 40)
                marker.write_text("bootstrap-local\n", encoding="utf-8")
                self.assertEqual(ns["deployed_source_commit"](), "unknown")
            finally:
                if previous is not None:
                    os.environ["SEA_SPEED_SOURCE_COMMIT"] = previous

    def test_state_freshness_marks_stale_worker_offline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_file = Path(temp_dir) / "cam1_state.json"
            ns: dict[str, Any] = {
                "json": json,
                "Any": Any,
                "Dict": dict,
                "STATE_FILE": state_file,
                "datetime": datetime,
                "time": time,
                "WORKER_STATE_SCHEMA": "sea_speed_worker_state_v1",
                "TELEMETRY_SCHEMA": "sea_speed_telemetry_v1",
            }
            load_functions({"read_json_file", "default_state", "get_cam1_state"}, ns)

            stale = (datetime.now(timezone.utc) - timedelta(seconds=31)).isoformat()
            state_file.write_text(json.dumps({"updated_at": stale, "worker_online": True}), encoding="utf-8")
            stale_state = ns["get_cam1_state"]()
            self.assertFalse(stale_state["worker_online"])
            self.assertEqual(stale_state["state_schema"], "sea_speed_worker_state_v1")

            fresh = datetime.now(timezone.utc).isoformat()
            state_file.write_text(json.dumps({"updated_at": fresh, "worker_online": False}), encoding="utf-8")
            self.assertTrue(ns["get_cam1_state"]()["worker_online"])

    def test_roi_and_speed_line_validation(self) -> None:
        writes: list[tuple[Path, dict[str, Any]]] = []
        ns: dict[str, Any] = {
            "Any": Any,
            "Dict": dict,
            "List": list,
            "HTTPException": HTTPExceptionStub,
            "ROI_FILE": Path("roi.json"),
            "SPEED_LINES_FILE": Path("lines.json"),
            "now_iso": lambda: "2026-08-02T00:00:00+00:00",
            "write_json_file": lambda path, data: writes.append((path, data)),
        }
        load_functions({"clean_points_list", "post_cam1_roi", "post_cam1_speed_lines"}, ns)

        with self.assertRaises(HTTPExceptionStub) as roi_error:
            ns["post_cam1_roi"]({"enabled": True, "polygon": [{"x": 1, "y": 2}]})
        self.assertEqual(roi_error.exception.status_code, 400)

        roi = ns["post_cam1_roi"]({
            "enabled": True,
            "polygon": [
                {"x": 1.2, "y": 2.7},
                {"x": 10, "y": 20},
                {"x": "30", "y": "40"},
            ],
        })
        self.assertEqual(roi["polygon"][0], {"x": 1, "y": 3})

        with self.assertRaises(HTTPExceptionStub):
            ns["post_cam1_speed_lines"]({"enabled": True, "distance_m": 0, "line_a": [], "line_b": []})
        with self.assertRaises(HTTPExceptionStub):
            ns["post_cam1_speed_lines"]({"enabled": True, "distance_m": 10, "line_a": [], "line_b": []})

        lines = ns["post_cam1_speed_lines"]({
            "enabled": True,
            "distance_m": 57,
            "line_a": [{"x": 0, "y": 1}, {"x": 2, "y": 3}],
            "line_b": [{"x": 4, "y": 5}, {"x": 6, "y": 7}],
        })
        self.assertTrue(lines["enabled"])
        self.assertEqual(lines["distance_m"], 57.0)
        self.assertEqual(len(writes), 2)

    def test_objects_registry_import_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = objects_namespace(temp_dir)
            load_functions(OBJECT_FUNCTIONS, ns)
            ns["initialize_objects_db"]()
            event = {
                "event_id": "event-1",
                "camera_id": "cam1",
                "track_id": 23,
                "created_at": "2026-08-02T10:00:00+00:00",
                "class_name": "car",
                "confidence": 0.91,
                "speed_kmh": 37.4,
                "snapshot_url": "/sea-speed/media/events/event-1.jpg",
            }
            ns["EVENTS_FILE"].write_text(json.dumps([event]), encoding="utf-8")

            self.assertEqual(ns["import_existing_events"](), 1)
            self.assertEqual(ns["import_existing_events"](), 0)
            with ns["open_objects_db"]() as connection:
                row = connection.execute("SELECT * FROM objects").fetchone()
            self.assertEqual(row["object_id"], "event-1")
            self.assertEqual(row["track_id"], 23)
            self.assertEqual(row["speed_kmh"], 37.4)
            self.assertEqual(row["status"], "new")

            legacy_event = {
                "created_at": "2026-08-02T10:05:00+00:00",
                "class_name": "truck",
                "speed_kmh": 41.2,
            }
            ns["EVENTS_FILE"].write_text(json.dumps([legacy_event]), encoding="utf-8")
            self.assertEqual(ns["import_existing_events"](), 1)
            self.assertEqual(ns["import_existing_events"](), 0)
            with ns["open_objects_db"]() as connection:
                legacy_ids = [
                    row["object_id"]
                    for row in connection.execute(
                        "SELECT object_id FROM objects WHERE object_id LIKE 'legacy-%'"
                    ).fetchall()
                ]
            self.assertEqual(len(legacy_ids), 1)

    def test_objects_list_edit_filter_and_soft_delete(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = objects_namespace(temp_dir)
            load_functions(OBJECT_FUNCTIONS, ns)
            ns["initialize_objects_db"]()
            ns["persist_object_event"]({
                "event_id": "event-1",
                "created_at": "2026-08-02T10:00:00+00:00",
                "class_name": "car",
                "speed_kmh": 37.4,
            })
            ns["persist_object_event"]({
                "event_id": "event-2",
                "created_at": "2026-08-02T11:00:00+00:00",
                "class_name": "truck",
                "speed_kmh": 52.0,
            })

            listing = ns["get_cam1_objects"](limit=10, status="new", speed_min=40)
            self.assertEqual(listing["total"], 1)
            self.assertEqual(listing["objects"][0]["object_id"], "event-2")

            edited = ns["patch_cam1_object"]("event-2", {
                "class_name": "vessel",
                "speed_kmh": 49.5,
                "comment": "Проверено оператором",
                "status": "reviewed",
            })["object"]
            self.assertEqual(edited["class_name"], "vessel")
            self.assertEqual(edited["speed_kmh"], 49.5)
            self.assertEqual(edited["status"], "reviewed")
            self.assertEqual(edited["comment"], "Проверено оператором")
            self.assertEqual(
                ns["get_cam1_object"]("event-2")["object"]["original_event"]["class_name"],
                "truck",
            )

            deleted = ns["delete_cam1_object"]("event-2")
            self.assertEqual(deleted["object_id"], "event-2")
            self.assertEqual(ns["get_cam1_objects"](limit=10)["total"], 1)
            self.assertEqual(ns["get_cam1_objects"](limit=10, include_deleted=True)["total"], 2)
            with self.assertRaises(HTTPExceptionStub) as missing:
                ns["get_cam1_object"]("event-2")
            self.assertEqual(missing.exception.status_code, 404)

    def test_objects_validation_rejects_invalid_status_and_speed_range(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = objects_namespace(temp_dir)
            load_functions(OBJECT_FUNCTIONS, ns)
            ns["initialize_objects_db"]()
            with self.assertRaises(HTTPExceptionStub) as invalid_status:
                ns["get_cam1_objects"](status="closed")
            self.assertEqual(invalid_status.exception.status_code, 400)
            with self.assertRaises(HTTPExceptionStub) as invalid_range:
                ns["get_cam1_objects"](speed_min=50, speed_max=10)
            self.assertEqual(invalid_range.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
