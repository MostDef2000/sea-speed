from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Module-wide updater path: every class in this module (structural and
# executed) tests the script this constant points at. SEA_SPEED_412_UPDATER_PATH
# overrides it for RED-vs-base and RED-vs-pre-repair runs.
UPDATER = Path(
    os.environ.get("SEA_SPEED_412_UPDATER_PATH", str(ROOT / "deploy" / "worker" / "ubuntu" / "update-exact.sh"))
)
BASH = shutil.which("bash") or "/bin/bash"


class UbuntuWorkerExactUpdaterTests(unittest.TestCase):
    def setUp(self) -> None: self.source = UPDATER.read_text(encoding="utf-8")

    def test_shell_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(UPDATER)], check=True)

    def test_exact_main_quality_and_shared_runtime_gates_remain(self) -> None:
        for marker in (
            "origin main:refs/remotes/origin/main", "merge-base --is-ancestor", "verify_quality_status.py",
            "--workflow-file quality-integration.yml", "runtime_id_file=", "RUNTIME_BOUND source_commit=",
            "quality-approved", "quality_check=quality-integration", "active-source-commit",
        ):
            self.assertIn(marker, self.source)
        self.assertNotIn("-m pip install", self.source)
        self.assertNotIn("download.pytorch.org", self.source)

    def test_water_and_road_desired_states_are_independent(self) -> None:
        for marker in (
            'desired_state_file="$install_root/shared/runtime/operator-desired-state"',
            'road_desired_state_file="$install_root/shared/road-runtime/operator-desired-state"',
            'desired_state="running"', 'road_desired_state="running"',
            'ERROR operator desired state is invalid', 'ERROR road operator desired state is invalid',
            'if [[ "$desired_state" == "stopped" ]]',
            'if [[ "$road_desired_state" == "stopped" ]]',
        ):
            self.assertIn(marker, self.source)
        self.assertIn('systemctl stop "$service_name"', self.source)
        self.assertIn('systemctl stop "$road_service_name"', self.source)
        self.assertIn('systemctl restart "$service_name"', self.source)
        self.assertIn('systemctl restart "$road_service_name"', self.source)

    def test_road_desired_state_controls_runtime_gate(self) -> None:
        self.assertIn('if [[ "$road_configured" == true && "$road_desired_state" == "running" ]]', self.source)
        self.assertIn("ROAD_RUNTIME_GATE frame_and_state_progression=PASS", self.source)
        self.assertIn("ROAD_RUNTIME_GATE skipped_reason=operator_desired_stopped", self.source)
        self.assertIn("ROAD_SERVICE_STOPPED", self.source)
        self.assertIn("ROAD_SERVICE_ACTIVE", self.source)

    def test_road_topology_is_backup_bound_and_runtime_gated(self) -> None:
        for marker in (
            'road_service_name="sea-speed-road-worker.service"', "road-unit-backup.XXXXXX",
            "restore_previous_road()", "road-worker-heartbeat.json", "ROAD_RUNTIME_GATE frame_and_state_progression=PASS",
            "road worker unit does not reference requested runtime ID",
        ):
            self.assertIn(marker, self.source)

    def test_pre_activation_state_validation_is_independent(self) -> None:
        self.assertIn("desired running worker is not active before activation", self.source)
        self.assertIn("desired stopped worker is unexpectedly active before activation", self.source)
        self.assertIn("desired running road worker is not active before activation", self.source)
        self.assertIn("desired stopped road worker is unexpectedly active before activation", self.source)

    def test_cleanup_covers_main_road_control_and_marker(self) -> None:
        cleanup = self.source[self.source.index("cleanup() {"):self.source.index("trap cleanup EXIT")]
        for marker in ("staging_root", "unit_backup", "road_unit_backup", "control_unit_backup", "marker_tmp"):
            self.assertIn(marker, cleanup)
        self.assertIn("return \"$status\"", cleanup)

    def test_failure_restores_previous_release_and_both_service_topologies(self) -> None:
        for marker in ("restore_previous()", "restore_previous_road()", "restore_previous_control()", "ACTIVATION_ABORTED", "ACTIVE_MARKER_UNCHANGED"):
            self.assertIn(marker, self.source)

    def test_watchdog_copy_is_refreshed_from_release_source(self) -> None:
        # Deferred from #384 / tracked in #389: the watchdog is not one of the three
        # deploy-managed units, so its installed copy must be refreshed from the exact
        # release source during activation to avoid a stale copy across deploys.
        # Since #406 the delivery is the inventory-driven refresh_installed_copies()
        # transaction; the watchdog trio is its declared inventory.
        for marker in (
            'watchdog_src="$release_root/source/deploy/worker/ubuntu/camera1-h264-freshness-watchdog.py"',
            'watchdog_dst="/usr/local/sbin/sea-speed-camera1-h264-freshness-watchdog"',
            'abort_activation "watchdog refresh source missing from release"',
            'refresh_installed_copies || abort_activation "installed copy refresh failed"',
            'abort_activation "watchdog timer enable failed"',
        ):
            self.assertIn(marker, self.source)


