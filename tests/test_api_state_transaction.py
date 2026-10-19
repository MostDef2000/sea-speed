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

Issue #537 wave 1 (road-event delivery receipts) extends this file with
store-level fault-injection coverage: the durable receipt semantics of
``store.deliver_event`` (identical retry → stored success response, content
or camera conflict → typed conflict, no partial state), duplicate
protection surviving simulated feed pruning, the additive-at-boot feed
migration (nullable event_id backfill, unique index creation, duplicate
historical IDs inventoried without deletion), the 90-day receipt
retention sweep, the atomic snapshot write (no partial file on failure,
orphan tmp cleaned) and the safe filename derivation.

The import-path coverage (T-A..T-D, V-A..V-E, W-A..W-E) was retired WITH
the dual-write window: the contracted retirement act removed the legacy
import path and its ``ingestion_log`` registry, so those tests were
deleted together with the machinery they exercised — the contracted
retirement of that coverage, not a weakening.
"""

import ast
import asyncio
import copy
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
API = REPO_ROOT / "api" / "app" / "main.py"
# Issue #396 wave 5: the analytics services moved out of main.py — the walk
# below resolves extracted functions from the analytics module with fallback
# to main, exactly like the other readers. The retirement teeth are untouched:
# the exec'd bodies are still the REAL append/persist paths (real store
# write_json_file/read_json_file fallback, byte-pinned legacy mirrors).
ANALYTICS_FILE = REPO_ROOT / "api" / "app" / "analytics.py"
STORE_FILE = REPO_ROOT / "api" / "app" / "store.py"


def _load_store():
    spec = importlib.util.spec_from_file_location("api_store_under_test", STORE_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STORE = _load_store() if STORE_FILE.exists() else None

_API_TREES = []
for _source in (API, ANALYTICS_FILE):
    if _source.exists():
        _API_TREES.append(
            ast.parse(_source.read_text(encoding="utf-8-sig"), filename=str(_source))
        )
MAIN_FUNCTION_NAMES = {
    node.name
    for _tree in _API_TREES
    for node in _tree.body
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}


def _extract_functions(names):
    found: Dict[str, Any] = {}
    for _tree in _API_TREES:
        for node in _tree.body:
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in names
                and node.name not in found
            ):
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
       mirrors (dual-write is over) — pinned end-to-end for ALL THREE
       accept paths: crossings (append_crossing_record), the analytics
       event feed (post_analytics_event) and the 1 Hz camera state
       (post_analytics_state);
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

    def _retired_mirror_namespace(self) -> Dict[str, Any]:
        """Namespace for the event/state accept paths (post-retirement).

        Mirrors the crossings pattern: the real legacy mirror files seeded
        in setUp are wired in as BOTH the ``analytics_data_file`` targets
        and the module constants, so a re-added dual-write mirror —
        whichever spelling it uses — would hit a byte-pinned baseline file.
        """
        return self.make_namespace(
            {
                "STATE_DB_FILE": self.state_db,
                "EVENTS_FEED_LIMIT": 500,
                # Real legacy file targets: point both the
                # analytics_data_file mapping and the constants at the
                # recorded baseline paths.
                "STATE_FILE": self.legacy_files["state"],
                "EVENTS_FILE": self.legacy_files["events"],
                "uuid": __import__("uuid"),
                "require_auth": lambda token: None,
                "persist_object_event": lambda event: True,
                "sweep_events_media": lambda force=False, now=None: 0,
                "EVENTS_MEDIA_DIR": Path(self.tmp.name) / "events_media",
                "Form": lambda *args, **kwargs: None,
                "File": lambda *args, **kwargs: None,
                "Header": lambda *args, **kwargs: None,
                "Optional": Optional,
                "UploadFile": object,
                "WORKER_STATE_SCHEMA": "sea_speed_worker_state_v1",
                "VEHICLE_EVENT_SCHEMA": "sea_speed_vehicle_event_v1",
                "TELEMETRY_SCHEMA": "sea_speed_telemetry_v1",
            }
        )

    # The event-feed accept path: the real post_analytics_event is
    # AST-executed and must commit to SQLite while leaving the legacy
    # events mirror byte-identical (the write_json_file stub is NOT
    # injected — the real store writer runs, so a re-added dual-write
    # mirror would fail this test).
    def test_retired_event_accept_appends_nothing_to_legacy_events_mirror(self) -> None:
        STORE.initialize_state_db(self.state_db)
        namespace = self._retired_mirror_namespace()
        _exec_functions(["post_analytics_event"], namespace)
        namespace["EVENTS_MEDIA_DIR"].mkdir(parents=True, exist_ok=True)

        class _FakeSnapshot:
            async def read(self) -> bytes:
                return b"jpeg-bytes"

        result = asyncio.run(
            namespace["post_analytics_event"](
                "cam1",
                metadata=json.dumps(
                    {"event_id": "e-new", "created_at": "2026-01-02T00:00:00+00:00"}
                ),
                snapshot=_FakeSnapshot(),
                authorization=None,
            )
        )
        self.assertTrue(result["ok"])
        self.assertEqual(
            [event["event_id"] for event in STORE.read_events(self.state_db, "cam1")],
            ["e-new"],
            "the API accept path must remain authoritative in SQLite",
        )
        self.assertTrue(
            self.legacy_files["events"].exists(),
            "legacy events file must never be deleted",
        )
        self.assertEqual(
            self.legacy_files["events"].read_bytes(),
            self.legacy_bytes["events"],
            "legacy events mirror must no longer be written by API accepts",
        )

    # The camera-state accept path: the real post_analytics_state is
    # AST-executed (with the real default-state fallback) and must upsert
    # to SQLite while leaving the legacy state mirror byte-identical.
    def test_retired_state_accept_writes_nothing_to_legacy_state_mirror(self) -> None:
        STORE.initialize_state_db(self.state_db)
        namespace = self._retired_mirror_namespace()
        _exec_functions(
            ["post_analytics_state", "analytics_default_state", "default_state"],
            namespace,
        )
        result = asyncio.run(
            namespace["post_analytics_state"](
                "cam1",
                metadata=json.dumps({"frame_no": 8}),
                overlay=None,
                authorization=None,
            )
        )
        self.assertTrue(result["ok"])
        self.assertEqual(
            STORE.read_camera_state(self.state_db, "cam1").get("frame_no"),
            8,
            "the API accept path must remain authoritative in SQLite",
        )
        self.assertTrue(
            self.legacy_files["state"].exists(),
            "legacy state file must never be deleted",
        )
        self.assertEqual(
            self.legacy_files["state"].read_bytes(),
            self.legacy_bytes["state"],
            "legacy state mirror must no longer be written by API accepts",
        )


def _receipt_count(state_db: Path) -> int:
    with STORE.open_state_db(state_db) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM event_receipts").fetchone()[0])


def _feed_rows(state_db: Path, camera_id: str = "cam1") -> List[Dict[str, Any]]:
    return STORE.read_events(state_db, camera_id)


@unittest.skipUnless(STORE is not None, "api/app/store.py is required")
class EventReceiptStoreTests(unittest.TestCase):
    """Issue #537 wave 1: store.deliver_event receipt semantics.

    (a) identical retry → duplicate success with the stored original event,
    exactly one feed row and one receipt; (b) the receipt still prevents
    reinsertion after the feed row is pruned; conflict cases raise without
    committing partial state; a feed row without a receipt (crash between
    stages / pre-upgrade row) is repaired on retry.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_db = Path(self.tmp.name) / "state.sqlite3"
        self.event = {
            "event_id": "evt-1",
            "camera_id": "road1",
            "object_type": "car",
            "created_at": "2026-10-19T00:00:00+00:00",
            "snapshot_url": "/sea-speed/media/events/road1-evt-1.jpg",
        }
        self.content_hash = STORE.event_content_fingerprint(self.event)
        self.snapshot_hash = STORE.hash_bytes(b"jpeg-bytes")

    def test_identical_retry_returns_duplicate_and_stored_event(self) -> None:
        outcome, stored = STORE.deliver_event(
            self.state_db, "road1", self.event, self.content_hash, self.snapshot_hash, 500
        )
        self.assertEqual(outcome, "stored")
        self.assertIsNone(stored)
        outcome, stored = STORE.deliver_event(
            self.state_db, "road1", self.event, self.content_hash, self.snapshot_hash, 500
        )
        self.assertEqual(outcome, "duplicate")
        self.assertEqual(stored, self.event)
        self.assertEqual(len(_feed_rows(self.state_db, "road1")), 1)
        self.assertEqual(_receipt_count(self.state_db), 1)
        receipt = STORE.find_event_receipt(self.state_db, "evt-1")
        self.assertEqual(receipt["camera_id"], "road1")
        self.assertEqual(receipt["content_hash"], self.content_hash)
        self.assertEqual(receipt["snapshot_hash"], self.snapshot_hash)
        self.assertEqual(json.loads(receipt["response_event_json"]), self.event)
        self.assertTrue(receipt["completed_at"])

    def test_duplicate_is_still_blocked_after_feed_pruning(self) -> None:
        STORE.deliver_event(self.state_db, "road1", self.event, self.content_hash, self.snapshot_hash, 500)
        with STORE.open_state_db(self.state_db) as connection:
            connection.execute("DELETE FROM event_feed")
        outcome, stored = STORE.deliver_event(
            self.state_db, "road1", self.event, self.content_hash, self.snapshot_hash, 500
        )
        self.assertEqual(outcome, "duplicate")
        self.assertEqual(stored, self.event)
        self.assertEqual(_feed_rows(self.state_db, "road1"), [], "receipt hit must not reinsert the pruned feed row")
        self.assertEqual(_receipt_count(self.state_db), 1)

    def test_same_id_different_content_conflicts_without_partial_state(self) -> None:
        STORE.deliver_event(self.state_db, "road1", self.event, self.content_hash, self.snapshot_hash, 500)
        conflicting = dict(self.event, object_type="truck")
        with self.assertRaises(STORE.EventDeliveryConflict):
            STORE.deliver_event(
                self.state_db, "road1", conflicting,
                STORE.event_content_fingerprint(conflicting), self.snapshot_hash, 500,
            )
        self.assertEqual([event["object_type"] for event in _feed_rows(self.state_db, "road1")], ["car"])
        self.assertEqual(_receipt_count(self.state_db), 1)

    def test_same_id_different_camera_conflicts(self) -> None:
        STORE.deliver_event(self.state_db, "road1", self.event, self.content_hash, self.snapshot_hash, 500)
        with self.assertRaises(STORE.EventDeliveryConflict):
            STORE.deliver_event(self.state_db, "cam1", self.event, self.content_hash, self.snapshot_hash, 500)
        self.assertEqual(len(_feed_rows(self.state_db, "cam1")), 0)
        self.assertEqual(len(_feed_rows(self.state_db, "road1")), 1)

    def test_same_id_different_snapshot_conflicts(self) -> None:
        STORE.deliver_event(self.state_db, "road1", self.event, self.content_hash, self.snapshot_hash, 500)
        with self.assertRaises(STORE.EventDeliveryConflict):
            STORE.deliver_event(self.state_db, "road1", self.event, self.content_hash, STORE.hash_bytes(b"other-jpeg"), 500)

    def test_feed_row_without_receipt_is_repaired_on_retry(self) -> None:
        # Crash between stages: the feed row was written (pre-receipt), the
        # receipt was not — the retry completes the missing receipt and
        # reports the delivery as the first confirmed success.
        STORE.append_event(self.state_db, "road1", self.event, 500)
        self.assertEqual(_receipt_count(self.state_db), 0)
        outcome, stored = STORE.deliver_event(
            self.state_db, "road1", self.event, self.content_hash, self.snapshot_hash, 500
        )
        self.assertEqual(outcome, "duplicate")
        self.assertEqual(stored, self.event)
        self.assertEqual(len(_feed_rows(self.state_db, "road1")), 1, "no second feed row")
        self.assertEqual(_receipt_count(self.state_db), 1)

    def test_feed_unique_index_blocks_blind_duplicate_appends(self) -> None:
        STORE.initialize_state_db(self.state_db)
        STORE.append_event(self.state_db, "road1", self.event, 500)
        with self.assertRaises(sqlite3.IntegrityError):
            STORE.append_event(self.state_db, "road1", self.event, 500)


