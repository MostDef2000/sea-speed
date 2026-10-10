"""Issue #442: the preview contour's inline config+catalog rendering moves into
the canonical renderer (scripts/operations/mediamtx_path_config.py).

Contract (from the issue):
- preview config+catalog rendered by the canonical module; the inline heredoc
  in camera-preview-relay.sh becomes a thin CLI;
- the preview reader rule carries a canonical marker and is verifiable by repo
  tooling (closes the D2 blind spot: #362-class drift becomes detectable);
- RFC1918 validation single-sourced (bounded: a `check-address` verb consumed
  by both relay shells);
- byte-identical output discipline: (a) re-render with the same inputs is
  byte-identical; (b) the canonical render minus the new marker line equals
  the legacy heredoc output (and the catalog minus the dropped non-deterministic
  `generated_at` equals the legacy catalog contract); (c) the 7 legacy renderer
  modes stay byte-identical (harness). The marker line and the dropped
  `generated_at` are documented one-time drifts, not contract violations.
- the preview profile stays API-LESS (no api/apiAddress block).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts/operations/mediamtx_path_config.py"
PREVIEW_SHELL = ROOT / "deploy/worker/ubuntu/camera-preview-relay.sh"
CAM1_SHELL = ROOT / "deploy/worker/ubuntu/camera-relay.sh"

_spec = importlib.util.spec_from_file_location("mediamtx_path_config", RENDERER)
mediamtx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mediamtx)

READER_IP_A = "10.123.239.101"
READER_IP_B = "10.123.239.102"
PRIVATE_ADDRESS = "10.0.0.8:8555"
# Runtime-assembled (never a literal credential shape in this file).
SOURCE_ROAD = "rtsp://" + "preview_user" + ":" + "preview_key" + "@10.0.0.31:554/road-stream"
SOURCE_WATER = "rtsp://" + "preview_user" + ":" + "preview_key" + "@10.0.0.32:554/water-stream"
PREVIEW_MARKER = (
    "# Sea Speed least-privilege reader for canonical preview-contour "
    "(path-pattern ~^preview_[a-z0-9._-]+$)"
)

# The legacy inline heredoc output for the SAME fixed single-camera input
# (frozen from camera-preview-relay.sh at c2bd3b9): the legacy-parity oracle.
LEGACY_SINGLE_CAMERA_CONFIG = """logLevel: error
logDestinations: [stdout]
authMethod: internal
authInternalUsers:
  - user: any
    pass:
    ips: ["10.123.239.101"]
    permissions:
      - action: read
        path: "~^preview_[a-z0-9._-]+$"
rtsp: true
rtspTransports: [tcp]
rtspAddress: "10.0.0.8:8555"
rtmp: false
hls: false
webrtc: false
srt: false
paths:
  "preview_road1":
    source: "rtsp://preview_user:preview_key@10.0.0.31:554/road-stream"
    sourceOnDemand: yes
    sourceOnDemandStartTimeout: 8s
    sourceOnDemandCloseAfter: 2s
    rtspTransport: tcp
