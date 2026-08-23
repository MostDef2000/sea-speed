from __future__ import annotations

import ast
import copy
import json
import os
import sqlite3
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "api" / "app" / "main.py"


def load_functions(names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8-sig"), filename=str(SOURCE))
    selected = []
    found = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            cloned = copy.deepcopy(node)
            cloned.decorator_list = (
                copy.deepcopy(node.decorator_list)
                if node.name in {"open_objects_db", "open_passages_db"}
                else []
            )
            selected.append(cloned)
            found.add(node.name)
    missing = names - found
    if missing:
        raise AssertionError(f"missing API functions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace


def retention_namespace(temp_dir: str) -> dict[str, Any]:
    return {
        "Any": Any, "Dict": Dict, "List": List, "Optional": Optional, "Path": Path,
        "json": json, "sqlite3": sqlite3, "time": time, "os": os,
        "contextmanager": contextmanager, "print": print,
        "OBJECTS_RETENTION_LIMIT": 100,
        "PASSAGES_RETENTION_LIMIT": 300,
        "EVENTS_MEDIA_GRACE_SECONDS": 24 * 3600,
        "EVENTS_SWEEP_INTERVAL_SECONDS": 3600,
        "_events_sweep_state": {"last": 0.0},
        "EVENTS_MEDIA_DIR": Path(temp_dir) / "media" / "events",
        "OBJECTS_DB_FILE": Path(temp_dir) / "objects.sqlite3",
        "PASSAGES_DB_FILE": Path(temp_dir) / "passages.sqlite3",
        "now_iso": lambda: "2026-08-23T00:00:00+00:00",
    }


RETENTION_FUNCTIONS = {
    "open_objects_db", "prune_objects_registry", "initialize_objects_db",
    "optional_float", "optional_int", "persist_object_event", "stable_object_id",
    "sweep_events_media", "_delete_passage_mirrors", "reconcile_passage_mirrors",
    "open_passages_db", "prune_water_passages", "initialize_water_passages_db",
    "persist_passage_object",
}


def seed_event(event_id: str, domain: str, minute: int) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "camera_id": "cam1" if domain == "water" else "road1",
        "domain": domain,
        "created_at": f"2026-08-23T10:{minute // 60:02d}:{minute % 60:02d}+00:00",
        "class_name": "vessel" if domain == "water" else "car",
        "snapshot_url": f"/sea-speed/media/events/{event_id}.jpg",
    }


class PerDomainRetentionTests(unittest.TestCase):
    def test_per_domain_retention_keeps_100_each(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = retention_namespace(temp_dir)
            load_functions(RETENTION_FUNCTIONS, ns)
            ns["initialize_objects_db"]()
            for index in range(150):
                ns["persist_object_event"](seed_event(f"w-{index:03d}", "water", index))
                ns["persist_object_event"](seed_event(f"r-{index:03d}", "road", index))
            with ns["open_objects_db"]() as connection:
                counts = dict(
                    connection.execute("SELECT domain, COUNT(*) FROM objects GROUP BY domain").fetchall()
                )
                newest_water = connection.execute(
                    "SELECT object_id FROM objects WHERE domain='water' "
                    "ORDER BY detected_at DESC LIMIT 1"
                ).fetchone()[0]
                oldest_water = connection.execute(
                    "SELECT object_id FROM objects WHERE domain='water' "
                    "ORDER BY detected_at ASC LIMIT 1"
                ).fetchone()[0]
            self.assertEqual(counts.get("water"), 100)
            self.assertEqual(counts.get("road"), 100)
            self.assertEqual(newest_water, "w-149")
            self.assertEqual(oldest_water, "w-050")

    def test_prune_returns_evicted_snapshot_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = retention_namespace(temp_dir)
            ns["OBJECTS_RETENTION_LIMIT"] = 1
            load_functions({"open_objects_db", "prune_objects_registry", "initialize_objects_db"}, ns)
            ns["initialize_objects_db"]()
            with ns["open_objects_db"]() as connection:
                for index in range(3):
                    connection.execute(
                        """INSERT INTO objects (
                            object_id, camera_id, detected_at, class_name, snapshot_url,
                            original_event_json, created_at, updated_at
                        ) VALUES (?, 'cam1', ?, 'vessel', ?, '{}', ?, ?)""",
                        (f"x-{index}", f"2026-08-23T10:{index:02d}:00+00:00",
                         f"/sea-speed/media/events/x-{index}.jpg",
                         f"2026-08-23T10:{index:02d}:00+00:00",
                         f"2026-08-23T10:{index:02d}:00+00:00"),
                    )
                evicted = ns["prune_objects_registry"](connection)
            self.assertEqual(sorted(evicted), [f"/sea-speed/media/events/x-{i}.jpg" for i in (0, 1)])


class EventsMediaSweepTests(unittest.TestCase):
    def _prepare(self, temp_dir: str) -> tuple[dict[str, Any], Path]:
        ns = retention_namespace(temp_dir)
        media_dir = ns["EVENTS_MEDIA_DIR"]
        media_dir.mkdir(parents=True, exist_ok=True)
        load_functions(
            {"open_objects_db", "prune_objects_registry", "initialize_objects_db", "sweep_events_media"},
            ns,
        )
        ns["initialize_objects_db"]()
        return ns, media_dir

    def _touch(self, media_dir: Path, name: str, age_seconds: float, now: float) -> None:
        path = media_dir / name
        path.write_bytes(b"jpg")
        stamp = now - age_seconds
        os.utime(path, (stamp, stamp))

    def test_sweep_deletes_unreferenced_old_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns, media_dir = self._prepare(temp_dir)
            now = 1_800_000_000
            self._touch(media_dir, "old-orphan.jpg", 25 * 3600, now)
            with ns["open_objects_db"]() as connection:
                connection.execute(
                    """INSERT INTO objects (
                        object_id, camera_id, detected_at, class_name, snapshot_url,
                        original_event_json, created_at, updated_at
                    ) VALUES ('live', 'cam1', '2026-08-23T10:00:00+00:00', 'vessel',
                              '/sea-speed/media/events/live.jpg', '{}',
                              '2026-08-23T10:00:00+00:00', '2026-08-23T10:00:00+00:00')"""
                )
            self._touch(media_dir, "live.jpg", 25 * 3600, now)
            deleted = ns["sweep_events_media"](force=True, now=now)
            self.assertEqual(deleted, 1)
            self.assertFalse((media_dir / "old-orphan.jpg").exists())
            self.assertTrue((media_dir / "live.jpg").exists())

    def test_sweep_keeps_recent_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns, media_dir = self._prepare(temp_dir)
            now = 1_800_000_000
            self._touch(media_dir, "fresh-orphan.jpg", 3600, now)
            deleted = ns["sweep_events_media"](force=True, now=now)
            self.assertEqual(deleted, 0)
            self.assertTrue((media_dir / "fresh-orphan.jpg").exists())

    def test_media_sweep_ignores_unsafe_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns, media_dir = self._prepare(temp_dir)
            now = 1_800_000_000
            subdir = media_dir / "nested.jpg"
            subdir.mkdir()
            (subdir / "inner.jpg").write_bytes(b"jpg")
            note = media_dir / "notes.txt"
            note.write_bytes(b"text")
            self._touch(media_dir, "notes.txt", 48 * 3600, now)
            self._touch(subdir, "inner.jpg", 48 * 3600, now)
            deleted = ns["sweep_events_media"](force=True, now=now)
            self.assertEqual(deleted, 0)
            self.assertTrue(subdir.exists())
            self.assertTrue((subdir / "inner.jpg").exists())
            self.assertTrue(note.exists())

    def test_sweep_throttled_to_hourly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns, media_dir = self._prepare(temp_dir)
            now = 1_800_000_000
            self._touch(media_dir, "old-a.jpg", 30 * 3600, now)
            first = ns["sweep_events_media"](force=False, now=now)
            self._touch(media_dir, "old-b.jpg", 30 * 3600, now + 60)
            second = ns["sweep_events_media"](force=False, now=now + 60)
            third = ns["sweep_events_media"](force=False, now=now + 3601)
            self.assertEqual(first, 1)
            self.assertEqual(second, 0)
            self.assertEqual(third, 1)
            self.assertFalse((media_dir / "old-b.jpg").exists())


class PassageMirrorSyncTests(unittest.TestCase):
    def _prepare(self, temp_dir: str) -> dict[str, Any]:
        ns = retention_namespace(temp_dir)
        load_functions(RETENTION_FUNCTIONS, ns)
        ns["initialize_objects_db"]()
        ns["initialize_water_passages_db"]()
        return ns

    def _insert_passage(self, ns: dict[str, Any], passage_id: str) -> None:
        with ns["open_passages_db"]() as connection:
            connection.execute(
                """
                INSERT INTO water_passages (
                    passage_id, camera_id, class_name, status, started_at,
                    last_seen_at, completed_at, track_fragments_json, confidence,
                    direction, speed_status, speed_kmh, snapshot_url,
                    measurement_meta_json, observation_count, created_at, updated_at
                ) VALUES (?, 'cam1', 'vessel', 'completed', '2026-08-23T09:00:00+00:00',
                          '2026-08-23T09:01:00+00:00', NULL, '[]', 0.8, NULL,
                          'measured', 12.0, '/sea-speed/media/passages/p.jpg',
                          '{}', 3, '2026-08-23T09:00:00+00:00', '2026-08-23T09:01:00+00:00')
                """,
                (passage_id,),
            )

    def test_passage_prune_removes_mirror_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = self._prepare(temp_dir)
            self._insert_passage(ns, "gone-1")
            self._insert_passage(ns, "gone-2")
            self._insert_passage(ns, "kept")
            ns["persist_passage_object"]({"passage_id": "gone-1"})
            ns["persist_passage_object"]({"passage_id": "gone-2"})
            ns["persist_passage_object"]({"passage_id": "kept"})
            with ns["open_passages_db"]() as connection:
                ns["prune_water_passages"](connection, target_limit=2)
            with ns["open_objects_db"]() as connection:
                remaining = {
                    row[0] for row in connection.execute("SELECT object_id FROM objects")
                }
            self.assertNotIn("passage-gone-1", remaining)
            self.assertIn("passage-kept", remaining)

    def test_reconciliation_removes_orphan_mirrors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = self._prepare(temp_dir)
            self._insert_passage(ns, "alive")
            ns["persist_passage_object"]({"passage_id": "alive"})
            ns["persist_passage_object"]({"passage_id": "orphan"})
            removed = ns["reconcile_passage_mirrors"]()
            with ns["open_objects_db"]() as connection:
                remaining = {
                    row[0] for row in connection.execute("SELECT object_id FROM objects")
                }
            self.assertEqual(removed, 1)
            self.assertNotIn("passage-orphan", remaining)
            self.assertIn("passage-alive", remaining)


if __name__ == "__main__":
    unittest.main()
