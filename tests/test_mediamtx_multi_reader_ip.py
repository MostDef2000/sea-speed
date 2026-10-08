"""Issue #372: repeatable/comma-separated --reader-ip for the canonical renderer.

The live Ubuntu worker cam1 reader rule legitimately carries TWO VPS reader
IPs (10.123.239.101, 10.123.239.102). The renderer core
(`ensure_internal_reader_rule` / `_reader_rule_lines` /
`verify_internal_reader_rule`) already accepts `str | list[str]`; these tests
pin the CLI/shell gap closure, the stable input-order rendering, the
fail-closed exact-block mismatch semantics, and the unchanged subset verify.
"""

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

spec = importlib.util.spec_from_file_location("mediamtx_path_config", RENDERER)
assert spec and spec.loader
mediamtx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mediamtx)

IP_A = "10.123.239.101"
IP_B = "10.123.239.102"
IP_C = "10.123.239.103"

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
"""

SINGLE_IP_BLOCK = (
    "  # Sea Speed least-privilege reader for canonical cam1\n"
    "  - user: any\n"
    "    pass:\n"
    '    ips: ["10.123.239.101"]\n'
    "    permissions:\n"
)


class MultiReaderIpRendererTests(unittest.TestCase):
    def test_two_ip_render_includes_both_ips_in_input_order(self) -> None:
        rendered = mediamtx.ensure_internal_reader_rule(BASE_CONFIG, "cam1", [IP_A, IP_B])
        self.assertIn(f'ips: ["{IP_A}", "{IP_B}"]', rendered)
        self.assertNotIn(IP_C, rendered)
        mediamtx.verify_internal_reader_rule(rendered, "cam1", [IP_A, IP_B])
        # Idempotent re-apply with the same two-IP list.
        self.assertEqual(
            mediamtx.ensure_internal_reader_rule(rendered, "cam1", [IP_A, IP_B]),
            rendered,
        )

    def test_render_order_follows_input_order_stably(self) -> None:
        first = mediamtx.ensure_internal_reader_rule(BASE_CONFIG, "cam1", [IP_A, IP_B])
        again = mediamtx.ensure_internal_reader_rule(BASE_CONFIG, "cam1", [IP_A, IP_B])
        self.assertEqual(first, again)
        flipped = mediamtx.ensure_internal_reader_rule(BASE_CONFIG, "cam1", [IP_B, IP_A])
        self.assertIn(f'ips: ["{IP_B}", "{IP_A}"]', flipped)
        self.assertNotEqual(flipped, first)

    def test_single_ip_is_byte_identical_to_historical_str_behavior(self) -> None:
        str_rendered = mediamtx.ensure_internal_reader_rule(BASE_CONFIG, "cam1", IP_A)
        list_rendered = mediamtx.ensure_internal_reader_rule(BASE_CONFIG, "cam1", [IP_A])
        self.assertEqual(list_rendered, str_rendered)
        # Comma separation is a CLI-boundary concern (_reader_ip_list), not a
        # core-API change: the core str|list API behaves exactly as before.
        self.assertEqual(mediamtx._reader_ip_list(IP_A), [IP_A])
        self.assertEqual(mediamtx._reader_ip_list(IP_A + ","), [IP_A])
        self.assertIn(SINGLE_IP_BLOCK, str_rendered)
        self.assertEqual(mediamtx.reader_scope_token(1), "single-rfc1918-ip")
        self.assertEqual(mediamtx.reader_scope_token(2), "multi-rfc1918-ip-count-2")
        self.assertEqual(mediamtx.reader_scope_token(3), "multi-rfc1918-ip-count-3")

    def test_mismatch_reader_ip_list_is_rejected_fail_closed(self) -> None:
        rendered = mediamtx.ensure_internal_reader_rule(BASE_CONFIG, "cam1", [IP_A, IP_B])
        for other in ([IP_A, IP_C], [IP_A], [IP_B, IP_A], [IP_A, IP_B, IP_C]):
            with self.subTest(other=other), self.assertRaises(mediamtx.ConfigError):
                mediamtx.ensure_internal_reader_rule(rendered, "cam1", other)

    def test_verify_subset_semantics_on_two_ip_live_rule(self) -> None:
        rendered = mediamtx.ensure_internal_reader_rule(BASE_CONFIG, "cam1", [IP_A, IP_B])
        mediamtx.verify_internal_reader_rule(rendered, "cam1", IP_A)
        mediamtx.verify_internal_reader_rule(rendered, "cam1", [IP_B])
        mediamtx.verify_internal_reader_rule(rendered, "cam1", [IP_A, IP_B])
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.verify_internal_reader_rule(rendered, "cam1", IP_C)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.verify_internal_reader_rule(rendered, "cam1", [IP_A, IP_C])

    def test_duplicate_reader_ips_fail_closed(self) -> None:
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx._reader_ip_list([IP_A, IP_A])
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx._reader_ip_list(f"{IP_A}, {IP_A}")
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx._reader_ip_list([])


class MultiReaderIpCliTests(unittest.TestCase):
    def run_renderer(self, config_text: str, reader_ip_args: list[str]) -> tuple[subprocess.CompletedProcess[str], str | None]:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "mediamtx.yml"
            env_file = root / "worker.env"
            candidate = root / "candidate.yml"
            config.write_text(config_text, encoding="utf-8")
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
                    *reader_ip_args,
                    "--path",
                    "cam1",
                    "--output",
                    str(candidate),
                ],
                text=True,
                capture_output=True,
            )
            rendered = candidate.read_text(encoding="utf-8") if candidate.exists() else None
            return result, rendered

    def test_cli_repeatable_flags_render_both_ips(self) -> None:
        result, rendered = self.run_renderer(BASE_CONFIG, ["--reader-ip", IP_A, "--reader-ip", IP_B])
        self.assertEqual(result.returncode, 0, result.stderr)
        assert rendered is not None
        self.assertIn(f'ips: ["{IP_A}", "{IP_B}"]', rendered)
        self.assertIn("reader_scope=multi-rfc1918-ip-count-2", result.stdout)
        mediamtx.verify_internal_reader_rule(rendered, "cam1", [IP_A, IP_B])

    def test_cli_comma_separated_value_renders_both_ips(self) -> None:
        result, rendered = self.run_renderer(BASE_CONFIG, ["--reader-ip", f"{IP_A},{IP_B}"])
        self.assertEqual(result.returncode, 0, result.stderr)
        assert rendered is not None
        self.assertIn(f'ips: ["{IP_A}", "{IP_B}"]', rendered)
        self.assertIn("reader_scope=multi-rfc1918-ip-count-2", result.stdout)

    def test_cli_single_flag_matches_historical_output(self) -> None:
        result, rendered = self.run_renderer(BASE_CONFIG, ["--reader-ip", IP_A])
        self.assertEqual(result.returncode, 0, result.stderr)
        assert rendered is not None
        self.assertIn("reader_scope=single-rfc1918-ip", result.stdout)
        self.assertIn(SINGLE_IP_BLOCK, rendered)
        # Re-apply with the historical str API stays byte-identical.
        self.assertEqual(mediamtx.ensure_internal_reader_rule(rendered, "cam1", IP_A), rendered)

    def test_cli_verify_reader_auth_accepts_repeatable_and_comma_ips(self) -> None:
        _, rendered = self.run_renderer(BASE_CONFIG, ["--reader-ip", IP_A, "--reader-ip", IP_B])
        assert rendered is not None
        with tempfile.TemporaryDirectory() as raw:
            config = Path(raw) / "mediamtx.yml"
            config.write_text(rendered, encoding="utf-8")
            for args in (["--reader-ip", IP_A], ["--reader-ip", f"{IP_A},{IP_B}"], ["--reader-ip", IP_B, "--reader-ip", IP_A]):
                result = subprocess.run(
                    [sys.executable, str(RENDERER), "verify-reader-auth", "--config", str(config), *args, "--path", "cam1"],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            subset = subprocess.run(
                [sys.executable, str(RENDERER), "verify-reader-auth", "--config", str(config), "--reader-ip", IP_C, "--path", "cam1"],
                text=True,
                capture_output=True,
            )
            self.assertEqual(subset.returncode, 1)
            self.assertIn("not a subset", subset.stderr)

    def test_cli_mismatch_list_is_rejected_and_candidate_untouched(self) -> None:
        _, rendered = self.run_renderer(BASE_CONFIG, ["--reader-ip", IP_A, "--reader-ip", IP_B])
        assert rendered is not None
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "mediamtx.yml"
            env_file = root / "worker.env"
            candidate = root / "candidate.yml"
            config.write_text(rendered, encoding="utf-8")
            env_file.write_text("HLS_URL=rtsp://camera_user:camera_key@10.0.0.21/live\n", encoding="utf-8")
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
                    IP_A,
                    "--reader-ip",
                    IP_C,
                    "--path",
                    "cam1",
                    "--output",
                    str(candidate),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("does not match the requested rule", result.stderr)
            self.assertFalse(candidate.exists())


class CameraRelayForwardingTests(unittest.TestCase):
    """Structural pins (established style): the shell forwards every occurrence."""

    def test_shell_contracts_forward_all_reader_ip_occurrences(self) -> None:
        subprocess.run(["bash", "-n", str(UBUNTU)], check=True)
        ubuntu = UBUNTU.read_text(encoding="utf-8")
        self.assertIn("reader_ips=()", ubuntu)
        self.assertIn("IFS=',' read -r -a __reader_ip_parts", ubuntu)
        self.assertIn('reader_ips+=("$__reader_ip_part")', ubuntu)
        self.assertIn('reader_ip_args+=(--reader-ip "$reader_ip")', ubuntu)
        # Both the prepare render and the activate verify-reader-auth call
        # forward the accumulated occurrences.
        self.assertEqual(ubuntu.count('"${reader_ip_args[@]}"'), 2)
        self.assertIn("verify-reader-auth", ubuntu)
        # Per-IP RFC1918 validation loop precedes any renderer invocation.
        self.assertLess(ubuntu.index("validate_reader_ip \"$reader_ip\""), ubuntu.index("ubuntu-relay"))
        # Generalized deterministic scope evidence; the single-reader literal
        # is preserved so single-IP output stays byte-identical.
        self.assertIn("printf 'cam1-single-rfc1918-peer'", ubuntu)
        self.assertIn("cam1-multi-rfc1918-peer-count-", ubuntu)
        self.assertEqual(ubuntu.count("READER_AUTH_SCOPE=%s"), 2)


if __name__ == "__main__":
    unittest.main()
