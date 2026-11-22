"""RED HTTP tests for MostDef2000/sea-speed#689 — non-object JSON metadata.

Issue #689: the ``metadata`` form field is parsed with ``json.loads(metadata)``
at four call sites in ``api/app/main.py``. Two already reject a parsed value
that is not a JSON object (400 "metadata must be a JSON object"):

* line 387 ``post_cam1_passage`` (POST /api/cam1/passages);
* line 1066 ``api_post_crossing`` (POST /api/analytics/{camera_id}/crossings).

The other two LACK the check, so a parsed non-object crashes the handler:

* line 602 ``post_analytics_state`` (POST /api/analytics/{camera_id}/state):
  ``data["camera_id"] = camera_id`` runs right after the parse and raises
  ``TypeError`` for ``[]`` / ``null`` / ``42`` / ``"str"`` -> unhandled -> 500;
* line 667 ``post_analytics_event`` (POST /api/analytics/{camera_id}/events):
  the #587 nonfinite scan (line 674) returns None for every non-object, then
  ``event.get("event_id")`` (line 677) raises ``AttributeError`` for the same
  four payloads -> unhandled -> 500.

RED/GREEN status on this base (94bce64) — the fix must flip RED to green and
leave GREEN untouched:

* RED — ``test_state_rejects_non_object_metadata_*`` and
  ``test_events_rejects_non_object_metadata_*`` (4 subTests each): observed
  status 500 (the TypeError/AttributeError above), wanted 400/422;
* RED — ``test_every_json_loads_metadata_site_is_dict_checked``: two of the
  four ``json.loads(metadata)`` sites (lines 602, 667) have no nearby
  ``isinstance(<var>, dict)`` guard;
* GREEN today, kept as regression guards — malformed JSON still returns 400
  "metadata must be valid JSON" on both endpoints (existing ``except``
  clause), a valid JSON object still round-trips (state persisted, event
  delivered), and the 403 permission boundary is intact.

Auth: the same authenticated-worker pattern as
``tests/test_api_http_integration.py`` (AUTH_HEADERS, line 116; env fixture,
line 170) and ``tests/test_587_nonfinite_residual_paths.py`` (AUTH_HEADERS,
line 151; env fixture, line 198) — the ``SEA_SPEED_API_TOKEN`` fixture env var
plus ``Authorization: Bearer <fixture>``, checked by the REAL ``require_auth``
(api/app/identity.py:92). No auth bypass, no stubbed identity.

``TestClient(..., raise_server_exceptions=False)`` (repo precedent:
tests/test_587_nonfinite_residual_paths.py:243) so the production 500 is
observed as an HTTP response instead of being re-raised in the test process.

One-process battery contract (identical to tests/test_587_...): guarded-
optional fastapi/httpx probe; ``MANAGED_MODULE_NAMES`` and
``API_APP_MODULE_NAMES`` evicted by the class cleanup when absent at
setUpClass, so the AST/exec harnesses and the later HTTP class re-import fresh.

No network, no sleeps: every request goes through the in-process TestClient
against a disposable temp ``SEA_SPEED_BASE_DIR``.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]

# Module names the guarded imports below may introduce into sys.modules when
# fastapi is installed. One-process battery contract (same rationale as
# tests/test_api_http_integration.py / tests/test_587_nonfinite_residual_paths.py):
# the AST/exec harnesses stub exactly these names only while they are ABSENT
# from sys.modules, so the class cleanup evicts the ones this module cached —
# restoring the setUpClass-time world instead of leaking real modules into
# the exec harnesses that follow. Names present at setUpClass are kept.
MANAGED_MODULE_NAMES = (
    "fastapi",
    "fastapi.staticfiles",
    "fastapi.responses",
)
# PREEXISTING_MODULES is captured per-class in setUpClass immediately
# before the app import — not at module import time, when the discovery-
# ordered module world can differ from the runtime world (see setUpClass).

# The package-context app import below caches the whole api.app.* module tree
# in sys.modules, bound to THIS class's temp SEA_SPEED_BASE_DIR (config reads
# the env at import time). Evicting the api.app.* names this import introduced
# lets the later sibling HTTP class (tests/test_api_http_integration.py) and
# any fresh importer re-import with their own env overrides instead of reusing
# a stale cached api.app.main bound to this class's cleaned-up temp dir.
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
# PREEXISTING_API_MODULES is likewise captured in setUpClass: a module-
# level importer from an earlier-discovered test file would otherwise bias
# this discovery-time snapshot and leak a partial api.app.* tree.

try:
    import fastapi  # noqa: F401  # guarded-optional probe (CI has no fastapi)
    from fastapi.testclient import TestClient

    import httpx  # noqa: F401  # TestClient's HTTP transport dependency
except ModuleNotFoundError:  # CI today: fastapi/httpx not installed
    HTTP_TESTS_ENABLED = False
else:
    HTTP_TESTS_ENABLED = True

# Gitleaks-safe fixture values (same convention as the #582/#587 files):
# low-entropy throwaway constants for a disposable temp environment, never
# real secrets.
BEARER_FIXTURE = "integration-fixture-689"
EDGE_HEADER_FIXTURE = "edge-fixture-689"
WORKER_TOKEN_FIXTURE = "worker-fixture-689"
ADMIN_USER_FIXTURE = "fixture-admin-689"
# 40 hex chars (deployed_source_commit validates SHA_RE), minimal entropy.
DEPLOYED_COMMIT_FIXTURE = "c" * 40

# Loopback is rejected by the app's own worker_control_origin guard before
# any connection is attempted: deterministic fail-closed, zero network.
UNREACHABLE_WORKER_CONTROL_URL = "http://127.0.0.1:19003"

# Worker authentication accepted by the real require_auth (identity.py:92)
# while SEA_SPEED_API_TOKEN is set to the fixture value.
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

# The four non-object JSON documents from the issue: each parses cleanly via
# json.loads (so the existing "must be valid JSON" except clause does NOT
# fire) but is not a JSON object. Raw form-field values, not Python objects.
NON_OBJECT_METADATA = (
    ("array", "[]"),
    ("null", "null"),
    ("number", "42"),
    ("string", '"str"'),
)

# Not JSON at all — the existing except clause turns this into a 400 today.
MALFORMED_METADATA = "{not json"


@unittest.skipUnless(
    HTTP_TESTS_ENABLED,
    "fastapi/httpx are not installed (CI installs only pyyaml; the HTTP "
    "integration tests run where the declared pins are installed)",
)
class MetadataJsonTypeHttpTests(unittest.TestCase):
    """Real-app HTTP boundary tests for issue #689 against a temp data root."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        temp = tempfile.TemporaryDirectory(prefix="sea-speed-689-http-")
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
        # Snapshot the exact sys.modules entries immediately before this
        # class's imports: sibling cleanups (tests/test_587_...) run between
        # discovery and here, so only the runtime snapshot matches the world
        # the cleanup must restore. Present names are kept (the import below
        # reuses them); absent names it introduces are evicted, so the later
        # HTTP class and the exec harnesses see exactly the state found here.
        cls.preexisting_modules = frozenset(
            name for name in MANAGED_MODULE_NAMES if name in sys.modules
        )
        cls.preexisting_api_modules = frozenset(
            name for name in API_APP_MODULE_NAMES if name in sys.modules
        )
        # Fresh package-context import: config reads the overrides above at
        # module level, so the whole data/media tree lands in the temp dir.
        cls.addClassCleanup(cls._restore_modules)
        cls.app_module = importlib.import_module("api.app.main")

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
            if name not in cls.preexisting_modules:
                sys.modules.pop(name, None)
        for name in API_APP_MODULE_NAMES:
            if name not in cls.preexisting_api_modules:
                sys.modules.pop(name, None)

    # -- helpers -----------------------------------------------------------

    def client(self):
        # raise_server_exceptions=False: observe the production 500 for the
        # unguarded non-object sites instead of re-raising in the test
        # process (repo precedent: tests/test_587_nonfinite_residual_paths.py).
        return TestClient(self.app_module.app, raise_server_exceptions=False)

    def post_state(self, client: Any, raw_metadata: str) -> Any:
        # State ingestion is a form POST; the overlay file is optional.
        return client.post(
            "/api/analytics/cam1/state",
            data={"metadata": raw_metadata},
            headers=AUTH_HEADERS,
        )

    def post_event(self, client: Any, raw_metadata: str, snapshot: bytes = b"fixture-jpeg-689") -> Any:
        # Event ingestion is a multipart form: metadata is a raw JSON string,
        # snapshot is a file (required by the handler AFTER metadata parsing).
        return client.post(
            "/api/analytics/cam1/events",
            data={"metadata": raw_metadata},
            files={"snapshot": ("snap.jpg", snapshot, "image/jpeg")},
            headers=AUTH_HEADERS,
        )

    def assert_client_rejection(self, response: Any, label: str) -> None:
        """400/422 — never the 500 the unguarded sites produce today."""
        self.assertIn(
            response.status_code,
            (400, 422),
            f"{label}: status={response.status_code} body={response.text!r}",
        )
        self.assertNotIn("traceback", response.text.lower(), f"{label}: body={response.text!r}")

    # -- state endpoint (main.py:602, UNGUARDED today) ---------------------

    def test_state_rejects_non_object_metadata_400_or_422(self):
        # RED today: TypeError at main.py:605 (data["camera_id"] = camera_id)
        # for every parsed non-object -> unhandled -> 500. Desired: 400/422.
        for label, raw in NON_OBJECT_METADATA:
            with self.subTest(label=label):
                with self.client() as client:
                    response = self.post_state(client, raw)
                self.assert_client_rejection(response, f"state {label}")

    def test_state_rejects_malformed_json_400_or_422(self):
        # GREEN today (existing except clause at main.py:603-604) — the fix
        # must not regress the "must be valid JSON" rejection.
        with self.client() as client:
            response = self.post_state(client, MALFORMED_METADATA)
        self.assert_client_rejection(response, "state malformed")

    def test_state_valid_object_persists_state_and_keeps_auth_boundary(self):
        # GREEN today — the fix must keep the happy path and permissions.
        payload = json.dumps({"frame_no": 7})
        with self.client() as client:
            # Permission boundary: no Authorization header -> 403, no write.
            denied = client.post(
                "/api/analytics/cam1/state",
                data={"metadata": payload},
            )
            self.assertEqual(denied.status_code, 403, denied.text)
            self.assertEqual(denied.json(), {"detail": "Forbidden"})
            response = self.post_state(client, payload)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["state"]["camera_id"], "cam1")
        self.assertEqual(body["state"]["frame_no"], 7)
        self.assertTrue(body["state"]["updated_at"])
        # Side effect: the state round-trips through the read boundary.
        with self.client() as client:
            fetched = client.get("/api/analytics/cam1/state")
        self.assertEqual(fetched.status_code, 200, fetched.text)
        self.assertEqual(fetched.json()["frame_no"], 7)

    # -- events endpoint (main.py:667, UNGUARDED today) --------------------

    def test_events_rejects_non_object_metadata_400_or_422(self):
        # RED today: the #587 scan (main.py:674) passes every non-object,
        # then event.get(...) at main.py:677 raises AttributeError ->
        # unhandled -> 500. Desired: 400/422.
        for label, raw in NON_OBJECT_METADATA:
            with self.subTest(label=label):
                with self.client() as client:
                    response = self.post_event(client, raw)
                self.assert_client_rejection(response, f"events {label}")

    def test_events_rejects_malformed_json_400_or_422(self):
        # GREEN today (existing except clause at main.py:668-669) — the fix
        # must not regress the "must be valid JSON" rejection.
        with self.client() as client:
            response = self.post_event(client, MALFORMED_METADATA)
        self.assert_client_rejection(response, "events malformed")

    def test_events_valid_object_delivers_event_and_keeps_auth_boundary(self):
        # GREEN today — the fix must keep delivery and permissions.
        event = {"event_id": "E-689-valid-1", "object_type": "boat", "class_name": "boat"}
        payload = json.dumps(event)
        with self.client() as client:
            # Permission boundary: no Authorization header -> 403, no write.
            denied = client.post(
                "/api/analytics/cam1/events",
                data={"metadata": payload},
                files={"snapshot": ("snap.jpg", b"denied", "image/jpeg")},
            )
            self.assertEqual(denied.status_code, 403, denied.text)
            self.assertEqual(denied.json(), {"detail": "Forbidden"})
            response = self.post_event(client, payload)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertTrue(body["ok"])
        self.assertFalse(body["duplicate"])
        self.assertEqual(body["event"]["event_id"], "E-689-valid-1")
        # Side effect: the event is served back through the read boundary.
        with self.client() as client:
            feed = client.get("/api/analytics/cam1/events")
        self.assertEqual(feed.status_code, 200, feed.text)
        self.assertIn(
            "E-689-valid-1",
            [item["event_id"] for item in feed.json()["events"]],
        )


