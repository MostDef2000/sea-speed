"""Issue #661: the transcode activate config-install permission contract.

Incident (#659 cutover): both transcode scripts' activate installed the
relay-owned MediaMTX config as a HARDCODED root:root 0600. On the box the
relay unit (`sea-speed-stream.service`) runs as root:mediamtx, so the relay
could not read the installed config and the #659 activation needed a MANUAL
root:mediamtx 0640 permission workaround. camera-relay.sh fixed the identical
failure mode in #447/#449 (fail-closed `derive_relay_service_identity` +
evidence before mutation); #661 ports that contract onto both transcode
scripts. This battery pins the ported contract on the REAL script bytes
(executed twins, one subclass per script):

- non-root relay identity (systemctl show User=mediamtx): activate evidences
  INSTALL_OWNER=root:mediamtx / MODE=0640 before any mutation and installs
  the config 0640 through the derived identity. RED on base: base hardcodes
  root:root 0600 and prints no INSTALL_OWNER evidence.
- root relay identity (systemctl show User=root): behavior-only backward
  compatibility guard — activate still succeeds and installs 0600. Deliberately
  NO evidence-line assertion. Plain test, no skip logic: on BASE it fails
  (base rejects the --systemd-unit-dir redirect at parse time); on the ported
  scripts it executes the full transaction.
- underivable identity (empty systemctl User AND a --relay-service name with
  no unit file anywhere): activate refuses fail-closed with exit 9 and the
  explicit derive error BEFORE any mutation — live config bytes and mode
  unchanged, no backup taken. RED on base: base has no derivation and
  proceeds (backup taken, then dies at the hardcoded real-/etc unit install).

The `id sea-speed` readiness gate and the `install` ownership application are
stubbed (OPT-IN via run_shell(stub_id=True, stub_install=True); every other
suite keeps the real coreutils tools): the sandbox has no sea-speed user and
no mediamtx group, and a single-uid user namespace cannot chown to a non-root
group at all (observed EINVAL; nonexistent groups fail earlier with "invalid
group") — cf. the camera-relay MED-2 twin note. Both are environment
readiness, not the behavior under test — same philosophy as the systemctl
stub. The install stub records its full argv in $INSTALL_LOG, so the twins
still prove the REAL install line consumed the derived identity, and it
applies the requested MODE for real (copy + chmod), keeping mode assertions
honest.

Environment-driven scenario notes (sandbox: uid 1000, real /etc/systemd/system
unwritable even inside the user namespace):
- The unit install is redirected into the temp tree through the #661
  --systemd-unit-dir flag wherever the transaction must run to completion
  (scenarios a/b). On BASE that flag does not exist, so those scenarios
  refuse at parse time — the RED is still authentic (the tests cannot pass
  on base); a base full-activate is environmentally impossible either way
  (the hardcoded unit install targets the unwritable real /etc).
- The underivable-identity scenario (c) is entirely FLAG-FREE (no
  --systemd-unit-dir, no --watchdog-bin-dir): the derivation refusal fires
  before any install, so the redirects are irrelevant post-fix, and on base
  the activate proceeds deeper (past the digest and id gates, takes the
  root:root 0600 backup, then dies at the hardcoded real-/etc unit install)
  — a behavioral RED that detects the missing fail-closed contract, not
  just the missing flag.
- All twins run from a COPY TREE (real script bytes + planted executable
  copy of the real renderer bytes, wave-3 demo layout) because activate's
  strict `[[ -x "$renderer" ]]` gate sits between the digest gates and the
  id gate, and the repo-tracked renderer is 100644 (not chmod-able from a
  test — outside the allowed paths). See _script_copy.
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

ROAD1 = ROOT / "deploy/worker/ubuntu/road1-h264-transcode.sh"
CAMERA1 = ROOT / "deploy/worker/ubuntu/camera1-h264-transcode.sh"
RENDERER = ROOT / "scripts/operations/mediamtx_path_config.py"

# Same live-relay shape as tests/test_road1_h264_transcode.py: the box's own
# ZeroTier IP publishes, the VPS (10.123.239.101) reads the transcode path.
RELAY_ADDRESS = "10.123.239.102:8554"
VPS_READER_IP = "10.123.239.101"

ROAD1_BASE_CONFIG = """logLevel: info
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

CAMERA1_BASE_CONFIG = """logLevel: info
authMethod: internal
authInternalUsers:
  # Sea Speed least-privilege reader for canonical cam1
  - user: any
    pass:
    ips: ["10.123.239.101"]
    permissions:
      - action: read
        path: cam1
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
  cam1:
    source: rtsp://10.123.239.55:554/cam1
    sourceOnDemand: yes
    rtspTransport: tcp
"""


