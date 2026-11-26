"""Issue #739: the deploy must not wipe the recorder configuration.

The production side landed with the code worker: the module-level recorder
contract in ``deploy/worker/ubuntu/configure-analytics-profiles.py``
(``RECORDER_PREFIX``/``RECORDER_DEFAULTS``/``RECORDER_BOUNDS``, the
validators and ``preserved_recorder_env``), the RELATIVE
``DEFAULT_DESTINATION`` in ``worker/recorder.py``, ``ensure_recorder_spool``
in ``deploy-authorized.sh``, the spool mkdir/chmod pass in
``install-systemd.sh`` and the env-example blocks. These tests pin the
OUTCOMES from AC-001..AC-007 of ``specs/739-config-preserve/spec.md`` with
literal expectations written from the spec text, never derived from the
implementation.

Sections (one class each):

* ``RecorderPreservationMatrixTests`` — AC-001/FR-001: the REAL configure
  step runs against a temp install root whose protected env files hold every
  ``SEA_SPEED_RECORDER_*`` key at a NON-default value (ENABLED=1,
  SOURCE_TYPE=rtsp, POLL_SEC=3, RSYNC_RETRIES=5, a relative DESTINATION,
  plus an unknown ``SEA_SPEED_RECORDER_*`` extra); after reconcile every key
  survives with the same value in BOTH water and road files, the run prints
  ``RECORDER_CONFIG_PRESERVED=YES`` and never echoes a recorder value; a
  Road file missing a key falls back to the safe default instead of
  inheriting the Water value.
* ``RecorderInvalidFallbackTests`` — AC-002/FR-002/FR-003/FR-005/FR-006:
  ``ENABLED=yes``->0, ``SOURCE_TYPE=bogus``->hls, ``POLL_SEC=abc``->2,
  out-of-range/non-finite ints and floats -> defaults, absolute
  DESTINATION -> relative default, traversal SPOOL_DIR -> ``recorder-spool``;
  the reconcile exits 0 and no invalid raw value or secret appears on
  stdout/stderr; ``SOURCE_TYPE`` is case-insensitive with lowercase output.
* ``RecorderDestinationContractTests`` — AC-003/AC-004/FR-004/FR-007:
  ``RecorderConfig.from_env()`` defaults to the RELATIVE
  ``root@10.123.239.127:./`` (absent env, disabled and enabled configs), an
  explicit env override is honoured, while the deploy validator rewrites an
  absolute/malformed target to that same relative default — the drift
  guardian pins configure == recorder == env examples, so a wiped config
  fails safe.
* ``RecorderSpoolProvisioningTests`` — AC-005/FR-008/FR-009: the REAL
  ``ensure_recorder_spool`` function (extracted from ``deploy-authorized.sh``
  and executed in bash) creates both spool dirs at mode 750, refuses a
  symlink and skips only an absent runtime root; the service-user owner
  flags, the reconcile -> spool -> activation ordering and the
  ``install-systemd.sh`` mkdir/chmod pass are source-pinned.
* ``RecorderReconcileIdempotencyTests`` — AC-001 repeat runs: a second
  reconcile produces byte-identical protected env files (no drift).
* ``ConfigPreserveScopeGuardTests`` — the admitted #739 change set over the
  pinned range ``BASE_SHA..HEAD_SHA`` (base ``1465db6`` -> merge ``ff82e19``)
  UNION the working tree, fail-closed (a guard that cannot read its inputs must
  not pass); allowed prefixes per the work order, forbidden ``api/``,
  ``.github/``, ``scripts/ci/validate_sdd.py`` and lockfiles.

Environment: stdlib-only top-level imports (battery import-hygiene scan);
``worker/recorder.py`` is imported inside the tests that need it. No
credential material: the API token is a non-secret fixture literal and no
recorder value is ever asserted against a real endpoint.

RED spot-check (what fails on base ``1465db6``, before the production
change; measured against a ``git archive`` of base extracted to a temp dir
with this file copied into ``tests/``, then ``python3 -m pytest
tests/test_739_config_preserve.py -q`` → **22 failed, 5 passed, 18
subtests passed**):

* Preservation matrix / invalid fallback / idempotency — base
  ``configure-analytics-profiles.py`` has NO ``preserved_recorder_env`` and
  no recorder contract (grep count 0), so the reconcile drops every
  ``SEA_SPEED_RECORDER_*`` key and stdout lacks
  ``RECORDER_CONFIG_PRESERVED=YES``; all four tests fail.
* Destination contract — base ``worker/recorder.py`` still defaults to the
  ABSOLUTE ``root@10.123.239.127:/mnt/fleet-backup/sea-speed/`` (the
  relative-default pin and the drift guardian fail on the literal) and base
  configure has no ``_recorder_destination`` /
  ``RECORDER_DEFAULT_DESTINATION`` (AttributeError in every validator
  subtest: 8 subtests failed); the env examples carry the absolute literal.
* Spool provisioning — base ``deploy-authorized.sh`` has no
  ``ensure_recorder_spool`` (extraction fails closed) and base
  ``install-systemd.sh`` has no ``recorder-spool`` in its mkdir/chmod pass;
  all five tests fail.
* Scope guard — the tree half fails closed on the archive (no ``.git``:
  ``git ... exit 128``); the two synthetic predicate tests (18 subtests) are
  green on base and change alike — they prove the guard's rules, per the
  #696/#699 convention.
* The only other green-on-base tests are the two FR-007 pins that an
  explicit env override is honoured by the recorder (that half of the
  contract was true before and after the change); everything that
  distinguishes #739 from base is RED.
"""