class MetadataJsonLoadsSourceGuardTests(unittest.TestCase):
    """Source-level guard: every json.loads(metadata) site is dict-checked.

    Pure stdlib line scan of api/app/main.py (no AST dependency, no fastapi
    needed — runs even where the HTTP tests skip). RED today: the sites at
    lines 602 (state) and 667 (events) parse without a nearby
    ``isinstance(<var>, dict)`` rejection, while lines 387 and 1066 are
    guarded 3 lines below the parse.
    """

    MAIN_SOURCE = ROOT / "api" / "app" / "main.py"
    # ``<var> = json.loads(metadata)`` — the four known call sites.
    SITE_RE = re.compile(r"(\w+)\s*=\s*json\.loads\(\s*metadata\s*\)")
    # The guarded sites put the isinstance check 3 lines below the parse;
    # 8 lines tolerates the intervening except/raise/comment block without
    # letting an unguarded handler drift past the guard.
    GUARD_WINDOW = 8

    def test_every_json_loads_metadata_site_is_dict_checked(self):
        lines = self.MAIN_SOURCE.read_text(encoding="utf-8").splitlines()
        sites = []
        for index, line in enumerate(lines):
            match = self.SITE_RE.search(line)
            if match is not None:
                sites.append((index + 1, match.group(1)))  # 1-based line no.
        # Anti-vacuity: the four known sites must be found — if the parse idiom
        # changes, this fails loudly instead of the guard passing on 0 sites.
        self.assertGreaterEqual(
            len(sites),
            4,
            f"expected the four known json.loads(metadata) sites, found {len(sites)}: {sites}",
        )
        unguarded = []
        for lineno, var in sites:
            check = re.compile(rf"isinstance\(\s*{re.escape(var)}\s*,\s*dict\s*\)")
            window = lines[lineno : lineno + self.GUARD_WINDOW]  # lines AFTER the call
            if not any(check.search(candidate) for candidate in window):
                unguarded.append((lineno, var))
        self.assertEqual(
            unguarded,
            [],
            "json.loads(metadata) sites without a nearby "
            f"isinstance(<var>, dict) rejection within {self.GUARD_WINDOW} lines: {unguarded}",
        )


if __name__ == "__main__":
    unittest.main()