@unittest.skipUnless(STORE is not None, "api/app/store.py is required")
class EventFeedMigrationTests(unittest.TestCase):
    """Issue #537 wave 1: additive-at-boot migration over legacy feed rows.

    A legacy database (event_feed without the event_id column) is migrated
    at boot: the column is added, existing rows are backfilled from their
    payloads, the unique event_id index is created when history is clean —
    and duplicate historical IDs are inventoried and preserved verbatim,
    never deleted to make the index succeed.
    """

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_db = Path(self.tmp.name) / "state.sqlite3"

    def _legacy_boot(self) -> None:
        STORE._initialized.discard(str(self.state_db))
        STORE.initialize_state_db(self.state_db)

    def _seed_legacy_feed(self, rows: List[Dict[str, Any]]) -> None:
        connection = sqlite3.connect(str(self.state_db))
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE event_feed ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "camera_id TEXT NOT NULL, "
                "payload_json TEXT NOT NULL, "
                "created_at TEXT NOT NULL)"
            )
            for row in rows:
                connection.execute(
                    "INSERT INTO event_feed (camera_id, payload_json, created_at) VALUES (?, ?, ?)",
                    (row["camera_id"], json.dumps(row["payload"]), row["created_at"]),
                )
            connection.commit()
        finally:
            connection.close()

    def _event_id_column(self) -> bool:
        with STORE.open_state_db(self.state_db) as connection:
            return "event_id" in {row["name"] for row in connection.execute("PRAGMA table_info(event_feed)")}

    def test_fresh_boot_creates_receipt_table_and_unique_index(self) -> None:
        self._legacy_boot_on_empty_db()
        tables = _table_names(self.state_db)
        self.assertIn("event_receipts", tables)
        with STORE.open_state_db(self.state_db) as connection:
            indexes = {
                row["name"]
                for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'index'")
            }
        self.assertIn("idx_event_feed_event_id", indexes)

    def _legacy_boot_on_empty_db(self) -> None:
        self._legacy_boot()

    def test_legacy_rows_are_backfilled_and_indexed(self) -> None:
        self._seed_legacy_feed(
            [
                {"camera_id": "road1", "payload": {"event_id": "old-1", "object_type": "car"}, "created_at": "t1"},
                {"camera_id": "road1", "payload": {"event_id": "old-2", "object_type": "car"}, "created_at": "t2"},
                {"camera_id": "cam1", "payload": {"seq": 1}, "created_at": "t3"},
            ]
        )
        self._legacy_boot()
        self.assertTrue(self._event_id_column())
        with STORE.open_state_db(self.state_db) as connection:
            backfilled = {
                row["id"]: row["event_id"]
                for row in connection.execute("SELECT id, event_id FROM event_feed ORDER BY id")
            }
        self.assertEqual(list(backfilled.values()), ["old-1", "old-2", None])
        self.assertEqual(_receipt_count(self.state_db), 0, "backfill must not invent receipts")

    def test_duplicate_history_is_inventoried_and_never_deleted(self) -> None:
        # Legacy rows were persisted with the fully normalized event payload;
        # the duplicate pair below is the exact history the inventory must
        # protect, and the re-delivery uses one row's exact payload.
        duplicate_payload = {
            "event_id": "dup-1",
            "camera_id": "road1",
            "object_type": "car",
            "created_at": "2026-01-01T00:00:00+00:00",
            "snapshot_url": "/sea-speed/media/events/road1-dup-1.jpg",
        }
        self._seed_legacy_feed(
            [
                {"camera_id": "road1", "payload": duplicate_payload, "created_at": "t1"},
                {"camera_id": "road1", "payload": duplicate_payload, "created_at": "t2"},
                {"camera_id": "road1", "payload": {"event_id": "keep-1"}, "created_at": "t3"},
            ]
        )
        self._legacy_boot()
        with STORE.open_state_db(self.state_db) as connection:
            rows = connection.execute("SELECT id, event_id FROM event_feed ORDER BY id").fetchall()
            inventory = connection.execute(
                "SELECT value_json FROM migration_inventory WHERE key = 'event_feed_duplicate_event_ids'"
            ).fetchone()
            index = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'idx_event_feed_event_id'"
            ).fetchone()
        self.assertEqual(
            [row["event_id"] for row in rows],
            ["dup-1", "dup-1", "keep-1"],
            "conflicting historical rows must never be deleted to make the index succeed",
        )
        self.assertIsNotNone(inventory)
        self.assertEqual(
            json.loads(inventory["value_json"]),
            [{"event_id": "dup-1", "retained_rows": 2}],
        )
        self.assertIsNone(index, "the unique index must be deferred while duplicates exist")
        # Idempotent: a second boot neither deletes, duplicates the
        # inventory rows, nor changes the deferred-index disposition.
        self._legacy_boot()
        with STORE.open_state_db(self.state_db) as connection:
            self.assertEqual(int(connection.execute("SELECT COUNT(*) FROM event_feed").fetchone()[0]), 3)
            self.assertEqual(
                int(connection.execute("SELECT COUNT(*) FROM migration_inventory").fetchone()[0]), 1
            )
        # Degraded DB stays functional: a duplicate re-delivery of an
        # already-retained identity is receipt/row-gated, not appended again.
        outcome, stored = STORE.deliver_event(
            self.state_db, "road1", dict(duplicate_payload),
            STORE.event_content_fingerprint(duplicate_payload), STORE.hash_bytes(b"jpeg"), 500,
        )
        self.assertEqual(outcome, "duplicate")
        self.assertEqual(stored, duplicate_payload)
        with STORE.open_state_db(self.state_db) as connection:
            self.assertEqual(int(connection.execute("SELECT COUNT(*) FROM event_feed").fetchone()[0]), 3)

    def test_boot_migration_is_idempotent_on_clean_legacy_database(self) -> None:
        self._seed_legacy_feed(
            [{"camera_id": "road1", "payload": {"event_id": "old-1"}, "created_at": "t1"}]
        )
        self._legacy_boot()
        self._legacy_boot()
        self.assertTrue(self._event_id_column())
        self.assertEqual(len(_feed_rows(self.state_db, "road1")), 1)