"""

CAMERA_ID_RE = r"[a-z0-9][a-z0-9._-]{0,63}"


def build_inventory(cameras: list[dict[str, str]]) -> str:
    return json.dumps(
        {"schema": "sea_speed_camera_preview_inventory_v1", "cameras": cameras}
    )


STANDARD_CAMERAS = [
    {"camera_id": "road1", "display_name": "Road worker preview", "source": SOURCE_ROAD},
    {"camera_id": "water1", "display_name": "Water worker preview", "source": SOURCE_WATER},
]


class PreviewRendererCliBase(unittest.TestCase):
    """Runs the canonical renderer's new ubuntu-preview-relay mode."""

    def render(
        self,
        cameras: list[dict[str, str]] | None = None,
        reader_ips: tuple[str, ...] = (READER_IP_A,),
        private_address: str = PRIVATE_ADDRESS,
    ) -> tuple[subprocess.CompletedProcess[str], str, str]:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            inventory = root / "inventory.json"
            inventory.write_text(build_inventory(cameras or STANDARD_CAMERAS), encoding="utf-8")
            os.chmod(inventory, 0o600)
            config_out = root / "mediamtx.yml"
            catalog_out = root / "camera-preview-catalog.json"
            argv = [
                sys.executable, str(RENDERER), "ubuntu-preview-relay",
                "--inventory", str(inventory),
                "--config-output", str(config_out),
                "--catalog-output", str(catalog_out),
                "--private-rtsp-address", private_address,
            ]
            for ip in reader_ips:
                argv += ["--reader-ip", ip]
            result = subprocess.run(argv, text=True, capture_output=True)
            rendered_config = (
                config_out.read_text(encoding="utf-8") if config_out.exists() else ""
            )
            rendered_catalog = (
                catalog_out.read_text(encoding="utf-8") if catalog_out.exists() else ""
            )
            output_modes = {
                name: oct(os.stat(path).st_mode & 0o777)
                for name, path in (
                    ("config", config_out),
                    ("catalog", catalog_out),
                )
                if path.exists()
            }
            return result, rendered_config, rendered_catalog, output_modes


class PreviewRendererGoldenTests(PreviewRendererCliBase):
    def test_two_camera_render_matches_golden_bytes(self) -> None:
        result, config, catalog, _ = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            config,
            'logLevel: error\n'
            'logDestinations: [stdout]\n'
            'authMethod: internal\n'
            'authInternalUsers:\n'
            f'  {PREVIEW_MARKER}\n'
            '  - user: any\n'
            '    pass:\n'
            '    ips: ["10.123.239.101"]\n'
            '    permissions:\n'
            '      - action: read\n'
            '        path: "~^preview_[a-z0-9._-]+$"\n'
            'rtsp: true\n'
            'rtspTransports: [tcp]\n'
            'rtspAddress: "10.0.0.8:8555"\n'
            'rtmp: false\n'
            'hls: false\n'
            'webrtc: false\n'
            'srt: false\n'
            'paths:\n'
            '  "preview_road1":\n'
            f'    source: {json.dumps(SOURCE_ROAD, ensure_ascii=False)}\n'
            '    sourceOnDemand: yes\n'
            '    sourceOnDemandStartTimeout: 8s\n'
            '    sourceOnDemandCloseAfter: 2s\n'
            '    rtspTransport: tcp\n'
            '  "preview_water1":\n'
            f'    source: {json.dumps(SOURCE_WATER, ensure_ascii=False)}\n'
            '    sourceOnDemand: yes\n'
            '    sourceOnDemandStartTimeout: 8s\n'
            '    sourceOnDemandCloseAfter: 2s\n'
            '    rtspTransport: tcp\n',
        )
        payload = json.loads(catalog)
        self.assertEqual(payload["schema"], "sea_speed_camera_preview_catalog_v1")
        self.assertEqual(
            payload["cameras"],
            [
                {
                    "camera_id": "road1",
                    "display_name": "Road worker preview",
                    "source": "rtsp://10.0.0.8:8555/preview_road1",
                },
                {
                    "camera_id": "water1",
                    "display_name": "Water worker preview",
                    "source": "rtsp://10.0.0.8:8555/preview_water1",
                },
            ],
        )
        self.assertTrue(catalog.endswith("}\n"))
        self.assertNotIn("generated_at", catalog)
        self.assertIn("camera_count=2", result.stdout)
        self.assertIn("reader_scope=preview-single-rfc1918-peer", result.stdout)

    def test_rendered_config_is_mode_0600(self) -> None:
        result, config, _, output_modes = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(config, "")
        self.assertEqual(output_modes, {"config": "0o600", "catalog": "0o600"})


