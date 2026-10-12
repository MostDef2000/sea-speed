"""Route-table fingerprint for the FastAPI app surface (issue #396, wave 2).

The main.py decomposition waves (issue #396) move code out of ``main.py``
wave by wave; this guard freezes the complete endpoint table parsed from
``main.py`` at the wave-2 base commit so any wave that accidentally adds,
drops or renames an endpoint fails loudly.

AST-level and import-free on purpose: the app boots against /opt state the
test environment does not provide, and the fingerprint only needs the
decorator syntax, so the check is deterministic and side-effect free.

Issue #396 wave 3 hardening (wave-2 peer-review follow-up): the fingerprint
pins the handler function name too — every entry is
``(handler_name, method, path)`` — so a wave that rewires a route to a
different function fails even when the method/path surface is unchanged.
"""

import ast
import unittest
from pathlib import Path

MAIN_SOURCE = Path(__file__).resolve().parent.parent / "api" / "app" / "main.py"

# Frozen at 38595d3245d53729568c7557ea6ba46c536e3ec0 (issue #396 wave 3 base):
# 61 @app.* endpoints, parsed with the same walker as the test below. Each
# entry is "<METHOD> <path>" -> "handler_name" (wave-3 route-name pinning).
EXPECTED_ROUTE_FINGERPRINTS = {
    "DELETE /api/cam1/objects/{object_id}": "delete_cam1_object",
    "DELETE /api/objects/{object_id}": "delete_object",
    "GET /api/analytics/road1/live": "get_road_live",
    "GET /api/analytics/road1/live/stream": "road_live_stream_internal",
    "GET /api/analytics/{camera_id}/crossing-line": "api_get_crossing_line",
    "GET /api/analytics/{camera_id}/crossings/summary": "api_get_crossings_summary",
    "GET /api/analytics/{camera_id}/events": "get_analytics_events",
    "GET /api/analytics/{camera_id}/objects": "get_analytics_objects",
    "GET /api/analytics/{camera_id}/roi": "get_analytics_roi",
    "GET /api/analytics/{camera_id}/speed-config": "get_analytics_speed_config",
    "GET /api/analytics/{camera_id}/speed-lines": "get_analytics_speed_lines",
    "GET /api/analytics/{camera_id}/state": "get_analytics_state",
    "GET /api/cam1/crossing-line": "get_cam1_crossing_line",
    "GET /api/cam1/crossings/summary": "get_cam1_crossings_summary",
    "GET /api/cam1/events": "get_cam1_events",
    "GET /api/cam1/live": "get_water_live",
    "GET /api/cam1/live/stream": "water_live_stream_internal",
    "GET /api/cam1/objects": "get_cam1_objects",
    "GET /api/cam1/objects/{object_id}": "get_cam1_object",
    "GET /api/cam1/passages": "get_cam1_passages",
    "GET /api/cam1/roi": "get_cam1_roi",
    "GET /api/cam1/speed-config": "get_cam1_speed_config",
    "GET /api/cam1/speed-lines": "get_cam1_speed_lines",
    "GET /api/cam1/state": "get_cam1_state",
    "GET /api/cameras": "get_cameras",
    "GET /api/cameras/preview": "get_camera_preview",
    "GET /api/cameras/{camera_id}/snapshot": "get_camera_snapshot",
    "GET /api/health": "health",
    "GET /api/objects": "get_objects",
    "GET /api/objects/{object_id}": "get_object",
    "GET /api/session": "get_session_identity",
    "GET /api/worker/control": "get_worker_control",
    "GET /api/worker/control/road1": "get_road_worker_control",
    "GET /sea-speed/api/analytics/road1/live/stream": "road_live_stream",
    "GET /sea-speed/api/cam1/live/stream": "water_live_stream",
    "PATCH /api/cam1/objects/{object_id}": "patch_cam1_object",
    "PATCH /api/objects/{object_id}": "patch_object",
    "POST /api/analytics/road1/live": "post_road_live",
    "POST /api/analytics/{camera_id}/crossing-line": "api_post_crossing_line",
    "POST /api/analytics/{camera_id}/crossings": "api_post_crossing",
    "POST /api/analytics/{camera_id}/events": "post_analytics_event",
    "POST /api/analytics/{camera_id}/roi": "post_analytics_roi",
    "POST /api/analytics/{camera_id}/speed-config": "post_analytics_speed_config",
    "POST /api/analytics/{camera_id}/speed-lines": "post_analytics_speed_lines",
    "POST /api/analytics/{camera_id}/state": "post_analytics_state",
    "POST /api/cam1/crossing-line": "post_cam1_crossing_line",
    "POST /api/cam1/crossings": "post_cam1_crossing",
    "POST /api/cam1/events": "post_cam1_event",
    "POST /api/cam1/live": "post_water_live",
    "POST /api/cam1/passages": "post_cam1_passage",
    "POST /api/cam1/roi": "post_cam1_roi",
    "POST /api/cam1/speed-config": "post_cam1_speed_config",
    "POST /api/cam1/speed-lines": "post_cam1_speed_lines",
    "POST /api/cam1/state": "post_cam1_state",
    "POST /api/cameras/preview/stop": "stop_camera_preview",
    "POST /api/cameras/{camera_id}/preview/start": "start_camera_preview",
    "POST /api/cameras/{camera_id}/snapshot/commit": "commit_camera_snapshot",
    "POST /api/worker/control/road1/start": "start_road_worker_control",
    "POST /api/worker/control/road1/stop": "stop_road_worker_control",
    "POST /api/worker/control/start": "start_worker_control",
    "POST /api/worker/control/stop": "stop_worker_control",
}

_DECORATED_METHODS = {"get", "post", "put", "patch", "delete"}


def _collect_app_route_fingerprints(source: str) -> dict:
    """Return {\"METHOD path\": handler_name} for every @app.<verb> endpoint."""
    tree = ast.parse(source)
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not (
                isinstance(dec, ast.Call)
                and isinstance(dec.func, ast.Attribute)
                and isinstance(dec.func.value, ast.Name)
                and dec.func.value.id == "app"
                and dec.func.attr in _DECORATED_METHODS
            ):
                continue
            if not (dec.args and isinstance(dec.args[0], ast.Constant)
                    and isinstance(dec.args[0].value, str)):
                raise AssertionError(
                    f"endpoint {node.name!r}: @app.{dec.func.attr} path is not a "
                    "string literal; extend the route-table extractor before "
                    "changing the decorator shape"
                )
            found[f"{dec.func.attr.upper()} {dec.args[0].value}"] = node.name
    return found


class RouteTableFingerprintTest(unittest.TestCase):
    def test_route_table_is_frozen(self):
        found = _collect_app_route_fingerprints(MAIN_SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(
            sorted(set(EXPECTED_ROUTE_FINGERPRINTS) - set(found)),
            [],
            "endpoints went missing from main.py — restore them or extend the "
            "baseline consciously",
        )
        self.assertEqual(
            sorted(set(found) - set(EXPECTED_ROUTE_FINGERPRINTS)),
            [],
            "new endpoints appeared in main.py — freeze them in the baseline",
        )
        # Wave-3 route-name pinning: method/path AND the bound handler name
        # must both match the frozen fingerprint.
        self.assertEqual(found, EXPECTED_ROUTE_FINGERPRINTS)
        self.assertEqual(len(EXPECTED_ROUTE_FINGERPRINTS), 61)


if __name__ == "__main__":
    unittest.main()
