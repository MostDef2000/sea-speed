from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/vps/mediamtx-compatibility-remediation.sh"
DOC = ROOT / "docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md"


class MediaMTXCompatibilityRemediationTests(unittest.TestCase):
    def test_shell_is_valid_and_exposes_digest_bound_prepare_activate_contract(self) -> None:
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn("prepare|activate|status", source)
        self.assertIn("--candidate-archive", source)
        self.assertIn("--candidate-version", source)
        self.assertIn("--expected-archive-sha256", source)
        self.assertIn("--expected-candidate-sha256", source)
        self.assertIn("CANDIDATE_ARCHIVE_SHA256", source)
        self.assertIn("CANDIDATE_BINARY_SHA256", source)
        self.assertIn("ACTIVE_CONFIG_SHA256", source)
        self.assertIn("installed_sha256=", source)
        self.assertIn("config_sha256=", source)
        self.assertIn("successful compatibility canary marker is missing", source)

    def test_canary_is_loopback_only_and_runs_as_existing_service_user(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('canary_rtsp_address="127.0.0.1:18954"', source)
        self.assertIn('canary_hls_address="127.0.0.1:18888"', source)
        self.assertIn('if host != "127.0.0.1"', source)
        self.assertIn("rtspTransports: [tcp]", source)
        self.assertIn("rtmp: no", source)
        self.assertIn("webrtc: no", source)
        self.assertIn("srt: no", source)
        self.assertIn('runuser -u "$service_user"', source)
        self.assertIn("sourceOnDemand: yes", source)
        self.assertIn("rtspTransport: tcp", source)
        self.assertNotIn("0.0.0.0:18954", source)
        self.assertNotIn("0.0.0.0:18888", source)

    def test_canary_requires_actual_rtsp_and_hls_media_before_activation_marker(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        marker_write = source.index('marker="$marker_root/$candidate_sha.ok"')
        rtsp_probe = source.index('CANARY_RTSP_MEDIA=PASS')
        hls_probe = source.index('CANARY_HLS_MEDIA=PASS')
        self.assertLess(marker_write, rtsp_probe)
        self.assertLess(marker_write, hls_probe)
        self.assertIn('probe_two_frames "$canary_rtsp_url" rtsp-tcp', source)
        self.assertIn('probe_two_frames "$canary_hls_url"', source)
        self.assertIn("COMPATIBILITY_CANARY=PASS", source)
        self.assertIn("PRODUCTION_BINARY_CHANGED=NO", source)
        self.assertIn("MEDIAMTX_RESTARTED=NO", source)

    def test_activation_changes_only_binary_after_canary_and_requires_real_production_hls(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('install -o root -g root -m 0700 "$installed_binary" "$backup"', source)
        self.assertIn('install -o "$owner" -g "$group" -m "$mode" "$persistent_candidate" "${installed_binary}.next"', source)
        self.assertIn('mv -f "${installed_binary}.next" "$installed_binary"', source)
        self.assertEqual(source.count('systemctl restart "$service_name"'), 1)
        self.assertIn('probe_two_frames "$production_hls_url"', source)
        self.assertIn("MEDIAMTX_COMPATIBILITY_ACTIVATED=YES", source)
        self.assertIn("LOCAL_CANONICAL_HLS_MEDIA=PASS", source)
        self.assertIn("PREVIOUS_BINARY_BACKUP", source)
        self.assertIn("automatic rollback is not authorized", source)
        self.assertNotIn("sea-speed-worker.service", source)
        self.assertNotIn("worker.env", source)
        self.assertNotIn("sudo -S", source)
        self.assertNotIn("StrictHostKeyChecking=no", source)

    def test_documentation_defines_single_final_live_completion_flow(self) -> None:
        source = DOC.read_text(encoding="utf-8")

        self.assertIn("E_RTSP_HANDSHAKE_COMPATIBILITY", source)
        self.assertIn("official `bluenviron/mediamtx` release", source)
        self.assertIn("checksums.sha256", source)
        self.assertIn("loopback-only compatibility canary", source)
        self.assertIn("/cams/hls/cam1/index.m3u8", source)
        self.assertIn("CONFIRM_NEW_CAMERA", source)
        self.assertIn("cam1-new", source)
        self.assertIn("sea-speed-worker.service", source)
        self.assertIn("Automatic rollback remains prohibited", source)
        self.assertIn("one OpenCode rollout scope", source)


if __name__ == "__main__":
    unittest.main()
