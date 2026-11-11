"""RED regression tests for MostDef2000/sea-speed#587 (wave-1 task B, phase 1).

Issue #587: every externally-supplied non-finite numeric input (NaN / ±Infinity,
including the ``1e999`` overflow literal and numeric strings such as ``"NaN"``)
must be rejected with HTTP 400 and must cause NO state change.

This file pins the DESIRED behavior. On the current base (35cabf9) every test
here FAILS for the documented current-vs-desired reason; once the fix lands the
tests pass unchanged. No test is weakened, skipped, or xfailed, and no code
under test is mocked.

The six residual sites (re-verified line numbers on this base):

1. ``post_analytics_speed_lines`` — unguarded ``int(reference_width/height)``
   (api/app/main.py:1108-1109 norm, 1117-1118 legacy). Today: 500 (unhandled
   ValueError/OverflowError from ``int(nan)``), raised BEFORE any write.
2. ``post_analytics_roi`` — api/app/main.py:964-965. Today: 500, no write.
3. ``post_analytics_crossing_line`` — api/app/analytics.py:397-398 (norm),
   406-407 (legacy); file is DATA_DIR/"cam1_crossing_line.json". Today: 500,
   no write.
4. ``measurement_meta`` — ``json.dumps`` with ``allow_nan=True``
   (api/app/water_passages.py:206-211, dumps at 209); persists to
   water_passages.sqlite3 ``measurement_meta_json``. Today: 200 and PERSISTED
   (bare NaN/Infinity tokens in the sqlite JSON column — invalid strict JSON).
   The path also mirrors a row into objects.sqlite3 and writes a snapshot
   media file.
5. ``deliver_event`` stores the event verbatim — api/app/store.py:528-553
   (dumps at 553); persists to state.sqlite3 ``event_feed.payload_json`` AND
   ``event_receipts.response_event_json``. Today: 200 and PERSISTED. The path
   also mirrors a row into objects.sqlite3 and writes a snapshot media file.
6. ``speed_min`` / ``speed_max`` Optional[float] query params with only a
   ``< 0`` guard — api/app/main.py:560-574 (get_cam1_objects) and 1180-1213
   (get_analytics_objects -> get_objects 1192-1221, guards 1204-1209). Today:
   200 with a silently empty (or unfiltered) result set.

Characterization notes (observed on this tree):

* ``json.loads`` ACCEPTS bare ``NaN`` / ``Infinity`` tokens (they reach the
  handlers as ``float('nan')`` / ``float('inf')``); ``1e999`` parses to
  ``inf``; there is no 422 parser-rejection path.
* Sites 1-3 today return **500** "Internal Server Error" (unhandled
  ValueError/OverflowError from ``int(nan)``), raised BEFORE any write, so no
  state change. The RED signal is the status code (500 != 400); the no-write
  assertion is kept as a guard so a future fix cannot write-then-reject.
* Sites 4-5 today return **200** and PERSIST: the sqlite JSON columns contain
  bare ``NaN`` / ``Infinity`` tokens (invalid strict JSON). Both paths also add
  a row to objects.sqlite3 (registry mirror) and write snapshot/media files.
  The RED signal is the no-write assertion (state changed) — that is the point.
* Site 6 today returns **200** with a silently empty result set (count=0
  total=0 even with objects present) for NaN/inf lower bounds.
* Client response bodies show ``null`` (FastAPI converts non-finite floats to
  null in responses) — the strict-JSON violation is in the PERSISTED bytes, not
  the immediate response.
* ``TestClient`` requires ``raise_server_exceptions=False`` to observe the
  production 500 instead of re-raising the handler exception in the test.

One-process battery contract (same as tests/test_api_http_integration.py):
fastapi/httpx are imported through the guarded-optional idiom and the
``MANAGED_MODULE_NAMES`` are evicted by the class cleanup so the AST/exec
harnesses in tests/test_numeric_input_validation.py are not polluted by leaked
real modules.
"""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]

# Module names the guarded imports below may introduce into sys.modules when
# fastapi is installed. One-process battery contract (same rationale as
# tests/test_api_http_integration.py): the AST/exec harnesses stub exactly
# these names only while they are ABSENT from sys.modules, so the class
# cleanup evicts the ones this module cached — restoring the pre-module world
# instead of leaking real modules into the exec harnesses that follow. Names
# that preexisted are never touched.
MANAGED_MODULE_NAMES = (
    "fastapi",
    "fastapi.staticfiles",
    "fastapi.responses",
)
PREEXISTING_MODULES = frozenset(
    name for name in MANAGED_MODULE_NAMES if name in sys.modules
)

