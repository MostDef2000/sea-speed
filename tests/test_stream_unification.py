"""Issue #637 stream unification: both cameras play permanent protected HLS.

The session-based preview contour is gone. These twins pin the four seams the
cutover touched:

1. the road operator page plays the permanent relay path statically (no
   preview session API anywhere in its shipped frontend),
2. the cameras page is a static two-player grid (cam1 + road1) with no
   camera-preview API surface left,
3. the canonical renderer carries the `ubuntu-relay-extra-path` subcommand
   that extends the converged relay config with one inventory-sourced
   permanent path (executed, digest-stable, fail-closed),
4. `configure-analytics-profiles.py` takes the road1 relay source through the
   validated `--road-relay-url` flag (sanitized private RTSP, exact /road1).
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts/operations/mediamtx_path_config.py"
CONFIGURE = ROOT / "deploy/worker/ubuntu/configure-analytics-profiles.py"
ROAD_MAIN_JS = ROOT / "frontend/sea-speed/road/main.js"
ROAD_PAGE = ROOT / "frontend/sea-speed/road/index.html"
CAMERAS_PAGE = ROOT / "frontend/sea-speed/cameras/index.html"
CAMERAS_JS = ROOT / "frontend/sea-speed/cameras/cameras.js"

spec = importlib.util.spec_from_file_location("mediamtx_path_config", RENDERER)
assert spec and spec.loader
mediamtx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mediamtx)

configure_spec = importlib.util.spec_from_file_location("configure_analytics_profiles", CONFIGURE)
assert configure_spec and configure_spec.loader
configure = importlib.util.module_from_spec(configure_spec)
configure_spec.loader.exec_module(configure)

BASE_CONFIG = """logLevel: info
authMethod: internal
authInternalUsers:
  - user: any
    pass:
    ips: ["127.0.0.1"]
    permissions:
      - action: api
rtsp: yes
rtspAddress: :8554
rtmp: no
hls: no
webrtc: no
srt: no
api: yes
apiAddress: 127.0.0.1:9997
paths:
  cam1:
    source: rtsp://relay:secret@10.123.239.102:8554/cam1-h264
    sourceOnDemand: yes
    rtspTransport: tcp