from __future__ import annotations

import importlib.util
import os
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = ROOT / "worker"
CONFIGURE = ROOT / "deploy" / "worker" / "ubuntu" / "configure-analytics-profiles.py"
DEPLOY_AUTHORIZED = ROOT / "deploy" / "worker" / "ubuntu" / "deploy-authorized.sh"
INSTALL_SYSTEMD = ROOT / "deploy" / "worker" / "ubuntu" / "install-systemd.sh"
ENV_EXAMPLES = (
    ROOT / "deploy" / "worker" / "ubuntu" / "worker.env.example",
    ROOT / "deploy" / "worker" / "ubuntu" / "road-worker.env.example",
)
if str(WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(WORKER_DIR))

configure_spec = importlib.util.spec_from_file_location(
    "configure_analytics_profiles_739", CONFIGURE
)
assert configure_spec and configure_spec.loader
configure = importlib.util.module_from_spec(configure_spec)
configure_spec.loader.exec_module(configure)

# Literal contract values (spec FR-004 / AC-003 / AC-004).
RELATIVE_DESTINATION = "root@10.123.239.127:./"
ABSOLUTE_DESTINATION = "root@10.123.239.127:/mnt/fleet-backup/sea-speed/"
ROAD_RELAY_URL = "rtsp://10.123.239.102:8554/road1"
TOKEN = "ingest-token-739-fixture"
API_SEED = (
    "SEA_SPEED_API_URL=http://10.123.239.101:18080/api/cam1/state\n"
    f"SEA_SPEED_API_TOKEN={TOKEN}\n"
)

# AC-001: every known key at a NON-default, valid operator value, plus an
# unknown SEA_SPEED_RECORDER_* extra (FR-001: preserved verbatim).
PRESERVED_RECORDER = {
    "SEA_SPEED_RECORDER_ENABLED": "1",
    "SEA_SPEED_RECORDER_SOURCE_TYPE": "rtsp",
    "SEA_SPEED_RECORDER_HLS_URL": "http://10.123.239.101:8080/recorder-playlist.m3u8",
    "SEA_SPEED_RECORDER_SPOOL_DIR": "recorder-spool-739",
    "SEA_SPEED_RECORDER_DESTINATION": "root@10.123.239.127:preserved/wave8",
    "SEA_SPEED_RECORDER_POLL_SEC": "3",
    "SEA_SPEED_RECORDER_OBJECT_MAX_BYTES": "33554432",
    "SEA_SPEED_RECORDER_MIN_FREE_BYTES": "21474836480",
    "SEA_SPEED_RECORDER_HTTP_TIMEOUT_SEC": "45",
    "SEA_SPEED_RECORDER_RSYNC_TIMEOUT_SEC": "120",
    "SEA_SPEED_RECORDER_RSYNC_RETRIES": "5",
    "SEA_SPEED_RECORDER_RSYNC_BACKOFF_SEC": "10",
    "SEA_SPEED_RECORDER_OPERATOR_NOTE": "keep-me-verbatim-739",
}