# The package-context app import below caches the whole api.app.* module tree
# in sys.modules, bound to THIS class's temp SEA_SPEED_BASE_DIR (config reads
# the env at import time). This file sorts BEFORE tests/test_api_http_integration.py
# (alphabetical battery order), so without this eviction the sibling HTTP
# integration class would reuse the stale cached api.app.main (and its config)
# bound to this class's temp dir and fail its own path assertions. Evicting the
# api.app.* names this import introduced lets the sibling re-import fresh with
# its own overrides. Names that preexisted are never touched. (The sibling's
# own MANAGED_MODULE_NAMES eviction covers only the fastapi names; the api.app.*
# eviction here is the additional cross-file hygiene this second importer needs.)
API_APP_MODULE_NAMES = (
    "api",
    "api.app",
    "api.app.analytics",
    "api.app.config",
    "api.app.identity",
    "api.app.live_feeds",
    "api.app.main",
    "api.app.objects_registry",
    "api.app.passage_mirrors",
    "api.app.store",
    "api.app.water_passages",
)
PREEXISTING_API_MODULES = frozenset(
    name for name in API_APP_MODULE_NAMES if name in sys.modules
)

try:
    import fastapi  # noqa: F401  # guarded-optional probe (CI has no fastapi)
    from fastapi.testclient import TestClient

    import httpx  # noqa: F401  # TestClient's HTTP transport dependency
except ModuleNotFoundError:  # CI today: fastapi/httpx not installed
    HTTP_TESTS_ENABLED = False
else:
    HTTP_TESTS_ENABLED = True

# Gitleaks-safe fixture values (same convention as
# tests/test_api_http_integration.py): low-entropy throwaway constants for a
# disposable temp environment, never real secrets.
BEARER_FIXTURE = "integration-fixture-587"
EDGE_HEADER_FIXTURE = "edge-fixture-587"
WORKER_TOKEN_FIXTURE = "worker-fixture-587"
ADMIN_USER_FIXTURE = "fixture-admin-587"
# 40 hex chars (deployed_source_commit validates SHA_RE), minimal entropy.
DEPLOYED_COMMIT_FIXTURE = "b" * 40

# Loopback is rejected by the app's own worker_control_origin guard before any
# connection is attempted: deterministic fail-closed, zero network.
UNREACHABLE_WORKER_CONTROL_URL = "http://127.0.0.1:19002"

# Identity headers accepted while EDGE_AUTH_SECRET is set to the fixture value;
# SEA_SPEED_ADMIN_USERS resolves the user to the admin role.
ADMIN_HEADERS = {
    "X-Authentik-Username": ADMIN_USER_FIXTURE,
    "X-Sea-Speed-Edge-Auth": EDGE_HEADER_FIXTURE,
}
AUTH_HEADERS = {"Authorization": f"Bearer {BEARER_FIXTURE}"}

# Every environment name this class touches; each is restored to its prior
# value (or removed) by a class cleanup so later tests in the same battery
# process see the original environment.
MANAGED_ENV_NAMES = (
    "SEA_SPEED_BASE_DIR",
    "SEA_SPEED_DEPLOYED_COMMIT_FILE",
    "SEA_SPEED_API_TOKEN",
    "SEA_SPEED_EDGE_AUTH_SECRET",
    "SEA_SPEED_ADMIN_USERS",
    "SEA_SPEED_WORKER_CONTROL_TOKEN",
    "SEA_SPEED_WORKER_CONTROL_URL",
    "SEA_SPEED_SOURCE_COMMIT",
)

# Placeholder string used to inject a raw non-finite literal (e.g. ``1e999``)
# into a JSON document that ``json.dumps`` cannot emit on its own (a Python
# float cannot represent 1e999 — it overflows to inf). The placeholder is a
# quoted JSON string in the serialized document and is replaced by the bare
# literal before the body is sent.
RAW_LITERAL_PLACEHOLDER = "__RAW_NONFINITE_587__"