class UbuntuWorkerWatchdogTransactionalRefreshTests(unittest.TestCase):
    # Issue #412: the watchdog refresh step is transactional — the pre-state is
    # captured before the first watchdog mutation, every activation abort after
    # the refresh started restores that captured pre-state, and the timer
    # enablement is reapplied from the captured state instead of being forced.
    def setUp(self) -> None: self.source = UPDATER.read_text(encoding="utf-8")

    def test_shell_syntax(self) -> None:
        subprocess.run(["bash", "-n", str(UPDATER)], check=True)

    def test_unconditional_timer_enable_is_removed(self) -> None:
        self.assertNotIn("systemctl enable --now sea-speed-camera1-h264-freshness.timer", self.source)
        self.assertNotIn('systemctl enable --now "$watchdog_timer_name"', self.source)

    def test_prestate_capture_precedes_first_watchdog_mutation(self) -> None:
        for marker in (
            'watchdog_unit_dst="/etc/systemd/system/sea-speed-camera1-h264-freshness.service"',
            'watchdog_timer_dst="/etc/systemd/system/sea-speed-camera1-h264-freshness.timer"',
            'watchdog_timer_name="sea-speed-camera1-h264-freshness.timer"',
            "previous_watchdog_script_present=false",
            "previous_watchdog_unit_present=false",
            "previous_watchdog_timer_present=false",
            "previous_watchdog_timer_enabled=false",
            "previous_watchdog_timer_active=false",
            'watchdog_script_backup="$(mktemp "$updater_root/watchdog-script-backup.XXXXXX")"',
            'watchdog_unit_backup="$(mktemp "$updater_root/watchdog-unit-backup.XXXXXX")"',
            'watchdog_timer_backup="$(mktemp "$updater_root/watchdog-timer-backup.XXXXXX")"',
            'if systemctl is-enabled --quiet "$watchdog_timer_name"; then',
            'if systemctl is-active --quiet "$watchdog_timer_name"; then',
            'abort_activation "watchdog pre-state capture failed"',
            "watchdog_prestate_captured=true",
        ):
            self.assertIn(marker, self.source)
        self.assertLess(
            self.source.index("watchdog_prestate_captured=true"),
            # Since #406 the first watchdog mutation is the inventory-driven
            # refresh_installed_copies() call, which itself is preceded by the
            # prestate capture (mechanical anchor update; assertion strength
            # unchanged: capture strictly precedes the first watchdog mutation).
            self.source.index('refresh_installed_copies || abort_activation "installed copy refresh failed"'),
        )

    def test_restore_previous_watchdog_restores_captured_prestate(self) -> None:
        for marker in (
            "restore_previous_watchdog()",
            'install -o root -g root -m 0755 "$watchdog_script_backup" "$watchdog_dst" || return 1',
            'install -o root -g root -m 0644 "$watchdog_unit_backup" "$watchdog_unit_dst" || return 1',
            'install -o root -g root -m 0644 "$watchdog_timer_backup" "$watchdog_timer_dst" || return 1',
            'rm -f "$watchdog_dst" || return 1',
            'rm -f "$watchdog_unit_dst" || return 1',
            'rm -f "$watchdog_timer_dst" || return 1',
            "RESTORED watchdog_script_present=",
        ):
            self.assertIn(marker, self.source)
        self.assertLess(
            self.source.index("restore_previous_watchdog()"),
            self.source.index("abort_activation()"),
        )

    def test_abort_paths_restore_watchdog_prestate(self) -> None:
        abort_body = self.source[self.source.index("abort_activation() {"):self.source.index("if ! (")]
        for marker in (
            "restore_previous_watchdog",
            "watchdog_prestate_restored",
            "CRITICAL watchdog pre-state could not be restored",
            "ACTIVATION_ABORTED target=%s restored=%s watchdog_prestate_restored=%s",
            "ACTIVE_MARKER_UNCHANGED source_commit=%s watchdog_prestate_restored=%s",
        ):
            self.assertIn(marker, abort_body)

    def test_timer_reapply_is_gated_on_captured_prestate(self) -> None:
        for marker in (
            'if [[ "$previous_watchdog_timer_enabled" == true ]]; then',
            'systemctl enable "$watchdog_timer_name" >/dev/null || abort_activation "watchdog timer enable failed"',
            'systemctl disable "$watchdog_timer_name" >/dev/null || abort_activation "watchdog timer disable failed"',
            'systemctl start "$watchdog_timer_name" >/dev/null || abort_activation "watchdog timer start failed"',
            "WATCHDOG_TIMER_REAPPLIED timer_present=",
        ):
            self.assertIn(marker, self.source)
        self.assertLess(
            self.source.index("WATCHDOG_TIMER_REAPPLIED timer_present="),
            self.source.index('if ! systemctl restart "$control_service_name"'),
        )

    def test_fresh_host_timer_stays_not_enabled(self) -> None:
        # A timer that did not exist before the deploy must not end up freshly
        # enabled: the absent-timer branch of reapply_watchdog_timer_state()
        # only stops/disables. The anchor is searched inside the function body
        # because restore_previous_watchdog()'s absent branch shares the same
        # indentation (mechanical anchor update from the pure-move extraction;
        # assertion strength unchanged).
        fn_start = self.source.index("reapply_watchdog_timer_state() {")
        absent_branch = self.source[
            self.source.index('else\n    systemctl stop "$watchdog_timer_name"', fn_start):self.source.index("WATCHDOG_TIMER_REAPPLIED")
        ]
        self.assertIn('systemctl disable "$watchdog_timer_name" >/dev/null 2>&1 || true', absent_branch)
        self.assertNotIn("systemctl enable", absent_branch)

    def test_cleanup_covers_watchdog_backups(self) -> None:
        cleanup = self.source[self.source.index("cleanup() {"):self.source.index("trap cleanup EXIT")]
        for marker in ("watchdog_script_backup", "watchdog_unit_backup", "watchdog_timer_backup"):
            self.assertIn(marker, cleanup)

    def test_success_path_timer_stop_verification_is_fail_closed(self) -> None:
        # Repair 2 (issue #412): a captured-inactive or absent-before timer that
        # is still active after the reapply stop is drift; the success path must
        # fail closed instead of reporting preserved inactivity.
        marker = '! systemctl is-active --quiet "$watchdog_timer_name" || abort_activation "watchdog timer stop verification failed"'
        self.assertIn(marker, self.source)
        self.assertEqual(self.source.count('abort_activation "watchdog timer stop verification failed"'), 2)


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

