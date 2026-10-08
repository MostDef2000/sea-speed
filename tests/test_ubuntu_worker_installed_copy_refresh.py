from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Module-wide updater path: every class in this module (structural and
# executed) tests the script this constant points at. SEA_SPEED_406_UPDATER_PATH
# overrides it for RED-vs-base and RED-vs-pre-repair runs.
UPDATER = Path(
    os.environ.get("SEA_SPEED_406_UPDATER_PATH", str(ROOT / "deploy" / "worker" / "ubuntu" / "update-exact.sh"))
)
BASH = shutil.which("bash") or "/bin/bash"

# Release-tree source bytes (v2) and stale installed bytes (v1) used by the
# executed scenarios. Built at runtime; never secret material.
RELEASE_BYTES = {
    "script": "release-watchdog-v2\n",
    "unit": "release-unit-v2\n",
    "timer": "release-timer-v2\n",
}
STALE_BYTES = {
    "script": "stale-watchdog-v1\n",
    "unit": "stale-unit-v1\n",
    "timer": "stale-timer-v1\n",
}


class UbuntuWorkerInstalledCopyRefreshContractTests(unittest.TestCase):
    """Structural contract for the #406 inventory-driven installed-copy refresh.

    The stale-copy class (audit 2026-10-07): installed copies of release-derived
    scripts outside the release tree are not deploy-managed units, so without an
    in-transaction refresh production can run arbitrarily old code while fixed
    releases sit in the release tree. Since #406 the delivery is
    refresh_installed_copies(): a declared inventory of
    release-source|installed-path|mode entries, refreshed transactionally.
    """

    def setUp(self) -> None: self.source = UPDATER.read_text(encoding="utf-8")

    def test_shell_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(UPDATER)], check=True)

    def test_inventory_covers_every_release_derived_installed_copy(self) -> None:
        # Full installed-copy inventory (recon, issue #406): the watchdog trio is
        # the complete set of release-derived files installed outside the release
        # tree; deploy-managed units are swapped by install-systemd.sh and every
        # other deploy/worker/ubuntu component executes in place from the release
        # tree, so nothing else can go stale.
        for marker in (
            "local -a installed_copy_inventory=(",
            '"$watchdog_src|$watchdog_dst|0755"',
            '"$watchdog_unit_src|$watchdog_unit_dst|0644"',
            '"$watchdog_timer_src|$watchdog_timer_dst|0644"',
        ):
            self.assertIn(marker, self.source)

    def test_refresh_runs_inside_deploy_transaction_before_control_restart(self) -> None:
        self.assertIn(
            'refresh_installed_copies || abort_activation "installed copy refresh failed"', self.source
        )
        self.assertLess(
            self.source.index("capture_watchdog_prestate\n"),
            self.source.index('refresh_installed_copies || abort_activation "installed copy refresh failed"'),
        )
        self.assertLess(
            self.source.index('refresh_installed_copies || abort_activation "installed copy refresh failed"'),
            self.source.index("systemctl daemon-reload || abort_activation \"watchdog daemon-reload failed\""),
        )
        self.assertLess(
            self.source.index("systemctl daemon-reload || abort_activation \"watchdog daemon-reload failed\""),
            self.source.index('if ! systemctl restart "$control_service_name"'),
        )

    def test_prior_bytes_backed_up_before_first_mutation(self) -> None:
        body = self._refresh_body()
        self.assertIn('installed_copy_backup="$(mktemp "$updater_root/installed-copy-backup.XXXXXX")" || return 1', body)
        self.assertIn('install -o root -g root -m 0600 "$dst" "$installed_copy_backup" || return 1', body)
        self.assertLess(
            body.index('install -o root -g root -m 0600 "$dst" "$installed_copy_backup"'),
            body.index('install -o root -g root -m "$mode" "$src" "$dst"'),
        )

    def test_hash_parity_is_verified_after_every_refresh(self) -> None:
        body = self._refresh_body()
        for marker in (
            'src_sha="$(sha256sum "$src")"',
            'dst_sha="$(sha256sum "$dst")"',
            'if [[ -z "$src_sha" || "$src_sha" != "$dst_sha" ]]; then',
            'install -o root -g root -m "$mode" "$installed_copy_backup" "$dst" || return 1',
        ):
            self.assertIn(marker, body)

    def test_leftover_is_reported_and_never_deleted(self) -> None:
        # Bounded behavior: a release tree that lacks the source for an existing
        # installed copy (installed-only leftover) is reported and left untouched;
        # the transaction must not delete installed artifacts.
        body = self._refresh_body()
        self.assertIn("INSTALLED_COPY_LEFTOVER", body)
        self.assertIn("action=reported_not_deleted", body)
        self.assertNotIn('rm -f "$dst"', body)

    def test_fresh_install_is_idempotent(self) -> None:
        # A missing installed copy is a fresh install from the release: the
        # refresh path must not require a pre-existing installed copy.
        body = self._refresh_body()
        self.assertIn('if [[ -f "$dst" ]]; then', body)
        self.assertIn('if ! install -o root -g root -m "$mode" "$src" "$dst"; then', body)

    def test_required_commands_include_sha256sum(self) -> None:
        self.assertIn("for command_name in git python3 ffmpeg tar flock stat install grep mktemp mv sha256sum; do", self.source)

    def test_cleanup_covers_installed_copy_backup(self) -> None:
        cleanup = self.source[self.source.index("cleanup() {"):self.source.index("trap cleanup EXIT")]
        self.assertIn("installed_copy_backup", cleanup)

    def _refresh_body(self) -> str:
        start = self.source.index("refresh_installed_copies() {")
        end = self.source.index("\n}", start)
        return self.source[start:end]


