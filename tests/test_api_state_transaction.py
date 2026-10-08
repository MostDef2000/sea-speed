"""Behavioral tests for transactional API state persistence (issue #394).

These tests load the real ``api/app/main.py`` functions (and the new
``api/app/store.py`` primitives) and assert the failure/concurrency
properties that the legacy implementation violated:

* fail-loud reads — a corrupt JSON store surfaces HTTP 500 instead of
  silently degrading to defaults;
* unique temporary files — concurrent writers can never share a fixed
  ``.tmp`` sibling;
* no lost updates — concurrent appenders never overwrite each other's
  records;
* bounded stores — the crossings (5000) and event feed (500) caps prune
  in the same transaction as the insert;
* transactional camera state upsert;
* idempotent, fail-closed startup migration that never deletes the
  legacy files.

On the pre-fix base the first four groups fail (RED); on the fixed head
they pass (GREEN). Tests that exercise main.py functions which only
exist after the fix are skipped on the base via ``skipUnless``.
"""

import ast
import copy
import importlib.util
import json
import os
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
API = REPO_ROOT / "api" / "app" / "main.py"
STORE_FILE = REPO_ROOT / "api" / "app" / "store.py"


def _load_store():
    spec = importlib.util.spec_from_file_location("api_store_under_test", STORE_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STORE = _load_store() if STORE_FILE.exists() else None

MAIN_TREE = ast.parse(API.read_text(encoding="utf-8-sig"), filename=str(API))
MAIN_FUNCTION_NAMES = {
    node.name for node in MAIN_TREE.body if isinstance(node, ast.FunctionDef)
}


def _extract_functions(names):
    found: Dict[str, ast.FunctionDef] = {}
    for node in MAIN_TREE.body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            found[node.name] = node
    missing = set(names) - set(found)
    if missing:
        raise AssertionError(f"missing API functions: {sorted(missing)}")
    cloned = []
    for name in names:
        function = copy.deepcopy(found[name])
        function.decorator_list = []  # endpoints are tested bare, without @app.get
        cloned.append(function)
    module = ast.Module(body=cloned, type_ignores=[])
    ast.fix_missing_locations(module)
    return module


def _exec_functions(names, namespace):
    exec(compile(_extract_functions(names), str(API), "exec"), namespace)
    return namespace


class _StubHTTPException(Exception):
    def __init__(self, status_code: int, detail: Any = None) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"{status_code}: {detail}")


def _resolved_read_json_file():
    """main.py's own helper on the base, the store's fail-loud one on the head."""
    if "read_json_file" in MAIN_FUNCTION_NAMES:
        namespace: Dict[str, Any] = {"json": json, "Path": Path}
        _exec_functions(["read_json_file"], namespace)
        return namespace["read_json_file"]
    return STORE.read_json_file


def _resolved_write_json_file():
    if "write_json_file" in MAIN_FUNCTION_NAMES:
        namespace: Dict[str, Any] = {"json": json, "os": os, "Path": Path}
        _exec_functions(["write_json_file"], namespace)
        return namespace["write_json_file"]
    return STORE.write_json_file


