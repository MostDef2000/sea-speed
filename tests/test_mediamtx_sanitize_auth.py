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
        # Issue #437 adds the `remediate` subcommand to the same dispatch.
        self.assertIn("prepare|activate|sanitize|remediate|status", ubuntu)
        self.assertIn("camera-relay.sh sanitize --config PATH", ubuntu)
        self.assertIn("ubuntu-sanitize-auth", ubuntu)
        # Verify-before on LIVE and verify-after on CANDIDATE (reader domain),
        # plus the existing activate verify and the #437 remediate pair — five
        # verify-reader-auth calls total.
        self.assertEqual(ubuntu.count("verify-reader-auth"), 5)
        # The sanitize candidate goes through the same digest emission as
        # prepare; activation stays the existing expected-sha256 flow. Issue
        # #437 adds a third digest-emitting remediate block.
        self.assertEqual(ubuntu.count("CANDIDATE_SHA256=%s"), 3)
        self.assertEqual(ubuntu.count("MUTATIONS=PROTECTED_CANDIDATE_ONLY"), 3)
        self.assertIn("SANITIZED_FOREIGN_AUTH=YES", ubuntu)
        self.assertIn("SERVICE_RESTARTED=NO", ubuntu)
        self.assertIn("--expected-sha256", ubuntu)
        self.assertIn("automatic rollback is not authorized", ubuntu)
        self.assertNotIn('systemctl restart "$worker_service"', ubuntu)
        self.assertNotIn('systemctl start "$worker_service"', ubuntu)
        self.assertNotIn('systemctl enable "$worker_service"', ubuntu)


# ---------------------------------------------------------------------------
# Issue #444: explicit opt-in prune of DECLARED legacy foreign rules.
#
# The 2026-10-10 operator sanitize transaction failed closed (by design)
# because the live config carries two UNMARKED legacy rules for the dead
# `cam1-test` path beside the target loopback-API duplicate. #444 adds
# repeatable explicit opt-in prune declarations: a declared (path, ips,
# actions) triple makes EXACTLY the unmarked rules matching that triple
# removable; every other foreign rule still fails the whole transaction
# closed. WITHOUT declarations the behavior is byte-for-byte the #436
# fail-closed default.
# ---------------------------------------------------------------------------

IP_LEGACY_PUBLISH = "10.123.239.102"

# The two unmarked legacy cam1-test rules observed on the worker (issue #444).
FOREIGN_CAM1_TEST_PUBLISH = (
    "  - user: any\n"
    "    pass:\n"
    f'    ips: ["{IP_LEGACY_PUBLISH}"]\n'
    "    permissions:\n"
    "      - action: publish\n"
    '        path: "cam1-test"\n'
    "      - action: read\n"
    '        path: "cam1-test"\n'
)

FOREIGN_CAM1_TEST_READ = (
    "  - user: any\n"
    "    pass:\n"
    f'    ips: ["{IP_VPS}"]\n'
    "    permissions:\n"
    "      - action: read\n"
    '        path: "cam1-test"\n'
)

# Explicit opt-in prune declarations (exact documented grammar).
DECL_SPEC_PUBLISH = f"path=cam1-test,ips={IP_LEGACY_PUBLISH},actions=publish,read"
DECL_SPEC_READ = f"path=cam1-test,ips={IP_VPS},actions=read"

# The retry-window transaction shape (issue #444): loopback-API duplicate
# (removable by default under #436) + both legacy cam1-test rules (removable
# only via explicit declarations), all three removed by one sanitize.
LEGACY_CONFIG = (
    HEADER
    + MARKED_API_RULE
    + MARKED_READER_RULE
    + MARKED_READER_H264_RULE
    + FOREIGN_DUPLICATE
    + FOREIGN_CAM1_TEST_PUBLISH
    + FOREIGN_CAM1_TEST_READ
    + "\n"
    + TAIL
)
EXPECTED_DECLARED_PRUNED = (
    HEADER
    + MARKED_API_RULE
    + MARKED_READER_RULE
    + MARKED_READER_H264_RULE
    + "\n"
    + TAIL
)


def legacy_with_foreign(foreign_block: str) -> str:
    """Marked rules + declared-shape cam1-test rules + one extra foreign block."""
    return (
        HEADER
        + MARKED_API_RULE
        + MARKED_READER_RULE
        + FOREIGN_CAM1_TEST_PUBLISH
        + FOREIGN_CAM1_TEST_READ
        + foreign_block
        + "\n"
        + TAIL
    )


