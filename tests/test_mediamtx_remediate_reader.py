"""Issue #437: canonical drift-remediation path for drifted LIVE reader rules.

During the #372 operator verification (2026-10-09) the canonical tool REFUSED
a prepare-only re-render of a drifted cam1 reader rule (fail-closed against
widening via the `ensure_internal_reader_rule` byte-exact guard). The refusal
is right; the gap is process: no repo-owned path converges a DRIFTED live
reader rule back to canonical while PRESERVING the live rule's current
scopes. This battery pins the bounded remediate path:

- renderer core: `remediate_internal_reader_rule` locates the marker-anchored
  reader rule, reuses `_parse_rule_block` to extract the live ips/actions,
  re-authorizes every scope element through the existing validators
  (`validate_peer_reader_ip`/`validate_reader_ip` — the relay profile renders
  reader IPs as literal RFC1918 IPv4, so non-IPv4/loopback/public/duplicate
  ips fail closed), requires actions ⊆ {read, publish} with publish failing
  closed on the read-only cam1 relay profile, re-emits the canonical block
  via `_reader_rule_lines` preserving the live scopes, and re-verifies
  reader + API rules plus the byte-exact `ensure_internal_reader_rule`
  idempotency post-condition.
- renderer CLI: `ubuntu-remediate-reader` verifies the marked API rule
  (verify-before), remediates, and writes a 0600 candidate; failure leaves
  the candidate untouched; a conforming rule is a byte-identical no-op with
  `remediation_needed=NO` evidence.
- shell contract: `camera-relay.sh remediate` wires verify-before (reader
  rule on LIVE) -> remediate render -> digest + 0600 sha file -> verify-after
  (reader rule on CANDIDATE) and reuses the existing digest-bound activate
  flow unchanged.
"""

from __future__ import annotations

import importlib.util
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

API_MARKER = "# Sea Speed loopback API observation rule for the freshness watchdog"
READER_MARKER_CAM1 = "# Sea Speed least-privilege reader for canonical cam1"
READER_MARKER_CAM1_H264 = "# Sea Speed least-privilege reader for canonical cam1-h264"
IP_VPS = "10.123.239.101"
IP_VPS_SECOND = "10.123.239.102"

HEADER = """logLevel: info
authMethod: internal
authInternalUsers:
"""

MARKED_API_RULE = (
    f"  {API_MARKER}\n"
    "  - user: any\n"
    '    ips: ["127.0.0.1"]\n'
    "    permissions:\n"
    "      - action: api\n"
)

# The canonical read-only relay block exactly as _reader_rule_lines renders it.
CANONICAL_READER_RULE = (
    f"  {READER_MARKER_CAM1}\n"
    "  - user: any\n"
    "    pass:\n"
    f'    ips: ["{IP_VPS}"]\n'
    "    permissions:\n"
    "      - action: read\n"
    '        path: "cam1"\n'
)

# The #372 drift shape: same scope, hand-edited FORM (no `pass:` field,
# unquoted ips/path) — verify-reader-auth passes on it, ensure_internal_reader_rule
# refuses the byte-exact re-render; remediate must converge it.
DRIFTED_SINGLE_IP_RULE = (
    f"  {READER_MARKER_CAM1}\n"
    "  - user: any\n"
    f"    ips: [{IP_VPS}]\n"
    "    permissions:\n"
    "      - action: read\n"
    "        path: cam1\n"
)

# Two-IP drift: block-style ips in live order [second, first], no `pass:`.
DRIFTED_TWO_IP_RULE = (
    f"  {READER_MARKER_CAM1}\n"
    "  - user: any\n"
    "    ips:\n"
    f'      - "{IP_VPS_SECOND}"\n'
    f'      - "{IP_VPS}"\n'
    "    permissions:\n"
    "      - action: read\n"
    "        path: cam1\n"
)

MARKED_READER_H264_RULE = (
    f"  {READER_MARKER_CAM1_H264}\n"
    "  - user: any\n"
    "    pass:\n"
    f'    ips: ["{IP_VPS}", "{IP_VPS_SECOND}"]\n'
    "    permissions:\n"
    "      - action: read\n"
    '        path: "cam1-h264"\n'
    "      - action: publish\n"
    '        path: "cam1-h264"\n'
)

