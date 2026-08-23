from __future__ import annotations

import ast
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "api" / "app" / "main.py"
REGISTRY_PAGE = ROOT / "frontend" / "sea-speed" / "objects" / "index.html"


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


def unified_namespace(temp_dir: str) -> dict[str, Any]:
    return {
        "Any": Any, "Dict": Dict, "List": List, "Optional": Optional, "Path": Path,
        "json": json, "hashlib": hashlib, "sqlite3": sqlite3,
        "contextmanager": contextmanager, "print": print,
        "OBJECTS_RETENTION_LIMIT": 100,
        "PASSAGES_RETENTION_LIMIT": 500,
        "OBJECTS_DB_FILE": Path(temp_dir) / "objects.sqlite3",
        "PASSAGES_DB_FILE": Path(temp_dir) / "passages.sqlite3",
        "now_iso": lambda: "2026-08-23T00:00:00+00:00",
    }


MIRROR_FUNCTIONS = {
    "open_objects_db", "prune_objects_registry", "initialize_objects_db",
    "optional_float", "optional_int", "persist_passage_object",
    "open_passages_db", "prune_water_passages", "initialize_water_passages_db",
    "import_existing_passages",
}


def passage(passage_id: str = "p1", **overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "passage_id": passage_id,
        "camera_id": "cam1",
        "class_name": "vessel",
        "status": "tracking",
        "started_at": "2026-08-23T09:00:00+00:00",
        "last_seen_at": "2026-08-23T09:00:20+00:00",
        "completed_at": None,
        "track_fragments": [7],
        "confidence": 0.82,
        "direction": "left_to_right",
        "speed_status": "unknown",
        "speed_kmh": None,
        "snapshot_url": "/sea-speed/media/passages/p1.jpg",
        "observation_count": 2,
    }
    base.update(overrides)
    return base