# The twelve safe defaults the spec pins (AC-002/AC-003/FR-003).
SAFE_DEFAULTS = {
    "SEA_SPEED_RECORDER_ENABLED": "0",
    "SEA_SPEED_RECORDER_SOURCE_TYPE": "hls",
    "SEA_SPEED_RECORDER_HLS_URL": "",
    "SEA_SPEED_RECORDER_SPOOL_DIR": "recorder-spool",
    "SEA_SPEED_RECORDER_DESTINATION": RELATIVE_DESTINATION,
    "SEA_SPEED_RECORDER_POLL_SEC": "2",
    "SEA_SPEED_RECORDER_OBJECT_MAX_BYTES": "67108864",
    "SEA_SPEED_RECORDER_MIN_FREE_BYTES": "12884901888",
    "SEA_SPEED_RECORDER_HTTP_TIMEOUT_SEC": "30",
    "SEA_SPEED_RECORDER_RSYNC_TIMEOUT_SEC": "60",
    "SEA_SPEED_RECORDER_RSYNC_RETRIES": "3",
    "SEA_SPEED_RECORDER_RSYNC_BACKOFF_SEC": "5",
}

# AC-002/AC-003: every value here is invalid per the spec and must be
# replaced by SAFE_DEFAULTS without aborting the deploy.
INVALID_RECORDER = {
    "SEA_SPEED_RECORDER_ENABLED": "yes",
    "SEA_SPEED_RECORDER_SOURCE_TYPE": "bogus",
    "SEA_SPEED_RECORDER_HLS_URL": "not a url",
    "SEA_SPEED_RECORDER_SPOOL_DIR": "../../etc",
    "SEA_SPEED_RECORDER_DESTINATION": ABSOLUTE_DESTINATION,
    "SEA_SPEED_RECORDER_POLL_SEC": "abc",
    "SEA_SPEED_RECORDER_OBJECT_MAX_BYTES": "1",
    "SEA_SPEED_RECORDER_MIN_FREE_BYTES": "99999999999999999",
    "SEA_SPEED_RECORDER_HTTP_TIMEOUT_SEC": "nan",
    "SEA_SPEED_RECORDER_RSYNC_TIMEOUT_SEC": "99999",
    "SEA_SPEED_RECORDER_RSYNC_RETRIES": "99",
    "SEA_SPEED_RECORDER_RSYNC_BACKOFF_SEC": "-5",
}

# Issue #739 scope-guard pins: BASE_SHA is main just before the #739 change
# and HEAD_SHA is the #739 MERGE COMMIT — the guard verifies the fixed,
# delivered #739 range UNION the working tree, fail-closed (work order), so
# later issues are not judged against #739's allowlist (the #699 REC change
# legitimately edits scripts/ci/validate_sdd.py, which stays forbidden here).
BASE_SHA = "1465db62a4c66c637f1a9b3c6620fabb6291afce"
HEAD_SHA = "ff82e199fe3ab18d6d585a9ef2c60cd43613d606"

ALLOWED_CHANGE_PREFIXES = (
    "tests/",
    "deploy/worker/ubuntu/configure-analytics-profiles.py",
    "deploy/worker/ubuntu/deploy-authorized.sh",
    "deploy/worker/ubuntu/install-systemd.sh",
    "deploy/worker/ubuntu/worker.env.example",
    "deploy/worker/ubuntu/road-worker.env.example",
    "worker/recorder.py",
    "specs/739-config-preserve/",
)
FORBIDDEN_CHANGE_PREFIXES = (
    "api/",
    ".github/",
    "scripts/ci/validate_sdd.py",
)
FORBIDDEN_LOCKFILE_NAMES = ("package-lock.json", "runtime-lock.json")
FORBIDDEN_LOCKFILE_SUFFIXES = (".lock", ".lock.txt")


