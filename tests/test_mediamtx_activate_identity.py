"""Issues #447/#449: activate service-identity derivation must fail closed
AND be productive offline.

Incident (2026-10-10, on-box activate under docker-chroot): `systemctl show
-p User` returned empty ("Failed to connect to system scope bus") and the
activate block silently fell back to root:root 0600 instead of the service's
root:mediamtx 0640; mediamtx crash-looped on the installed config until the
operator hand-fixed ownership. The no-auto-rollback contract held, but the
permission derivation failed OPEN. #447 made the derivation fail closed.

RF-001 on-box finding (#449): `systemctl cat` is ALSO bus-dependent — under
docker-chroot the #447 unit-file fallback never fired; activate refused
fail-closed (safe, but never productively derived). #449 makes the offline
branch parse the ON-DISK unit file directly (standard unit paths, first
readable regular non-symlink file wins, drop-in directory next to it
merged, LAST `User=`/`Group=` assignment still wins) and tolerates optional
whitespace after `=` in the captures (hand-edited `User= mediamtx` edge —
the incident direction; #448 peer review F3a). Neither derivation readable
still refuses with the explicit #447 error BEFORE backup/install.

This battery pins:
- `derive_relay_service_identity` (extractable function): (1) `systemctl
  show` is definitive only when User is non-empty; (2) the offline branch
  reads the on-disk unit file (+ its `.d/*.conf` drop-ins, lexical order)
  and parses the LAST assignment with whitespace tolerance; (3) BOTH
  failing returns nonzero with the explicit ERROR. The function must NOT
  call `systemctl cat` (bus-dependent — the #449 bug).
- The caller's exact field order (`read -r install_owner install_group
  install_mode <<< "$identity"`) is pinned (#448 F2).
- The activate block evidences the derived identity before any mutation.
- The activate flow is otherwise unchanged (digest binding, backup, restart,
  probes, no auto-rollback); renderer invocation counts are unchanged.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from support import relay_shell  # noqa: E402

UBUNTU = ROOT / "deploy/worker/ubuntu/camera-relay.sh"

UNIT_PATH_ROOTS = {
    "etc": "/etc/systemd/system",
    "lib": "/lib/systemd/system",
    "usrlib": "/usr/lib/systemd/system",
}


def shell_function(source: str, name: str) -> str:
    start = source.index(f"{name}() {{")
    end = source.index("\n}\n\n", start) + 2
    return source[start:end]


def run_identity(
    source: str,
    systemctl_stub: str,
    id_stub: str = "",
    unit_files: dict[str, str] | None = None,
    dropin_files: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Execute the extracted derivation with stubbed systemctl/id.

    #449: the offline branch parses the ON-DISK unit file, so the harness
    substitutes the function's unit-path roots with a temp tree (the path
    literals are asserted first so a path drift fails loudly) and
    materializes the scenario's unit files there: `unit_files` maps a root
    kind ("etc"/"lib"/"usrlib") to the unit content; `dropin_files` maps a
    root kind to override.conf content placed in `<unit>.d/`.
    """
    function = shell_function(source, "derive_relay_service_identity")
    with tempfile.TemporaryDirectory() as raw:
        tree = Path(raw)
        for kind, root_literal in sorted(
            UNIT_PATH_ROOTS.items(), key=lambda item: -len(item[1])
        ):
            # The harness seam: the real path literal must exist in the
            # function source, then is substituted with the temp tree.
            # Longest-first so /usr/lib/... is not corrupted by the
            # /lib/... substring replacement.
            self_check = f'"{root_literal}/$service_name"'
            assert self_check in function, f"unit path literal drifted: {self_check}"
            function = function.replace(root_literal, str(tree / kind))
            unit_root = tree / kind
            unit_root.mkdir(parents=True, exist_ok=True)
            if unit_files and kind in unit_files:
                (unit_root / "sea-speed-stream.service").write_text(unit_files[kind], encoding="utf-8")
            if dropin_files and kind in dropin_files:
                dropin_dir = unit_root / "sea-speed-stream.service.d"
                dropin_dir.mkdir(parents=True, exist_ok=True)
                (dropin_dir / "override.conf").write_text(dropin_files[kind], encoding="utf-8")
        stubs = systemctl_stub + ("\n" + id_stub if id_stub else "") + "\n"
        script = (
            f"{function}\n{stubs}\n"
            "service_name='sea-speed-stream.service'\n"
            'identity="$(derive_relay_service_identity)"\n'
            "rc=$?\n"
            'printf "RC=%s\\n" "$rc"\n'
            '[[ $rc -eq 0 ]] && printf "IDENTITY=%s\\n" "$identity"\n'
            'exit "$rc"\n'
        )
        return subprocess.run(["bash", "-c", script, "_"], text=True, capture_output=True)


