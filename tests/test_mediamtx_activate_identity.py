"""Issue #447: activate service-identity derivation must fail closed.

Incident (2026-10-10, on-box activate under docker-chroot): `systemctl show
-p User` returned empty ("Failed to connect to system scope bus") and the
activate block silently fell back to root:root 0600 instead of the service's
root:mediamtx 0640; mediamtx crash-looped on the installed config until the
operator hand-fixed ownership. The no-auto-rollback contract held, but the
permission derivation failed OPEN.

This battery pins the fail-closed, chroot-safe derivation:

- `derive_relay_service_identity` (extractable function): (1) `systemctl
  show` is definitive only when User is non-empty; (2) fallback parses the
  LAST `User=`/`Group=` assignment from `systemctl cat` output (offline-safe;
  systemd override semantics; User absent or empty means the unit runs as
  root); (3) BOTH failing returns nonzero with an explicit ERROR — the
  caller refuses to install with guessed ownership BEFORE any backup or
  install.
- The activate block evidences the derived identity
  (`INSTALL_OWNER=<owner>:<group>` + `MODE=<mode>`) before any mutation.
- The activate flow is otherwise unchanged (digest binding, backup, restart,
  probes, no auto-rollback); renderer invocation counts are unchanged.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UBUNTU = ROOT / "deploy/worker/ubuntu/camera-relay.sh"


def shell_function(source: str, name: str) -> str:
    start = source.index(f"{name}() {{")
    end = source.index("\n}\n\n", start) + 2
    return source[start:end]


def run_identity(source: str, systemctl_stub: str, id_stub: str = "") -> subprocess.CompletedProcess:
    """Execute the extracted derivation with stubbed systemctl/id."""
    function = shell_function(source, "derive_relay_service_identity")
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

# Chroot simulation: systemctl show hits the bus and fails; systemctl cat
# reads the unit file from disk.
BUS_FAIL_CAT_UNIT = (
    "systemctl() {\n"
    '  if [[ "$1" == show ]]; then echo "Failed to connect to system scope bus" >&2; return 1; fi\n'
    '  if [[ "$1" == cat ]]; then printf "# /etc/systemd/system/sea-speed-stream.service\\n[Service]\\nUser=mediamtx\\nGroup=mediamtx\\nExecStart=/usr/bin/mediamtx\\n"; return 0; fi\n'
    "  return 0\n"
    "}"
)

BUS_FAIL_CAT_UNIT_NO_USER = (
    "systemctl() {\n"
    '  if [[ "$1" == show ]]; then echo "Failed to connect to system scope bus" >&2; return 1; fi\n'
    '  if [[ "$1" == cat ]]; then printf "# /etc/systemd/system/sea-speed-stream.service\\n[Service]\\nExecStart=/usr/bin/mediamtx\\n"; return 0; fi\n'
    "  return 0\n"
    "}"
)

BUS_FAIL_CAT_UNIT_NO_GROUP = (
    "systemctl() {\n"
    '  if [[ "$1" == show ]]; then echo "Failed to connect to system scope bus" >&2; return 1; fi\n'
    '  if [[ "$1" == cat ]]; then printf "# /etc/systemd/system/sea-speed-stream.service\\n[Service]\\nUser=mediamtx\\n"; return 0; fi\n'
    "  return 0\n"
    "}"
)

ID_MEDIAMTX = 'id() { printf "mediamtx\\n"; }'

# Drop-in override: the LAST User=/Group= assignment wins.
BUS_FAIL_CAT_UNIT_WITH_OVERRIDE = (
    "systemctl() {\n"
    '  if [[ "$1" == show ]]; then echo "Failed to connect to system scope bus" >&2; return 1; fi\n'
    '  if [[ "$1" == cat ]]; then printf "# /etc/systemd/system/sea-speed-stream.service\\n[Service]\\nUser=legacyuser\\nGroup=legacygrp\\n\\n# /etc/systemd/system/sea-speed-stream.service.d/override.conf\\n[Service]\\nUser=mediamtx\\nGroup=mediamtx\\n"; return 0; fi\n'
    "  return 0\n"
    "}"
)

# Both derivations fail: show fails AND cat returns nothing.
BUS_FAIL_CAT_FAIL = (
    "systemctl() {\n"
    '  if [[ "$1" == show ]]; then echo "Failed to connect to system scope bus" >&2; return 1; fi\n'
    '  echo "System has not been booted with systemd" >&2\n'
    "  return 1\n"
    "}"
)


class ActivateIdentityDerivationTests(unittest.TestCase):
    """derive_relay_service_identity: show definitive, unit-file fallback,
    fail closed when both are unavailable."""

    def test_show_user_mediamtx_derives_group_from_show(self) -> None:
        result = run_identity(UBUNTU.read_text(encoding="utf-8"), SHOW_MEDIAMTX)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RC=0", result.stdout)
        self.assertIn("IDENTITY=root mediamtx 0640", result.stdout)

    def test_show_explicit_root_keeps_root_root_0600(self) -> None:
        result = run_identity(UBUNTU.read_text(encoding="utf-8"), SHOW_ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IDENTITY=root root 0600", result.stdout)

    def test_chroot_show_unavailable_falls_back_to_unit_file(self) -> None:
        # The #447 incident: systemctl show returns empty under chroot; the
        # unit file on disk is authoritative.
        result = run_identity(UBUNTU.read_text(encoding="utf-8"), BUS_FAIL_CAT_UNIT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IDENTITY=root mediamtx 0640", result.stdout)

    def test_chroot_unit_without_user_means_root(self) -> None:
        result = run_identity(UBUNTU.read_text(encoding="utf-8"), BUS_FAIL_CAT_UNIT_NO_USER)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IDENTITY=root root 0600", result.stdout)

    def test_chroot_unit_group_missing_resolves_via_id(self) -> None:
        result = run_identity(UBUNTU.read_text(encoding="utf-8"), BUS_FAIL_CAT_UNIT_NO_GROUP, ID_MEDIAMTX)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IDENTITY=root mediamtx 0640", result.stdout)

    def test_unit_file_override_last_assignment_wins(self) -> None:
        result = run_identity(UBUNTU.read_text(encoding="utf-8"), BUS_FAIL_CAT_UNIT_WITH_OVERRIDE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("IDENTITY=root mediamtx 0640", result.stdout)

    def test_both_derivations_fail_closed(self) -> None:
        result = run_identity(UBUNTU.read_text(encoding="utf-8"), BUS_FAIL_CAT_FAIL)
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
        # User derives from the unit file but no group anywhere: refuse.
        result = run_identity(UBUNTU.read_text(encoding="utf-8"), BUS_FAIL_CAT_UNIT_NO_GROUP)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RC=1", result.stdout)
        self.assertIn("cannot resolve relay service group", result.stderr)
        self.assertNotIn("IDENTITY=", result.stdout)


class ActivateIdentityContractTests(unittest.TestCase):
    """Structural pins: fail-closed ordering, evidence, unchanged counts."""

    def test_shell_is_valid_and_contracts_fail_closed_derivation(self) -> None:
        subprocess.run(["bash", "-n", str(UBUNTU)], check=True)
        source = UBUNTU.read_text(encoding="utf-8")

        # The extractable derivation function exists.
        self.assertIn("derive_relay_service_identity() {", source)
        # The activate block calls it and refuses on failure (exit 9).
        self.assertIn('identity="$(derive_relay_service_identity)" || exit 9', source)
        # The old silent fallback is gone.
        self.assertNotIn('[[ -z "$service_user" || "$service_user" == "root" ]]', source)
        self.assertNotIn('install_group="root"', source)
        self.assertNotIn('install_mode="0600"', source)
        # Explicit fail-closed error before any install.
        self.assertIn(
            "refusing to install with guessed ownership",
            source,
        )
        # AC-2: expected ownership/mode evidenced on the install path.
        self.assertIn("INSTALL_OWNER=%s:%s", source)
        self.assertIn("MODE=%s", source)

    def test_identity_derivation_precedes_any_mutation(self) -> None:
        source = UBUNTU.read_text(encoding="utf-8")
        derivation = source.index('identity="$(derive_relay_service_identity)"')
        backup = source.index('backup="$backup_root/')
        install = source.index('install -o "$install_owner"')
        self.assertLess(derivation, backup)
        self.assertLess(derivation, install)

    def test_activate_flow_unchanged_pins_hold(self) -> None:
        source = UBUNTU.read_text(encoding="utf-8")
        # AC-3: no new renderer invocations, digest/backup/restart discipline
        # unchanged.
        self.assertEqual(source.count("verify-reader-auth"), 5)
        self.assertEqual(source.count("CANDIDATE_SHA256=%s"), 3)
        self.assertEqual(source.count("MUTATIONS=PROTECTED_CANDIDATE_ONLY"), 3)
        self.assertIn("automatic rollback is not authorized", source)
        self.assertIn("--expected-sha256", source)
        self.assertIn('systemctl restart "$service_name"', source)


if __name__ == "__main__":
    unittest.main()
