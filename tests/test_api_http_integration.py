"""Real FastAPI HTTP integration tests (issue #582 wave 1, audit #534 P2-01).

First TestClient harness in the suite: these tests drive the REAL
``api/app/main.py`` FastAPI app through the real HTTP boundary (status
codes, response bodies, persisted side effects) instead of the AST/exec
harnesses the rest of the suite needs because the app could not be
imported without fastapi. Coverage targets the riskiest routes first:
the authorization boundary, event ingestion, ROI, calibration
(speed-config/speed-lines), object deletion, worker control and
/api/health.

Reproducible environment: ``setUpClass`` points ``SEA_SPEED_BASE_DIR`` at a
fresh temp directory (the #582 config override — every derived path and the
import-time mkdirs redirect together) and ``SEA_SPEED_DEPLOYED_COMMIT_FILE``
at a fixture file inside it, sets the auth fixtures
(``SEA_SPEED_API_TOKEN`` / ``SEA_SPEED_EDGE_AUTH_SECRET`` /
``SEA_SPEED_ADMIN_USERS`` / ``SEA_SPEED_WORKER_CONTROL_*``) to gitleaks-safe
low-entropy constants (repo precedent: tests/test_sea_speed_edge_vhost_renderer.py),
and THEN imports the app in package context (``importlib.import_module``).
Package context keeps the bare ``config``/``store`` direct-file module names
out of ``sys.modules``, so the existing tests that exec ``main.py`` sources
with their own stubs stay independent; the env overrides are restored by a
class cleanup, and the full one-process battery is the no-cross-pollution
proof.

Guarded-optional idiom (tests/test_live_envelope_validators.py): fastapi and
httpx are imported inside a try whose handler catches ModuleNotFoundError;
when they are absent (CI today — quality-integration.yml installs only
pyyaml) the whole module skips and the battery stays green unchanged. The
runner (scripts/run_tests.py) does NOT install fastapi/httpx — its import
hygiene scan merely classifies these guarded imports as allowed
guarded-optional — so the tests execute for real only in environments that
already provide fastapi (e.g. a local PYTHONPATH), and skip everywhere else;
activating them in CI is a workflow-lane change deliberately out of this
wave's scope (documented gap, issue #582).

Worker control is never pointed at a real worker: the only permitted stub
boundary. ``SEA_SPEED_WORKER_CONTROL_URL`` targets loopback, which the app's
own ``worker_control_origin`` guard rejects before any connection is
attempted, so the route is proven to fail closed (503) deterministically
with no network I/O. The connection-refused path (unreachable RFC1918
agent) is deferred to a later wave.
"""

from __future__ import annotations

import importlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]

# Module names the guarded imports below may introduce into sys.modules when
# fastapi is installed. One-process battery contract (same rationale as the
# MANAGED_ENV_NAMES restore in the class cleanup): tests/test_roi_normalization.py
# stubs exactly these names only while they are ABSENT from sys.modules, so
# the class cleanup evicts the ones this module cached — restoring the
# pre-module world instead of leaking real modules into the exec harnesses
# that follow. Names that preexisted are never touched.
#
# Boundary: eviction is intentionally shallow. Transitive modules the real
# fastapi import pulls in (starlette, pydantic, httpx, ...) stay cached in
# sys.modules; no exec harness in the suite stubs those names, so leaving
# them cached is inert. The full one-process battery with fastapi present
# is the standing proof of that boundary.
MANAGED_MODULE_NAMES = (
    "fastapi",
    "fastapi.staticfiles",
    "fastapi.responses",
)
PREEXISTING_MODULES = frozenset(
    name for name in MANAGED_MODULE_NAMES if name in sys.modules
)

try:
    import fastapi  # noqa: F401  # guarded-optional probe (CI has no fastapi)
    from fastapi.testclient import TestClient

    import httpx  # noqa: F401  # TestClient's HTTP transport dependency
except ModuleNotFoundError:  # CI today: fastapi/httpx not installed
    HTTP_TESTS_ENABLED = False
else:
    HTTP_TESTS_ENABLED = True

