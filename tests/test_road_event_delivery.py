"""Handler-level fault-injection tests for road-event delivery (issue #537).

These tests AST-execute the REAL ``post_analytics_event`` from
``api/app/main.py`` (the same extraction pattern as
``tests/test_road_event_hygiene.py``) against the REAL ``api/app/store.py``
primitives in temporary directories. The objects registry is replaced by an
INSERT OR IGNORE spy that mirrors ``persist_object_event`` semantics without
touching production /opt state.

Proven behaviors (design P1-01 §3/§6/§9, API part):

* (a) duplicate delivery, same ID + same content → HTTP 200 with
  ``duplicate=true`` and the STORED original event; exactly one feed row and
  one receipt (also covers the design case "server commits, response lost →
  retry returns duplicate");
* (b) duplicate after simulated feed pruning → the receipt still prevents
  reinsertion (no new feed row, stored success response);
* (c) same ID with different immutable content → 409, no partial state;
* (d) same ID with different camera → 409, no cross-camera state;
* (e) atomic snapshot publish — a simulated publish failure leaves no
  partial file and no orphan tmp, and a retry succeeds;
* (f) crash between stages — snapshot written and/or registry written with
  feed+receipt missing → the retry completes the missing pieces;
* (g) concurrent duplicate ingestion → exactly one stored delivery, every
  other request served the duplicate success, no failures;
* the road person-filter response is preserved verbatim and persists
  nothing;
* the events-media sweep cleans orphaned ``*.tmp`` siblings left by
  interrupted atomic writes while keeping every pinned behavior.

RED authenticity: cases (a)-(d), (f), (g) and the sweep tmp case fail
against the pre-change behavior (blind feed insert, no receipts, non-atomic
snapshot write, no ``duplicate`` response field) for behavioral reasons —
not for missing imports. The recorded RED run is referenced from
specs/537-wave1-event-delivery-receipts/.
"""

import ast
import asyncio
import copy
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
API = REPO_ROOT / "api" / "app" / "main.py"
ANALYTICS_FILE = REPO_ROOT / "api" / "app" / "analytics.py"
STORE_FILE = REPO_ROOT / "api" / "app" / "store.py"


