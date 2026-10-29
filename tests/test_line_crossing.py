from __future__ import annotations

import ast
import copy
import importlib.util
import json
import sys
import tempfile
import time
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "worker" / "hls_motion_yolo_worker_events.py"
API = ROOT / "api" / "app" / "main.py"
# Issue #396 wave 2: objects-registry layer moved out of main.py.
OBJECTS_REGISTRY_SOURCE = ROOT / "api" / "app" / "objects_registry.py"
PASSAGE_MIRRORS_SOURCE = ROOT / "api" / "app" / "passage_mirrors.py"
# Issue #396 wave 3: the water-passages store moved out of main.py.
WATER_PASSAGES_SOURCE = ROOT / "api" / "app" / "water_passages.py"
# Issue #396 wave 5: the analytics services (crossing/passage record services
# and the ROI/points helpers) moved out of main.py.
ANALYTICS_SOURCE = ROOT / "api" / "app" / "analytics.py"
STORE_FILE = ROOT / "api" / "app" / "store.py"

try:
    from tests.support import frontend_html, worker_source
except ModuleNotFoundError:  # direct file execution: put the repo root on sys.path
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.support import frontend_html, worker_source


def _load_api_store():
    spec = importlib.util.spec_from_file_location("api_store_line_crossing_test", STORE_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _purge_crossings(namespace: dict[str, Any], camera_id: str) -> None:
    """Reset a camera's crossings rows so exact-count summary tests stay isolated."""
    with namespace["store"].open_state_db(namespace["STATE_DB_FILE"]) as connection:
        connection.execute("DELETE FROM crossings WHERE camera_id = ?", (camera_id,))


def extract_worker_functions(names: set[str]) -> dict[str, Any]:
    # 398-wave-a: shared AST-slice+exec harness (was a private duplicate pinned
    # to one path) — tests/support/worker_source.py resolves the worker source
    # by path so the #397 decomposition can move functions between files.
    namespace: dict[str, Any] = {
        "time": time,
        "json": json,
        "datetime": datetime,
        "timedelta": timedelta,
        "timezone": timezone,
        "uuid": uuid,
        "print": print,
        "env_str": lambda name, default=None: default,
        "env_float": lambda name, default=0.0: float(default),
        "requests": None,
        "_crossing_line_cache": {"ts": 0.0, "enabled": False, "line": [], "signature": ""},
        "_crossing_track_sides": {},
        "_crossing_counts": {"left_to_right": 0, "right_to_left": 0},
        "_crossings_by_class": {},
        "_crossing_pending_posts": [],
        "_crossing_vlz_date": None,
        "VLZ_TIMEZONE": timezone(timedelta(hours=10)),
    }
    return worker_source.load_functions(names, namespace)


def det(track_id: int, x1: float, y1: float, x2: float, y2: float, object_type: str = "car") -> Dict[str, Any]:
    return {
        "track_id": track_id,
        "bbox_xyxy": (x1, y1, x2, y2),
        "object_type": object_type,
        "class_name": object_type,
        "confidence": 0.9,
    }


VERTICAL_LINE = [(100, 0), (100, 576)]


class CrossingDetectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ns = extract_worker_functions(
            {
                "side_of_line",
                "sign_with_deadzone",
                "update_crossing_counts",
                "crossing_overlay_summary",
                "reset_crossing_counts",
                "prune_crossing_tracks",
                "maybe_reset_daily_crossings",
                "vlz_date",
            }
        )

    def setUp(self) -> None:
        self.ns["reset_crossing_counts"]()
        self.ns["_crossing_line_cache"].update({"enabled": True, "line": VERTICAL_LINE})
        self.ns["fetch_crossing_line_config"] = lambda: {"enabled": True, "line": VERTICAL_LINE}

    def test_left_to_right_crossing_counted_once(self) -> None:
        update = self.ns["update_crossing_counts"]
        update([det(7, 30, 100, 70, 140)], now=10.0)
        crossings = update([det(7, 130, 100, 170, 140)], now=11.0)
        self.assertEqual(len(crossings), 1)
        self.assertEqual(crossings[0]["direction"], "left_to_right")
        summary = self.ns["crossing_overlay_summary"]()
        self.assertEqual(summary["left_to_right"], 1)
        self.assertEqual(summary["right_to_left"], 0)

    def test_right_to_left_crossing_counted(self) -> None:
        update = self.ns["update_crossing_counts"]
        update([det(3, 130, 100, 170, 140)], now=10.0)
        crossings = update([det(3, 30, 100, 70, 140)], now=11.0)
        self.assertEqual(len(crossings), 1)
        self.assertEqual(crossings[0]["direction"], "right_to_left")

    def test_wobble_within_cooldown_does_not_double_count(self) -> None:
        update = self.ns["update_crossing_counts"]
        update([det(5, 30, 100, 70, 140)], now=10.0)
        first = update([det(5, 130, 100, 170, 140)], now=11.0)
        wobble = update([det(5, 30, 100, 70, 140)], now=11.5)
        self.assertEqual(len(first), 1)
        self.assertEqual(wobble, [])
        summary = self.ns["crossing_overlay_summary"]()
        self.assertEqual(summary["left_to_right"] + summary["right_to_left"], 1)

    def test_person_detections_are_counted(self) -> None:
        update = self.ns["update_crossing_counts"]
        update([det(9, 30, 100, 70, 140, object_type="person")], now=10.0)
        crossings = update([det(9, 130, 100, 170, 140, object_type="person")], now=11.0)
        self.assertEqual(len(crossings), 1)
        self.assertEqual(crossings[0]["direction"], "left_to_right")
        summary = self.ns["crossing_overlay_summary"]()
        self.assertEqual(summary["by_class"]["person"]["left_to_right"], 1)

    def test_disabled_line_counts_nothing(self) -> None:
        self.ns["fetch_crossing_line_config"] = lambda: {"enabled": False, "line": []}
        update = self.ns["update_crossing_counts"]
        update([det(4, 30, 100, 70, 140)], now=10.0)
        self.assertEqual(update([det(4, 130, 100, 170, 140)], now=11.0), [])

    def test_by_class_grouping_and_pending_posts(self) -> None:
        update = self.ns["update_crossing_counts"]
        update([det(11, 30, 100, 70, 140, object_type="bus")], now=10.0)
        update([det(11, 130, 100, 170, 140, object_type="bus")], now=11.0)
        summary = self.ns["crossing_overlay_summary"]()
        self.assertEqual(summary["by_class"]["bus"]["left_to_right"], 1)
        pending = self.ns["_crossing_pending_posts"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["direction"], "left_to_right")
        self.assertEqual(pending[0]["object_type"], "bus")

    def test_crossing_snapshot_is_deeply_immutable(self) -> None:
        update = self.ns["update_crossing_counts"]
        update([det(21, 30, 100, 70, 140, object_type="car")], now=10.0)
        update([det(21, 130, 100, 170, 140, object_type="car")], now=11.0)
        first = self.ns["crossing_overlay_summary"]()

        update([det(22, 30, 100, 70, 140, object_type="car")], now=20.0)
        update([det(22, 130, 100, 170, 140, object_type="car")], now=21.0)
        current = self.ns["crossing_overlay_summary"]()

        self.assertEqual(first["left_to_right"], 1)
        self.assertEqual(first["by_class"]["car"]["left_to_right"], 1)
        self.assertEqual(current["left_to_right"], 2)
        self.assertEqual(current["by_class"]["car"]["left_to_right"], 2)
        for summary in (first, current):
            self.assertEqual(
                summary["left_to_right"],
                sum(v["left_to_right"] for v in summary["by_class"].values()),
            )
            self.assertEqual(
                summary["right_to_left"],
                sum(v["right_to_left"] for v in summary["by_class"].values()),
            )

    def test_crossing_payload_carries_measured_speed(self) -> None:
        update = self.ns["update_crossing_counts"]
        d = det(13, 30, 100, 70, 140, object_type="car")
        d["speed_kmh"] = 42.5
        update([d], now=10.0)
        d2 = det(13, 130, 100, 170, 140, object_type="car")
        d2["speed_kmh"] = 42.5
        crossings = update([d2], now=11.0)
        self.assertEqual(len(crossings), 1)
        self.assertEqual(crossings[0]["speed_kmh"], 42.5)


class OverlayLayoutTests(unittest.TestCase):
    def test_stats_block_moved_to_bottom_left(self) -> None:
        # 398-wave-a: converted from source-text pin (was L203-206) — the
        # stats block must anchor to the bottom of the frame (y computed from
        # block height) and the legacy top-anchored y = 24 must stay removed.
        draw = worker_source.function_node("draw_overlay")
        y_assignments = worker_source.find_assignments(draw, "y")
        self.assertTrue(
            any(worker_source.dump(a.value) == worker_source.expr_dump("height - block_height + line_height - 4") for a in y_assignments),
            "stats block must anchor y to height - block_height + line_height - 4",
        )
        for assignment in y_assignments:
            value = assignment.value
            self.assertFalse(
                isinstance(value, ast.Constant) and value.value == 24,
                "stats block must not regress to the top-anchored y = 24",
            )

    def test_counter_block_drawn_bottom_right(self) -> None:
        # 398-wave-a: converted from source-text pin (was L208-212) — the
        # crossing counter block keeps its optional crossing_summary parameter
        # (None default), renders right-aligned at width - 16 - tw, and keeps
        # the "CROSSINGS ->" label.
        draw = worker_source.function_node("draw_overlay")
        summary_params = [
            (arg, default)
            for arg, default in zip(
                reversed(draw.args.args),
                reversed([*draw.args.defaults]),
            )
        ]
        self.assertTrue(
            any(arg.arg == "crossing_summary" and isinstance(default, ast.Constant) and default.value is None for arg, default in summary_params),
            "draw_overlay must keep the optional crossing_summary parameter (None default)",
        )
        self.assertTrue(
            worker_source.contains_expr(draw, "(width - 16 - tw, c_y)"),
            "counter text must render right-aligned at width - 16 - tw",
        )
        self.assertTrue(
            any(part.startswith("CROSSINGS ->") for part in worker_source.string_constants(draw)),
            "counter block must keep the CROSSINGS -> label",
        )


class _StubHTTPException(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


CROSSING_API_FUNCTIONS = {
    "_vlz_day_bounds",
    "clean_points_list",
    "_clean_norm_points",
    "_infer_legacy_ref_w_h",
    "_normalize_from_absolute",
    "_denormalize_to_absolute",
    "_normalize_legacy_polygon",
    "optional_int",
    "optional_float",
    "get_analytics_crossing_line",
    "post_analytics_crossing_line",
    "post_analytics_crossing",
    "append_crossing_record",
    "get_analytics_crossings_summary",
}


class ApiCrossingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.namespace: dict[str, Any] = {
            "HTTPException": _StubHTTPException,
            "Path": Path,
            "json": json,
            "time": time,
            "uuid": uuid,
            "datetime": datetime,
            "date": date,
            "timedelta": timedelta,
            "timezone": timezone,
            "VLZ_TIMEZONE": timezone(timedelta(hours=10)),
            "Any": Any,
            "Dict": Dict,
            "List": List,
            "DEFAULT_ROI_REF_W": 1920,
            "DEFAULT_ROI_REF_H": 1080,
            "LEGACY_ROI_W": 704,
            "LEGACY_ROI_H": 576,
            "DATA_DIR": Path(cls.tmp.name),
            "CROSSINGS_STORE_LIMIT": 5000,
            "CROSSING_DIRECTIONS": ("left_to_right", "right_to_left"),
            "now_iso": lambda: datetime.now(timezone.utc).isoformat(),
            "analytics_identity": lambda camera_id: (
                {"domain": "water", "analytics_profile": "water-v1"}
                if camera_id == "cam1"
                else {"domain": "road", "analytics_profile": "road-v1"}
            ),
            "analytics_data_file": lambda camera_id, kind: Path(cls.tmp.name) / f"{camera_id}_{kind}.json",
            "read_json_file": lambda path, default: (
                json.loads(Path(path).read_text()) if Path(path).exists() else default
            ),
            "write_json_file": lambda path, data: Path(path).write_text(
                json.dumps(data, ensure_ascii=False)
            ),
            "store": _load_api_store(),
            "STATE_DB_FILE": Path(cls.tmp.name) / "state.sqlite3",
            "sys": sys,
        }
        cls.persisted: List[Dict[str, Any]] = []
        cls.namespace["persist_object_event"] = lambda event: cls.persisted.append(event) or True
        # Issue #396 wave 3: water_passages.py joined the walk (defensive —
        # the crossing slice stays in main.py this wave).
        # Issue #396 wave 5: the crossing/passage record services and the
        # ROI/points helpers moved to analytics.py — the walk follows them.
        tree_candidates = (API, OBJECTS_REGISTRY_SOURCE, PASSAGE_MIRRORS_SOURCE, WATER_PASSAGES_SOURCE, ANALYTICS_SOURCE)
        selected = []
        found = set()
        for source in tree_candidates:
            if not source.exists():
                continue
            tree = ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) and node.name in CROSSING_API_FUNCTIONS and node.name not in found:
                    cloned = copy.deepcopy(node)
                    cloned.decorator_list = []
                    selected.append(cloned)
                    found.add(node.name)
        missing = CROSSING_API_FUNCTIONS - found
        if missing:
            raise AssertionError(f"missing API functions: {sorted(missing)}")
        module = ast.Module(body=selected, type_ignores=[])
        ast.fix_missing_locations(module)
        exec(compile(module, str(API), "exec"), cls.namespace)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def setUp(self) -> None:
        self.ns = type(self).namespace
        self.persisted = type(self).persisted
        self.persisted.clear()

    def test_crossing_line_config_round_trip(self) -> None:
        ns = self.ns
        empty = ns["get_analytics_crossing_line"]("road1")
        self.assertFalse(empty["enabled"])
        config = ns["post_analytics_crossing_line"](
            "road1", {"enabled": True, "line": [{"x": 10, "y": 20}, {"x": 30, "y": 40}]}
        )
        self.assertTrue(config["enabled"])
        self.assertEqual(len(config["line"]), 2)
        reread = ns["get_analytics_crossing_line"]("road1")
        # legacy 704 → normalized → 1920 HD response
        self.assertEqual(reread["line"], [{"x": 27, "y": 38}, {"x": 82, "y": 75}])

    def test_crossing_line_validation_rejects_bad_payload(self) -> None:
        ns = self.ns
        with self.assertRaises(_StubHTTPException):
            ns["post_analytics_crossing_line"]("road1", {"enabled": True, "line": [{"x": 1}]})

    def test_ingest_persists_registry_row_and_store(self) -> None:
        ns = self.ns
        result = ns["post_analytics_crossing"](
            "road1",
            {
                "track_id": 12,
                "object_type": "car",
                "direction": "left_to_right",
                "confidence": 0.8,
            },
        )
        self.assertTrue(result["ok"])
        self.assertEqual(len(self.persisted), 1)
        row = self.persisted[0]
        self.assertEqual(row["domain"], "road")
        self.assertEqual(row["kind"], "line_crossing")
        store = ns["store"].read_crossings(ns["STATE_DB_FILE"], "road1")
        self.assertEqual(store[0]["event_id"], result["event_id"])
        speed_row = ns["post_analytics_crossing"](
            "road1",
            {
                "track_id": 14,
                "object_type": "car",
                "direction": "right_to_left",
                "confidence": 0.9,
                "speed_kmh": 57.3,
            },
        )
        self.assertTrue(speed_row["ok"])
        self.assertAlmostEqual(self.persisted[-1]["speed_kmh"], 57.3)

    def test_road_person_crossing_skips_registry_but_feeds_store(self) -> None:
        ns = self.ns
        result = ns["post_analytics_crossing"](
            "road1",
            {
                "track_id": 21,
                "object_type": "person",
                "direction": "right_to_left",
                "confidence": 0.7,
            },
        )
        self.assertTrue(result["ok"])
        self.assertEqual(self.persisted, [])
        store = ns["store"].read_crossings(ns["STATE_DB_FILE"], "road1")
        self.assertEqual(store[0]["object_type"], "person")

    def test_water_person_crossing_would_persist_registry(self) -> None:
        ns = self.ns
        ns["post_analytics_crossing"](
            "cam1",
            {
                "track_id": 22,
                "object_type": "vessel",
                "direction": "left_to_right",
            },
        )
        self.assertEqual(len(self.persisted), 1)

    def test_ingest_rejects_unknown_direction(self) -> None:
        with self.assertRaises(_StubHTTPException):
            self.ns["post_analytics_crossing"]("road1", {"object_type": "car", "direction": "up"})

    def test_summary_aggregates_within_window_by_class(self) -> None:
        ns = self.ns
        now = datetime.now(timezone.utc)
        old_ts = (now - timedelta(hours=30)).isoformat()
        fresh_ts = (now - timedelta(hours=1)).isoformat()
        _purge_crossings(ns, "cam1")
        for record in (
            {"object_type": "vessel", "direction": "left_to_right", "created_at": old_ts},
            {"object_type": "vessel", "direction": "left_to_right", "created_at": fresh_ts},
            {"object_type": "vessel", "direction": "right_to_left", "created_at": fresh_ts},
        ):
            ns["store"].append_crossing(ns["STATE_DB_FILE"], "cam1", record, 5000)
        summary = ns["get_analytics_crossings_summary"]("cam1", hours=24)
        self.assertEqual(summary["totals"], {"left_to_right": 1, "right_to_left": 1})
        self.assertEqual(summary["by_class"]["vessel"]["left_to_right"], 1)

    def test_summary_default_domain_identity(self) -> None:
        summary = self.ns["get_analytics_crossings_summary"]("road1", hours=24)
        self.assertEqual(summary["domain"], "road")


class Cam1LegacyKindFallbackTests(unittest.TestCase):
    def test_cam1_unknown_kind_falls_back_to_data_dir(self) -> None:
        # Issue #396 wave 5: the cam1 legacy-kind fallback moved with the
        # crossing slice into analytics.py. 398-wave-4: the source-text pin
        # became an AST twin — the fallback condition must exist as a real
        # boolean expression (comment-blind, rename-tolerant).
        tree = ast.parse(ANALYTICS_SOURCE.read_text(encoding="utf-8-sig"), filename=str(ANALYTICS_SOURCE))
        self.assertTrue(
            worker_source.contains_expr(tree, 'camera_id == "cam1" and kind in legacy'),
            "the cam1 legacy-kind fallback condition must stay in the crossing slice",
        )


class CrossingUrlTests(unittest.TestCase):
    def test_crossing_line_url_derived_from_state_path(self) -> None:
        for state_url, expected in [
            ("http://10.0.0.5:8010/api/cam1/state", "http://10.0.0.5:8010/api/cam1/crossing-line"),
            ("http://10.0.0.5:8010/api/analytics/road1/state", "http://10.0.0.5:8010/api/analytics/road1/crossing-line"),
        ]:
            ns = extract_worker_functions({"get_crossing_line_url"})
            ns["env_str"] = lambda name, default=None, _u=state_url: _u if name == "SEA_SPEED_API_URL" else default
            self.assertEqual(ns["get_crossing_line_url"](), expected)

    def test_post_crossing_url_has_no_duplicated_path(self) -> None:
        # 398-wave-a: converted from source-text pin (was L441-445) — now
        # behavioral: post_crossing must derive the crossing ingest URL from
        # the state URL by trimming its last path segment (never by
        # interpolating the camera id into an /analytics/ template), proven by
        # executing the live function against a recording requests stub; an
        # AST negative keeps the module free of f-string-built crossing URLs.
        posts: list[str] = []

        class FakeResponse:
            status_code = 200

        class FakeRequests:
            @staticmethod
            def post(url: str, headers: object = None, data: object = None, timeout: object = None):
                posts.append(url)
                return FakeResponse()

        ns: dict[str, Any] = {
            "requests": FakeRequests,
            "env_str": lambda name, default="": {
                "SEA_SPEED_API_URL": "http://10.0.0.5:8010/api/cam1/state",
                "SEA_SPEED_API_TOKEN": "token",
            }.get(name, default),
            "json": json,
        }
        worker_source.load_functions({"post_crossing"}, ns)
        self.assertTrue(ns["post_crossing"]({"direction": "left_to_right"}))
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0], "http://10.0.0.5:8010/api/cam1/crossings")
        self.assertNotIn("/analytics/", posts[0])
        for tree in worker_source.module_trees():
            for part in worker_source.joined_string_constants(tree):
                self.assertNotIn("/crossings", part)
                self.assertNotIn("/crossing-line", part)

    def test_overlay_summary_includes_line_points(self) -> None:
        ns = extract_worker_functions({"crossing_overlay_summary", "reset_crossing_counts"})
        ns["reset_crossing_counts"]()
        ns["_crossing_line_cache"].update({"enabled": True, "line": [(10, 20), (30, 40)]})
        summary = ns["crossing_overlay_summary"]()
        self.assertEqual(summary["line"], [[10, 20], [30, 40]])


