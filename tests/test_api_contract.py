from __future__ import annotations

import ast
import copy
import json
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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
            cloned.decorator_list = []
            selected.append(cloned)
    missing = names - {node.name for node in selected}
    if missing:
        raise AssertionError(f"missing API functions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


class ApiContractTests(unittest.TestCase):
    def test_atomic_json_round_trip_and_invalid_fallback(self) -> None:
        ns = load_functions(
            {"read_json_file", "write_json_file"},
            {"json": json, "Any": Any},
        )
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
            }
            load_functions({"read_json_file", "default_state", "get_cam1_state"}, ns)

            stale = (datetime.now(timezone.utc) - timedelta(seconds=31)).isoformat()
            state_file.write_text(json.dumps({"updated_at": stale, "worker_online": True}), encoding="utf-8")
            self.assertFalse(ns["get_cam1_state"]()["worker_online"])

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


if __name__ == "__main__":
    unittest.main()