def _load_store():
    spec = importlib.util.spec_from_file_location("api_store_road_delivery_test", STORE_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STORE = _load_store()

_LIST_FILE = API  # post_analytics_event lives in main.py on base and head


class HTTPExceptionStub(Exception):
    def __init__(self, status_code: Optional[int] = None, detail: Any = None, *args, **kwargs) -> None:
        super().__init__(detail or "")
        self.status_code = status_code
        self.detail = detail


class FakeSnapshot:
    def __init__(self, data: bytes = b"jpeg-bytes") -> None:
        self._data = data

    async def read(self) -> bytes:
        return self._data


class FakeRegistry:
    """INSERT OR IGNORE spy mirroring persist_object_event semantics."""

    def __init__(self) -> None:
        self.registered: List[Dict[str, Any]] = []
        self.ids: set = set()

    def persist_object_event(self, event: Dict[str, Any]) -> bool:
        snapshot_url = str(event.get("snapshot_url") or "").strip()
        if not snapshot_url.startswith("/sea-speed/media/"):
            return False
        object_id = str(event.get("event_id"))
        if object_id in self.ids:
            return False
        self.ids.add(object_id)
        self.registered.append(event)
        return True


def _receipt_rows(state_db: Path) -> List[Dict[str, Any]]:
    with STORE.open_state_db(state_db) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM event_receipts").fetchall()]


class RoadEventDeliveryTestCase(unittest.TestCase):
    """Shared harness: real store, temp dirs, spy registry, recorded sweep."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.temp_dir = Path(tmp.name)
        self.state_db = self.temp_dir / "state.sqlite3"
        self.media_dir = self.temp_dir / "events"
        self.media_dir.mkdir(parents=True, exist_ok=True)
        STORE.initialize_state_db(self.state_db)
        self.registry = FakeRegistry()
        self.sweep_calls: List[Dict[str, Any]] = []

        def record_sweep(force: bool = False, now: Optional[float] = None) -> int:
            self.sweep_calls.append({"force": force, "now": now})
            return 0

        self.namespace: Dict[str, Any] = {
            "json": json,
            "uuid": __import__("uuid"),
            "Path": Path,
            "Dict": Dict,
            "Any": Any,
            "Optional": Optional,
            "UploadFile": type("UploadFileStub", (), {}),
            "Form": lambda *a, **k: None,
            "File": lambda *a, **k: None,
            "Header": lambda *a, **k: None,
            "HTTPException": HTTPExceptionStub,
            "require_auth": lambda token: None,
            "analytics_identity": lambda camera_id: (
                {"analytics_profile": "water-v1", "domain": "water"}
                if camera_id == "cam1"
                else {"analytics_profile": "road-v1", "domain": "road"}
            ),
            "EVENTS_MEDIA_DIR": self.media_dir,
            "now_iso": lambda: "2026-10-19T12:00:00+00:00",
            "persist_object_event": self.registry.persist_object_event,
            "sweep_events_media": record_sweep,
            "TELEMETRY_SCHEMA": "sea_speed_telemetry_v1",
            "VEHICLE_EVENT_SCHEMA": "sea_speed_vehicle_event_v1",
            "WORKER_STATE_SCHEMA": "sea_speed_worker_state_v1",
            "store": STORE,
            "STATE_DB_FILE": self.state_db,
            "EVENTS_FEED_LIMIT": 500,
            "sys": sys,
        }
        self.post = self._rebind_handler()

    def _rebind_handler(self) -> Any:
        """AST-execute the real handler body against this test's namespace."""
        tree = ast.parse(API.read_text(encoding="utf-8-sig"), filename=str(API))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "post_analytics_event":
                cloned = copy.deepcopy(node)
                cloned.decorator_list = []
                module = ast.Module(body=[cloned], type_ignores=[])
                ast.fix_missing_locations(module)
                exec(compile(module, str(API), "exec"), self.namespace)
                return self.namespace["post_analytics_event"]
        raise AssertionError("post_analytics_event not found")

    def post_event(
        self,
        metadata: Dict[str, Any],
        snapshot: Any = None,
        camera_id: str = "road1",
    ) -> Dict[str, Any]:
        return asyncio.run(
            self.post(
                camera_id,
                metadata=json.dumps(metadata),
                snapshot=snapshot if snapshot is not None else FakeSnapshot(),
                authorization=None,
            )
        )

    def snapshot_path(self, camera_id: str, event_id: str) -> Path:
        return self.media_dir / STORE.safe_event_filename(camera_id, event_id)

    def tmp_leftovers(self) -> List[str]:
        return [p.name for p in self.media_dir.iterdir() if p.name.endswith(".tmp")]


class DuplicateDeliveryTests(RoadEventDeliveryTestCase):
    def test_duplicate_same_id_same_content_returns_stored_success(self) -> None:
        metadata = {
            "event_id": "evt-1",
            "object_type": "car",
            "created_at": "2026-10-19T11:59:00+00:00",
        }
        first = self.post_event(metadata)
        self.assertTrue(first["ok"])
        self.assertIs(first.get("duplicate"), False, "first delivery must report duplicate=false")
        self.assertEqual(first["event"]["event_id"], "evt-1")

        second = self.post_event(metadata)
        self.assertTrue(second["ok"])
        self.assertIs(second.get("duplicate"), True, "retry must report duplicate=true")
        self.assertEqual(second["event"], first["event"], "duplicate must return the stored original event")
        self.assertEqual(second["event"]["snapshot_url"], first["event"]["snapshot_url"])

        events = STORE.read_events(self.state_db, "road1")
        self.assertEqual([event["event_id"] for event in events], ["evt-1"], "exactly one feed row")
        receipts = _receipt_rows(self.state_db)
        self.assertEqual(len(receipts), 1, "exactly one receipt")
        self.assertEqual(receipts[0]["camera_id"], "road1")
        self.assertEqual(json.loads(receipts[0]["response_event_json"]), first["event"])
        self.assertTrue(self.snapshot_path("road1", "evt-1").is_file())

    def test_duplicate_delivery_records_one_registry_object(self) -> None:
        metadata = {"event_id": "evt-reg", "object_type": "car", "created_at": "2026-10-19T11:59:00+00:00"}
        self.post_event(metadata)
        self.post_event(metadata)
        self.assertEqual(len(self.registry.registered), 1, "the registry must see the object exactly once")

    def test_person_gate_response_is_preserved_verbatim(self) -> None:
        result = self.post_event({"event_id": "p1", "object_type": "person"}, snapshot=FakeSnapshot(b"jpeg"))
        self.assertEqual(result, {"ok": True, "event": None})
        self.assertEqual(STORE.read_events(self.state_db, "road1"), [], "person events never reach the feed")
        self.assertEqual(_receipt_rows(self.state_db), [], "person events never receive a receipt")
        self.assertEqual(self.registry.registered, [], "person events are never persisted")
        self.assertEqual(list(self.media_dir.iterdir()), [], "no snapshot is written for person events")


class DuplicateAfterPruneTests(RoadEventDeliveryTestCase):
    def test_receipt_prevents_reinsertion_after_feed_pruning(self) -> None:
        metadata = {"event_id": "evt-prune", "object_type": "car", "created_at": "2026-10-19T11:58:00+00:00"}
        first = self.post_event(metadata)
        self.assertIs(first.get("duplicate"), False)
        # Simulated feed pruning (the 500-per-camera cap or a future sweep).
        with STORE.open_state_db(self.state_db) as connection:
            connection.execute("DELETE FROM event_feed")
        self.assertEqual(STORE.read_events(self.state_db, "road1"), [])

        retry = self.post_event(metadata)
        self.assertTrue(retry["ok"])
        self.assertIs(retry.get("duplicate"), True)
        self.assertEqual(retry["event"], first["event"], "stored success response must survive pruning")
        self.assertEqual(
            STORE.read_events(self.state_db, "road1"),
            [],
            "the receipt must prevent feed reinsertion after pruning",
        )
        self.assertEqual(len(_receipt_rows(self.state_db)), 1)


class ConflictTests(RoadEventDeliveryTestCase):
    def test_same_id_different_snapshot_content_is_409_without_partial_state(self) -> None:
        metadata = {"event_id": "evt-409", "object_type": "car", "created_at": "2026-10-19T11:57:00+00:00"}
        first = self.post_event(metadata)
        self.assertIs(first.get("duplicate"), False)
        original_bytes = self.snapshot_path("road1", "evt-409").read_bytes()
        feed_before = STORE.read_events(self.state_db, "road1")
        receipts_before = _receipt_rows(self.state_db)

        with self.assertRaises(HTTPExceptionStub) as context:
            self.post_event(metadata, snapshot=FakeSnapshot(b"different-jpeg"))
        self.assertEqual(context.exception.status_code, 409)

        self.assertEqual(STORE.read_events(self.state_db, "road1"), feed_before, "feed unchanged after conflict")
        self.assertEqual(_receipt_rows(self.state_db), receipts_before, "receipt unchanged after conflict")
        self.assertEqual(self.snapshot_path("road1", "evt-409").read_bytes(), original_bytes)
        self.assertEqual(len(self.registry.registered), 1, "no second registry object")

    def test_same_id_different_metadata_is_409(self) -> None:
        metadata = {"event_id": "evt-meta", "object_type": "car", "created_at": "2026-10-19T11:56:00+00:00"}
        self.post_event(metadata)
        with self.assertRaises(HTTPExceptionStub) as context:
            self.post_event(dict(metadata, speed_kmh=42.0))
        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(len(STORE.read_events(self.state_db, "road1")), 1)

    def test_same_id_different_camera_is_409(self) -> None:
        metadata = {"event_id": "evt-cam", "object_type": "car", "created_at": "2026-10-19T11:55:00+00:00"}
        self.post_event(metadata)
        with self.assertRaises(HTTPExceptionStub) as context:
            self.post_event(metadata, camera_id="cam1")
        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(STORE.read_events(self.state_db, "cam1"), [], "no cross-camera feed row")
        self.assertEqual(
            [receipt["camera_id"] for receipt in _receipt_rows(self.state_db)],
            ["road1"],
            "receipt stays bound to the original camera",
        )

    def test_feed_row_conflict_without_receipt_is_409(self) -> None:
        # Same ID re-delivered with different content after the receipt was
        # pruned but the feed row survives (e.g. long outage, high volume):
        # the retained feed row must still answer with a conflict, not a
        # silent overwrite of history.
        metadata = {"event_id": "evt-row", "object_type": "car", "created_at": "2026-10-19T11:54:00+00:00"}
        self.post_event(metadata)
        with STORE.open_state_db(self.state_db) as connection:
            connection.execute("DELETE FROM event_receipts")
        with self.assertRaises(HTTPExceptionStub) as context:
            self.post_event(dict(metadata, object_type="truck"))
        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(
            [event["object_type"] for event in STORE.read_events(self.state_db, "road1")],
            ["car"],
            "the accepted delivery is never overwritten",
        )

    def test_conflict_redelivery_keeps_published_snapshot_bytes(self) -> None:
        # A 409 must leave the media of the accepted delivery untouched: the
        # conflict path (retained feed row, pruned receipt) currently writes
        # the rejected JPEG via atomic_write_bytes BEFORE deliver_event raises,
        # so the published snapshot of the first delivery gets overwritten.
        # The DB-only assertions above cannot see that — this test reads the
        # real file bytes.
        metadata = {"event_id": "evt-409-media", "object_type": "car", "created_at": "2026-10-19T11:53:30+00:00"}
        original_bytes = b"snapshot-A-published-jpeg"
        rejected_bytes = b"snapshot-B-rejected-jpeg"
        self.post_event(metadata, snapshot=FakeSnapshot(original_bytes))
        target = self.snapshot_path("road1", "evt-409-media")
        self.assertEqual(target.read_bytes(), original_bytes, "baseline: accepted delivery published bytes A")
        with STORE.open_state_db(self.state_db) as connection:
            connection.execute("DELETE FROM event_receipts")
        with self.assertRaises(HTTPExceptionStub) as context:
            self.post_event(
                dict(metadata, object_type="truck"),
                snapshot=FakeSnapshot(rejected_bytes),
            )
        self.assertEqual(context.exception.status_code, 409)
        self.assertEqual(
            target.read_bytes(),
            original_bytes,
            "a rejected (409) re-delivery must not overwrite the published snapshot media",
        )


class AtomicSnapshotTests(RoadEventDeliveryTestCase):
    def test_failed_publish_leaves_no_partial_file_and_retry_succeeds(self) -> None:
        metadata = {"event_id": "evt-atomic", "object_type": "car", "created_at": "2026-10-19T11:53:00+00:00"}
        self.assertIsNone(STORE.find_event_receipt(self.state_db, "evt-atomic"))
        target = self.snapshot_path("road1", "evt-atomic")

        real_replace = os.replace

        def failing_replace(src: Any, dst: Any) -> None:
            raise OSError("simulated storage failure")

        try:
            os.replace = failing_replace
            with self.assertRaises(OSError):
                self.post_event(metadata)
        finally:
            os.replace = real_replace

        self.assertFalse(target.exists(), "a failed publish must not leave a partial snapshot")
        self.assertEqual(self.tmp_leftovers(), [], "orphan tmp must be cleaned after the failed publish")
        self.assertEqual(_receipt_rows(self.state_db), [], "a failed snapshot write must not confirm delivery")
        self.assertEqual(STORE.read_events(self.state_db, "road1"), [], "feed must stay empty after the failure")

        retry = self.post_event(metadata)
        self.assertTrue(retry["ok"])
        self.assertIs(retry.get("duplicate"), False, "the retry is the first confirmed delivery")
        self.assertEqual(target.read_bytes(), b"jpeg-bytes")
        self.assertEqual(len(STORE.read_events(self.state_db, "road1")), 1)

    def test_successful_delivery_publishes_exact_bytes_without_tmp(self) -> None:
        self.post_event({"event_id": "evt-clean", "object_type": "car", "created_at": "2026-10-19T11:52:00+00:00"})
        path = self.snapshot_path("road1", "evt-clean")
        self.assertEqual(path.read_bytes(), b"jpeg-bytes")
        self.assertEqual(self.tmp_leftovers(), [])


class CrashRepairTests(RoadEventDeliveryTestCase):
    def test_retry_completes_missing_feed_and_receipt_after_crash(self) -> None:
        # Crash simulation: the atomic snapshot publish and the registry
        # persist completed, but the process died before the feed/receipt
        # transaction. The retry must complete the missing pieces.
        metadata = {"event_id": "evt-crash", "object_type": "car", "created_at": "2026-10-19T11:52:00+00:00"}
        path = self.snapshot_path("road1", "evt-crash")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"jpeg-crash")
        self.registry.ids.add("evt-crash")  # registry row committed before the crash
        self.assertEqual(STORE.read_events(self.state_db, "road1"), [])
        self.assertEqual(_receipt_rows(self.state_db), [])

        result = self.post_event(metadata)
        self.assertTrue(result["ok"])
        self.assertIs(
            result.get("duplicate"), False,
            "the retry is the first confirmed delivery — the crashed one was never acknowledged",
        )
        self.assertEqual([event["event_id"] for event in STORE.read_events(self.state_db, "road1")], ["evt-crash"])
        self.assertEqual(len(_receipt_rows(self.state_db)), 1)
        self.assertEqual(len(self.registry.registered), 0, "the registry path stays idempotent (no second object)")

    def test_retry_completes_missing_snapshot_after_registry_only_crash(self) -> None:
        metadata = {"event_id": "evt-crash2", "object_type": "car", "created_at": "2026-10-19T11:51:00+00:00"}
        self.registry.ids.add("evt-crash2")  # registry committed, nothing else
        result = self.post_event(metadata)
        self.assertTrue(result["ok"])
        self.assertIs(result.get("duplicate"), False)
        self.assertEqual(self.snapshot_path("road1", "evt-crash2").read_bytes(), b"jpeg-bytes")
        self.assertEqual([event["event_id"] for event in STORE.read_events(self.state_db, "road1")], ["evt-crash2"])
        self.assertEqual(len(_receipt_rows(self.state_db)), 1)


