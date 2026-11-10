"""Behavioral RED suite for issue #635 — camera preview TTL-renew.

SDD trio: specs/635-preview-ttl-renew/{spec,plan,tasks}.md. Pins the DESIRED
behavior of the #635 design on the REAL FastAPI app through the real HTTP
boundary (TestClient harness, same pattern as
tests/test_api_http_integration.py):

* T-1  a session-bound route ``GET /media/camera-preview/{session_id}/{filename}``
       serves the active session's HLS artifacts and renews the session on
       every successful fetch (sliding ``now + CAMERA_PREVIEW_TTL_SEC``), so
       continuous fetches keep the same session_id/pid alive across several
       original TTL boundaries (AC-001).
* T-2  renewal persistence is debounced: two fetches < 5 s apart persist at
       most one expiry extension; expires_epoch and expires_at move together;
       session_id/started_at/ttl_sec are untouched.
* T-3  status routes (GET /api/cameras, GET /api/cameras/preview) and snapshot
       read/commit NEVER renew (AC-003).
* T-4  after the inactivity window lapses the media route 404s, the session is
       terminated (state {}, ffmpeg killed, media removed) and cannot be
       resurrected (AC-003).
* T-5  a lifespan-managed sweeper terminates an expired session with zero HTTP
       traffic, survives a failed iteration (retries on the next tick) and
       shutdown terminates any active preview (AC-002, R-5).
* T-6  wrong/malformed session ids, path traversal, unsupported filenames and
       missing files 404 without renewal and without leaking files outside the
       session dir (AC-004).
* T-7  every preview media response (200/206/404) carries Cache-Control:
       no-store (R-6).
* T-8  unrelated media paths keep flowing through the /media StaticFiles mount
       (R-1 compatibility).
* T-10 terminate-first: a fetch for a replaced (stale) session id 404s and
       cannot renew (AC-005).

On the current base (450b317d) the feature is absent: the media path is served
by the bare /media StaticFiles mount (no session binding, no renewal, no
no-store, no filename allowlist) and there is no lifespan/sweeper. The feature
tests therefore FAIL for the documented current-vs-desired reason; the guard
tests (T-3, T-8, T-10 and the green sub-cases of T-6) pass on base and must
keep passing after the implementation. No test is weakened, skipped or
xfailed.

Time control: the preview code reads ``time.time()`` for expiry arithmetic.
The tests install a controllable clock shim on the ``time`` attribute of the
camera_preview/main modules (delegating monotonic/sleep to the real time
module) so a test can advance the preview's notion of "now" across TTL
boundaries without real waiting; CAMERA_PREVIEW_TTL_SEC is monkeypatched to 30
on the module-level names the implementation reads, and the sweeper interval to
0.05 s for the one real lifespan test. No test sleeps more than 2 s; no real
ffmpeg (a fake executable named ``ffmpeg`` writes the HLS artifacts and stays
alive until SIGTERM) and no network.

One-process battery contract (same as tests/test_api_http_integration.py and
tests/test_587_nonfinite_residual_paths.py): fastapi/httpx are
guarded-optional; the class cleanup evicts the fastapi names and the api.app.*
package names this import introduced so the exec harnesses and the sibling
package importers see the original sys.modules.
"""

from __future__ import annotations

import importlib
import json
import os
import signal
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]