# Gitleaks-safe low-entropy fixture values (repo precedent:
# tests/test_sea_speed_edge_vhost_renderer.py EDGE_SNIPPET_FIXTURE,
# tests/test_393_control_token_separation.py INGESTION_TOKEN). These are
# throwaway constants for a disposable temp environment, never real secrets.
API_TOKEN_FIXTURE = "integration-fixture-582"
EDGE_SECRET_FIXTURE = "edge-fixture-582"
WORKER_TOKEN_FIXTURE = "worker-fixture-582"
ADMIN_USER_FIXTURE = "fixture-admin-582"
# 40 hex chars (deployed_source_commit validates SHA_RE), minimal entropy.
DEPLOYED_COMMIT_FIXTURE = "a" * 40

# Loopback is rejected by the app's own worker_control_origin guard before
# any connection is attempted: deterministic fail-closed, zero network.
UNREACHABLE_WORKER_CONTROL_URL = "http://127.0.0.1:19001"

# Identity headers accepted while EDGE_AUTH_SECRET is set to the fixture
# value; SEA_SPEED_ADMIN_USERS resolves the user to the admin role.
ADMIN_HEADERS = {
    "X-Authentik-Username": ADMIN_USER_FIXTURE,
    "X-Sea-Speed-Edge-Auth": EDGE_SECRET_FIXTURE,
}
AUTH_HEADERS = {"Authorization": f"Bearer {API_TOKEN_FIXTURE}"}

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

# Runs in a fresh interpreter (cwd=repository root) with SEA_SPEED_API_TOKEN
# removed: proves the 500 "SEA_SPEED_API_TOKEN is not set" fail-closed path
# through the real HTTP boundary without a second in-process app import.
SUBPROCESS_PROBE = (
    "import json, os, sys\n"
    "sys.path.insert(0, os.getcwd())\n"
    "import api.app.main as app_module\n"
    "from fastapi.testclient import TestClient\n"
    "with TestClient(app_module.app) as client:\n"
    "    response = client.post('/api/cam1/events', data={'metadata': '{}'})\n"
    "print(json.dumps({'status': response.status_code, "
    "'detail': response.json()['detail']}))\n"
)