@unittest.skipUnless(STORE is not None, "api/app/store.py is required")
class ReceiptRetentionTests(unittest.TestCase):
    """Issue #537 wave 1: the 90-day retention sweep removes only old receipts."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.state_db = Path(self.tmp.name) / "state.sqlite3"
        STORE.initialize_state_db(self.state_db)
        self.now = 1_800_000_000.0

    def _receipt(self, event_id: str, completed_at: str) -> None:
        with STORE.open_state_db(self.state_db) as connection:
            connection.execute(
                "INSERT INTO event_receipts (event_id, camera_id, content_hash, snapshot_hash, response_event_json, completed_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (event_id, "road1", "c", "s", "{}", completed_at),
            )

    def test_prune_removes_only_receipts_older_than_retention(self) -> None:
        moment = datetime.fromtimestamp(self.now, timezone.utc)
        old = (moment - timedelta(days=91)).isoformat()
        boundary = (moment - timedelta(days=90, seconds=1)).isoformat()
        fresh = (moment - timedelta(days=1)).isoformat()
        self._receipt("old", old)
        self._receipt("boundary", boundary)
        self._receipt("fresh", fresh)
        deleted = STORE.prune_event_receipts(self.state_db, now=self.now)
        self.assertEqual(deleted, 2)
        remaining = {row for row in _receipt_event_ids(self.state_db)}
        self.assertEqual(remaining, {"fresh"})

    def test_prune_with_default_retention_uses_90_days(self) -> None:
        self.assertEqual(STORE.EVENT_RECEIPTS_RETENTION_DAYS, 90)

    def test_prune_leaves_feed_and_crossings_untouched(self) -> None:
        moment = datetime.fromtimestamp(self.now, timezone.utc)
        self._receipt("old", (moment - timedelta(days=120)).isoformat())
        STORE.append_event(self.state_db, "road1", {"event_id": "feed-1"}, 500)
        STORE.append_crossing(self.state_db, "road1", {"event_id": "cross-1"})
        STORE.prune_event_receipts(self.state_db, now=self.now)
        self.assertEqual(_receipt_count(self.state_db), 0)
        self.assertEqual([event["event_id"] for event in _feed_rows(self.state_db, "road1")], ["feed-1"])
        self.assertEqual([record["event_id"] for record in STORE.read_crossings(self.state_db, "road1")], ["cross-1"])


def _receipt_event_ids(state_db: Path) -> List[str]:
    with STORE.open_state_db(state_db) as connection:
        return [str(row["event_id"]) for row in connection.execute("SELECT event_id FROM event_receipts")]


@unittest.skipUnless(STORE is not None, "api/app/store.py is required")
class AtomicWriteBytesTests(unittest.TestCase):
    """Issue #537 wave 1: atomic snapshot publish (design §6 API)."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.target = self.directory / "snap.jpg"

    def test_happy_path_publishes_exact_bytes_and_no_tmp(self) -> None:
        STORE.atomic_write_bytes(self.target, b"jpeg-v1")
        self.assertEqual(self.target.read_bytes(), b"jpeg-v1")
        self.assertEqual([p.name for p in self.directory.iterdir()], ["snap.jpg"])
        STORE.atomic_write_bytes(self.target, b"jpeg-v2")
        self.assertEqual(self.target.read_bytes(), b"jpeg-v2")
        self.assertEqual([p.name for p in self.directory.iterdir()], ["snap.jpg"])

    def test_failed_replace_leaves_previous_content_and_no_tmp(self) -> None:
        STORE.atomic_write_bytes(self.target, b"jpeg-v1")
        real_replace = os.replace

        def failing_replace(src: Any, dst: Any) -> None:
            raise OSError("disk full")

        try:
            os.replace = failing_replace
            with self.assertRaises(OSError):
                STORE.atomic_write_bytes(self.target, b"jpeg-v2")
        finally:
            os.replace = real_replace
        self.assertEqual(self.target.read_bytes(), b"jpeg-v1", "previous content must survive a failed publish")
        leftovers = [p.name for p in self.directory.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [], "orphan tmp must be cleaned after a failed publish")

    def test_failed_fsync_leaves_no_partial_file(self) -> None:
        real_fsync = os.fsync

        def failing_fsync(fd: int) -> None:
            raise OSError("fsync failed")

        try:
            os.fsync = failing_fsync
            with self.assertRaises(OSError):
                STORE.atomic_write_bytes(self.target, b"jpeg-bytes")
        finally:
            os.fsync = real_fsync
        self.assertFalse(self.target.exists(), "no partial file may be published")
        leftovers = [p.name for p in self.directory.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_concurrent_writers_never_share_a_tmp(self) -> None:
        errors: List[BaseException] = []

        def writer(index: int) -> None:
            try:
                for round_no in range(25):
                    STORE.atomic_write_bytes(self.target, f"writer-{index}-{round_no}".encode())
            except BaseException as error:  # pragma: no cover - failure path
                errors.append(error)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertTrue(self.target.read_bytes().startswith(b"writer-"))
        leftovers = [p.name for p in self.directory.iterdir() if p.name.endswith(".tmp")]
        self.assertEqual(leftovers, [])


@unittest.skipUnless(STORE is not None, "api/app/store.py is required")
class EventIdentityHelperTests(unittest.TestCase):
    def test_content_fingerprint_is_stable_and_content_sensitive(self) -> None:
        event = {"event_id": "e1", "camera_id": "road1", "object_type": "car", "created_at": "t"}
        first = STORE.event_content_fingerprint(event)
        self.assertEqual(first, STORE.event_content_fingerprint(dict(event)))
        self.assertNotEqual(first, STORE.event_content_fingerprint(dict(event, object_type="truck")))
        self.assertNotEqual(first, STORE.event_content_fingerprint(dict(event, camera_id="cam1")))
        self.assertNotEqual(first, STORE.event_content_fingerprint(dict(event, created_at="t2")))

    def test_safe_event_filename_keeps_safe_ids_verbatim(self) -> None:
        self.assertEqual(STORE.safe_event_filename("road1", "1750000000-abcd1234"), "road1-1750000000-abcd1234.jpg")
        self.assertEqual(STORE.safe_event_filename("cam1", "E.1_2-3"), "cam1-E.1_2-3.jpg")

    def test_safe_event_filename_never_escapes_the_media_directory(self) -> None:
        for hostile in ("../../etc/passwd", "..", "a/b", "a\\b", ".hidden", "", "x" * 500, "ev id"):
            filename = STORE.safe_event_filename("road1", hostile)
            self.assertTrue(filename.startswith("road1-"))
            self.assertTrue(filename.endswith(".jpg"))
            self.assertEqual(Path(filename).name, filename, f"filename must stay a bare name for {hostile!r}")
            self.assertNotIn("/", filename)
            self.assertNotIn("\\", filename)
            self.assertNotIn("..", filename)
        # Deterministic: the same hostile id always maps to the same name.
        self.assertEqual(
            STORE.safe_event_filename("road1", "../../etc/passwd"),
            STORE.safe_event_filename("road1", "../../etc/passwd"),
        )


if __name__ == "__main__":
    unittest.main()
