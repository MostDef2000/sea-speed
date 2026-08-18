from __future__ import annotations

import ast
import copy
import json
import re
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
WORKER_SOURCE = ROOT / "worker" / "hls_motion_yolo_worker_events.py"
API_SOURCE = ROOT / "api" / "app" / "main.py"
FRONTEND_SOURCE = ROOT / "frontend" / "sea-speed" / "index.html"
ARTIFACT_SOURCE = ROOT / "scripts" / "quality" / "build_exact_artifacts.py"

import sys
sys.path.insert(0, str(ROOT / "worker"))
from water_passage import MeasurementResult, SpeedEstimator, TwoGateSpeedEstimator, WaterPassageEngine


class HTTPExceptionStub(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def load_api_functions(names: set[str], namespace: dict[str, Any]) -> dict[str, Any]:
    tree = ast.parse(API_SOURCE.read_text(encoding="utf-8-sig"), filename=str(API_SOURCE))
    selected = []
    found = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in names:
            cloned = copy.deepcopy(node)
            cloned.decorator_list = copy.deepcopy(node.decorator_list) if node.name in {"open_passages_db"} else []
            selected.append(cloned)
            found.add(node.name)
    missing = names - found
    if missing:
        raise AssertionError(f"missing API functions: {sorted(missing)}")
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, str(API_SOURCE), "exec"), namespace)
    return namespace


def det(track_id: int, y: float, confidence: float = 0.8, x: float = 50.0) -> Dict[str, object]:
    return {
        "track_id": track_id,
        "class_name": "vessel",
        "bbox_xyxy": [x - 10, y - 10, x + 10, y],
        "confidence": confidence,
    }