# systemctl stubs ------------------------------------------------------------

SHOW_MEDIAMTX = (
    "systemctl() {\n"
    '  if [[ "$1" == show && "$3" == User ]]; then printf "mediamtx\\n"; return 0; fi\n'
    '  if [[ "$1" == show && "$3" == Group ]]; then printf "mediamtx\\n"; return 0; fi\n'
    "  return 0\n"
    "}"
)

SHOW_ROOT = (
    "systemctl() {\n"
    '  if [[ "$1" == show && "$3" == User ]]; then printf "root\\n"; return 0; fi\n'
    '  if [[ "$1" == show && "$3" == Group ]]; then printf "root\\n"; return 0; fi\n'
    "  return 0\n"
    "}"
)

# Real chroot shape (#449 RF-001 finding): systemctl is bus-dependent for
# EVERYTHING — show AND cat both fail even though the unit file is readable
# on disk.
BUS_FAIL = (
    "systemctl() {\n"
    '  echo "Failed to connect to system scope bus via local transport" >&2\n'
    "  return 1\n"
    "}"
)

UNIT_MEDIAMTX = "[Service]\nUser=mediamtx\nGroup=mediamtx\nExecStart=/usr/bin/mediamtx\n"
UNIT_NO_USER = "[Service]\nExecStart=/usr/bin/mediamtx\n"
UNIT_NO_GROUP = "[Service]\nUser=mediamtx\n"
UNIT_WHITESPACE = "[Service]\nUser= mediamtx\nGroup= mediamtx\n"

ID_MEDIAMTX = 'id() { printf "mediamtx\\n"; }'


