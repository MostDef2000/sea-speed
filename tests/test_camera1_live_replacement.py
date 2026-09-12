from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts/operations/mediamtx_path_config.py"
UBUNTU = ROOT / "deploy/worker/ubuntu/camera-relay.sh"
VPS = ROOT / "deploy/vps/camera-source-switch.sh"
DOC = ROOT / "docs/operations/CAMERA1_LIVE_REPLACEMENT.md"

spec = importlib.util.spec_from_file_location("mediamtx_path_config", RENDERER)
assert spec and spec.loader
mediamtx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mediamtx)


BASE_CONFIG = """logLevel: info
authMethod: internal
authInternalUsers:
  - user: any
    pass:
    ips: ["10.0.0.7"]
    permissions:
      - action: read
        path: existing-private-path
  - user: any
    pass:
    ips: ["127.0.0.1"]
    permissions:
      - action: api
rtsp: yes
rtspAddress: :8554
rtmp: yes
hls: yes
webrtc: yes
srt: yes
paths:
  cam1:
    source: rtsp://legacy.example.invalid/live
    sourceOnDemand: no
    rtspTransport: automatic
    runOnReady: echo-safe-marker
  cam1-new:
    source: rtsp://10.0.0.8:8554/cam1-test
    sourceOnDemand: yes
"""