NGINX_AUTH = ROOT / "scripts" / "operations" / "nginx_sea_speed_auth.py"


class IngressAllowlistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.namespace: dict[str, Any] = {}
        exec(compile(NGINX_AUTH.read_text(encoding="utf-8"), str(NGINX_AUTH), "exec"), cls.namespace)
        cls.endpoints = set(cls.namespace["WORKER_PRIVATE_ENDPOINTS"])

    def test_exactly_four_new_crossing_endpoints_with_exact_methods(self) -> None:
        crossing = {e for e in self.endpoints if "crossing" in e[0]}
        expected = {
            ("/api/cam1/crossing-line", "GET"),
            ("/api/cam1/crossings", "POST"),
            ("/api/analytics/road1/crossing-line", "GET"),
            ("/api/analytics/road1/crossings", "POST"),
        }
        self.assertEqual(crossing, expected)

    def test_previously_allowed_endpoints_remain(self) -> None:
        for endpoint in (
            ("/api/cam1/state", "POST"),
            ("/api/cam1/events", "POST"),
            ("/api/cam1/passages", "POST"),
            ("/api/cam1/speed-lines", "GET"),
            ("/api/analytics/road1/state", "POST"),
            ("/api/analytics/road1/events", "POST"),
            ("/api/analytics/road1/speed-lines", "GET"),
        ):
            self.assertIn(endpoint, self.endpoints)

    def test_worker_control_never_exposed(self) -> None:
        for path, _method in self.endpoints:
            self.assertFalse(path.startswith("/api/worker/control"))

    def test_no_wildcard_or_prefix_locations_for_crossings(self) -> None:
        for path, _method in self.endpoints:
            self.assertTrue(path.startswith("/"))
            self.assertNotIn("*", path)