INSTALL_STUB = r"""#!/usr/bin/env bash
# Records every invocation (dst is the last argument), creates the dst file,
# and fails on the Nth call when INSTALL_FAIL_ON_CALL is set (1-based).
printf '%s\n' "install $*" >> "$INSTALL_LOG"
count_file="${INSTALL_COUNT_FILE:?}"
n="$(cat "$count_file" 2>/dev/null || echo 0)"
n=$((n + 1))
printf '%s' "$n" > "$count_file"
if [[ -n "${INSTALL_FAIL_ON_CALL:-}" && "$n" == "$INSTALL_FAIL_ON_CALL" ]]; then
  echo "install: simulated failure" >&2
  exit 1
fi
dst="${*: -1}"
: > "$dst"
exit 0
"""

SYSTEMCTL_STUB = r"""#!/usr/bin/env bash
# Records every invocation; is-enabled/is-active return configurable results.
printf '%s\n' "systemctl $*" >> "$CALLS_LOG"
case "${1:-}" in
  is-enabled) exit "${SYSTEMCTL_IS_ENABLED_RC:-1}" ;;
  is-active) exit "${SYSTEMCTL_IS_ACTIVE_RC:-1}" ;;
  *) exit 0 ;;
esac
"""

RM_STUB = r"""#!/usr/bin/env bash
# Records the invocation, then performs the real removal.
printf '%s\n' "rm $*" >> "$CALLS_LOG"
exec /bin/rm "$@"
"""