class Camera1LiveReplacementTests(unittest.TestCase):
    def test_path_switch_preserves_unrelated_fields_and_pins_tcp_idempotently(self) -> None:
        relay = "rtsp://10.0.0.8:8554/cam1"
        rendered = mediamtx.set_path_source(
            BASE_CONFIG,
            "cam1",
            relay,
            source_on_demand=True,
            rtsp_transport="tcp",
        )
        self.assertIn('source: "rtsp://10.0.0.8:8554/cam1"', rendered)
        self.assertIn("sourceOnDemand: yes", rendered)
        self.assertIn("rtspTransport: tcp", rendered)
        self.assertNotIn("rtspTransport: automatic", rendered)
        self.assertIn("runOnReady: echo-safe-marker", rendered)
        self.assertIn("cam1-new:", rendered)
        self.assertNotIn("legacy.example.invalid", mediamtx.get_path_field(rendered, "cam1", "source") or "")
        mediamtx.verify_vps_relay_path(rendered, "cam1", relay)
        self.assertEqual(
            mediamtx.set_path_source(
                rendered,
                "cam1",
                relay,
                source_on_demand=True,
                rtsp_transport="tcp",
            ),
            rendered,
        )

    def test_reader_auth_is_single_peer_read_only_idempotent_and_preserves_existing_rules(self) -> None:
        original_auth = BASE_CONFIG.split("rtsp: yes", 1)[0]
        rendered = mediamtx.ensure_internal_reader_rule(BASE_CONFIG, "cam1", "10.0.0.9")
        self.assertTrue(rendered.startswith(original_auth))
        self.assertIn("# Sea Speed least-privilege reader for canonical cam1", rendered)
        self.assertIn('ips: ["10.0.0.9"]', rendered)
        self.assertIn("      - action: read\n        path: \"cam1\"", rendered)
        self.assertNotIn("      - action: publish\n        path: \"cam1\"", rendered)
        self.assertNotIn("      - action: api\n        path: \"cam1\"", rendered)
        mediamtx.verify_internal_reader_rule(rendered, "cam1", "10.0.0.9")
        self.assertEqual(
            mediamtx.ensure_internal_reader_rule(rendered, "cam1", "10.0.0.9"),
            rendered,
        )
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.ensure_internal_reader_rule(rendered, "cam1", "10.0.0.10")

    def test_reader_auth_rejects_non_rfc1918_and_non_internal_auth(self) -> None:
        for value in ("203.0.113.8", "127.0.0.1", "10.0.0.0/24"):
            with self.subTest(value=value), self.assertRaises(mediamtx.ConfigError):
                mediamtx.validate_reader_ip(value)
        external = BASE_CONFIG.replace("authMethod: internal", "authMethod: http", 1)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.ensure_internal_reader_rule(external, "cam1", "10.0.0.9")

    def test_ubuntu_renderer_keeps_secret_out_of_output_and_locks_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "mediamtx.yml"
            env_file = root / "worker.env"
            candidate = root / "candidate.yml"
            config.write_text(BASE_CONFIG, encoding="utf-8")
            secret = "rtsp://" + "camera_user:camera_key" + "@10.0.0.21/live"
            env_file.write_text("HLS_URL=" + secret + "\n", encoding="utf-8")
            os.chmod(env_file, 0o600)

            result = subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "ubuntu-relay",
                    "--config",
                    str(config),
                    "--source-env-file",
                    str(env_file),
                    "--private-rtsp-address",
                    "10.0.0.8:8554",
                    "--reader-ip",
                    "10.0.0.9",
                    "--path",
                    "cam1",
                    "--output",
                    str(candidate),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertNotIn(secret, result.stdout)
            self.assertNotIn(secret, result.stderr)
            self.assertIn("reader_scope=single-rfc1918-ip", result.stdout)
            self.assertIn("reader_permission=read-only", result.stdout)
            self.assertEqual(candidate.stat().st_mode & 0o777, 0o600)
            rendered = candidate.read_text(encoding="utf-8")
            self.assertIn(secret, rendered)
            self.assertIn('rtspAddress: "10.0.0.8:8554"', rendered)
            self.assertIn("rtmp: no", rendered)
            self.assertIn("hls: no", rendered)
            self.assertIn("webrtc: no", rendered)
            self.assertIn("srt: no", rendered)
            self.assertEqual(mediamtx.get_path_field(rendered, "cam1", "source"), secret)
            mediamtx.verify_internal_reader_rule(rendered, "cam1", "10.0.0.9")

    def test_vps_relay_must_be_private_and_credential_free(self) -> None:
        mediamtx.validate_private_relay_url("rtsp://10.0.0.8:8554/cam1", "cam1")
        # Cutover topology: the switched HLS path `cam1` may source a distinct
        # Worker transcode path `cam1-h264`; relay path need not equal switched path.
        mediamtx.validate_private_relay_url("rtsp://10.0.0.8:8554/cam1-h264", "cam1")
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.validate_private_relay_url(
                "rtsp://" + "u:k" + "@10.0.0.8:8554/cam1", "cam1"
            )
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.validate_private_relay_url("rtsp://203.0.113.8:8554/cam1", "cam1")

    def test_vps_renderer_writes_and_verifies_tcp_candidate(self) -> None:
        relay = "rtsp://10.0.0.8:8554/cam1"
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "mediamtx.yml"
            candidate = root / "candidate.yml"
            config.write_text(BASE_CONFIG, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "vps-switch",
                    "--config",
                    str(config),
                    "--relay-url",
                    relay,
                    "--path",
                    "cam1",
                    "--output",
                    str(candidate),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            self.assertIn("rtsp_transport=tcp", result.stdout)
            self.assertEqual(candidate.stat().st_mode & 0o777, 0o600)
            rendered = candidate.read_text(encoding="utf-8")
            mediamtx.verify_vps_relay_path(rendered, "cam1", relay)
            subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "verify-vps-switch",
                    "--config",
                    str(candidate),
                    "--relay-url",
                    relay,
                    "--path",
                    "cam1",
                ],
                check=True,
                text=True,
                capture_output=True,
            )

    def test_cleanup_requires_expected_tcp_canonical_source_then_removes_only_cam1_new(self) -> None:
        relay = "rtsp://10.0.0.8:8554/cam1"
        switched = mediamtx.set_path_source(
            BASE_CONFIG,
            "cam1",
            relay,
            rtsp_transport="tcp",
        )
        mediamtx.verify_vps_relay_path(switched, "cam1", relay)
        cleaned = mediamtx.remove_path(switched, "cam1-new")
        self.assertNotIn("cam1-new:", cleaned)
        mediamtx.verify_vps_relay_path(cleaned, "cam1", relay)
        self.assertIn("runOnReady: echo-safe-marker", cleaned)

        wrong_transport = switched.replace("rtspTransport: tcp", "rtspTransport: automatic", 1)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.verify_vps_relay_path(wrong_transport, "cam1", relay)

    def test_shell_contracts_are_explicit_and_ai_worker_is_not_controlled(self) -> None:
        subprocess.run(["bash", "-n", str(UBUNTU)], check=True)
        subprocess.run(["bash", "-n", str(VPS)], check=True)
        ubuntu = UBUNTU.read_text(encoding="utf-8")
        vps = VPS.read_text(encoding="utf-8")

        self.assertIn('worker_service="sea-speed-worker.service"', ubuntu)
        self.assertIn("--reader-ip", ubuntu)
        self.assertIn("READER_AUTH_SCOPE=cam1-single-rfc1918-peer", ubuntu)
        self.assertIn("verify-reader-auth", ubuntu)
        self.assertIn("MTX_AUTHMETHOD=", ubuntu)
        self.assertIn("AI worker must remain stopped", ubuntu)
        self.assertNotIn('systemctl restart "$worker_service"', ubuntu)
        self.assertNotIn('systemctl start "$worker_service"', ubuntu)
        self.assertNotIn('systemctl enable "$worker_service"', ubuntu)
        self.assertIn("automatic rollback is not authorized", ubuntu)

        self.assertIn("--confirmed-public-hls", vps)
        self.assertIn("cam1-new", vps)
        self.assertIn("verify-vps-switch", vps)
        self.assertIn("RTSP_TRANSPORT=tcp", vps)
        self.assertIn("LOCAL_CANONICAL_HLS=PASS", vps)
        self.assertIn("automatic rollback is not authorized", vps)
        self.assertNotIn("worker.env", vps)

    def test_documentation_preserves_private_relay_and_records_auth_v1_boundary(self) -> None:
        source = DOC.read_text(encoding="utf-8")
        self.assertIn("Issue #115", source)
        self.assertIn("/sea-speed/media/cam1/index.m3u8", source)
        self.assertIn("retired `/cams/hls/cam1/index.m3u8`", source)
        self.assertIn("does not create `cam2`", source)
        self.assertIn("independent of `sea-speed-worker.service`", source)
        self.assertIn("single VPS ZeroTier peer", source)
        self.assertIn("--reader-ip", source)
        self.assertIn("rtspTransport: tcp", source)
        self.assertIn("cam1-new", source)
        self.assertIn("sea-speed-auth-cutover.sh", source)
        self.assertIn("explicit production rollback decision", source)
        self.assertNotIn("runtime remains `UNKNOWN`", source)


class WaterRtspTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.transcode_text = (ROOT / "deploy/worker/ubuntu/camera1-h264-transcode.sh").read_text(encoding="utf-8")
        cls.entrypoint_text = (ROOT / "worker/ubuntu_worker_entrypoint.py").read_text(encoding="utf-8")

    def test_transcode_run_hides_credentials_and_configures_transport(self) -> None:
        subprocess.run(["bash", "-n", str(ROOT / "deploy/worker/ubuntu/camera1-h264-transcode.sh")], check=True)
        self.assertIn("CAMERA1_RTSP_TRANSPORT", self.transcode_text)
        self.assertIn("option rtsp_transport", self.transcode_text)
        self.assertIn("-f concat -safe 0", self.transcode_text)
        self.assertIn("-protocol_whitelist file,rtsp,tcp,udp,rtp", self.transcode_text)
        self.assertIn("rm -f /tmp/camera1-h264-input.ffconcat.", self.transcode_text)
        self.assertIn("chmod 0600", self.transcode_text)
        self.assertNotIn('-i "$HLS_URL"', self.transcode_text)
        file_idx = self.transcode_text.index('printf "file \'%s\'\\n"')
        option_idx = self.transcode_text.index("printf 'option rtsp_transport")
        self.assertLess(file_idx, option_idx, "concat `option` needs a preceding `file` directive (NEEDS_FILE)")

    def test_entrypoint_transport_knob_and_ffconcat_contract(self) -> None:
        self.assertIn("CAMERA1_RTSP_TRANSPORT", self.entrypoint_text)
        self.assertIn('os.environ.get("CAMERA1_RTSP_TRANSPORT", "udp")', self.entrypoint_text)
        self.assertIn("ffconcat version 1.0", self.entrypoint_text)
        self.assertIn("option rtsp_transport", self.entrypoint_text)
        self.assertIn('"-f",', self.entrypoint_text)
        self.assertIn('"concat",', self.entrypoint_text)
        self.assertIn('"-protocol_whitelist"', self.entrypoint_text)
        self.assertIn('"file,rtsp,tcp,udp,rtp"', self.entrypoint_text)
        self.assertIn("O_NOFOLLOW", self.entrypoint_text)
        self.assertNotIn("print(input_url)", self.entrypoint_text)
        self.assertIn("NEEDS_FILE", self.entrypoint_text)

    def test_entrypoint_transport_helpers_behavior(self) -> None:
        import unittest.mock as mock

        for name in ("numpy", "cv2", "ultralytics", "av", "requests"):
            if name not in sys.modules:
                sys.modules[name] = mock.MagicMock()
        worker_dir = str(ROOT / "worker")
        if worker_dir not in sys.path:
            sys.path.insert(0, worker_dir)
        import ubuntu_worker_entrypoint as entry

        relay = "rtsp://10.0.0.8:8554/cam1"
        cred = "rtsp://camera_user:camera_key@192.168.88.20:554/Streaming/Channels/101"
        with mock.patch.dict(os.environ, {"CAMERA1_RTSP_TRANSPORT": "udp"}):
            self.assertEqual(entry._camera1_rtsp_transport(relay), "tcp")
            self.assertEqual(entry._camera1_rtsp_transport(cred), "udp")
        with mock.patch.dict(os.environ, {"CAMERA1_RTSP_TRANSPORT": "tcp"}):
            self.assertEqual(entry._camera1_rtsp_transport(cred), "tcp")
        with mock.patch.dict(os.environ, {"CAMERA1_RTSP_TRANSPORT": "bogus"}):
            with self.assertRaises(RuntimeError):
                entry._camera1_rtsp_transport(cred)

        self.assertNotIn("camera_key", entry._redact_media_secrets(f"Impossible to open '{cred}'"))
        self.assertIn("rtsp://[REDACTED]", entry._redact_media_secrets(f"Opening {cred}"))

        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"ANALYTICS_PROFILE": "water-v1"}), mock.patch.object(tempfile, "gettempdir", return_value=tmp):
                path = entry._write_rtsp_ffconcat_input(cred, "udp")
            self.assertTrue(str(path).startswith(tmp))
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            self.assertNotIn("camera_key", path)
            content = Path(path).read_text(encoding="utf-8")
            self.assertIn("ffconcat version 1.0", content)
            self.assertIn("option rtsp_transport udp", content)
            self.assertIn(f"file '{cred}'", content)
            self.assertLess(
                content.index(f"file '{cred}'"),
                content.index("option rtsp_transport udp"),
                "concat `option` needs a preceding `file` directive (NEEDS_FILE)",
            )
            with self.assertRaises(RuntimeError):
                entry._write_rtsp_ffconcat_input("rtsp://u:se'cret@h/x", "udp")


if __name__ == "__main__":
    unittest.main()