MKTEMP_STUB = r"""#!/usr/bin/env bash
# Behaves like real mktemp (creates the file, prints its path) except on the
# Nth call (MKTEMP_FAIL_ON_CALL, 1-based), which fails like a full disk.
count_file="${MKTEMP_COUNT_FILE:?}"
n="$(cat "$count_file" 2>/dev/null || echo 0)"
n=$((n + 1))
printf '%s' "$n" > "$count_file"
if [[ -n "${MKTEMP_FAIL_ON_CALL:-}" && "$n" == "$MKTEMP_FAIL_ON_CALL" ]]; then
  echo "mktemp: simulated allocation failure" >&2
  exit 1
fi
template="${1:?}"
out="${template//XXXXXX/$$-$n}"
: > "$out"
printf '%s\n' "$out"
"""

INSTALL_COPY_STUB = r"""#!/usr/bin/env bash
# Records every invocation and copies source bytes to the destination like the
# real install(1) (flags -m/-o/-g are accepted and ignored: the sandbox runs
# unprivileged). Fails on the Nth call when INSTALL_FAIL_ON_CALL is set, and
# writes corrupted bytes on the Nth call when INSTALL_CORRUPT_ON_CALL is set
# (1-based) to simulate a torn/poisoned refresh without a real I/O fault.
printf '%s\n' "install $*" >> "$INSTALL_LOG"
count_file="${INSTALL_COUNT_FILE:?}"
n="$(cat "$count_file" 2>/dev/null || echo 0)"
n=$((n + 1))
printf '%s' "$n" > "$count_file"
if [[ -n "${INSTALL_FAIL_ON_CALL:-}" && "$n" == "$INSTALL_FAIL_ON_CALL" ]]; then
  echo "install: simulated failure" >&2
  exit 1
fi
paths=()
skip_next=0
for arg in "$@"; do
  if [[ "$skip_next" == 1 ]]; then skip_next=0; continue; fi
  case "$arg" in
    -m|-o|-g) skip_next=1 ;;
    -*) ;;
    *) paths+=("$arg") ;;
  esac
done
src="${paths[0]}"
dst="${paths[1]}"
if [[ -n "${INSTALL_CORRUPT_ON_CALL:-}" && "$n" == "$INSTALL_CORRUPT_ON_CALL" ]]; then
  printf 'corrupted-payload\n' > "$dst"
  exit 0
fi
cat "$src" > "$dst"
exit 0
"""


