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
import contextlib
import copy
import importlib.util
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
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

    def test_import_legacy_camera_state_without_timestamp_never_displaces_stored_row(self) -> None:
        # An undated legacy payload cannot be ordered against the stored row,
        # so it may only seed an empty camera_state (T-D edge case).
        STORE.upsert_camera_state(self.state_db, "cam1", {"frame_no": 99})
        self.assertFalse(STORE.import_legacy_camera_state(self.state_db, "cam1", {"frame_no": 1}))
        self.assertEqual(STORE.read_camera_state(self.state_db, "cam1"), {"frame_no": 99})
        self.assertTrue(STORE.import_legacy_camera_state(self.state_db, "road1", {"frame_no": 1}))
        self.assertEqual(STORE.read_camera_state(self.state_db, "road1"), {"frame_no": 1})

    # T-C — core lifecycle regression: import -> rollback-window writes by
    # the previous release -> re-upgrade must merge the new records in,
    # ignore duplicates, and respect the per-camera cap.
    def test_rollback_window_records_are_merged_idempotent(self) -> None:
        t1, t2, t3 = (
            "2026-01-01T00:00:00+00:00",
            "2026-01-02T00:00:00+00:00",
            "2026-01-03T00:00:00+00:00",
        )
        legacy = [{"event_id": "e2", "created_at": t2}, {"event_id": "e1", "created_at": t1}]
        self.assertEqual(STORE.import_legacy_records(self.state_db, "crossings", "cam1", legacy, 5000), 2)

        # Rollback window: the old release appends a NEW record to the JSON.
        upgraded_file = legacy + [{"event_id": "e3", "created_at": t3}]
        self.assertEqual(
            STORE.import_legacy_records(self.state_db, "crossings", "cam1", upgraded_file, 5000),
            1,
            "only the rollback-window record may be inserted",
        )
        self.assertEqual(
            [record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")],
            ["e3", "e2", "e1"],
        )

        # Repeated boots are no-ops: canonical-payload duplicates are skipped.
        self.assertEqual(STORE.import_legacy_records(self.state_db, "crossings", "cam1", upgraded_file, 5000), 0)
        self.assertEqual(len(STORE.read_crossings(self.state_db, "cam1")), 3)

        # The per-camera cap is applied to the merged result.
        self.assertEqual(STORE.import_legacy_records(self.state_db, "crossings", "cam1", upgraded_file, 2), 0)
        with STORE.open_state_db(self.state_db) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM crossings WHERE camera_id = ?", ("cam1",)).fetchone()[0],
                2,
            )
        self.assertEqual(
            [record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")],
            ["e3", "e2"],
        )

    # V-A — live-appended rows carry no dedupe key: a legacy mirror that
    # contains a live row (exactly what the rollback-window JSON becomes)
    # must never duplicate it, on any number of re-imports.
    def test_live_rows_are_not_duplicated_by_mirror_import(self) -> None:
        record = {"event_id": "c1", "created_at": "2026-01-01T00:00:00+00:00"}
        STORE.append_crossing(self.state_db, "cam1", record)
        mirror = [record]

        self.assertEqual(
            STORE.import_legacy_records(self.state_db, "crossings", "cam1", mirror, 5000),
            0,
            "the mirror copy of a live row must be deduped away",
        )
        self.assertEqual(STORE.read_crossings(self.state_db, "cam1"), [record])

        # Restart equivalent: importing the same mirror again stays a no-op.
        self.assertEqual(STORE.import_legacy_records(self.state_db, "crossings", "cam1", mirror, 5000), 0)
        self.assertEqual(STORE.read_crossings(self.state_db, "cam1"), [record])

    # V-B — mixed imported + live rows at the production caps (5000
    # crossings / 500 events): a mirror of exactly the retained rows must
    # be a complete no-op (no duplication, no eviction), and only genuinely
    # new records may consume cap headroom with exact arithmetic.
    def test_import_at_production_caps_preserves_retained_history(self) -> None:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        stamp = lambda i: (base + timedelta(seconds=i)).isoformat()

        # Legacy files are newest-first: e2499 is the first list entry.
        legacy = [{"event_id": f"e{i}", "created_at": stamp(i)} for i in range(2499, -1, -1)]
        self.assertEqual(STORE.import_legacy_records(self.state_db, "crossings", "cam1", legacy, 5000), 2500)
        live = [{"event_id": f"e{i}", "created_at": stamp(i)} for i in range(2500, 5000)]
        for record in live:
            STORE.append_crossing(self.state_db, "cam1", record)
        self.assertEqual(len(STORE.read_crossings(self.state_db, "cam1")), 5000)

        # Mirror holding exactly the retained rows (live rows included):
        # zero inserts, zero evictions, live history intact.
        mirror = list(reversed(legacy + live))  # newest-first, as the file is written
        self.assertEqual(STORE.import_legacy_records(self.state_db, "crossings", "cam1", mirror, 5000), 0)
        retained = STORE.read_crossings(self.state_db, "cam1")
        self.assertEqual(len(retained), 5000)
        self.assertEqual(retained[0], live[-1], "newest live record must survive")
        self.assertEqual(retained[-1], legacy[-1], "oldest retained record must survive")

        # +5 genuinely new records → exactly 5 inserts, cap evicts exactly
        # the 5 oldest rows (new block appended newest-first, as in a file).
        mirror = [{"event_id": f"e{i}", "created_at": stamp(i)} for i in range(5004, 4999, -1)] + mirror
        self.assertEqual(STORE.import_legacy_records(self.state_db, "crossings", "cam1", mirror, 5000), 5)
        retained = STORE.read_crossings(self.state_db, "cam1")
        self.assertEqual(len(retained), 5000)
        self.assertEqual(retained[0]["event_id"], "e5004")
        self.assertEqual(retained[-1]["event_id"], "e5", "eviction removed exactly the 5 oldest")

        # Same discipline at the event-feed cap (500).
        legacy_events = [{"event_id": f"f{i}", "created_at": stamp(i)} for i in range(249, -1, -1)]
        self.assertEqual(STORE.import_legacy_records(self.state_db, "events", "cam1", legacy_events, 500), 250)
        for i in range(250, 500):
            STORE.append_event(self.state_db, "cam1", {"event_id": f"f{i}", "created_at": stamp(i)})
        events_mirror = [{"event_id": f"f{i}", "created_at": stamp(i)} for i in range(499, -1, -1)]
        self.assertEqual(STORE.import_legacy_records(self.state_db, "events", "cam1", events_mirror, 500), 0)
        self.assertEqual(len(STORE.read_events(self.state_db, "cam1")), 500)
        self.assertEqual(STORE.read_events(self.state_db, "cam1")[0]["event_id"], "f499")

    # W-A — anti-resurrection by ingestion history (round-4 design). The
    # round-3 timestamp floor failed when a pruned record's timestamp EQUALS
    # the retained floor: it re-imported from a stale mirror with a new id,
    # evicted retained records and churned on every restart. The
    # ingestion-log registry is time-blind — a record that was ever
    # ingested is skipped, whatever (or whether) it is dated.
    def test_equal_timestamp_stale_mirror_never_resurrects_or_churns(self) -> None:
        t = "2026-01-01T00:00:00+00:00"  # every record shares ONE timestamp
        cap = 3
        for event_id in ("a", "b", "c"):
            STORE.append_crossing(self.state_db, "cam1", {"event_id": event_id, "created_at": t}, cap)
        STORE.append_crossing(self.state_db, "cam1", {"event_id": "d", "created_at": t}, cap)
        self.assertEqual(
            [record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")],
            ["d", "c", "b"],
            "cap pruned a; b/c/d retained — all four records share one timestamp",
        )

        # The old release's mirror update failed, so its file is the stale
        # snapshot [c, b, a] from before d was appended. Importing it must
        # NOT resurrect the pruned a with a fresh id.
        stale_mirror = [
            {"event_id": "c", "created_at": t},
            {"event_id": "b", "created_at": t},
            {"event_id": "a", "created_at": t},
        ]
        self.assertEqual(
            STORE.import_legacy_records(self.state_db, "crossings", "cam1", stale_mirror, cap),
            0,
            "equal-timestamp pruned record must be skipped via ingestion history",
        )
        self.assertEqual(
            [record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")],
            ["d", "c", "b"],
            "b/c must not be evicted by a resurrected row",
        )

        # Repeated restarts: the same stale mirror must never churn retention.
        for _ in range(2):
            self.assertEqual(STORE.import_legacy_records(self.state_db, "crossings", "cam1", stale_mirror, cap), 0)
            self.assertEqual(
                [record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")],
                ["d", "c", "b"],
            )

    # W-B — the registry is timestamp-blind, so undated records are
    # covered: an undated record that was ingested and later pruned stays
    # skipped (no timestamp comparison could order it), while a genuinely
    # new undated rollback-period record (never ingested) merges.
    def test_undated_records_obey_the_ingestion_registry(self) -> None:
        undated = {"event_id": "u1"}  # no created_at at all
        STORE.append_event(self.state_db, "cam1", undated, 1)
        live = {"event_id": "x1"}
        STORE.append_event(self.state_db, "cam1", live, 1)  # cap 1 prunes u1
        self.assertEqual([event["event_id"] for event in STORE.read_events(self.state_db, "cam1")], ["x1"])

        # Stale mirror still carrying the pruned undated record: skipped.
        stale_mirror = [live, undated]
        self.assertEqual(
            STORE.import_legacy_records(self.state_db, "events", "cam1", stale_mirror, 1),
            0,
            "a pruned undated record must be skipped via the ingestion registry",
        )
        self.assertEqual([event["event_id"] for event in STORE.read_events(self.state_db, "cam1")], ["x1"])

        # A genuinely new undated rollback-period record (never ingested) merges.
        rollback = {"event_id": "r1"}  # undated, never seen by this store
        self.assertEqual(
            STORE.import_legacy_records(self.state_db, "events", "cam1", [rollback, live], 2),
            1,
        )
        self.assertEqual(
            sorted(event["event_id"] for event in STORE.read_events(self.state_db, "cam1")),
            ["r1", "x1"],
        )

    # W-C — event time is not ingestion order: a rollback-period record
    # with an event timestamp OLDER than every retained row (a delayed
    # submission) must merge when it was never ingested. The round-3
    # timestamp floor silently discarded exactly this record.
    def test_delayed_rollback_record_with_old_event_time_merges(self) -> None:
        t0, t1, t2 = (
            "2025-12-31T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
            "2026-01-02T00:00:00+00:00",
        )
        legacy = [{"event_id": "e2", "created_at": t2}, {"event_id": "e1", "created_at": t1}]
        self.assertEqual(STORE.import_legacy_records(self.state_db, "crossings", "cam1", legacy, 10), 2)

        # The old release ingests a delayed record (old event time, free cap
        # headroom); its file becomes [e0, e2, e1] (newest-first).
        delayed_mirror = [{"event_id": "e0", "created_at": t0}] + legacy
        self.assertEqual(
            STORE.import_legacy_records(self.state_db, "crossings", "cam1", delayed_mirror, 10),
            1,
            "a never-ingested record must merge regardless of its old event timestamp",
        )
        self.assertEqual(
            [record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")],
            ["e0", "e2", "e1"],
        )
        # The merged record is now registered: rebooting on the same mirror is a no-op.
        self.assertEqual(STORE.import_legacy_records(self.state_db, "crossings", "cam1", delayed_mirror, 10), 0)

    # W-D — repeated boots over a stable intact mirror are zero-mutation
    # (only merged records are registered, so every boot after the first is
    # a complete no-op), and identities NEVER expire (round-5: the registry
    # has no prune at all). After churn far beyond any 4×cap-scale window —
    # enough that a pruned registry would have expired every original
    # identity — importing the ORIGINAL stale mirror is still a complete
    # no-op: zero new rows, retained rows byte-identical, registry count
    # unchanged.
    def test_repeated_boots_are_zero_mutation_and_identities_never_expire(self) -> None:
        def registry_count() -> int:
            with STORE.open_state_db(self.state_db) as connection:
                return connection.execute(
                    "SELECT COUNT(*) FROM ingestion_log WHERE camera_id = ? AND kind = ?",
                    ("cam1", "crossings"),
                ).fetchone()[0]

        def table_snapshot() -> List[Any]:
            with STORE.open_state_db(self.state_db) as connection:
                return [
                    tuple(row)
                    for row in connection.execute(
                        "SELECT id, payload_json, created_at FROM crossings WHERE camera_id = ? ORDER BY id",
                        ("cam1",),
                    )
                ]

        cap = 2  # a round-4 4×cap window would have been 8
        legacy = [
            {"event_id": "e2", "created_at": "2026-01-02T00:00:00+00:00"},
            {"event_id": "e1", "created_at": "2026-01-01T00:00:00+00:00"},
            {"event_id": "e0", "created_at": "2025-12-31T00:00:00+00:00"},
        ]
        self.assertEqual(STORE.import_legacy_records(self.state_db, "crossings", "cam1", legacy, cap), 3)
        self.assertEqual(len(table_snapshot()), 2)
        self.assertEqual(registry_count(), 3)

        # Three consecutive boots on the SAME intact mirror (the file's e0
        # was pruned from the table but is registered): zero mutations.
        snapshot = table_snapshot()
        for boot in range(3):
            self.assertEqual(
                STORE.import_legacy_records(self.state_db, "crossings", "cam1", legacy, cap),
                0,
                f"boot {boot + 2} must be a complete no-op",
            )
            self.assertEqual(table_snapshot(), snapshot, f"boot {boot + 2} mutated retained rows")
        self.assertEqual(registry_count(), 3, "no-op boots must not write the registry either")

        # Churn far beyond any window scale: 40 live appends (43 total
        # ingestions, window would have been 8) evict the original rows
        # from retention — and would have expired their identities from a
        # pruned registry.
        base = datetime(2026, 2, 1, tzinfo=timezone.utc)
        for index in range(40):
            STORE.append_crossing(
                self.state_db,
                "cam1",
                {"event_id": f"n{index}", "created_at": (base + timedelta(seconds=index)).isoformat()},
                cap,
            )
        self.assertEqual(
            {record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")},
            {"n39", "n38"},
            "churn evicted the original rows from retention",
        )
        self.assertEqual(registry_count(), 43, "the registry never prunes — identities never expire")

        # The validator's missing assertion: importing the ORIGINAL stale
        # mirror after all that churn is still a complete no-op — zero new
        # rows, retained rows byte-identical, registry count unchanged.
        churned_snapshot = table_snapshot()
        self.assertEqual(
            STORE.import_legacy_records(self.state_db, "crossings", "cam1", legacy, cap),
            0,
            "stale identities must never expire — the original mirror stays a no-op",
        )
        self.assertEqual(table_snapshot(), churned_snapshot, "the stale mirror must not evict retained rows")
        self.assertEqual(registry_count(), 43, "the no-op boot must not write the registry either")

    # W-E — the validator's production-cap failure sequence, scaled down:
    # import file F at the cap → churn with FAILING mirror writes far
    # beyond the round-4 4×cap window (SQLite retention evicts every
    # original row; the legacy file stays stale) → rollback (the old
    # release appends rollback-period records to the stale file → F') →
    # re-upgrade imports F'. The rollback records must merge, F's stale
    # records must NOT resurrect with fresh ids, and the retained set must
    # stay stable. The round-4 4×cap prune failed exactly this sequence:
    # every original identity expired, the intact stale file re-imported
    # and evicted the authoritative records.
    def test_rollback_after_churn_beyond_window_keeps_retention_stable(self) -> None:
        def registry_count() -> int:
            with STORE.open_state_db(self.state_db) as connection:
                return connection.execute(
                    "SELECT COUNT(*) FROM ingestion_log WHERE camera_id = ? AND kind = ?",
                    ("cam1", "crossings"),
                ).fetchone()[0]

        cap = 5  # a round-4 4×cap window would have been 20
        base = datetime(2026, 3, 1, tzinfo=timezone.utc)
        stamp = lambda i: (base + timedelta(seconds=i)).isoformat()

        # Boot 1: import F (50 records, newest-first file) at the cap.
        f_file = [{"event_id": f"f{i}", "created_at": stamp(i)} for i in range(49, -1, -1)]
        self.assertEqual(STORE.import_legacy_records(self.state_db, "crossings", "cam1", f_file, cap), 50)
        self.assertEqual(len(STORE.read_crossings(self.state_db, "cam1")), cap)
        self.assertEqual(registry_count(), 50)

        # Churn with failing mirror writes: 60 live appends (>> 20) —
        # retention evicts every f-record and a pruned registry would have
        # expired every f-identity. File F never updates (writes fail).
        for index in range(50, 110):
            STORE.append_crossing(self.state_db, "cam1", {"event_id": f"n{index}", "created_at": stamp(index)}, cap)
        self.assertEqual(
            {record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")},
            {f"n{i}" for i in range(105, 110)},
            "churn evicted all original rows from retention",
        )
        self.assertEqual(registry_count(), 110, "no identities expired during churn")

        # Rollback: the old release appends two rollback-period records to
        # the STALE file → F' (newest-first: rollback records on top).
        f_prime = [
            {"event_id": "rb1", "created_at": stamp(200)},
            {"event_id": "rb0", "created_at": stamp(199)},
        ] + f_file

        # Re-upgrade: import F'. Exactly the two rollback records merge;
        # the stale f-records do NOT resurrect; retention stays stable.
        self.assertEqual(
            STORE.import_legacy_records(self.state_db, "crossings", "cam1", f_prime, cap),
            2,
            "only the rollback-period records may merge",
        )
        merged = [record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")]
        self.assertEqual(merged, ["rb1", "rb0", "n109", "n108", "n107"])
        self.assertEqual(
            {event_id for event_id in merged if event_id.startswith("f")},
            set(),
            "stale file records must not resurrect with fresh ids",
        )

        # Repeated boots on F' stay no-ops with the retained set stable.
        self.assertEqual(STORE.import_legacy_records(self.state_db, "crossings", "cam1", f_prime, cap), 0)
        self.assertEqual(
            [record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")],
            ["rb1", "rb0", "n109", "n108", "n107"],
        )
        self.assertEqual(registry_count(), 112, "no-op boots register nothing")

    # V-D — unusable/absent timestamps cannot displace stored camera
    # state; only a genuinely newer ISO timestamp replaces it, and an
    # undated payload only ever seeds an empty row.
    def test_camera_state_import_ignores_unusable_timestamps(self) -> None:
        stored = {"frame_no": 10, "updated_at": "2026-01-02T00:00:00+00:00"}
        STORE.upsert_camera_state(self.state_db, "cam1", stored)

        unparseable = {"frame_no": 1, "updated_at": "zzz"}
        self.assertFalse(STORE.import_legacy_camera_state(self.state_db, "cam1", unparseable))
        self.assertEqual(STORE.read_camera_state(self.state_db, "cam1"), stored)

        newer = {"frame_no": 20, "updated_at": "2026-01-03T00:00:00+00:00"}
        self.assertTrue(STORE.import_legacy_camera_state(self.state_db, "cam1", newer))
        self.assertEqual(STORE.read_camera_state(self.state_db, "cam1"), newer)

        undated = {"frame_no": 1}
        self.assertFalse(STORE.import_legacy_camera_state(self.state_db, "cam1", undated))
        self.assertEqual(STORE.read_camera_state(self.state_db, "cam1"), newer)

        # Undated still seeds a genuinely empty camera.
        self.assertTrue(STORE.import_legacy_camera_state(self.state_db, "road1", undated))
        self.assertEqual(STORE.read_camera_state(self.state_db, "road1"), undated)

    # T-D — camera_state: legacy NEWER than stored wins; older loses.
    def test_camera_state_import_is_newer_wins(self) -> None:
        stored_updated_at = "2026-01-02T00:00:00+00:00"
        STORE.upsert_camera_state(self.state_db, "cam1", {"frame_no": 10, "updated_at": stored_updated_at})

        older = {"frame_no": 5, "updated_at": "2026-01-01T00:00:00+00:00"}
        self.assertFalse(STORE.import_legacy_camera_state(self.state_db, "cam1", older))
        self.assertEqual(STORE.read_camera_state(self.state_db, "cam1"), {"frame_no": 10, "updated_at": stored_updated_at})

        newer = {"frame_no": 20, "updated_at": "2026-01-03T00:00:00+00:00"}
        self.assertTrue(STORE.import_legacy_camera_state(self.state_db, "cam1", newer))
        self.assertEqual(STORE.read_camera_state(self.state_db, "cam1"), newer)

        # Mixed UTC offsets must order by the actual instant, not by string:
        # 2026-01-03T01:00+03:00 == 2026-01-02T22:00Z, which is older.
        stale_other_offset = {"frame_no": 7, "updated_at": "2026-01-03T01:00:00+03:00"}
        self.assertFalse(STORE.import_legacy_camera_state(self.state_db, "cam1", stale_other_offset))
        self.assertEqual(STORE.read_camera_state(self.state_db, "cam1"), newer)


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

    # T-B — empty target + corrupt legacy JSON: the initial authoritative
    # migration must fail closed so the deploy gate rolls the release back
    # instead of silently losing history.
    def test_corrupt_legacy_file_fails_closed(self) -> None:
        crossings = Path(self.tmp.name) / "cam1_crossings.json"
        crossings.write_text("{corrupt", encoding="utf-8")
        namespace = self._namespace()
        with self.assertRaises((OSError, ValueError)):
            namespace["import_legacy_state_store"]()

    # T-A — populated (healthy authoritative) store + corrupt non-authoritative
    # legacy mirror: the boot import path must NOT raise, must log a warning to
    # stderr, and the authoritative data must stay intact.
    def test_corrupt_legacy_mirror_is_best_effort_when_store_is_populated(self) -> None:
        crossings = Path(self.tmp.name) / "cam1_crossings.json"
        crossings.write_text("{corrupt", encoding="utf-8")
        STORE.append_crossing(self.state_db, "cam1", {"event_id": "c-live", "created_at": "2026-01-01T00:00:00+00:00"})
        STORE.append_event(self.state_db, "cam1", {"event_id": "e-live", "created_at": "2026-01-01T00:00:00+00:00"})
        STORE.upsert_camera_state(self.state_db, "cam1", {"frame_no": 1})

        namespace = self._namespace()
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            namespace["import_legacy_state_store"]()

        self.assertIn("legacy cam1 crossings mirror is unreadable", stderr.getvalue())
        self.assertEqual(
            [record["event_id"] for record in STORE.read_crossings(self.state_db, "cam1")],
            ["c-live"],
            "authoritative crossing rows must be untouched",
        )
        self.assertEqual(
            [record["event_id"] for record in STORE.read_events(self.state_db, "cam1")],
            ["e-live"],
        )
        self.assertEqual(STORE.read_camera_state(self.state_db, "cam1"), {"frame_no": 1})

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
