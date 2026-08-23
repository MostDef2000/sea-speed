from __future__ import annotations

import ast
import copy
import json
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


def extract_worker_functions(names: set[str]) -> dict[str, Any]:
    tree = ast.parse(WORKER.read_text(encoding="utf-8-sig"), filename=str(WORKER))
    selected = []
    found = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            selected.append(copy.deepcopy(node))
            found.add(node.name)
    missing = names - found
    if missing:
        raise AssertionError(f"missing worker functions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
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
    exec(compile(module, str(WORKER), "exec"), namespace)
    return namespace


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
        text = WORKER.read_text(encoding="utf-8")
        self.assertIn("y = height - block_height + line_height - 4", text)
        self.assertNotIn("\n    y = 24\n", text)

    def test_counter_block_drawn_bottom_right(self) -> None:
        text = WORKER.read_text(encoding="utf-8")
        self.assertIn("crossing_summary=None", text)
        self.assertIn("(width - 16 - tw, c_y)", text)
        self.assertIn("CROSSINGS ->", text)


class _StubHTTPException(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


CROSSING_API_FUNCTIONS = {
    "clean_points_list",
    "optional_int",
    "optional_float",
    "get_analytics_crossing_line",
    "post_analytics_crossing_line",
    "post_analytics_crossing",
    "append_crossing_record",
    "crossings_store_path",
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
        }
        cls.persisted: List[Dict[str, Any]] = []
        cls.namespace["persist_object_event"] = lambda event: cls.persisted.append(event) or True
        tree = ast.parse(API.read_text(encoding="utf-8-sig"), filename=str(API))
        selected = []
        found = set()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in CROSSING_API_FUNCTIONS:
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
        self.assertEqual(reread["line"], [{"x": 10, "y": 20}, {"x": 30, "y": 40}])

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
        store = ns["read_json_file"](ns["crossings_store_path"]("road1"), [])
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
        store = ns["read_json_file"](ns["crossings_store_path"]("road1"), [])
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
        ns["write_json_file"](
            ns["crossings_store_path"]("cam1"),
            [
                {"object_type": "vessel", "direction": "left_to_right", "created_at": fresh_ts},
                {"object_type": "vessel", "direction": "right_to_left", "created_at": fresh_ts},
                {"object_type": "vessel", "direction": "left_to_right", "created_at": old_ts},
            ],
        )
        summary = ns["get_analytics_crossings_summary"]("cam1", hours=24)
        self.assertEqual(summary["totals"], {"left_to_right": 1, "right_to_left": 1})
        self.assertEqual(summary["by_class"]["vessel"]["left_to_right"], 1)

    def test_summary_default_domain_identity(self) -> None:
        summary = self.ns["get_analytics_crossings_summary"]("road1", hours=24)
        self.assertEqual(summary["domain"], "road")


class Cam1LegacyKindFallbackTests(unittest.TestCase):
    def test_cam1_unknown_kind_falls_back_to_data_dir(self) -> None:
        text = API.read_text(encoding="utf-8")
        self.assertIn('if camera_id == "cam1" and kind in legacy:', text)


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
        text = WORKER.read_text(encoding="utf-8")
        self.assertIn('url = state_url.rsplit("/", 1)[0] + "/crossings"', text)
        self.assertNotIn('f"/analytics/{camera_id}/crossings"', text)
        self.assertNotIn('f"/analytics/{camera_id}/crossing-line"', text)

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
        text = WORKER.read_text(encoding="utf-8")
        self.assertIn("(0, 255, 255), 2, cv2.LINE_AA", text)
        self.assertNotIn("(255, 210, 60)", text)


class CrossingPanelUiTests(unittest.TestCase):
    PANEL_PAGES = ("frontend/sea-speed/index.html", "frontend/sea-speed/road/index.html")

    def test_delete_line_button_replaces_point_undo(self) -> None:
        for rel in self.PANEL_PAGES:
            text = (ROOT / rel).read_text(encoding="utf-8")
            start = text.index('id="crossingCard"')
            block = text[start:text.index("</details>", start)]
            self.assertIn(">Удалить линию<", block)
            self.assertNotIn("Отменить точку", block)

    def test_delete_line_persists_disabled_empty_state(self) -> None:
        for rel in self.PANEL_PAGES:
            text = (ROOT / rel).read_text(encoding="utf-8")
            start = text.index('id="cxUndoBtn"')
            block = text[start:text.index("</script>", start)]
            self.assertIn("enabled:false,line:[]", block)
            self.assertIn("линия удалена", block)

    def test_off_button_is_dynamic_toggle(self) -> None:
        for rel in self.PANEL_PAGES:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn('cfg.enabled?"Выключить":"Включить"', text)
            start = text.index('id="cxOffBtn"')
            block = text[start:text.index("</script>", start)]
            self.assertIn("нет линии для включения", block)
            self.assertIn("линия включена", block)


class CrossingPanelDomGuardTests(unittest.TestCase):
    """Regression pin: the panel script must defer init until the DOM is fully
    parsed — on pages where the utilities rail renders before the camera stage,
    an immediate getElementById returns null and the panel silently dies."""

    def test_panel_init_deferred_until_dom_ready(self) -> None:
        for rel in CrossingPanelUiTests.PANEL_PAGES:
            text = (ROOT / rel).read_text(encoding="utf-8")
            start = text.index('id="crossingCard"')
            block = text[start:text.index("</script>", start)]
            self.assertIn('document.readyState==="loading"', block)
            self.assertIn('addEventListener("DOMContentLoaded",init)', block)
            self.assertIn("function init(){", block)


class CrossingConfigRefreshTests(unittest.TestCase):
    def test_config_refresh_default_is_one_second(self) -> None:
        text = WORKER.read_text(encoding="utf-8")
        self.assertIn('env_float("CROSSING_LINE_REFRESH_SEC", 1.0)', text)
        self.assertNotIn('env_float("CROSSING_LINE_REFRESH_SEC", 5.0)', text)


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
        text = API.read_text(encoding="utf-8")
        self.assertIn("date_from: Optional[str] = None, date_to: Optional[str] = None", text)
        self.assertIn('"mode": "vlz_days"', text)
        self.assertIn("VLZ_TIMEZONE = timezone(timedelta(hours=10))", text)

    def test_summary_rejects_malformed_dates(self) -> None:
        ns = dict(ApiCrossingTests.namespace)
        with self.assertRaises(_StubHTTPException):
            ns["get_analytics_crossings_summary"]("road1", hours=24, date_from="bad-date")


class OverlayAllClassesTests(unittest.TestCase):
    def test_overlay_counter_has_no_class_cap(self) -> None:
        text = WORKER.read_text(encoding="utf-8")
        self.assertNotIn(')[:5]:', text)
        self.assertIn('for class_name, counts in sorted(by_class.items()', text)


class RegistrySpeedRowTests(unittest.TestCase):
    def test_registry_card_shows_speed_in_description(self) -> None:
        text = (ROOT / "frontend/sea-speed/objects/index.html").read_text(encoding="utf-8")
        self.assertIn("<div>Скорость<span class=\"meta-value\">", text)

    def test_objects_page_has_crossings_layer(self) -> None:
        text = (ROOT / "frontend/sea-speed/objects/index.html").read_text(encoding="utf-8")
        self.assertIn('id="crossingsLayer"', text)
        self.assertIn("date_from", text)


class CrossingsLayerToggleTests(unittest.TestCase):
    def test_toggle_button_is_outside_hidden_layer(self) -> None:
        text = (ROOT / "frontend/sea-speed/objects/index.html").read_text(encoding="utf-8")
        i_btn = text.index('id="cxViewBtn"')
        i_layer = text.index('id="crossingsLayer"')
        self.assertLess(i_btn, i_layer)