class UbuntuWorkerWatchdogExecutedTransactionTests(unittest.TestCase):
    """Executed fault-path coverage for the #412 watchdog transaction functions.

    ``capture_watchdog_prestate``, ``restore_previous_watchdog`` and
    ``reapply_watchdog_timer_state`` are extracted from the script text and
    executed in a sandbox bash process (no root, no systemd): stub executables
    for mktemp, install, systemctl and rm are placed first on PATH, and the
    ``abort_activation`` helper is a harness stub defined AFTER the extracted
    sources (bash resolves functions at call time) that records the reason and
    exits 99.

    The updater script path is overridden module-wide through
    SEA_SPEED_412_UPDATER_PATH (see UPDATER) for RED-vs-base and
    RED-vs-pre-repair runs. The structural marker pin for the success-path stop
    verification (test_success_path_timer_stop_verification_is_fail_closed) is
    kept as an additional guard on top of the executed scenarios.
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

    def _run_harness(self, globals_block: str, invoke: str, stub_env: dict) -> subprocess.CompletedProcess:
        work = Path(tempfile.mkdtemp(prefix="sea-speed-412-harness."))
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        bin_dir = work / "bin"
        bin_dir.mkdir()
        for name, stub_source in (
            ("mktemp", MKTEMP_STUB),
            ("install", INSTALL_STUB),
            ("systemctl", SYSTEMCTL_STUB),
            ("rm", RM_STUB),
        ):
            stub = bin_dir / name
            stub.write_text(stub_source, encoding="utf-8")
            os.chmod(stub, 0o755)
        self.calls_log = work / "calls.log"
        self.install_log = work / "install.log"
        mktemp_count = work / "mktemp.count"
        install_count = work / "install.count"
        for path in (self.calls_log, self.install_log, mktemp_count, install_count):
            path.write_text("", encoding="utf-8")
        harness = (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f'export PATH="{bin_dir}:/usr/bin:/bin"\n'
            f"{self._extract_function('capture_watchdog_prestate')}\n"
            f"{self._extract_function('restore_previous_watchdog')}\n"
            f"{self._extract_function('reapply_watchdog_timer_state')}\n"
            "abort_activation() {\n"
            '  printf \'%s\\n\' "ABORT:$1" >> "$CALLS_LOG"\n'
            "  exit 99\n"
            "}\n"
            f"{globals_block}\n"
            f"{invoke}\n"
        )
        script = work / "harness.sh"
        script.write_text(harness, encoding="utf-8")
        env = {
            **os.environ,
            "CALLS_LOG": str(self.calls_log),
            "INSTALL_LOG": str(self.install_log),
            "MKTEMP_COUNT_FILE": str(mktemp_count),
            "INSTALL_COUNT_FILE": str(install_count),
            **stub_env,
        }
        return subprocess.run([BASH, str(script)], capture_output=True, text=True, env=env)

    def _watchdog_fixture(self, work: Path, present: bool, with_updater_root: bool = False) -> dict:
        values = {
            "watchdog_dst": str(work / "watchdog-script"),
            "watchdog_unit_dst": str(work / "watchdog-unit"),
            "watchdog_timer_dst": str(work / "watchdog-timer"),
            "watchdog_timer_name": "sea-speed-camera1-h264-freshness.timer",
            "watchdog_prestate_captured": "false",
        }
        if with_updater_root:
            updater_root = work / "updater"
            updater_root.mkdir()
            values["updater_root"] = str(updater_root)
        if present:
            for key in ("watchdog_dst", "watchdog_unit_dst", "watchdog_timer_dst"):
                Path(values[key]).write_text("installed-copy\n", encoding="utf-8")
        return values

    def _assert_no_watchdog_mutation(self) -> None:
        recorded = self.install_log.read_text(encoding="utf-8").splitlines()
        for line in recorded:
            self.assertNotEqual(
                line.split()[-1],
                self.watchdog_dst,
                f"watchdog mutation recorded on the abort path: {line}",
            )

    def test_capture_mktemp_failure_aborts_and_skips_watchdog_mutation(self) -> None:
        work = Path(tempfile.mkdtemp(prefix="sea-speed-412-scenario1."))
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        values = self._watchdog_fixture(work, present=True, with_updater_root=True)
        self.watchdog_dst = values["watchdog_dst"]
        globals_block = "\n".join(f'{key}="{value}"' for key, value in values.items())
        proc = self._run_harness(globals_block, "capture_watchdog_prestate", {"MKTEMP_FAIL_ON_CALL": "1"})
        self.assertEqual(proc.returncode, 99, proc.stderr)
        self.assertIn("ABORT:watchdog pre-state capture failed", self.calls_log.read_text(encoding="utf-8"))
        self._assert_no_watchdog_mutation()
        self.assertEqual(self.install_log.read_text(), "")

    def test_capture_install_backup_failure_aborts_and_skips_watchdog_mutation(self) -> None:
        work = Path(tempfile.mkdtemp(prefix="sea-speed-412-scenario2."))
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        values = self._watchdog_fixture(work, present=True, with_updater_root=True)
        self.watchdog_dst = values["watchdog_dst"]
        globals_block = "\n".join(f'{key}="{value}"' for key, value in values.items())
        proc = self._run_harness(globals_block, "capture_watchdog_prestate", {"INSTALL_FAIL_ON_CALL": "1"})
        self.assertEqual(proc.returncode, 99, proc.stderr)
        self.assertIn("ABORT:watchdog pre-state capture failed", self.calls_log.read_text(encoding="utf-8"))
        self._assert_no_watchdog_mutation()
        recorded = self.install_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(recorded), 1, recorded)
        self.assertIn("-m 0600", recorded[0])

    def test_restore_present_timer_enabled_active_restores_bytes_and_state(self) -> None:
        work = Path(tempfile.mkdtemp(prefix="sea-speed-412-scenario3."))
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        values = self._watchdog_fixture(work, present=True)
        self.watchdog_dst = values["watchdog_dst"]
        values.update(
            {
                "watchdog_prestate_captured": "true",
                "previous_watchdog_script_present": "true",
                "previous_watchdog_unit_present": "true",
                "previous_watchdog_timer_present": "true",
                "previous_watchdog_timer_enabled": "true",
                "previous_watchdog_timer_active": "true",
                "watchdog_script_backup": str(work / "backup-script"),
                "watchdog_unit_backup": str(work / "backup-unit"),
                "watchdog_timer_backup": str(work / "backup-timer"),
            }
        )
        for backup in ("watchdog_script_backup", "watchdog_unit_backup", "watchdog_timer_backup"):
            Path(values[backup]).write_text("previous-bytes\n", encoding="utf-8")
        globals_block = "\n".join(f'{key}="{value}"' for key, value in values.items())
        proc = self._run_harness(
            globals_block,
            "restore_previous_watchdog",
            {"SYSTEMCTL_IS_ACTIVE_RC": "0"},
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        install_lines = self.install_log.read_text(encoding="utf-8").splitlines()
        self.assertIn(
            f"install -o root -g root -m 0755 {values['watchdog_script_backup']} {values['watchdog_dst']}",
            install_lines,
        )
        self.assertIn(
            f"install -o root -g root -m 0644 {values['watchdog_unit_backup']} {values['watchdog_unit_dst']}",
            install_lines,
        )
        self.assertIn(
            f"install -o root -g root -m 0644 {values['watchdog_timer_backup']} {values['watchdog_timer_dst']}",
            install_lines,
        )
        calls = self.calls_log.read_text(encoding="utf-8")
        timer = values["watchdog_timer_name"]
        self.assertIn("systemctl daemon-reload", calls)
        self.assertIn(f"systemctl enable {timer}", calls)
        self.assertIn(f"systemctl start {timer}", calls)
        self.assertLess(calls.index("systemctl daemon-reload"), calls.index(f"systemctl enable {timer}"))
        self.assertLess(calls.index(f"systemctl enable {timer}"), calls.index(f"systemctl start {timer}"))

    def test_restore_absent_before_artifacts_are_removed_without_enable(self) -> None:
        work = Path(tempfile.mkdtemp(prefix="sea-speed-412-scenario4."))
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        values = self._watchdog_fixture(work, present=False)
        values.update(
            {
                "watchdog_prestate_captured": "true",
                "previous_watchdog_script_present": "false",
                "previous_watchdog_unit_present": "false",
                "previous_watchdog_timer_present": "false",
                "previous_watchdog_timer_enabled": "false",
                "previous_watchdog_timer_active": "false",
                "watchdog_script_backup": "",
                "watchdog_unit_backup": "",
                "watchdog_timer_backup": "",
            }
        )
        globals_block = "\n".join(f'{key}="{value}"' for key, value in values.items())
        proc = self._run_harness(globals_block, "restore_previous_watchdog", {})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        calls = self.calls_log.read_text(encoding="utf-8")
        timer = values["watchdog_timer_name"]
        self.assertIn(f"rm -f {values['watchdog_dst']}", calls)
        self.assertIn(f"rm -f {values['watchdog_unit_dst']}", calls)
        self.assertIn(f"rm -f {values['watchdog_timer_dst']}", calls)
        self.assertIn(f"systemctl stop {timer}", calls)
        self.assertIn(f"systemctl disable {timer}", calls)
        self.assertIn("systemctl daemon-reload", calls)
        self.assertNotIn(f"systemctl enable {timer}", calls)

    def test_reapply_captured_inactive_timer_still_active_fails_closed(self) -> None:
        # Captured present + enabled + inactive: enable is reapplied first, then
        # the stop branch runs; if the timer is still active afterwards (stop
        # failure or became-active drift) the success path must fail closed
        # instead of reporting preserved inactivity.
        work = Path(tempfile.mkdtemp(prefix="sea-speed-412-scenario5."))
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        values = self._watchdog_fixture(work, present=False)
        values.update(
            {
                "watchdog_prestate_captured": "true",
                "previous_watchdog_timer_present": "true",
                "previous_watchdog_timer_enabled": "true",
                "previous_watchdog_timer_active": "false",
            }
        )
        globals_block = "\n".join(f'{key}="{value}"' for key, value in values.items())
        proc = self._run_harness(globals_block, "reapply_watchdog_timer_state", {"SYSTEMCTL_IS_ACTIVE_RC": "0"})
        self.assertEqual(proc.returncode, 99, proc.stderr)
        calls = self.calls_log.read_text(encoding="utf-8")
        timer = values["watchdog_timer_name"]
        self.assertIn("ABORT:watchdog timer stop verification failed", calls)
        self.assertLess(calls.index(f"systemctl enable {timer}"), calls.index(f"systemctl stop {timer}"))
        self.assertLess(calls.index(f"systemctl stop {timer}"), calls.index(f"systemctl is-active --quiet {timer}"))
        self.assertNotIn(f"systemctl start {timer}", calls)

    def test_reapply_captured_enabled_active_timer_starts_and_reports(self) -> None:
        # Captured present + enabled + active: enable then start succeed and the
        # evidence line reports the captured state; the deploy preserves it.
        work = Path(tempfile.mkdtemp(prefix="sea-speed-412-scenario6."))
        self.addCleanup(shutil.rmtree, work, ignore_errors=True)
        values = self._watchdog_fixture(work, present=False)
        values.update(
            {
                "watchdog_prestate_captured": "true",
                "previous_watchdog_timer_present": "true",
                "previous_watchdog_timer_enabled": "true",
                "previous_watchdog_timer_active": "true",
            }
        )
        globals_block = "\n".join(f'{key}="{value}"' for key, value in values.items())
        proc = self._run_harness(globals_block, "reapply_watchdog_timer_state", {"SYSTEMCTL_IS_ACTIVE_RC": "0"})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        calls = self.calls_log.read_text(encoding="utf-8")
        timer = values["watchdog_timer_name"]
        self.assertLess(calls.index(f"systemctl enable {timer}"), calls.index(f"systemctl start {timer}"))
        self.assertIn(
            "WATCHDOG_TIMER_REAPPLIED timer_present=true timer_enabled=true timer_active=true",
            proc.stderr,
        )
        self.assertNotIn("ABORT:", calls)


if __name__ == "__main__":
    unittest.main()