class PassageEngineTests(unittest.TestCase):
    def make_estimator(self) -> TwoGateSpeedEstimator:
        return TwoGateSpeedEstimator([(0, 20), (100, 20)], [(0, 80), (100, 80)], 60.0, True)

    def test_short_bytetrack_split_stitches_to_one_passage(self) -> None:
        ids = iter(["P-TEST-0001", "P-TEST-0002"])
        engine = WaterPassageEngine(
            self.make_estimator,
            id_factory=lambda _ts: next(ids),
            stitch_window_sec=3,
            stitch_distance_px=50,
            passage_end_gap_sec=8,
        )
        first = engine.update([det(11, 30)], 1.0)[-1]["passage"]
        second = engine.update([det(22, 35)], 2.0)[-1]["passage"]
        self.assertEqual(first["passage_id"], second["passage_id"])
        self.assertEqual(second["track_fragments"], [11, 22])
        self.assertEqual(engine.active_count, 1)

    def test_new_track_after_stitch_window_creates_new_passage(self) -> None:
        ids = iter(["P-TEST-0001", "P-TEST-0002"])
        engine = WaterPassageEngine(
            self.make_estimator,
            id_factory=lambda _ts: next(ids),
            stitch_window_sec=2,
            stitch_distance_px=50,
            passage_end_gap_sec=8,
        )
        first = engine.update([det(1, 30)], 1.0)[-1]["passage"]
        second = engine.update([det(2, 32)], 4.0)[-1]["passage"]
        self.assertNotEqual(first["passage_id"], second["passage_id"])
        self.assertEqual(engine.active_count, 2)

    def test_two_gate_strategy_measures_both_directions(self) -> None:
        a_to_b = self.make_estimator()
        for ts, y in ((0.0, 10), (1.0, 30), (2.0, 70), (3.0, 90)):
            result = a_to_b.update(self._obs(ts, y))
        self.assertEqual(result.speed_status, "measured")
        self.assertEqual(result.speed_method, "two_gate")
        self.assertEqual(result.direction, "A->B")
        self.assertGreater(result.speed_kmh or 0, 0)

        b_to_a = self.make_estimator()
        for ts, y in ((0.0, 90), (1.0, 70), (2.0, 30), (3.0, 10)):
            reverse = b_to_a.update(self._obs(ts, y))
        self.assertEqual(reverse.speed_status, "measured")
        self.assertEqual(reverse.direction, "B->A")
        self.assertAlmostEqual(reverse.speed_kmh or 0, result.speed_kmh or 0, places=6)

    def test_incomplete_gate_stays_null_speed(self) -> None:
        estimator = self.make_estimator()
        estimator.update(self._obs(0.0, 10))
        estimator.update(self._obs(1.0, 30))
        result = estimator.finalize()
        self.assertEqual(result.speed_status, "incomplete")
        self.assertIsNone(result.speed_kmh)
        self.assertEqual(result.speed_method, "two_gate")

    def test_pluggable_estimator_does_not_change_passage_contract(self) -> None:
        class FakeEstimator(SpeedEstimator):
            method = "trajectory-test"

            def __init__(self):
                self.count = 0

            def update(self, _observation):
                self.count += 1
                if self.count >= 2:
                    return MeasurementResult("measured", 12.3, self.method, "AUTO", {"samples_used": self.count})
                return MeasurementResult("measuring", None, self.method, None, {"samples_used": self.count})

        engine = WaterPassageEngine(lambda: FakeEstimator(), id_factory=lambda _ts: "P-TEST-PLUG")
        engine.update([det(1, 10)], 1.0)
        passage = engine.update([det(1, 12)], 2.0)[-1]["passage"]
        self.assertEqual(passage["speed_method"], "trajectory-test")
        self.assertEqual(passage["speed_kmh"], 12.3)
        self.assertEqual(passage["speed_status"], "measured")

    def test_observation_history_is_bounded_in_ram(self) -> None:
        engine = WaterPassageEngine(self.make_estimator, id_factory=lambda _ts: "P-TEST-RING", max_observations=8)
        passage = None
        for index in range(30):
            passage = engine.update([det(1, 10 + index * 0.1)], float(index))[-1]["passage"]
        self.assertIsNotNone(passage)
        self.assertLessEqual(int(passage["observation_count"]), 8)

    def test_best_snapshot_is_replaced_only_after_material_improvement(self) -> None:
        engine = WaterPassageEngine(
            self.make_estimator,
            id_factory=lambda _ts: "P-TEST-SNAP",
            snapshot_improvement_ratio=1.15,
        )
        first = engine.update([det(1, 30, confidence=0.80)], 1.0)[-1]
        second = engine.update([det(1, 31, confidence=0.84)], 2.0)[-1]
        third = engine.update([det(1, 32, confidence=0.98)], 3.0)[-1]
        self.assertTrue(first["snapshot_candidate"])
        self.assertFalse(second["snapshot_candidate"])
        self.assertTrue(third["snapshot_candidate"])

    @staticmethod
    def _obs(ts: float, y: float):
        from water_passage import Observation
        return Observation(ts, 1, 50.0, y, (40.0, y - 10, 60.0, y), 0.8)


