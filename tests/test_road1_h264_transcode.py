from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "scripts/operations/mediamtx_path_config.py"
TRANSCODE = ROOT / "deploy/worker/ubuntu/road1-h264-transcode.sh"
sys.path.insert(0, str(ROOT / "tests"))

spec = importlib.util.spec_from_file_location("mediamtx_path_config", RENDERER)
assert spec and spec.loader
mediamtx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mediamtx)

from support import relay_shell  # noqa: E402

# Live relay shape after the #637 road1 cutover: the box's own ZeroTier IP
# (10.123.239.102) reads road1 (the road analytics worker runs on the box),
# the VPS (10.123.239.101) pulls rtsp://10.123.239.102:8554/road1. The stored
# source here is a credential-free placeholder — the real relay config's
# road1 source is inventory-sourced and never appears in tests.
RELAY_READER_IP = "10.123.239.102"
VPS_READER_IP = "10.123.239.101"
RELAY_ADDRESS = "10.123.239.102:8554"

BASE_CONFIG = """logLevel: info
authMethod: internal
authInternalUsers:
  # Sea Speed least-privilege reader for canonical road1
  - user: any
    pass:
    ips: ["10.123.239.102"]
    permissions:
      - action: read
        path: road1
  - user: any
    pass:
    ips: ["127.0.0.1"]
    permissions:
      - action: api
api: yes
apiAddress: 127.0.0.1:9997
rtsp: yes
rtspAddress: :8554
paths:
  road1:
    source: rtsp://10.123.239.55:554/road1
    sourceOnDemand: yes
    rtspTransport: tcp
"""


def _ffmpeg_argv_recorder(tmp: Path) -> Path:
    """Plant the recording ffmpeg stub (the run flow execs whatever ffmpeg is
    on PATH; the sandbox has no real ffmpeg, and prepare/activate only need
    `command -v ffmpeg` to pass validate_common)."""
    stubs = tmp / "stubs"
    stubs.mkdir(parents=True, exist_ok=True)
    ffmpeg = stubs / "ffmpeg"
    ffmpeg.write_text(
        "#!/usr/bin/env bash\n"
        '{ printf \'%s\\t\' "$@"; printf \'\\n\'; } >> "$FFMPEG_ARGV_LOG"\n',
        encoding="utf-8",
    )
    ffmpeg.chmod(0o755)
    return stubs


def _argv_lines(tmp: Path) -> list[list[str]]:
    log = tmp / "ffmpeg-argv.log"
    if not log.exists():
        return []
    return [line.rstrip("\t").split("\t") for line in log.read_text(encoding="utf-8").splitlines()]