class RetryQueueTests(unittest.TestCase):
    def _namespace_with_posts(self, results):
        ns = extract_worker_functions({"flush_crossing_posts"})
        calls = []
        iterator = iter(results)

        def post_crossing(crossing):
            calls.append(crossing)
            return next(iterator)

        ns["post_crossing"] = post_crossing
        return ns, calls

    def test_failed_post_keeps_event_in_queue(self) -> None:
        ns, calls = self._namespace_with_posts([False])
        ns["_crossing_pending_posts"].append({"direction": "left_to_right"})
        ns["flush_crossing_posts"]()
        self.assertEqual(len(ns["_crossing_pending_posts"]), 1)
        self.assertEqual(len(calls), 1)

    def test_successful_retry_removes_event_exactly_once(self) -> None:
        ns, calls = self._namespace_with_posts([False, True])
        event = {"direction": "right_to_left"}
        ns["_crossing_pending_posts"].append(event)
        ns["flush_crossing_posts"]()
        self.assertEqual(len(ns["_crossing_pending_posts"]), 1)
        ns["flush_crossing_posts"]()
        self.assertEqual(ns["_crossing_pending_posts"], [])
        self.assertEqual(len(calls), 2)
        self.assertIs(calls[0], event)
        self.assertIs(calls[1], event)