class PassageApiRetentionTests(unittest.TestCase):
    FUNCTIONS = {
        "optional_float", "optional_int", "open_passages_db", "cleanup_passage_media",
        "prune_water_passages", "initialize_water_passages_db", "passage_row_to_dict",
        "_validate_passage_payload", "upsert_water_passage", "list_water_passages",
    }

    def namespace(self, temp_dir: str) -> dict[str, Any]:
        media = Path(temp_dir) / "media"
        media.mkdir()
        return {
            "Any": Any, "Dict": Dict, "List": List, "Optional": Optional,
            "Path": Path, "json": json, "sqlite3": sqlite3, "contextmanager": contextmanager,
            "HTTPException": HTTPExceptionStub,
            "PASSAGES_DB_FILE": Path(temp_dir) / "water_passages.sqlite3",
            "PASSAGE_MEDIA_DIR": media,
            "PASSAGES_RETENTION_LIMIT": 3,
            "PASSAGE_STATUSES": {"tracking", "measuring", "measured", "completed"},
            "PASSAGE_SPEED_STATUSES": {"unknown", "measuring", "measured", "incomplete"},
            "PASSAGE_ID_RE": re.compile(r"^P-[A-Za-z0-9][A-Za-z0-9._-]{1,78}$"),
            "now_iso": lambda: "2026-08-18T00:00:00+00:00",
        }

    def passage(self, index: int, *, status: str = "completed", speed: Optional[float] = None) -> Dict[str, Any]:
        ts = f"2026-08-18T00:00:{index:02d}+00:00"
        return {
            "passage_id": f"P-TEST-{index:04d}",
            "status": status,
            "started_at": ts,
            "last_seen_at": ts,
            "completed_at": ts if status == "completed" else None,
            "track_fragments": [index],
            "confidence": 0.8,
            "speed_status": "measured" if speed is not None else ("incomplete" if status == "completed" else "measuring"),
            "speed_kmh": speed,
            "speed_method": "two_gate",
            "direction": "A->B" if speed is not None else None,
            "measurement_meta": {"samples_used": 2},
            "observation_count": 2,
            "snapshot_score": 10 + index,
            "snapshot_url": f"/sea-speed/media/passages/P-TEST-{index:04d}.jpg",
        }

    def test_upsert_updates_same_passage_without_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = self.namespace(temp_dir)
            load_api_functions(self.FUNCTIONS, ns)
            ns["initialize_water_passages_db"]()
            ns["upsert_water_passage"](self.passage(1, status="measuring"))
            updated = self.passage(1, status="completed", speed=8.7)
            ns["upsert_water_passage"](updated)
            rows = ns["list_water_passages"](10)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["speed_kmh"], 8.7)
            self.assertEqual(rows[0]["status"], "completed")

    def test_retention_prunes_oldest_completed_and_orphaned_media(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = self.namespace(temp_dir)
            load_api_functions(self.FUNCTIONS, ns)
            ns["initialize_water_passages_db"]()
            for index in range(4):
                image = ns["PASSAGE_MEDIA_DIR"] / f"P-TEST-{index:04d}.jpg"
                image.write_bytes(b"jpg")
                ns["upsert_water_passage"](self.passage(index, speed=5.0 + index))
            rows = ns["list_water_passages"](10)
            self.assertEqual(len(rows), 3)
            self.assertNotIn("P-TEST-0000", {row["passage_id"] for row in rows})
            self.assertFalse((ns["PASSAGE_MEDIA_DIR"] / "P-TEST-0000.jpg").exists())

    def test_retention_refuses_to_delete_active_passage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            ns = self.namespace(temp_dir)
            load_api_functions(self.FUNCTIONS, ns)
            ns["initialize_water_passages_db"]()
            for index in range(3):
                ns["upsert_water_passage"](self.passage(index, status="measuring"))
            with self.assertRaises(RuntimeError):
                ns["upsert_water_passage"](self.passage(9, status="measuring"))
            self.assertEqual(len(ns["list_water_passages"](10)), 3)

    def test_api_schema_does_not_persist_per_frame_trajectory_rows(self) -> None:
        source = API_SOURCE.read_text(encoding="utf-8")
        self.assertIn("PASSAGES_RETENTION_LIMIT = 300", source)
        self.assertIn("CREATE TABLE IF NOT EXISTS water_passages", source)
        self.assertNotIn("CREATE TABLE IF NOT EXISTS passage_observations", source)


class IntegrationContractTests(unittest.TestCase):
    def test_worker_uses_passage_engine_but_preserves_road_event_path(self) -> None:
        source = WORKER_SOURCE.read_text(encoding="utf-8")
        for marker in (
            "from water_passage import WaterPassageEngine, build_two_gate_estimator",
            "passage_engine.update(detections, now)",
            "def post_passage(",
            'profile.domain == "water":\n                for vessel in water_event_candidates',
            "elif detections:",
            "legacy_event_ready",
        ):
            self.assertIn(marker, source)

    def test_frontend_renders_passage_lifecycle(self) -> None:
        source = FRONTEND_SOURCE.read_text(encoding="utf-8")
        for marker in (
            "/sea-speed/api/cam1/passages?limit=3",
            "Последние проходы",
            "ev.passage_id",
            "ev.speed_status",
            "измеряется",
            "ev.direction",
        ):
            self.assertIn(marker, source)

    def test_exact_artifacts_package_passage_module(self) -> None:
        source = ARTIFACT_SOURCE.read_text(encoding="utf-8")
        self.assertEqual(source.count('"worker/water_passage.py"'), 2)
        self.assertIn('"ubuntu-worker"', source)
        self.assertIn('"edge"', source)


if __name__ == "__main__":
    unittest.main()