@unittest.skipUnless(
    HTTP_TESTS_ENABLED,
    "fastapi/httpx are not installed (CI installs only pyyaml; the HTTP "
    "integration tests run where the declared pins are installed)",
)
class SeaSpeedApiHttpIntegrationTests(unittest.TestCase):
    """Real-app HTTP boundary tests against a disposable temp data root."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        temp = tempfile.TemporaryDirectory(prefix="sea-speed-582-http-")
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
                "SEA_SPEED_API_TOKEN": API_TOKEN_FIXTURE,
                "SEA_SPEED_EDGE_AUTH_SECRET": EDGE_SECRET_FIXTURE,
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
        # env restore above: when the class is done, evict the names that
        # were not preexisting so later tests that stub those names only
        # while they are absent (tests/test_roi_normalization.py) see the
        # original sys.modules again.
        cls.addClassCleanup(cls._restore_modules)
        # Fresh package-context import: config reads the overrides above at
        # module level, so the whole data/media tree lands in the temp dir.
        cls.app_module = importlib.import_module("api.app.main")
        cls.config = cls.app_module.config
        cls.store = cls.app_module.store

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

    # -- helpers -----------------------------------------------------------

    def client(self):
        return TestClient(self.app_module.app)

    def sqlite_rows(self, db_path: Path, query: str, parameters: tuple = ()) -> List[Any]:
        connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            return connection.execute(query, parameters).fetchall()
        finally:
            connection.close()

    def post_event(self, client: Any, event: Dict[str, Any], snapshot: bytes = b"fixture-jpeg") -> Any:
        return client.post(
            "/api/cam1/events",
            data={"metadata": json.dumps(event)},
            files={"snapshot": ("snap.jpg", snapshot, "image/jpeg")},
            headers=AUTH_HEADERS,
        )

    def post_json(self, client: Any, url: str, payload: Dict[str, Any], headers: Dict[str, str]) -> Any:
        # httpx's json= serializes strict JSON and refuses non-finite floats;
        # the #577 threat is exactly a Python worker json.dumps'ing
        # NaN/Infinity literals, so those probes send the raw document.
        return client.post(
            url,
            content=json.dumps(payload),
            headers={"Content-Type": "application/json", **headers},
        )

    # -- g. /api/health ----------------------------------------------------

    def test_health_is_unauthenticated_and_reports_service_identity(self):
        with self.client() as client:
            response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["service"], "sea-speed-api")
        self.assertEqual(body["api_schema"], "sea_speed_api_v1")
        self.assertEqual(body["source_commit"], DEPLOYED_COMMIT_FIXTURE)
        self.assertTrue(body["time"])

    # -- a. authorization boundary ----------------------------------------

    def test_missing_authorization_header_is_rejected_403(self):
        with self.client() as client:
            response = client.post("/api/cam1/events", data={"metadata": "{}"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "Forbidden"})

    def test_wrong_bearer_token_is_rejected_403(self):
        with self.client() as client:
            response = client.post(
                "/api/cam1/events",
                data={"metadata": "{}"},
                headers={"Authorization": "Bearer not-the-fixture-token"},
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "Forbidden"})

    def test_correct_bearer_token_passes_the_authorization_boundary(self):
        # A correct token gets PAST require_auth: the same request with a
        # missing/wrong header stops at 403, while this one reaches the
        # metadata validation and fails there with 400 instead.
        with self.client() as client:
            response = client.post(
                "/api/cam1/events",
                data={"metadata": "not-json"},
                headers=AUTH_HEADERS,
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "metadata must be valid JSON"})

    def test_unset_token_env_fails_closed_500(self):
        """Fresh interpreter without SEA_SPEED_API_TOKEN: 500 fail-closed."""
        env = dict(os.environ)
        env.pop("SEA_SPEED_API_TOKEN", None)
        completed = subprocess.run(
            [sys.executable, "-c", SUBPROCESS_PROBE],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(payload["status"], 500)
        self.assertEqual(payload["detail"], "SEA_SPEED_API_TOKEN is not set")

    # -- b. event ingestion ------------------------------------------------

    def test_event_ingestion_round_trip_persists_to_temp_data_root(self):
        event = {"event_id": "E-582-int-1", "object_type": "boat", "class_name": "boat"}
        snapshot = b"\xff\xd8\xff\xe0fixture-jpeg-bytes-582"
        with self.client() as client:
            response = self.post_event(client, event, snapshot)
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["duplicate"])
        self.assertEqual(body["event"]["event_id"], "E-582-int-1")
        filename = self.store.safe_event_filename("cam1", "E-582-int-1")
        self.assertEqual(body["event"]["snapshot_url"], f"/sea-speed/media/events/{filename}")
        # The snapshot landed in the overridden media tree, byte-for-byte.
        media_path = self.config.EVENTS_MEDIA_DIR / filename
        self.assertTrue(media_path.is_file())
        self.assertEqual(media_path.read_bytes(), snapshot)
        # The feed row landed in the temp state sqlite (real store files).
        feed = self.sqlite_rows(
            self.config.STATE_DB_FILE,
            "SELECT payload_json FROM event_feed WHERE camera_id = ?",
            ("cam1",),
        )
        payloads = [json.loads(row[0]) for row in feed]
        self.assertIn("E-582-int-1", [item["event_id"] for item in payloads])
        # The delivery receipt is stored for the same event_id.
        receipts = self.sqlite_rows(
            self.config.STATE_DB_FILE,
            "SELECT event_id FROM event_receipts WHERE event_id = ?",
            ("E-582-int-1",),
        )
        self.assertEqual([row[0] for row in receipts], ["E-582-int-1"])
        # And the event is served back through the read boundary.
        with self.client() as client:
            feed = client.get("/api/cam1/events")
        self.assertEqual(feed.status_code, 200)
        self.assertIn("E-582-int-1", [e["event_id"] for e in feed.json()["events"]])

    def test_event_ingestion_rejects_malformed_metadata_400(self):
        with self.client() as client:
            response = client.post(
                "/api/cam1/events",
                data={"metadata": "not-json"},
                files={"snapshot": ("snap.jpg", b"bytes", "image/jpeg")},
                headers=AUTH_HEADERS,
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"detail": "metadata must be valid JSON"})

    def test_event_ingestion_requires_snapshot_422(self):
        with self.client() as client:
            response = client.post(
                "/api/cam1/events",
                data={"metadata": json.dumps({"event_id": "E-582-nosnap"})},
                headers=AUTH_HEADERS,
            )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json(), {"detail": "snapshot is required"})

    # -- c. ROI ------------------------------------------------------------

    def test_roi_get_defaults_then_admin_save_round_trip(self):
        polygon = [
            {"x_norm": 0.1, "y_norm": 0.1},
            {"x_norm": 0.5, "y_norm": 0.1},
            {"x_norm": 0.5, "y_norm": 0.8},
        ]
        with self.client() as client:
            empty = client.get("/api/cam1/roi")
            self.assertEqual(empty.status_code, 200)
            self.assertFalse(empty.json()["enabled"])
            self.assertEqual(empty.json()["polygon_norm"], [])
            unauthenticated = client.post(
                "/api/cam1/roi",
                json={"enabled": True, "polygon_norm": polygon},
            )
            self.assertEqual(unauthenticated.status_code, 403)
            self.assertEqual(unauthenticated.json(), {"detail": "Forbidden"})
            saved = client.post(
                "/api/cam1/roi",
                json={"enabled": True, "polygon_norm": polygon},
                headers=ADMIN_HEADERS,
            )
        self.assertEqual(saved.status_code, 200)
        self.assertTrue(saved.json()["enabled"])
        self.assertEqual(saved.json()["polygon_norm"], polygon)
        persisted = json.loads(self.config.ROI_FILE.read_text(encoding="utf-8"))
        self.assertTrue(persisted["enabled"])
        self.assertEqual(persisted["polygon_norm"], polygon)
        with self.client() as client:
            fetched = client.get("/api/cam1/roi")
        self.assertEqual(fetched.status_code, 200)
        self.assertTrue(fetched.json()["enabled"])
        self.assertEqual(fetched.json()["polygon_norm"], polygon)

    def test_roi_rejects_insufficient_polygon_400(self):
        with self.client() as client:
            response = client.post(
                "/api/cam1/roi",
                json={"enabled": True, "polygon_norm": [{"x_norm": 0.1, "y_norm": 0.1}]},
                headers=ADMIN_HEADERS,
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {"detail": "ROI polygon must contain at least 3 points"},
        )

    # -- d. calibration ----------------------------------------------------

    def test_speed_config_finite_gate_and_persistence(self):
        with self.client() as client:
            empty = client.get("/api/cam1/speed-config")
            self.assertEqual(empty.status_code, 200)
            self.assertFalse(empty.json()["enabled"])
            self.assertEqual(empty.json()["kmh_per_px_s"], 0.0)
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(value=value):
                    rejected = self.post_json(
                        client,
                        "/api/cam1/speed-config",
                        {"enabled": True, "kmh_per_px_s": value},
                        ADMIN_HEADERS,
                    )
                    self.assertEqual(rejected.status_code, 400)
                    self.assertEqual(
                        rejected.json(),
                        {"detail": "kmh_per_px_s must be a finite number"},
                    )
            negative = client.post(
                "/api/cam1/speed-config",
                json={"enabled": True, "kmh_per_px_s": -1.0},
                headers=ADMIN_HEADERS,
            )
            self.assertEqual(negative.status_code, 400)
            self.assertEqual(negative.json(), {"detail": "kmh_per_px_s must be >= 0"})
            saved = client.post(
                "/api/cam1/speed-config",
                json={"enabled": True, "kmh_per_px_s": 1.5},
                headers=ADMIN_HEADERS,
            )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["kmh_per_px_s"], 1.5)
        persisted = json.loads(self.config.SPEED_CONFIG_FILE.read_text(encoding="utf-8"))
        self.assertEqual(persisted["kmh_per_px_s"], 1.5)
        self.assertTrue(persisted["enabled"])

    def test_speed_lines_finite_gate_and_persistence(self):
        lines = {
            "enabled": True,
            "distance_m": 57.0,
            "line_a_norm": [{"x_norm": 0.2, "y_norm": 0.2}, {"x_norm": 0.8, "y_norm": 0.2}],
            "line_b_norm": [{"x_norm": 0.2, "y_norm": 0.8}, {"x_norm": 0.8, "y_norm": 0.8}],
        }
        with self.client() as client:
            for value in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(value=value):
                    rejected = self.post_json(
                        client,
                        "/api/cam1/speed-lines",
                        {
                            "enabled": True,
                            "distance_m": value,
                            "line_a_norm": lines["line_a_norm"],
                            "line_b_norm": lines["line_b_norm"],
                        },
                        ADMIN_HEADERS,
                    )
                    self.assertEqual(rejected.status_code, 400)
                    self.assertEqual(
                        rejected.json(),
                        {"detail": "distance_m must be a finite number"},
                    )
            negative = client.post(
                "/api/cam1/speed-lines",
                json={
                    "enabled": True,
                    "distance_m": -1.0,
                    "line_a_norm": lines["line_a_norm"],
                    "line_b_norm": lines["line_b_norm"],
                },
                headers=ADMIN_HEADERS,
            )
            self.assertEqual(negative.status_code, 400)
            self.assertEqual(negative.json(), {"detail": "distance_m must be > 0"})
            saved = client.post(
                "/api/cam1/speed-lines",
                json=lines,
                headers=ADMIN_HEADERS,
            )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["distance_m"], 57.0)
        persisted = json.loads(self.config.SPEED_LINES_FILE.read_text(encoding="utf-8"))
        self.assertEqual(persisted["distance_m"], 57.0)
        self.assertEqual(len(persisted["line_a_norm"]), 2)
        self.assertEqual(len(persisted["line_b_norm"]), 2)

    # -- e. object deletion ------------------------------------------------

    def test_object_delete_requires_admin_and_removes_the_record(self):
        event = {"event_id": "E-582-del-1", "object_type": "boat"}
        with self.client() as client:
            ingested = self.post_event(client, event)
            self.assertEqual(ingested.status_code, 200)
            listing = client.get("/api/objects", params={"camera_id": "cam1"})
            self.assertEqual(listing.status_code, 200)
            self.assertIn(
                "E-582-del-1",
                [item["object_id"] for item in listing.json()["objects"]],
            )
            forbidden = client.delete("/api/objects/E-582-del-1")
            self.assertEqual(forbidden.status_code, 403)
            deleted = client.delete("/api/objects/E-582-del-1", headers=ADMIN_HEADERS)
        self.assertEqual(deleted.status_code, 200)
        self.assertTrue(deleted.json()["ok"])
        self.assertEqual(deleted.json()["object_id"], "E-582-del-1")
        rows = self.sqlite_rows(
            self.config.OBJECTS_DB_FILE,
            "SELECT deleted_at FROM objects WHERE object_id = ?",
            ("E-582-del-1",),
        )
        self.assertEqual(len(rows), 1)
        self.assertIsNotNone(rows[0][0])  # soft delete recorded in the temp db
        with self.client() as client:
            gone = client.get("/api/objects/E-582-del-1")
            self.assertEqual(gone.status_code, 404)
            self.assertEqual(gone.json(), {"detail": "Object not found"})
            repeat = client.delete("/api/objects/E-582-del-1", headers=ADMIN_HEADERS)
        self.assertEqual(repeat.status_code, 404)
        self.assertEqual(repeat.json(), {"detail": "Object not found"})

    # -- f. worker control (fail-closed, no real worker) -------------------

    def test_worker_control_fails_closed_on_unreachable_origin(self):
        # WORKER_CONTROL_URL points at loopback; the app's own origin guard
        # rejects it before any connection is attempted (503, no network).
        with self.client() as client:
            response = client.get("/api/worker/control", headers=ADMIN_HEADERS)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Worker control origin is invalid"})

    def test_worker_control_requires_trusted_identity(self):
        # Strict edge mode (#520): EDGE_AUTH_SECRET is set in this harness, so
        # a request without the edge-injected header is 403 before any
        # username handling — a forged X-Authentik-Username reveals nothing.
        with self.client() as client:
            response = client.get("/api/worker/control")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "Forbidden"})


if __name__ == "__main__":
    unittest.main()