class ConcurrentDuplicateTests(RoadEventDeliveryTestCase):
    def test_concurrent_duplicates_produce_exactly_one_stored_delivery(self) -> None:
        metadata = {"event_id": "evt-race", "object_type": "car", "created_at": "2026-10-19T11:50:00+00:00"}
        results: List[Dict[str, Any]] = []
        errors: List[BaseException] = []
        barrier = threading.Barrier(8)

        def deliver() -> None:
            try:
                barrier.wait(timeout=10)
                results.append(
                    asyncio.run(
                        self.post(
                            "road1",
                            metadata=json.dumps(metadata),
                            snapshot=FakeSnapshot(),
                            authorization=None,
                        )
                    )
                )
            except BaseException as error:  # pragma: no cover - failure path
                errors.append(error)

        threads = [threading.Thread(target=deliver) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(errors, [], "no concurrent request may fail")
        stored = [result for result in results if result.get("duplicate") is False]
        duplicates = [result for result in results if result.get("duplicate") is True]
        self.assertEqual(len(stored), 1, "exactly one request performs the stored delivery")
        self.assertEqual(len(duplicates), 7, "every other concurrent request is served the duplicate success")
        self.assertEqual(len(STORE.read_events(self.state_db, "road1")), 1, "one feed row total")
        self.assertEqual(len(_receipt_rows(self.state_db)), 1, "one receipt")
        self.assertEqual(len(self.registry.registered), 1, "one registry object")


class SweepOrphanTmpTests(RoadEventDeliveryTestCase):
    def _load_sweep(self) -> Any:
        class _EmptyCursor:
            def fetchall(self) -> List[Any]:
                return []

            def __iter__(self) -> Any:
                return iter([])

        class _EmptyObjectsDb:
            def execute(self, *args: Any, **kwargs: Any) -> "_EmptyCursor":
                return _EmptyCursor()

            def __enter__(self) -> "_EmptyObjectsDb":
                return self

            def __exit__(self, *args: Any) -> bool:
                return False

        namespace: Dict[str, Any] = {
            "sys": sys,
            "time": time,
            "Path": Path,
            "print": print,
            "EVENTS_MEDIA_DIR": self.media_dir,
            "EVENTS_SWEEP_INTERVAL_SECONDS": 3600,
            "_events_sweep_state": {"last": 0.0},
            "EVENTS_MEDIA_GRACE_SECONDS": 24 * 3600,
            "open_objects_db": lambda: _EmptyObjectsDb(),
        }
        tree = ast.parse(ANALYTICS_FILE.read_text(encoding="utf-8-sig"), filename=str(ANALYTICS_FILE))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "sweep_events_media":
                cloned = copy.deepcopy(node)
                cloned.decorator_list = []
                module = ast.Module(body=[cloned], type_ignores=[])
                ast.fix_missing_locations(module)
                exec(compile(module, str(ANALYTICS_FILE), "exec"), namespace)
                return namespace["sweep_events_media"]
        raise AssertionError("sweep_events_media not found")

    def _touch(self, name: str, age_seconds: float, now: float) -> Path:
        path = self.media_dir / name
        path.write_bytes(b"x")
        stamp = now - age_seconds
        os.utime(path, (stamp, stamp))
        return path

    def test_sweep_cleans_orphan_tmp_and_keeps_everything_else(self) -> None:
        sweep = self._load_sweep()

        now = 1_800_000_000.0
        self._touch("old-orphan.jpg", 25 * 3600, now)  # pinned: unreferenced old jpeg is swept
        stale_tmp = self._touch("road1-evt-x.jpg.deadbeef.tmp", 25 * 3600, now)  # interrupted atomic write
        fresh_tmp = self._touch("road1-evt-y.jpg.cafe.tmp", 60, now)  # in-flight upload tmp
        notes = self._touch("notes.txt", 48 * 3600, now)  # pinned: non-media names untouched

        deleted = sweep(force=True, now=now)

        self.assertGreaterEqual(deleted, 2)
        self.assertFalse((self.media_dir / "old-orphan.jpg").exists())
        self.assertFalse(stale_tmp.exists(), "orphan tmp from an interrupted write must be swept")
        self.assertTrue(fresh_tmp.exists(), "an in-flight tmp is younger than the grace window")
        self.assertTrue(notes.exists())


class LegacyResponseCompatibilityTests(RoadEventDeliveryTestCase):
    def test_event_payload_shape_is_unchanged_and_response_stays_ok(self) -> None:
        result = self.post_event(
            {
                "event_id": "evt-shape",
                "object_type": "car",
                "track_id": 7,
                "confidence": 0.9,
                "created_at": "2026-10-19T11:49:00+00:00",
            }
        )
        self.assertTrue(result["ok"])
        self.assertIn("event", result)
        event = result["event"]
        self.assertEqual(event["event_id"], "evt-shape")
        self.assertEqual(event["camera_id"], "road1")
        self.assertEqual(event["analytics_profile"], "road-v1")
        self.assertEqual(event["domain"], "road")
        self.assertEqual(event["event_schema"], "sea_speed_vehicle_event_v1")
        self.assertEqual(event["telemetry_schema"], "sea_speed_telemetry_v1")
        self.assertEqual(event["snapshot_url"], "/sea-speed/media/events/road1-evt-shape.jpg")
        self.assertTrue(self.snapshot_path("road1", "evt-shape").is_file())
        # The stored receipt response equals the delivered event exactly, so
        # future duplicates reproduce today's payload byte-for-byte (parsed).
        receipt = _receipt_rows(self.state_db)[0]
        self.assertEqual(json.loads(receipt["response_event_json"]), event)

    def test_water_camera_events_ingest_through_the_same_path(self) -> None:
        result = self.post_event(
            {"event_id": "w-1", "object_type": "vessel", "created_at": "2026-10-19T11:48:00+00:00"},
            camera_id="cam1",
        )
        self.assertTrue(result["ok"])
        self.assertIs(result.get("duplicate"), False)
        self.assertEqual([event["event_id"] for event in STORE.read_events(self.state_db, "cam1")], ["w-1"])


if __name__ == "__main__":
    unittest.main()
