from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHDOG_PATH = ROOT / "deploy/vps/camera1-h264-freshness-watchdog.py"
SERVICE_UNIT = ROOT / "deploy/vps/sea-speed-camera1-h264-freshness.service"
TIMER_UNIT = ROOT / "deploy/vps/sea-speed-camera1-h264-freshness.timer"
INSTALLER = ROOT / "deploy/vps/install-auth-privilege-boundary.sh"

spec = importlib.util.spec_from_file_location("camera1_h264_freshness_watchdog", WATCHDOG_PATH)
assert spec and spec.loader
watchdog = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = watchdog
spec.loader.exec_module(watchdog)

UBUNTU_WATCHDOG_PATH = ROOT / "deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py"
ubuntu_spec = importlib.util.spec_from_file_location("ubuntu_camera1_h264_freshness_watchdog", UBUNTU_WATCHDOG_PATH)
assert ubuntu_spec and ubuntu_spec.loader
ubuntu_watchdog = importlib.util.module_from_spec(ubuntu_spec)
sys.modules[ubuntu_spec.name] = ubuntu_watchdog
ubuntu_spec.loader.exec_module(ubuntu_watchdog)


class WatchdogTests(unittest.TestCase):
    @staticmethod
    def completed(argv: list[str], returncode: int = 0, stdout: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, returncode, stdout=stdout)

    def state_root(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return temp, Path(temp.name) / "state"

    def test_advancing_hls_is_noop(self) -> None:
        _, state_root = self.state_root()
        calls: list[list[str]] = []
        sequences = iter((100, 101))

        def runner(argv, **kwargs):
            calls.append(list(argv))
            if argv[0] == "curl":
                return self.completed(argv, stdout=f"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:{next(sequences)}\n")
            raise AssertionError(f"unexpected command: {argv}")

        lines = watchdog.run_once(runner=runner, sleeper=lambda _: None, clock=lambda: 1000.0, state_root=state_root)
        self.assertIn("CAMERA1_H264_RECOVERY=NOOP", lines)
        self.assertFalse(any(argv[0] == "ffmpeg" for argv in calls))
        self.assertFalse(any(argv[:2] == ["systemctl", "restart"] for argv in calls))

    def test_static_hls_healthy_source_resources_cam1_via_api(self) -> None:
        _, state_root = self.state_root()
        calls: list[list[str]] = []
        sequences = iter((40, 40, 1, 2))

        def runner(argv, **kwargs):
            calls.append(list(argv))
            if argv[0] == "curl" and any("v3/paths/cam1/patch" in a for a in argv):
                return self.completed(argv)
            if argv[0] == "curl":
                return self.completed(argv, stdout=f"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:{next(sequences)}\n")
            if argv[0] == "ffmpeg":
                return self.completed(argv)
            raise AssertionError(f"unexpected command: {argv}")

        lines = watchdog.run_once(runner=runner, sleeper=lambda _: None, clock=lambda: 1000.0, state_root=state_root)
        self.assertIn("CAMERA1_H264_RECOVERY=API_RESOURCE", lines)
        self.assertIn("CAMERA1_PRIVATE_RELAY=PASS", lines)
        self.assertFalse(any(argv[:2] == ["systemctl", "restart"] for argv in calls))
        self.assertTrue(any(any("v3/paths/cam1/patch" in a for a in argv) for argv in calls))
        relay = next(argv for argv in calls if argv[0] == "ffmpeg")
        self.assertEqual(
            relay,
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-rtsp_transport",
                "tcp",
                "-timeout",
                "10000000",
                "-i",
                "rtsp://10.123.239.102:8554/cam1-h264",
                "-frames:v",
                "1",
                "-f",
                "null",
                "-",
            ],
        )

    def test_static_hls_unavailable_source_never_resources(self) -> None:
        _, state_root = self.state_root()
        calls: list[list[str]] = []
        sequences = iter((50, 50))

        def runner(argv, **kwargs):
            calls.append(list(argv))
            if argv[0] == "curl":
                return self.completed(argv, stdout=f"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:{next(sequences)}\n")
            if argv[0] == "ffmpeg":
                return self.completed(argv, returncode=1, stdout="source unavailable")
            raise AssertionError(f"unexpected command: {argv}")

        with self.assertRaises(watchdog.WatchdogError):
            watchdog.run_once(runner=runner, sleeper=lambda _: None, clock=lambda: 1000.0, state_root=state_root)
        self.assertFalse(any(argv[:2] == ["systemctl", "restart"] for argv in calls))
        self.assertFalse(any(any("v3/paths/cam1/patch" in a for a in argv) for argv in calls))

    def test_cooldown_prevents_restart_storm(self) -> None:
        _, state_root = self.state_root()
        state_root.mkdir(parents=True)
        watchdog._write_last_attempt(state_root / "state.json", 900.0)
        calls: list[list[str]] = []
        sequences = iter((77, 77))

        def runner(argv, **kwargs):
            calls.append(list(argv))
            if argv[0] == "curl":
                return self.completed(argv, stdout=f"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:{next(sequences)}\n")
            raise AssertionError(f"unexpected command: {argv}")

        lines = watchdog.run_once(runner=runner, sleeper=lambda _: None, clock=lambda: 1000.0, state_root=state_root)
        self.assertIn("CAMERA1_H264_RECOVERY=COOLDOWN", lines)
        self.assertFalse(any(argv[0] == "ffmpeg" for argv in calls))
        self.assertFalse(any(argv[:2] == ["systemctl", "restart"] for argv in calls))

    def test_post_api_resource_static_hls_fails_and_keeps_cooldown(self) -> None:
        _, state_root = self.state_root()
        calls: list[list[str]] = []
        sequences = iter((10, 10, 20, 20))

        def runner(argv, **kwargs):
            calls.append(list(argv))
            if argv[0] == "curl" and any("v3/paths/cam1/patch" in a for a in argv):
                return self.completed(argv)
            if argv[0] == "curl":
                return self.completed(argv, stdout=f"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:{next(sequences)}\n")
            if argv[0] == "ffmpeg":
                return self.completed(argv)
            raise AssertionError(f"unexpected command: {argv}")

        with self.assertRaises(watchdog.WatchdogError):
            watchdog.run_once(runner=runner, sleeper=lambda _: None, clock=lambda: 2000.0, state_root=state_root)
        self.assertTrue((state_root / "state.json").is_file())
        self.assertFalse(any(argv[:2] == ["systemctl", "restart"] for argv in calls))
        self.assertTrue(any(any("v3/paths/cam1/patch" in a for a in argv) for argv in calls))

    def test_runtime_entrypoint_has_no_selectable_topology(self) -> None:
        self.assertEqual(watchdog.CAMERA1_H264_SOURCE, "rtsp://10.123.239.102:8554/cam1-h264")
        self.assertEqual(watchdog.CAMERA1_LOCAL_HLS, "http://127.0.0.1:18889/cam1/index.m3u8")
        self.assertEqual(watchdog.CAMERA1_H264_SERVICE, "sea-speed-camera1-h264.service")
        text = WATCHDOG_PATH.read_text(encoding="utf-8")
        for forbidden in ("argparse", "os.environ", "nginx.service", "mediamtx.service", "sea-speed-worker.service", "sea-speed-road-worker.service"):
            self.assertNotIn(forbidden, text)

    def test_systemd_timer_is_fixed_and_persistent_runtime_supervision(self) -> None:
        service = SERVICE_UNIT.read_text(encoding="utf-8")
        timer = TIMER_UNIT.read_text(encoding="utf-8")
        self.assertIn("ExecStart=/usr/local/sbin/sea-speed-camera1-h264-freshness-watchdog", service)
        self.assertIn("User=root", service)
        self.assertIn("NoNewPrivileges=yes", service)
        self.assertIn("OnActiveSec=20s", timer)
        self.assertIn("OnUnitInactiveSec=30s", timer)
        self.assertIn("WantedBy=timers.target", timer)

    def test_exact_source_installer_owns_watchdog_activation_boundary(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('WATCHDOG_PATH="${PREFIX}/usr/local/sbin/sea-speed-camera1-h264-freshness-watchdog"', text)
        self.assertIn('WATCHDOG_SERVICE_PATH="${PREFIX}/etc/systemd/system/$WATCHDOG_SERVICE"', text)
        self.assertIn('WATCHDOG_TIMER_PATH="${PREFIX}/etc/systemd/system/$WATCHDOG_TIMER"', text)
        self.assertIn('systemctl enable --now "$WATCHDOG_TIMER"', text)
        self.assertIn('restore_timer_runtime', text)
        self.assertIn('CAMERA1_FRESHNESS_WATCHDOG=INSTALLED', text)


    def test_worker_source_probe_targets_product_path_cam1_h264(self) -> None:
        self.assertEqual(ubuntu_watchdog.CAMERA1_H264_SOURCE, "rtsp://10.123.239.102:8554/cam1-h264")


# Verbatim MediaMTX v1.19.1 GET /v3/paths/get/cam1-h264 response captured by the
# operator (issue #410); timestamps/ids are fixed literals. The numeric inbound
# fields use the operator-verified freshness-oracle values (inboundBytes grew
# 1161959598 -> 1165817532 in ~10 s while the producer was publishing).
CAM1_H264_V1191_JSON = json.dumps(
    {
        "name": "cam1-h264",
        "confName": "cam1-h264",
        "ready": True,
        "readyTime": "2026-10-07T13:35:41.739346459Z",
        "available": True,
        "availableTime": "2026-10-07T13:35:41.739346459Z",
        "online": True,
        "onlineTime": "2026-10-07T13:35:41.739346496Z",
        "source": {"type": "rtspSession", "id": "f70edb94-95d6-4a30-b4e9-370c80d53b6b"},
        "tracks": ["H264"],
        "tracks2": [
            {
                "codec": "H264",
                "codecProps": {"width": 1280, "height": 720, "profile": "High", "level": "3.1"},
            }
        ],
        "readers": [{"type": "rtspSession", "id": "9f0202e7-4b62-4144-a8bc-b2946bb5827c"}],
        "bytesReceived": 1161959598,
        "bytesSent": 0,
        "inboundBytes": 1161959598,
        "inboundFramesInError": 0,
        "outboundBytes": 0,
    }
)

V1191_BYTES_T0 = 1161959598
V1191_BYTES_T1 = 1165817532
V1191_GET_ROUTE = "/v3/paths/get/cam1-h264"
V1191_LEGACY_ROUTE = "/v3/paths/cam1-h264"


def cam1_h264_v1191_payload(**overrides: object) -> str:
    payload = json.loads(CAM1_H264_V1191_JSON)
    payload.update(overrides)
    return json.dumps(payload)


class UbuntuWatchdogMediaMTXV1191Tests(unittest.TestCase):
    """Ubuntu worker watchdog pins against the MediaMTX v1.19.1 REST API (#410)."""

    @staticmethod
    def completed(argv: list[str], returncode: int = 0, stdout: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, returncode, stdout=stdout)

    def state_root(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return temp, Path(temp.name) / "state"

    def ready_runner(self, payloads: list[object]) -> tuple[list[list[str]], object]:
        results = iter(payloads)
        calls: list[list[str]] = []

        def runner(argv, **kwargs):
            calls.append(list(argv))
            if argv[0] == "curl":
                result = next(results)
                if isinstance(result, str):
                    return self.completed(argv, stdout=result)
                return result
            raise AssertionError(f"unexpected command: {argv}")

        return calls, runner

    def watchdog_runner(self, curl_results: list[object]) -> tuple[list[list[str]], object]:
        results = iter(curl_results)
        calls: list[list[str]] = []

        def runner(argv, **kwargs):
            calls.append(list(argv))
            if argv[0] == "curl":
                result = next(results)
                if isinstance(result, str):
                    return self.completed(argv, stdout=result)
                return result
            if argv[0] == "ffmpeg":
                return self.completed(argv)
            if argv == ["systemctl", "restart", ubuntu_watchdog.CAMERA1_H264_SERVICE]:
                return self.completed(argv)
            if argv == ["systemctl", "is-active", "--quiet", ubuntu_watchdog.CAMERA1_H264_SERVICE]:
                return self.completed(argv)
            raise AssertionError(f"unexpected command: {argv}")

        return calls, runner

    def assert_v1191_route(self, calls: list[list[str]]) -> None:
        curl_calls = [argv for argv in calls if argv[0] == "curl"]
        self.assertTrue(curl_calls)
        for argv in curl_calls:
            self.assertTrue(any(V1191_GET_ROUTE in argument for argument in argv), argv)
            self.assertFalse(any(V1191_LEGACY_ROUTE in argument for argument in argv), argv)

    def test_growing_inbound_bytes_is_pass_noop(self) -> None:
        _, state_root = self.state_root()
        calls, runner = self.watchdog_runner(
            [
                cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T0),
                cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T1),
            ]
        )
        lines = ubuntu_watchdog.run_once(
            runner=runner, sleeper=lambda _: None, clock=lambda: 1000.0, state_root=state_root
        )
        self.assertIn("CAMERA1_H264_FRESHNESS=PASS", lines)
        self.assertIn("CAMERA1_H264_RECOVERY=NOOP", lines)
        self.assertIn("CAMERA1_SOURCE=NOT_CHECKED", lines)
        self.assertEqual([argv for argv in calls if argv[0] == "curl"].__len__(), 2)
        self.assert_v1191_route(calls)
        self.assertFalse(any(argv[0] == "ffmpeg" for argv in calls))
        self.assertFalse(any(argv[:2] == ["systemctl", "restart"] for argv in calls))

    def test_curl_failure_within_cooldown_is_stale_without_restart(self) -> None:
        _, state_root = self.state_root()
        state_root.mkdir(parents=True)
        ubuntu_watchdog._write_last_attempt(state_root / "state.json", 900.0)
        calls, runner = self.watchdog_runner(
            [
                self.completed(["curl"], returncode=22, stdout="curl: (22) The requested URL returned error: 404"),
                self.completed(["curl"], returncode=22, stdout="curl: (22) The requested URL returned error: 404"),
            ]
        )
        lines = ubuntu_watchdog.run_once(
            runner=runner, sleeper=lambda _: None, clock=lambda: 1000.0, state_root=state_root
        )
        self.assertIn("CAMERA1_H264_FRESHNESS=STALE", lines)
        self.assertIn("CAMERA1_H264_RECOVERY=COOLDOWN", lines)
        self.assertIn("CAMERA1_H264_COOLDOWN_REMAINING_SECONDS=200", lines)
        self.assert_v1191_route(calls)
        self.assertFalse(any(argv[0] == "ffmpeg" for argv in calls))
        self.assertFalse(any(argv[:2] == ["systemctl", "restart"] for argv in calls))

    def test_curl_failure_without_state_recovers_and_verifies_growth(self) -> None:
        _, state_root = self.state_root()
        calls, runner = self.watchdog_runner(
            [
                self.completed(["curl"], returncode=22, stdout="curl: (22) The requested URL returned error: 404"),
                cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T0),
                cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T1),
            ]
        )
        lines = ubuntu_watchdog.run_once(
            runner=runner, sleeper=lambda _: None, clock=lambda: 1000.0, state_root=state_root
        )
        self.assertIn("CAMERA1_H264_FRESHNESS=PASS", lines)
        self.assertIn("CAMERA1_H264_RECOVERY=RESTARTED", lines)
        self.assertIn("CAMERA1_SOURCE=PASS", lines)
        self.assert_v1191_route(calls)
        self.assertEqual(
            [argv for argv in calls if argv[:2] == ["systemctl", "restart"]],
            [["systemctl", "restart", "sea-speed-camera1-h264.service"]],
        )

    def test_identical_inbound_bytes_recovers_via_restart(self) -> None:
        _, state_root = self.state_root()
        calls, runner = self.watchdog_runner(
            [
                cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T0),
                cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T0),
                cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T0),
                cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T1),
            ]
        )
        lines = ubuntu_watchdog.run_once(
            runner=runner, sleeper=lambda _: None, clock=lambda: 1000.0, state_root=state_root
        )
        self.assertIn("CAMERA1_H264_RECOVERY=RESTARTED", lines)
        self.assert_v1191_route(calls)
        self.assertTrue(any(argv[0] == "ffmpeg" for argv in calls))

    def test_path_ready_fail_closed_variants(self) -> None:
        sleeps: list[float] = []
        noop_sleeper = sleeps.append
        cases: list[list[object]] = [
            [self.completed(["curl"], returncode=22, stdout="404")],
            [self.completed(["curl"], returncode=7, stdout="curl: (7)Failed to connect")],
            ["not-json"],
            [""],
            ["null"],
            ["[]"],
            ['"text"'],
            ["42"],
            [cam1_h264_v1191_payload(ready=False)],
            [cam1_h264_v1191_payload(available=None)],
            [cam1_h264_v1191_payload(inboundBytes=None)],
            [cam1_h264_v1191_payload(inboundBytes="1161959598")],
            [cam1_h264_v1191_payload(inboundBytes=-1)],
            [cam1_h264_v1191_payload(inboundBytes=True)],
            [cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T0), cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T0)],
            [cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T1), cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T0)],
        ]
        for payloads in cases:
            with self.subTest(payloads=payloads):
                calls, runner = self.ready_runner(list(payloads))
                self.assertFalse(ubuntu_watchdog._path_ready(runner, noop_sleeper))
                self.assert_v1191_route(calls)

    def test_path_ready_fail_closed_on_non_object_second_sample(self) -> None:
        sleeps: list[float] = []
        calls, runner = self.ready_runner(
            [
                cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T0),
                "null",
            ]
        )
        self.assertFalse(ubuntu_watchdog._path_ready(runner, sleeps.append))
        self.assert_v1191_route(calls)
        self.assertEqual(sleeps, [ubuntu_watchdog.SAMPLE_SECONDS])

    def test_non_object_body_recovers_via_restart(self) -> None:
        _, state_root = self.state_root()
        calls, runner = self.watchdog_runner(
            [
                "null",
                cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T0),
                cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T1),
            ]
        )
        lines = ubuntu_watchdog.run_once(
            runner=runner, sleeper=lambda _: None, clock=lambda: 1000.0, state_root=state_root
        )
        self.assertIn("CAMERA1_H264_FRESHNESS=PASS", lines)
        self.assertIn("CAMERA1_H264_RECOVERY=RESTARTED", lines)
        self.assertIn("CAMERA1_SOURCE=PASS", lines)
        self.assert_v1191_route(calls)
        self.assertEqual(
            [argv for argv in calls if argv[:2] == ["systemctl", "restart"]],
            [["systemctl", "restart", "sea-speed-camera1-h264.service"]],
        )

    def test_path_ready_passes_on_growth(self) -> None:
        calls, runner = self.ready_runner(
            [
                cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T0),
                cam1_h264_v1191_payload(inboundBytes=V1191_BYTES_T1),
            ]
        )
        sleeps: list[float] = []
        self.assertTrue(ubuntu_watchdog._path_ready(runner, sleeps.append))
        self.assertEqual(sleeps, [ubuntu_watchdog.SAMPLE_SECONDS])
        self.assert_v1191_route(calls)

    def test_v1191_source_pins(self) -> None:
        text = UBUNTU_WATCHDOG_PATH.read_text(encoding="utf-8")
        self.assertIn("/v3/paths/get/{CAMERA1_H264_PATH}", text)
        self.assertNotIn("/v3/paths/{CAMERA1_H264_PATH}", text)
        self.assertNotIn("lastFrameTime", text)
        self.assertNotIn("STALE_SECONDS", text)
        self.assertNotIn("from datetime import", text)


if __name__ == "__main__":
    unittest.main()