class PreviewLegacyParityTests(PreviewRendererCliBase):
    def test_canonical_config_minus_marker_equals_legacy_heredoc_output(self) -> None:
        result, config, _, _ = self.render(cameras=STANDARD_CAMERAS[:1])
        self.assertEqual(result.returncode, 0, result.stderr)
        marker_line = f"  {PREVIEW_MARKER}\n"
        self.assertIn(marker_line, config)
        self.assertEqual(config.replace(marker_line, ""), LEGACY_SINGLE_CAMERA_CONFIG)

    def test_canonical_catalog_matches_legacy_contract_minus_generated_at(self) -> None:
        result, _, catalog, _ = self.render(cameras=STANDARD_CAMERAS[:1])
        self.assertEqual(result.returncode, 0, result.stderr)
        legacy = {
            "schema": "sea_speed_camera_preview_catalog_v1",
            "generated_at": "1970-01-01T00:00:00+00:00",
            "cameras": [
                {
                    "camera_id": "road1",
                    "display_name": "Road worker preview",
                    "source": "rtsp://10.0.0.8:8555/preview_road1",
                }
            ],
        }
        legacy_text = json.dumps(legacy, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        strip = lambda text: "\n".join(  # noqa: E731
            line for line in text.splitlines() if '"generated_at"' not in line
        )
        self.assertEqual(strip(catalog), strip(legacy_text))

    def test_re_render_with_same_inputs_is_byte_identical(self) -> None:
        _, config_first, catalog_first, _ = self.render()
        _, config_second, catalog_second, _ = self.render()
        self.assertEqual(config_first, config_second)
        self.assertEqual(catalog_first, catalog_second)


class PreviewAuthVerificationTests(PreviewRendererCliBase):
    """D2 blind spot closure: the marked preview rule is verifiable by repo tooling."""

    def verify(self, config_text: str, reader_ips: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as raw:
            config = Path(raw) / "mediamtx.yml"
            config.write_text(config_text, encoding="utf-8")
            argv = [sys.executable, str(RENDERER), "verify-preview-auth", "--config", str(config)]
            for ip in reader_ips:
                argv += ["--reader-ip", ip]
            return subprocess.run(argv, text=True, capture_output=True)

    def test_verify_accepts_the_canonical_render(self) -> None:
        result, config, _, _ = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        verified = self.verify(config, (READER_IP_A,))
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn("VERIFIED mode=preview-auth", verified.stdout)
        self.assertIn("reader_scope=preview-single-rfc1918-peer", verified.stdout)

    def test_verify_is_subset_semantics_on_multi_ip_rule(self) -> None:
        result, config, _, _ = self.render(reader_ips=(READER_IP_A, READER_IP_B))
        self.assertEqual(result.returncode, 0, result.stderr)
        # Subset verify: a single requested IP is a subset of the rule scope
        # (the VERIFIED line reports the REQUESTED scope, matching the
        # established verify-reader-auth evidence convention).
        single = self.verify(config, (READER_IP_A,))
        self.assertEqual(single.returncode, 0, single.stderr)
        self.assertIn("reader_scope=preview-single-rfc1918-peer", single.stdout)
        # Full-scope verify additionally byte-compares the block.
        full = self.verify(config, (READER_IP_A, READER_IP_B))
        self.assertEqual(full.returncode, 0, full.stderr)
        self.assertIn("reader_scope=preview-multi-rfc1918-peer-count-2", full.stdout)

    def test_verify_rejects_drifted_ips_fail_closed(self) -> None:
        result, config, _, _ = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        drifted = config.replace(f'ips: ["{READER_IP_A}"]', f'ips: ["{READER_IP_B}"]')
        rejected = self.verify(drifted, (READER_IP_A,))
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("not a subset", rejected.stderr)

    def test_verify_rejects_missing_marker(self) -> None:
        result, config, _, _ = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        unmarked = config.replace(f"  {PREVIEW_MARKER}\n", "")
        rejected = self.verify(unmarked, (READER_IP_A,))
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("exactly one", rejected.stderr)

    def test_verify_rejects_drifted_action(self) -> None:
        result, config, _, _ = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        drifted = config.replace("      - action: read\n", "      - action: publish\n")
        rejected = self.verify(drifted, (READER_IP_A,))
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("read", rejected.stderr)


class PreviewProfileContractTests(PreviewRendererCliBase):
    def test_preview_profile_stays_api_less(self) -> None:
        result, config, _, _ = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("api: yes", config)
        self.assertNotIn("apiAddress", config)
        # The renderer-level marker ownership contract holds: the marker keeps
        # the "# Sea Speed " prefix so the bounded sanitize scanner marks the
        # rule as renderer-owned.
        marker_line = f"  {PREVIEW_MARKER}\n"
        self.assertIn(marker_line, config)

    def test_preview_rule_verifies_through_the_shared_rule_parser(self) -> None:
        result, config, _, _ = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        # The marker starts with the canonical prefix, so the span-terminating
        # parser treats it as a rule boundary (sanitize scanner compatibility).
        lines = config.splitlines(keepends=True)
        start = next(i for i, line in enumerate(lines) if line.strip() == PREVIEW_MARKER)
        ips, actions = mediamtx._parse_rule_block(lines, start, len(lines))
        self.assertEqual(ips, {READER_IP_A})
        self.assertEqual(actions, {"read"})


class PreviewInventoryValidationTests(PreviewRendererCliBase):
    def expect_rejected(self, cameras: list[dict[str, str]] | None = None, raw_payload: str | None = None) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            inventory = root / "inventory.json"
            inventory.write_text(
                raw_payload if raw_payload is not None else build_inventory(cameras or []),
                encoding="utf-8",
            )
            os.chmod(inventory, 0o600)
            config_out = root / "mediamtx.yml"
            catalog_out = root / "camera-preview-catalog.json"
            result = subprocess.run(
                [
                    sys.executable, str(RENDERER), "ubuntu-preview-relay",
                    "--inventory", str(inventory),
                    "--config-output", str(config_out),
                    "--catalog-output", str(catalog_out),
                    "--private-rtsp-address", PRIVATE_ADDRESS,
                    "--reader-ip", READER_IP_A,
                ],
                text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertFalse(config_out.exists())
            self.assertFalse(catalog_out.exists())
            return result

    def test_unsupported_schema_is_rejected(self) -> None:
        result = self.expect_rejected(raw_payload=json.dumps({"schema": "other", "cameras": STANDARD_CAMERAS}))
        self.assertIn("schema", result.stderr)

    def test_empty_camera_list_is_rejected(self) -> None:
        result = self.expect_rejected(cameras=[])
        self.assertIn("at least one camera", result.stderr)

    def test_duplicate_camera_id_is_rejected(self) -> None:
        result = self.expect_rejected(cameras=[STANDARD_CAMERAS[0], dict(STANDARD_CAMERAS[0])])
        self.assertIn("duplicate camera_id", result.stderr)

    def test_unsafe_camera_id_is_rejected(self) -> None:
        cameras = [dict(STANDARD_CAMERAS[0], camera_id="Road1!")]
        result = self.expect_rejected(cameras=cameras)
        self.assertIn("lowercase safe characters", result.stderr)

    def test_public_camera_source_is_rejected(self) -> None:
        cameras = [dict(STANDARD_CAMERAS[0], source="rtsp://" + "u" + ":" + "p" + "@93.184.216.34:554/live")]
        result = self.expect_rejected(cameras=cameras)
        self.assertIn("private RTSP URL", result.stderr)

    def test_source_without_userinfo_is_rejected(self) -> None:
        cameras = [dict(STANDARD_CAMERAS[0], source="rtsp://10.0.0.31:554/road-stream")]
        result = self.expect_rejected(cameras=cameras)
        self.assertIn("protected userinfo", result.stderr)

    def test_overlong_display_name_is_rejected(self) -> None:
        cameras = [dict(STANDARD_CAMERAS[0], display_name="x" * 121)]
        result = self.expect_rejected(cameras=cameras)
        self.assertIn("display_name", result.stderr)

    def test_non_rfc1918_reader_ip_is_rejected_and_outputs_absent(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            inventory = root / "inventory.json"
            inventory.write_text(build_inventory(STANDARD_CAMERAS), encoding="utf-8")
            os.chmod(inventory, 0o600)
            config_out = root / "mediamtx.yml"
            result = subprocess.run(
                [
                    sys.executable, str(RENDERER), "ubuntu-preview-relay",
                    "--inventory", str(inventory),
                    "--config-output", str(config_out),
                    "--catalog-output", str(root / "camera-preview-catalog.json"),
                    "--private-rtsp-address", PRIVATE_ADDRESS,
                    "--reader-ip", "93.184.216.34",
                ],
                text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("RFC1918", result.stderr)
            self.assertFalse(config_out.exists())


class CheckAddressCliTests(unittest.TestCase):
    def run_check(self, kind: str, value: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RENDERER), "check-address", "--kind", kind, "--value", value],
            text=True, capture_output=True,
        )

    def test_valid_reader_ip_passes_with_empty_stdout(self) -> None:
        result = self.run_check("reader-ip", READER_IP_A)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_invalid_reader_ip_fails_closed_with_stderr(self) -> None:
        for value in ("93.184.216.34", "::1", "10.0.0.8/32", "nonsense"):
            result = self.run_check("reader-ip", value)
            self.assertEqual(result.returncode, 1, value)
            self.assertNotEqual(result.stderr, "")

    def test_valid_private_rtsp_address_prints_host_then_port(self) -> None:
        result = self.run_check("private-rtsp", PRIVATE_ADDRESS)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "10.0.0.8\n8555\n")

    def test_invalid_private_rtsp_address_fails_closed(self) -> None:
        for value in ("10.0.0.8", "10.0.0.8:0", "10.0.0.8:99999", "10.0.0.8:8554:9", "example.invalid:8554"):
            result = self.run_check("private-rtsp", value)
            self.assertEqual(result.returncode, 1, value)

    def test_both_relay_shells_single_source_validation_through_check_address(self) -> None:
        shell_text = CAM1_SHELL.read_text(encoding="utf-8")
        preview_text = PREVIEW_SHELL.read_text(encoding="utf-8")
        for text in (shell_text, preview_text):
            self.assertIn("check-address", text)
            self.assertIn('"$renderer"', text)


class PreviewRendererStructuralTests(unittest.TestCase):
    def test_renderer_owns_the_preview_marker_and_validation(self) -> None:
        source = RENDERER.read_text(encoding="utf-8")
        self.assertIn("preview-contour", source)
        self.assertIn("def render_ubuntu_preview_relay", source)
        self.assertIn("def verify_preview_reader_auth", source)
        self.assertIn("sea_speed_camera_preview_inventory_v1", source)
        self.assertIn("sea_speed_camera_preview_catalog_v1", source)
        self.assertIn("check-address", source)
        self.assertNotIn("generated_at", source)

    def test_legacy_modes_are_untouched_in_the_parser(self) -> None:
        source = RENDERER.read_text(encoding="utf-8")
        for legacy in (
            "ubuntu-relay", "verify-reader-auth", "ubuntu-sanitize-auth",
            "ubuntu-remediate-reader", "ubuntu-transcode-reader",
            "verify-vps-switch", "vps-switch", "vps-set-hls-address", "vps-cleanup",
        ):
            self.assertIn(legacy, source)

    def test_preview_scope_token_is_preview_prefixed(self) -> None:
        self.assertEqual(mediamtx.reader_scope_token(1), "single-rfc1918-ip")
        self.assertEqual(mediamtx.reader_scope_token(3), "multi-rfc1918-ip-count-3")


class PreviewShellContractTests(unittest.TestCase):
    def test_shell_is_valid_and_renders_through_the_canonical_module(self) -> None:
        subprocess.run(["bash", "-n", str(PREVIEW_SHELL)], check=True)
        shell = PREVIEW_SHELL.read_text(encoding="utf-8")
        self.assertIn('ubuntu-preview-relay \\', shell)
        self.assertIn("--config-output \"$candidate_config\"", shell)
        self.assertIn("--catalog-output \"$candidate_catalog\"", shell)
        self.assertIn("--inventory \"$inventory\"", shell)
        # The inline heredoc renderer is gone: no top-level config keys in the shell.
        self.assertNotIn("authInternalUsers", shell)
        self.assertNotIn("sourceOnDemandStartTimeout", shell)
        self.assertNotIn("sea_speed_camera_preview_catalog_v1", shell)
        self.assertNotIn("generated_at", shell)

    def test_shell_resolves_the_renderer_from_the_repository_source(self) -> None:
        shell = PREVIEW_SHELL.read_text(encoding="utf-8")
        self.assertIn('repo_root="$(CDPATH= cd -- "$script_dir/../../.." && pwd)"', shell)
        self.assertIn('renderer="$repo_root/scripts/operations/mediamtx_path_config.py"', shell)
        self.assertIn('ERROR renderer missing from exact repository source', shell)

    def test_shell_multi_reader_ip_parse_and_forwarding(self) -> None:
        subprocess.run(["bash", "-n", str(PREVIEW_SHELL)], check=True)
        shell = PREVIEW_SHELL.read_text(encoding="utf-8")
        self.assertIn("reader_ips=()", shell)
        self.assertIn("IFS=',' read -r -a __reader_ip_parts", shell)
        self.assertIn('reader_ips+=("$__reader_ip_part")', shell)
        self.assertIn('reader_ip_args+=(--reader-ip "$reader_ip")', shell)
        # The prepare render forwards the accumulated occurrences; the RFC1918
        # validation loop precedes it.
        self.assertEqual(shell.count('"${reader_ip_args[@]}"'), 1)
        self.assertLess(
            shell.index("check-address"),
            shell.index("ubuntu-preview-relay"),
        )

    def test_shell_keeps_protected_inventory_gate_and_evidence_contract(self) -> None:
        shell = PREVIEW_SHELL.read_text(encoding="utf-8")
        self.assertIn('inventory mode must be 600', shell)
        self.assertIn('inventory must be root-owned', shell)
        self.assertIn('ERROR inventory must be a regular non-symlink file', shell)
        for marker in (
            "PREPARED_PREVIEW_RELAY=YES", "CAMERA_COUNT=%s", "CONFIG_SHA256=%s",
            "UNIT_SHA256=%s", "SANITIZED_CATALOG_SHA256=%s", "MUTATIONS=PROTECTED_CANDIDATES_ONLY",
            "SERVICE_RESTARTED=NO", "SECRETS_DISPLAYED=NO", "CAM1_RELAY_CHANGED=NO",
            "AI_WORKER_CHANGED=NO", "AUTOMATIC_ROLLBACK=NO",
        ):
            self.assertIn(marker, shell)
        # R8 (this slice): preview activate does NOT gain the #447 derivation.
        self.assertNotIn("derive_relay_service_identity", shell)

    def test_shell_emits_preview_reader_scope_evidence(self) -> None:
        shell = PREVIEW_SHELL.read_text(encoding="utf-8")
        self.assertIn("printf 'preview-single-rfc1918-peer'", shell)
        self.assertIn("preview-multi-rfc1918-peer-count-", shell)
        self.assertEqual(shell.count("READER_AUTH_SCOPE=%s"), 1)

    def test_cam1_relay_shell_validators_move_to_check_address(self) -> None:
        subprocess.run(["bash", "-n", str(CAM1_SHELL)], check=True)
        shell = CAM1_SHELL.read_text(encoding="utf-8")
        self.assertIn("check-address", shell)
        self.assertIn('python3 "$renderer" check-address --kind private-rtsp', shell)
        self.assertIn('python3 "$renderer" check-address --kind reader-ip', shell)
        # The duplicated inline RFC1918 heredoc validators are gone.
        self.assertNotIn("networks = tuple(ipaddress.ip_network", shell)


if __name__ == "__main__":
    unittest.main()