class OverlayLineColorTests(unittest.TestCase):
    def test_counting_line_drawn_yellow_bgr(self) -> None:
        # 398-wave-a: converted from source-text pin (was L530-534) — the
        # counting line must be drawn by a cv2.line call in yellow BGR
        # (0, 255, 255) at width 2 with anti-aliasing, and the retired
        # (255, 210, 60) color must stay out of the whole worker module.
        draw = worker_source.function_node("draw_overlay")
        yellow_lines = [
            call
            for call in worker_source.method_calls(draw, "cv2", "line")
            if (0, 255, 255) in worker_source.tuple_constants(call)
            and any(isinstance(arg, ast.Constant) and arg.value == 2 for arg in call.args)
            and any(
                isinstance(arg, ast.Attribute)
                and arg.attr == "LINE_AA"
                and isinstance(arg.value, ast.Name)
                and arg.value.id == "cv2"
                for arg in call.args
            )
        ]
        self.assertTrue(yellow_lines, "counting line must be drawn yellow BGR (0, 255, 255), width 2, cv2.LINE_AA")
        for tree in worker_source.module_trees():
            self.assertNotIn((255, 210, 60), worker_source.tuple_constants(tree), "retired line color must stay removed")


CROSSING_PANEL_BOOT_RESPONSE = {
    "match": "/crossing-line",
    "json": {"enabled": True, "line": [{"x": 100, "y": 0}, {"x": 100, "y": 576}]},
}