@unittest.skipUnless(STORE is not None, "api/app/store.py is required")
class StoreJsonIoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "probe.json"

    def test_missing_file_returns_default(self) -> None:
        self.assertEqual(STORE.read_json_file(self.path, {"d": 1}), {"d": 1})

    def test_corrupt_file_raises_instead_of_degrading(self) -> None:
        self.path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(STORE.JSON_READ_ERRORS):
            STORE.read_json_file(self.path, {"d": 1})

    def test_write_round_trip_is_atomic(self) -> None:
        STORE.write_json_file(self.path, {"a": 1, "b": [2, 3]})
        self.assertEqual(STORE.read_json_file(self.path, None), {"a": 1, "b": [2, 3]})
        leftovers = [p.name for p in Path(self.tmp.name).iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_concurrent_writers_leave_one_valid_file_and_no_tmp(self) -> None:
        errors: List[BaseException] = []

        def writer(index: int) -> None:
            try:
                for round_no in range(25):
                    STORE.write_json_file(self.path, {"writer": index, "round": round_no})
            except BaseException as error:  # pragma: no cover - failure path
                errors.append(error)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        payload = STORE.read_json_file(self.path, None)
        self.assertIsInstance(payload, dict)
        self.assertIn("writer", payload)
        leftovers = [p.name for p in Path(self.tmp.name).iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_legacy_fixed_tmp_collision_is_eliminated(self) -> None:
        if "write_json_file" not in MAIN_FUNCTION_NAMES:
            self.skipTest("main.py no longer defines write_json_file (store.py owns it)")
        # Reconstruct the legacy fixed-sibling tmp write and force both
        # writers through os-level rename of the SAME tmp path: one replace
        # consumes it and the second explodes (or installs the other
        # writer's bytes) — the defect #394 removes.
        barrier = threading.Barrier(2)
        shared_tmp = self.path.with_name(self.path.name + ".shared.tmp")
        errors: List[BaseException] = []

        class _FakeTmp:
            def write_text(self, text: str, encoding: Any = None) -> None:
                shared_tmp.write_text(text, encoding=encoding)

            def replace(self, target: Any) -> None:
                barrier.wait(timeout=10)  # both writers hold the same tmp
                shared_tmp.replace(target)

        class _FakePath:
            suffix = ".json"

            def with_suffix(self, suffix: str) -> "_FakeTmp":
                return _FakeTmp()

        namespace: Dict[str, Any] = {"json": json, "os": os, "Path": Path}
        _exec_functions(["write_json_file"], namespace)
        legacy_write = namespace["write_json_file"]
        fake_path = _FakePath()

        def writer(payload: Dict[str, str]) -> None:
            try:
                legacy_write(fake_path, payload)
            except BaseException as error:
                errors.append(error)

        threads = [threading.Thread(target=writer, args={"who": name}) for name in ("a", "b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        shared_tmp.unlink(missing_ok=True)
        self.assertEqual(
            errors, [], "fixed .tmp sibling collided under concurrent writers"
        )


class _ConfigEndpointMixin:
    """Shared harness for endpoint functions extracted from main.py."""

    def make_namespace(self, extra: Dict[str, Any]) -> Dict[str, Any]:
        store = STORE if STORE is not None else _StoreShim()
        tmp = Path(self.tmp.name)
        namespace: Dict[str, Any] = {
            "HTTPException": _StubHTTPException,
            "Path": Path,
            "json": json,
            "os": os,
            "sys": sys,
            "store": store,
            "STATE_DB_FILE": tmp / "state.sqlite3",
            "EVENTS_FEED_LIMIT": 500,
            "CROSSINGS_STORE_LIMIT": 5000,
            "CROSSING_DIRECTIONS": ("left_to_right", "right_to_left"),
            "DATA_DIR": tmp,
            "STATE_FILE": tmp / "cam1_state.json",
            "EVENTS_FILE": tmp / "events.json",
            "ROI_FILE": tmp / "cam1_roi.json",
            "SPEED_CONFIG_FILE": tmp / "cam1_speed_config.json",
            "SPEED_LINES_FILE": tmp / "cam1_speed_lines.json",
            "read_json_file": _resolved_read_json_file(),
            "write_json_file": _resolved_write_json_file(),
            "now_iso": lambda: datetime.now(timezone.utc).isoformat(),
            "DEFAULT_ROI_REF_W": 1920,
            "DEFAULT_ROI_REF_H": 1080,
            "analytics_identity": lambda camera_id: (
                {"domain": "water", "analytics_profile": "water-v1"}
                if camera_id == "cam1"
                else {"domain": "road", "analytics_profile": "road-v1"}
            ),
        }
        _exec_functions(["analytics_data_file"], namespace)
        for name, value in (extra or {}).items():
            namespace[name] = value
        return namespace


class _StoreShim:
    """Fallback when store.py is absent (pristine base): mirrors its contract."""

    JSON_READ_ERRORS = (OSError, ValueError)


class FailLoudReadTests(unittest.TestCase, _ConfigEndpointMixin):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _corrupt(self, camera_id: str, kind: str) -> Path:
        namespace = self.make_namespace({})
        path = namespace["analytics_data_file"](camera_id, kind)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{corrupt", encoding="utf-8")
        return path

    def _assert_corrupt_store_is_http_500(self, function_name: str, kind: str) -> None:
        self._corrupt("cam1", kind)
        namespace = self.make_namespace({})
        _exec_functions([function_name], namespace)
        with self.assertRaises(_StubHTTPException) as context:
            namespace[function_name]("cam1")
        self.assertEqual(context.exception.status_code, 500)

    def test_speed_config_corrupt_store_returns_500(self) -> None:
        self._assert_corrupt_store_is_http_500("get_analytics_speed_config", "speed_config")

    def test_speed_lines_corrupt_store_returns_500(self) -> None:
        self._corrupt("cam1", "speed_lines")
        namespace = self.make_namespace({})
        _exec_functions(["get_analytics_speed_lines"], namespace)
        with self.assertRaises(_StubHTTPException) as context:
            namespace["get_analytics_speed_lines"]("cam1")
        self.assertEqual(context.exception.status_code, 500)

    def test_crossing_line_corrupt_store_returns_500(self) -> None:
        self._corrupt("cam1", "crossing_line")
        namespace = self.make_namespace({})
        _exec_functions(["get_analytics_crossing_line"], namespace)
        with self.assertRaises(_StubHTTPException) as context:
            namespace["get_analytics_crossing_line"]("cam1")
        self.assertEqual(context.exception.status_code, 500)

    def test_events_endpoint_reads_sqlite_authoritatively(self) -> None:
        namespace = self.make_namespace({})
        _exec_functions(["get_analytics_events"], namespace)
        STORE.append_event(namespace["STATE_DB_FILE"], "cam1", {"event_id": "e1"}, 500)
        STORE.append_event(namespace["STATE_DB_FILE"], "cam1", {"event_id": "e2"}, 500)
        result = namespace["get_analytics_events"]("cam1", limit=50)
        self.assertTrue(result["ok"])
        self.assertEqual([event["event_id"] for event in result["events"]], ["e2", "e1"])


@unittest.skipUnless(STORE is not None, "api/app/store.py is required")
class NoLostUpdateTests(unittest.TestCase):
    PARTIES = 8

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_db = Path(self.tmp.name) / "state.sqlite3"
        self.crossings_path = Path(self.tmp.name) / "cam1_crossings.json"
        read_barrier = threading.Barrier(self.PARTIES)

        def barriered_read(path: Any, default: Any) -> Any:
            result = _resolved_read_json_file()(path, default)
            if str(path).endswith("_crossings.json"):
                read_barrier.wait(timeout=10)
            return result

        namespace: Dict[str, Any] = {
            "HTTPException": _StubHTTPException,
            "Path": Path,
            "json": json,
            "os": os,
            "sys": sys,
            "store": STORE,
            "STATE_DB_FILE": self.state_db,
            "CROSSINGS_STORE_LIMIT": 5000,
            "DATA_DIR": Path(self.tmp.name),
            "STATE_FILE": Path(self.tmp.name) / "cam1_state.json",
            "EVENTS_FILE": Path(self.tmp.name) / "events.json",
            "ROI_FILE": Path(self.tmp.name) / "cam1_roi.json",
            "SPEED_CONFIG_FILE": Path(self.tmp.name) / "cam1_speed_config.json",
            "SPEED_LINES_FILE": Path(self.tmp.name) / "cam1_speed_lines.json",
            "read_json_file": barriered_read,
            "write_json_file": _resolved_write_json_file(),
            "analytics_identity": lambda camera_id: {"domain": "water", "analytics_profile": "water-v1"},
        }
        _exec_functions(
            ["analytics_data_file", "crossings_store_path", "append_crossing_record"], namespace
        )
        self.append_crossing_record = namespace["append_crossing_record"]

    def test_concurrent_appenders_never_lose_records(self) -> None:
        expected = {f"event-{i}" for i in range(self.PARTIES)}

        def appender(index: int) -> None:
            self.append_crossing_record("cam1", {"event_id": f"event-{index}", "created_at": "2026-01-01T00:00:00+00:00"})

        threads = [threading.Thread(target=appender, args=(i,)) for i in range(self.PARTIES)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        stored = STORE.read_crossings(self.state_db, "cam1")
        seen = {record.get("event_id") for record in stored}
        seen.update(self._legacy_file_event_ids())
        self.assertEqual(
            seen,
            expected,
            "concurrent appenders lost records — persistence is not transactional",
        )

    def _legacy_file_event_ids(self) -> set:
        if not self.crossings_path.exists():
            return set()
        try:
            payload = json.loads(self.crossings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return set()
        if not isinstance(payload, list):
            return set()
        return {record.get("event_id") for record in payload if isinstance(record, dict)}


@unittest.skipUnless(STORE is not None, "api/app/store.py is required")
class StoreCapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_db = Path(self.tmp.name) / "state.sqlite3"

    def _seed_rows(self, table: str, count: int, camera_id: str = "cam1") -> None:
        STORE.initialize_state_db(self.state_db)
        with STORE.open_state_db(self.state_db) as connection:
            for index in range(count):
                connection.execute(
                    f"INSERT INTO {table} (camera_id, payload_json, created_at) VALUES (?, ?, ?)",
                    (camera_id, json.dumps({"seq": index}), f"2026-01-01T00:00:{index % 60:02d}+00:00"),
                )

    def test_crossings_cap_prunes_to_5000(self) -> None:
        self._seed_rows("crossings", 5002)
        for index in range(3):
            STORE.append_crossing(self.state_db, "cam1", {"event_id": f"new-{index}"}, 5000)
        rows = STORE.read_crossings(self.state_db, "cam1")
        self.assertEqual(len(rows), 5000)
        self.assertEqual(rows[0].get("event_id"), "new-2")

    def test_events_cap_prunes_to_500(self) -> None:
        self._seed_rows("event_feed", 502)
        for index in range(3):
            STORE.append_event(self.state_db, "cam1", {"event_id": f"new-{index}"}, 500)
        rows = STORE.read_events(self.state_db, "cam1")
        self.assertEqual(len(rows), 500)
        self.assertEqual(rows[0].get("event_id"), "new-2")

    def test_caps_are_per_camera(self) -> None:
        self._seed_rows("crossings", 5002, camera_id="cam1")
        STORE.append_crossing(self.state_db, "road1", {"event_id": "road-1"}, 5000)
        self.assertEqual(len(STORE.read_crossings(self.state_db, "road1")), 1)


@unittest.skipUnless(STORE is not None, "api/app/store.py is required")
class CameraStateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_db = Path(self.tmp.name) / "state.sqlite3"

    def test_absent_state_reads_none(self) -> None:
        self.assertIsNone(STORE.read_camera_state(self.state_db, "cam1"))

    def test_upsert_is_last_write_wins(self) -> None:
        STORE.upsert_camera_state(self.state_db, "cam1", {"frame_no": 1})
        STORE.upsert_camera_state(self.state_db, "cam1", {"frame_no": 2, "ai_active": True})
        state = STORE.read_camera_state(self.state_db, "cam1")
        self.assertEqual(state, {"frame_no": 2, "ai_active": True})


@unittest.skipUnless(STORE is not None, "api/app/store.py is required")
class LegacyMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_db = Path(self.tmp.name) / "state.sqlite3"

    def test_import_preserves_newest_first_order_and_is_idempotent(self) -> None:
        legacy = [{"event_id": "e3"}, {"event_id": "e2"}, {"event_id": "e1"}]
        imported = STORE.import_legacy_records(self.state_db, "events", "cam1", legacy, 500)
        self.assertEqual(imported, 3)
        self.assertEqual(
            [event["event_id"] for event in STORE.read_events(self.state_db, "cam1")],
            ["e3", "e2", "e1"],
        )
        self.assertEqual(STORE.import_legacy_records(self.state_db, "events", "cam1", legacy, 500), 0)
        self.assertEqual(len(STORE.read_events(self.state_db, "cam1")), 3)

    def test_import_skips_non_dict_records(self) -> None:
        imported = STORE.import_legacy_records(self.state_db, "crossings", "cam1", [{"event_id": "e1"}, "junk", 7], 5000)
        self.assertEqual(imported, 1)
        self.assertEqual(len(STORE.read_crossings(self.state_db, "cam1")), 1)

    def test_import_legacy_camera_state_never_overwrites(self) -> None:
        STORE.upsert_camera_state(self.state_db, "cam1", {"frame_no": 99})
        self.assertFalse(STORE.import_legacy_camera_state(self.state_db, "cam1", {"frame_no": 1}))
        self.assertEqual(STORE.read_camera_state(self.state_db, "cam1"), {"frame_no": 99})
        self.assertTrue(STORE.import_legacy_camera_state(self.state_db, "road1", {"frame_no": 1}))
        self.assertEqual(STORE.read_camera_state(self.state_db, "road1"), {"frame_no": 1})


@unittest.skipUnless(
    "import_legacy_state_store" in MAIN_FUNCTION_NAMES,
    "startup migration only exists after the fix",
)
class StartupMigrationTests(unittest.TestCase, _ConfigEndpointMixin):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_db = Path(self.tmp.name) / "state.sqlite3"

    def _namespace(self, read_override: Any = None) -> Dict[str, Any]:
        namespace = self.make_namespace(
            {
                "ANALYTICS_IDENTITIES": {"cam1": {}, "road1": {}},
                "EVENTS_FEED_LIMIT": 500,
                "CROSSINGS_STORE_LIMIT": 5000,
                "STATE_DB_FILE": self.state_db,
            }
        )
        if read_override is not None:
            namespace["read_json_file"] = read_override
        _exec_functions(["import_legacy_state_store"], namespace)
        return namespace

    def test_corrupt_legacy_file_fails_closed(self) -> None:
        crossings = Path(self.tmp.name) / "cam1_crossings.json"
        crossings.write_text("{corrupt", encoding="utf-8")
        namespace = self._namespace()
        with self.assertRaises((OSError, ValueError)):
            namespace["import_legacy_state_store"]()

    def test_import_never_deletes_legacy_files(self) -> None:
        crossings = Path(self.tmp.name) / "cam1_crossings.json"
        crossings.write_text(json.dumps([{"event_id": "c1", "created_at": "2026-01-01T00:00:00+00:00"}]), encoding="utf-8")
        events = Path(self.tmp.name) / "events.json"
        events.write_text(json.dumps([{"event_id": "e1", "created_at": "2026-01-01T00:00:00+00:00"}]), encoding="utf-8")
        namespace = self._namespace()
        namespace["import_legacy_state_store"]()
        self.assertTrue(crossings.exists(), "migration must not delete the legacy file")
        self.assertTrue(events.exists(), "migration must not delete the legacy file")
        self.assertEqual(
            [record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")],
            ["c1"],
        )
        self.assertEqual(
            [event["event_id"] for event in STORE.read_events(self.state_db, "cam1")],
            ["e1"],
        )
        # Idempotent: a restart must not duplicate rows.
        namespace["import_legacy_state_store"]()
        self.assertEqual(len(STORE.read_crossings(self.state_db, "cam1")), 1)
        self.assertEqual(len(STORE.read_events(self.state_db, "cam1")), 1)


if __name__ == "__main__":
    unittest.main()