class ActivateIdentityDerivationTests(unittest.TestCase):
    """derive_relay_service_identity: show definitive, ON-DISK unit-file
    fallback (#449), fail closed when both are unavailable."""

    def test_show_user_mediamtx_derives_group_from_show(self) -> None:
        result = run_identity(UBUNTU.read_text(encoding="utf-8"), SHOW_MEDIAMTX)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RC=0", result.stdout)
        self.assertIn("IDENTITY=root mediamtx 0640", result.stdout)

    def test_show_explicit_root_keeps_root_root_0600(self) -> None:
        result = run_identity(UBUNTU.read_text(encoding="utf-8"), SHOW_ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IDENTITY=root root 0600", result.stdout)

    def test_chroot_show_and_cat_fail_parses_on_disk_unit_file(self) -> None:
        # The #449 RF-001 finding: under chroot BOTH systemctl show and cat
        # fail (bus-dependent); the unit file on disk is authoritative.
        result = run_identity(
            UBUNTU.read_text(encoding="utf-8"), BUS_FAIL, unit_files={"etc": UNIT_MEDIAMTX}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IDENTITY=root mediamtx 0640", result.stdout)

    def test_chroot_on_disk_unit_without_user_means_root(self) -> None:
        result = run_identity(
            UBUNTU.read_text(encoding="utf-8"), BUS_FAIL, unit_files={"etc": UNIT_NO_USER}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IDENTITY=root root 0600", result.stdout)

    def test_chroot_on_disk_unit_group_missing_resolves_via_id(self) -> None:
        result = run_identity(
            UBUNTU.read_text(encoding="utf-8"), BUS_FAIL, ID_MEDIAMTX, unit_files={"etc": UNIT_NO_GROUP}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IDENTITY=root mediamtx 0640", result.stdout)

    def test_offline_drop_in_directory_last_assignment_wins(self) -> None:
        # systemctl cat used to concatenate main unit + drop-ins; the on-disk
        # parse reads the unit file AND its .d/ override directory, so the
        # last assignment still wins.
        result = run_identity(
            UBUNTU.read_text(encoding="utf-8"),
            BUS_FAIL,
            unit_files={"etc": "[Service]\nUser=legacyuser\nGroup=legacygrp\n"},
            dropin_files={"etc": "[Service]\nUser=mediamtx\nGroup=mediamtx\n"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IDENTITY=root mediamtx 0640", result.stdout)

    def test_offline_unit_path_precedence_etc_wins(self) -> None:
        result = run_identity(
            UBUNTU.read_text(encoding="utf-8"),
            BUS_FAIL,
            unit_files={
                "etc": "[Service]\nUser=mediamtx\nGroup=mediamtx\n",
                "lib": "[Service]\nUser=otheruser\nGroup=othergrp\n",
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IDENTITY=root mediamtx 0640", result.stdout)

    def test_offline_unit_path_precedence_falls_through_to_lib(self) -> None:
        result = run_identity(
            UBUNTU.read_text(encoding="utf-8"),
            BUS_FAIL,
            unit_files={"lib": "[Service]\nUser=mediamtx\nGroup=mediamtx\n"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IDENTITY=root mediamtx 0640", result.stdout)

    def test_offline_whitespace_after_equals_is_tolerated(self) -> None:
        # #448 F3a: a hand-edited `User= mediamtx` must derive non-root (the
        # incident direction), not silently degrade to root.
        result = run_identity(
            UBUNTU.read_text(encoding="utf-8"), BUS_FAIL, unit_files={"etc": UNIT_WHITESPACE}
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IDENTITY=root mediamtx 0640", result.stdout)

    def test_offline_symlinked_unit_is_refused(self) -> None:
        # Bounded decision: a symlinked unit file is NOT followed (fail-closed,
        # consistent with the renderer's regular-non-symlink discipline); the
        # refusal is explicit, never a guessed ownership.
        source = UBUNTU.read_text(encoding="utf-8")
        function = shell_function(source, "derive_relay_service_identity")
        with tempfile.TemporaryDirectory() as raw:
            tree = Path(raw)
            for kind, root_literal in sorted(
                UNIT_PATH_ROOTS.items(), key=lambda item: -len(item[1])
            ):
                assert f'"{root_literal}/$service_name"' in function
                function = function.replace(root_literal, str(tree / kind))
                (tree / kind).mkdir(parents=True, exist_ok=True)
            target = tree / "lib" / "real-unit"
            target.write_text(UNIT_MEDIAMTX, encoding="utf-8")
            link = tree / "etc" / "sea-speed-stream.service"
            link.symlink_to(target)
            stubs = BUS_FAIL + "\n"
            script = (
                f"{function}\n{stubs}\n"
                "service_name='sea-speed-stream.service'\n"
                'identity="$(derive_relay_service_identity)"\n'
                "rc=$?\n"
                'printf "RC=%s\\n" "$rc"\n'
                '[[ $rc -eq 0 ]] && printf "IDENTITY=%s\\n" "$identity"\n'
                'exit "$rc"\n'
            )
            result = subprocess.run(["bash", "-c", script, "_"], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RC=1", result.stdout)
        self.assertIn("refusing to install with guessed ownership", result.stderr)
        self.assertNotIn("IDENTITY=", result.stdout)

    def test_both_derivations_fail_closed(self) -> None:
        # No bus AND no readable unit file anywhere: explicit refusal (the
        # #447 contract, unchanged).
        result = run_identity(UBUNTU.read_text(encoding="utf-8"), BUS_FAIL)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RC=1", result.stdout)
        self.assertIn(
            "ERROR relay service identity could not be derived "
            "(systemctl unavailable and unit file unreadable); "
            "refusing to install with guessed ownership",
            result.stderr,
        )
        self.assertNotIn("IDENTITY=", result.stdout)

    def test_unit_file_group_unresolvable_fails_closed(self) -> None:
        # User derives from the on-disk unit file but no group anywhere: refuse.
        result = run_identity(
            UBUNTU.read_text(encoding="utf-8"), BUS_FAIL, unit_files={"etc": UNIT_NO_GROUP}
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RC=1", result.stdout)
        self.assertIn("cannot resolve relay service group", result.stderr)
        self.assertNotIn("IDENTITY=", result.stdout)


RELAY_CONFIG = """logLevel: info
authMethod: internal
authInternalUsers:
  - user: any
    pass:
    ips: ["127.0.0.1"]
    permissions:
      - action: api
rtsp: yes
rtspAddress: :8554
api: yes
apiAddress: "127.0.0.1:9997"
paths:
  cam1:
    source: rtsp://10.0.0.8:8554/cam1
    sourceOnDemand: yes
    rtspTransport: tcp
"""

READER_IP = "10.123.239.101"
PRIV_ADDR = "10.0.0.8:8554"


class ActivateFlowExecutedTwinTests(unittest.TestCase):
    """398-wave3: executed twins for the activate-block contract pins.

    The REAL camera-relay.sh bytes run (a) bare for the rootless status
    subcommand and (b) under an unprivileged user namespace for the
    root-gated prepare/activate flows, with systemctl stubbed on PATH and
    every mutable path inside a temp dir. Identity derivation, digest
    binding, the worker-stopped gate, backup/install/mv, the systemctl
    restart hand-off and the private-listener probe execute for real.
    """

    def _env_file(self, tmp: Path) -> Path:
        env_file = tmp / "worker.env"
        # Runtime-assembled, never a literal credential shape in this file.
        env_file.write_text("HLS_URL=rtsp://" + "cam_user:cam_key" + "@10.0.0.21/live\n", encoding="utf-8")
        env_file.chmod(0o600)
        return env_file

    def prepare_candidate(self, tmp: Path, private_address: str) -> tuple[str, str, Path]:
        config = tmp / "mediamtx.yml"
        config.write_text(RELAY_CONFIG, encoding="utf-8")
        result = relay_shell.run_shell(
            relay_shell.CAMERA_RELAY,
            [
                "prepare", "--config", str(config),
                "--private-rtsp-address", private_address,
                "--reader-ip", READER_IP,
                "--source-env-file", str(self._env_file(tmp)),
                "--state-root", str(tmp / "state"),
            ],
            tmp,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        digest = ""
        for line in result.stdout.splitlines():
            if line.startswith("CANDIDATE_SHA256="):
                digest = line.split("=", 1)[1]
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        candidate = tmp / "state" / "cam1-mediamtx.candidate.yml"
        self.assertTrue(candidate.exists())
        return digest, config.read_text(encoding="utf-8"), candidate

    def activate(self, tmp: Path, digest: str, **env: str) -> subprocess.CompletedProcess:
        return relay_shell.run_shell(
            relay_shell.CAMERA_RELAY,
            [
                "activate", "--config", str(tmp / "mediamtx.yml"),
                "--private-rtsp-address", PRIV_ADDR,
                "--reader-ip", READER_IP,
                "--expected-sha256", digest,
                "--state-root", str(tmp / "state"),
            ],
            tmp,
            env_extra=env or None,
        )

    def test_status_reports_without_root(self) -> None:
        # The status subcommand executes bare (no user namespace, no root):
        # evidence fields come from the stubbed systemctl, the private
        # listener is NOT_CHECKED without --private-rtsp-address.
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            result = relay_shell.run_shell(
                relay_shell.CAMERA_RELAY,
                ["status"],
                tmp,
                use_unshare=False,
                env_extra={
                    "SYSTEMCTL_ENABLED_TEXT": "enabled",
                    "SYSTEMCTL_ACTIVE_TEXT": "active",
                },
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("RELAY_ENABLED=enabled", result.stdout)
            self.assertIn("RELAY_ACTIVE=active", result.stdout)
            self.assertIn("AI_WORKER_ACTIVE=active", result.stdout)
            self.assertIn("PRIVATE_RELAY_TCP=NOT_CHECKED", result.stdout)

    def test_activate_digest_mismatch_refuses_before_any_mutation(self) -> None:
        # --expected-sha256 binds activation to the reviewed prepare digest.
        relay_shell.skip_without_user_namespace(self)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            digest, original, candidate = self.prepare_candidate(tmp, PRIV_ADDR)
            wrong = "0" * 64
            self.assertNotEqual(wrong, digest)
            result = self.activate(tmp, wrong)
            self.assertEqual(result.returncode, 7)
            self.assertIn("ERROR prepared candidate digest mismatch", result.stderr)
            self.assertNotIn("INSTALL_OWNER=", result.stdout)
            self.assertEqual((tmp / "mediamtx.yml").read_text(encoding="utf-8"), original)
            # state/ exists from prepare; "no mutation" means no backup was taken.
            self.assertFalse(list((tmp / "state" / "backups").glob("mediamtx.*.yml")))

    def test_activate_refuses_when_ai_worker_is_active(self) -> None:
        # Executed twin: the worker-stopped gate fires before the identity
        # derivation and any mutation.
        relay_shell.skip_without_user_namespace(self)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            digest, original, candidate = self.prepare_candidate(tmp, PRIV_ADDR)
            result = self.activate(
                tmp, digest, SYSTEMCTL_QUIET_ACTIVE_SERVICES="sea-speed-worker.service"
            )
            self.assertEqual(result.returncode, 8)
            self.assertIn("ERROR AI worker must remain stopped", result.stderr)
            self.assertNotIn("INSTALL_OWNER=", result.stdout)
            self.assertEqual((tmp / "mediamtx.yml").read_text(encoding="utf-8"), original)
            # state/ exists from prepare; "no mutation" means no backup was taken.
            self.assertFalse(list((tmp / "state" / "backups").glob("mediamtx.*.yml")))

    def test_activate_refuses_when_identity_cannot_be_derived_and_mutates_nothing(self) -> None:
        # Executed twin of the fail-closed ordering: the derivation runs
        # BEFORE any mutation, so an underivable identity exits 9 with the
        # explicit error, the live config is untouched and no backup exists.
        relay_shell.skip_without_user_namespace(self)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            digest, original, candidate = self.prepare_candidate(tmp, PRIV_ADDR)
            # Default stub: systemctl show returns an empty User and no
            # readable unit file exists anywhere in the sandbox image.
            result = self.activate(tmp, digest)
            self.assertEqual(result.returncode, 9)
            self.assertIn("refusing to install with guessed ownership", result.stderr)
            self.assertNotIn("INSTALL_OWNER=", result.stdout)
            self.assertNotIn("MODE=", result.stdout)
            self.assertEqual((tmp / "mediamtx.yml").read_text(encoding="utf-8"), original)
            # state/ exists from prepare; "no mutation" means no backup was taken.
            self.assertFalse(list((tmp / "state" / "backups").glob("mediamtx.*.yml")))

    def test_activate_restart_failure_preserves_backup_and_refuses_rollback(self) -> None:
        # Executed twin of the deploy-transaction contract: after the identity
        # is derived and evidenced, the candidate is backed up (0600), the
        # live config is replaced through .next, and a failed systemctl
        # restart refuses with the rollback warning while pointing at the
        # protected backup.
        relay_shell.skip_without_user_namespace(self)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            digest, original, candidate = self.prepare_candidate(tmp, PRIV_ADDR)
            log = tmp / "systemctl-calls.log"
            result = self.activate(
                tmp,
                digest,
                SYSTEMCTL_USER="root",
                SYSTEMCTL_GROUP="root",
                SYSTEMCTL_QUIET_ACTIVE_SERVICES="sea-speed-stream.service",
                SYSTEMCTL_LOG=str(log),
                SYSTEMCTL_RESTART_FAIL="yes",
            )
            self.assertEqual(result.returncode, 30)
            self.assertIn("INSTALL_OWNER=root:root", result.stdout)
            self.assertIn("MODE=0600", result.stdout)
            self.assertIn(
                "relay service restart failed; automatic rollback is not authorized",
                result.stderr,
            )
            self.assertIn("BACKUP=", result.stderr)
            backups = sorted((tmp / "state" / "backups").glob("mediamtx.*.yml"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)
            # The candidate replaced the live config (mv happened before the
            # restart), and exactly one restart reached systemctl.
            self.assertEqual(
                (tmp / "mediamtx.yml").read_text(encoding="utf-8"),
                candidate.read_text(encoding="utf-8"),
            )
            restarts = [
                line for line in log.read_text(encoding="utf-8").splitlines()
                if line.startswith("restart ")
            ]
            self.assertEqual(restarts, ["restart sea-speed-stream.service"])

    def test_activate_field_order_distinct_identity_fails_closed_at_install(self) -> None:
        # 398-wave3 review MED-2: executed twin of the retired #448 F2 caller
        # field-order pin (`read -r install_owner install_group install_mode`).
        # The identity fields are made DISTINCT (SYSTEMCTL_USER=nobody takes
        # the non-root derivation branch → identity "root nogroup 0640"), so
        # the real caller's order-sensitive evidence proves the destructure:
        # a swapped owner/group read flips INSTALL_OWNER=nogroup:root, a
        # misplaced mode flips MODE. The subsequent
        # `install -o root -g nogroup` fails closed in the single-uid
        # namespace (chown to the unmapped group is EINVAL) — observed
        # empirically — so the transaction dies before the mv: no activation,
        # live config untouched, and the root:root backup (installed first)
        # is preserved. Asserting the installed file's uid/gid for a distinct
        # group is impossible here (unmapped gid), so the order-sensitive
        # evidence plus fail-closed semantics is the strongest executed twin.
        relay_shell.skip_without_user_namespace(self)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            digest, original, candidate = self.prepare_candidate(tmp, PRIV_ADDR)
            result = self.activate(
                tmp,
                digest,
                SYSTEMCTL_USER="nobody",
                SYSTEMCTL_GROUP="nogroup",
                SYSTEMCTL_QUIET_ACTIVE_SERVICES="sea-speed-stream.service",
            )
            # Past the worker gate (8) and the derivation (9); the failure is
            # the candidate install itself (never reached restart's 30).
            self.assertNotIn(result.returncode, (0, 8, 9, 30), result.stdout + result.stderr)
            self.assertIn("INSTALL_OWNER=root:nogroup", result.stdout)
            self.assertIn("MODE=0640", result.stdout)
            self.assertNotIn("ACTIVATED_RELAY=YES", result.stdout)
            # The candidate install died before the mv: live config untouched.
            self.assertEqual((tmp / "mediamtx.yml").read_text(encoding="utf-8"), original)
            backups = sorted((tmp / "state" / "backups").glob("mediamtx.*.yml"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)

    def test_activate_full_happy_path_against_real_private_listener(self) -> None:
        # Executed twin of the success contract: digest verified, worker
        # stopped, identity derived and evidenced, backup taken, config
        # replaced, restart accepted, is-active quiet-passes, and the REAL
        # TCP probe reaches a listening private socket.
        relay_shell.skip_without_user_namespace(self)
        listener = relay_shell.bindable_private_listener()
        if listener is None:
            self.skipTest("no bindable RFC1918 address for a deterministic listener probe")
        address, sock = listener
        try:
            with tempfile.TemporaryDirectory() as raw:
                tmp = Path(raw)
                digest, original, candidate = self.prepare_candidate(tmp, address)
                log = tmp / "systemctl-calls.log"
                result = self.activate(
                    tmp,
                    digest,
                    SYSTEMCTL_USER="root",
                    SYSTEMCTL_GROUP="root",
                    SYSTEMCTL_QUIET_ACTIVE_SERVICES="sea-speed-stream.service",
                    SYSTEMCTL_LOG=str(log),
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("ACTIVATED_RELAY=YES", result.stdout)
                self.assertIn("PRIVATE_RELAY_TCP=PASS", result.stdout)
                self.assertIn("INSTALL_OWNER=root:root", result.stdout)
                self.assertIn("MODE=0600", result.stdout)
                self.assertIn("READER_AUTH_SCOPE=cam1-single-rfc1918-peer", result.stdout)
                self.assertIn("READER_AUTH_PERMISSION=read-only", result.stdout)
                self.assertIn("RELAY_ACTIVE=active", result.stdout)
                self.assertIn("AI_WORKER_ACTIVE=inactive", result.stdout)
                self.assertIn("AI_WORKER_STARTED=NO", result.stdout)
                self.assertIn("CAMERA_PLAYBACK_TESTED=NO", result.stdout)
                self.assertIn("SECRETS_DISPLAYED=NO", result.stdout)
                self.assertIn("BACKUP=", result.stdout)
                self.assertEqual(
                    (tmp / "mediamtx.yml").read_text(encoding="utf-8"),
                    candidate.read_text(encoding="utf-8"),
                )
        finally:
            sock.close()

    def test_prepare_refuses_systemd_auth_environment_override(self) -> None:
        # check_auth_environment_override executes: an MTX_AUTHMETHOD
        # systemd-environment override fails the transaction closed before
        # any candidate is rendered.
        relay_shell.skip_without_user_namespace(self)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            config = tmp / "mediamtx.yml"
            config.write_text(RELAY_CONFIG, encoding="utf-8")
            result = relay_shell.run_shell(
                relay_shell.CAMERA_RELAY,
                [
                    "prepare", "--config", str(config),
                    "--private-rtsp-address", PRIV_ADDR,
                    "--reader-ip", READER_IP,
                    "--source-env-file", str(self._env_file(tmp)),
                    "--state-root", str(tmp / "state"),
                ],
                tmp,
                env_extra={"SYSTEMCTL_ENVIRONMENT": "MTX_AUTHMETHOD=internal"},
            )
            self.assertEqual(result.returncode, 10)
            self.assertIn("relay authentication is overridden by systemd environment", result.stderr)
            self.assertFalse((tmp / "state" / "cam1-mediamtx.candidate.yml").exists())


class ActivateIdentityContractTests(unittest.TestCase):
    """Structural pins: fail-closed ordering, evidence, unchanged counts,
    offline productivity (#449), caller field order (#448 F2)."""

    def test_shell_is_valid_and_contracts_fail_closed_derivation(self) -> None:
        subprocess.run(["bash", "-n", str(UBUNTU)], check=True)
        source = UBUNTU.read_text(encoding="utf-8")
        # 398-wave3: the derivation-existence, exit-9 caller wiring, explicit
        # error and INSTALL_OWNER/MODE evidence pins were retired against the
        # executed twins in ActivateFlowExecutedTwinTests (the real script
        # bytes exit 9 / emit INSTALL_OWNER=.../MODE=... / refuse with the
        # exact error under the stubbed-systemctl user-namespace harness).
        # Kept below: the silent-fallback bans are SP policy pins.
        # The old silent fallback is gone (SP pin — the #447 failure mode
        # must never return; no executed twin can prove a permanent absence).
        self.assertNotIn('[[ -z "$service_user" || "$service_user" == "root" ]]', source)
        self.assertNotIn('install_group="root"', source)
        self.assertNotIn('install_mode="0600"', source)

    def test_activate_flow_unchanged_pins_hold(self) -> None:
        source = UBUNTU.read_text(encoding="utf-8")
        # AC-3: no new renderer invocations, digest/backup/restart discipline
        # unchanged. 398-wave3: the "--expected-sha256" / restart / rollback
        # pins retired against the executed activate twins (digest-mismatch
        # refusal, restart call logged, dead-listener rollback warning);
        # the cross-flow counts stay SP (structural invariant across all
        # three digest-emitting blocks; prepare/sanitize/remediate twins live
        # in the sibling suites).
        self.assertEqual(source.count("verify-reader-auth"), 5)
        self.assertEqual(source.count("CANDIDATE_SHA256=%s"), 3)
        self.assertEqual(source.count("MUTATIONS=PROTECTED_CANDIDATE_ONLY"), 3)

    def test_offline_branch_does_not_call_systemctl_cat(self) -> None:
        # #449 AC-1 (productivity): the bus-dependent `systemctl cat` is the
        # reason the #447 fallback never fired offline — the executable body
        # must not call it at all (comment lines are exempt: they document
        # the history).
        function = shell_function(UBUNTU.read_text(encoding="utf-8"), "derive_relay_service_identity")
        executable = [
            line for line in function.splitlines() if not line.lstrip().startswith("#")
        ]
        self.assertNotIn("systemctl cat", "\n".join(executable))

    def test_offline_branch_reads_standard_unit_paths_in_order(self) -> None:
        # 398-wave3: kept — /usr/lib precedence has no planted-unit executed
        # twin (the namespace cannot write /usr/lib), so this stays the only
        # guard for the third unit-path root.
        function = shell_function(UBUNTU.read_text(encoding="utf-8"), "derive_relay_service_identity")
        etc = function.index('"/etc/systemd/system/$service_name"')
        lib = function.index('"/lib/systemd/system/$service_name"')
        usrlib = function.index('"/usr/lib/systemd/system/$service_name"')
        self.assertLess(etc, lib)
        self.assertLess(lib, usrlib)

    # 398-wave3 retired source-text pins and their executed twins (same
    # commit, this file):
    # - the exact `read -r install_owner install_group install_mode <<<`
    #   caller line (#448 F2) →
    #   ActivateFlowExecutedTwinTests.
    #   test_activate_field_order_distinct_identity_fails_closed_at_install
    #   (the real caller destructures a distinct owner/group/mode identity
    #   and prints the order-sensitive evidence before the install);
    #   test_activate_full_happy_path_against_real_private_listener and
    #   .test_activate_restart_failure_preserves_backup_and_refuses_rollback
    #   additionally execute the derived-identity install end to end.
    # - the whitespace-tolerant capture regexes (#448 F3a) →
    #   test_offline_whitespace_after_equals_is_tolerated (executes the real
    #   derivation against `User= mediamtx` / `Group= mediamtx` fixtures).


if __name__ == "__main__":
    unittest.main()
