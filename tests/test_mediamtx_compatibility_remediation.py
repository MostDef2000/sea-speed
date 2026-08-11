from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/vps/mediamtx-compatibility-remediation.sh"
DOC = ROOT / "docs/operations/MEDIAMTX_COMPATIBILITY_REMEDIATION.md"


def shell_function(source: str, name: str) -> str:
    start = source.index(f"{name}() {{")
    end = source.index("\n}\n\n", start) + 2
    return source[start:end]


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
        self.assertIn("api: no", source)
        self.assertIn("metrics: no", source)
        self.assertIn("pprof: no", source)
        self.assertIn("playback: no", source)
        self.assertIn("rtmp: no", source)
        self.assertIn("webrtc: no", source)
        self.assertIn("srt: no", source)
        self.assertIn("moq: no", source)
        self.assertIn('--property="User=$service_user"', source)
        self.assertIn('--property="Group=$service_group"', source)
        self.assertIn("sourceOnDemand: yes", source)
        self.assertIn("rtspTransport: tcp", source)
        self.assertNotIn("0.0.0.0:18954", source)
        self.assertNotIn("0.0.0.0:18888", source)

    def test_canary_requires_actual_rtsp_and_hls_media_before_activation_marker(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        active_config_check = source.index('config_check_unit="sea-speed-mediamtx-config-check-')
        canary_start = source.index('canary_unit="sea-speed-mediamtx-canary-')
        rtsp_gate = source.index('if [[ "$rtsp_ok" != true ]]')
        hls_gate = source.index('if [[ "$hls_ok" != true ]]')
        marker_write = source.index('cat > "$marker_tmp"')
        self.assertLess(active_config_check, canary_start)
        self.assertLess(canary_start, rtsp_gate)
        self.assertLess(rtsp_gate, hls_gate)
        self.assertLess(hls_gate, marker_write)
        self.assertIn('probe_two_frames "$canary_rtsp_url" rtsp-tcp', source)
        self.assertIn('probe_two_frames "$canary_hls_probe_url"', source)
        self.assertIn("active_config_compatibility=pass", source)
        self.assertIn("COMPATIBILITY_CANARY=PASS", source)
        self.assertIn("PRODUCTION_BINARY_CHANGED=NO", source)
        self.assertIn("MEDIAMTX_RESTARTED=NO", source)

    def test_v120_startup_regression_disables_moq_and_waits_for_listener_readiness(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        config = source.split('cat > "$run_config" <<EOF_CONFIG', 1)[1].split("EOF_CONFIG", 1)[0]

        self.assertIn("rtsp: yes", config)
        self.assertIn("hls: yes", config)
        self.assertIn("sourceOnDemand: yes", config)
        self.assertIn("moq: no", config)
        self.assertIn("hlsVariant: fmp4", config)
        self.assertNotIn("moq: yes", config)
        self.assertNotIn("hlsVariant: mpegts", config)
        self.assertIn('canary_listeners_ready "$rtsp_port" "$hls_port"', source)
        self.assertNotIn("sleep 1\n  kill -0", source)

    def test_hls_probe_uses_cookie_check_and_decodes_media(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('canary_hls_probe_url="${canary_hls_url}?cookieCheck=1"', source)
        self.assertIn('probe_two_frames "$canary_hls_probe_url"', source)
        self.assertIn('production_hls_probe_url="${production_hls_url}?cookieCheck=1"', source)
        self.assertIn('probe_two_frames "$production_hls_probe_url"', source)
        self.assertIn("HLS_MPEGTS_H265_UNSUPPORTED", source)

    def test_active_config_compatibility_is_sandboxed_and_marker_bound(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('install -o root -g "$service_group" -m 0640 "$config" "$active_config"', source)
        self.assertIn("--property=PrivateNetwork=yes", source)
        self.assertIn("--property=ProtectSystem=strict", source)
        self.assertIn("--property=PrivateUsers=self", source)
        self.assertIn("--property=RestrictNamespaces=yes", source)
        self.assertIn("--property=NoExecPaths=/", source)
        self.assertIn('--property="ReadWritePaths=$run_root"', source)
        self.assertIn('/usr/bin/env -i PATH=/usr/bin:/bin HOME=/nonexistent "$run_binary" "$active_config"', source)
        self.assertNotIn("MTX_MOQ=false", source)
        self.assertNotIn("unshare --net", source)
        self.assertIn('systemctl is-active --quiet "$config_check_unit"', source)
        self.assertIn("--property=IPAddressDeny=any", source)
        self.assertIn('--property="IPAddressAllow=$relay_address/32"', source)
        self.assertIn("service_contract_sha256=", source)
        self.assertIn("tool_sha256=", source)
        self.assertIn('[[ "$marker_active_config_compatibility" == pass ]]', source)
        self.assertIn('[[ "$marker_service_contract_sha" == "$service_contract_sha" ]]', source)
        self.assertIn('[[ "$marker_tool_sha" == "$tool_sha" ]]', source)
        marker_validation = source.index('[[ "$marker_active_config_compatibility" == pass ]]')
        binary_replacement = source.index('install -o "$owner" -g "$group" -m "$mode" "$persistent_candidate"')
        self.assertLess(marker_validation, binary_replacement)

    def test_relay_url_validation_rejects_ambiguous_or_credential_bearing_values(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        function = shell_function(source, "validate_relay_url")

        for value in (
            "rtsp://10.1.2.3/cam1",
            "rtsp://user:secret@10.1.2.3:8554/cam1",
            "rtsp://10.1.2.3:8554/cam1?token=value",
            "rtsp://10.1.2.3:8554/cam1/",
            "rtsp://127.0.0.1:8554/cam1",
        ):
            result = subprocess.run(
                ["bash", "-c", f'{function}\nrelay_url="$1"\nvalidate_relay_url', "_", value],
                check=False,
            )
            self.assertNotEqual(result.returncode, 0, value)

        subprocess.run(
            ["bash", "-c", f'{function}\nrelay_url="$1"\nvalidate_relay_url', "_", "rtsp://10.1.2.3:8554/cam1"],
            check=True,
            capture_output=True,
        )

    def test_media_probe_requires_progress_for_at_least_two_frames(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        function = shell_function(source, "probe_two_frames")

        one_frame = subprocess.run(
            ["bash", "-c", f"{function}\ntimeout() {{ printf 'frame=1\\nprogress=end\\n'; }}\nprobe_two_frames test"],
            check=False,
        )
        self.assertNotEqual(one_frame.returncode, 0)

        subprocess.run(
            ["bash", "-c", f"{function}\ntimeout() {{ printf 'frame=1\\nframe=2\\nprogress=end\\n'; }}\nprobe_two_frames test"],
            check=True,
        )

    def test_failure_diagnostic_classification_is_protected(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        function = shell_function(source, "preserve_failure_log")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            log = root / "candidate.log"
            log.write_text("native MoQ QUIC listener: open auto.key: permission denied\n", encoding="utf-8")
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f'{function}\ndiagnostic_root="$1"\ncandidate_sha="$(printf a%.0s {{1..64}})"\npreserve_failure_log STARTUP "$2"',
                    "_",
                    str(root),
                    str(log),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("CANARY_FAILURE_REASON=MOQ_TLS_KEYPAIR_PERMISSION_DENIED", result.stderr)
            preserved = list(root.glob("canary.*.STARTUP.*.log"))
            self.assertEqual(len(preserved), 1)
            self.assertEqual(preserved[0].stat().st_mode & 0o777, 0o600)

    def test_transient_unit_cleanup_stops_and_verifies_the_unit(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        function = shell_function(source, "stop_transient_unit")

        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f'{function}\nstate_file="$1/stopped"\nsystemctl() {{ if [[ "$1" == show ]]; then [[ -f "$state_file" ]] && printf "inactive\\n" || printf "active\\n"; elif [[ "$1" == stop ]]; then touch "$state_file"; fi; }}\nstop_transient_unit test.service\n[[ -f "$state_file" ]]',
                    "_",
                    directory,
                ],
                check=True,
            )

    def test_cam1_contract_binds_relay_transport_and_hls_port(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")
        function = shell_function(source, "verify_cam1_contract")

        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "mediamtx.yml"
            valid = "hls: yes\nhlsAddress: :8888\npaths:\n  cam1:\n    source: rtsp://10.1.2.3:8554/cam1\n    sourceOnDemand: yes\n    rtspTransport: tcp\n"
            config.write_text(valid, encoding="utf-8")
            command = f'{function}\nrelay_url="rtsp://10.1.2.3:8554/cam1"\nproduction_hls_url="http://127.0.0.1:8888/cam1/index.m3u8"\nverify_cam1_contract "$1"'
            subprocess.run(["bash", "-c", command, "_", str(config)], check=True)

            config.write_text(valid.replace("rtspTransport: tcp", "rtspTransport: udp"), encoding="utf-8")
            result = subprocess.run(["bash", "-c", command, "_", str(config)], check=False)
            self.assertNotEqual(result.returncode, 0)

            config.write_text("hls: yes\nhlsAddress: :8888\nhlsVariant: mpegts\npaths:\n  cam1:\n    source: rtsp://10.1.2.3:8554/cam1\n    sourceOnDemand: yes\n    rtspTransport: tcp\n", encoding="utf-8")
            result = subprocess.run(["bash", "-c", command, "_", str(config)], check=False)
            self.assertNotEqual(result.returncode, 0)

    def test_startup_failure_evidence_is_protected_and_sanitized(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('diagnostic_root="$state_root/diagnostics"', source)
        self.assertIn('install -o root -g root -m 0600 "$source" "$destination"', source)
        self.assertIn("MOQ_TLS_KEYPAIR_PERMISSION_DENIED", source)
        self.assertIn("CANARY_FAILURE_CATEGORY", source)
        self.assertIn("CANARY_FAILURE_REASON", source)
        self.assertIn("CANARY_FAILURE_LOG", source)
        self.assertNotIn('cat "$destination"', source)

    def test_activation_changes_only_binary_after_canary_and_requires_real_production_hls(self) -> None:
        source = SCRIPT.read_text(encoding="utf-8")

        self.assertIn('install -o root -g root -m 0700 "$installed_binary" "$backup"', source)
        self.assertIn('install -o "$owner" -g "$group" -m "$mode" "$persistent_candidate" "$activation_next"', source)
        self.assertIn('mv -f "$activation_next" "$installed_binary"', source)
        self.assertEqual(source.count('systemctl restart "$service_name"'), 1)
        self.assertIn('probe_two_frames "$production_hls_probe_url"', source)
        self.assertIn("write_activation_state prepared", source)
        self.assertIn("write_activation_state binary_replaced", source)
        self.assertIn("write_activation_state complete", source)
        self.assertIn('sha256sum "/proc/$main_pid/exe"', source)
        self.assertNotIn('$installed_binary --version', source)
        self.assertIn("MEDIAMTX_COMPATIBILITY_ACTIVATED=YES", source)
        self.assertIn("LOCAL_CANONICAL_HLS_MEDIA=PASS", source)
        self.assertIn("PREVIOUS_BINARY_BACKUP", source)
        self.assertIn("automatic rollback is not authorized", source)
        self.assertNotIn("ROLLBACK_PERFORMED=YES", source)
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
        self.assertIn("sandboxed active-config compatibility proof", source)
        self.assertIn("MoQ", source)
        self.assertIn("/cams/hls/cam1/index.m3u8", source)
        self.assertIn("CONFIRM_NEW_CAMERA", source)
        self.assertIn("cam1-new", source)
        self.assertIn("sea-speed-worker.service", source)
        self.assertIn("Automatic rollback remains prohibited", source)
        self.assertIn("one OpenCode rollout scope", source)


if __name__ == "__main__":
    unittest.main()