class DeclaredAuthPruneSpecTests(unittest.TestCase):
    """Declaration grammar: path=<p>,ips=<i,...>,actions=<a,...> (repeatable
    flag; bare tokens continue the previous key)."""

    def test_parse_declared_spec_full_grammar(self) -> None:
        declaration = mediamtx.parse_declared_auth_prune(
            f"path=cam1-test,ips={IP_LEGACY_PUBLISH},actions=publish,read"
        )
        self.assertEqual(declaration.path, "cam1-test")
        self.assertEqual(declaration.ips, (IP_LEGACY_PUBLISH,))
        self.assertEqual(declaration.actions, ("publish", "read"))

    def test_parse_declared_spec_bare_tokens_continue_previous_key(self) -> None:
        declaration = mediamtx.parse_declared_auth_prune(
            f"path=cam1-test,ips={IP_LEGACY_PUBLISH},{IP_VPS},actions=publish,read"
        )
        self.assertEqual(declaration.ips, (IP_LEGACY_PUBLISH, IP_VPS))
        self.assertEqual(declaration.actions, ("publish", "read"))

    def test_parse_declared_spec_rejects_unknown_key(self) -> None:
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.parse_declared_auth_prune("path=cam1-test,users=x,actions=read")

    def test_parse_declared_spec_rejects_missing_path(self) -> None:
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.parse_declared_auth_prune(f"ips={IP_VPS},actions=read")

    def test_parse_declared_spec_rejects_missing_ips(self) -> None:
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.parse_declared_auth_prune("path=cam1-test,actions=read")

    def test_parse_declared_spec_rejects_missing_actions(self) -> None:
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.parse_declared_auth_prune(f"path=cam1-test,ips={IP_VPS}")

    def test_parse_declared_spec_rejects_invalid_ip(self) -> None:
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.parse_declared_auth_prune("path=cam1-test,ips=not-an-ip,actions=read")

    def test_parse_declared_spec_rejects_invalid_action(self) -> None:
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.parse_declared_auth_prune(
                f"path=cam1-test,ips={IP_VPS},actions=read,play"
            )

    def test_parse_declared_spec_rejects_duplicate_path_key(self) -> None:
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.parse_declared_auth_prune(
                f"path=cam1-test,path=cam1,ips={IP_VPS},actions=read"
            )

    def test_parse_declared_spec_rejects_empty_spec(self) -> None:
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.parse_declared_auth_prune("")


