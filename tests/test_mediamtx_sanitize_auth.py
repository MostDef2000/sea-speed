"""Issue #436: prune foreign unmarked loopback-API auth rules via the canonical tool.

The #407 on-box activation left a foreign UNMARKED authInternalUsers entry
(hand-added on 2026-10-07) whose scope exactly equals the canonical loopback
API rule (ips ["127.0.0.1"] / action api). The existing verify machinery is
marker-anchored and merges ips/actions across its span, so the duplicate is
invisible to it and every re-render reinstalls it. This battery pins the new
bounded sanitize path:

- renderer core: foreign = authInternalUsers entry whose preceding non-blank
  line is not a "# Sea Speed " marker comment; ONLY foreign entries whose
  scope EXACTLY equals the canonical loopback-api scope (ips == {127.0.0.1},
  actions == {"api"}, fully modeled fields) are deletable; ANY other foreign
  entry fails the whole sanitize closed (ConfigError before any deletion);
  marked rules are preserved byte-identically.
- renderer CLI: `ubuntu-sanitize-auth` verifies the marked API rule
  (verify-before), prunes, asserts the foreign-rule count == 0 explicitly
  (NOT via the legacy span-merge verify), re-verifies (verify-after) and
  writes a 0600 candidate; failure leaves the candidate untouched.
- shell contract: `camera-relay.sh sanitize` wires verify-before (reader rule
  on LIVE) -> sanitize render -> verify-after (reader rule on CANDIDATE) and
  reuses the existing digest-bound activate flow unchanged.
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
IP_PUB = "10.0.0.9"

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

MARKED_READER_RULE = (
    f"  {READER_MARKER_CAM1}\n"
    "  - user: any\n"
    "    pass:\n"
    f'    ips: ["{IP_VPS}"]\n'
    "    permissions:\n"
    "      - action: read\n"
    '        path: "cam1"\n'
)

MARKED_READER_H264_RULE = (
    f"  {READER_MARKER_CAM1_H264}\n"
    "  - user: any\n"
    "    pass:\n"
    f'    ips: ["{IP_VPS}", "{IP_PUB}"]\n'
    "    permissions:\n"
    "      - action: read\n"
    '        path: "cam1-h264"\n'
    "      - action: publish\n"
    '        path: "cam1-h264"\n'
)

# The exact unmarked duplicate shape observed on the worker (issue #436).
FOREIGN_DUPLICATE = (
    "  - user: any\n"
    "    pass:\n"
    '    ips: ["127.0.0.1"]\n'
    "    permissions:\n"
    "      - action: api\n"
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

LIVE_CONFIG = (
    HEADER
    + MARKED_API_RULE
    + MARKED_READER_RULE
    + MARKED_READER_H264_RULE
    + FOREIGN_DUPLICATE
    + "\n"
    + TAIL
)
EXPECTED_PRUNED = LIVE_CONFIG.replace(FOREIGN_DUPLICATE, "", 1)


def live_with_foreign(foreign_block: str) -> str:
    return HEADER + MARKED_API_RULE + MARKED_READER_RULE + foreign_block + "\n" + TAIL


class SanitizeForeignAuthRuleTests(unittest.TestCase):
    """Renderer core: bounded foreign-rule scan/prune with fail-closed scope."""

    def test_scan_counts_only_unmarked_entries(self) -> None:
        self.assertEqual(mediamtx.count_foreign_auth_rules(LIVE_CONFIG), 1)
        descriptions = mediamtx.scan_foreign_auth_rules(LIVE_CONFIG)
        self.assertEqual(len(descriptions), 1)
        self.assertIn("127.0.0.1", descriptions[0])
        self.assertIn("api", descriptions[0])
        # The canonical marked rules are never counted as foreign.
        self.assertEqual(mediamtx.count_foreign_auth_rules(EXPECTED_PRUNED), 0)
        self.assertEqual(mediamtx.scan_foreign_auth_rules(EXPECTED_PRUNED), [])

    def test_sanitize_removes_only_the_canonical_scope_duplicate(self) -> None:
        pruned, removed = mediamtx.sanitize_foreign_auth_rules(LIVE_CONFIG)
        self.assertEqual(removed, 1)
        self.assertEqual(pruned, EXPECTED_PRUNED)
        # Marked rules survive byte-identically (AC-2).
        self.assertIn(MARKED_API_RULE, pruned)
        self.assertIn(MARKED_READER_RULE, pruned)
        self.assertIn(MARKED_READER_H264_RULE, pruned)
        # The canonical verify pair passes next to the pruned block.
        mediamtx.verify_internal_api_rule(pruned)
        mediamtx.verify_internal_reader_rule(pruned, "cam1", IP_VPS)
        mediamtx.verify_internal_reader_rule(pruned, "cam1-h264", [IP_VPS, IP_PUB])

    def test_sanitize_is_idempotent_noop_without_foreign_rules(self) -> None:
        pruned, removed = mediamtx.sanitize_foreign_auth_rules(EXPECTED_PRUNED)
        self.assertEqual(removed, 0)
        self.assertEqual(pruned, EXPECTED_PRUNED)

    def test_sanitize_fails_closed_on_wider_foreign_ips(self) -> None:
        wider = (
            "  - user: any\n"
            "    pass:\n"
            f'    ips: ["{IP_VPS}", "127.0.0.1"]\n'
            "    permissions:\n"
            "      - action: api\n"
        )
        text = live_with_foreign(wider)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.sanitize_foreign_auth_rules(text)
        # Fail closed = no deletion, text untouched.
        self.assertEqual(mediamtx.count_foreign_auth_rules(text), 1)
        self.assertIn(wider, text)

    def test_sanitize_fails_closed_on_wider_foreign_actions(self) -> None:
        wider = (
            "  - user: any\n"
            "    pass:\n"
            '    ips: ["127.0.0.1"]\n'
            "    permissions:\n"
            "      - action: api\n"
            "      - action: read\n"
        )
        text = live_with_foreign(wider)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.sanitize_foreign_auth_rules(text)
        self.assertIn(wider, text)

    def test_sanitize_fails_closed_on_non_api_foreign_rule(self) -> None:
        reader_like = (
            "  - user: any\n"
            "    pass:\n"
            f'    ips: ["{IP_VPS}"]\n'
            "    permissions:\n"
            "      - action: read\n"
            '        path: "cam1"\n'
        )
        text = live_with_foreign(reader_like)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.sanitize_foreign_auth_rules(text)
        self.assertIn(reader_like, text)

    def test_sanitize_fails_closed_on_ip_less_api_rule(self) -> None:
        # No ips restriction = wider than the canonical loopback scope.
        ip_less = (
            "  - user: any\n"
            "    pass:\n"
            "    permissions:\n"
            "      - action: api\n"
        )
        text = live_with_foreign(ip_less)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.sanitize_foreign_auth_rules(text)
        self.assertIn(ip_less, text)

    def test_sanitize_fails_closed_on_unmodeled_fields(self) -> None:
        exotic = (
            "  - user: any\n"
            "    pass:\n"
            '    ips: ["127.0.0.1"]\n'
            "    permissions:\n"
            "      - action: api\n"
            "        ips: [127.0.0.1]\n"
        )
        text = live_with_foreign(exotic)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.sanitize_foreign_auth_rules(text)
        self.assertIn(exotic, text)

    def test_sanitize_requires_internal_auth_method(self) -> None:
        external = LIVE_CONFIG.replace("authMethod: internal", "authMethod: http", 1)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.sanitize_foreign_auth_rules(external)

    def test_sanitize_requires_auth_internal_users_block(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            config = Path(raw) / "mediamtx.yml"
            config.write_text("logLevel: info\npaths:\n  cam1:\n", encoding="utf-8")
            with self.assertRaises(mediamtx.ConfigError):
                mediamtx.sanitize_foreign_auth_rules(config.read_text(encoding="utf-8"))

    def test_sanitize_removes_multiple_exact_duplicates(self) -> None:
        duplicated = (
            HEADER
            + MARKED_API_RULE
            + MARKED_READER_RULE
            + FOREIGN_DUPLICATE
            + FOREIGN_DUPLICATE
            + "\n"
            + TAIL
        )
        pruned, removed = mediamtx.sanitize_foreign_auth_rules(duplicated)
        self.assertEqual(removed, 2)
        self.assertEqual(pruned, HEADER + MARKED_API_RULE + MARKED_READER_RULE + "\n" + TAIL)


class SanitizeCliTests(unittest.TestCase):
    """CLI mode ubuntu-sanitize-auth: verify-before -> prune -> verify-after."""

    def test_cli_sanitize_removes_duplicate_and_reverifies_clean(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "mediamtx.yml"
            candidate = root / "candidate.yml"
            config.write_text(LIVE_CONFIG, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "ubuntu-sanitize-auth",
                    "--config",
                    str(config),
                    "--output",
                    str(candidate),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SANITIZED mode=ubuntu-sanitize-auth", result.stdout)
            self.assertIn("foreign_rules_removed=1", result.stdout)
            self.assertIn("foreign_rules_remaining=0", result.stdout)
            self.assertIn("output_sha256=", result.stdout)
            self.assertEqual(candidate.stat().st_mode & 0o777, 0o600)
            pruned = candidate.read_text(encoding="utf-8")
            self.assertEqual(pruned, EXPECTED_PRUNED)
            mediamtx.verify_internal_api_rule(pruned)
            mediamtx.verify_internal_reader_rule(pruned, "cam1", IP_VPS)
            mediamtx.verify_internal_reader_rule(pruned, "cam1-h264", [IP_VPS, IP_PUB])

    def test_cli_sanitize_noop_is_byte_identical_and_reverifies_clean(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "mediamtx.yml"
            candidate = root / "candidate.yml"
            config.write_text(EXPECTED_PRUNED, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "ubuntu-sanitize-auth",
                    "--config",
                    str(config),
                    "--output",
                    str(candidate),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("foreign_rules_removed=0", result.stdout)
            self.assertIn("foreign_rules_remaining=0", result.stdout)
            self.assertEqual(candidate.read_text(encoding="utf-8"), EXPECTED_PRUNED)

    def test_cli_sanitize_fail_closed_leaves_candidate_untouched(self) -> None:
        wider = (
            "  - user: any\n"
            "    pass:\n"
            f'    ips: ["{IP_VPS}", "127.0.0.1"]\n'
            "    permissions:\n"
            "      - action: api\n"
        )
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "mediamtx.yml"
            candidate = root / "candidate.yml"
            config.write_text(live_with_foreign(wider), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "ubuntu-sanitize-auth",
                    "--config",
                    str(config),
                    "--output",
                    str(candidate),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("ERROR:", result.stderr)
            self.assertIn("loopback-api scope", result.stderr)
            self.assertFalse(candidate.exists())

    def test_cli_sanitize_verify_before_rejects_missing_marked_api_rule(self) -> None:
        without_api = (
            HEADER
            + MARKED_READER_RULE
            + MARKED_READER_H264_RULE
            + FOREIGN_DUPLICATE
            + "\n"
            + TAIL
        )
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "mediamtx.yml"
            candidate = root / "candidate.yml"
            config.write_text(without_api, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "ubuntu-sanitize-auth",
                    "--config",
                    str(config),
                    "--output",
                    str(candidate),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("ERROR:", result.stderr)
            self.assertFalse(candidate.exists())


class SanitizeShellContractTests(unittest.TestCase):
    """Structural pins (established style): the sanitize subcommand reuses the
    digest-bound activate runbook and never mutates live state directly."""

    def test_shell_contracts_sanitize_subcommand(self) -> None:
        subprocess.run(["bash", "-n", str(UBUNTU)], check=True)
        ubuntu = UBUNTU.read_text(encoding="utf-8")
        self.assertIn("prepare|activate|sanitize|status", ubuntu)
        self.assertIn("camera-relay.sh sanitize --config PATH", ubuntu)
        self.assertIn("ubuntu-sanitize-auth", ubuntu)
        # Verify-before on LIVE and verify-after on CANDIDATE (reader domain),
        # plus the existing activate verify -> three verify-reader-auth calls.
        self.assertEqual(ubuntu.count("verify-reader-auth"), 3)
        # The sanitize candidate goes through the same digest emission as
        # prepare; activation stays the existing expected-sha256 flow.
        self.assertEqual(ubuntu.count("CANDIDATE_SHA256=%s"), 2)
        self.assertEqual(ubuntu.count("MUTATIONS=PROTECTED_CANDIDATE_ONLY"), 2)
        self.assertIn("SANITIZED_FOREIGN_AUTH=YES", ubuntu)
        self.assertIn("SERVICE_RESTARTED=NO", ubuntu)
        self.assertIn("--expected-sha256", ubuntu)
        self.assertIn("automatic rollback is not authorized", ubuntu)
        self.assertNotIn('systemctl restart "$worker_service"', ubuntu)
        self.assertNotIn('systemctl start "$worker_service"', ubuntu)
        self.assertNotIn('systemctl enable "$worker_service"', ubuntu)


if __name__ == "__main__":
    unittest.main()
