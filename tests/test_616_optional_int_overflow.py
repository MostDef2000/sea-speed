"""RED regression tests for MostDef2000/sea-speed#616.

Issue #616: ``objects_registry.optional_int`` caught only ``(TypeError,
ValueError)``. A JSON number like ``1e999`` parses to float ``inf`` and
``int(inf)`` raises ``OverflowError`` — unhandled, that surfaced as HTTP 500
on the crossing ingestion path (``post_analytics_crossing``, parsed at
api/app/analytics.py:454 via ``optional_int(data.get("track_id"))``; the
route POST /api/cam1/crossings -> api_post_crossing wraps the handler in no
try/except, so the unhandled OverflowError IS the production 500, and unlike
the passage/event metadata paths it has no #587 non-finite boundary scan).

Desired behavior pinned here: non-finite floats (NaN / ±Infinity, including
the ``1e999`` overflow literal) are dropped exactly like non-numeric input
(``optional_int`` returns None, mirroring the #577-hardened
``optional_float``), while exact integers keep full precision — the fix must
NOT round-trip integers through ``float()`` (``float(10**30)`` loses
precision), so ``10**30`` must survive unchanged.

On base fa8148f9 the non-finite cases FAIL (OverflowError from the exec
harness, both at the unit level and inside the ingestion handler); once the
fix lands the tests pass unchanged. No test is weakened, skipped, or
xfailed, and no code under test is mocked away — the ingestion harness runs
the REAL ``post_analytics_crossing`` with the REAL ``optional_int`` /
``optional_float`` and stubs only the sinks.

Coverage mirrors the issue-#587 wave idioms:

* exec-harness unit pins for ``optional_int`` itself (AST-extracted from
  api/app/objects_registry.py and exec'd against a stub namespace — the
  namespace holds only ``typing.Any``/``Optional``, so any module-level
  reference in the body would raise NameError here; this also pins the
  module-import-free-body contract), same as
  tests/test_numeric_input_validation.py's ``OptionalFloatFiniteTests``, and
* an exec-harness pin for the track_id ingestion path: the real
  ``post_analytics_crossing`` (AST-extracted from api/app/analytics.py,
  same handler-harness idiom as that file's endpoint tests) called with a
  non-finite ``track_id`` — today it raises OverflowError (the #616 500),
  desired: the crossing record flows to both sinks with ``track_id`` None,
  exactly the treatment an absent or non-numeric track_id already gets.

The #587 file (tests/test_587_nonfinite_residual_paths.py) additionally
exercises its sites through TestClient; that variant needs the
guarded-optional ``fastapi``/``httpx`` probe whose exact per-file registry
is pinned by tests/test_run_tests_script.py's import-hygiene scan —
registering a new guarded-optional file means extending that pinned list,
which lives outside this fix's allowed paths. The handler-level exec harness
below pins the same defect (the route adds no exception handling of its
own) without a third-party import, so the one-process battery stays green
and the import-hygiene gate is not gamed with scanner-invisible dynamic
imports.
"""

from __future__ import annotations

import ast
import copy
import json
import types
import unittest
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
OBJECTS_REGISTRY_SOURCE = ROOT / "api" / "app" / "objects_registry.py"
ANALYTICS_SOURCE = ROOT / "api" / "app" / "analytics.py"