TAIL = """rtsp: yes
rtspAddress: :8554
api: yes
apiAddress: "127.0.0.1:9997"
paths:
  cam1:
    source: rtsp://10.0.0.8:8554/cam1
    sourceOnDemand: yes
    rtspTransport: tcp
  cam1-h264:
    source: publisher
    sourceOnDemand: no
"""

LIVE_CONFIG = HEADER + MARKED_API_RULE + CANONICAL_READER_RULE + MARKED_READER_H264_RULE + "\n" + TAIL


def live_with_reader_block(block: str) -> str:
    return HEADER + MARKED_API_RULE + block + MARKED_READER_H264_RULE + "\n" + TAIL


def canonical_reader_block(ips: list[str]) -> str:
    """The canonical block the renderer itself emits for the given scopes."""
    return "".join(mediamtx._reader_rule_lines("cam1", list(ips)))


class RemediateCoreTests(unittest.TestCase):
    """Renderer core: bounded drift convergence with fail-closed scope."""

    def test_remediate_converges_drifted_single_ip_rule(self) -> None:
        drifted = live_with_reader_block(DRIFTED_SINGLE_IP_RULE)
        remediated, ips, needed = mediamtx.remediate_internal_reader_rule(drifted, "cam1")
        self.assertTrue(needed)
        self.assertEqual(ips, [IP_VPS])
        self.assertEqual(
            remediated,
            HEADER + MARKED_API_RULE + CANONICAL_READER_RULE + MARKED_READER_H264_RULE + "\n" + TAIL,
        )
        # The canonical marked rules outside the remediated span survive
        # byte-identically (AC-2).
        self.assertIn(MARKED_API_RULE, remediated)
        self.assertIn(MARKED_READER_H264_RULE, remediated)
        # The canonical verify pair passes on the remediated config and the
        # byte-exact ensure guard accepts a re-render (ubuntu-relay parity).
        mediamtx.verify_internal_reader_rule(remediated, "cam1", IP_VPS)
        mediamtx.verify_internal_api_rule(remediated)
        self.assertEqual(
            mediamtx.ensure_internal_reader_rule(remediated, "cam1", IP_VPS),
            remediated,
        )

    def test_remediate_preserves_live_two_ip_scope_in_live_order(self) -> None:
        drifted = live_with_reader_block(DRIFTED_TWO_IP_RULE)
        remediated, ips, needed = mediamtx.remediate_internal_reader_rule(drifted, "cam1")
        self.assertTrue(needed)
        self.assertEqual(ips, [IP_VPS_SECOND, IP_VPS])
        # Byte-identity pin: the remediated block equals what the renderer
        # (ubuntu-relay -> _reader_rule_lines) emits for the same live scopes
        # in the live order.
        block_start = remediated.index(f"  {READER_MARKER_CAM1}\n")
        block_end = remediated.index(f"  {READER_MARKER_CAM1_H264}\n")
        self.assertEqual(
            remediated[block_start:block_end],
            canonical_reader_block([IP_VPS_SECOND, IP_VPS]),
        )
        mediamtx.verify_internal_reader_rule(remediated, "cam1", [IP_VPS_SECOND, IP_VPS])
        mediamtx.verify_internal_api_rule(remediated)

    def test_remediate_is_idempotent_noop_on_conforming_rule(self) -> None:
        remediated, ips, needed = mediamtx.remediate_internal_reader_rule(LIVE_CONFIG, "cam1")
        self.assertFalse(needed)
        self.assertEqual(ips, [IP_VPS])
        self.assertEqual(remediated, LIVE_CONFIG)

    def test_remediate_fails_closed_on_publish_action(self) -> None:
        # The cam1 relay profile is read-only; publish cannot be canonized.
        publish_rule = (
            CANONICAL_READER_RULE
            + "      - action: publish\n"
            + '        path: "cam1"\n'
        )
        text = live_with_reader_block(publish_rule)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.remediate_internal_reader_rule(text, "cam1")
        self.assertIn(publish_rule, text)

    def test_remediate_fails_closed_on_action_outside_read_publish(self) -> None:
        api_action_rule = CANONICAL_READER_RULE.replace(
            "      - action: read\n", "      - action: api\n", 1
        )
        text = live_with_reader_block(api_action_rule)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.remediate_internal_reader_rule(text, "cam1")
        self.assertIn(api_action_rule, text)

    def test_remediate_fails_closed_on_public_ip(self) -> None:
        public_rule = CANONICAL_READER_RULE.replace(IP_VPS, "203.0.113.8", 1)
        text = live_with_reader_block(public_rule)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.remediate_internal_reader_rule(text, "cam1")
        self.assertIn(public_rule, text)

    def test_remediate_fails_closed_on_loopback_ip(self) -> None:
        loopback_rule = CANONICAL_READER_RULE.replace(IP_VPS, "127.0.0.1", 1)
        text = live_with_reader_block(loopback_rule)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.remediate_internal_reader_rule(text, "cam1")
        self.assertIn(loopback_rule, text)

    def test_remediate_fails_closed_on_non_ipv4_entry(self) -> None:
        cidr_rule = CANONICAL_READER_RULE.replace(IP_VPS, "10.0.0.0/24", 1)
        text = live_with_reader_block(cidr_rule)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.remediate_internal_reader_rule(text, "cam1")
        self.assertIn(cidr_rule, text)

    def test_remediate_fails_closed_on_duplicate_ips(self) -> None:
        duplicate_rule = (
            f"  {READER_MARKER_CAM1}\n"
            "  - user: any\n"
            "    pass:\n"
            f'    ips: ["{IP_VPS}", "{IP_VPS}"]\n'
            "    permissions:\n"
            "      - action: read\n"
            '        path: "cam1"\n'
        )
        text = live_with_reader_block(duplicate_rule)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.remediate_internal_reader_rule(text, "cam1")
        self.assertIn(duplicate_rule, text)

    def test_remediate_fails_closed_without_marked_rule(self) -> None:
        without_reader = HEADER + MARKED_API_RULE + MARKED_READER_H264_RULE + "\n" + TAIL
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.remediate_internal_reader_rule(without_reader, "cam1")

    def test_remediate_fails_closed_on_multiple_marked_rules(self) -> None:
        duplicated = (
            HEADER
            + MARKED_API_RULE
            + CANONICAL_READER_RULE
            + CANONICAL_READER_RULE
            + MARKED_READER_H264_RULE
            + "\n"
            + TAIL
        )
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.remediate_internal_reader_rule(duplicated, "cam1")

    def test_remediate_fails_closed_on_foreign_entry_inside_span(self) -> None:
        # A foreign unmarked entry between the cam1 block and the next reader
        # marker would merge scopes in the legacy span parse — remediation
        # refuses to canonize merged auth rules (run sanitize first).
        foreign_duplicate = (
            "  - user: any\n"
            "    pass:\n"
            '    ips: ["127.0.0.1"]\n'
            "    permissions:\n"
            "      - action: api\n"
        )
        text = (
            HEADER
            + MARKED_API_RULE
            + CANONICAL_READER_RULE
            + foreign_duplicate
            + MARKED_READER_H264_RULE
            + "\n"
            + TAIL
        )
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.remediate_internal_reader_rule(text, "cam1")
        self.assertIn(foreign_duplicate, text)

    def test_remediate_requires_internal_auth_method(self) -> None:
        external = LIVE_CONFIG.replace("authMethod: internal", "authMethod: http", 1)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.remediate_internal_reader_rule(external, "cam1")