class ConfigureRunBase(unittest.TestCase):
    """Temp install root + the REAL configure subprocess (AC-001..AC-003)."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="test739-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.install_root = self.root / "install"
        self.config_root = self.install_root / "shared" / "config"
        self.config_root.mkdir(parents=True)
        self.worker_env = self.config_root / "worker.env"
        self.road_env = self.config_root / "road-worker.env"

    def write_env(self, path: Path, recorder_values: dict) -> None:
        content = API_SEED + "".join(
            f"{key}={value}\n" for key, value in sorted(recorder_values.items())
        )
        path.write_text(content, encoding="utf-8")
        os.chmod(path, 0o600)

    def seed(self, water_values: dict, road_values: dict | None = None) -> None:
        self.write_env(self.worker_env, water_values)
        self.write_env(self.road_env, {} if road_values is None else road_values)

    def run_configure(self) -> subprocess.CompletedProcess:
        result = subprocess.run(
            [
                sys.executable,
                str(CONFIGURE),
                "--install-root",
                str(self.install_root),
                "--road-relay-url",
                ROAD_RELAY_URL,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"configure exited {result.returncode}\n{result.stdout}\n{result.stderr}",
        )
        return result

    def water(self) -> dict:
        return configure.read_env(self.worker_env)

    def road(self) -> dict:
        return configure.read_env(self.road_env)


# ---------------------------------------------------------------------------
# 1. Preservation matrix (AC-001 / FR-001)
# ---------------------------------------------------------------------------


class RecorderPreservationMatrixTests(ConfigureRunBase):
    def test_every_recorder_key_survives_in_water_and_road(self) -> None:
        self.seed(PRESERVED_RECORDER, PRESERVED_RECORDER)
        result = self.run_configure()

        self.assertIn("RECORDER_CONFIG_PRESERVED=YES", result.stdout)
        for profile, values in (("water", self.water()), ("road", self.road())):
            with self.subTest(profile=profile):
                recorder_keys = {
                    key for key in values if key.startswith("SEA_SPEED_RECORDER_")
                }
                self.assertEqual(
                    recorder_keys,
                    set(PRESERVED_RECORDER),
                    f"{profile} recorder block must be exactly the preserved keys",
                )
                for key, expected in PRESERVED_RECORDER.items():
                    self.assertEqual(
                        values.get(key),
                        expected,
                        f"{key} must survive the reconcile in {profile}",
                    )
        # FR-006: no recorder value (and no token) is ever printed.
        output = result.stdout + result.stderr
        for never_printed in (
            TOKEN,
            PRESERVED_RECORDER["SEA_SPEED_RECORDER_DESTINATION"],
            PRESERVED_RECORDER["SEA_SPEED_RECORDER_HLS_URL"],
            PRESERVED_RECORDER["SEA_SPEED_RECORDER_OPERATOR_NOTE"],
        ):
            self.assertNotIn(never_printed, output)
        self.assertIn("SECRETS_DISPLAYED=NO", result.stdout)

    def test_missing_road_key_falls_back_to_safe_default_not_water_value(
        self,
    ) -> None:
        # Spec Scenario 2: Water keeps ENABLED=1, a Road file without the
        # key gets the safe default instead of inheriting the Water value.
        self.seed(PRESERVED_RECORDER, road_values={})
        self.run_configure()

        self.assertEqual(self.water()["SEA_SPEED_RECORDER_ENABLED"], "1")
        road = self.road()
        for key, expected in SAFE_DEFAULTS.items():
            self.assertEqual(
                road.get(key), expected, f"road {key} must fall back to the default"
            )


# ---------------------------------------------------------------------------
# 2. Invalid fallback (AC-002 / FR-002 / FR-003 / FR-005 / FR-006)
# ---------------------------------------------------------------------------


class RecorderInvalidFallbackTests(ConfigureRunBase):
    def test_invalid_values_fall_back_to_safe_defaults_and_exit_zero(self) -> None:
        self.seed(INVALID_RECORDER, INVALID_RECORDER)
        result = self.run_configure()

        self.assertIn("RECORDER_CONFIG_PRESERVED=YES", result.stdout)
        self.assertIn("SECRETS_DISPLAYED=NO", result.stdout)
        for profile, values in (("water", self.water()), ("road", self.road())):
            with self.subTest(profile=profile):
                for key, expected in SAFE_DEFAULTS.items():
                    self.assertEqual(
                        values.get(key),
                        expected,
                        f"{key}={INVALID_RECORDER.get(key)!r} must fall back to {expected!r}",
                    )
        # FR-006: the invalid raw values are never echoed (exit 0 asserted by
        # run_configure). Short numeric raws ("1", "99") are excluded — they
        # are substrings of unrelated status words.
        output = result.stdout + result.stderr
        for raw in (
            "yes",
            "bogus",
            "not a url",
            "../../etc",
            ABSOLUTE_DESTINATION,
            "abc",
            "nan",
            "99999",
            "-5",
            "99999999999999999",
            TOKEN,
        ):
            self.assertNotIn(raw, output, f"raw value {raw!r} leaked into output")

    def test_source_type_choice_is_case_insensitive_with_lowercase_output(
        self,
    ) -> None:
        # FR-002: case-insensitive input, lowercase output.
        values = dict(PRESERVED_RECORDER, SEA_SPEED_RECORDER_SOURCE_TYPE="RTSP")
        self.seed(values, values)
        self.run_configure()

        self.assertEqual(self.water()["SEA_SPEED_RECORDER_SOURCE_TYPE"], "rtsp")
        self.assertEqual(self.road()["SEA_SPEED_RECORDER_SOURCE_TYPE"], "rtsp")


# ---------------------------------------------------------------------------
# 3. Destination contract (AC-003 / AC-004 / FR-004 / FR-007)
# ---------------------------------------------------------------------------


class RecorderDestinationContractTests(unittest.TestCase):
    @staticmethod
    def _recorder_module():
        if str(WORKER_DIR) not in sys.path:
            sys.path.insert(0, str(WORKER_DIR))
        import recorder

        return recorder

    @classmethod
    def _from_env(cls, overrides: dict):
        recorder = cls._recorder_module()
        clean = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SEA_SPEED_RECORDER_")
        }
        clean.update(overrides)
        with mock.patch.dict(os.environ, clean, clear=True):
            return recorder.RecorderConfig.from_env()

    @staticmethod
    def _enabled_env(**extra) -> dict:
        env = {
            "SEA_SPEED_RECORDER_ENABLED": "1",
            "SEA_SPEED_RECORDER_SOURCE_TYPE": "hls",
            "SEA_SPEED_RECORDER_HLS_URL": "http://10.123.239.101:8080/x.m3u8",
        }
        env.update(extra)
        return env

    def test_recorder_default_destination_is_relative(self) -> None:
        recorder = self._recorder_module()
        self.assertEqual(recorder.DEFAULT_DESTINATION, RELATIVE_DESTINATION)
        self.assertEqual(recorder.RecorderConfig().destination, RELATIVE_DESTINATION)
        # Env absent, recorder disabled: still the relative default.
        self.assertEqual(
            self._from_env({"SEA_SPEED_RECORDER_ENABLED": "0"}).destination,
            RELATIVE_DESTINATION,
        )
        # Env absent, recorder enabled (AC-004): the relative default.
        self.assertEqual(
            self._from_env(self._enabled_env()).destination, RELATIVE_DESTINATION
        )

    def test_explicit_relative_env_override_is_kept(self) -> None:
        config = self._from_env(
            self._enabled_env(SEA_SPEED_RECORDER_DESTINATION="root@10.123.239.127:custom/dir")
        )
        # The operator path is kept (the recorder normalises it to a
        # directory target with one trailing slash).
        self.assertEqual(config.destination, "root@10.123.239.127:custom/dir/")

    def test_absolute_env_override_is_honoured_by_the_recorder(self) -> None:
        # FR-007: the environment override keeps working unchanged in the
        # recorder. The DEPLOY is the layer that rejects an absolute target
        # (pinned below and end-to-end in RecorderInvalidFallbackTests), so
        # a wiped protected config can never re-introduce it.
        config = self._from_env(
            self._enabled_env(SEA_SPEED_RECORDER_DESTINATION=ABSOLUTE_DESTINATION)
        )
        self.assertEqual(config.destination, ABSOLUTE_DESTINATION)

    def test_deploy_validator_rewrites_bad_targets_to_the_relative_default(
        self,
    ) -> None:
        cases = {
            ABSOLUTE_DESTINATION: RELATIVE_DESTINATION,
            "": RELATIVE_DESTINATION,
            "root@10.123.239.127:": RELATIVE_DESTINATION,
            "10.123.239.127:../escape": RELATIVE_DESTINATION,
            "root@10.123.239.127:a:b": RELATIVE_DESTINATION,
            "root@10.123.239.127:has space": RELATIVE_DESTINATION,
            "relative-without-host": RELATIVE_DESTINATION,
            "root@10.123.239.127:preserved/wave8": "root@10.123.239.127:preserved/wave8",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(configure._recorder_destination(raw), expected)

    def test_drift_guardian_configure_default_equals_recorder_default(
        self,
    ) -> None:
        # A wiped config fails safe only if BOTH layers emit the same
        # relative target.
        recorder = self._recorder_module()
        self.assertEqual(configure.RECORDER_DEFAULT_DESTINATION, RELATIVE_DESTINATION)
        self.assertEqual(
            configure.RECORDER_DEFAULTS["SEA_SPEED_RECORDER_DESTINATION"],
            RELATIVE_DESTINATION,
        )
        self.assertEqual(recorder.DEFAULT_DESTINATION, RELATIVE_DESTINATION)
        self.assertEqual(
            configure.RECORDER_DEFAULT_DESTINATION, recorder.DEFAULT_DESTINATION
        )
        for path in ENV_EXAMPLES:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn(
                    f"SEA_SPEED_RECORDER_DESTINATION={RELATIVE_DESTINATION}", text
                )
                self.assertNotIn(
                    f"SEA_SPEED_RECORDER_DESTINATION={ABSOLUTE_DESTINATION}", text
                )


# ---------------------------------------------------------------------------
# 4. Spool provisioning (AC-005 / FR-008 / FR-009)
# ---------------------------------------------------------------------------


class RecorderSpoolProvisioningTests(unittest.TestCase):
    @staticmethod
    def _spool_function() -> str:
        """Extract the REAL ensure_recorder_spool() body, fail-closed."""
        lines = DEPLOY_AUTHORIZED.read_text(encoding="utf-8").splitlines(keepends=True)
        try:
            start = next(
                index
                for index, line in enumerate(lines)
                if line.startswith("ensure_recorder_spool() {")
            )
            end = next(
                index
                for index in range(start + 1, len(lines))
                if lines[index].rstrip("\n") == "}"
            )
        except StopIteration as exc:
            raise AssertionError(
                "ensure_recorder_spool() not found in deploy-authorized.sh — "
                "Failing closed: a pin that cannot read its input must not pass."
            ) from exc
        return "".join(lines[start : end + 1])

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="test739spool-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.function_file = self.tmp / "ensure_recorder_spool.sh"
        self.function_file.write_text(self._spool_function(), encoding="utf-8")

    def run_spool(self, install_root: Path) -> subprocess.CompletedProcess:
        harness = (
            f"install_root={shlex.quote(str(install_root))}\n"
            "test_mode=1\n"
            "service_user=sea-speed\n"
            f"source {shlex.quote(str(self.function_file))}\n"
            "ensure_recorder_spool\n"
        )
        return subprocess.run(
            ["bash", "-c", harness], capture_output=True, text=True, timeout=60
        )

    @staticmethod
    def _runtime_roots(install_root: Path, water: bool = True, road: bool = True):
        if water:
            (install_root / "shared" / "runtime").mkdir(parents=True)
        if road:
            (install_root / "shared" / "road-runtime").mkdir(parents=True)

    def test_both_spool_dirs_created_at_mode_750_and_not_symlinks(self) -> None:
        install_root = self.tmp / "install"
        self._runtime_roots(install_root)
        result = self.run_spool(install_root)

        self.assertEqual(
            result.returncode, 0, f"spool provisioning failed:\n{result.stderr}"
        )
        self.assertIn("RECORDER_SPOOL_READY=YES", result.stdout)
        for relative in (
            "shared/runtime/recorder-spool",
            "shared/road-runtime/recorder-spool",
        ):
            with self.subTest(spool=relative):
                spool = install_root / relative
                self.assertTrue(spool.is_dir(), f"{relative} must exist")
                self.assertFalse(spool.is_symlink(), f"{relative} must not be a symlink")
                self.assertEqual(
                    stat.S_IMODE(spool.lstat().st_mode), 0o750, relative
                )

    def test_symlink_spool_is_refused(self) -> None:
        install_root = self.tmp / "install"
        self._runtime_roots(install_root)
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        (install_root / "shared" / "runtime" / "recorder-spool").symlink_to(elsewhere)

        result = self.run_spool(install_root)

        self.assertNotEqual(result.returncode, 0, "a symlink spool must fail the deploy")
        self.assertIn("recorder spool path must not be a symlink", result.stderr)

    def test_absent_runtime_root_is_skipped_not_created(self) -> None:
        install_root = self.tmp / "install"
        self._runtime_roots(install_root, water=False)
        result = self.run_spool(install_root)

        self.assertEqual(result.returncode, 0, f"unexpected failure:\n{result.stderr}")
        self.assertTrue(
            (install_root / "shared" / "road-runtime" / "recorder-spool").is_dir()
        )
        self.assertFalse(
            (install_root / "shared" / "runtime" / "recorder-spool").exists(),
            "an absent runtime root must be skipped, not created",
        )

    def test_owner_mode_flags_and_reconcile_spool_activation_order(self) -> None:
        subprocess.run(["bash", "-n", str(DEPLOY_AUTHORIZED)], check=True)
        source = DEPLOY_AUTHORIZED.read_text(encoding="utf-8")

        # FR-008: service-user owner, mode 750, symlink refused.
        self.assertIn(
            'install -d -o "$service_user" -g "$service_user" -m 0750 "$spool_root"',
            source,
        )
        self.assertIn('[[ ! -L "$spool_root" ]]', source)
        # FR-008: provisioned AFTER the protected-config reconcile and
        # BEFORE service activation.
        reconcile = source.index('echo "PROTECTED_CONFIG_RECONCILED=YES"')
        spool_call = source.index("if ! ensure_recorder_spool; then")
        activation = source.index("--activate; then")
        self.assertLess(reconcile, spool_call, "spool must follow the reconcile")
        self.assertLess(spool_call, activation, "spool must precede activation")

    def test_install_systemd_creates_both_spools_in_mkdir_and_chmod_pass(
        self,
    ) -> None:
        subprocess.run(["bash", "-n", str(INSTALL_SYSTEMD)], check=True)
        source = INSTALL_SYSTEMD.read_text(encoding="utf-8")

        # FR-009: both spool dirs in the mkdir pass ...
        self.assertIn(
            '  "$runtime_state_root/recorder-spool" "$road_runtime_root/recorder-spool"',
            source,
        )
        # ... and in the existing 750 ownership/mode pass.
        chmod_750 = [
            line for line in source.splitlines() if line.startswith("chmod 750 ")
        ]
        self.assertEqual(len(chmod_750), 1, "expected exactly one chmod 750 pass")
        self.assertIn('"$runtime_state_root/recorder-spool"', chmod_750[0])
        self.assertIn('"$road_runtime_root/recorder-spool"', chmod_750[0])


# ---------------------------------------------------------------------------
# 5. Idempotency (AC-001 repeat runs)
# ---------------------------------------------------------------------------


class RecorderReconcileIdempotencyTests(ConfigureRunBase):
    def test_second_reconcile_is_byte_identical_no_drift(self) -> None:
        self.seed(PRESERVED_RECORDER, PRESERVED_RECORDER)
        first = self.run_configure()
        self.assertIn("RECORDER_CONFIG_PRESERVED=YES", first.stdout)
        water_first = self.worker_env.read_bytes()
        road_first = self.road_env.read_bytes()

        second = self.run_configure()
        self.assertIn("RECORDER_CONFIG_PRESERVED=YES", second.stdout)

        self.assertEqual(
            self.worker_env.read_bytes(), water_first, "water env drifted on rerun"
        )
        self.assertEqual(
            self.road_env.read_bytes(), road_first, "road env drifted on rerun"
        )
        for values in (self.water(), self.road()):
            for key, expected in PRESERVED_RECORDER.items():
                self.assertEqual(values.get(key), expected)
        self.assertEqual(stat.S_IMODE(self.worker_env.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.road_env.stat().st_mode), 0o600)


# ---------------------------------------------------------------------------
# 6. Scope guard (pinned range UNION working tree, fail-closed)
# ---------------------------------------------------------------------------


class ConfigPreserveScopeGuardTests(unittest.TestCase):
    """The admitted #739 change set; fail-closed when inputs are unreadable."""

    ALLOWED_CHANGE_PREFIXES = ALLOWED_CHANGE_PREFIXES
    FORBIDDEN_CHANGE_PREFIXES = FORBIDDEN_CHANGE_PREFIXES

    @staticmethod
    def _run_git(arguments: list) -> str:
        try:
            result = subprocess.run(
                ["git", "-C", str(ROOT), *arguments],
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, OSError) as exc:
            detail = getattr(exc, "stderr", None) or str(exc)
            raise AssertionError(
                "scope guard cannot read the #739 change set: "
                f"`git {' '.join(arguments)}` failed ({detail.strip()}) — "
                "Failing closed: a guard that cannot read its inputs must not pass."
            ) from exc
        return result.stdout

    @classmethod
    def _changed_paths(cls) -> list:
        # Half A: the pinned BASE_SHA..HEAD_SHA range.
        diff = cls._run_git(["diff", "--name-only", BASE_SHA, HEAD_SHA])
        paths = {
            line.strip().strip('"')
            for line in diff.splitlines()
            if line.strip()
        }
        # Half B: the working-tree status (uncommitted production + tests).
        status = cls._run_git(["status", "--porcelain", "--untracked-files=all"])
        for line in status.splitlines():
            if not line.strip():
                continue
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ")[-1]
            paths.add(path.strip().strip('"'))
        return sorted(paths)

    @classmethod
    def _offenders(cls, paths: list) -> list:
        return [
            path
            for path in paths
            if not any(
                path.startswith(prefix)
                for prefix in cls.ALLOWED_CHANGE_PREFIXES
            )
        ]

    @staticmethod
    def _is_lockfile(path: str) -> bool:
        name = Path(path).name
        return name in FORBIDDEN_LOCKFILE_NAMES or any(
            name.endswith(suffix) for suffix in FORBIDDEN_LOCKFILE_SUFFIXES
        )

    def test_change_set_touches_only_the_739_surface(self) -> None:
        changed = self._changed_paths()
        offenders = self._offenders(changed)
        self.assertEqual(
            offenders,
            [],
            f"out-of-scope paths in the #739 change set "
            f"(pinned range UNION working tree): {offenders}",
        )

    def test_no_forbidden_api_workflow_validate_sdd_or_lockfile_change(
        self,
    ) -> None:
        changed = self._changed_paths()
        for path in changed:
            with self.subTest(path=path):
                for prefix in self.FORBIDDEN_CHANGE_PREFIXES:
                    self.assertFalse(
                        path.startswith(prefix), f"forbidden path changed: {path}"
                    )
                self.assertFalse(self._is_lockfile(path), f"lockfile changed: {path}")

    # -- synthetic predicate proofs (green on base and change alike) -------

    def test_predicate_rejects_out_of_scope_paths(self) -> None:
        rejected = [
            "api/app/main.py",
            ".github/workflows/quality-integration.yml",
            "scripts/ci/validate_sdd.py",
            "package-lock.json",
            "deploy/worker/ubuntu/requirements-runtime.lock.txt",
            "deploy/worker/ubuntu/preflight.sh",
            "worker/worker_media.py",
        ]
        for path in rejected:
            with self.subTest(path=path):
                allowed = any(
                    path.startswith(prefix)
                    for prefix in self.ALLOWED_CHANGE_PREFIXES
                )
                forbidden = any(
                    path.startswith(prefix)
                    for prefix in self.FORBIDDEN_CHANGE_PREFIXES
                )
                self.assertFalse(
                    allowed and not forbidden and not self._is_lockfile(path),
                    f"guard must reject {path}",
                )

    def test_predicate_accepts_admitted_paths(self) -> None:
        admitted = [
            "tests/test_739_config_preserve.py",
            "tests/test_699_recorder_lifecycle.py",
            "deploy/worker/ubuntu/configure-analytics-profiles.py",
            "deploy/worker/ubuntu/deploy-authorized.sh",
            "deploy/worker/ubuntu/install-systemd.sh",
            "deploy/worker/ubuntu/worker.env.example",
            "deploy/worker/ubuntu/road-worker.env.example",
            "worker/recorder.py",
            "specs/739-config-preserve/spec.md",
            "specs/739-config-preserve/plan.md",
            "specs/739-config-preserve/tasks.md",
        ]
        for path in admitted:
            with self.subTest(path=path):
                self.assertTrue(
                    any(
                        path.startswith(prefix)
                        for prefix in self.ALLOWED_CHANGE_PREFIXES
                    ),
                    f"admitted path wrongly rejected: {path}",
                )
                self.assertFalse(
                    any(
                        path.startswith(prefix)
                        for prefix in self.FORBIDDEN_CHANGE_PREFIXES
                    ),
                    f"admitted path wrongly forbidden: {path}",
                )
                self.assertFalse(self._is_lockfile(path))


if __name__ == "__main__":
    unittest.main()