class UbuntuWorkerInstalledCopyRefreshExecutedTests(unittest.TestCase):
    """Executed fault-path coverage for refresh_installed_copies() (issue #406).

    The function is extracted from the script text and executed in a sandbox
    bash process (no root, no systemd): stub executables for mktemp and install
    are placed first on PATH (sha256sum resolves to the real coreutils binary);
    the ``abort_activation`` helper is a harness stub defined AFTER the extracted
    source (bash resolves functions at call time) that records the reason and
    exits 99. The updater script path is overridden module-wide through
    SEA_SPEED_406_UPDATER_PATH (see UPDATER) for RED-vs-base runs.
    """

    def setUp(self) -> None:
        self.updater_path = UPDATER
        self.source = UPDATER.read_text(encoding="utf-8")

    def _extract_function(self, name: str) -> str:
        start = self.source.index(f"{name}() {{")
        lines = self.source[start:].splitlines(keepends=True)
        body = [lines[0]]
        for line in lines[1:]:
            body.append(line)
            if line.rstrip("\n") == "}":
                break
        else:
            self.fail(f"closing brace of {name} not found in {self.updater_path}")
        return "".join(body)

    def _make_work(self, name: str) -> Path:
        work = Path(tempfile.mkdtemp(prefix=f"sea-speed-406-{name}."))
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        return work

    def _release_sources(self, work: Path, omit_script: bool = False) -> dict:
        src_dir = work / "release" / "source" / "deploy" / "worker" / "ubuntu"
        src_dir.mkdir(parents=True)
        sources = {
            "script": src_dir / "camera1-h264-freshness-watchdog.py",
            "unit": src_dir / "sea-speed-camera1-h264-freshness.service",
            "timer": src_dir / "sea-speed-camera1-h264-freshness.timer",
        }
        for key, path in sources.items():
            if omit_script and key == "script":
                continue
            path.write_text(RELEASE_BYTES[key], encoding="utf-8")
        return sources

    def _installed_paths(self, work: Path) -> dict:
        return {
            "script": work / "usr-local-sbin" / "sea-speed-camera1-h264-freshness-watchdog",
            "unit": work / "systemd" / "sea-speed-camera1-h264-freshness.service",
            "timer": work / "systemd" / "sea-speed-camera1-h264-freshness.timer",
        }

    def _run_refresh(self, work: Path, sources: dict, installed: dict, stub_env: dict) -> subprocess.CompletedProcess:
        bin_dir = work / "bin"
        bin_dir.mkdir(exist_ok=True)
        for name, stub_source in (("mktemp", MKTEMP_STUB), ("install", INSTALL_COPY_STUB)):
            stub = bin_dir / name
            stub.write_text(stub_source, encoding="utf-8")
            os.chmod(stub, 0o755)
        calls_log = work / "calls.log"
        install_log = work / "install.log"
        mktemp_count = work / "mktemp.count"
        install_count = work / "install.count"
        for path in (calls_log, install_log, mktemp_count, install_count):
            path.write_text("", encoding="utf-8")
        updater_root = work / "updater"
        updater_root.mkdir(exist_ok=True)
        globals_block = (
            f'updater_root="{updater_root}"\n'
            f'watchdog_src="{sources["script"]}"\n'
            f'watchdog_dst="{installed["script"]}"\n'
            f'watchdog_unit_src="{sources["unit"]}"\n'
            f'watchdog_unit_dst="{installed["unit"]}"\n'
            f'watchdog_timer_src="{sources["timer"]}"\n'
            f'watchdog_timer_dst="{installed["timer"]}"\n'
            'installed_copy_backup=""\n'
        )
        harness = (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f'export PATH="{bin_dir}:/usr/bin:/bin"\n'
            f"{self._extract_function('refresh_installed_copies')}\n"
            "abort_activation() {\n"
            '  printf \'%s\\n\' "ABORT:$1" >> "$CALLS_LOG"\n'
            "  exit 99\n"
            "}\n"
            f"{globals_block}\n"
            # Mirror the production transaction wiring exactly: the refresh
            # failure is routed through abort_activation (stub -> exit 99), not
            # through a bare set -e exit.
            'refresh_installed_copies || abort_activation "installed copy refresh failed"\n'
        )
        script = work / "harness.sh"
        script.write_text(harness, encoding="utf-8")
        env = {
            **os.environ,
            "CALLS_LOG": str(calls_log),
            "INSTALL_LOG": str(install_log),
            "MKTEMP_COUNT_FILE": str(mktemp_count),
            "INSTALL_COUNT_FILE": str(install_count),
            **stub_env,
        }
        self.calls_log = calls_log
        self.install_log = install_log
        return subprocess.run([BASH, str(script)], capture_output=True, text=True, env=env)

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_stale_installed_copies_are_refreshed_to_release_bytes(self) -> None:
        # (a): a stale installed copy is detected and refreshed to the exact
        # release bytes by the transaction, with post-refresh SHA-256 parity for
        # the whole inventory.
        work = self._make_work("stale-refreshed")
        sources = self._release_sources(work)
        installed = self._installed_paths(work)
        for key, path in installed.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(STALE_BYTES[key], encoding="utf-8")
        proc = self._run_refresh(work, sources, installed, {})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("ABORT:", self.calls_log.read_text(encoding="utf-8"))
        for key, path in installed.items():
            self.assertEqual(path.read_text(encoding="utf-8"), RELEASE_BYTES[key])
            self.assertEqual(self._sha256(path), self._sha256(sources[key]))
        for key in ("script", "unit", "timer"):
            self.assertIn(
                f"INSTALLED_COPY_REFRESHED installed_path={installed[key]}",
                proc.stderr,
            )

    def test_install_failure_fails_closed_and_restores_prior_bytes(self) -> None:
        # (b) refresh failure -> fail-closed abort; the prior installed bytes are
        # restored from the backup and the remaining inventory is left untouched.
        work = self._make_work("install-failure")
        sources = self._release_sources(work)
        installed = self._installed_paths(work)
        for key, path in installed.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(STALE_BYTES[key], encoding="utf-8")
        # Entry 1 (script) backup=install call 1, refresh install=call 2.
        proc = self._run_refresh(work, sources, installed, {"INSTALL_FAIL_ON_CALL": "2"})
        self.assertEqual(proc.returncode, 99, proc.stderr)
        self.assertIn("ABORT:installed copy refresh failed", self.calls_log.read_text(encoding="utf-8"))
        self.assertEqual(installed["script"].read_text(encoding="utf-8"), STALE_BYTES["script"])
        self.assertNotEqual(installed["script"].read_text(encoding="utf-8"), RELEASE_BYTES["script"])
        self.assertEqual(installed["unit"].read_text(encoding="utf-8"), STALE_BYTES["unit"])
        self.assertEqual(installed["timer"].read_text(encoding="utf-8"), STALE_BYTES["timer"])

    def test_hash_mismatch_fails_closed_and_restores_prior_bytes(self) -> None:
        # (b) verification failure (torn/poisoned refresh install) -> SHA-256
        # parity gate detects it, restores the prior bytes from the backup and
        # the caller fails the activation closed.
        work = self._make_work("hash-mismatch")
        sources = self._release_sources(work)
        installed = self._installed_paths(work)
        for key, path in installed.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(STALE_BYTES[key], encoding="utf-8")
        proc = self._run_refresh(work, sources, installed, {"INSTALL_CORRUPT_ON_CALL": "2"})
        self.assertEqual(proc.returncode, 99, proc.stderr)
        self.assertIn("ABORT:installed copy refresh failed", self.calls_log.read_text(encoding="utf-8"))
        self.assertEqual(installed["script"].read_text(encoding="utf-8"), STALE_BYTES["script"])
        for key in ("unit", "timer"):
            self.assertEqual(installed[key].read_text(encoding="utf-8"), STALE_BYTES[key])

    def test_fresh_host_installs_every_inventory_entry_from_release(self) -> None:
        # Idempotent for fresh installs: a missing installed copy is installed
        # from the release (no backup step, no abort).
        work = self._make_work("fresh-install")
        sources = self._release_sources(work)
        installed = self._installed_paths(work)
        installed["script"].parent.mkdir(parents=True, exist_ok=True)
        installed["unit"].parent.mkdir(parents=True, exist_ok=True)
        proc = self._run_refresh(work, sources, installed, {})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("ABORT:", self.calls_log.read_text(encoding="utf-8"))
        for key, path in installed.items():
            self.assertEqual(path.read_text(encoding="utf-8"), RELEASE_BYTES[key])
            self.assertEqual(self._sha256(path), self._sha256(sources[key]))
        recorded = self.install_log.read_text(encoding="utf-8")
        # Fresh install: no prior bytes exist, so no 0600 backup install ran.
        self.assertNotIn("-m 0600", recorded)
        for key in ("script", "unit", "timer"):
            self.assertIn(f"INSTALLED_COPY_REFRESHED installed_path={installed[key]}", proc.stderr)

    def test_second_run_is_byte_identical_idempotent(self) -> None:
        # (d) idempotency: a second run over a freshly refreshed host leaves every
        # installed copy byte-identical (same SHA-256) and does not abort.
        work = self._make_work("idempotent")
        sources = self._release_sources(work)
        installed = self._installed_paths(work)
        installed["script"].parent.mkdir(parents=True, exist_ok=True)
        installed["unit"].parent.mkdir(parents=True, exist_ok=True)
        first = self._run_refresh(work, sources, installed, {})
        self.assertEqual(first.returncode, 0, first.stderr)
        hashes_after_first = {key: self._sha256(path) for key, path in installed.items()}
        second = self._run_refresh(work, sources, installed, {})
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotIn("ABORT:", self.calls_log.read_text(encoding="utf-8"))
        for key, path in installed.items():
            self.assertEqual(self._sha256(path), hashes_after_first[key])
            self.assertEqual(path.read_text(encoding="utf-8"), RELEASE_BYTES[key])

    def test_release_tree_lacking_source_reports_leftover_without_deletion(self) -> None:
        # Installed-only leftover: the release tree lacks the legacy source, the
        # installed copy is reported and NOT deleted, and the transaction does not
        # fail (bounded behavior); the other inventory entries still refresh.
        work = self._make_work("leftover")
        sources = self._release_sources(work, omit_script=True)
        installed = self._installed_paths(work)
        for key, path in installed.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(STALE_BYTES[key], encoding="utf-8")
        proc = self._run_refresh(work, sources, installed, {})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("ABORT:", self.calls_log.read_text(encoding="utf-8"))
        self.assertEqual(installed["script"].read_text(encoding="utf-8"), STALE_BYTES["script"])
        self.assertIn(f"INSTALLED_COPY_LEFTOVER installed_path={installed['script']}", proc.stderr)
        self.assertIn("action=reported_not_deleted", proc.stderr)
        for key in ("unit", "timer"):
            self.assertEqual(installed[key].read_text(encoding="utf-8"), RELEASE_BYTES[key])
            self.assertEqual(self._sha256(installed[key]), self._sha256(sources[key]))
        self.assertNotIn(f"INSTALLED_COPY_REFRESHED installed_path={installed['script']}", proc.stderr)

    def test_backup_mktemp_failure_aborts_before_any_mutation(self) -> None:
        # Fail-closed before mutation: a backup allocation failure aborts before
        # any installed copy is touched.
        work = self._make_work("mktemp-failure")
        sources = self._release_sources(work)
        installed = self._installed_paths(work)
        for key, path in installed.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(STALE_BYTES[key], encoding="utf-8")
        proc = self._run_refresh(work, sources, installed, {"MKTEMP_FAIL_ON_CALL": "1"})
        self.assertEqual(proc.returncode, 99, proc.stderr)
        self.assertIn("ABORT:installed copy refresh failed", self.calls_log.read_text(encoding="utf-8"))
        self.assertEqual(self.install_log.read_text(encoding="utf-8"), "")
        for key, path in installed.items():
            self.assertEqual(path.read_text(encoding="utf-8"), STALE_BYTES[key])

    def test_post_transaction_hash_parity_holds_for_whole_inventory(self) -> None:
        # (c) explicit whole-inventory parity assertion after a successful run,
        # including a mixed host where only some copies were stale.
        work = self._make_work("parity")
        sources = self._release_sources(work)
        installed = self._installed_paths(work)
        installed["script"].parent.mkdir(parents=True, exist_ok=True)
        installed["unit"].parent.mkdir(parents=True, exist_ok=True)
        installed["timer"].parent.mkdir(parents=True, exist_ok=True)
        installed["script"].write_text(STALE_BYTES["script"], encoding="utf-8")
        installed["unit"].write_text(RELEASE_BYTES["unit"], encoding="utf-8")
        installed["timer"].write_text(RELEASE_BYTES["timer"], encoding="utf-8")
        proc = self._run_refresh(work, sources, installed, {})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for key in ("script", "unit", "timer"):
            self.assertEqual(
                self._sha256(installed[key]),
                self._sha256(sources[key]),
                f"post-transaction hash parity broken for {key}",
            )


if __name__ == "__main__":
    unittest.main()