# Executed crossing-panel twins (water + road). Both pages wire the panel
# handlers onto the same recorded element ids (water: the crossingCard panel
# IIFE; road: the main script's crossingCfg handlers), so one page-agnostic
# scenario drives the real handlers on both pages. The panel API prefix is
# derived from the recorded boot GET instead of hardcoding per-page URLs.
CROSSING_PANEL_PREAMBLE = """
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
  const lineCalls = () => __record.fetch.filter((c) => c.url.endsWith("/crossing-line"));
  const bootGet = lineCalls().find((c) => (c.options.method || "GET") === "GET");
  assert(bootGet, "panel must load the crossing-line config at boot");
  assert(bootGet.options.credentials === "same-origin", "crossing-line config fetch must be same-origin");
  const api = bootGet.url.slice(0, -"/crossing-line".length);
  const postsToLine = () => lineCalls().filter((c) => (c.options.method || "GET") === "POST" && c.url === api + "/crossing-line");
"""

CROSSING_TOGGLE_SCENARIO = """
;(async () => {
""" + CROSSING_PANEL_PREAMBLE + """
  assert(__record.elements.cxStatus.textContent === "линия активна", "boot cfg enabled must show the active status: " + __record.elements.cxStatus.textContent);
  assert(__record.elements.cxOffBtn.textContent === "Выключить", "toggle label must follow cfg.enabled");
  __responses.length = 0;
  __setResponse("/crossing-line", { enabled: false, line: [{ x: 100, y: 0 }, { x: 100, y: 576 }] });
  await __record.elements.cxOffBtn.onclick();
  await new Promise((r) => setImmediate(r));
  let posts = postsToLine();
  assert(posts.length === 1, "disable must POST the crossing-line config exactly once");
  let body = JSON.parse(posts[0].options.body);
  assert(body.enabled === false && body.line.length === 2 && body.line[0].x === 100 && body.line[1].y === 576, "disable POST must carry enabled:false + the loaded line: " + posts[0].options.body);
  assert(__record.elements.cxStatus.textContent === "линия выключена", "disable must report the off status: " + __record.elements.cxStatus.textContent);
  assert(__record.elements.cxOffBtn.textContent === "Включить", "toggle label must flip after disable");
  __responses.length = 0;
  __setResponse("/crossing-line", { enabled: true, line: [{ x: 100, y: 0 }, { x: 100, y: 576 }] });
  await __record.elements.cxOffBtn.onclick();
  await new Promise((r) => setImmediate(r));
  posts = postsToLine();
  assert(posts.length === 2, "enable must POST the crossing-line config exactly once");
  body = JSON.parse(posts[1].options.body);
  assert(body.enabled === true && body.line.length === 2 && body.line[0].x === 100 && body.line[1].y === 576, "enable POST must carry enabled:true + the line: " + posts[1].options.body);
  assert(__record.elements.cxStatus.textContent === "линия включена", "enable must report the enabled status: " + __record.elements.cxStatus.textContent);
  assert(__record.elements.cxOffBtn.textContent === "Выключить", "toggle label must flip after enable");
  console.log("###" + JSON.stringify({ api, posts: posts.length }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""

CROSSING_DELETE_SCENARIO = """
;(async () => {
""" + CROSSING_PANEL_PREAMBLE + """
  __responses.length = 0;
  __setResponse("/crossing-line", { enabled: false, line: [] });
  await __record.elements.cxUndoBtn.onclick();
  await new Promise((r) => setImmediate(r));
  const posts = postsToLine();
  assert(posts.length === 1, "delete must POST the crossing-line config exactly once");
  const body = JSON.parse(posts[0].options.body);
  assert(body.enabled === false && Array.isArray(body.line) && body.line.length === 0, "delete must persist the disabled empty state: " + posts[0].options.body);
  assert(__record.elements.cxStatus.textContent === "линия удалена", "delete must report the removal: " + __record.elements.cxStatus.textContent);
  assert(__record.elements.cxOffBtn.textContent === "Включить", "toggle label must offer enable after delete");
  console.log("###" + JSON.stringify({ api, posts: posts.length }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""

# Executed DOM-guard twin (water page): booted while document.readyState is
# "loading", the panel must not touch the crossing-line API and must register
# a document DOMContentLoaded listener; firing it runs the deferred init
# exactly once (config GET + cfg consumed into the status/toggle UI).
CROSSING_DOM_GUARD_SCENARIO = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
  const lineCalls = () => __record.fetch.filter((c) => c.url.endsWith("/crossing-line"));
  assert(lineCalls().length === 0, "panel init must stay deferred while the DOM is loading");
  const dcl = __record.listeners.filter(([scope, type]) => scope === "document" && type === "DOMContentLoaded");
  assert(dcl.length >= 1, "panel must register a document DOMContentLoaded listener while the DOM is loading");
  for (const [, , fn] of dcl) fn();
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
  const gets = lineCalls().filter((c) => (c.options.method || "GET") === "GET");
  assert(gets.length === 1, "firing DOMContentLoaded must load the crossing-line config exactly once");
  assert(gets[0].options.cache === "no-store" && gets[0].options.credentials === "same-origin", "deferred config fetch must be same-origin no-store");
  assert(__record.elements.cxStatus.textContent === "линия активна", "deferred init must consume the config into the status: " + __record.elements.cxStatus.textContent);
  assert(__record.elements.cxOffBtn.textContent === "Выключить", "deferred init must sync the toggle label");
  console.log("###" + JSON.stringify({ gets: gets.length }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


class CrossingPanelUiTests(unittest.TestCase):
    PANEL_PAGES = (ROOT / "frontend/sea-speed/index.html", ROOT / "frontend/sea-speed/road/index.html")

    def test_delete_line_button_replaces_point_undo(self) -> None:
        # SS: the button labels are static panel markup (no AST/behavior beyond
        # the label text); the executed delete behavior is the twin below.
        for page in self.PANEL_PAGES:
            text = page.read_text(encoding="utf-8")
            start = text.index('id="crossingCard"')
            block = text[start:text.index("</details>", start)]
            self.assertIn(">Удалить линию<", block)
            self.assertNotIn("Отменить точку", block)

    def test_delete_line_persists_disabled_empty_state(self) -> None:
        # Executed twin: the recorded cxUndoBtn handler must POST the disabled
        # empty config and report the removal on both pages.
        for page in self.PANEL_PAGES:
            frontend_html.run_inline_scripts(
                source=page,
                scenario=CROSSING_DELETE_SCENARIO,
                responses=[CROSSING_PANEL_BOOT_RESPONSE],
            )

    def test_off_button_is_dynamic_toggle(self) -> None:
        # Executed twin: the recorded cxOffBtn handler must toggle the config
        # through the API (enabled:false keeping the line, then enabled:true
        # with it), keep the label in sync, and the boot response must drive
        # the initial label — on both pages.
        for page in self.PANEL_PAGES:
            frontend_html.run_inline_scripts(
                source=page,
                scenario=CROSSING_TOGGLE_SCENARIO,
                responses=[CROSSING_PANEL_BOOT_RESPONSE],
            )


class CrossingPanelDomGuardTests(unittest.TestCase):
    """Regression pin: the panel script must defer init until the DOM is fully
    parsed — on pages where the utilities rail renders before the camera stage,
    an immediate getElementById returns null and the panel silently dies."""

    def test_panel_init_deferred_until_dom_ready(self) -> None:
        # Executed twin (water page): booting with readyState "loading" must
        # keep the panel off the wire until the recorded DOMContentLoaded
        # listener fires. The road page's crossingCard script block is a
        # deliberate DOM-contract stub (the real road handlers live in the
        # main script and are proven by the executed toggle/delete twins), so
        # its guard markers stay a structural scan.
        frontend_html.run_inline_scripts(
            source=ROOT / "frontend/sea-speed/index.html",
            scenario=CROSSING_DOM_GUARD_SCENARIO,
            responses=[CROSSING_PANEL_BOOT_RESPONSE],
            ready_state="loading",
        )
        text = (ROOT / "frontend/sea-speed/road/index.html").read_text(encoding="utf-8")
        start = text.index('id="crossingCard"')
        block = text[start:text.index("</script>", start)]
        self.assertIn('document.readyState==="loading"', block)
        self.assertIn('addEventListener("DOMContentLoaded",init)', block)
        self.assertIn("function init(){", block)


class CrossingConfigRefreshTests(unittest.TestCase):
    def test_config_refresh_default_is_one_second(self) -> None:
        # 398-wave-a: converted from source-text pin (was L582-585) — every
        # CROSSING_LINE_REFRESH_SEC read must default to 1.0 (catches any
        # re-introduced default, not just the historical 5.0).
        refresh_calls = [
            call
            for tree in worker_source.module_trees()
            for call in worker_source.calls_with_constant_arg(tree, "env_float", "CROSSING_LINE_REFRESH_SEC")
        ]
        self.assertTrue(refresh_calls, "worker must read CROSSING_LINE_REFRESH_SEC")
        for call in refresh_calls:
            self.assertEqual(
                worker_source.dump(call.args[1]),
                worker_source.expr_dump("1.0"),
                "CROSSING_LINE_REFRESH_SEC default must stay 1.0s",
            )


class VlzDailyResetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ns = extract_worker_functions(
            {"reset_crossing_counts", "maybe_reset_daily_crossings", "vlz_date",
             "crossing_overlay_summary", "prune_crossing_tracks"}
        )
        self.ns["reset_crossing_counts"]()

    def test_counters_reset_on_vlz_midnight(self) -> None:
        ns = self.ns
        # 2026-08-23 15:00 UTC == 2026-08-24 01:00 VLZ (next day)
        ns["maybe_reset_daily_crossings"](now=1_787_500_000)
        ns["_crossing_counts"]["left_to_right"] = 7
        ns["_crossings_by_class"]["car"] = {"left_to_right": 7, "right_to_left": 0}
        # same VLZ day -> no reset
        self.assertFalse(ns["maybe_reset_daily_crossings"](now=1_787_503_600))
        self.assertEqual(ns["_crossing_counts"]["left_to_right"], 7)
        # next VLZ day -> reset, but pending posts survive
        ns["_crossing_pending_posts"].append({"direction": "left_to_right"})
        self.assertTrue(ns["maybe_reset_daily_crossings"](now=1_787_590_000))
        self.assertEqual(ns["_crossing_counts"]["left_to_right"], 0)
        self.assertEqual(ns["_crossings_by_class"], {})
        self.assertEqual(len(ns["_crossing_pending_posts"]), 1)

    def test_vlz_date_is_utc_plus_ten(self) -> None:
        ns = self.ns
        # 2026-08-23 15:30 UTC is already 2026-08-24 in Vladivostok
        d = ns["vlz_date"](1_787_502_600)
        self.assertEqual((d.year, d.month, d.day), (2026, 8, 24))


class SummaryDateRangeTests(unittest.TestCase):
    def test_summary_supports_vlz_day_window_params(self) -> None:
        # Issue #396 wave 5: the crossings summary service moved to
        # analytics.py. 398-wave-4: the source-text pins became AST twins —
        # the summary handler signature keeps optional date_from/date_to
        # params, the VLZ window mode literal stays, and the VLZ timezone
        # offset assignment stays a real call expression.
        tree = ast.parse(ANALYTICS_SOURCE.read_text(encoding="utf-8-sig"), filename=str(ANALYTICS_SOURCE))
        summary = next(
            (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "get_analytics_crossings_summary"),
            None,
        )
        self.assertIsNotNone(summary, "get_analytics_crossings_summary must stay in the analytics module")
        positional = {
            arg.arg: default
            for arg, default in zip(
                summary.args.args[len(summary.args.args) - len(summary.args.defaults):],
                summary.args.defaults,
            )
        }
        kwonly = {arg.arg: default for arg, default in zip(summary.args.kwonlyargs, summary.args.kw_defaults)}
        defaults = {**positional, **kwonly}
        for param in ("date_from", "date_to"):
            self.assertIn(param, defaults, f"summary must keep the {param} parameter")
            self.assertIsInstance(defaults[param], ast.Constant)
            self.assertIsNone(defaults[param].value, f"{param} must default to None")
        vlz_mode_dicts = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Dict)
            and any(
                isinstance(k, ast.Constant) and k.value == "mode" and isinstance(v, ast.Constant) and v.value == "vlz_days"
                for k, v in zip(node.keys, node.values)
            )
        ]
        self.assertTrue(vlz_mode_dicts, "the summary window must keep the vlz_days mode literal")
        vlz_assignments = worker_source.find_assignments(tree, "VLZ_TIMEZONE")
        self.assertTrue(
            any(
                worker_source.dump(a.value) == worker_source.expr_dump("timezone(timedelta(hours=10))")
                for a in vlz_assignments
            ),
            "VLZ_TIMEZONE must stay UTC+10",
        )

    def test_summary_rejects_malformed_dates(self) -> None:
        ApiCrossingTests.setUpClass()  # fresh tmp so the SQLite store is openable
        ns = dict(ApiCrossingTests.namespace)
        with self.assertRaises(_StubHTTPException):
            ns["get_analytics_crossings_summary"]("road1", hours=24, date_from="bad-date")


class OverlayAllClassesTests(unittest.TestCase):
    def test_overlay_counter_has_no_class_cap(self) -> None:
        # 398-wave-a: converted from source-text pin (was L639-643) — no
        # sorted(...)[:5] capped iteration may exist anywhere in the worker
        # module (the historical class cap), and the counter block must keep
        # building its lines from the full "CROSSINGS" f-string list.
        for tree in worker_source.module_trees():
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Subscript)
                    and isinstance(node.slice, ast.Slice)
                    and isinstance(node.slice.upper, ast.Constant)
                    and node.slice.upper.value == 5
                    and isinstance(node.value, ast.Call)
                    and isinstance(node.value.func, ast.Name)
                    and node.value.func.id == "sorted"
                ):
                    self.fail("capped class iteration re-introduced: sorted(...)[:5]")
        draw = worker_source.function_node("draw_overlay")
        counter_assignments = worker_source.find_assignments(draw, "counter_lines")
        self.assertTrue(
            any(
                isinstance(a.value, ast.List)
                and any("CROSSINGS" in part for part in worker_source.joined_string_constants(a.value))
                for a in counter_assignments
            ),
            "overlay counter must be built from the CROSSINGS f-string without a class cap",
        )


OBJECTS_SPEED_RESPONSE = {
    "match": "/sea-speed/api/objects",
    "json": {
        "objects": [
            {
                "object_id": "obj-1",
                "class_name": "car",
                "camera_id": "road1",
                "domain": "road",
                "speed_kmh": 57.3,
                "status": "measured",
            }
        ],
        "total": 1,
        "count": 1,
    },
}

# Executed objects-registry twins: the page boots against the shim with the
# road scope (?scope=road via location_overrides) and the rendered card grid.
OBJECTS_SCOPE_SCENARIO = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
  assert(typeof registryScopeKey !== "undefined" && registryScopeKey === "road", "?scope=road must bind the global registry scope key: " + String(registryScopeKey));
  assert(typeof window.registryScopeKey === "undefined", "the scope binding must live in the script scope, not on window");
  const objectsFetch = __record.fetch.find((c) => c.url.startsWith("/sea-speed/api/objects"));
  assert(objectsFetch, "objects page must load the registry at boot");
  assert(objectsFetch.url.includes("camera_id=road1") && objectsFetch.url.includes("domain=road"), "road scope must query the road1 registry: " + objectsFetch.url);
  console.log("###" + JSON.stringify({ url: objectsFetch.url }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""

OBJECTS_SPEED_SCENARIO = """
;(async () => {
  const assert = (cond, msg) => { if (!cond) { console.error("FAIL: " + msg); process.exit(1); } };
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
  const grid = __record.elements.objectsGrid.innerHTML;
  assert(grid.includes('<div>Скорость<span class="meta-value">'), "object card must render the speed row: " + grid.slice(0, 300));
  assert(grid.includes("57.3"), "rendered card must carry the measured speed value");
  console.log("###" + JSON.stringify({ rendered: grid.includes("obj-1") }));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


class RegistrySpeedRowTests(unittest.TestCase):
    def test_registry_card_shows_speed_in_description(self) -> None:
        # Executed twin: the objects page must render a measured detection
        # into a card whose meta block carries the speed row and value.
        evidence = frontend_html.run_inline_scripts(
            source=ROOT / "frontend/sea-speed/objects/index.html",
            scenario=OBJECTS_SPEED_SCENARIO,
            responses=[OBJECTS_SPEED_RESPONSE],
        )
        self.assertTrue(evidence["rendered"])

    def test_objects_page_has_crossings_layer(self) -> None:
        # SS: static layer markup (container id + filter field names).
        text = (ROOT / "frontend/sea-speed/objects/index.html").read_text(encoding="utf-8")
        self.assertIn('id="crossingsLayer"', text)
        self.assertIn("date_from", text)


class CrossingsLayerToggleTests(unittest.TestCase):
    def test_toggle_button_is_outside_hidden_layer(self) -> None:
        # SS: static markup ordering (button before the hidden layer).
        text = (ROOT / "frontend/sea-speed/objects/index.html").read_text(encoding="utf-8")
        i_btn = text.index('id="cxViewBtn"')
        i_layer = text.index('id="crossingsLayer"')
        self.assertLess(i_btn, i_layer)


class SummaryVlzHappyPathTests(unittest.TestCase):
    def test_valid_date_window_returns_filtered_totals(self) -> None:
        ApiCrossingTests.setUpClass()
        ns = dict(ApiCrossingTests.namespace)
        _purge_crossings(ns, "road1")  # isolate store
        for record in (
            {"object_type": "bus", "direction": "right_to_left",
             "created_at": "2026-08-22T20:00:00+00:00"},
            {"object_type": "car", "direction": "left_to_right",
             "created_at": "2026-08-23T02:00:00+00:00"},
        ):
            ns["store"].append_crossing(ns["STATE_DB_FILE"], "road1", record, 5000)
        r = ns["get_analytics_crossings_summary"](
            "road1", hours=24, date_from="2026-08-23", date_to="2026-08-23")
        self.assertEqual(r["window"]["mode"], "vlz_days")
        # VLZ day 2026-08-23 spans 2026-08-22T14:00Z..2026-08-23T14:00Z,
        # so both records fall inside the window.
        self.assertEqual(r["totals"], {"left_to_right": 1, "right_to_left": 1})

    def test_toggle_button_lives_in_filter_actions_row(self) -> None:
        # SS: static markup containment (button inside the filter-actions row).
        text = (ROOT / "frontend/sea-speed/objects/index.html").read_text(encoding="utf-8")
        i_actions = text.index('class="filter-actions"')
        i_btn = text.index('id="cxViewBtn"')
        i_close = text.index("</div>", i_actions)
        self.assertLess(i_actions, i_btn)
        self.assertLess(i_btn, i_close)


class CrossingsLayerCameraScopeTests(unittest.TestCase):
    def test_layer_reads_global_scope_binding_not_window(self) -> None:
        # Executed twin: booting the objects page with ?scope=road must bind
        # registryScopeKey as a script-scope global (never a window property)
        # and the registry load must query the road1 camera/domain.
        evidence = frontend_html.run_inline_scripts(
            source=ROOT / "frontend/sea-speed/objects/index.html",
            scenario=OBJECTS_SCOPE_SCENARIO,
            location_overrides={"search": "?scope=road"},
        )
        self.assertTrue(evidence["url"].startswith("/sea-speed/api/objects"))