def _without_flag_value_pairs(args: list[str], flags: tuple[str, ...]) -> list[str]:
    """Drop `FLAG VALUE` pairs for the given flags. The underivable-identity
    scenario must be entirely flag-free (see the module docstring): post-fix
    the derivation refuses before any install, so the redirects are never
    reached, and on base the flag-free run executes deeper."""
    kept: list[str] = []
    skip_value = False
    for arg in args:
        if skip_value:
            skip_value = False
            continue
        if arg in flags:
            skip_value = True
            continue
        kept.append(arg)
    return kept


class TranscodeActivatePermissionContractTests(unittest.TestCase):
    """Shared executed-twin driver for the activate config-install permission
    contract (one subclass per transcode script binds SCRIPT, SERVICE, the
    config fixture and the script-specific CLI flags). The base defines no
    test methods itself — subclasses expose the three scenarios so unittest
    discovery collects exactly the per-script twins."""

    SCRIPT: Path  # bound by each subclass
    SERVICE: str  # transcode unit name (default --service)
    BASE_CONFIG: str  # per-script relay config fixture

    def _config(self, tmp: Path) -> Path:
        config = tmp / "mediamtx.yml"
        config.write_text(self.BASE_CONFIG, encoding="utf-8")
        # Live relay config shape on the box: root:mediamtx 0640 (the #659
        # incident's manual workaround mode). The underivable-identity twin
        # pins that a refused activate leaves BOTH bytes and mode untouched.
        config.chmod(0o640)
        return config

    def _source_env_file(self, tmp: Path) -> Path:
        # Runtime-assembled synthetic credential shape (never a literal
        # credential in this file); camera1's gates require 0600.
        env_file = tmp / "worker.env"
        env_file.write_text("HLS_URL=rtsp://" + "cam_user:cam_key" + "@10.0.0.21/live\n", encoding="utf-8")
        env_file.chmod(0o600)
        return env_file

    def _plant_ffmpeg_stub(self, tmp: Path) -> None:
        # validate_common requires ffmpeg on PATH; prepare/activate never exec
        # it. Written into tmp/stubs BEFORE run_shell (stub_dir keeps it).
        stubs = tmp / "stubs"
        stubs.mkdir(parents=True, exist_ok=True)
        ffmpeg = stubs / "ffmpeg"
        ffmpeg.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        ffmpeg.chmod(0o755)

    def _script_copy(self, tmp: Path) -> Path:
        """Copy-tree execution (wave-3 demo layout): the REAL script bytes run
        from <tmp>/isolated/deploy/worker/ubuntu/<name>.sh, so the script's
        script_dir/../../.. walk resolves <tmp>/isolated as the repo root and
        the activate flow's strict `[[ -x "$renderer" ]]` gate (road1 L258 /
        camera1 L314) sees a planted EXECUTABLE copy of the REAL renderer
        bytes. The repo-tracked renderer is 100644 and must not be chmod'd
        (outside this battery's allowed paths); the existing suites never
        reach that gate (their activate twins stop at digest-mismatch exit 7),
        but the flag-free underivable-identity twin must execute deeper on
        base — exactly as the box's executable renderer would allow."""
        tree = tmp / "isolated"
        script_dir = tree / "deploy" / "worker" / "ubuntu"
        script_dir.mkdir(parents=True, exist_ok=True)
        copied = script_dir / self.SCRIPT.name
        copied.write_bytes(self.SCRIPT.read_bytes())
        copied.chmod(0o755)
        renderer = tree / "scripts" / "operations" / RENDERER.name
        renderer.parent.mkdir(parents=True, exist_ok=True)
        renderer.write_bytes(RENDERER.read_bytes())
        renderer.chmod(0o755)
        self._copy_script_neighbors(script_dir)
        return copied

    def _copy_script_neighbors(self, script_dir: Path) -> None:
        """Script-dir siblings the activate flow installs (base: none)."""

    def _prepare_args(self, tmp: Path) -> list[str]:
        return [
            "prepare",
            "--config", str(tmp / "mediamtx.yml"),
            "--private-rtsp-address", RELAY_ADDRESS,
            "--reader-ip", VPS_READER_IP,
            "--state-root", str(tmp / "state"),
        ]

    def _activate_args(self, tmp: Path, config_digest: str, unit_digest: str) -> list[str]:
        return [
            "activate",
            "--config", str(tmp / "mediamtx.yml"),
            "--private-rtsp-address", RELAY_ADDRESS,
            "--reader-ip", VPS_READER_IP,
            "--expected-config-sha256", config_digest,
            "--expected-unit-sha256", unit_digest,
            "--state-root", str(tmp / "state"),
            # The namespace cannot write the real /etc/systemd/system; the
            # #661 --systemd-unit-dir flag redirects the unit install into
            # the temp tree (the flag itself is part of the pinned contract).
            "--systemd-unit-dir", str(tmp / "systemd-system"),
        ]

    def _prepare(self, tmp: Path) -> tuple[str, str]:
        self._plant_ffmpeg_stub(tmp)
        self._config(tmp)
        result = relay_shell.run_shell(
            self._script_copy(tmp),
            self._prepare_args(tmp),
            tmp,
            stub_id=True,
            stub_install=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PREPARED_TRANSCODE_CANDIDATE=YES", result.stdout)
        return self._digest(result.stdout, "CONFIG_SHA256"), self._digest(result.stdout, "UNIT_SHA256")

    def _activate(
        self,
        tmp: Path,
        config_digest: str,
        unit_digest: str,
        *,
        relay_service: str | None = None,
        unit_dir: bool = True,
        **env: str,
    ) -> subprocess.CompletedProcess:
        args = self._activate_args(tmp, config_digest, unit_digest)
        if not unit_dir:
            # The underivable-identity scenario is entirely FLAG-FREE: the
            # derivation refusal fires before any install, so the unit-dir /
            # watchdog-bin redirects are never reached post-fix, and on base
            # the flag-free run executes deeper (a behavioral RED: activate
            # proceeds, takes the root:root 0600 backup, then dies at the
            # hardcoded real-/etc unit install).
            args = _without_flag_value_pairs(
                args, ("--systemd-unit-dir", "--watchdog-bin-dir")
            )
        if relay_service is not None:
            args += ["--relay-service", relay_service]
        # The scripts install INTO the unit/watchdog directories without
        # mkdir (on the box /etc/systemd/system and /usr/local/sbin exist);
        # the redirected temp-tree counterparts must pre-exist the same way.
        (tmp / "systemd-system").mkdir(parents=True, exist_ok=True)
        (tmp / "usr-local-sbin").mkdir(parents=True, exist_ok=True)
        environment = {"INSTALL_LOG": str(tmp / "install.log"), **env}
        return relay_shell.run_shell(
            self._script_copy(tmp),
            args,
            tmp,
            env_extra=environment,
            stub_id=True,
            stub_install=True,
        )

    @staticmethod
    def _digest(stdout: str, key: str) -> str:
        for line in stdout.splitlines():
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
        raise AssertionError(f"{key} not found in prepare stdout")

    def _install_log_lines(self, tmp: Path) -> list[str]:
        log = tmp / "install.log"
        if not log.exists():
            return []
        return log.read_text(encoding="utf-8").splitlines()

    # Shared scenario drivers (subclasses expose them as test methods) -------

    def _scenario_non_root_relay_identity(self) -> None:
        # (a) RED pair on base: the relay unit runs as root:mediamtx, so the
        # activate must derive the identity, evidence it BEFORE any mutation,
        # and install the config 0640 through the derived owner/group/mode.
        relay_shell.skip_without_user_namespace(self)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            config_digest, unit_digest = self._prepare(tmp)
            result = self._activate(
                tmp,
                config_digest,
                unit_digest,
                SYSTEMCTL_USER="mediamtx",
                SYSTEMCTL_GROUP="mediamtx",
                SYSTEMCTL_QUIET_ACTIVE_SERVICES=f"sea-speed-stream.service {self.SERVICE}",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            # Evidence before mutation (the camera-relay.sh caller pattern).
            self.assertIn("INSTALL_OWNER=root:mediamtx", result.stdout)
            self.assertIn("MODE=0640", result.stdout)
            # The REAL install line consumed the derived identity (the stub
            # logs its argv): the config install targets ${config}.next with
            # the derived owner/group/mode — not a hardcoded root:root 0600.
            config_installs = [
                line for line in self._install_log_lines(tmp) if line.rstrip().endswith(".next")
            ]
            self.assertEqual(len(config_installs), 1, self._install_log_lines(tmp))
            self.assertIn("-o root -g mediamtx -m 0640", config_installs[0])
            # The installed live config carries the derived MODE.
            self.assertEqual((tmp / "mediamtx.yml").stat().st_mode & 0o777, 0o640)

    def _scenario_root_relay_identity(self) -> None:
        # (b) Backward-compat guard, GREEN against the ported scripts: a root
        # relay identity keeps the root:root 0600 install. Behavior only — no
        # evidence-line assertion (base prints none; the ported script does).
        # Plain test, no skip logic: on BASE it fails (base rejects the
        # --systemd-unit-dir redirect at parse time); on the ported scripts
        # it executes the full transaction.
        relay_shell.skip_without_user_namespace(self)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            config_digest, unit_digest = self._prepare(tmp)
            result = self._activate(
                tmp,
                config_digest,
                unit_digest,
                SYSTEMCTL_USER="root",
                SYSTEMCTL_GROUP="root",
                SYSTEMCTL_QUIET_ACTIVE_SERVICES=f"sea-speed-stream.service {self.SERVICE}",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((tmp / "mediamtx.yml").stat().st_mode & 0o777, 0o600)

    def _scenario_underivable_identity(self) -> None:
        # (c) RED on base: empty systemctl User AND a --relay-service with no
        # unit file anywhere -> the derivation must fail closed (exit 9, the
        # explicit derive error) BEFORE any mutation: live config bytes and
        # mode unchanged, no backup taken. Base has no derivation at all and
        # proceeds (takes the root:root 0600 backup, then dies at the
        # hardcoded real-/etc unit install) — RED on the exit code and the
        # backup assertions. Entirely flag-free (see _activate).
        relay_shell.skip_without_user_namespace(self)
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            config = tmp / "mediamtx.yml"
            config_digest, unit_digest = self._prepare(tmp)
            original = config.read_bytes()
            original_mode = config.stat().st_mode & 0o777
            # SYSTEMCTL_USER deliberately unset -> the stub's `show` returns
            # an empty User; the custom relay-service name has no unit file
            # in any standard unit path.
            result = self._activate(
                tmp,
                config_digest,
                unit_digest,
                relay_service="sea-speed-relay-underivable-test.service",
                unit_dir=False,
                SYSTEMCTL_QUIET_ACTIVE_SERVICES=f"sea-speed-stream.service {self.SERVICE}",
            )
            self.assertEqual(result.returncode, 9, result.stdout + result.stderr)
            self.assertIn("refusing to install with guessed ownership", result.stderr)
            self.assertNotIn("INSTALL_OWNER=", result.stdout)
            self.assertNotIn("MODE=", result.stdout)
            self.assertEqual(config.read_bytes(), original)
            self.assertEqual(config.stat().st_mode & 0o777, original_mode)
            # state/ exists from prepare; "no mutation" means no backup.
            self.assertFalse(list((tmp / "state" / "backups").glob("mediamtx.*.yml")))


class Road1TranscodeActivatePermissionTests(TranscodeActivatePermissionContractTests):
    """Executed twins for road1-h264-transcode.sh's activate config-install
    permission contract (issue #661)."""

    SCRIPT = ROAD1
    SERVICE = "sea-speed-road1-h264.service"
    BASE_CONFIG = ROAD1_BASE_CONFIG

    def test_activate_non_root_relay_identity_evidences_and_installs_0640(self) -> None:
        self._scenario_non_root_relay_identity()

    def test_activate_root_relay_identity_keeps_0600_install(self) -> None:
        self._scenario_root_relay_identity()

    def test_activate_underivable_identity_refuses_fail_closed_before_mutation(self) -> None:
        self._scenario_underivable_identity()


class Camera1TranscodeActivatePermissionTests(TranscodeActivatePermissionContractTests):
    """Executed twins for camera1-h264-transcode.sh's activate config-install
    permission contract (issue #661), including the --source-env-file and
    --watchdog-bin-dir surfaces."""

    SCRIPT = CAMERA1
    SERVICE = "sea-speed-camera1-h264.service"
    BASE_CONFIG = CAMERA1_BASE_CONFIG

    def _prepare_args(self, tmp: Path) -> list[str]:
        return super()._prepare_args(tmp) + [
            "--source-env-file", str(self._source_env_file(tmp)),
        ]

    def _activate_args(self, tmp: Path, config_digest: str, unit_digest: str) -> list[str]:
        return super()._activate_args(tmp, config_digest, unit_digest) + [
            "--source-env-file", str(self._source_env_file(tmp)),
            # The namespace cannot write the real /usr/local/sbin either.
            "--watchdog-bin-dir", str(tmp / "usr-local-sbin"),
        ]

    def _copy_script_neighbors(self, script_dir: Path) -> None:
        # camera1's activate installs the freshness watchdog and its units
        # from script_dir (L343-345); the copy tree needs the REAL sibling
        # bytes next to the script copy or the transaction dies at the
        # watchdog install.
        for name in (
            "camera1-h264-freshness-watchdog.py",
            "sea-speed-camera1-h264-freshness.service",
            "sea-speed-camera1-h264-freshness.timer",
        ):
            source = ROOT / "deploy/worker/ubuntu" / name
            (script_dir / name).write_bytes(source.read_bytes())

    def test_activate_non_root_relay_identity_evidences_and_installs_0640(self) -> None:
        self._scenario_non_root_relay_identity()

    def test_activate_root_relay_identity_keeps_0600_install(self) -> None:
        self._scenario_root_relay_identity()

    def test_activate_underivable_identity_refuses_fail_closed_before_mutation(self) -> None:
        self._scenario_underivable_identity()


if __name__ == "__main__":
    unittest.main()
