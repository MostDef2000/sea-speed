from __future__ import annotations

# Issue #577: NaN/Infinity must not bypass numeric input validation.
# Covers the five defect sites from the issue audit:
#   1. objects_registry.optional_float — NaN/±inf passed through to ingest
#   2. analytics._clean_norm_points — non-finite ROI points silently clamped to 1.0/0.0
#   3. main.post_analytics_speed_config — NaN/±inf kmh_per_px_s bypassed the < 0 guard
#   4. main.post_analytics_speed_lines — NaN/±inf distance_m bypassed the <= 0 guard
#   5. objects_registry.patch_object_record — NaN/±inf speed_kmh bypassed the < 0 guard
# Harness style: AST-extract the handlers and exec them into a stub namespace
# (same idiom as tests/test_water_passage.py / tests/test_sea_speed_rbac.py —
# there is no TestClient in this suite, that is issue #582).

import ast
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
API_SOURCE = ROOT / "api" / "app" / "main.py"
ANALYTICS_SOURCE = ROOT / "api" / "app" / "analytics.py"
OBJECTS_REGISTRY_SOURCE = ROOT / "api" / "app" / "objects_registry.py"


class HTTPExceptionStub(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def load_api_functions(sources: list[Path], names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    selected = []
    found = set()
    for source in sources:
        if not source.exists():
            continue
        tree = ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names and node.name not in found:
                cloned = copy.deepcopy(node)
                # keep @contextmanager on the db-open helper (same special case
                # as open_passages_db in tests/test_water_passage.py)
                cloned.decorator_list = copy.deepcopy(node.decorator_list) if node.name in {"open_objects_db"} else []
                selected.append(cloned)
                found.add(node.name)
    missing = names - found
    if missing:
        raise AssertionError(f"missing API functions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(sources[0]), "exec"), namespace)
    return namespace


class OptionalFloatFiniteTests(unittest.TestCase):
    """Site 1: the shared ingest helper must drop NaN/±inf like non-numeric input."""

    def setUp(self) -> None:
        self.ns: dict[str, Any] = {"Any": Any, "Optional": Optional}
        load_api_functions([OBJECTS_REGISTRY_SOURCE], {"optional_float"}, self.ns)
        self.optional_float = self.ns["optional_float"]

    def test_non_finite_values_return_none(self) -> None:
        # On base 79ffab2 every one of these returned the non-finite float and
        # slipped past the callers' `if x < 0` guards.
        for value in (float("nan"), float("inf"), float("-inf"), "nan", "inf", "-inf"):
            with self.subTest(value=value):
                self.assertIsNone(self.optional_float(value))

    def test_finite_behavior_unchanged(self) -> None:
        cases: list[tuple[Any, Any]] = [
            (0, 0.0),
            (12.5, 12.5),
            (-3.5, -3.5),  # negative finite stays legal here; range checks belong to callers
            ("12.5", 12.5),
            (True, 1.0),
            (None, None),
            ("", None),
            ("abc", None),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(self.optional_float(value), expected)


class CleanNormPointsFiniteTests(unittest.TestCase):
    """Site 2: non-finite ROI points must drop exactly like malformed points."""

    def setUp(self) -> None:
        self.ns: dict[str, Any] = {"Any": Any, "Dict": Dict, "List": List}
        load_api_functions([ANALYTICS_SOURCE], {"_clean_norm_points"}, self.ns)
        self.clean = self.ns["_clean_norm_points"]

    def test_non_finite_points_dropped(self) -> None:
        # On base these were silently clamped (NaN/+inf -> 1.0, -inf -> 0.0),
        # corrupting the saved ROI geometry.
        raw_cases: list[list[Dict[str, Any]]] = [
            [{"x_norm": float("nan"), "y_norm": 0.5}],
            [{"x_norm": 0.5, "y_norm": float("nan")}],
            [{"x_norm": float("inf"), "y_norm": 0.5}],
            [{"x_norm": 0.5, "y_norm": float("-inf")}],
            [{"x_norm": "nan", "y_norm": 0.5}],
        ]
        for raw in raw_cases:
            with self.subTest(raw=raw):
                self.assertEqual(self.clean(raw), [])

    def test_valid_clamping_and_malformed_drop_unchanged(self) -> None:
        self.assertEqual(self.clean([{"x_norm": 1.7, "y_norm": -0.4}]), [{"x_norm": 1.0, "y_norm": 0.0}])
        self.assertEqual(self.clean([{"x_norm": "abc", "y_norm": 0.5}]), [])
        # absolute x/y without an explicit *_norm key are still not normalized input
        self.assertEqual(self.clean([{"x": 0.3, "y": 0.6}]), [])
        self.assertEqual(self.clean("not-a-list"), [])

    def test_mixed_input_keeps_only_finite_points(self) -> None:
        raw = [
            {"x_norm": float("nan"), "y_norm": 0.1},
            {"x_norm": 0.25, "y_norm": 0.75},
            {"x_norm": float("inf"), "y_norm": 0.2},
        ]
        self.assertEqual(self.clean(raw), [{"x_norm": 0.25, "y_norm": 0.75}])


class SpeedConfigEndpointFiniteTests(unittest.TestCase):
    """Site 3: speed-config calibration must 400 on non-finite kmh_per_px_s."""

    def setUp(self) -> None:
        self.writes: list[tuple[Path, Dict[str, Any]]] = []
        self.ns: dict[str, Any] = {
            "Any": Any,
            "Dict": Dict,
            "Optional": Optional,
            "HTTPException": HTTPExceptionStub,
            "Header": lambda default=None: default,
            "require_role": lambda *args, **kwargs: None,
            "analytics_identity": lambda camera_id: None,
            "analytics_data_file": lambda camera_id, kind: Path(f"/sea-speed-test-data/{camera_id}_{kind}.json"),
            "write_json_file": lambda path, data: self.writes.append((path, data)),
            "now_iso": lambda: "2026-11-01T00:00:00+00:00",
        }
        load_api_functions([API_SOURCE], {"post_analytics_speed_config"}, self.ns)
        self.handler = self.ns["post_analytics_speed_config"]

    def test_non_finite_kmh_per_px_s_rejected_400(self) -> None:
        # On base the NaN/±inf values passed the `< 0` guard and were written
        # into the persisted speed config.
        for value in (float("nan"), float("inf"), float("-inf"), "nan", "inf"):
            with self.subTest(value=value):
                self.writes.clear()
                with self.assertRaises(HTTPExceptionStub) as raised:
                    self.handler("cam1", {"kmh_per_px_s": value})
                self.assertEqual(raised.exception.status_code, 400)
                self.assertEqual(raised.exception.detail, "kmh_per_px_s must be a finite number")
                self.assertEqual(self.writes, [])

    def test_finite_and_range_behavior_unchanged(self) -> None:
        result = self.handler("cam1", {"kmh_per_px_s": 1.25, "enabled": True})
        self.assertTrue(result["ok"])
        self.assertEqual(result["kmh_per_px_s"], 1.25)
        self.assertTrue(result["enabled"])
        self.assertEqual(len(self.writes), 1)
        with self.assertRaises(HTTPExceptionStub) as raised:
            self.handler("cam1", {"kmh_per_px_s": -1})
        self.assertEqual(raised.exception.detail, "kmh_per_px_s must be >= 0")
        with self.assertRaises(HTTPExceptionStub) as raised:
            self.handler("cam1", {"kmh_per_px_s": "abc"})
        self.assertEqual(raised.exception.detail, "kmh_per_px_s must be a number")


class SpeedLinesEndpointFiniteTests(unittest.TestCase):
    """Site 4: speed-lines calibration must 400 on non-finite distance_m,
    and non-finite line points must not reach the persisted config."""

    def setUp(self) -> None:
        self.writes: list[tuple[Path, Dict[str, Any]]] = []
        self.ns: dict[str, Any] = {
            "Any": Any,
            "Dict": Dict,
            "List": List,
            "Optional": Optional,
            "HTTPException": HTTPExceptionStub,
            "Header": lambda default=None: default,
            "require_role": lambda *args, **kwargs: None,
            "analytics_identity": lambda camera_id: None,
            "analytics_data_file": lambda camera_id, kind: Path(f"/sea-speed-test-data/{camera_id}_{kind}.json"),
            "write_json_file": lambda path, data: self.writes.append((path, data)),
            "now_iso": lambda: "2026-11-01T00:00:00+00:00",
            "DEFAULT_ROI_REF_W": 1920,
            "DEFAULT_ROI_REF_H": 1080,
            "LEGACY_ROI_W": 704,
            "LEGACY_ROI_H": 576,
        }
        load_api_functions(
            [API_SOURCE, ANALYTICS_SOURCE],
            {
                "post_analytics_speed_lines",
                "clean_points_list",
                "_clean_norm_points",
                "_infer_legacy_ref_w_h",
                "_normalize_from_absolute",
                "_denormalize_to_absolute",
            },
            self.ns,
        )
        self.handler = self.ns["post_analytics_speed_lines"]

    def test_non_finite_distance_m_rejected_400(self) -> None:
        # On base the NaN/±inf values passed the `<= 0` guard and were persisted.
        for value in (float("nan"), float("inf"), float("-inf"), "nan", "inf"):
            with self.subTest(value=value):
                self.writes.clear()
                with self.assertRaises(HTTPExceptionStub) as raised:
                    self.handler("cam1", {"distance_m": value, "enabled": False})
                self.assertEqual(raised.exception.status_code, 400)
                self.assertEqual(raised.exception.detail, "distance_m must be a finite number")
                self.assertEqual(self.writes, [])

    def test_finite_and_range_behavior_unchanged(self) -> None:
        result = self.handler("cam1", {"distance_m": 57.0, "enabled": False})
        self.assertTrue(result["ok"])
        self.assertEqual(result["distance_m"], 57.0)
        self.assertFalse(result["enabled"])
        self.assertEqual(len(self.writes), 1)
        with self.assertRaises(HTTPExceptionStub) as raised:
            self.handler("cam1", {"distance_m": 0, "enabled": False})
        self.assertEqual(raised.exception.detail, "distance_m must be > 0")
        with self.assertRaises(HTTPExceptionStub) as raised:
            self.handler("cam1", {"distance_m": "abc"})
        self.assertEqual(raised.exception.detail, "distance_m must be a number")

    def test_valid_enabled_config_still_writes(self) -> None:
        payload = {
            "distance_m": 57.0,
            "enabled": True,
            "line_a_norm": [{"x_norm": 0.1, "y_norm": 0.1}, {"x_norm": 0.9, "y_norm": 0.1}],
            "line_b_norm": [{"x_norm": 0.1, "y_norm": 0.9}, {"x_norm": 0.9, "y_norm": 0.9}],
        }
        result = self.handler("cam1", payload)
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["line_a_norm"]), 2)
        self.assertEqual(len(self.writes), 1)

    def test_non_finite_line_point_cannot_complete_enabled_config(self) -> None:
        # Enabled calibration requires exactly 2 points per line; on base the
        # NaN point was clamped to 1.0 and the corrupted geometry was saved.
        payload = {
            "distance_m": 57.0,
            "enabled": True,
            "line_a_norm": [{"x_norm": 0.1, "y_norm": 0.1}, {"x_norm": float("nan"), "y_norm": 0.2}],
            "line_b_norm": [{"x_norm": 0.2, "y_norm": 0.2}, {"x_norm": 0.8, "y_norm": 0.8}],
        }
        with self.assertRaises(HTTPExceptionStub) as raised:
            self.handler("cam1", payload)
        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(self.writes, [])


class PatchObjectSpeedFiniteTests(unittest.TestCase):
    """Site 5: object update must 400 on non-finite speed_kmh."""

    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.ns: dict[str, Any] = {
            "Any": Any,
            "Dict": Dict,
            "List": List,
            "Optional": Optional,
            "Path": Path,
            "json": json,
            "hashlib": hashlib,
            "sqlite3": sqlite3,
            "contextmanager": contextmanager,
            "HTTPException": HTTPExceptionStub,
            "OBJECTS_DB_FILE": Path(temp.name) / "objects.sqlite3",
            "OBJECTS_RETENTION_LIMIT": 100,
            "OBJECT_STATUSES": ("new", "reviewed", "ignored"),
            "now_iso": lambda: "2026-11-01T00:00:00+00:00",
            "read_json_file": lambda path, default: default,
        }
        load_api_functions(
            [OBJECTS_REGISTRY_SOURCE],
            {
                "open_objects_db",
                "prune_objects_registry",
                "initialize_objects_db",
                "prune_snapshotless_objects",
                "optional_float",
                "optional_int",
                "stable_object_id",
                "persist_object_event",
                "object_row_to_dict",
                "patch_object_record",
            },
            self.ns,
        )
        self.ns["initialize_objects_db"]()
        self.assertTrue(
            self.ns["persist_object_event"](
                {
                    "event_id": "obj-577",
                    "camera_id": "cam1",
                    "class_name": "vessel",
                    "speed_kmh": 5.0,
                    "confidence": 0.9,
                    "snapshot_url": "/sea-speed/media/passages/obj-577.jpg",
                }
            )
        )
        self.patch = self.ns["patch_object_record"]

    def test_non_finite_speed_kmh_rejected_400(self) -> None:
        # On base NaN/±inf passed the `< 0` guard and were written to the registry.
        for value in (float("nan"), float("inf"), float("-inf"), "nan", "inf"):
            with self.subTest(value=value):
                with self.assertRaises(HTTPExceptionStub) as raised:
                    self.patch("obj-577", {"speed_kmh": value})
                self.assertEqual(raised.exception.status_code, 400)
                self.assertEqual(raised.exception.detail, "speed_kmh must be a finite number")

    def test_finite_null_and_range_behavior_unchanged(self) -> None:
        result = self.patch("obj-577", {"speed_kmh": 12.5})
        self.assertTrue(result["ok"])
        self.assertEqual(result["object"]["speed_kmh"], 12.5)
        result = self.patch("obj-577", {"speed_kmh": None})
        self.assertTrue(result["ok"])
        self.assertIsNone(result["object"]["speed_kmh"])
        with self.assertRaises(HTTPExceptionStub) as raised:
            self.patch("obj-577", {"speed_kmh": -1})
        self.assertEqual(raised.exception.detail, "speed_kmh must be >= 0")
        with self.assertRaises(HTTPExceptionStub) as raised:
            self.patch("obj-577", {"speed_kmh": "abc"})
        self.assertEqual(raised.exception.detail, "speed_kmh must be a number or null")


if __name__ == "__main__":
    unittest.main()