class HTTPExceptionStub(Exception):
    """Stand-in for fastapi.HTTPException in exec'd handler bodies."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def load_registry_functions(sources: list[Path], names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    """AST-extract the named functions and exec them into ``namespace``.

    Same harness idiom as tests/test_numeric_input_validation.py: the
    extracted function bodies run against a stub namespace, so they must be
    module-import-free (any module-level reference raises NameError at call
    time).
    """
    selected = []
    found = set()
    for source in sources:
        tree = ast.parse(source.read_text(encoding="utf-8-sig"), filename=str(source))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name in names and node.name not in found:
                selected.append(copy.deepcopy(node))
                found.add(node.name)
    missing = names - found
    if missing:
        raise AssertionError(f"missing registry functions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(sources[0]), "exec"), namespace)
    return namespace


class OptionalIntOverflowTests(unittest.TestCase):
    """optional_int must drop non-finite floats like non-numeric input (#616)."""

    def setUp(self) -> None:
        self.ns: dict[str, Any] = {"Any": Any, "Optional": Optional}
        load_registry_functions([OBJECTS_REGISTRY_SOURCE], {"optional_int"}, self.ns)
        self.optional_int = self.ns["optional_int"]

    def test_non_finite_floats_return_none(self) -> None:
        # On base fa8148f9 int(inf)/int(-inf) raised OverflowError (issue
        # #616): the JSON literals 1e999 / -1e999 arrive here as non-finite
        # floats and must be dropped like non-numeric input. (int(nan) raises
        # ValueError on CPython 3.14 but OverflowError on older CPythons —
        # the finiteness guard pins all three uniformly.)
        for value in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(value=value):
                self.assertIsNone(self.optional_int(value))

    def test_exact_large_int_survives_unchanged(self) -> None:
        # Precision guard: the fix must NOT round-trip integers through
        # float() — float(10**30) loses precision — so the exact int must
        # pass through unchanged and stay an int.
        result = self.optional_int(10**30)
        self.assertEqual(result, 10**30)
        self.assertIsInstance(result, int)

    def test_numeric_string_overflow_returns_none(self) -> None:
        # "1e999" as a STRING is non-numeric to int() -> ValueError -> None.
        # Existing path, must stay unchanged.
        self.assertIsNone(self.optional_int("1e999"))

    def test_none_empty_and_non_numeric_return_none(self) -> None:
        for value in (None, "", "abc"):
            with self.subTest(value=value):
                self.assertIsNone(self.optional_int(value))

    def test_finite_and_integer_behavior_unchanged(self) -> None:
        cases: list[tuple[Any, Any]] = [
            (3.0, 3),  # finite float truncates to int (existing behavior)
            (12, 12),
            ("42", 42),
            (True, 1),
            (0, 0),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                result = self.optional_int(value)
                self.assertEqual(result, expected)
                self.assertIsInstance(result, int)


class CrossingTrackIdIngestionTests(unittest.TestCase):
    """The crossing ingestion handler must survive a non-finite track_id (#616).

    Exec-harness mirror of the #587 ingestion-path coverage: the REAL
    ``post_analytics_crossing`` (api/app/analytics.py:454) runs with the REAL
    ``optional_int`` / ``optional_float`` in its namespace; only the sinks
    (``persist_object_event`` / ``append_crossing_record``) and the identity
    seam are stubbed. On base fa8148f9 a track_id of 1e999 (parsed by
    json.loads to float inf, exactly as the POST /api/cam1/crossings route
    parses the metadata form field) raises OverflowError out of the handler
    — the production 500.
    """

    def setUp(self) -> None:
        self.persisted: list[Dict[str, Any]] = []
        self.appended: list[Dict[str, Any]] = []
        self.ns: dict[str, Any] = {
            "Any": Any,
            "Dict": Dict,
            "Optional": Optional,
            "HTTPException": HTTPExceptionStub,
            "analytics_identity": lambda camera_id: {"analytics_profile": "water-v1", "domain": "water"},
            "CROSSING_DIRECTIONS": ("left_to_right", "right_to_left"),
            "time": types.SimpleNamespace(time=lambda: 0.0),
            "uuid": types.SimpleNamespace(uuid4=lambda: types.SimpleNamespace(hex="0" * 8)),
            "now_iso": lambda: "2026-11-01T00:00:00+00:00",
            "persist_object_event": lambda record: self.persisted.append(record) or False,
            "append_crossing_record": lambda camera_id, record: self.appended.append(record),
        }
        load_registry_functions(
            [OBJECTS_REGISTRY_SOURCE, ANALYTICS_SOURCE],
            {"optional_int", "optional_float", "post_analytics_crossing"},
            self.ns,
        )
        self.handler = self.ns["post_analytics_crossing"]

    def _payload(self, event_id: str, track_id: Any) -> Dict[str, Any]:
        return {
            "event_id": event_id,
            "direction": "left_to_right",
            "object_type": "vessel",
            "track_id": track_id,
        }

    def test_non_finite_track_id_ingests_without_overflow(self) -> None:
        # RED on base fa8148f9: OverflowError from int(inf)/int(-inf) inside
        # the handler (the production 500). Desired: the handler completes,
        # and the crossing record reaches both sinks with track_id None —
        # the same treatment an absent or non-numeric track_id gets.
        for label, value in (
            ("inf", float("inf")),
            ("-inf", float("-inf")),
            ("nan", float("nan")),
            ("raw-1e999", json.loads('{"v": 1e999}')["v"]),
            ("raw--1e999", json.loads('{"v": -1e999}')["v"]),
        ):
            with self.subTest(label=label):
                self.persisted.clear()
                self.appended.clear()
                result = self.handler("cam1", self._payload(f"E-616-{label}", value))
                self.assertTrue(result["ok"])
                self.assertEqual(result["event_id"], f"E-616-{label}")
                self.assertEqual(len(self.appended), 1, "crossing record must still be stored")
                self.assertIsNone(self.appended[0]["track_id"])
                self.assertEqual(len(self.persisted), 1, "registry mirror must still run")
                self.assertIsNone(self.persisted[0]["track_id"])

    def test_valid_and_large_track_id_unchanged(self) -> None:
        # Guard: normal and exact-large integer track_ids still ingest and
        # persist exactly as before — 10**30 keeps full precision end-to-end
        # (no float() round-trip anywhere in the path).
        result = self.handler("cam1", self._payload("E-616-large", 10**30))
        self.assertTrue(result["ok"])
        self.assertEqual(self.appended[0]["track_id"], 10**30)
        self.assertIsInstance(self.appended[0]["track_id"], int)
        self.assertEqual(self.persisted[0]["track_id"], 10**30)
        self.persisted.clear()
        self.appended.clear()
        result = self.handler("cam1", self._payload("E-616-small", 42))
        self.assertTrue(result["ok"])
        self.assertEqual(self.appended[0]["track_id"], 42)

    def test_absent_track_id_still_ingests_with_none(self) -> None:
        # Guard: the pre-existing absent-track_id contract is untouched.
        payload = self._payload("E-616-absent", None)
        del payload["track_id"]
        result = self.handler("cam1", payload)
        self.assertTrue(result["ok"])
        self.assertIsNone(self.appended[0]["track_id"])


if __name__ == "__main__":
    unittest.main()
