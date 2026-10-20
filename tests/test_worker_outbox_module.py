"""Issue #537 wave 2 — worker_outbox module-level guards.

Module invariants of worker/worker_outbox.py per specs/537-wave2-worker-outbox
(plan D-102/D-103, FR-002/FR-006, RISK-002):

(a) Import allowlist guard in the style of tests/test_worker_transport_module.py:
    every import in the module stays within the amended allowlist — stdlib
    json, time, pathlib, hashlib, sqlite3, threading, os, random + guarded
    requests (orchestrator ruling 2026-10-21) — and the forbidden offline/
    process layers (cv2/numpy/ultralytics/av/subprocess/socket) appear nowhere.
(b) The requests import is GUARDED (try/except with a None fallback): the
    persistence layer must work without requests installed.
(c) The allowlist is declared in the module docstring (guarded-import test
    convention of the worker_*.py modules).
(d) Explicit schema init at outbox OPEN (wave-1 "lazy migration" gotcha,
    KB INFRASTRUCTURE.md gotcha #34): a fresh file has both tables and the
    meta counters right after construction — before any enqueue and without
    ever starting the publisher thread.
(e) WAL mode active on a fresh open.
(f) event_id UNIQUE constraint (one logical object per event id).
(g) SEA_SPEED_OUTBOX_DB override honored at the entrypoint seam (FR-002):
    the outbox file is created at the override path, not the default.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
OUTBOX = ROOT / "worker" / "worker_outbox.py"
ENTRYPOINT = ROOT / "worker/ubuntu_worker_entrypoint.py"
SOURCE_COMMIT = "0123456789abcdef0123456789abcdef01234567"

# Amended import allowlist for worker_outbox (D-102, orchestrator ruling
# 2026-10-21): stdlib json, time, pathlib, hashlib, sqlite3, threading, os,
# random + guarded requests. os: SEA_SPEED_OUTBOX_DB + FR-006 env derivation;
# random: FR-005 default jitter source.
OUTBOX_IMPORT_ALLOWLIST = frozenset(
    {
        "hashlib",
        "json",
        "os",
        "pathlib",
        "random",
        "requests",
        "sqlite3",
        "threading",
        "time",
    }
)

FORBIDDEN_OUTBOX_IMPORTS = frozenset(
    {"cv2", "numpy", "ultralytics", "av", "subprocess", "socket"}
)


def _module_tree() -> ast.Module:
    return ast.parse(OUTBOX.read_text(encoding="utf-8-sig"), filename=str(OUTBOX))


def _all_import_roots(tree: ast.Module) -> set[str]:
    """Every import root anywhere in the module (stricter than top-level only:
    function-local imports must not smuggle extra dependencies either)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def load_outbox_module():
    worker_dir = str(ROOT / "worker")
    if worker_dir not in sys.path:
        sys.path.insert(0, worker_dir)
    import worker_outbox

    return worker_outbox


class WorkerOutboxImportAllowlistTests(unittest.TestCase):
    def test_outbox_module_imports_stay_within_allowlist(self) -> None:
        imported = _all_import_roots(_module_tree())
        self.assertEqual(
            sorted(imported - OUTBOX_IMPORT_ALLOWLIST),
            [],
            "worker_outbox gained an import outside the amended D-102 allowlist",
        )

    def test_outbox_module_has_no_forbidden_layer_imports(self) -> None:
        imported = _all_import_roots(_module_tree())
        self.assertEqual(
            sorted(imported & FORBIDDEN_OUTBOX_IMPORTS),
            [],
            "outbox persistence/delivery must not touch cv2/numpy/ultralytics/av/"
            "subprocess/socket",
        )

    def test_requests_import_is_guarded_with_none_fallback(self) -> None:
        # Persistence must work without requests installed: the import lives in
        # a top-level try/except whose handler binds requests = None.
        tree = _module_tree()
        guarded = False
        for node in tree.body:
            if not isinstance(node, ast.Try):
                continue
            body_imports = {
                alias.name.split(".")[0]
                for stmt in node.body
                if isinstance(stmt, ast.Import)
                for alias in stmt.names
            }
            if "requests" not in body_imports:
                continue
            for handler in node.handlers:
                assignments = {
                    target.id
                    for stmt in ast.walk(handler)
                    if isinstance(stmt, ast.Assign)
                    for target in stmt.targets
                    if isinstance(target, ast.Name)
                }
                if "requests" in assignments:
                    guarded = True
        self.assertTrue(
            guarded,
            "requests must be imported in a guarded try/except with a None fallback",
        )

    def test_allowlist_declared_in_module_docstring(self) -> None:
        docstring = ast.get_docstring(_module_tree()) or ""
        self.assertIn("Import allowlist", docstring)
        for name in sorted(OUTBOX_IMPORT_ALLOWLIST):
            self.assertIn(name, docstring, f"allowlist entry {name} not declared")


class WorkerOutboxSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.db_path = self.tmp / "road-worker-outbox.sqlite3"
        self.snapshot = self.tmp / "event.jpg"
        self.snapshot.write_bytes(b"\xff\xd8module-probe\xff\xd9")

    def test_schema_created_explicitly_at_open_before_any_enqueue(self) -> None:
        """D-103/RISK-002 regression: a fresh open creates the schema eagerly.

        Right after construction — no enqueue, no publisher thread — an
        independent connection already sees both tables and the meta counters.
        (The wave-1 'lazy migration' gotcha: schema must never be created from
        a publisher-thread path.)
        """
        self.assertFalse(self.db_path.exists())
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        self.addCleanup(outbox.close)
        self.assertIsNone(outbox._thread, "construction must not start the publisher")
        with sqlite3.connect(self.db_path) as conn:
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
            }
            meta = dict(conn.execute("SELECT key, value FROM outbox_meta"))
        self.assertIn("outbox_events", tables)
        self.assertIn("outbox_meta", tables)
        self.assertEqual(meta.get("schema_version"), "1")
        for counter in (
            "outbox_send_errors_total",
            "outbox_retries_total",
            "outbox_accept_errors_total",
        ):
            self.assertEqual(meta.get(counter), "0")
        # the empty schema is immediately usable: pending_count works pre-enqueue
        self.assertEqual(outbox.pending_count(), 0)

    def test_wal_mode_active_on_fresh_open(self) -> None:
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        self.addCleanup(outbox.close)
        with sqlite3.connect(self.db_path) as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode.lower(), "wal")

    def test_event_id_unique_constraint_rejects_duplicates(self) -> None:
        """FR-001/D-109: one logical object per event_id — a duplicate enqueue
        fails on the UNIQUE constraint and the first row stays intact."""
        mod = load_outbox_module()
        outbox = mod.WorkerOutbox(self.db_path, jitter_function=lambda: 0.0)
        self.addCleanup(outbox.close)
        metadata = json.dumps({"event_id": "evt-unique", "camera_id": "road1"})
        self.assertIs(outbox.enqueue("evt-unique", metadata, self.snapshot), True)
        with self.assertRaises(sqlite3.IntegrityError):
            outbox.enqueue("evt-unique", metadata, self.snapshot)
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT metadata FROM outbox_events WHERE event_id = 'evt-unique'"
            ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], metadata)


class WorkerOutboxSeamEnvTests(unittest.TestCase):
    """SEA_SPEED_OUTBOX_DB is read at the entrypoint seam (FR-002/D-103); the
    loader follows tests/test_ubuntu_worker_runtime_provenance.py:17-60."""

    def load_entrypoint(self):
        worker = types.ModuleType("hls_motion_yolo_worker_events")
        worker.start_media_reader = lambda av_module=None: None
        worker.post_state = lambda metadata, overlay_path: "state-ok"
        worker.post_event = lambda metadata, snapshot_path: "event-ok"
        profiles = types.ModuleType("analytics_profiles")
        profiles.get_profile = lambda _name: types.SimpleNamespace(
            sample_fps=5.0,
            model_name="models/yolo26x.pt",
            tracker="bytetrack.yaml",
            image_size=960,
            confidence=0.15,
            name="road-v1",
        )
        load_outbox_module()  # worker/ on sys.path for the seam's lazy import
        spec = importlib.util.spec_from_file_location(
            f"entrypoint_outbox_env_{id(self)}", ENTRYPOINT
        )
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(
            sys.modules,
            {
                "analytics_profiles": profiles,
                "hls_motion_yolo_worker_events": worker,
                "numpy": types.ModuleType("numpy"),
            },
        ):
            spec.loader.exec_module(module)
        return module

    def test_sea_speed_outbox_db_override_honored(self) -> None:
        """FR-002/AC-001: with SEA_SPEED_OUTBOX_DB set, post_event persists to
        exactly that file; the default (cwd) file is never created."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            override_db = root / "operator-recovery" / "outbox.sqlite3"
            override_db.parent.mkdir(parents=True)
            snapshot = root / "event.jpg"
            snapshot.write_bytes(b"\xff\xd8override-probe\xff\xd9")
            with mock.patch.dict(
                os.environ,
                {
                    "SEA_SPEED_SOURCE_COMMIT": SOURCE_COMMIT,
                    "SEA_SPEED_OUTBOX_DB": str(override_db),
                },
                clear=False,
            ):
                os.environ.pop("SEA_SPEED_SYNC_PUBLISH", None)
                entrypoint = self.load_entrypoint()
                try:
                    self.assertIs(
                        entrypoint.post_event(
                            {"event_id": "evt-override", "camera_id": "road1"}, snapshot
                        ),
                        True,
                    )
                    self.assertTrue(override_db.is_file())
                    with sqlite3.connect(override_db) as conn:
                        rows = conn.execute(
                            "SELECT event_id, snapshot_bytes FROM outbox_events"
                        ).fetchall()
                    self.assertEqual(rows, [("evt-override", b"\xff\xd8override-probe\xff\xd9")])
                finally:
                    entrypoint._close_outbox()
            # the seam must not have written a default-name file anywhere near cwd
            self.assertFalse(Path("road-worker-outbox.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
