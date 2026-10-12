"""Route-table fingerprint for the FastAPI app surface (issue #396, wave 2).

The main.py decomposition waves (issue #396) move code out of ``main.py``
wave by wave; this guard freezes the complete ``(method, path)`` endpoint
table parsed from ``main.py`` at the wave-2 base commit so any wave that
accidentally adds, drops or renames an endpoint fails loudly.

AST-level and import-free on purpose: the app boots against /opt state the
test environment does not provide, and the fingerprint only needs the
decorator syntax, so the check is deterministic and side-effect free.
"""

import ast
import unittest
from pathlib import Path

MAIN_SOURCE = Path(__file__).resolve().parent.parent / "api" / "app" / "main.py"

# Frozen at f863f1cab6ab07f0aa0c10996d800cb2f55daf91 (issue #396 wave 2 base):
# 61 @app.* endpoints, parsed with the same walker as the test below.
EXPECTED_ROUTES = frozenset(
    {
        "DELETE /api/cam1/objects/{object_id}",
        "DELETE /api/objects/{object_id}",
        "GET /api/analytics/road1/live",
        "GET /api/analytics/road1/live/stream",
        "GET /api/analytics/{camera_id}/crossing-line",
        "GET /api/analytics/{camera_id}/crossings/summary",
        "GET /api/analytics/{camera_id}/events",
        "GET /api/analytics/{camera_id}/objects",
        "GET /api/analytics/{camera_id}/roi",
        "GET /api/analytics/{camera_id}/speed-config",
        "GET /api/analytics/{camera_id}/speed-lines",
        "GET /api/analytics/{camera_id}/state",
        "GET /api/cam1/crossing-line",
        "GET /api/cam1/crossings/summary",
        "GET /api/cam1/events",
        "GET /api/cam1/live",
        "GET /api/cam1/live/stream",
        "GET /api/cam1/objects",
        "GET /api/cam1/objects/{object_id}",
        "GET /api/cam1/passages",
        "GET /api/cam1/roi",
        "GET /api/cam1/speed-config",
        "GET /api/cam1/speed-lines",
        "GET /api/cam1/state",
        "GET /api/cameras",
        "GET /api/cameras/preview",
        "GET /api/cameras/{camera_id}/snapshot",
        "GET /api/health",
        "GET /api/objects",
        "GET /api/objects/{object_id}",
        "GET /api/session",
        "GET /api/worker/control",
        "GET /api/worker/control/road1",
        "GET /sea-speed/api/analytics/road1/live/stream",
        "GET /sea-speed/api/cam1/live/stream",
        "PATCH /api/cam1/objects/{object_id}",
        "PATCH /api/objects/{object_id}",
        "POST /api/analytics/road1/live",
        "POST /api/analytics/{camera_id}/crossing-line",
        "POST /api/analytics/{camera_id}/crossings",
        "POST /api/analytics/{camera_id}/events",
        "POST /api/analytics/{camera_id}/roi",
        "POST /api/analytics/{camera_id}/speed-config",
        "POST /api/analytics/{camera_id}/speed-lines",
        "POST /api/analytics/{camera_id}/state",
        "POST /api/cam1/crossing-line",
        "POST /api/cam1/crossings",
        "POST /api/cam1/events",
        "POST /api/cam1/live",
        "POST /api/cam1/passages",
        "POST /api/cam1/roi",
        "POST /api/cam1/speed-config",
        "POST /api/cam1/speed-lines",
        "POST /api/cam1/state",
        "POST /api/cameras/preview/stop",
        "POST /api/cameras/{camera_id}/preview/start",
        "POST /api/cameras/{camera_id}/snapshot/commit",
        "POST /api/worker/control/road1/start",
        "POST /api/worker/control/road1/stop",
        "POST /api/worker/control/start",
        "POST /api/worker/control/stop",
    }
)

_DECORATED_METHODS = {"get", "post", "put", "patch", "delete"}


def _collect_app_routes(source: str) -> set:
    """Return the (METHOD path) strings of every @app.<verb> endpoint."""
    tree = ast.parse(source)
    found = set()
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
            found.add(f"{dec.func.attr.upper()} {dec.args[0].value}")
    return found


class RouteTableFingerprintTest(unittest.TestCase):
    def test_route_table_is_frozen(self):
        found = _collect_app_routes(MAIN_SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(
            sorted(EXPECTED_ROUTES - found),
            [],
            "endpoints went missing from main.py — restore them or extend the "
            "baseline consciously",
        )
        self.assertEqual(
            sorted(found - EXPECTED_ROUTES),
            [],
            "new endpoints appeared in main.py — freeze them in the baseline",
        )
        self.assertEqual(found, EXPECTED_ROUTES)
        self.assertEqual(len(EXPECTED_ROUTES), 61)


if __name__ == "__main__":
    unittest.main()