class Road1TranscodeRunExecutedTests(unittest.TestCase):
    """Executed twins for the road1 transcode `run` subcommand (issue #659).

    The REAL road1-h264-transcode.sh bytes execute the `run` flow (no root
    gate) with a recording fake ffmpeg on PATH; the full ffmpeg argv is
    captured and asserted, including the mandatory bitrate-cap triple and,
    since #675, the pinned 2 s GOP that makes the encoder tail identical to
    the cam1 transcode's.
    """

    def _run(self, tmp: Path, *args: str) -> subprocess.CompletedProcess[str]:
        _ffmpeg_argv_recorder(tmp)
        return relay_shell.run_shell(
            TRANSCODE,
            ["run", *args],
            tmp,
            env_extra={"FFMPEG_ARGV_LOG": str(tmp / "ffmpeg-argv.log")},
            use_unshare=False,
        )

    def test_run_publishes_capped_720p_from_the_relay_path(self) -> None:
        # Executed twin of the #659 run contract: the source URL is derived
        # from --private-rtsp-address as rtsp://<host>:<port>/road1 (the
        # credential-free relay path), -rtsp_transport tcp is an INPUT option
        # sitting immediately before -i, and the argv carries the exact
        # 720p15 encoding chain ending with the mandatory bitrate-cap triple
        # and the road1-720p publish target.
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            result = self._run(
                tmp,
                "--private-rtsp-address", RELAY_ADDRESS,
                "--publish-address", RELAY_READER_IP,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            argv_lines = _argv_lines(tmp)
            self.assertEqual(len(argv_lines), 1)
            argv = argv_lines[0]
            input_idx = argv.index("-i")
            # -rtsp_transport tcp is an INPUT option: immediately before -i.
            self.assertEqual(argv[input_idx - 2], "-rtsp_transport")
            self.assertEqual(argv[input_idx - 1], "tcp")
            self.assertEqual(argv[input_idx + 1], "rtsp://10.123.239.102:8554/road1")
            self.assertIn("-an", argv)
            self.assertEqual(argv[argv.index("-vf") + 1], "fps=15,scale=-2:720")
            self.assertEqual(argv[argv.index("-c:v") + 1], "libx264")
            self.assertEqual(argv[argv.index("-preset") + 1], "veryfast")
            self.assertEqual(argv[argv.index("-tune") + 1], "zerolatency")
            # The ordered bitrate-cap triple — the entire point of this script
            # (cam1's transcode lacks it): -b:v 1500k, then -maxrate 1600k,
            # then -bufsize 3200k.
            bitrate_idx = argv.index("-b:v")
            maxrate_idx = argv.index("-maxrate")
            bufsize_idx = argv.index("-bufsize")
            self.assertLess(bitrate_idx, maxrate_idx)
            self.assertLess(maxrate_idx, bufsize_idx)
            self.assertEqual(argv[bitrate_idx + 1], "1500k")
            self.assertEqual(argv[maxrate_idx + 1], "1600k")
            self.assertEqual(argv[bufsize_idx + 1], "3200k")
            # The pinned GOP (issue #675, cam1 #672 precedent): -g 30, then
            # -keyint_min 30 (2 s at fps=15 → ~2 s HLS segments instead of
            # the default keyint 250 / EXTINF 16.66667).
            gop_idx = argv.index("-g")
            keyint_idx = argv.index("-keyint_min")
            self.assertLess(gop_idx, keyint_idx)
            self.assertEqual(argv[gop_idx + 1], "30")
            self.assertEqual(argv[keyint_idx + 1], "30")
            # The publish target ends the argv (after `-f rtsp`).
            self.assertEqual(argv[-3:], ["-f", "rtsp", "rtsp://10.123.239.102:8554/road1-720p"])

    def test_run_without_publish_address_fails_closed(self) -> None:
        # Executed twin: run without --publish-address refuses (exit 2) before
        # any ffmpeg invocation.
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            result = self._run(tmp, "--private-rtsp-address", RELAY_ADDRESS)
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertIn("--publish-address", result.stderr)
            self.assertEqual(_argv_lines(tmp), [])


class Road1TranscodePrepareExecutedTests(unittest.TestCase):
    """Executed twins for the road1 transcode prepare/activate transaction.

    The REAL road1-h264-transcode.sh bytes run under an unprivileged user
    namespace with the real renderer (resolved in place through the script's
    own script_dir/../../.. walk), a stubbed systemctl and a stubbed ffmpeg:
    the renderer transaction, the 0600 digest-bound candidates and the
    fail-closed activate refusal all execute for real. A successful activate
    is deliberately NOT executed (it installs to the real /etc/systemd/system);
    only the digest-mismatch refusal path, which exits before any install.
    """

    def _prepare(self, tmp: Path) -> subprocess.CompletedProcess[str]:
        _ffmpeg_argv_recorder(tmp)
        config = tmp / "mediamtx.yml"
        config.write_text(BASE_CONFIG, encoding="utf-8")
        return relay_shell.run_shell(
            TRANSCODE,
            [
                "prepare",
                "--config", str(config),
                "--private-rtsp-address", RELAY_ADDRESS,
                "--reader-ip", VPS_READER_IP,
                "--state-root", str(tmp / "state"),
            ],
            tmp,
        )

    def test_prepare_renders_road1_720p_candidate_and_unit(self) -> None:
        # Executed twin of the prepare transaction: the real renderer adds the
        # road1-720p publisher path plus the combined read+publish rule on the
        # live relay config, both candidates land 0600 in the state root with
        # their digests emitted, and the unit clones the cam1 hardening shape
        # without any EnvironmentFile.
        relay_shell.skip_without_user_namespace(self)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            result = self._prepare(tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PREPARED_TRANSCODE_CANDIDATE=YES", result.stdout)
            self.assertIn("TRANSCODE_PATH=road1-720p", result.stdout)
            self.assertIn("MUTATIONS=PROTECTED_CANDIDATES_ONLY", result.stdout)
            self.assertIn("SERVICE_RESTARTED=NO", result.stdout)
            self.assertIn("SECRETS_DISPLAYED=NO", result.stdout)
            config_digest = self._digest(result.stdout, "CONFIG_SHA256")
            unit_digest = self._digest(result.stdout, "UNIT_SHA256")
            self.assertRegex(config_digest, r"^[0-9a-f]{64}$")
            self.assertRegex(unit_digest, r"^[0-9a-f]{64}$")

            candidate = tmp / "state" / "road1-720p-mediamtx.candidate.yml"
            unit = tmp / "state" / "sea-speed-road1-h264.service"
            self.assertTrue(candidate.exists())
            self.assertTrue(unit.exists())
            self.assertEqual(candidate.stat().st_mode & 0o777, 0o600)
            self.assertEqual(unit.stat().st_mode & 0o777, 0o600)

            parsed = yaml.safe_load(candidate.read_text(encoding="utf-8"))
            self.assertEqual(parsed["paths"]["road1-720p"]["source"], "publisher")
            self.assertIs(parsed["paths"]["road1-720p"]["sourceOnDemand"], False)
            rule_blocks = [
                block
                for block in parsed["authInternalUsers"]
                if isinstance(block, dict)
                and any(
                    isinstance(permission, dict)
                    and permission.get("action") == "read"
                    and permission.get("path") == "road1-720p"
                    for permission in block.get("permissions") or []
                )
            ]
            self.assertEqual(len(rule_blocks), 1)
            self.assertEqual(rule_blocks[0]["ips"], [VPS_READER_IP, RELAY_READER_IP])
            self.assertEqual(
                rule_blocks[0]["permissions"],
                [
                    {"action": "read", "path": "road1-720p"},
                    {"action": "publish", "path": "road1-720p"},
                ],
            )

            unit_text = unit.read_text(encoding="utf-8")
            self.assertIn("road1-h264-transcode.sh run", unit_text)
            self.assertIn("--publish-address", unit_text)
            self.assertNotIn("EnvironmentFile", unit_text)
            self.assertIn("ProtectSystem=strict", unit_text)
            self.assertIn("Restart=always", unit_text)

    @staticmethod
    def _digest(stdout: str, key: str) -> str:
        for line in stdout.splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
        raise AssertionError(f"{key} not found in prepare stdout")

    def test_activate_digest_mismatch_refuses_fail_closed(self) -> None:
        # Executed twin of the digest-bound activate gate: a wrong
        # --expected-config-sha256 refuses the activation (exit 7) before any
        # install — no unit in /etc/systemd/system, live config byte-identical,
        # no .next residue. A successful activate is deliberately never
        # executed in tests (it would install to the real /etc).
        relay_shell.skip_without_user_namespace(self)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            prepare = self._prepare(tmp)
            self.assertEqual(prepare.returncode, 0, prepare.stdout + prepare.stderr)
            config = tmp / "mediamtx.yml"
            config_before = config.read_bytes()
            result = relay_shell.run_shell(
                TRANSCODE,
                [
                    "activate",
                    "--config", str(config),
                    "--private-rtsp-address", RELAY_ADDRESS,
                    "--reader-ip", VPS_READER_IP,
                    "--expected-config-sha256", "0" * 64,
                    "--expected-unit-sha256", "0" * 64,
                    "--state-root", str(tmp / "state"),
                ],
                tmp,
            )
            self.assertEqual(result.returncode, 7, result.stdout + result.stderr)
            self.assertIn("digest mismatch", result.stderr)
            self.assertFalse(Path("/etc/systemd/system/sea-speed-road1-h264.service").exists())
            self.assertEqual(config.read_bytes(), config_before)
            self.assertFalse(config.with_name(config.name + ".next").exists())


class Road1TranscodeSourcePins(unittest.TestCase):
    """Source-scan pins: the bitrate cap and path literals exist in the real
    script bytes, and no credential-env/ffconcat machinery leaked in."""

    def test_script_is_valid_bash_and_pins_the_bitrate_cap(self) -> None:
        subprocess.run(["bash", "-n", str(TRANSCODE)], check=True)
        text = TRANSCODE.read_text(encoding="utf-8")
        for pin in (
            "-b:v 1500k",
            "-maxrate 1600k",
            "-bufsize 3200k",
            "road1-720p",
            "fps=15,scale=-2:720",
        ):
            self.assertIn(pin, text)
        self.assertNotIn("HLS_URL", text)
        self.assertNotIn("ffconcat", text)


class Road1TranscodeRendererCompatTests(unittest.TestCase):
    """Renderer-compat regression (mirror of
    test_ensure_cam1_reader_is_subset_safe_when_adding_cam1_h264): rendering
    the road1-720p transcode rule must preserve the existing road1, cam1 and
    cam1-h264 rules exactly."""

    def test_ensure_road1_720p_rule_preserves_existing_relay_rules(self) -> None:
        # Build the live-shaped config: road1 (from BASE_CONFIG) plus the cam1
        # and cam1-h264 rules, then render road1-720p through the real
        # renderer entry point.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            with_cam1 = mediamtx.ensure_internal_reader_rule(BASE_CONFIG, "cam1", "10.0.0.9")
            with_cam1_h264 = mediamtx.ensure_internal_reader_rule(
                with_cam1, "cam1-h264", "10.0.0.9", publisher_ips=["10.0.0.10"]
            )
            config = root / "mediamtx.yml"
            config.write_text(with_cam1_h264, encoding="utf-8")
            out = root / "candidate.yml"
            mediamtx.render_ubuntu_transcode_reader(
                argparse.Namespace(
                    config=config,
                    path="road1-720p",
                    reader_ip=VPS_READER_IP,
                    publisher_ip=RELAY_READER_IP,
                    output=out,
                )
            )
            text = out.read_text(encoding="utf-8")
            # Pre-existing rules are preserved exactly.
            mediamtx.verify_internal_reader_rule(text, "road1", reader_ip=RELAY_READER_IP)
            mediamtx.verify_internal_reader_rule(text, "cam1", reader_ip="10.0.0.9")
            mediamtx.verify_internal_reader_rule(
                text, "cam1-h264", reader_ip="10.0.0.9", publisher_ips=["10.0.0.10"]
            )
            # The new road1-720p rule carries the exact reader+publisher ips
            # with read+publish permissions, and the publisher path exists.
            mediamtx.verify_internal_reader_rule(
                text, "road1-720p", reader_ip=VPS_READER_IP, publisher_ips=[RELAY_READER_IP]
            )
            parsed = yaml.safe_load(text)
            rule_blocks = [
                block
                for block in parsed["authInternalUsers"]
                if isinstance(block, dict)
                and any(
                    isinstance(permission, dict)
                    and permission.get("action") == "read"
                    and permission.get("path") == "road1-720p"
                    for permission in block.get("permissions") or []
                )
            ]
            self.assertEqual(len(rule_blocks), 1)
            self.assertEqual(rule_blocks[0]["ips"], [VPS_READER_IP, RELAY_READER_IP])
            self.assertEqual(
                rule_blocks[0]["permissions"],
                [
                    {"action": "read", "path": "road1-720p"},
                    {"action": "publish", "path": "road1-720p"},
                ],
            )
            self.assertEqual(parsed["paths"]["road1-720p"]["source"], "publisher")
            self.assertIs(parsed["paths"]["road1-720p"]["sourceOnDemand"], False)
            # The full-res road1 path the AI worker consumes is untouched.
            self.assertIs(parsed["paths"]["road1"]["sourceOnDemand"], True)
            self.assertEqual(parsed["paths"]["road1"]["rtspTransport"], "tcp")


if __name__ == "__main__":
    unittest.main()