# Module names the guarded imports below may introduce into sys.modules when
# fastapi is installed. One-process battery contract (same rationale as
# tests/test_api_http_integration.py): the class cleanup evicts the ones this
# module cached that were not preexisting.
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
# the env at import time). This file sorts AFTER tests/test_api_http_integration.py
# (alphabetical battery order), whose class leaves api.app.* cached bound to
# ITS (already cleaned up) temp dir — so setUpClass evicts the names before
# importing, and the class cleanup evicts the names this import introduced so
# later importers re-import fresh. Names that preexisted are never touched.
API_APP_MODULE_NAMES = (
    "api",
    "api.app",
    "api.app.analytics",
    "api.app.camera_preview",
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
BEARER_FIXTURE = "integration-fixture-635"
EDGE_HEADER_FIXTURE = "edge-fixture-635"
WORKER_TOKEN_FIXTURE = "worker-fixture-635"
ADMIN_USER_FIXTURE = "fixture-admin-635"
# 40 hex chars (deployed_source_commit validates SHA_RE), minimal entropy.
DEPLOYED_COMMIT_FIXTURE = "c" * 40

# Loopback is rejected by the app's own worker_control_origin guard before any
# connection is attempted: deterministic fail-closed, zero network.
UNREACHABLE_WORKER_CONTROL_URL = "http://127.0.0.1:19003"

# Identity headers accepted while EDGE_AUTH_SECRET is set to the fixture
# value; SEA_SPEED_ADMIN_USERS resolves the user to the admin role (>= the
# operator minimum the preview start/stop routes require).
ADMIN_HEADERS = {
    "X-Authentik-Username": ADMIN_USER_FIXTURE,
    "X-Sea-Speed-Edge-Auth": EDGE_HEADER_FIXTURE,
}

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
    "SEA_SPEED_CAMERA_PREVIEW_FFMPEG",
    "SEA_SPEED_CAMERA_PREVIEW_CATALOG",
)

# Fake ffmpeg (issue #635 test boundary): the ONLY permitted stand-in for the
# transcoder. In preview mode (args carry "-f hls") it writes the session's
# HLS artifacts (index.m3u8 with #EXTM3U — what start_camera_preview_locked
# waits for — plus init.mp4 and two segments) and then stays alive until
# SIGTERM, so camera_preview_pid_matches sees a live process whose cmdline
# carries the binary name and the expected playlist path. In snapshot-extract
# mode (no "-f hls") it exits 0 immediately without producing a JPEG, so the
# last-good quality gate rejects the candidate fast (422, no 8 s timeout).
FAKE_FFMPEG_SOURCE = '''\
#!/usr/bin/env python3
import os
import signal
import sys
import time

def main():
    args = sys.argv[1:]
    playlist = None
    for arg in args:
        if arg.endswith(".m3u8"):
            playlist = arg
    preview = "-f" in args and "hls" in args
    if preview and playlist:
        out_dir = os.path.dirname(playlist)
        with open(playlist, "w", encoding="utf-8") as handle:
            handle.write(
                "#EXTM3U\\n#EXT-X-VERSION:3\\n#EXT-X-TARGETDURATION:1\\n"
                "#EXT-X-MEDIA-SEQUENCE:0\\n#EXTINF:1.000000,\\nsegment_00000.m4s\\n"
                "#EXTINF:1.000000,\\nsegment_00001.m4s\\n"
            )
        with open(os.path.join(out_dir, "init.mp4"), "wb") as handle:
            handle.write(b"fake-init-mp4-635")
        for index in (0, 1):
            with open(os.path.join(out_dir, "segment_%05d.m4s" % index), "wb") as handle:
                handle.write(b"fake-segment-635-%d" % index)
    signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(0))
    if not preview:
        return 0
    while True:
        time.sleep(0.2)
    return 0

if __name__ == "__main__":
    sys.exit(main())
'''

# The preview catalog: two RFC1918 relay sources matching the camera ids
# (validate_camera_preview_source requires rtsp://<rfc1918>:<port>/preview_<id>).
PREVIEW_CATALOG = {
    "schema": "sea_speed_camera_preview_catalog_v1",
    "cameras": [
        {"camera_id": "cam-a", "display_name": "Cam A", "source": "rtsp://192.168.1.50:554/preview_cam-a"},
        {"camera_id": "cam-b", "display_name": "Cam B", "source": "rtsp://192.168.1.51:554/preview_cam-b"},
    ],
}

# The TTL the tests run with: small enough to reason about boundaries, large
# enough that the 5 s renewal debounce stays meaningful.
TEST_TTL_SEC = 30
# Sweeper tick for the one real lifespan test: fast enough for a 2 s polling
# window, slow enough to be a real loop.
TEST_SWEEP_INTERVAL_SEC = 0.05

_SENTINEL = object()


