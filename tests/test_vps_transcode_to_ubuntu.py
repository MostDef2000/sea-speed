from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts/operations/mediamtx_path_config.py"
UBUNTU_WATCHDOG_PATH = ROOT / "deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py"

renderer_spec = importlib.util.spec_from_file_location("mediamtx_path_config", RENDERER)
assert renderer_spec and renderer_spec.loader
mediamtx = importlib.util.module_from_spec(renderer_spec)
sys.modules[renderer_spec.name] = mediamtx
renderer_spec.loader.exec_module(mediamtx)

ubuntu_watchdog_spec = importlib.util.spec_from_file_location("ubuntu_camera1_h264_freshness_watchdog", UBUNTU_WATCHDOG_PATH)
assert ubuntu_watchdog_spec and ubuntu_watchdog_spec.loader
ubuntu_watchdog = importlib.util.module_from_spec(ubuntu_watchdog_spec)
sys.modules[ubuntu_watchdog_spec.name] = ubuntu_watchdog
ubuntu_watchdog_spec.loader.exec_module(ubuntu_watchdog)


BASE_CONFIG = """authInternalUsers:
  - username: cam1
    password: internal
paths:
  cam1:
    source: rtsp://10.123.239.102:8554/cam1
    sourceOnDemand: true
"""


class ReaderRuleGeneralizationTests(unittest.TestCase):
    def test_ubuntu_transcode_reader_renders_combined_cam1_h264_rule(self) -> None:
        cfg = Path(tempfile.mkdtemp()) / "mediamtx.yml"
        cfg.write_text(BASE_CONFIG, encoding="utf-8")
        out = Path(tempfile.mkdtemp()) / "mediamtx.yml"
        mediamtx.render_ubuntu_transcode_reader(
            argparse.Namespace(
                config=cfg,
                path="cam1-h264",
                reader_ip="82.146.37.153",
                publisher_ip="10.123.239.102",
                output=out,
            )
        )
        text = out.read_text(encoding="utf-8")
        mediamtx.verify_internal_reader_rule(text, "cam1-h264", reader_ip="82.146.37.153", publisher_ips=["10.123.239.102"])
        # The combined rule must allow both VPS read and Ubuntu publish.
        self.assertIn("ips:", text)
        self.assertIn("read", text)
        self.assertIn("publish", text)

    def test_ensure_cam1_reader_is_subset_safe_when_adding_cam1_h264(self) -> None:
        # Adding cam1-h264 must not disturb the existing single-peer cam1 reader rule.
        updated = mediamtx.ensure_internal_reader_rule(BASE_CONFIG, "cam1", "10.0.0.9")
        mediamtx.verify_internal_reader_rule(updated, "cam1", reader_ip="10.0.0.9")
        # Now add cam1-h264; cam1 rule must remain exactly the single peer.
        updated2 = mediamtx.ensure_internal_reader_rule(updated, "cam1-h264", "10.0.0.9", publisher_ips=["10.0.0.10"])
        mediamtx.verify_internal_reader_rule(updated2, "cam1", reader_ip="10.0.0.9")
        mediamtx.verify_internal_reader_rule(updated2, "cam1-h264", reader_ip="10.0.0.9", publisher_ips=["10.0.0.10"])

    def test_vps_set_hls_address_sets_global_scalar(self) -> None:
        cfg = Path(tempfile.mkdtemp()) / "mediamtx.yml"
        cfg.write_text(BASE_CONFIG, encoding="utf-8")
        out = Path(tempfile.mkdtemp()) / "mediamtx.yml"
        mediamtx.render_vps_set_hls_address(
            argparse.Namespace(config=cfg, hls_address=":18889", output=out)
        )
        text = out.read_text(encoding="utf-8")
        self.assertIn('hlsAddress: ":18889"', text)


class UbuntuFreshnessWatchdogTests(unittest.TestCase):
    @staticmethod
    def completed(argv, returncode=0, stdout=""):
        return subprocess.CompletedProcess(argv, returncode, stdout=stdout)

    def state_root(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        return Path(temp.name) / "state"

    def test_ready_path_is_noop(self) -> None:
        state_root = self.state_root()
        calls = []

        def runner(argv, **kwargs):
            calls.append(list(argv))
            if argv[0] == "curl":
                payload = json.dumps({"state": "ready", "lastFrameTime": datetime.now(timezone.utc).isoformat()})
                return self.completed(argv, stdout=payload)
            raise AssertionError(f"unexpected command: {argv}")

        lines = ubuntu_watchdog.run_once(runner=runner, sleeper=lambda _: None, clock=lambda: 1000.0, state_root=state_root)
        self.assertIn("CAMERA1_H264_RECOVERY=NOOP", lines)
        self.assertFalse(any(argv[:2] == ["systemctl", "restart"] for argv in calls))

    def test_stale_path_restarts_transcode_service(self) -> None:
        state_root = self.state_root()
        calls = []
        curl_count = [0]

        def runner(argv, **kwargs):
            calls.append(list(argv))
            if argv[0] == "curl":
                curl_count[0] += 1
                stamp = datetime.now(timezone.utc).isoformat() if curl_count[0] >= 2 else "2020-01-01T00:00:00Z"
                payload = json.dumps({"state": "ready", "lastFrameTime": stamp})
                return self.completed(argv, stdout=payload)
            if argv[0] == "ffmpeg":
                return self.completed(argv)
            if argv == ["systemctl", "restart", ubuntu_watchdog.CAMERA1_H264_SERVICE]:
                return self.completed(argv)
            if argv == ["systemctl", "is-active", "--quiet", ubuntu_watchdog.CAMERA1_H264_SERVICE]:
                return self.completed(argv)
            raise AssertionError(f"unexpected command: {argv}")

        lines = ubuntu_watchdog.run_once(runner=runner, sleeper=lambda _: None, clock=lambda: 1000.0, state_root=state_root)
        self.assertIn("CAMERA1_H264_RECOVERY=RESTARTED", lines)
        self.assertEqual(
            [argv for argv in calls if argv[:2] == ["systemctl", "restart"]],
            [["systemctl", "restart", "sea-speed-camera1-h264.service"]],
        )

    def test_missing_source_fails_before_restart(self) -> None:
        state_root = self.state_root()
        calls = []

        def runner(argv, **kwargs):
            calls.append(list(argv))
            if argv[0] == "curl":
                payload = json.dumps({"state": "ready", "lastFrameTime": "2020-01-01T00:00:00Z"})
                return self.completed(argv, stdout=payload)
            if argv[0] == "ffmpeg":
                return self.completed(argv, returncode=1, stdout="source unavailable")
            raise AssertionError(f"unexpected command: {argv}")

        with self.assertRaises(ubuntu_watchdog.WatchdogError):
            ubuntu_watchdog.run_once(runner=runner, sleeper=lambda _: None, clock=lambda: 1000.0, state_root=state_root)
        self.assertFalse(any(argv[:2] == ["systemctl", "restart"] for argv in calls))


if __name__ == "__main__":
    unittest.main()