class RemediateCliTests(unittest.TestCase):
    """CLI mode ubuntu-remediate-reader: verify-before -> converge -> 0600."""

    def run_renderer(self, config_text: str) -> tuple[subprocess.CompletedProcess[str], bytes | None, int | None]:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "mediamtx.yml"
            candidate = root / "candidate.yml"
            config.write_text(config_text, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "ubuntu-remediate-reader",
                    "--config",
                    str(config),
                    "--path",
                    "cam1",
                    "--output",
                    str(candidate),
                ],
                text=True,
                capture_output=True,
            )
            candidate_bytes = candidate.read_bytes() if candidate.exists() else None
            candidate_mode = candidate.stat().st_mode & 0o777 if candidate.exists() else None
            return result, candidate_bytes, candidate_mode

    def test_cli_remediate_converges_and_writes_0600_candidate(self) -> None:
        drifted = live_with_reader_block(DRIFTED_SINGLE_IP_RULE)
        result, candidate_bytes, candidate_mode = self.run_renderer(drifted)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("REMEDIATED mode=ubuntu-remediate-reader", result.stdout)
        self.assertIn("remediation_needed=YES", result.stdout)
        self.assertIn("reader_scope=single-rfc1918-ip", result.stdout)
        self.assertIn("reader_permission=read-only", result.stdout)
        self.assertIn("output_sha256=", result.stdout)
        self.assertIsNotNone(candidate_bytes)
        self.assertEqual(candidate_mode, 0o600)
        remediated = (candidate_bytes or b"").decode("utf-8")
        self.assertEqual(
            remediated,
            HEADER + MARKED_API_RULE + CANONICAL_READER_RULE + MARKED_READER_H264_RULE + "\n" + TAIL,
        )
        mediamtx.verify_internal_reader_rule(remediated, "cam1", IP_VPS)
        mediamtx.verify_internal_api_rule(remediated)

    def test_cli_remediate_noop_is_byte_identical_with_clear_evidence(self) -> None:
        result, candidate_bytes, _ = self.run_renderer(LIVE_CONFIG)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("remediation_needed=NO", result.stdout)
        self.assertIsNotNone(candidate_bytes)
        self.assertEqual(candidate_bytes.decode("utf-8"), LIVE_CONFIG)

    def test_cli_remediate_fail_closed_leaves_candidate_untouched(self) -> None:
        publish_rule = (
            CANONICAL_READER_RULE
            + "      - action: publish\n"
            + '        path: "cam1"\n'
        )
        text = live_with_reader_block(publish_rule)
        result, candidate_bytes, _ = self.run_renderer(text)
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR:", result.stderr)
        self.assertIn("read-only", result.stderr)
        self.assertIsNone(candidate_bytes)

    def test_cli_remediate_verify_before_rejects_external_auth_method(self) -> None:
        external = LIVE_CONFIG.replace("authMethod: internal", "authMethod: http", 1)
        result, candidate_bytes, _ = self.run_renderer(external)
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR:", result.stderr)
        self.assertIsNone(candidate_bytes)


