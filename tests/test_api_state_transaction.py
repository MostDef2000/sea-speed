"""Behavioral tests for transactional API state persistence (issue #394).

These tests load the real ``api/app/store.py`` primitives and the real
``api/app/main.py`` functions (AST extraction, like the existing
harnesses) and assert the properties the legacy implementation violated:

* fail-loud reads — a corrupt JSON store surfaces HTTP 500 instead of
  silently degrading to defaults;
* unique temporary files — concurrent writers can never share a fixed
  ``.tmp`` sibling;
* no lost updates — concurrent appenders never lose records;
* bounded stores — the crossings (5000) and event feed (500) caps prune
  in the same transaction as the insert;
* transactional camera state upsert;
* RISK-005 retirement — the boot schema has no ``ingestion_log``, a
  pre-existing (dual-write-era) ``ingestion_log`` table is dropped at
  startup, records accepted via the API append nothing to the legacy
  JSON mirrors, and legacy files are never deleted.

The import-path coverage (T-A..T-D, V-A..V-E, W-A..W-E) was retired WITH
the dual-write window: the contracted retirement act removed the legacy
import path and its ``ingestion_log`` registry, so those tests were
deleted together with the machinery they exercised — the contracted
retirement of that coverage, not a weakening.
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
            "read_json_file": _resolved_read_json_file(),
            "write_json_file": _resolved_write_json_file(),
            "analytics_identity": lambda camera_id: {"domain": "water", "analytics_profile": "water-v1"},
        }
        _exec_functions(["analytics_data_file", "append_crossing_record"], namespace)
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
        self.assertEqual(
            seen,
            expected,
            "concurrent appenders lost records — persistence is not transactional",
        )
        self.assertEqual(
            len(stored),
            self.PARTIES,
            "no duplicate rows may appear under concurrent appends",
        )


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


def _seed_dual_write_era_registry(state_db: Path) -> None:
    """Recreate the dual-write-era schema: an ingestion_log registry with rows.

    Existing VPS databases from the dual-write window carry exactly this
    retired table (created by the pre-retirement ``_SCHEMA_STATEMENTS``).
    """
    STORE.initialize_state_db(state_db)
    with STORE.open_state_db(state_db) as connection:
        connection.execute(
            "CREATE TABLE ingestion_log ("
            "seq INTEGER PRIMARY KEY AUTOINCREMENT, "
            "camera_id TEXT NOT NULL, "
            "kind TEXT NOT NULL, "
            "payload_hash TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE INDEX idx_ingestion_log_keys ON ingestion_log(camera_id, kind, payload_hash)"
        )
        connection.execute(
            "INSERT INTO ingestion_log (camera_id, kind, payload_hash) VALUES (?, ?, ?)",
            ("cam1", "crossings", "a" * 64),
        )


def _table_names(state_db: Path) -> set:
    with STORE.open_state_db(state_db) as connection:
        return {
            row["name"]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }


@unittest.skipUnless(STORE is not None, "api/app/store.py is required")
class StartupMigrationTests(unittest.TestCase):
    """Post-retirement boot schema: ``ingestion_log`` is gone after boot."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_db = Path(self.tmp.name) / "state.sqlite3"

    def test_fresh_boot_creates_schema_without_ingestion_log(self) -> None:
        STORE.initialize_state_db(self.state_db)
        tables = _table_names(self.state_db)
        self.assertIn("crossings", tables)
        self.assertIn("event_feed", tables)
        self.assertIn("camera_state", tables)
        self.assertNotIn(
            "ingestion_log",
            tables,
            "the retired registry must not be created on a fresh install",
        )

    def test_boot_is_idempotent(self) -> None:
        STORE.initialize_state_db(self.state_db)
        STORE.initialize_state_db(self.state_db)
        STORE.initialize_state_db(self.state_db)
        self.assertNotIn("ingestion_log", _table_names(self.state_db))
        # The store stays fully functional across repeated boots.
        STORE.append_crossing(self.state_db, "cam1", {"event_id": "c1"})
        self.assertEqual(
            [record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")],
            ["c1"],
        )

    # Contracted retirement act, part 1: the startup migration drops a
    # pre-existing (dual-write-era) ingestion_log table, idempotently, and
    # retained records survive untouched.
    def test_boot_drops_preexisting_ingestion_log(self) -> None:
        _seed_dual_write_era_registry(self.state_db)
        STORE.append_crossing(self.state_db, "cam1", {"event_id": "c-live", "created_at": "2026-01-01T00:00:00+00:00"})

        # A real boot is a fresh process: simulate it by clearing the
        # module's per-process init cache so the startup migration re-runs.
        STORE._initialized.discard(str(self.state_db))
        STORE.initialize_state_db(self.state_db)  # the post-retirement boot

        self.assertNotIn(
            "ingestion_log",
            _table_names(self.state_db),
            "the pre-existing ingestion_log table must be dropped at boot",
        )
        self.assertEqual(
            [record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")],
            ["c-live"],
            "retained records must survive the registry drop",
        )
        # Idempotent: a second boot neither fails nor resurrects the table.
        STORE.initialize_state_db(self.state_db)
        self.assertNotIn("ingestion_log", _table_names(self.state_db))


class RetiredDualWriteTests(unittest.TestCase, _ConfigEndpointMixin):
    """Contracted RISK-005 retirement regression, all three parts together:

    1. the post-retirement boot DROPS a pre-existing ingestion_log table;
    2. records accepted via the API append NOTHING to the legacy JSON
       mirrors (dual-write is over);
    3. legacy JSON files are never deleted (inert history on disk).
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_db = Path(self.tmp.name) / "state.sqlite3"
        self.legacy_files = {
            "crossings": Path(self.tmp.name) / "cam1_crossings.json",
            "events": Path(self.tmp.name) / "cam1_events.json",
            "state": Path(self.tmp.name) / "cam1_state.json",
        }
        self.legacy_files["crossings"].write_text(
            json.dumps([{"event_id": "legacy-c1", "created_at": "2026-01-01T00:00:00+00:00"}]),
            encoding="utf-8",
        )
        self.legacy_files["events"].write_text(
            json.dumps([{"event_id": "legacy-e1", "created_at": "2026-01-01T00:00:00+00:00"}]),
            encoding="utf-8",
        )
        self.legacy_files["state"].write_text(
            json.dumps({"frame_no": 7, "updated_at": "2026-01-01T00:00:00+00:00"}),
            encoding="utf-8",
        )
        self.legacy_bytes = {kind: path.read_bytes() for kind, path in self.legacy_files.items()}

    def test_retired_boot_drops_registry_and_leaves_legacy_files_inert(self) -> None:
        # Dual-write-era shape: a registered identity plus a retained record.
        _seed_dual_write_era_registry(self.state_db)
        STORE.append_crossing(self.state_db, "cam1", {"event_id": "c-live", "created_at": "2026-01-01T00:00:00+00:00"})

        # Boot exactly as a fresh API process does at startup (the module's
        # per-process init cache is cleared to simulate the new process).
        STORE._initialized.discard(str(self.state_db))
        STORE.initialize_state_db(self.state_db)

        # Part 1: the pre-existing registry is dropped; records survive.
        self.assertNotIn("ingestion_log", _table_names(self.state_db))
        self.assertEqual(
            [record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")],
            ["c-live"],
        )

        # Part 2: a record accepted via the API write path commits to
        # SQLite and appends NOTHING to the legacy JSON mirror.
        namespace = self.make_namespace(
            {
                "STATE_DB_FILE": self.state_db,
                "CROSSINGS_STORE_LIMIT": 5000,
            }
        )
        _exec_functions(["append_crossing_record"], namespace)
        namespace["append_crossing_record"](
            "cam1", {"event_id": "c-new", "created_at": "2026-01-02T00:00:00+00:00"}
        )
        self.assertEqual(
            [record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")],
            ["c-new", "c-live"],
            "the API accept path must remain authoritative in SQLite",
        )

        # Part 3: legacy files are neither deleted nor rewritten.
        for kind, path in self.legacy_files.items():
            self.assertTrue(path.exists(), f"legacy {kind} file must never be deleted")
            self.assertEqual(
                path.read_bytes(),
                self.legacy_bytes[kind],
                f"legacy {kind} mirror must no longer be written by API accepts",
            )

        # A second boot stays idempotent: registry stays gone, records and
        # legacy files remain untouched.
        STORE.initialize_state_db(self.state_db)
        self.assertNotIn("ingestion_log", _table_names(self.state_db))
        self.assertEqual(len(STORE.read_crossings(self.state_db, "cam1")), 2)
        for kind, path in self.legacy_files.items():
            self.assertTrue(path.exists(), f"legacy {kind} file must never be deleted")
            self.assertEqual(path.read_bytes(), self.legacy_bytes[kind])


if __name__ == "__main__":
    unittest.main()