class _ShimClock:
    """Controllable stand-in for the ``time`` module reference.

    The camera preview code reads ``time.time()`` for expiry arithmetic and
    ``time.monotonic()``/``time.sleep()`` for process management. The shim
    delegates everything to the real time module except ``time()``, which
    returns the test-controlled ``now`` — so a test can advance the preview's
    notion of "now" across TTL boundaries without real waiting.
    """

    def __init__(self, real_time_module: Any) -> None:
        self._real = real_time_module
        self.now = real_time_module.time()

    def time(self) -> float:
        return self.now

    def __call__(self) -> float:
        # Also works when a module bound ``from time import time`` and the
        # shim replaced the function object directly.
        return self.now

    def monotonic(self) -> float:
        return self._real.monotonic()

    def sleep(self, seconds: float) -> None:
        return self._real.sleep(seconds)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._real, name)


@unittest.skipUnless(
    HTTP_TESTS_ENABLED,
    "fastapi/httpx are not installed (CI installs only pyyaml; the HTTP "
    "integration tests run where the declared pins are installed)",
)
class CameraPreviewTtlRenewTests(unittest.TestCase):
    """Behavioral pins for the #635 preview TTL-renew design (RED on base)."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        temp = tempfile.TemporaryDirectory(prefix="sea-speed-635-http-")
        cls.addClassCleanup(temp.cleanup)
        base_dir = Path(temp.name)
        deployed_file = base_dir / "deploy-state" / "current-release"
        deployed_file.parent.mkdir(parents=True, exist_ok=True)
        deployed_file.write_text(DEPLOYED_COMMIT_FIXTURE + "\n", encoding="utf-8")
        fakebin = base_dir / "fakebin"
        fakebin.mkdir()
        fake_ffmpeg = fakebin / "ffmpeg"
        fake_ffmpeg.write_text(FAKE_FFMPEG_SOURCE, encoding="utf-8")
        fake_ffmpeg.chmod(0o755)
        catalog_file = base_dir / "camera-preview-catalog.json"
        catalog_file.write_text(json.dumps(PREVIEW_CATALOG), encoding="utf-8")
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
                "SEA_SPEED_CAMERA_PREVIEW_FFMPEG": str(fake_ffmpeg),
                "SEA_SPEED_CAMERA_PREVIEW_CATALOG": str(catalog_file),
            }
        )
        # deployed_source_commit prefers this env var over the commit file;
        # remove it so the fixture file is the authoritative source here.
        os.environ.pop("SEA_SPEED_SOURCE_COMMIT", None)
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        cls.addClassCleanup(cls._restore_modules)
        cls._live_pids: List[int] = []
        cls.addClassCleanup(cls._kill_tracked_pids)
        # The sibling HTTP-integration class (test_api_http_integration.py,
        # which sorts before this file) leaves api.app.* cached in
        # sys.modules bound to ITS temp dir; evict so this import binds to
        # THIS class's overrides.
        for name in API_APP_MODULE_NAMES:
            sys.modules.pop(name, None)
        # Fresh package-context import: config reads the overrides above at
        # module level, so the whole data/media tree lands in the temp dir.
        cls.app_module = importlib.import_module("api.app.main")
        cls.config = cls.app_module.config
        cls.camera_preview = cls.app_module.camera_preview

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

    @classmethod
    def _kill_tracked_pids(cls) -> None:
        for pid in cls._live_pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass

    # -- helpers -----------------------------------------------------------

    def client(self):
        return TestClient(self.app_module.app)

    def start_preview(self, client: Any, camera_id: str = "cam-a") -> Dict[str, Any]:
        response = client.post(
            f"/api/cameras/{camera_id}/preview/start", headers=ADMIN_HEADERS
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["preview"]

    def fetch_media(self, client: Any, session_id: str, filename: str) -> Any:
        return client.get(f"/media/camera-preview/{session_id}/{filename}")

    def read_state(self) -> Dict[str, Any]:
        path = self.config.CAMERA_PREVIEW_STATE_FILE
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _track_pid(self, pid: int) -> None:
        self.__class__._live_pids.append(pid)

    def process_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        # A zombie (killed, not yet reaped) is dead for every purpose here:
        # the app's own pid_matches check already treats it as gone (its
        # /proc/<pid>/cmdline is empty).
        try:
            stat = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8")
        except OSError:
            return False
        return stat.rsplit(")", 1)[1].split()[0] != "Z"

    def wait_until(self, predicate, timeout: float = 2.0, interval: float = 0.05) -> bool:
        deadline = time.monotonic() + timeout
        while True:
            if predicate():
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(interval)

    def _install_clock(self) -> _ShimClock:
        shim = _ShimClock(time)
        patched = []
        for module in (self.camera_preview, self.app_module):
            prior = getattr(module, "time", None)
            if prior is not None:
                module.time = shim
                patched.append((module, prior))
        self.addCleanup(self._restore_clock, patched)
        return shim

    @staticmethod
    def _restore_clock(patched: List[tuple]) -> None:
        for module, prior in patched:
            module.time = prior

    def _patch_const(self, name: str, value: Any) -> None:
        patched = []
        for module in (self.config, self.camera_preview, self.app_module):
            prior = getattr(module, name, _SENTINEL)
            setattr(module, name, value)
            patched.append((module, name, prior))
        self.addCleanup(self._restore_const, patched)

    @staticmethod
    def _restore_const(patched: List[tuple]) -> None:
        for module, name, prior in patched:
            if prior is _SENTINEL:
                delattr(module, name)
            else:
                setattr(module, name, prior)

    def _assert_no_store(self, response: Any) -> None:
        header = response.headers.get("cache-control")
        self.assertIsNotNone(
            header, "Cache-Control must be set on preview media responses"
        )
        self.assertEqual(
            header.split(",")[0].strip(), "no-store", f"got {header!r}"
        )

    # -- T-1: renewal across TTL boundaries (AC-001) ------------------------

    def test_media_fetches_renew_the_session_across_ttl_boundaries(self):
        shim = self._install_clock()
        self._patch_const("CAMERA_PREVIEW_TTL_SEC", TEST_TTL_SEC)
        with self.client() as client:
            preview = self.start_preview(client)
            session_id = preview["session_id"]
            t0 = shim.now
            state = self.read_state()
            pid = state["pid"]
            self._track_pid(pid)
            self.assertAlmostEqual(state["expires_epoch"], t0 + TEST_TTL_SEC, delta=0.001)
            # Boundary 1: 1 s before the original expiry, fetch each artifact
            # kind — each successful fetch must slide the expiry forward.
            shim.now = t0 + TEST_TTL_SEC - 1
            for filename in ("index.m3u8", "init.mp4", "segment_00000.m4s"):
                with self.subTest(filename=filename):
                    response = self.fetch_media(client, session_id, filename)
                    self.assertEqual(response.status_code, 200, response.text)
            state = self.read_state()
            self.assertEqual(state["session_id"], session_id)
            self.assertEqual(state["pid"], pid)
            self.assertGreater(
                state["expires_epoch"],
                t0 + TEST_TTL_SEC + 5,
                "fetches near the original expiry must renew it (sliding window)",
            )
            # Boundary 2: past the original TTL boundary, fetch again — the
            # renewed session must still be alive and renew again.
            shim.now = t0 + TEST_TTL_SEC * 2 - 2
            response = self.fetch_media(client, session_id, "index.m3u8")
            self.assertEqual(response.status_code, 200, response.text)
            state = self.read_state()
            self.assertEqual(state["session_id"], session_id)
            self.assertEqual(state["pid"], pid)
            self.assertGreater(
                state["expires_epoch"],
                t0 + TEST_TTL_SEC * 2 + 5,
                "the session must survive a second original TTL boundary",
            )
            # The status route still sees the same live session.
            status = client.get("/api/cameras/preview")
            self.assertEqual(status.status_code, 200)
            self.assertEqual(status.json()["active"]["session_id"], session_id)

    # -- T-2: renewal debounce ----------------------------------------------

    def test_close_fetches_persist_at_most_one_renewal_and_fields_move_together(self):
        shim = self._install_clock()
        self._patch_const("CAMERA_PREVIEW_TTL_SEC", TEST_TTL_SEC)
        with self.client() as client:
            preview = self.start_preview(client)
            session_id = preview["session_id"]
            t0 = shim.now
            self._track_pid(self.read_state()["pid"])
            # Two fetches 0.5 s apart, once the persisted expiry has aged.
            shim.now = t0 + TEST_TTL_SEC - 1
            first = self.fetch_media(client, session_id, "index.m3u8")
            self.assertEqual(first.status_code, 200, first.text)
            state = self.read_state()
            first_expiry = state["expires_epoch"]
            self.assertAlmostEqual(
                first_expiry,
                t0 + TEST_TTL_SEC * 2 - 1,
                delta=1.0,
                msg="the first fetch must persist one renewal (now + TTL)",
            )
            shim.now = t0 + TEST_TTL_SEC - 0.5
            second = self.fetch_media(client, session_id, "init.mp4")
            self.assertEqual(second.status_code, 200, second.text)
            state = self.read_state()
            self.assertAlmostEqual(
                state["expires_epoch"],
                first_expiry,
                delta=0.5,
                msg="a fetch within the 5 s debounce must not persist another extension",
            )
            # expires_epoch and expires_at move together (same instant).
            expires_at = datetime.fromisoformat(state["expires_at"]).timestamp()
            self.assertAlmostEqual(expires_at, state["expires_epoch"], delta=1.0)
            # Identity is untouched by renewal.
            self.assertEqual(state["session_id"], session_id)
            self.assertEqual(state["ttl_sec"], TEST_TTL_SEC)

    # -- T-3: status/snapshot routes never renew (AC-003) -------------------

    def test_status_and_snapshot_routes_never_renew(self):
        shim = self._install_clock()
        self._patch_const("CAMERA_PREVIEW_TTL_SEC", TEST_TTL_SEC)
        with self.client() as client:
            preview = self.start_preview(client)
            session_id = preview["session_id"]
            t0 = shim.now
            self._track_pid(self.read_state()["pid"])
            baseline = self.read_state()["expires_epoch"]
            shim.now = t0 + 10
            for url in ("/api/cameras", "/api/cameras/preview"):
                with self.subTest(url=url):
                    response = client.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json()["active"]["session_id"], session_id)
            snapshot = client.get("/api/cameras/cam-a/snapshot")
            self.assertEqual(snapshot.status_code, 404)
            commit = client.post(
                f"/api/cameras/cam-a/snapshot/commit?session_id={session_id}",
                headers=ADMIN_HEADERS,
            )
            # The fake ffmpeg cannot pass the last-good quality gate: 422 —
            # the point is that the attempt never renews the session.
            self.assertEqual(commit.status_code, 422, commit.text)
            state = self.read_state()
            self.assertEqual(state["session_id"], session_id)
            self.assertAlmostEqual(
                state["expires_epoch"],
                baseline,
                delta=0.001,
                msg="status/snapshot routes must never extend the expiry",
            )

    # -- T-4: expiry termination, no resurrection (AC-003) ------------------

    def test_lapsed_session_media_404s_and_cannot_be_resurrected(self):
        shim = self._install_clock()
        self._patch_const("CAMERA_PREVIEW_TTL_SEC", TEST_TTL_SEC)
        with self.client() as client:
            preview = self.start_preview(client)
            session_id = preview["session_id"]
            t0 = shim.now
            pid = self.read_state()["pid"]
            self._track_pid(pid)
            shim.now = t0 + TEST_TTL_SEC + 1  # the window lapsed; no fetches
            response = self.fetch_media(client, session_id, "index.m3u8")
            self.assertEqual(
                response.status_code, 404, "an expired session must not serve media"
            )
            self.assertEqual(self.read_state(), {}, "the expired session must be terminated")
            self.assertFalse(self.process_alive(pid))
            self.assertFalse((self.config.CAMERA_PREVIEW_DIR / session_id).exists())
            # No resurrection through the media route or the status route.
            again = self.fetch_media(client, session_id, "index.m3u8")
            self.assertEqual(again.status_code, 404)
            status = client.get("/api/cameras/preview")
            self.assertIsNone(status.json()["active"])

    # -- T-5: sweeper (AC-002, R-5) ------------------------------------------

    def test_sweeper_terminates_expired_session_without_http_traffic(self):
        shim = self._install_clock()
        self._patch_const("CAMERA_PREVIEW_TTL_SEC", TEST_TTL_SEC)
        self._patch_const("CAMERA_PREVIEW_SWEEP_INTERVAL_SEC", TEST_SWEEP_INTERVAL_SEC)
        with self.client() as client:  # lifespan: the sweeper task runs
            preview = self.start_preview(client)
            session_id = preview["session_id"]
            t0 = shim.now
            pid = self.read_state()["pid"]
            self._track_pid(pid)
            shim.now = t0 + TEST_TTL_SEC + 1  # abandoned: no further HTTP traffic
            cleaned = self.wait_until(lambda: self.read_state() == {})
            self.assertTrue(
                cleaned,
                "the sweeper must terminate the expired session without HTTP traffic",
            )
            self.assertFalse(self.process_alive(pid))
            self.assertFalse((self.config.CAMERA_PREVIEW_DIR / session_id).exists())

    def test_sweeper_retries_after_a_failed_iteration(self):
        shim = self._install_clock()
        self._patch_const("CAMERA_PREVIEW_TTL_SEC", TEST_TTL_SEC)
        self._patch_const("CAMERA_PREVIEW_SWEEP_INTERVAL_SEC", TEST_SWEEP_INTERVAL_SEC)
        state_file = self.config.CAMERA_PREVIEW_STATE_FILE
        with self.client() as client:
            preview = self.start_preview(client)
            session_id = preview["session_id"]
            t0 = shim.now
            pid = self.read_state()["pid"]
            self._track_pid(pid)
            # Break the state surface so the next sweep iterations fail
            # (read_json_file raises); a correct sweeper logs and keeps
            # looping instead of dying.
            backup = state_file.with_name(state_file.name + ".bak-635")
            os.replace(state_file, backup)
            state_file.mkdir()
            time.sleep(0.3)  # let several ticks fail
            state_file.rmdir()
            os.replace(backup, state_file)
            shim.now = t0 + TEST_TTL_SEC + 1  # now expired: still must clean up
            cleaned = self.wait_until(lambda: self.read_state() == {})
            self.assertTrue(
                cleaned,
                "a failed sweep iteration must not kill the sweeper loop",
            )
            self.assertFalse(self.process_alive(pid))

    def test_shutdown_terminates_the_active_preview(self):
        shim = self._install_clock()
        self._patch_const("CAMERA_PREVIEW_TTL_SEC", TEST_TTL_SEC)
        self._patch_const("CAMERA_PREVIEW_SWEEP_INTERVAL_SEC", TEST_SWEEP_INTERVAL_SEC)
        with self.client() as client:
            preview = self.start_preview(client)
            session_id = preview["session_id"]
            pid = self.read_state()["pid"]
            self._track_pid(pid)
            # The session is still live (not expired): only shutdown may end it.
        self.assertEqual(
            self.read_state(), {}, "shutdown must terminate the active preview"
        )
        self.assertFalse(self.process_alive(pid))
        self.assertFalse((self.config.CAMERA_PREVIEW_DIR / session_id).exists())

    # -- T-6: binding / 404 / no leak (AC-004) -------------------------------

    def test_media_route_binding_404s_without_renewal_or_leak(self):
        shim = self._install_clock()
        self._patch_const("CAMERA_PREVIEW_TTL_SEC", TEST_TTL_SEC)
        with self.client() as client:
            preview = self.start_preview(client)
            session_id = preview["session_id"]
            t0 = shim.now
            self._track_pid(self.read_state()["pid"])
            baseline = self.read_state()["expires_epoch"]
            session_dir = self.config.CAMERA_PREVIEW_DIR / session_id
            # An unsupported filename that exists on disk: the allowlist, not
            # mere existence, must gate the response.
            (session_dir / "evil.sh").write_text("not-hls-635", encoding="utf-8")
            # A sibling session's playlist: must never be reachable through
            # this session's route.
            sibling_dir = self.config.CAMERA_PREVIEW_DIR / "deadbeef0001"
            sibling_dir.mkdir(exist_ok=True)
            (sibling_dir / "index.m3u8").write_text(
                "#EXTM3U\nsibling-secret-635\n", encoding="utf-8"
            )
            cases = (
                ("wrong-session", f"/media/camera-preview/deadbeef0002/index.m3u8"),
                ("malformed-session", "/media/camera-preview/notasession/index.m3u8"),
                ("traversal-dotdot", f"/media/camera-preview/{session_id}/.."),
                ("traversal-encoded", f"/media/camera-preview/{session_id}/..%2Fsibling%2Findex.m3u8"),
                ("unsupported-filename", f"/media/camera-preview/{session_id}/evil.sh"),
                ("missing-file", f"/media/camera-preview/{session_id}/segment_00042.m4s"),
            )
            for label, url in cases:
                with self.subTest(label=label):
                    response = client.get(url)
                    self.assertEqual(response.status_code, 404, f"{label}: {response.text!r}")
                    self.assertNotIn(b"sibling-secret-635", response.content)
            state = self.read_state()
            self.assertEqual(state["session_id"], session_id)
            self.assertAlmostEqual(
                state["expires_epoch"],
                baseline,
                delta=0.001,
                msg="rejected media requests must not renew",
            )

    # -- T-7: no-store on 200/206/404 (R-6) ----------------------------------

    def test_media_responses_carry_no_store(self):
        shim = self._install_clock()
        self._patch_const("CAMERA_PREVIEW_TTL_SEC", TEST_TTL_SEC)
        with self.client() as client:
            preview = self.start_preview(client)
            session_id = preview["session_id"]
            self._track_pid(self.read_state()["pid"])
            ok = self.fetch_media(client, session_id, "index.m3u8")
            self.assertEqual(ok.status_code, 200, ok.text)
            self._assert_no_store(ok)
            ranged = client.get(
                f"/media/camera-preview/{session_id}/index.m3u8",
                headers={"Range": "bytes=0-4"},
            )
            self.assertEqual(ranged.status_code, 206, ranged.text)
            self.assertEqual(ranged.content, ok.content[:5])
            self._assert_no_store(ranged)
            missing = self.fetch_media(client, session_id, "segment_00042.m4s")
            self.assertEqual(missing.status_code, 404)
            self._assert_no_store(missing)

    # -- T-8: mount compatibility (R-1) ---------------------------------------

    def test_unrelated_media_still_served_by_static_mount(self):
        target = self.config.EVENTS_MEDIA_DIR / "635-mount-compat.jpg"
        target.write_bytes(b"mount-compat-bytes-635")
        with self.client() as client:
            response = client.get("/media/events/635-mount-compat.jpg")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.content, b"mount-compat-bytes-635")

    # -- T-10: terminate-first / stale id (AC-005) ----------------------------

    def test_stale_session_cannot_renew_after_terminate_first(self):
        shim = self._install_clock()
        self._patch_const("CAMERA_PREVIEW_TTL_SEC", TEST_TTL_SEC)
        with self.client() as client:
            first = self.start_preview(client, "cam-a")
            session_a = first["session_id"]
            second = self.start_preview(client, "cam-b")
            session_b = second["session_id"]
            self.assertNotEqual(session_a, session_b)
            state = self.read_state()
            self.assertEqual(state["session_id"], session_b)
            pid_b = state["pid"]
            self._track_pid(pid_b)
            # Terminate-first already removed A's media.
            self.assertFalse((self.config.CAMERA_PREVIEW_DIR / session_a).exists())
            stale = self.fetch_media(client, session_a, "index.m3u8")
            self.assertEqual(stale.status_code, 404, "a replaced session must not serve media")
            fresh = self.fetch_media(client, session_b, "index.m3u8")
            self.assertEqual(fresh.status_code, 200, fresh.text)
            state = self.read_state()
            self.assertEqual(state["session_id"], session_b)
            self.assertEqual(state["pid"], pid_b)


if __name__ == "__main__":
    unittest.main()