"""

INVENTORY = (
    '{"schema": "sea_speed_camera_preview_inventory_v1", "cameras": ['
    '{"camera_id": "road1", "display_name": "road1", '
    '"source": "rtsp://relay:secret@10.123.239.102:8554/road1"}]}'
)

READER_IP = "10.123.239.101"


def _render_extra_path(config_path: Path, inventory_path: Path, output_path: Path) -> str:
    result = subprocess.run(
        [
            sys.executable,
            str(RENDERER),
            "ubuntu-relay-extra-path",
            "--config",
            str(config_path),
            "--inventory",
            str(inventory_path),
            "--reader-ip",
            READER_IP,
            "--output",
            str(output_path),
        ],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise AssertionError(f"renderer failed: {result.stderr}")
    return result.stdout


class RoadPermanentStreamTests(unittest.TestCase):
    """The road page plays the permanent relay path; no preview session API."""

    def test_road_frontend_is_static_hls_with_no_preview_surface(self) -> None:
        js = ROAD_MAIN_JS.read_text(encoding="utf-8")
        html = ROAD_PAGE.read_text(encoding="utf-8-sig")
        self.assertIn('const HLS_URL="/sea-speed/media/road1/index.m3u8"', js)
        # The preview session contour is gone from the shipped page: no
        # start/stop endpoints, no session-scoped HLS URL handling.
        self.assertNotIn("preview/start", js)
        self.assertNotIn("preview/stop", js)
        self.assertNotIn("PREVIEW_START_URL", js)
        self.assertNotIn("preview", html.lower().replace("previewpath", ""))
        # The stream toggle is a pure local player control: it never calls
        # the camera API (worker control stays on its own endpoint).
        self.assertNotIn("/api/cameras", js)

    def test_road_hls_url_targets_the_permanent_relay_path(self) -> None:
        js = ROAD_MAIN_JS.read_text(encoding="utf-8")
        self.assertIn('"/sea-speed/media/road1/index.m3u8"', js)
        self.assertNotIn("8555", js)
        self.assertNotIn("preview_road1", js)


class CamerasStaticGridTests(unittest.TestCase):
    """The cameras page is a static two-player grid; the catalog API is read-only."""

    def test_cameras_page_has_exactly_two_static_players(self) -> None:
        html = CAMERAS_PAGE.read_text(encoding="utf-8-sig")
        self.assertEqual(html.count("<video"), 2)
        self.assertIn('id="video-cam1"', html)
        self.assertIn('id="video-road1"', html)
        self.assertNotIn("data-video", html)

    def test_cameras_js_wires_both_permanent_streams_without_camera_api(self) -> None:
        js = CAMERAS_JS.read_text(encoding="utf-8")
        self.assertIn('id:"cam1",url:"/sea-speed/media/cam1/index.m3u8"', js)
        self.assertIn('id:"road1",url:"/sea-speed/media/road1/index.m3u8"', js)
        # The only API call on the page is the trusted session identity.
        self.assertIn('"/sea-speed/api/session"', js)
        self.assertNotIn("/api/cameras", js)
        self.assertNotIn("snapshot", js.lower())
        self.assertNotIn("preview", js)

    def test_cameras_page_has_no_batch_or_snapshot_contour(self) -> None:
        html = CAMERAS_PAGE.read_text(encoding="utf-8-sig")
        for gone in ("batchBar", "snapshot", "commit", "ttl", "data-video", "data-state", "data-error"):
            self.assertNotIn(gone, html)


class RendererExtraPathSubcommandTests(unittest.TestCase):
    """Executed renderer twin: one inventory-sourced permanent relay path."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.config = root / "mediamtx.yml"
        self.config.write_text(BASE_CONFIG, encoding="utf-8")
        self.inventory = root / "camera-preview-inventory.json"
        self.inventory.write_text(INVENTORY, encoding="utf-8")
        self.output = root / "mediamtx.candidate.yml"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_extra_path_renders_inventory_sourced_candidate(self) -> None:
        first = _render_extra_path(self.config, self.inventory, self.output)
        text = self.output.read_text(encoding="utf-8")
        self.assertEqual(
            mediamtx.get_path_field(text, "road1", "source"),
            "rtsp://relay:secret@10.123.239.102:8554/road1",
        )
        self.assertEqual(mediamtx.get_path_field(text, "road1", "sourceOnDemand"), "yes")
        self.assertEqual(mediamtx.get_path_field(text, "road1", "rtspTransport"), "tcp")
        # Least-privilege reader rule: exact reader IP, read-only, road1 only.
        self.assertIn(mediamtx.reader_marker("road1"), text)
        self.assertIn('ips: ["10.123.239.101"]', text)
        self.assertNotIn("action: publish", text)
        # The cam1 path and global scalars are untouched: this mode extends
        # an already converged relay config.
        self.assertEqual(
            mediamtx.get_path_field(text, "cam1", "source"),
            "rtsp://relay:secret@10.123.239.102:8554/cam1-h264",
        )
        # Re-render with the same inputs is byte-identical.
        second = _render_extra_path(self.config, self.inventory, self.output)
        self.assertEqual(first, second)

    def test_extra_path_refuses_path_absent_from_inventory(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(RENDERER),
                "ubuntu-relay-extra-path",
                "--config",
                str(self.config),
                "--inventory",
                str(self.inventory),
                "--path",
                "ghost1",
                "--reader-ip",
                READER_IP,
                "--output",
                str(self.output),
            ],
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("absent from the protected inventory", result.stderr + result.stdout)

    def test_preview_relay_subcommands_are_gone(self) -> None:
        result = subprocess.run(
            [sys.executable, str(RENDERER), "--help"],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("ubuntu-relay-extra-path", result.stdout)
        self.assertNotIn("preview", result.stdout.lower())


class ConfigureRoadRelayUrlTests(unittest.TestCase):
    """The road1 relay source is validated fail-closed (issue #637)."""

    GOOD = "rtsp://10.123.239.102:8554/road1"

    def test_production_relay_url_is_accepted(self) -> None:
        self.assertEqual(configure.road_relay_source(self.GOOD), self.GOOD)

    def test_rejects_non_rtsp_scheme(self) -> None:
        with self.assertRaises(SystemExit):
            configure.road_relay_source("http://10.123.239.102:8554/road1")

    def test_rejects_public_ip(self) -> None:
        with self.assertRaises(SystemExit):
            configure.road_relay_source("rtsp://93.184.216.34:8554/road1")

    def test_rejects_missing_port(self) -> None:
        with self.assertRaises(SystemExit):
            configure.road_relay_source("rtsp://10.123.239.102/road1")

    def test_rejects_userinfo(self) -> None:
        with self.assertRaises(SystemExit):
            configure.road_relay_source("rtsp://user:pass@10.123.239.102:8554/road1")

    def test_rejects_wrong_path(self) -> None:
        with self.assertRaises(SystemExit):
            configure.road_relay_source("rtsp://10.123.239.102:8554/preview_road1")

    def test_rejects_query_and_fragment(self) -> None:
        with self.assertRaises(SystemExit):
            configure.road_relay_source("rtsp://10.123.239.102:8554/road1?x=1")
        with self.assertRaises(SystemExit):
            configure.road_relay_source("rtsp://10.123.239.102:8554/road1#frag")

    def test_road_relay_url_flag_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            result = subprocess.run(
                [sys.executable, str(CONFIGURE), "--install-root", raw],
                text=True,
                capture_output=True,
            )
        self.assertNotEqual(result.returncode, 0)
        combined = result.stderr + result.stdout
        self.assertIn("--road-relay-url", combined)


if __name__ == "__main__":
    unittest.main()
