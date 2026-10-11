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
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
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


class ActivateIdentityContractTests(unittest.TestCase):
    """Structural pins: fail-closed ordering, evidence, unchanged counts,
    offline productivity (#449), caller field order (#448 F2)."""

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
        function = shell_function(UBUNTU.read_text(encoding="utf-8"), "derive_relay_service_identity")
        etc = function.index('"/etc/systemd/system/$service_name"')
        lib = function.index('"/lib/systemd/system/$service_name"')
        usrlib = function.index('"/usr/lib/systemd/system/$service_name"')
        self.assertLess(etc, lib)
        self.assertLess(lib, usrlib)

    def test_caller_read_field_order_is_pinned(self) -> None:
        # #448 F2: a field-swap regression in the caller would be
        # transcript-visible but suite-invisible; pin the exact line.
        source = UBUNTU.read_text(encoding="utf-8")
        self.assertIn('read -r install_owner install_group install_mode <<< "$identity"', source)

    def test_whitespace_tolerant_captures_are_pinned(self) -> None:
        # #448 F3a: optional whitespace after `=` in both captures.
        function = shell_function(UBUNTU.read_text(encoding="utf-8"), "derive_relay_service_identity")
        self.assertIn("User=[[:space:]]*([^[:space:]].*)$", function)
        self.assertIn("Group=[[:space:]]*([^[:space:]].*)$", function)


if __name__ == "__main__":
    unittest.main()