class DeclaredPruneCoreTests(unittest.TestCase):
    """Renderer core: declared triples extend the removable set; everything
    else about the #436 fail-closed discipline is unchanged."""

    def _decls(self):
        return [
            mediamtx.parse_declared_auth_prune(DECL_SPEC_PUBLISH),
            mediamtx.parse_declared_auth_prune(DECL_SPEC_READ),
        ]

    def test_declared_prune_removes_exactly_the_declared_triples(self) -> None:
        pruned, removed, per_declaration = mediamtx.sanitize_foreign_auth_rules_declared(
            LEGACY_CONFIG, self._decls()
        )
        # 1 loopback-API duplicate (default #436 scope) + 2 declared triples.
        self.assertEqual(removed, 3)
        self.assertEqual(per_declaration, [1, 1])
        self.assertEqual(pruned, EXPECTED_DECLARED_PRUNED)
        self.assertNotIn("cam1-test", pruned)
        # Marked rules survive byte-identically; canonical verifies pass.
        self.assertIn(MARKED_API_RULE, pruned)
        self.assertIn(MARKED_READER_RULE, pruned)
        self.assertIn(MARKED_READER_H264_RULE, pruned)
        mediamtx.verify_internal_api_rule(pruned)
        mediamtx.verify_internal_reader_rule(pruned, "cam1", IP_VPS)
        mediamtx.verify_internal_reader_rule(pruned, "cam1-h264", [IP_VPS, IP_PUB])
        self.assertEqual(mediamtx.count_foreign_auth_rules(pruned), 0)

    def test_declared_prune_leaves_undeclared_foreign_rule_fail_closed(self) -> None:
        # A third cam1-test-shaped rule whose IP is NOT declared: it is
        # neither the canonical loopback-API scope nor a declared triple, so
        # it must refuse the whole transaction (fail closed, text untouched).
        undeclared = (
            "  - user: any\n"
            "    pass:\n"
            f'    ips: ["{IP_PUB}"]\n'
            "    permissions:\n"
            "      - action: read\n"
            '        path: "cam1-test"\n'
        )
        text = legacy_with_foreign(undeclared)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.sanitize_foreign_auth_rules_declared(text, self._decls())
        self.assertIn(FOREIGN_CAM1_TEST_PUBLISH, text)
        self.assertIn(undeclared, text)

    def test_declared_prune_rejects_partial_match_extra_ip(self) -> None:
        extra_ip = (
            "  - user: any\n"
            "    pass:\n"
            f'    ips: ["{IP_LEGACY_PUBLISH}", "10.0.0.9"]\n'
            "    permissions:\n"
            "      - action: publish\n"
            '        path: "cam1-test"\n'
            "      - action: read\n"
            '        path: "cam1-test"\n'
        )
        text = legacy_with_foreign(extra_ip)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.sanitize_foreign_auth_rules_declared(text, self._decls())
        self.assertIn(extra_ip, text)

    def test_declared_prune_rejects_partial_match_different_path(self) -> None:
        # Same ips/actions as a declaration but on the canonical cam1 path:
        # a DIFFERENT triple is still foreign and undeclared.
        cam1_shaped = (
            "  - user: any\n"
            "    pass:\n"
            f'    ips: ["{IP_LEGACY_PUBLISH}"]\n'
            "    permissions:\n"
            "      - action: publish\n"
            '        path: "cam1"\n'
            "      - action: read\n"
            '        path: "cam1"\n'
        )
        text = legacy_with_foreign(cam1_shaped)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.sanitize_foreign_auth_rules_declared(text, self._decls())
        self.assertIn(cam1_shaped, text)

    def test_declared_prune_rejects_partial_match_extra_action(self) -> None:
        extra_action = (
            "  - user: any\n"
            "    pass:\n"
            f'    ips: ["{IP_LEGACY_PUBLISH}"]\n'
            "    permissions:\n"
            "      - action: publish\n"
            '        path: "cam1-test"\n'
            "      - action: read\n"
            '        path: "cam1-test"\n'
            "      - action: api\n"
            '        path: "cam1-test"\n'
        )
        text = legacy_with_foreign(extra_action)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.sanitize_foreign_auth_rules_declared(text, self._decls())
        self.assertIn(extra_action, text)

    def test_no_declarations_is_byte_for_byte_todays_default(self) -> None:
        # AC-1 guard: without declarations the #436 fail-closed behavior is
        # unchanged (the legacy cam1-test rules refuse the transaction).
        with self.assertRaises(mediamtx.ConfigError) as ctx:
            mediamtx.sanitize_foreign_auth_rules(LEGACY_CONFIG)
        self.assertIn("loopback-api scope", str(ctx.exception))
        # The declared-aware core with an empty declaration list behaves
        # identically.
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.sanitize_foreign_auth_rules_declared(LEGACY_CONFIG, [])

    def test_declared_prune_never_touches_marked_rule_matching_the_triple(self) -> None:
        marked_legacy = (
            "  # Sea Speed legacy cam1-test reader (kept example)\n"
            "  - user: any\n"
            "    pass:\n"
            f'    ips: ["{IP_LEGACY_PUBLISH}"]\n'
            "    permissions:\n"
            "      - action: publish\n"
            '        path: "cam1-test"\n'
            "      - action: read\n"
            '        path: "cam1-test"\n'
        )
        text = HEADER + MARKED_API_RULE + marked_legacy + "\n" + TAIL
        pruned, removed, per_declaration = mediamtx.sanitize_foreign_auth_rules_declared(
            text, self._decls()
        )
        self.assertEqual(removed, 0)
        self.assertEqual(per_declaration, [0, 0])
        self.assertEqual(pruned, text)
        self.assertIn(marked_legacy, pruned)

    def test_declared_prune_rejects_unmodeled_foreign_rule_even_if_scoped(self) -> None:
        exotic = (
            "  - user: any\n"
            "    pass:\n"
            f'    ips: ["{IP_LEGACY_PUBLISH}"]\n'
            "    permissions:\n"
            "      - action: publish\n"
            '        path: "cam1-test"\n'
            "        source: any\n"
        )
        text = legacy_with_foreign(exotic)
        with self.assertRaises(mediamtx.ConfigError):
            mediamtx.sanitize_foreign_auth_rules_declared(text, self._decls())
        self.assertIn(exotic, text)

    def test_declared_prune_is_idempotent_noop_on_clean_config(self) -> None:
        pruned, removed, per_declaration = mediamtx.sanitize_foreign_auth_rules_declared(
            EXPECTED_DECLARED_PRUNED, self._decls()
        )
        self.assertEqual(removed, 0)
        self.assertEqual(per_declaration, [0, 0])
        self.assertEqual(pruned, EXPECTED_DECLARED_PRUNED)


