from __future__ import annotations

import importlib.util
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

    def test_static_hls_healthy_relay_restarts_only_fixed_service(self) -> None:
        _, state_root = self.state_root()
        calls: list[list[str]] = []
        sequences = iter((40, 40, 1, 2))

        def runner(argv, **kwargs):
            calls.append(list(argv))
            if argv[0] == "curl":
                return self.completed(argv, stdout=f"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:{next(sequences)}\n")
            if argv[0] == "ffmpeg":
                return self.completed(argv)
            if argv == ["systemctl", "restart", watchdog.CAMERA1_H264_SERVICE]:
                return self.completed(argv)
            if argv == ["systemctl", "is-active", "--quiet", watchdog.CAMERA1_H264_SERVICE]:
                return self.completed(argv)
            raise AssertionError(f"unexpected command: {argv}")

        lines = watchdog.run_once(runner=runner, sleeper=lambda _: None, clock=lambda: 1000.0, state_root=state_root)
        self.assertIn("CAMERA1_H264_RECOVERY=RESTARTED", lines)
        self.assertIn("CAMERA1_PRIVATE_RELAY=PASS", lines)
        self.assertEqual(
            [argv for argv in calls if argv[:2] == ["systemctl", "restart"]],
            [["systemctl", "restart", "sea-speed-camera1-h264.service"]],
        )
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
                "rtsp://10.123.239.102:8554/cam1",
                "-frames:v",
                "1",
                "-f",
                "null",
                "-",
            ],
        )

    def test_static_hls_unavailable_relay_never_restarts(self) -> None:
        _, state_root = self.state_root()
        calls: list[list[str]] = []
        sequences = iter((50, 50))

        def runner(argv, **kwargs):
            calls.append(list(argv))
            if argv[0] == "curl":
                return self.completed(argv, stdout=f"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:{next(sequences)}\n")
            if argv[0] == "ffmpeg":
                return self.completed(argv, returncode=1, stdout="relay unavailable")
            raise AssertionError(f"unexpected command: {argv}")

        with self.assertRaises(watchdog.WatchdogError):
            watchdog.run_once(runner=runner, sleeper=lambda _: None, clock=lambda: 1000.0, state_root=state_root)
        self.assertFalse(any(argv[:2] == ["systemctl", "restart"] for argv in calls))

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

    def test_post_restart_static_hls_fails_and_keeps_cooldown(self) -> None:
        _, state_root = self.state_root()
        calls: list[list[str]] = []
        sequences = iter((10, 10, 20, 20))

        def runner(argv, **kwargs):
            calls.append(list(argv))
            if argv[0] == "curl":
                return self.completed(argv, stdout=f"#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:{next(sequences)}\n")
            if argv[0] == "ffmpeg" or argv[0] == "systemctl":
                return self.completed(argv)
            raise AssertionError(f"unexpected command: {argv}")

        with self.assertRaises(watchdog.WatchdogError):
            watchdog.run_once(runner=runner, sleeper=lambda _: None, clock=lambda: 2000.0, state_root=state_root)
        self.assertTrue((state_root / "state.json").is_file())
        self.assertEqual(
            [argv for argv in calls if argv[:2] == ["systemctl", "restart"]],
            [["systemctl", "restart", watchdog.CAMERA1_H264_SERVICE]],
        )

    def test_runtime_entrypoint_has_no_selectable_topology(self) -> None:
        self.assertEqual(watchdog.CAMERA1_PRIVATE_RELAY, "rtsp://10.123.239.102:8554/cam1")
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


if __name__ == "__main__":
    unittest.main()