@unittest.skipUnless(
    HTTP_TESTS_ENABLED,
    "fastapi/httpx are not installed (CI installs only pyyaml; the HTTP "
    "integration tests run where the declared pins are installed)",
)
class NonFiniteResidualPathTests(unittest.TestCase):
    """RED pins: non-finite numeric input must be 400 with no state change."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        temp = tempfile.TemporaryDirectory(prefix="sea-speed-587-http-")
        cls.addClassCleanup(temp.cleanup)
        base_dir = Path(temp.name)
        deployed_file = base_dir / "deploy-state" / "current-release"
        deployed_file.parent.mkdir(parents=True, exist_ok=True)
        deployed_file.write_text(DEPLOYED_COMMIT_FIXTURE + "\n", encoding="utf-8")
        prior = {name: os.environ.get(name) for name in MANAGED_ENV_NAMES}
        cls.addClassCleanup(cls._restore_env, prior)
        os.environ.update(
            {
                "SEA_SPEED_BASE_DIR": str(base_dir),
                "SEA_SPEED_DEPLOYED_COMMIT_FILE": str(deployed_file),
                "SEA_SPEED_API_TOKEN": BEARER_FIXTURE,
                "SEA_SPEED_EDGE_AUTH_SECRET": EDGE_HEADER_FIXTURE,
                "SEA_SPEED_ADMIN_USERS": ADMIN_USER_FIXTURE,
                "SEA_SPEED_WORKER_CONTROL_TOKEN": WORKER_TOKEN_FIXTURE,
                "SEA_SPEED_WORKER_CONTROL_URL": UNREACHABLE_WORKER_CONTROL_URL,
            }
        )
        # deployed_source_commit prefers this env var over the commit file;
        # remove it so the fixture file is the authoritative source here.
        os.environ.pop("SEA_SPEED_SOURCE_COMMIT", None)
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        # The app import below caches fastapi/fastapi.staticfiles/
        # fastapi.responses in sys.modules. Same one-process contract as the
        # env restore above: when the class is done, evict the names that were
        # not preexisting so later tests that stub those names only while they
        # are absent see the original sys.modules again.
        cls.addClassCleanup(cls._restore_modules)
        # Fresh package-context import: config reads the overrides above at
        # module level, so the whole data/media tree lands in the temp dir.
        cls.app_module = importlib.import_module("api.app.main")
        cls.config = cls.app_module.config

    @classmethod
    def _restore_env(cls, prior: Dict[str, Optional[str]]) -> None:
        for name, value in prior.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    @classmethod
    def _restore_modules(cls) -> None:
        for name in MANAGED_MODULE_NAMES:
            if name not in PREEXISTING_MODULES:
                sys.modules.pop(name, None)
        for name in API_APP_MODULE_NAMES:
            if name not in PREEXISTING_API_MODULES:
                sys.modules.pop(name, None)

    # -- helpers -----------------------------------------------------------

    def client(self):
        # raise_server_exceptions=False: observe the production 500 for the
        # unhandled int(nan) sites instead of re-raising in the test process.
        return TestClient(self.app_module.app, raise_server_exceptions=False)

    def post_json(self, client: Any, url: str, raw_body: str, headers: Dict[str, str]) -> Any:
        # httpx's json= serializes strict JSON and refuses non-finite floats;
        # the #587 threat is exactly a client/worker shipping NaN/Infinity/
        # 1e999 literals, so the body is sent as raw content.
        return client.post(
            url,
            content=raw_body,
            headers={"Content-Type": "application/json", **headers},
        )

    def post_form_event(self, client: Any, url: str, raw_metadata: str, snapshot: bytes = b"fixture-jpeg-587") -> Any:
        # Event/passage ingestion is a multipart form: the metadata field is a
        # raw JSON string (bare NaN/Infinity tokens allowed by json.loads), the
        # snapshot is a file.
        return client.post(
            url,
            data={"metadata": raw_metadata},
            files={"snapshot": ("snap.jpg", snapshot, "image/jpeg")},
            headers=AUTH_HEADERS,
        )

    def raw_json(self, payload: Dict[str, Any]) -> str:
        # json.dumps(allow_nan=True) emits bare NaN/Infinity tokens for
        # float('nan')/float('inf') — exactly the non-strict JSON a Python
        # worker would ship.
        return json.dumps(payload)

    def raw_json_with_literal(self, payload: Dict[str, Any], literal: str) -> str:
        # Replace the quoted placeholder with a bare non-finite literal
        # (e.g. 1e999) that json.dumps cannot emit from a Python value.
        return json.dumps(payload).replace(f'"{RAW_LITERAL_PLACEHOLDER}"', literal)

    def _row_count(self, db_path: Path, query: str) -> int:
        if not db_path.exists():
            return 0
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            return int(connection.execute(query).fetchone()[0])
        except sqlite3.Error:
            return 0
        finally:
            connection.close()

    def _media_tree(self) -> List[str]:
        if not self.config.MEDIA_DIR.is_dir():
            return []
        return sorted(
            str(p.relative_to(self.config.MEDIA_DIR))
            for p in self.config.MEDIA_DIR.rglob("*")
            if p.is_file()
        )

    def _file_text(self, path: Path) -> Optional[str]:
        if not path.is_file():
            return None
        return path.read_text(encoding="utf-8")

    def state_snapshot(self) -> Dict[str, Any]:
        """Deterministic snapshot of every state surface the six sites touch.

        Per-DB table row counts (state.sqlite3: event_feed, event_receipts;
        water_passages.sqlite3: water_passages; objects.sqlite3: objects), the
        full media-dir file tree, and the analytics JSON-file contents
        (crossing-line, speed-lines, roi). Asserted equal before/after each
        mutation case to pin "no state change".
        """
        return {
            "event_feed": self._row_count(self.config.STATE_DB_FILE, "SELECT COUNT(*) FROM event_feed"),
            "event_receipts": self._row_count(self.config.STATE_DB_FILE, "SELECT COUNT(*) FROM event_receipts"),
            "water_passages": self._row_count(self.config.PASSAGES_DB_FILE, "SELECT COUNT(*) FROM water_passages"),
            "objects": self._row_count(self.config.OBJECTS_DB_FILE, "SELECT COUNT(*) FROM objects"),
            "media_tree": self._media_tree(),
            "crossing_line": self._file_text(self.config.DATA_DIR / "cam1_crossing_line.json"),
            "speed_lines": self._file_text(self.config.SPEED_LINES_FILE),
            "roi": self._file_text(self.config.ROI_FILE),
        }

    def assert_no_state_change(self, before: Dict[str, Any], label: str) -> None:
        after = self.state_snapshot()
        self.assertEqual(
            after,
            before,
            f"state changed for {label}: "
            f"before={json.dumps(before, sort_keys=True, default=str)} "
            f"after={json.dumps(after, sort_keys=True, default=str)}",
        )

    # The five non-finite variants of a single numeric field, as (label,
    # raw-json) pairs. ``field`` is a top-level key of ``payload``.
    def _field_variants(self, payload: Dict[str, Any], field: str) -> List[tuple]:
        variants: List[tuple] = []
        p = dict(payload)
        p[field] = float("nan")
        variants.append(("bare-NaN", self.raw_json(p)))
        p = dict(payload)
        p[field] = RAW_LITERAL_PLACEHOLDER
        variants.append(("1e999", self.raw_json_with_literal(p, "1e999")))
        p = dict(payload)
        p[field] = RAW_LITERAL_PLACEHOLDER
        variants.append(("-1e999", self.raw_json_with_literal(p, "-1e999")))
        p = dict(payload)
        p[field] = "NaN"
        variants.append(("str-NaN", self.raw_json(p)))
        p = dict(payload)
        p[field] = "1e999"
        variants.append(("str-1e999", self.raw_json(p)))
        return variants

    # -- site 1: post_analytics_speed_lines (main.py:1108-1109 / 1117-1118) --

    def _speed_lines_norm_payload(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "distance_m": 57.0,
            "line_a_norm": [{"x_norm": 0.2, "y_norm": 0.2}, {"x_norm": 0.8, "y_norm": 0.2}],
            "line_b_norm": [{"x_norm": 0.2, "y_norm": 0.8}, {"x_norm": 0.8, "y_norm": 0.8}],
        }

    def _speed_lines_legacy_payload(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "distance_m": 57.0,
            "line_a": [{"x": 100, "y": 100}, {"x": 500, "y": 100}],
            "line_b": [{"x": 100, "y": 500}, {"x": 500, "y": 500}],
        }

    def test_speed_lines_norm_rejects_nonfinite_reference_width_400(self):
        # Norm path (main.py:1108-1109): int(reference_width) on a non-finite
        # value. Today: 500 (unhandled ValueError/OverflowError), no write.
        # Desired: 400, no write.
        for label, raw in self._field_variants(self._speed_lines_norm_payload(), "reference_width"):
            with self.subTest(label=label):
                before = self.state_snapshot()
                with self.client() as client:
                    response = self.post_json(client, "/api/cam1/speed-lines", raw, ADMIN_HEADERS)
                # 500-site: status assertion first (RED today: 500 != 400).
                self.assertEqual(response.status_code, 400, f"{label}: body={response.text!r}")
                # Guard: the rejection must not have written the speed-lines file.
                self.assert_no_state_change(before, f"speed-lines norm {label}")

    def test_speed_lines_legacy_rejects_nonfinite_reference_width_400(self):
        # Legacy path (main.py:1117-1118): int(reference_width) after
        # _infer_legacy_ref_w_h. Today: 500, no write. Desired: 400, no write.
        for label, raw in self._field_variants(self._speed_lines_legacy_payload(), "reference_width"):
            with self.subTest(label=label):
                before = self.state_snapshot()
                with self.client() as client:
                    response = self.post_json(client, "/api/cam1/speed-lines", raw, ADMIN_HEADERS)
                self.assertEqual(response.status_code, 400, f"{label}: body={response.text!r}")
                self.assert_no_state_change(before, f"speed-lines legacy {label}")

    # -- site 2: post_analytics_roi (main.py:964-965) -----------------------

    def test_roi_rejects_nonfinite_reference_width_400(self):
        # Norm path (main.py:964-965): int(reference_width) on a non-finite
        # value. Today: 500, no write. Desired: 400, no write.
        payload = {
            "enabled": True,
            "polygon_norm": [
                {"x_norm": 0.1, "y_norm": 0.1},
                {"x_norm": 0.5, "y_norm": 0.1},
                {"x_norm": 0.5, "y_norm": 0.8},
            ],
        }
        for label, raw in self._field_variants(payload, "reference_width"):
            with self.subTest(label=label):
                before = self.state_snapshot()
                with self.client() as client:
                    response = self.post_json(client, "/api/cam1/roi", raw, ADMIN_HEADERS)
                self.assertEqual(response.status_code, 400, f"{label}: body={response.text!r}")
                self.assert_no_state_change(before, f"roi {label}")

    # -- site 3: post_analytics_crossing_line (analytics.py:397-398/406-407) --

    def _crossing_line_norm_payload(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "line_norm": [{"x_norm": 0.2, "y_norm": 0.2}, {"x_norm": 0.8, "y_norm": 0.2}],
        }

    def _crossing_line_legacy_payload(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "line": [{"x": 100, "y": 100}, {"x": 500, "y": 100}],
        }

    def test_crossing_line_norm_rejects_nonfinite_reference_width_400(self):
        # Norm path (analytics.py:397-398): int(reference_width) on a
        # non-finite value. Today: 500, no write. Desired: 400, no write.
        for label, raw in self._field_variants(self._crossing_line_norm_payload(), "reference_width"):
            with self.subTest(label=label):
                before = self.state_snapshot()
                with self.client() as client:
                    response = self.post_json(client, "/api/cam1/crossing-line", raw, ADMIN_HEADERS)
                self.assertEqual(response.status_code, 400, f"{label}: body={response.text!r}")
                self.assert_no_state_change(before, f"crossing-line norm {label}")

    def test_crossing_line_legacy_rejects_nonfinite_reference_width_400(self):
        # Legacy path (analytics.py:406-407): int(reference_width) after
        # _infer_legacy_ref_w_h. Today: 500, no write. Desired: 400, no write.
        for label, raw in self._field_variants(self._crossing_line_legacy_payload(), "reference_width"):
            with self.subTest(label=label):
                before = self.state_snapshot()
                with self.client() as client:
                    response = self.post_json(client, "/api/cam1/crossing-line", raw, ADMIN_HEADERS)
                self.assertEqual(response.status_code, 400, f"{label}: body={response.text!r}")
                self.assert_no_state_change(before, f"crossing-line legacy {label}")

    # -- site 4: measurement_meta (water_passages.py:206-211) ---------------

    def _passage_payload(self, passage_id: str, measurement_meta: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "passage_id": passage_id,
            "status": "measured",
            "speed_status": "measured",
            "speed_kmh": 12.0,
            "started_at": "2026-01-01T00:00:00+00:00",
            "last_seen_at": "2026-01-01T00:00:05+00:00",
            "class_name": "vessel",
            "track_fragments": [1],
            "measurement_meta": measurement_meta,
        }

    def test_water_passage_rejects_nonfinite_measurement_meta_400(self):
        # Persist-site (water_passages.py:209): json.dumps(allow_nan=True)
        # persists bare NaN/Infinity tokens into measurement_meta_json.
        # Today: 200 and PERSISTED (water_passages row + objects mirror +
        # snapshot media). Desired: 400, no write.
        # no-write assertion FIRST (that failure is the point).
        cases = [
            ("bare-NaN", {"value": float("nan")}),
            ("1e999", {"value": RAW_LITERAL_PLACEHOLDER}),
            ("-1e999", {"value": RAW_LITERAL_PLACEHOLDER}),
            ("nested-nested-NaN", {"outer": {"inner": {"deep": float("nan")}}}),
            ("nested-list-inf", {"values": [float("inf"), float("-inf")]}),
        ]
        for index, (label, meta) in enumerate(cases, start=1):
            with self.subTest(label=label):
                passage_id = f"P-587-mm-{index}"
                payload = self._passage_payload(passage_id, meta)
                if RAW_LITERAL_PLACEHOLDER in json.dumps(meta):
                    raw = self.raw_json_with_literal(payload, "1e999" if label == "1e999" else "-1e999")
                else:
                    raw = self.raw_json(payload)
                before = self.state_snapshot()
                with self.client() as client:
                    response = self.post_form_event(client, "/api/cam1/passages", raw)
                # Persist-site: no-write assertion first (RED today: persisted).
                self.assert_no_state_change(before, f"water-passage {label}")
                self.assertEqual(response.status_code, 400, f"{label}: body={response.text!r}")

    # -- site 5: deliver_event verbatim (store.py:528-553) ------------------

    def test_event_rejects_nonfinite_telemetry_400(self):
        # Persist-site (store.py:553): json.dumps(allow_nan=True) persists the
        # event verbatim into event_feed.payload_json AND
        # event_receipts.response_event_json. Today: 200 and PERSISTED
        # (event_feed + event_receipts + objects mirror + snapshot media).
        # Desired: 400, no write. no-write assertion FIRST.
        cases = [
            ("bare-NaN", {"telemetry": {"speed_kmh": float("nan")}}),
            ("1e999", {"telemetry": {"speed_kmh": RAW_LITERAL_PLACEHOLDER}}),
            ("-1e999", {"telemetry": {"speed_kmh": RAW_LITERAL_PLACEHOLDER}}),
            ("nested-nested-inf", {"telemetry": {"nested": {"deep": float("inf")}}}),
            ("top-level-NaN", {"quality": float("nan")}),
        ]
        for index, (label, extra) in enumerate(cases, start=1):
            with self.subTest(label=label):
                event = {
                    "event_id": f"E-587-ev-{index}",
                    "object_type": "boat",
                    "class_name": "boat",
                }
                event.update(extra)
                if RAW_LITERAL_PLACEHOLDER in json.dumps(extra):
                    raw = self.raw_json_with_literal(event, "1e999" if label == "1e999" else "-1e999")
                else:
                    raw = self.raw_json(event)
                before = self.state_snapshot()
                with self.client() as client:
                    response = self.post_form_event(client, "/api/cam1/events", raw)
                # Persist-site: no-write assertion first (RED today: persisted).
                self.assert_no_state_change(before, f"event {label}")
                self.assertEqual(response.status_code, 400, f"{label}: body={response.text!r}")

    # -- site 6: speed_min/speed_max query params (main.py:560-574/1180-1213) --

    def test_objects_query_rejects_nonfinite_speed_bounds_400(self):
        # Query-param site (main.py:568-571 / 1204-1207): only a `< 0` guard,
        # so NaN/±inf pass and reach the SQL where-clause. Today: 200 with a
        # silently empty (NaN/inf lower bound) or unfiltered (inf upper bound)
        # result set. Desired: 400.
        # Seed one real object so the "silently empty even with objects
        # present" characterization is meaningful.
        seed = {"event_id": "E-587-seed", "object_type": "boat", "class_name": "boat"}
        with self.client() as client:
            seeded = self.post_form_event(client, "/api/cam1/events", self.raw_json(seed))
            self.assertEqual(seeded.status_code, 200, f"seed failed: {seeded.text!r}")
            baseline = client.get("/api/cam1/objects")
            self.assertEqual(baseline.status_code, 200)
            self.assertGreaterEqual(baseline.json()["total"], 1, "seed object must be queryable")
            for label, params in [
                ("speed_min=NaN", {"speed_min": "NaN"}),
                ("speed_min=1e999", {"speed_min": "1e999"}),
                ("speed_max=Infinity", {"speed_max": "Infinity"}),
                ("speed_min=-1e999", {"speed_min": "-1e999"}),
            ]:
                with self.subTest(label=label):
                    response = client.get("/api/cam1/objects", params=params)
                    # Query site: status assertion is the RED signal
                    # (today: 200 != 400).
                    self.assertEqual(response.status_code, 400, f"{label}: body={response.text!r}")


if __name__ == "__main__":
    unittest.main()