class PassageMirrorTests(unittest.TestCase):
    def test_persists_water_passage_into_objects_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = unified_namespace(temp_dir)
            load_functions(MIRROR_FUNCTIONS, ns)
            ns["initialize_objects_db"]()
            self.assertTrue(ns["persist_passage_object"](passage()))
            with ns["open_objects_db"]() as connection:
                row = connection.execute(
                    "SELECT * FROM objects WHERE object_id='passage-p1'"
                ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["camera_id"], "cam1")
            self.assertEqual(row["domain"], "water")
            self.assertEqual(row["analytics_profile"], "water-v1")
            self.assertEqual(row["class_name"], "vessel")
            self.assertEqual(row["track_id"], 7)
            self.assertEqual(row["detected_at"], "2026-08-23T09:00:00+00:00")
            self.assertEqual(row["status"], "new")
            mirror = json.loads(row["original_event_json"])
            self.assertEqual(
                mirror["registry_mirror_schema"],
                "sea_speed_water_passage_registry_mirror_v1",
            )
            self.assertEqual(mirror["passage"]["passage_id"], "p1")

    def test_repeated_updates_refresh_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = unified_namespace(temp_dir)
            load_functions(MIRROR_FUNCTIONS, ns)
            ns["initialize_objects_db"]()
            ns["persist_passage_object"](passage(speed_kmh=None, speed_status="tracking"))
            ns["persist_passage_object"](
                passage(status="completed", speed_kmh=14.7, speed_status="measured", confidence=0.9)
            )
            with ns["open_objects_db"]() as connection:
                count = connection.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
                row = connection.execute(
                    "SELECT * FROM objects WHERE object_id='passage-p1'"
                ).fetchone()
            self.assertEqual(count, 1)
            self.assertEqual(row["speed_kmh"], 14.7)
            self.assertEqual(row["confidence"], 0.9)
            self.assertEqual(row["class_name"], "vessel")

    def test_operator_fields_survive_mirroring(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = unified_namespace(temp_dir)
            load_functions(MIRROR_FUNCTIONS, ns)
            ns["initialize_objects_db"]()
            ns["persist_passage_object"](passage())
            with ns["open_objects_db"]() as connection:
                connection.execute(
                    "UPDATE objects SET status='reviewed', comment='op note' "
                    "WHERE object_id='passage-p1'"
                )
            ns["persist_passage_object"](passage(speed_kmh=9.5))
            with ns["open_objects_db"]() as connection:
                row = connection.execute(
                    "SELECT * FROM objects WHERE object_id='passage-p1'"
                ).fetchone()
            self.assertEqual((row["status"], row["comment"]), ("reviewed", "op note"))
            self.assertEqual(row["speed_kmh"], 9.5)

    def test_startup_backfill_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = unified_namespace(temp_dir)
            load_functions(MIRROR_FUNCTIONS, ns)
            ns["initialize_objects_db"]()
            ns["initialize_water_passages_db"]()
            with ns["open_passages_db"]() as connection:
                for index in range(3):
                    item = passage(f"backfill-{index}")
                    connection.execute(
                        """
                        INSERT INTO water_passages (
                            passage_id, camera_id, class_name, status, started_at,
                            last_seen_at, completed_at, track_fragments_json, confidence,
                            direction, speed_status, speed_kmh, snapshot_url,
                            measurement_meta_json, observation_count, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?, ?)
                        """,
                        (
                            item["passage_id"], item["camera_id"], item["class_name"],
                            item["status"], item["started_at"], item["last_seen_at"],
                            item["completed_at"], json.dumps(item["track_fragments"]),
                            item["confidence"], item["direction"], item["speed_status"],
                            item["speed_kmh"], item["snapshot_url"],
                            item["observation_count"], item["started_at"], item["last_seen_at"],
                        ),
                    )
            first = ns["import_existing_passages"]()
            ns["import_existing_passages"]()
            with ns["open_objects_db"]() as connection:
                rows = connection.execute(
                    "SELECT object_id FROM objects WHERE object_id LIKE 'passage-backfill-%'"
                ).fetchall()
                total = connection.execute("SELECT COUNT(*) FROM objects").fetchone()[0]
            self.assertEqual(first, 3)
            self.assertEqual(len(rows), 3)
            self.assertEqual(total, 3)

    def test_domain_water_filter_returns_passages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = unified_namespace(temp_dir)
            load_functions(MIRROR_FUNCTIONS | {"build_objects_where"}, ns)
            ns["initialize_objects_db"]()
            ns["persist_passage_object"](passage("w1"))
            where, params = ns["build_objects_where"](
                camera_id="cam1", domain="water", date_from=None, date_to=None,
                class_name=None, status=None, speed_min=None, speed_max=None,
                search=None, include_deleted=False,
            )
            with ns["open_objects_db"]() as connection:
                rows = connection.execute(
                    f"SELECT object_id FROM objects WHERE {where}", params
                ).fetchall()
            self.assertEqual([row["object_id"] for row in rows], ["passage-w1"])

    def test_mirror_failure_is_isolated_from_caller(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = unified_namespace(temp_dir)
            load_functions({"persist_passage_object"}, ns)
            ns["optional_int"] = lambda value: None
            ns["optional_float"] = lambda value: None

            def broken_connection():
                raise RuntimeError("db unavailable")

            ns["open_objects_db"] = broken_connection
            with self.assertRaises(RuntimeError):
                ns["persist_passage_object"](passage())


class RegistryPageContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.page = REGISTRY_PAGE.read_text(encoding="utf-8")

    def test_domain_selector_enabled_with_switch_handler(self) -> None:
        self.assertRegex(self.page, r'<select id="domainInput"[^>]*(?<!disabled)>')
        self.assertIn('domainInput.addEventListener("change"', self.page)
        self.assertIn("function setRegistryScope(", self.page)
        self.assertIn("applyRegistryScope();loadObjects()", self.page)

    def test_referrer_pre_selection_preserved(self) -> None:
        self.assertIn('referrerPath.startsWith("/sea-speed/road/")?"road":"water"', self.page)
        self.assertIn('hasOwnProperty.call(REGISTRY_SCOPES,requestedScope)', self.page)

    def test_single_registry_nav_link(self) -> None:
        self.assertNotIn('objects/?scope=water">', self.page.split("<nav")[1].split("</nav>")[0])
        self.assertNotIn('objects/?scope=road">', self.page.split("<nav")[1].split("</nav>")[0])
        self.assertIn('href="/sea-speed/objects/">Реестр объектов</a>', self.page)


if __name__ == "__main__":
    unittest.main()