class RemediateShellContractTests(unittest.TestCase):
    """Structural pins (established style): the remediate subcommand reuses the
    digest-bound activate runbook and never mutates live state directly."""

    def test_shell_contracts_remediate_subcommand(self) -> None:
        subprocess.run(["bash", "-n", str(UBUNTU)], check=True)
        ubuntu = UBUNTU.read_text(encoding="utf-8")
        self.assertIn("prepare|activate|sanitize|remediate|status", ubuntu)
        self.assertIn("camera-relay.sh remediate --config PATH", ubuntu)
        self.assertIn("ubuntu-remediate-reader", ubuntu)
        # Verify-before on LIVE and verify-after on CANDIDATE (reader domain),
        # plus the existing activate verify and the #436 sanitize pair — five
        # verify-reader-auth calls total.
        self.assertEqual(ubuntu.count("verify-reader-auth"), 5)
        # The remediate candidate goes through the same digest emission as
        # prepare/sanitize; activation stays the existing expected-sha256 flow.
        self.assertEqual(ubuntu.count("CANDIDATE_SHA256=%s"), 3)
        self.assertEqual(ubuntu.count("MUTATIONS=PROTECTED_CANDIDATE_ONLY"), 3)
        self.assertIn("REMEDIATED_READER=YES", ubuntu)
        self.assertIn("REMEDIATION_NEEDED=%s", ubuntu)
        self.assertIn('remediation_needed="YES"', ubuntu)
        self.assertIn("SERVICE_RESTARTED=NO", ubuntu)
        self.assertIn("--expected-sha256", ubuntu)
        self.assertIn("automatic rollback is not authorized", ubuntu)
        self.assertNotIn('systemctl restart "$worker_service"', ubuntu)
        self.assertNotIn('systemctl start "$worker_service"', ubuntu)
        self.assertNotIn('systemctl enable "$worker_service"', ubuntu)


if __name__ == "__main__":
    unittest.main()
