from __future__ import annotations

import ast
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
TRANSCODE = ROOT / "deploy/worker/ubuntu/camera1-h264-transcode.sh"
DOC = ROOT / "docs/operations/CAMERA1_LIVE_REPLACEMENT.md"
sys.path.insert(0, str(ROOT / "tests"))

spec = importlib.util.spec_from_file_location("mediamtx_path_config", RENDERER)
assert spec and spec.loader
mediamtx = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mediamtx)

from support import relay_shell  # noqa: E402
from support import worker_source  # noqa: E402
from support import markdown_docs  # noqa: E402


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

        # 398-wave3: retired source-text pins and their executed twins (same
        # commit, this cluster):
        # - "--reader-ip" and the scope-evidence emission literals
        #   (cam1-single-rfc1918-peer / cam1-multi-rfc1918-peer-count-,
        #   READER_AUTH_SCOPE count) → the F1 executed activate flow observes
        #   READER_AUTH_SCOPE=cam1-single-rfc1918-peer and the F3 forwarding
        #   twins observe cam1-multi-rfc1918-peer-count-2 from the REAL shell.
        # - "AI worker must remain stopped" → the F1 rc-8 twin observes the
        #   real refusal line from the stubbed-but-real flow.
        # - "verify-reader-auth" presence → count==5 wiring pinned as SP in
        #   the remediate/sanitize batteries (same cross-flow discipline).
        # Kept as SP pins: the worker_service variable wiring (no executed
        # negative-space surface), MTX_AUTHMETHOD renderer env wiring, the
        # worker start/restart/enable bans and the rollback warning.
        self.assertIn('worker_service="sea-speed-worker.service"', ubuntu)
        self.assertIn("MTX_AUTHMETHOD=", ubuntu)
        self.assertNotIn('systemctl restart "$worker_service"', ubuntu)
        self.assertNotIn('systemctl start "$worker_service"', ubuntu)
        self.assertNotIn('systemctl enable "$worker_service"', ubuntu)
        self.assertIn("automatic rollback is not authorized", ubuntu)

        # 398-wave3: SP pins — the VPS shell is outside the executed surface
        # (no sandbox lane runs deploy/vps/**); its renderer-side contract is
        # executed above through the vps-switch / verify-vps-switch CLI twins.
        self.assertIn("--confirmed-public-hls", vps)
        self.assertIn("cam1-new", vps)
        self.assertIn("verify-vps-switch", vps)
        self.assertIn("RTSP_TRANSPORT=tcp", vps)
        self.assertIn("LOCAL_CANONICAL_HLS=PASS", vps)
        self.assertIn("automatic rollback is not authorized", vps)
        self.assertNotIn("worker.env", vps)

    def test_documentation_preserves_private_relay_and_records_auth_v1_boundary(self) -> None:
        # SS twins (issue #398 wave 6): each retired anywhere-in-file pin is
        # superseded by a section-scoped twin on the parsed runbook — the
        # Issue #115 supersession in the status preamble, the protected
        # browser path / retired-path ban / cam2 ban / worker-independence
        # contracts in the Product goal section, the single-reader rule in
        # the Security model section, the cutover activation boundary in
        # Repository components, the rollback-decision rule in the Rollback
        # boundary section, the relay prepare command shape and the exact
        # three-field canonical cam1 source block.
        source = DOC.read_text(encoding="utf-8")
        self.assertIsNotNone(markdown_docs.section_containing(source, "Issue #115", "superseded"))
        self.assertIsNotNone(
            markdown_docs.section_containing(source, "/sea-speed/media/cam1/index.m3u8", "Authentik-protected")
        )
        self.assertIsNotNone(
            markdown_docs.section_containing(
                source, "retired `/cams/hls/cam1/index.m3u8`", "must not be recreated"
            )
        )
        self.assertIsNotNone(
            markdown_docs.section_containing(
                source, "does not create `cam2`", "does not change the physical Camera 1 identity"
            )
        )
        self.assertIsNotNone(
            markdown_docs.section_containing(
                source, "independent of `sea-speed-worker.service`", "Stopping the AI worker must not stop"
            )
        )
        self.assertIsNotNone(
            markdown_docs.section_containing(source, "single VPS ZeroTier peer", "read")
        )
        prepare_section = markdown_docs.section_titled(source, "prepare ubuntu relay candidate")
        self.assertIsNotNone(prepare_section)
        prepare_blocks = [
            block
            for block in markdown_docs.fenced_blocks(prepare_section[1])
            if any("--reader-ip" in line for line in block)
        ]
        self.assertEqual(len(prepare_blocks), 1)
        prepare_command = prepare_blocks[0][0].strip()
        for flag in ("camera-relay.sh prepare", "--private-rtsp-address", "--reader-ip"):
            self.assertIn(flag, prepare_command, flag)
        source_blocks = [
            block
            for _, body in markdown_docs.sections(source)
            for block in markdown_docs.fenced_blocks(body)
            if len(block) == 3 and any(line.strip() == "rtspTransport: tcp" for line in block)
        ]
        self.assertEqual(len(source_blocks), 1)
        self.assertEqual(
            [line.strip() for line in source_blocks[0]],
            [
                "source: rtsp://<ubuntu-private-ip>:8554/cam1",
                "sourceOnDemand: yes",
                "rtspTransport: tcp",
            ],
        )
        retire_section = markdown_docs.section_titled(source, "retire", "cam1-new")
        self.assertIsNotNone(retire_section)
        # The retirement RULE lives in the section body (peer review F2 —
        # heading presence alone is not the contract): the gated cleanup flow
        # (prepare-cleanup → activate-cleanup, both gated on the confirmed
        # protected-HLS precondition via --confirmed-public-hls) and the
        # refuse-unless-canonical-bound guard that removes only `cam1-new`.
        # Same-or-stronger vs the retired anywhere-in-file
        # `assertIn("cam1-new", source)` pin.
        self.assertIn("camera-source-switch.sh prepare-cleanup", retire_section[1])
        self.assertIn("camera-source-switch.sh activate-cleanup", retire_section[1])
        self.assertIn("--confirmed-public-hls", retire_section[1])
        self.assertIn("refuses to proceed unless canonical `cam1`", retire_section[1])
        self.assertIn("removes only `cam1-new`", retire_section[1])
        self.assertIsNotNone(
            markdown_docs.section_containing(source, "sea-speed-auth-cutover.sh", "activation boundary")
        )
        self.assertIsNotNone(
            markdown_docs.section_containing(
                source, "explicit production rollback decision", "do not restore them automatically"
            )
        )
        # SP keep (issue #398 wave 6): the UNKNOWN runtime-state ban is a
        # negative contract — the stale placeholder must not appear anywhere
        # in the runbook.
        self.assertNotIn("runtime remains `UNKNOWN`", source)


class WaterRtspTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.transcode_text = (ROOT / "deploy/worker/ubuntu/camera1-h264-transcode.sh").read_text(encoding="utf-8")
        cls.entrypoint_text = (ROOT / "worker/ubuntu_worker_entrypoint.py").read_text(encoding="utf-8")

    def test_transcode_run_hides_credentials_and_configures_transport(self) -> None:
        # 398-wave3: converted from source-text pins — the real `run`
        # subcommand executes with a recording fake ffmpeg (TranscodeRunExecutedTests):
        # the ffconcat contract (0600, file-before-option, transport value),
        # the ffmpeg argv shape (-f concat, -protocol_whitelist) and the
        # credential-never-in-argv property are all observed from the REAL
        # script bytes. Kept as SP pin: the pre-run stale-input sweep
        # (`rm -f /tmp/camera1-h264-input.ffconcat.*`) — defensive hygiene
        # with no observable executed surface (exec replaces the process).
        subprocess.run(["bash", "-n", str(TRANSCODE)], check=True)
        self.assertIn("rm -f /tmp/camera1-h264-input.ffconcat.", self.transcode_text)

    def test_entrypoint_transport_knob_and_ffconcat_contract(self) -> None:
        # 398-wave3: converted from source-text pins — the entrypoint's
        # transport knob, ffconcat framing and no-secret-print property are
        # asserted on the parsed AST: the required string constants exist as
        # real constants, O_NOFOLLOW is referenced, and no `print` call
        # emits the credential-bearing input URL (the behavior twins below
        # additionally execute the helpers for real).
        # worker_source's curated path list does not include the entrypoint
        # module; parse it directly (same AST discipline, exact file bytes).
        entry_tree = ast.parse(
            (ROOT / "worker/ubuntu_worker_entrypoint.py").read_text(encoding="utf-8")
        )
        constants = set(worker_source.string_constants(entry_tree))
        for required in (
            "CAMERA1_RTSP_TRANSPORT", "-protocol_whitelist", "file,rtsp,tcp,udp,rtp",
            "-f", "concat",
        ):
            self.assertIn(required, constants, required)
        # Docstring-embedded / format-whitespace constants: substring semantics
        # (NEEDS_FILE is documented inside the ffconcat docstring; the framing
        # constants carry format whitespace).
        self.assertTrue(any("NEEDS_FILE" in value for value in constants))
        self.assertTrue(any("ffconcat version 1.0" in value for value in constants))
        self.assertTrue(any("option rtsp_transport" in value for value in constants))
        self.assertTrue(worker_source.references_name([entry_tree], "O_NOFOLLOW"))  # type: ignore[arg-type]
        for node in ast.walk(entry_tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
                self.assertFalse(
                    any(isinstance(arg, ast.Name) and arg.id == "input_url" for arg in node.args),
                    "the entrypoint must never print the credential-bearing input URL",
                )

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
        # 398-wave3 review MED-5: the udp DEFAULT is behavioral (a udp→tcp
        # default change must fail here) — asserted with the env var absent
        # AND with it set to an empty string (both fall back to udp for
        # credential-bearing inputs; the private relay stays tcp regardless).
        with mock.patch.dict(os.environ):
            os.environ.pop("CAMERA1_RTSP_TRANSPORT", None)
            self.assertEqual(entry._camera1_rtsp_transport(cred), "udp")
            self.assertEqual(entry._camera1_rtsp_transport(relay), "tcp")
        with mock.patch.dict(os.environ, {"CAMERA1_RTSP_TRANSPORT": ""}):
            self.assertEqual(entry._camera1_rtsp_transport(cred), "udp")

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


class TranscodeRunExecutedTests(unittest.TestCase):
    """Executed twins for the transcode `run` subcommand (#398 wave 3).

    The REAL camera1-h264-transcode.sh bytes execute the `run` flow (no root
    gate) with a recording fake ffmpeg on PATH; the ffconcat handoff file and
    the full ffmpeg argv are captured and asserted.
    """

    CREDENTIAL_URL = "rtsp://camera_user:camera_key@10.0.0.21:554/live"

    def _env_file(self, tmp: Path) -> Path:
        env_file = tmp / "worker.env"
        env_file.write_text("HLS_URL=" + self.CREDENTIAL_URL + "\n", encoding="utf-8")
        env_file.chmod(0o600)
        return env_file

    def _run(self, tmp: Path, transport: str | None = None, publish: str = "10.0.0.8") -> tuple[subprocess.CompletedProcess[str], list[list[str]], Path | None]:
        stubs = tmp / "stubs"
        stubs.mkdir(parents=True, exist_ok=True)
        ffmpeg = stubs / "ffmpeg"
        ffmpeg.write_text(
            "#!/usr/bin/env bash\n"
            '{ printf \'%s\\t\' "$@"; printf \'\\n\'; } >> "$FFMPEG_ARGV_LOG"\n',
            encoding="utf-8",
        )
        ffmpeg.chmod(0o755)
        env: dict[str, str] = {
            "FFMPEG_ARGV_LOG": str(tmp / "ffmpeg-argv.log"),
        }
        if transport is not None:
            env["CAMERA1_RTSP_TRANSPORT"] = transport
        result = relay_shell.run_shell(
            TRANSCODE,
            ["run", "--source-env-file", str(tmp / "worker.env"), "--publish-address", publish],
            tmp,
            env_extra=env,
            use_unshare=False,
        )
        argv_lines = [
            line.rstrip("\t").split("\t") for line in (tmp / "ffmpeg-argv.log").read_text(encoding="utf-8").splitlines()
        ] if (tmp / "ffmpeg-argv.log").exists() else []
        return result, argv_lines, tmp / "worker.env"

    def test_run_streams_ffconcat_input_and_hides_credentials_from_argv(self) -> None:
        # Executed twin of the #522 ffconcat contract: the credential-bearing
        # camera URL reaches ffmpeg ONLY through a 0600 ffconcat file (the
        # argv's -i target), the file directive precedes the transport option,
        # and the publish target ends the argv.
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            (tmp / "worker.env").write_text("HLS_URL=" + self.CREDENTIAL_URL + "\n", encoding="utf-8")
            (tmp / "worker.env").chmod(0o600)
            result, argv_lines, _ = self._run(tmp, transport="tcp")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("CAMERA1_CREDENTIALS_IN_ARGV=NO", result.stdout)
            self.assertIn("CAMERA1_RTSP_TRANSPORT=tcp", result.stdout)
            self.assertEqual(len(argv_lines), 1)
            argv = argv_lines[0]
            concat_idx = argv.index("-f")
            self.assertEqual(argv[concat_idx + 1], "concat")
            self.assertIn("-safe", argv)
            whitelist_idx = argv.index("-protocol_whitelist")
            self.assertEqual(argv[whitelist_idx + 1], "file,rtsp,tcp,udp,rtp")
            input_idx = argv.index("-i")
            ffconcat_path = Path(argv[input_idx + 1])
            self.assertEqual(ffconcat_path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn("camera_key", ffconcat_path.name)
            content = ffconcat_path.read_text(encoding="utf-8")
            self.assertIn("ffconcat version 1.0", content)
            self.assertIn(f"file '{self.CREDENTIAL_URL}'", content)
            self.assertIn("option rtsp_transport tcp", content)
            self.assertLess(
                content.index(f"file '{self.CREDENTIAL_URL}'"),
                content.index("option rtsp_transport tcp"),
                "concat `option` needs a preceding `file` directive (NEEDS_FILE)",
            )
            # The credential URL never appears anywhere in the ffmpeg argv;
            # the publish target ends the argv (after `-f rtsp`).
            for element in argv:
                self.assertNotIn("camera_key", element)
            self.assertEqual(argv[-1], "rtsp://10.0.0.8:8554/cam1-h264")
            self.assertEqual(argv[-2], "rtsp")

    def test_run_rejects_invalid_transport_fail_closed(self) -> None:
        # Executed twin of the transport vocabulary gate: an unsupported
        # CAMERA1_RTSP_TRANSPORT refuses the run (exit 6) before any ffmpeg
        # invocation.
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            (tmp / "worker.env").write_text("HLS_URL=" + self.CREDENTIAL_URL + "\n", encoding="utf-8")
            (tmp / "worker.env").chmod(0o600)
            result, argv_lines, _ = self._run(tmp, transport="bogus")
            self.assertEqual(result.returncode, 6, result.stdout)
            self.assertIn("CAMERA1_RTSP_TRANSPORT must be one of: udp, tcp, automatic", result.stderr)
            self.assertEqual(argv_lines, [])

    def test_run_rejects_bad_source_env_fail_closed(self) -> None:
        # Executed twins: a missing env file and a non-credential URL both
        # refuse the run closed (exit 6) — no ffmpeg, no ffconcat residue.
        for scenario in ("missing-file", "no-userinfo", "single-quote"):
            with self.subTest(scenario=scenario):
                with tempfile.TemporaryDirectory() as raw:
                    tmp = Path(raw)
                    env_file = tmp / "worker.env"
                    if scenario != "missing-file":
                        payload = {
                            "no-userinfo": "HLS_URL=rtsp://10.0.0.21/live\n",
                            "single-quote": "HLS_URL=rtsp://u:se'cret@10.0.0.21/live\n",
                        }[scenario]
                        env_file.write_text(payload, encoding="utf-8")
                        env_file.chmod(0o600)
                    result, argv_lines, _ = self._run(tmp)
                    self.assertEqual(result.returncode, 6, result.stdout)
                    self.assertEqual(argv_lines, [])


class UbuntuRelayApiBlockTests(unittest.TestCase):
    """#407: the ubuntu-relay profile durably carries the loopback watchdog API block."""

    def rendered_candidate(self, config_text: str) -> tuple[str, str]:
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
            self.assertIn("api=loopback-watchdog", result.stdout)
            return candidate.read_text(encoding="utf-8"), secret

    def test_ubuntu_relay_renders_loopback_api_block(self) -> None:
        rendered, _ = self.rendered_candidate(BASE_CONFIG)
        self.assertIn("api: yes\n", rendered)
        self.assertIn('apiAddress: "127.0.0.1:9997"\n', rendered)
        self.assertIn(
            "# Sea Speed loopback API observation rule for the freshness watchdog", rendered
        )
        self.assertIn('ips: ["127.0.0.1"]', rendered)
        self.assertIn("      - action: api\n", rendered)
        mediamtx.verify_internal_api_rule(rendered)
        mediamtx.verify_internal_reader_rule(rendered, "cam1", "10.0.0.9")

    def test_api_block_survives_re_render_idempotently(self) -> None:
        first, _ = self.rendered_candidate(BASE_CONFIG)
        self.assertEqual(
            mediamtx.set_top_level_scalar(first, "api", "yes", quote=False),
            first,
        )
        second, _ = self.rendered_candidate(first)
        self.assertEqual(second, first)
        source = mediamtx.get_path_field(second, "cam1", "source") or ""
        self.assertTrue(source.startswith("rtsp://"), source)
        self.assertTrue(source.endswith("@10.0.0.21/live"), source)
        mediamtx.verify_internal_api_rule(second)

    def test_api_rule_drift_is_rejected(self) -> None:
        # Baseline without a pre-existing (marker-less) api rule: the marked
        # rule is then the only api grant in its parse span, so drift of the
        # marked rule itself is what the assertions exercise.
        baseline = BASE_CONFIG.replace(
            '  - user: any\n    pass:\n    ips: ["127.0.0.1"]\n    permissions:\n      - action: api\n',
            "",
            1,
        )
        rendered, _ = self.rendered_candidate(baseline)
        self.assertEqual(
            mediamtx.ensure_internal_api_rule(rendered),
            rendered,
        )
        drifted = rendered.replace("- action: api\n", "- action: read\n", 1)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.ensure_internal_api_rule(drifted)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.verify_internal_api_rule(drifted)
        no_loopback = rendered.replace('ips: ["127.0.0.1"]', 'ips: ["203.0.113.8"]', 1)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.verify_internal_api_rule(no_loopback)
        external = rendered.replace("authMethod: internal", "authMethod: http", 1)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.ensure_internal_api_rule(external)

    def test_non_relay_modes_do_not_render_the_api_block(self) -> None:
        marker = "# Sea Speed loopback API observation rule for the freshness watchdog"
        reader_only = mediamtx.ensure_internal_reader_rule(BASE_CONFIG, "cam1", "10.0.0.9")
        self.assertNotIn("api: yes\n", reader_only)
        self.assertNotIn(marker, reader_only)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "mediamtx.yml"
            candidate = root / "candidate.yml"
            config.write_text(BASE_CONFIG, encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "vps-switch",
                    "--config",
                    str(config),
                    "--relay-url",
                    "rtsp://10.0.0.8:8554/cam1",
                    "--path",
                    "cam1",
                    "--output",
                    str(candidate),
                ],
                check=True,
                text=True,
                capture_output=True,
            )
            rendered = candidate.read_text(encoding="utf-8")
            self.assertNotIn("api: yes\n", rendered)
            self.assertNotIn(marker, rendered)


if __name__ == "__main__":
    unittest.main()