class DeclaredPruneCliTests(unittest.TestCase):
    """CLI: repeatable --prune-declared passthrough with per-declaration
    evidence; WITHOUT the flag the transaction is byte-for-byte today's."""

    def test_cli_declared_prune_removes_legacy_rules_and_api_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "mediamtx.yml"
            candidate = root / "candidate.yml"
            config.write_text(LEGACY_CONFIG, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "ubuntu-sanitize-auth",
                    "--config",
                    str(config),
                    "--output",
                    str(candidate),
                    "--prune-declared",
                    DECL_SPEC_PUBLISH,
                    "--prune-declared",
                    DECL_SPEC_READ,
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SANITIZED mode=ubuntu-sanitize-auth", result.stdout)
            self.assertIn("foreign_rules_removed=3", result.stdout)
            self.assertIn("foreign_rules_remaining=0", result.stdout)
            self.assertIn("output_sha256=", result.stdout)
            # Per-declaration removal evidence (AC-3).
            self.assertEqual(result.stdout.count("DECLARED_PRUNED path=cam1-test"), 2)
            self.assertIn(f"ips={IP_LEGACY_PUBLISH}", result.stdout)
            self.assertIn(f"ips={IP_VPS}", result.stdout)
            self.assertEqual(candidate.stat().st_mode & 0o777, 0o600)
            pruned = candidate.read_text(encoding="utf-8")
            self.assertEqual(pruned, EXPECTED_DECLARED_PRUNED)
            mediamtx.verify_internal_api_rule(pruned)
            mediamtx.verify_internal_reader_rule(pruned, "cam1", IP_VPS)
            mediamtx.verify_internal_reader_rule(pruned, "cam1-h264", [IP_VPS, IP_PUB])

    def test_cli_without_declarations_refuses_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "mediamtx.yml"
            candidate = root / "candidate.yml"
            config.write_text(LEGACY_CONFIG, encoding="utf-8")
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
            self.assertNotIn("DECLARED_PRUNED", result.stdout)
            self.assertFalse(candidate.exists())

    def test_cli_one_declaration_with_two_legacy_rules_refuses(self) -> None:
        # Only the publish/read rule is declared; the read-only cam1-test
        # rule stays foreign and undeclared -> whole transaction refuses.
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "mediamtx.yml"
            candidate = root / "candidate.yml"
            config.write_text(LEGACY_CONFIG, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "ubuntu-sanitize-auth",
                    "--config",
                    str(config),
                    "--output",
                    str(candidate),
                    "--prune-declared",
                    DECL_SPEC_PUBLISH,
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("ERROR:", result.stderr)
            self.assertFalse(candidate.exists())

    def test_cli_invalid_declaration_spec_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            config = root / "mediamtx.yml"
            candidate = root / "candidate.yml"
            config.write_text(LEGACY_CONFIG, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(RENDERER),
                    "ubuntu-sanitize-auth",
                    "--config",
                    str(config),
                    "--output",
                    str(candidate),
                    "--prune-declared",
                    "path=cam1-test,users=x,actions=read",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("ERROR:", result.stderr)
            self.assertFalse(candidate.exists())


class DeclaredPruneShellTests(unittest.TestCase):
    """Shell contract: camera-relay.sh sanitize forwards repeatable
    --prune-declared specs to the renderer and reports per-declaration
    removals; the digest-bound activate discipline is untouched."""

    def test_shell_contracts_declared_prune_passthrough(self) -> None:
        subprocess.run(["bash", "-n", str(UBUNTU)], check=True)
        ubuntu = UBUNTU.read_text(encoding="utf-8")
        # Usage documents the repeatable declaration option for sanitize.
        self.assertIn("--prune-declared", ubuntu)
        # The option is collected repeatable and forwarded to the renderer.
        self.assertIn("declared_prune_specs+=(", ubuntu)
        self.assertIn("declared_args+=(--prune-declared", ubuntu)
        self.assertIn('"${declared_args[@]}"', ubuntu)
        # Per-declaration removal evidence line (AC-3).
        self.assertIn("DECLARED_PRUNED=", ubuntu)
        # The transaction discipline is unchanged: still exactly five
        # verify-reader-auth calls, three digest-emitting blocks, no worker
        # control, no auto-rollback.
        self.assertEqual(ubuntu.count("verify-reader-auth"), 5)
        self.assertEqual(ubuntu.count("CANDIDATE_SHA256=%s"), 3)
        self.assertEqual(ubuntu.count("MUTATIONS=PROTECTED_CANDIDATE_ONLY"), 3)
        self.assertIn("SANITIZED_FOREIGN_AUTH=YES", ubuntu)
        self.assertIn("automatic rollback is not authorized", ubuntu)


if __name__ == "__main__":
    unittest.main()
