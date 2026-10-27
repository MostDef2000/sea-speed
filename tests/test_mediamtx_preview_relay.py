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
  Issue #522 adds a third documented one-time drift: the server skeleton
  pins every unused default server off (`api/metrics/pprof/playback/moq:
  false` next to the existing `rtmp/hls/webrtc/srt: false`) — the parity
  oracle below freezes the bumped bytes.
- the preview profile stays API-LESS (`api: false`, no `apiAddress` block).
"""
from __future__ import annotations

import ast
import hashlib
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
sys.path.insert(0, str(ROOT / "tests"))

_spec = importlib.util.spec_from_file_location("mediamtx_path_config", RENDERER)
mediamtx = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mediamtx)

from support import relay_shell  # noqa: E402

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

# Parity oracle for the fixed single-camera input: the legacy inline heredoc
# output (frozen from camera-preview-relay.sh at c2bd3b9) PLUS the documented
# #522 skeleton bump — every unused default server explicitly pinned off
# (D-3 one-time synchronized drift; renderer + tests + runbook in one change).
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
api: false
metrics: false
pprof: false
playback: false
moq: false
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
            'api: false\n'
            'metrics: false\n'
            'pprof: false\n'
            'playback: false\n'
            'moq: false\n'
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
        # #522 (D-3): the parity oracle carries the documented one-time
        # skeleton bump (five explicit server-off toggles); the #442 parity
        # shape (canonical render minus the marker) is otherwise unchanged.
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

    def test_verify_rejects_drifted_path_pattern_fail_closed(self) -> None:
        # Issue #452 (F1): the full-scope byte-exact comparison is the SOLE
        # drift detector for a mutated `path:` pattern line — the marker (which
        # embeds the canonical pattern), the ips and the action stay intact, so
        # the marker-count, subset and read checks all pass and only the
        # byte-exact branch can reject. The drift is a realistic loosening of
        # the preview path pattern (grants read on non-preview paths).
        result, config, _, _ = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        canonical_path_line = '        path: "~^preview_[a-z0-9._-]+$"\n'
        self.assertEqual(config.count(canonical_path_line), 1)
        drifted = config.replace(
            canonical_path_line, '        path: "~^preview_.*$"\n'
        )
        self.assertIn(f"  {PREVIEW_MARKER}\n", drifted)  # marker line untouched
        self.assertIn(f'ips: ["{READER_IP_A}"]', drifted)  # ips untouched
        rejected = self.verify(drifted, (READER_IP_A,))  # full-scope request
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("does not match the requested rule", rejected.stderr)


class PreviewProfileContractTests(PreviewRendererCliBase):
    def test_preview_profile_stays_api_less(self) -> None:
        result, config, _, _ = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("api: yes", config)
        self.assertNotIn("apiAddress", config)
        # #522: the API server is not merely absent — it is explicitly pinned
        # off in the rendered skeleton (stronger than absence).
        self.assertIn("api: false\n", config)
        # The renderer-level marker ownership contract holds: the marker keeps
        # the "# Sea Speed " prefix so the bounded sanitize scanner marks the
        # rule as renderer-owned.
        marker_line = f"  {PREVIEW_MARKER}\n"
        self.assertIn(marker_line, config)

    def test_preview_profile_pins_all_unused_servers_off(self) -> None:
        # #522 (R-1/R-2): every unused default server is explicitly pinned off
        # in the rendered skeleton — no reliance on mediamtx version defaults —
        # while the RTSP endpoint stays enabled (R-4).
        result, config, _, _ = self.render()
        self.assertEqual(result.returncode, 0, result.stderr)
        for key in ("api", "metrics", "pprof", "playback", "moq"):
            self.assertIn(f"{key}: false\n", config)
        self.assertIn("rtsp: true\n", config)

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
        # 398-wave3: converted from source-text pins (was L493-L501) — the
        # renderer's ownership of the preview contour is asserted on the
        # parsed AST: the two contract functions exist as definitions, the
        # contour/schema/check-address strings exist as constants, and no
        # string constant reintroduces the dropped `generated_at` field.
        tree = ast.parse(RENDERER.read_text(encoding="utf-8"))
        function_names = {
            node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
        }
        self.assertIn("render_ubuntu_preview_relay", function_names)
        self.assertIn("verify_preview_reader_auth_config", function_names)
        constants = {
            node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        self.assertIn("sea_speed_camera_preview_inventory_v1", constants)
        self.assertIn("sea_speed_camera_preview_catalog_v1", constants)
        self.assertIn("check-address", constants)
        self.assertTrue(any("preview-contour" in value for value in constants))
        self.assertFalse(any("generated_at" in value for value in constants))

    def test_legacy_modes_are_untouched_in_the_parser(self) -> None:
        # 398-wave3: converted from source-text pins (was L503-L510) — every
        # legacy renderer mode is probed through the real CLI: a REGISTERED
        # mode fails with a missing-argument error (exit 2, "required"), not
        # with argparse's "invalid choice", which proves the mode is
        # dispatched by the live parser.
        for legacy in (
            "ubuntu-relay", "verify-reader-auth", "ubuntu-sanitize-auth",
            "ubuntu-remediate-reader", "ubuntu-transcode-reader",
            "verify-vps-switch", "vps-switch", "vps-set-hls-address", "vps-cleanup",
        ):
            with self.subTest(mode=legacy):
                result = subprocess.run(
                    [sys.executable, str(RENDERER), legacy],
                    text=True, capture_output=True,
                )
                self.assertEqual(result.returncode, 2, legacy)
                self.assertIn("required", result.stderr, legacy)
                self.assertNotIn("invalid choice", result.stderr, legacy)

    def test_preview_scope_token_is_preview_prefixed(self) -> None:
        self.assertEqual(mediamtx.reader_scope_token(1), "single-rfc1918-ip")
        self.assertEqual(mediamtx.reader_scope_token(3), "multi-rfc1918-ip-count-3")


class PreviewRelayExecutedTests(unittest.TestCase):
    """Executed twins for the preview shell contract (#398 wave 3).

    The REAL camera-preview-relay.sh bytes run (a) bare for the standalone
    status subcommand and the non-root renderer gate, and (b) under an
    unprivileged user namespace for the root-gated prepare flow with the
    real canonical renderer. Copy-tree runs relocate the script so the
    renderer-missing gate executes against a repository root that truly
    lacks the renderer.
    """

    def _inventory_payload(self, cameras: list[dict[str, str]] | None = None) -> str:
        return build_inventory(cameras if cameras is not None else STANDARD_CAMERAS)

    def _plant_inventory(self, tmp: Path, payload: str, mode: int = 0o600) -> Path:
        # The inventory must be root-owned when the shell runs inside the
        # user namespace; files created inside the namespace are owned by
        # the mapped root, so a tiny writer script is executed under the
        # same namespace before the shell run.
        writer = tmp / "make_inventory.sh"
        writer.write_text(
            "#!/usr/bin/env bash\n"
            "cat > \"$1\" <<'EOF_INVENTORY'\n"
            f"{payload}\n"
            "EOF_INVENTORY\n"
            f"chmod {oct(mode)[2:]} \"$1\"\n",
            encoding="utf-8",
        )
        inventory = tmp / "inventory.json"
        relay_shell.run_shell(writer, [str(inventory)], tmp, use_unshare=True, with_stubs=False)
        return inventory

    def _prepare_argv(self, tmp: Path, inventory: Path, *, address: str = PRIVATE_ADDRESS, reader_ips: tuple[str, ...] = (READER_IP_A, READER_IP_B)) -> list[str]:
        return [
            "prepare",
            "--inventory", str(inventory),
            "--private-rtsp-address", address,
            *sum((["--reader-ip", ip] for ip in reader_ips), []),
            "--state-root", str(tmp / "state"),
        ]

    def _candidates(self, tmp: Path) -> tuple[Path, Path, Path]:
        candidates = tmp / "state" / "candidates"
        return (
            candidates / "mediamtx.yml",
            candidates / "sea-speed-camera-preview-relay.service",
            candidates / "camera-preview-catalog.json",
        )

    def _copy_tree(self, tmp: Path) -> Path:
        """Relocate the script so repo_root resolves into an empty tree."""
        target = tmp / "isolated" / "deploy" / "worker" / "ubuntu"
        target.mkdir(parents=True)
        copied = target / PREVIEW_SHELL.name
        copied.write_text(PREVIEW_SHELL.read_text(encoding="utf-8"), encoding="utf-8")
        return copied

    def test_status_is_standalone_without_renderer(self) -> None:
        # Executed twin of the #452 F2 ordering contract: bare status runs
        # WITHOUT the renderer present (copy tree has no renderer file) and
        # reports NOT_CHECKED for the private probe.
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            copied = self._copy_tree(tmp)
            result = relay_shell.run_shell(copied, ["status"], tmp, use_unshare=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PRIVATE_PREVIEW_RELAY_TCP=NOT_CHECKED", result.stdout)
            self.assertIn("SECRETS_DISPLAYED=NO", result.stdout)

    def test_status_tcp_probe_without_renderer_refuses(self) -> None:
        # Executed twin of the conditional gate inside the status branch:
        # with --private-rtsp-address the probe resolves through the
        # renderer's check-address, so a missing renderer exits 4.
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            copied = self._copy_tree(tmp)
            result = relay_shell.run_shell(
                copied, ["status", "--private-rtsp-address", PRIVATE_ADDRESS], tmp, use_unshare=False
            )
            self.assertEqual(result.returncode, 4, result.stdout)
            self.assertIn("ERROR renderer missing from exact repository source", result.stderr)

    def test_prepare_without_renderer_refuses_before_root_check(self) -> None:
        # Executed twin of the gate-before-root ordering: running as non-root
        # with NO renderer, the renderer gate (exit 4) fires before
        # require_root (exit 1) could.
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            copied = self._copy_tree(tmp)
            result = relay_shell.run_shell(
                copied, ["prepare", "--inventory", str(tmp / "missing.json")], tmp, use_unshare=False
            )
            self.assertEqual(result.returncode, 4, result.stdout)
            self.assertIn("ERROR renderer missing from exact repository source", result.stderr)

    def test_prepare_with_renderer_refuses_as_non_root(self) -> None:
        # Executed twin: with the renderer present, the gate passes and the
        # root requirement fires (exit 1) for the bare (non-namespace) run.
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            result = relay_shell.run_shell(
                relay_shell.PREVIEW_RELAY,
                ["prepare", "--inventory", str(tmp / "missing.json"), "--state-root", str(tmp / "state")],
                tmp,
                use_unshare=False,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("ERROR run this command as root", result.stderr)

    def test_prepare_renders_canonical_candidates_with_parity(self) -> None:
        # Executed twin of the #442 closure contract: the shell's prepare
        # flow renders through the canonical renderer, and the shell-produced
        # config and catalog are BYTE-IDENTICAL to a direct renderer
        # invocation with the same inputs. The accumulated reader-ip
        # occurrences reach the renderer (multi-peer scope evidence), the
        # unit is generated and all three candidates land 0600.
        relay_shell.skip_without_user_namespace(self)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            inventory = self._plant_inventory(tmp, self._inventory_payload())
            result = relay_shell.run_shell(
                relay_shell.PREVIEW_RELAY, self._prepare_argv(tmp, inventory), tmp
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PREPARED_PREVIEW_RELAY=YES", result.stdout)
            self.assertIn("CAMERA_COUNT=2", result.stdout)
            self.assertIn("READER_AUTH_SCOPE=preview-multi-rfc1918-peer-count-2", result.stdout)
            self.assertIn("MUTATIONS=PROTECTED_CANDIDATES_ONLY", result.stdout)
            self.assertIn("SERVICE_RESTARTED=NO", result.stdout)
            self.assertIn("SECRETS_DISPLAYED=NO", result.stdout)
            # 398-wave3 review MED-1: the retired `CONFIG_SHA256=%s` /
            # `UNIT_SHA256=%s` / `SANITIZED_CATALOG_SHA256=%s` printf pins
            # have an executed twin — the real flow emits all three digests
            # and each matches the sha256 of the corresponding candidate
            # bytes (evidence truthfulness, not just presence).
            config, unit, catalog = self._candidates(tmp)
            for prefix, path in (
                ("CONFIG_SHA256=", config),
                ("UNIT_SHA256=", unit),
                ("SANITIZED_CATALOG_SHA256=", catalog),
            ):
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertIn(f"{prefix}{digest}", result.stdout)
            self.assertTrue(config.exists() and unit.exists() and catalog.exists())
            for path in (config, unit, catalog):
                self.assertEqual(path.stat().st_mode & 0o777, 0o600, path.name)
            self.assertIn("User=mediamtx\n", unit.read_text(encoding="utf-8"))

            # Direct renderer invocation with the same inputs (outside the
            # namespace) must reproduce the shell-rendered bytes exactly.
            direct = tmp / "direct"
            direct.mkdir()
            direct_inventory = direct / "inventory.json"
            direct_inventory.write_text(self._inventory_payload(), encoding="utf-8")
            direct_inventory.chmod(0o600)
            rendered = subprocess.run(
                [
                    sys.executable, str(RENDERER), "ubuntu-preview-relay",
                    "--inventory", str(direct_inventory),
                    "--config-output", str(direct / "config.yml"),
                    "--catalog-output", str(direct / "catalog.json"),
                    "--private-rtsp-address", PRIVATE_ADDRESS,
                    "--reader-ip", READER_IP_A,
                    "--reader-ip", READER_IP_B,
                ],
                text=True, capture_output=True,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertEqual(
                config.read_text(encoding="utf-8"),
                (direct / "config.yml").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                catalog.read_text(encoding="utf-8"),
                (direct / "catalog.json").read_text(encoding="utf-8"),
            )

    def test_prepare_rejects_invalid_private_address_before_rendering(self) -> None:
        # Executed twin of the check-address single-sourcing: an address the
        # renderer rejects fails the transaction closed (exit 3) with no
        # candidates rendered.
        relay_shell.skip_without_user_namespace(self)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            inventory = self._plant_inventory(tmp, self._inventory_payload())
            result = relay_shell.run_shell(
                relay_shell.PREVIEW_RELAY,
                self._prepare_argv(tmp, inventory, address="10.0.0.8"),
                tmp,
            )
            self.assertEqual(result.returncode, 3, result.stdout)
            self.assertIn("private RTSP address must be private IPv4:PORT", result.stderr)
            config, unit, catalog = self._candidates(tmp)
            self.assertFalse(config.exists() and unit.exists() and catalog.exists())

    def test_prepare_single_reader_ip_emits_single_peer_scope(self) -> None:
        # 398-wave3 review LOW-6: the single-peer scope token executes through
        # the REAL shell prepare flow (one accumulated --reader-ip reaches the
        # renderer and the emitted scope evidence drops to the single-peer
        # token) — the scope-emission contract no longer rests on the
        # renderer-level tests alone.
        relay_shell.skip_without_user_namespace(self)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            inventory = self._plant_inventory(tmp, self._inventory_payload())
            result = relay_shell.run_shell(
                relay_shell.PREVIEW_RELAY,
                self._prepare_argv(tmp, inventory, reader_ips=(READER_IP_A,)),
                tmp,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PREPARED_PREVIEW_RELAY=YES", result.stdout)
            self.assertIn("CAMERA_COUNT=2", result.stdout)
            self.assertIn("READER_AUTH_SCOPE=preview-single-rfc1918-peer", result.stdout)

    def test_inventory_gates_reject_fail_closed(self) -> None:
        # Executed twins of the protected-inventory contract: a group/other
        # readable inventory and a symlinked inventory both exit 5 with no
        # candidates rendered.
        relay_shell.skip_without_user_namespace(self)
        for mode, plant in ((0o644, False), (0o600, True)):
            with self.subTest(mode=oct(mode), symlink=plant):
                with tempfile.TemporaryDirectory() as raw:
                    tmp = Path(raw)
                    inventory = self._plant_inventory(tmp, self._inventory_payload(), mode=mode)
                    if plant:
                        real = tmp / "real-inventory.json"
                        real.write_text(self._inventory_payload(), encoding="utf-8")
                        inventory.unlink()
                        inventory.symlink_to(real)
                    result = relay_shell.run_shell(
                        relay_shell.PREVIEW_RELAY, self._prepare_argv(tmp, inventory), tmp
                    )
                    self.assertEqual(result.returncode, 5, result.stdout)
                    self.assertIn("ERROR inventory", result.stderr)
                    config, unit, catalog = self._candidates(tmp)
                    self.assertFalse(config.exists() and unit.exists() and catalog.exists())

    def test_inventory_root_ownership_gate_rejects_non_root_uid(self) -> None:
        # 398-wave3 review MED-3 — camera-preview-relay.sh:207 (rc 5 on a
        # non-root-owned inventory). Choice record: the reject branch cannot
        # plant a real non-root-owned file inside the sandbox namespace —
        # `unshare --user --map-root-user` maps a single uid (newuidmap/
        # subuid are unavailable, so richer mappings are impossible) and
        # every file the test can create is owned by the mapped root, while
        # protected_hardlinks blocks linking a root-owned 0600 file. So the
        # strongest achievable twin executes the REAL gate line extracted
        # verbatim from the script (a drifted gate string fails extraction)
        # with `stat` stubbed to report both outcomes: uid 0 passes, any
        # non-zero uid exits 5 with the exact error. The passing direction
        # against a real root-owned inventory is executed by the flow twins
        # above (the planted inventory is root-owned inside the namespace).
        source = PREVIEW_SHELL.read_text(encoding="utf-8")
        gate_lines = [
            line.strip()
            for line in source.splitlines()
            if "stat -c '%u' \"$inventory\"" in line
        ]
        self.assertEqual(len(gate_lines), 1, "root-ownership inventory gate drifted")
        gate = gate_lines[0]
        with tempfile.TemporaryDirectory() as raw:
            inventory = Path(raw) / "inventory.json"
            inventory.write_text("{}", encoding="utf-8")
            harness = (
                f"stat() {{ printf '%s\\n' \"$FAKE_UID\"; }}\n"
                f"inventory={json.dumps(str(inventory))}\n"
                f"{gate}\n"
                "echo GATE_PASSED\n"
            )
            passed = subprocess.run(
                ["bash", "-c", harness], text=True, capture_output=True, env=dict(os.environ, FAKE_UID="0")
            )
            self.assertEqual(passed.returncode, 0, passed.stderr)
            self.assertIn("GATE_PASSED", passed.stdout)
            rejected = subprocess.run(
                ["bash", "-c", harness], text=True, capture_output=True, env=dict(os.environ, FAKE_UID="65534")
            )
            self.assertEqual(rejected.returncode, 5, rejected.stdout)
            self.assertIn("ERROR inventory must be root-owned", rejected.stderr)

    def test_status_tcp_probe_passes_against_real_listener(self) -> None:
        # Executed twin replacing the `check-address appears in both shells`
        # text pin (was CheckAddressCliTests.test_both_relay_shells, L484):
        # BOTH relay shells execute the renderer-backed check-address path
        # for real — a bound private listener reports PASS through the exact
        # status plumbing.
        listener = relay_shell.bindable_private_listener()
        if listener is None:
            self.skipTest("no bindable RFC1918 address for a deterministic listener probe")
        address, sock = listener
        try:
            with tempfile.TemporaryDirectory() as raw:
                tmp = Path(raw)
                preview = relay_shell.run_shell(
                    relay_shell.PREVIEW_RELAY,
                    ["status", "--private-rtsp-address", address],
                    tmp,
                    use_unshare=False,
                )
                self.assertEqual(preview.returncode, 0, preview.stderr)
                self.assertIn("PRIVATE_PREVIEW_RELAY_TCP=PASS", preview.stdout)
                cam1 = relay_shell.run_shell(
                    relay_shell.CAMERA_RELAY,
                    ["status", "--private-rtsp-address", address],
                    tmp,
                    use_unshare=False,
                )
                self.assertEqual(cam1.returncode, 0, cam1.stderr)
                self.assertIn("PRIVATE_RELAY_TCP=PASS", cam1.stdout)
        finally:
            sock.close()


class PreviewShellContractTests(unittest.TestCase):
    def test_shell_is_valid_and_renders_through_the_canonical_module(self) -> None:
        subprocess.run(["bash", "-n", str(PREVIEW_SHELL)], check=True)
        # 398-wave3: converted from source-text pins (was L518-L529) — the
        # `ubuntu-preview-relay \` and --config-output/--catalog-output/
        # --inventory wiring pins and the inline-heredoc bans are retired:
        # PreviewRelayExecutedTests.test_prepare_renders_canonical_candidates_
        # with_parity executes the real shell flow and byte-compares the
        # candidates against a direct renderer invocation, which proves the
        # shell renders through the canonical module (an inline heredoc
        # renderer could not reproduce those bytes).
        shell = PREVIEW_SHELL.read_text(encoding="utf-8")
        self.assertIn('ubuntu-preview-relay', shell)
        self.assertIn("--config-output \"$candidate_config\"", shell)
        self.assertIn("--catalog-output \"$candidate_catalog\"", shell)
        self.assertIn("--inventory \"$inventory\"", shell)

    def test_shell_resolves_the_renderer_from_the_repository_source(self) -> None:
        # 398-wave3: converted from source-text pins (was L531-L535) — the
        # repo_root resolution and the missing-renderer error string are
        # exercised by executed copy-tree twins:
        # PreviewRelayExecutedTests.test_prepare_without_renderer_refuses_
        # before_root_check and .test_status_tcp_probe_without_renderer_
        # refuses both run the REAL script from a relocated tree whose repo
        # root lacks the renderer and observe the exact gate behavior.
        subprocess.run(["bash", "-n", str(PREVIEW_SHELL)], check=True)

    def test_shell_status_is_standalone_and_renderer_gate_follows_it(self) -> None:
        # 398-wave3: converted from source-text pins (was L537-L554) — the
        # standalone-status / gate-after-status / gate-before-root ordering
        # is exercised by three executed twins:
        # test_status_is_standalone_without_renderer (status runs bare, no
        # renderer), test_status_tcp_probe_without_renderer_refuses (the
        # conditional probe gate fires inside status), and
        # test_prepare_without_renderer_refuses_before_root_check (exit 4
        # observed as non-root, so the gate precedes require_root).
        subprocess.run(["bash", "-n", str(PREVIEW_SHELL)], check=True)

    def test_shell_multi_reader_ip_parse_and_forwarding(self) -> None:
        # 398-wave3: converted from source-text pins (was L556-L569) — the
        # reader-ip accumulation loop text and the forwarding count are
        # retired: test_prepare_renders_canonical_candidates_with_parity
        # forwards TWO accumulated occurrences into the real renderer and
        # observes the multi-peer scope evidence, and the check-address
        # ordering is exercised by the invalid-address twin (exit 3 before
        # any candidate is rendered).
        subprocess.run(["bash", "-n", str(PREVIEW_SHELL)], check=True)

    def test_shell_keeps_protected_inventory_gate_and_evidence_contract(self) -> None:
        # 398-wave3: converted from source-text pins — the inventory gates
        # (regular non-symlink, mode 600, root-owned) and the prepare
        # evidence markers (PREPARED_PREVIEW_RELAY, CAMERA_COUNT, sha256
        # triple, MUTATIONS, SERVICE_RESTARTED, SECRETS_DISPLAYED) execute
        # for real in PreviewRelayExecutedTests. Kept as SP pins: the
        # activate-only evidence literals (the preview activate flow needs
        # real id/getent users and is not executed in-sandbox) and the
        # #452 R8 ban (preview activate must not gain the derivation).
        shell = PREVIEW_SHELL.read_text(encoding="utf-8")
        self.assertIn("CAM1_RELAY_CHANGED=NO", shell)
        self.assertIn("AI_WORKER_CHANGED=NO", shell)
        self.assertIn("AUTOMATIC_ROLLBACK=NO", shell)
        self.assertNotIn("derive_relay_service_identity", shell)

    def test_shell_emits_preview_reader_scope_evidence(self) -> None:
        # 398-wave3: converted from source-text pins (was L586-L590) — the
        # scope-emission printf literals are retired: the executed parity
        # twin observes READER_AUTH_SCOPE=preview-multi-rfc1918-peer-count-2
        # from the real flow, and (398-wave3 review LOW-6)
        # test_prepare_single_reader_ip_emits_single_peer_scope executes the
        # single-peer token through the same real flow with one reader IP.
        subprocess.run(["bash", "-n", str(PREVIEW_SHELL)], check=True)

    def test_cam1_relay_shell_validators_move_to_check_address(self) -> None:
        # 398-wave3: converted from source-text pins (was L592-L599) — the
        # check-address invocation pins and the inline-heredoc ban are
        # retired: cam1's reader-ip validation executes through the renderer
        # in the bad-IP forwarding twins (test_mediamtx_multi_reader_ip), and
        # BOTH shells execute the renderer-backed private-rtsp probe through
        # the real status plumbing in
        # PreviewRelayExecutedTests.test_status_tcp_probe_passes_against_
        # real_listener.
        subprocess.run(["bash", "-n", str(CAM1_SHELL)], check=True)


if __name__ == "__main__":
    unittest.main()
