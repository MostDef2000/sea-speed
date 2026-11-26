"""Issue #699: recorder lifecycle, packaging inventory and scope guard.

The production side (``worker/ubuntu_worker_entrypoint.py`` lifecycle hooks,
``worker/recorder.py``, the env-example opt-in blocks, the service-template
``LoadCredential`` mounts and the exact-artifact inventories) landed with the
code worker; these tests pin the OUTCOMES from AC-001/AC-006/AC-007 plus the
issue's scope contract.

Sections (one class each):

* ``RecorderEntrypointLifecycleTests`` — AC-001/AC-006: only the literal
  flag ``1`` enables; enabled spawns exactly one child with
  ``stdin=DEVNULL`` + ``start_new_session=True`` + ``close_fds=True`` and
  NO wait; disabled spawns nothing; a spawn failure logs
  ``recorder disabled spawn failure`` and leaves no child without raising;
  ``_stop_recorder`` sends SIGTERM to the child's process GROUP (killpg,
  covering the rsync descendant), escalates to SIGKILL when the child does
  not reap, clears the slot, and is a no-op with no child; SIGTERM/SIGINT
  handlers raise ``SystemExit(128+signum)`` (143/130); a REAL process-group
  stop kills both the child and its grandchild (the rsync stand-in); and the
  ``__main__`` wiring is pinned (stop signals installed, recorder started
  before ``worker.main()``, ``_stop_recorder`` in the ``finally``).
* ``RecorderPackagingTests`` — AC-007/AC-010: ``worker/recorder.py`` AND
  ``worker/recorder_rtsp.py`` in the ubuntu-worker exact-artifact inventories
  ONLY (absent from vps/edge, in BOTH the builder and the validator); the real
  build+validate subprocess pair passes and the built ubuntu-worker artifact
  contains both recorder modules while vps/edge do not; both env examples
  carry the IDENTICAL opt-in block (default ``SEA_SPEED_RECORDER_ENABLED=0``,
  selector ``SEA_SPEED_RECORDER_SOURCE_TYPE=hls`` present in both); the
  selector source pin (``worker/recorder.py`` reads the selector and lazy-
  imports ``recorder_rtsp``); both service templates keep the literal
  ``LoadCredential=recorder_ed25519`` line.
* ``RecorderScopeGuardTests`` — the admitted #699 change set over the
  DELIVERED pinned range ``BASE_SHA..HEAD_SHA`` (base ``a66b5a8`` → merge
  ``c689947``; fail-closed: a guard that cannot read its inputs must not
  pass), allowed prefixes per the work order, forbidden ``api/``,
  ``worker/worker_media.py``, ``.github/`` and lockfiles — restrictions
  unchanged from the merge-time pin (the allowlist is NOT widened).
* ``RtspScopeGuardTests`` — the #699b change set: the working tree (status)
  UNION the ``c689947..HEAD`` range, fail-closed, allowed prefixes =
  ``tests/``, ``worker/recorder.py``, ``worker/recorder_rtsp.py``,
  ``deploy/worker/ubuntu/*.env.example``, the two exact-artifact scripts,
  ``scripts/ci/validate_sdd.py`` and ``specs/699-rtsp-recorder/``;
  forbidden = ``api/``, ``worker/worker_media.py``,
  ``worker/ubuntu_worker_entrypoint.py``, ``.github/`` and lockfiles.

Environment: stdlib-only top-level imports (battery import-hygiene scan).
The entrypoint is loaded through the provenance pattern
(tests/test_696/test_worker_outbox_delivery): only the heavy runtime worker
module is stubbed; numpy/requests are guarded-optional.

RED spot-check (what fails on base ``a66b5a8``, before the production
change; measured against a ``git archive`` of base):

* Entrypoint lifecycle — base has NO ``_recorder_enabled`` /
  ``_start_recorder`` / ``_stop_recorder`` / ``_install_stop_signals``
  (grep count 0), so every lifecycle test errors with AttributeError and
  the ``__main__`` wiring pin finds no recorder calls.
* Packaging — base inventories contain no ``worker/recorder.py`` (grep
  count 0), so the inventory pins fail; the env examples have no
  ``SEA_SPEED_RECORDER`` block (grep count 0) and the templates have no
  ``LoadCredential=recorder_ed25519`` line.
* Scope guard — the two tree tests fail closed on the archive (no ``.git``;
  ``CalledProcessError exit 128``); the synthetic predicate tests pass on
  base and the change alike (they prove the guard's rules, like the #696
  scope-guard convention).
"""

from __future__ import annotations

import ast
import contextlib
import fnmatch
import importlib.util
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKER_DIR = ROOT / "worker"
ENTRYPOINT = WORKER_DIR / "ubuntu_worker_entrypoint.py"
RECORDER_SCRIPT = WORKER_DIR / "recorder.py"
BUILDER = ROOT / "scripts" / "quality" / "build_exact_artifacts.py"
VALIDATOR = ROOT / "scripts" / "quality" / "validate_exact_artifacts.py"
ENV_EXAMPLES = (
    ROOT / "deploy" / "worker" / "ubuntu" / "worker.env.example",
    ROOT / "deploy" / "worker" / "ubuntu" / "road-worker.env.example",
)
SERVICE_TEMPLATES = (
    ROOT / "deploy" / "worker" / "ubuntu" / "sea-speed-worker.service.template",
    ROOT
    / "deploy"
    / "worker"
    / "ubuntu"
    / "sea-speed-road-worker.service.template",
)
for _root in (str(ROOT), str(WORKER_DIR)):
    if _root not in sys.path:
        sys.path.insert(0, _root)

# Issue #699 scope-guard pins: BASE_SHA is main just before the #699 change
# and HEAD_SHA is the #699 MERGE COMMIT — the guard verifies the fixed,
# non-empty DELIVERED #699 change set (work order re-pin, 2026-11-26), with
# the original restrictions intact (allowlist not widened, lockfile ban kept).
# The working tree is guarded by the #699b guard below (RtspScopeGuardTests).
BASE_SHA = "a66b5a8039cdba585f8b549e1091989586b0d72a"
HEAD_SHA = "c689947350f141aada84943a6e06a71e3cbb28b4"

# Issue #699b scope-guard pins: the RTSP recorder change set is the working
# tree UNION the range from the delivered #699 merge to the branch tip,
# fail-closed (work order).
RTSP_BASE_SHA = "c689947350f141aada84943a6e06a71e3cbb28b4"
RTSP_HEAD_SHA = "HEAD"

RTSP_ALLOWED_CHANGE_PREFIXES = (
    "tests/",
    "worker/recorder.py",
    "worker/recorder_rtsp.py",
    "deploy/worker/ubuntu/*.env.example",
    "scripts/quality/build_exact_artifacts.py",
    "scripts/quality/validate_exact_artifacts.py",
    "scripts/ci/validate_sdd.py",
    "specs/699-rtsp-recorder/",
)
RTSP_FORBIDDEN_CHANGE_PREFIXES = (
    "api/",
    "worker/worker_media.py",
    "worker/ubuntu_worker_entrypoint.py",
    ".github/",
)

ALLOWED_CHANGE_PREFIXES = (
    "tests/",
    "worker/recorder.py",
    "worker/ubuntu_worker_entrypoint.py",
    "deploy/worker/ubuntu/",
    "scripts/quality/build_exact_artifacts.py",
    "scripts/quality/validate_exact_artifacts.py",
    "specs/699-recorder-first/",
)
FORBIDDEN_CHANGE_PREFIXES = (
    "api/",
    "worker/worker_media.py",
    ".github/",
    ".gitlab",
)
FORBIDDEN_LOCKFILE_NAMES = ("package-lock.json", "runtime-lock.json")
FORBIDDEN_LOCKFILE_SUFFIXES = (".lock", ".lock.txt")

LOAD_CREDENTIAL_LINE = (
    "LoadCredential=recorder_ed25519:/etc/sea-speed/recorder_ed25519"
)
RECORDER_ENV_KEYS = (
    "SEA_SPEED_RECORDER_ENABLED=0",
    "SEA_SPEED_RECORDER_SOURCE_TYPE=hls",
    "SEA_SPEED_RECORDER_HLS_URL=",
    "SEA_SPEED_RECORDER_SPOOL_DIR=recorder-spool",
    "SEA_SPEED_RECORDER_DESTINATION=root@10.123.239.127:/mnt/fleet-backup/sea-speed/",
    "SEA_SPEED_RECORDER_POLL_SEC=2",
    "SEA_SPEED_RECORDER_OBJECT_MAX_BYTES=67108864",
    "SEA_SPEED_RECORDER_MIN_FREE_BYTES=12884901888",
    "SEA_SPEED_RECORDER_HTTP_TIMEOUT_SEC=30",
    "SEA_SPEED_RECORDER_RSYNC_TIMEOUT_SEC=60",
    "SEA_SPEED_RECORDER_RSYNC_RETRIES=3",
    "SEA_SPEED_RECORDER_RSYNC_BACKOFF_SEC=5",
)
BUILD_COMMIT = "a66b5a8039cdba585f8b549e1091989586b0d72a"


# ---------------------------------------------------------------------------
# Entrypoint loader (provenance pattern, tests/test_696 + outbox delivery)
# ---------------------------------------------------------------------------


def load_entrypoint():
    """Load the Ubuntu entrypoint with ONLY the heavy runtime worker stubbed.

    ``mock.patch.dict(sys.modules, ...)`` is deliberately NOT used to hold
    the stub after exec beyond the import window: the returned module keeps
    its own reference to the stub ``worker`` module.
    """
    for name in ("numpy", "requests"):
        if name in sys.modules:
            continue
        try:
            available = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            available = False
        if not available:
            sys.modules[name] = mock.MagicMock(name=name)
    runtime_worker = types.ModuleType("hls_motion_yolo_worker_events")
    runtime_worker.start_media_reader = lambda av_module=None: None
    runtime_worker.post_state = lambda metadata, overlay_path: True
    runtime_worker.post_event = lambda metadata, snapshot_path: True
    runtime_worker.env_str = lambda name, default="": os.environ.get(name, default)
    runtime_worker.env_int = lambda name, default=0: int(
        os.environ.get(name, default)
    )
    runtime_worker.env_float = lambda name, default=0.0: float(
        os.environ.get(name, default)
    )
    runtime_worker.safe_media_input_label = lambda url: "<configured>"
    spec = importlib.util.spec_from_file_location(
        "ubuntu_worker_entrypoint_699_lifecycle", ENTRYPOINT
    )
    module = importlib.util.module_from_spec(spec)
    # Single-key management, NOT mock.patch.dict(sys.modules): patch.dict
    # restores the WHOLE dict on exit, evicting numpy/requests imported
    # during exec — a later re-import dies with "cannot load module more
    # than once per process" (the tests/test_696 docstring warning).
    previous = sys.modules.get("hls_motion_yolo_worker_events")
    sys.modules["hls_motion_yolo_worker_events"] = runtime_worker
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop("hls_motion_yolo_worker_events", None)
        else:
            sys.modules["hls_motion_yolo_worker_events"] = previous
    return module


class RecorderLifecycleBase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="test699life-")
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.entry = load_entrypoint()
        # Each test starts with no recorder child recorded.
        self.entry._recorder_process = None

    def _flag_env(self, flag: str | None) -> dict:
        clean = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("SEA_SPEED_RECORDER_")
        }
        if flag is not None:
            clean["SEA_SPEED_RECORDER_ENABLED"] = flag
        return clean

    def _start_with(self, flag: str | None, popen) -> str:
        out = io.StringIO()
        with mock.patch.dict(os.environ, self._flag_env(flag), clear=True):
            with contextlib.redirect_stdout(out):
                with mock.patch.object(
                    self.entry.subprocess, "Popen", popen
                ):
                    self.entry._start_recorder()
        return out.getvalue()


# ---------------------------------------------------------------------------
# 1. Entrypoint lifecycle (AC-001 / AC-006)
# ---------------------------------------------------------------------------


class RecorderEntrypointLifecycleTests(RecorderLifecycleBase):
    def test_recorder_enabled_only_for_literal_one(self) -> None:
        cases = {
            "1": True,
            "0": False,
            "true": False,
            "yes": False,
            "2": False,
            "": False,
        }
        for flag, expected in cases.items():
            with self.subTest(flag=flag):
                with mock.patch.dict(
                    os.environ, self._flag_env(flag), clear=True
                ):
                    self.assertIs(self.entry._recorder_enabled(), expected)

    def test_spawn_on_enabled_with_devnull_session_and_no_wait(self) -> None:
        child = mock.Mock(pid=4242)
        popen = mock.Mock(return_value=child)
        out = self._start_with("1", popen)

        self.assertEqual(popen.call_count, 1)
        args, kwargs = popen.call_args
        script = args[0]
        self.assertEqual(script[0], sys.executable)
        self.assertEqual(script[1], str(RECORDER_SCRIPT))
        self.assertIs(kwargs.get("stdin"), subprocess.DEVNULL)
        self.assertIs(kwargs.get("start_new_session"), True)
        self.assertIs(kwargs.get("close_fds"), True)
        # No readiness wait: the child is never waited on at spawn.
        child.wait.assert_not_called()
        self.assertIs(self.entry._recorder_process, child)
        self.assertIn("recorder started pid=4242", out)

    def test_no_spawn_when_disabled(self) -> None:
        for flag in (None, "0", "true"):
            with self.subTest(flag=flag):
                popen = mock.Mock()
                out = self._start_with(flag, popen)
                popen.assert_not_called()
                self.assertIsNone(self.entry._recorder_process)
                self.assertIn("recorder disabled", out)

    def test_spawn_failure_disables_recording_only_without_raising(self) -> None:
        def _boom(*args, **kwargs):
            raise OSError("no fork today")

        out = self._start_with("1", _boom)
        self.assertIsNone(self.entry._recorder_process)
        self.assertIn("recorder disabled spawn failure reason=OSError", out)
        # No exception escaped: the analytics worker would have continued.

    def test_missing_script_disables_recording_only(self) -> None:
        # Simulate the pre-#699 tree: recorder.py absent next to the entry.
        popen = mock.Mock()
        fake_script = mock.Mock()
        fake_script.is_file.return_value = False
        fake_path_entry = mock.Mock()
        fake_path_entry.with_name.return_value = fake_script
        fake_path = mock.Mock(return_value=fake_path_entry)
        with mock.patch.object(self.entry, "Path", fake_path):
            out = self._start_with("1", popen)
        popen.assert_not_called()
        self.assertIsNone(self.entry._recorder_process)
        self.assertIn("recorder disabled spawn failure reason=missing_script", out)

    def test_stop_noop_without_child(self) -> None:
        with mock.patch.object(self.entry.os, "killpg") as killpg:
            self.entry._stop_recorder()
        killpg.assert_not_called()
        self.assertIsNone(self.entry._recorder_process)

    def test_stop_uses_killpg_sigterm_then_sigkill_and_clears_slot(self) -> None:
        child = mock.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="recorder", timeout=10.0),
            0,
        ]
        self.entry._recorder_process = child
        with mock.patch.object(self.entry.os, "killpg") as killpg:
            self.entry._stop_recorder()

        self.assertEqual(
            killpg.call_args_list,
            [
                mock.call(4242, signal.SIGTERM),
                mock.call(4242, signal.SIGKILL),
            ],
            "stop must SIGTERM the group first, then SIGKILL the survivor",
        )
        self.assertEqual(child.wait.call_count, 2)
        self.assertIsNone(self.entry._recorder_process)

    def test_stop_escalates_only_when_child_does_not_reap(self) -> None:
        child = mock.Mock(pid=4242)
        child.poll.return_value = None
        child.wait.return_value = 0  # reaps after SIGTERM: no SIGKILL
        self.entry._recorder_process = child
        with mock.patch.object(self.entry.os, "killpg") as killpg:
            self.entry._stop_recorder()
        killpg.assert_called_once_with(4242, signal.SIGTERM)
        self.assertIsNone(self.entry._recorder_process)

    def test_stop_terminates_child_and_process_group_grandchild(self) -> None:
        """Real killpg: the child's group includes its rsync descendant."""
        grandchild_marker = self.tmp / "grandchild.pid"
        child_script = (
            "import subprocess, sys, time\n"
            "grandchild = subprocess.Popen(\n"
            "    [sys.executable, '-c', 'import time; time.sleep(300)']\n"
            ")\n"
            f"open({str(grandchild_marker)!r}, 'w').write(str(grandchild.pid))\n"
            "time.sleep(300)\n"
        )
        child = subprocess.Popen(
            [sys.executable, "-c", child_script],
            stdin=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )
        self.entry._recorder_process = child
        try:
            deadline = time.monotonic() + 10.0
            while not grandchild_marker.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(grandchild_marker.exists(), "grandchild never spawned")
            grandchild_pid = int(grandchild_marker.read_text())

            self.entry._stop_recorder()

            self.assertIsNotNone(child.poll(), "child must be reaped")
            # The grandchild lived in the child's NEW session/group, so the
            # same killpg that stopped the child stopped it too. A dead
            # orphan may linger as a zombie under a non-reaping PID 1 —
            # either gone or 'Z' counts as terminated.
            def _terminated(pid: int) -> bool:
                try:
                    stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
                except OSError:
                    return True
                state = stat.rsplit(")", 1)[1].split()[0]
                return state in ("Z", "X")

            deadline = time.monotonic() + 5.0
            while not _terminated(grandchild_pid) and time.monotonic() < deadline:
                time.sleep(0.1)
            self.assertTrue(
                _terminated(grandchild_pid),
                f"rsync descendant pid {grandchild_pid} survived the group stop",
            )
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)

    def test_stop_signals_raise_systemexit_143_and_130(self) -> None:
        registered: dict = {}
        with mock.patch.object(
            self.entry.signal,
            "signal",
            side_effect=lambda signum, handler: registered.__setitem__(
                signum, handler
            ),
        ):
            self.entry._install_stop_signals()

        self.assertIn(signal.SIGTERM, registered)
        self.assertIn(signal.SIGINT, registered)
        with self.assertRaises(SystemExit) as term:
            registered[signal.SIGTERM](signal.SIGTERM, None)
        self.assertEqual(term.exception.code, 128 + signal.SIGTERM)  # 143
        with self.assertRaises(SystemExit) as interrupt:
            registered[signal.SIGINT](signal.SIGINT, None)
        self.assertEqual(interrupt.exception.code, 128 + signal.SIGINT)  # 130

    def test_main_wiring_installs_signals_starts_recorder_and_stops_in_finally(
        self,
    ) -> None:
        tree = ast.parse(ENTRYPOINT.read_text(encoding="utf-8"))
        main_guard = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.If)
                and isinstance(node.test, ast.Compare)
                and isinstance(node.test.left, ast.Name)
                and node.test.left.id == "__name__"
                and any(
                    isinstance(comp, ast.Constant) and comp.value == "__main__"
                    for comp in node.test.comparators
                )
            ),
            None,
        )
        self.assertIsNotNone(main_guard, "entrypoint __main__ block not found")
        tries = [
            node for node in ast.walk(main_guard) if isinstance(node, ast.Try)
        ]
        self.assertTrue(tries, "the __main__ block must be a try/finally")
        top_try = next(
            node for node in main_guard.body if isinstance(node, ast.Try)
        )

        def called_names(nodes) -> set:
            names: set = set()
            for node in nodes:
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name):
                            names.add(child.func.id)
                        elif isinstance(child.func, ast.Attribute):
                            names.add(child.func.attr)
            return names

        body_names = called_names(top_try.body)
        self.assertIn("_install_stop_signals", body_names)
        self.assertIn("_start_recorder", body_names)
        self.assertIn("main", body_names)
        final_names = called_names(top_try.finalbody)
        self.assertIn(
            "_stop_recorder",
            final_names,
            "the recorder child must be stopped in the __main__ finally",
        )
        # Ordering: recorder starts before worker.main() runs.
        body_source = ast.unparse(top_try)
        self.assertLess(
            body_source.index("_start_recorder"),
            body_source.index("worker.main()"),
            "recorder must start before the ingest loop",
        )


# ---------------------------------------------------------------------------
# 2. Packaging (AC-007)
# ---------------------------------------------------------------------------


class RecorderPackagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from scripts.quality.build_exact_artifacts import COMPONENT_FILES
        from scripts.quality.validate_exact_artifacts import REQUIRED_BY_COMPONENT

        cls.builder_inventory = COMPONENT_FILES
        cls.validator_inventory = REQUIRED_BY_COMPONENT

    def test_recorder_in_ubuntu_inventory_only_in_both_scripts(self) -> None:
        for component in ("vps", "edge"):
            with self.subTest(component=component, script="builder"):
                self.assertNotIn(
                    "worker/recorder.py",
                    self.builder_inventory[component]["required"],
                )
                self.assertNotIn(
                    "worker/recorder.py",
                    self.builder_inventory[component].get("optional", []),
                )
            with self.subTest(component=component, script="validator"):
                self.assertNotIn(
                    "worker/recorder.py", self.validator_inventory[component]
                )
        self.assertIn(
            "worker/recorder.py",
            self.builder_inventory["ubuntu-worker"]["required"],
            "worker/recorder.py must ship in the ubuntu-worker artifact",
        )
        self.assertIn(
            "worker/recorder.py",
            self.validator_inventory["ubuntu-worker"],
            "the validator must require worker/recorder.py for ubuntu-worker",
        )

    def test_recorder_rtsp_in_ubuntu_inventory_only_in_both_scripts(self) -> None:
        for component in ("vps", "edge"):
            with self.subTest(component=component, script="builder"):
                self.assertNotIn(
                    "worker/recorder_rtsp.py",
                    self.builder_inventory[component]["required"],
                )
                self.assertNotIn(
                    "worker/recorder_rtsp.py",
                    self.builder_inventory[component].get("optional", []),
                )
            with self.subTest(component=component, script="validator"):
                self.assertNotIn(
                    "worker/recorder_rtsp.py", self.validator_inventory[component]
                )
        self.assertIn(
            "worker/recorder_rtsp.py",
            self.builder_inventory["ubuntu-worker"]["required"],
            "worker/recorder_rtsp.py must ship in the ubuntu-worker artifact",
        )
        self.assertIn(
            "worker/recorder_rtsp.py",
            self.validator_inventory["ubuntu-worker"],
            "the validator must require worker/recorder_rtsp.py for ubuntu-worker",
        )

    def test_recorder_selector_source_is_pinned(self) -> None:
        source = RECORDER_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("SEA_SPEED_RECORDER_SOURCE_TYPE", source)
        self.assertIn(
            "SEA_SPEED_RECORDER_SOURCE_TYPE must be hls or rtsp", source
        )
        self.assertIn(
            "HLS_URL is required when SEA_SPEED_RECORDER_SOURCE_TYPE=rtsp",
            source,
            "the rtsp arm must read the existing HLS_URL with no fallback",
        )
        self.assertIn("import recorder_rtsp", source, "the RTSP arm is lazy")

    def test_build_and_validate_pass_and_contain_recorder(self) -> None:
        with tempfile.TemporaryDirectory(prefix="test699artifacts-") as out:
            build = subprocess.run(
                [
                    sys.executable,
                    str(BUILDER),
                    "--source-commit",
                    BUILD_COMMIT,
                    "--output-dir",
                    out,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=300,
            )
            self.assertEqual(
                build.returncode,
                0,
                f"build_exact_artifacts failed:\n{build.stdout}\n{build.stderr}",
            )
            validate = subprocess.run(
                [
                    sys.executable,
                    str(VALIDATOR),
                    "--manifest",
                    str(Path(out) / "exact-artifacts.json"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=300,
            )
            self.assertEqual(
                validate.returncode,
                0,
                f"validate_exact_artifacts failed:\n{validate.stdout}\n"
                f"{validate.stderr}",
            )
            self.assertIn("Exact artifacts valid", validate.stdout)

            manifest = json.loads(
                (Path(out) / "exact-artifacts.json").read_text(encoding="utf-8")
            )
            by_component = {
                entry["component"]: entry
                for entry in [*manifest["artifacts"], *manifest["release_artifacts"]]
            }
            ubuntu_paths = {
                item["path"] for item in by_component["ubuntu-worker"]["files"]
            }
            self.assertIn("worker/recorder.py", ubuntu_paths)
            self.assertIn(
                "worker/recorder_rtsp.py",
                ubuntu_paths,
                "worker/recorder_rtsp.py must ship in the ubuntu-worker artifact",
            )
            for component in ("vps", "edge"):
                paths = {
                    item["path"] for item in by_component[component]["files"]
                }
                self.assertNotIn(
                    "worker/recorder.py",
                    paths,
                    f"recorder must not ship in the {component} artifact",
                )
                self.assertNotIn(
                    "worker/recorder_rtsp.py",
                    paths,
                    f"recorder_rtsp must not ship in the {component} artifact",
                )

    @staticmethod
    def _recorder_block(text: str) -> list:
        lines = text.splitlines()
        start = next(
            index
            for index, line in enumerate(lines)
            if line.startswith("# Issue #699")
        )
        block: list = []
        seen_key = False
        for line in lines[start:]:
            if line.startswith("SEA_SPEED_RECORDER_"):
                seen_key = True
                block.append(line)
            elif line.startswith("#") and not seen_key:
                block.append(line)
            elif seen_key:
                break
            else:  # pragma: no cover - defensive: blank line inside comment
                block.append(line)
        return block

    def test_env_examples_carry_identical_opt_in_block(self) -> None:
        blocks = [
            self._recorder_block(path.read_text(encoding="utf-8"))
            for path in ENV_EXAMPLES
        ]
        self.assertEqual(
            blocks[0],
            blocks[1],
            "both Ubuntu env examples must carry the identical opt-in block",
        )
        for path, block in zip(ENV_EXAMPLES, blocks):
            with self.subTest(path=path.name):
                self.assertIn("SEA_SPEED_RECORDER_ENABLED=0", block)
                for key in RECORDER_ENV_KEYS:
                    self.assertIn(key, block, f"{key} missing from {path.name}")

    def test_service_templates_keep_load_credential_mount(self) -> None:
        for path in SERVICE_TEMPLATES:
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn(LOAD_CREDENTIAL_LINE, text)


# ---------------------------------------------------------------------------
# 3. Scope guard (pinned range UNION working tree, fail-closed)
# ---------------------------------------------------------------------------


class RecorderScopeGuardTests(unittest.TestCase):
    """The delivered #699 range; fail-closed when inputs unreadable.

    Re-pinned to the delivered range (base ``a66b5a8`` → merge ``c689947``)
    with the original restrictions intact: same allowlist (not widened),
    same forbidden prefixes, same lockfile ban, same fail-closed git reads.
    The working tree is guarded by ``RtspScopeGuardTests`` below, so the
    union of both guards still covers every uncommitted path.
    """

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
                "scope guard cannot read the #699 change set: "
                f"`git {' '.join(arguments)}` failed "
                f"({detail.strip()}) — Failing closed: a guard that cannot "
                "read its inputs must not pass."
            ) from exc
        return result.stdout

    @classmethod
    def _changed_paths(cls) -> list:
        # The delivered #699 change set: the pinned BASE_SHA..HEAD_SHA range
        # (fail-closed on git errors — see _run_git).
        diff = cls._run_git(["diff", "--name-only", BASE_SHA, HEAD_SHA])
        paths = {
            line.strip().strip('"')
            for line in diff.splitlines()
            if line.strip()
        }
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

    ALLOWED_CHANGE_PREFIXES = ALLOWED_CHANGE_PREFIXES
    FORBIDDEN_CHANGE_PREFIXES = FORBIDDEN_CHANGE_PREFIXES

    def test_change_set_touches_only_the_699_surface(self) -> None:
        changed = self._changed_paths()
        offenders = self._offenders(changed)
        self.assertEqual(
            offenders,
            [],
            f"out-of-scope paths in the #699 change set "
            f"(pinned range UNION working tree): {offenders}",
        )

    def test_no_forbidden_api_media_workflow_or_lockfile_change(self) -> None:
        changed = self._changed_paths()
        for path in changed:
            with self.subTest(path=path):
                for prefix in self.FORBIDDEN_CHANGE_PREFIXES:
                    self.assertFalse(
                        path.startswith(prefix),
                        f"forbidden path changed: {path}",
                    )
                name = Path(path).name
                self.assertFalse(
                    name in FORBIDDEN_LOCKFILE_NAMES
                    or any(
                        name.endswith(suffix)
                        for suffix in FORBIDDEN_LOCKFILE_SUFFIXES
                    ),
                    f"lockfile changed: {path}",
                )

    # -- synthetic predicate proofs (green on base and change alike) -------

    def test_predicate_rejects_out_of_scope_paths(self) -> None:
        rejected = [
            "api/app/main.py",
            "worker/worker_media.py",
            ".github/workflows/quality-integration.yml",
            "package-lock.json",
            "deploy/worker/ubuntu/requirements-runtime.lock.txt",
            "secrets-thing.env",
        ]
        for path in rejected:
            with self.subTest(path=path):
                allowed = any(
                    path.startswith(prefix)
                    for prefix in self.ALLOWED_CHANGE_PREFIXES
                ) and not any(
                    path.startswith(prefix)
                    for prefix in self.FORBIDDEN_CHANGE_PREFIXES
                )
                name = Path(path).name
                is_lockfile = name in FORBIDDEN_LOCKFILE_NAMES or any(
                    name.endswith(suffix)
                    for suffix in FORBIDDEN_LOCKFILE_SUFFIXES
                )
                self.assertFalse(
                    allowed and not is_lockfile,
                    f"guard must reject {path}",
                )

    def test_predicate_accepts_admitted_paths(self) -> None:
        admitted = [
            "tests/test_699_recorder.py",
            "tests/test_699_recorder_lifecycle.py",
            "worker/recorder.py",
            "worker/ubuntu_worker_entrypoint.py",
            "deploy/worker/ubuntu/worker.env.example",
            "deploy/worker/ubuntu/road-worker.env.example",
            "deploy/worker/ubuntu/sea-speed-worker.service.template",
            "deploy/worker/ubuntu/sea-speed-road-worker.service.template",
            "scripts/quality/build_exact_artifacts.py",
            "scripts/quality/validate_exact_artifacts.py",
            "specs/699-recorder-first/spec.md",
            "specs/699-recorder-first/plan.md",
            "specs/699-recorder-first/tasks.md",
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


class RtspScopeGuardTests(unittest.TestCase):
    """The admitted #699b change set: working tree UNION pinned range.

    Fail-closed: a guard that cannot read its inputs must not pass. The
    allowed prefixes are exactly the work-order list (wildcards matched with
    ``fnmatch``); the forbidden prefixes and the lockfile ban are checked
    independently of the allowlist.
    """

    ALLOWED_CHANGE_PREFIXES = RTSP_ALLOWED_CHANGE_PREFIXES
    FORBIDDEN_CHANGE_PREFIXES = RTSP_FORBIDDEN_CHANGE_PREFIXES

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
                "scope guard cannot read the #699b change set: "
                f"`git {' '.join(arguments)}` failed "
                f"({detail.strip()}) — Failing closed: a guard that cannot "
                "read its inputs must not pass."
            ) from exc
        return result.stdout

    @classmethod
    def _changed_paths(cls) -> list:
        # Half A: the pinned range from the delivered #699 merge to the tip.
        diff = cls._run_git(
            ["diff", "--name-only", RTSP_BASE_SHA, RTSP_HEAD_SHA]
        )
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
    def _matches(cls, path: str, patterns: tuple) -> bool:
        for pattern in patterns:
            if "*" in pattern:
                if fnmatch.fnmatch(path, pattern):
                    return True
            elif path.startswith(pattern):
                return True
        return False

    @classmethod
    def _offenders(cls, paths: list) -> list:
        return [
            path
            for path in paths
            if not cls._matches(path, cls.ALLOWED_CHANGE_PREFIXES)
        ]

    @staticmethod
    def _is_lockfile(path: str) -> bool:
        name = Path(path).name
        return name in FORBIDDEN_LOCKFILE_NAMES or any(
            name.endswith(suffix) for suffix in FORBIDDEN_LOCKFILE_SUFFIXES
        )

    def test_change_set_touches_only_the_699b_surface(self) -> None:
        changed = self._changed_paths()
        offenders = self._offenders(changed)
        self.assertEqual(
            offenders,
            [],
            f"out-of-scope paths in the #699b change set "
            f"(pinned range UNION working tree): {offenders}",
        )

    def test_no_forbidden_api_media_entrypoint_workflow_or_lockfile_change(
        self,
    ) -> None:
        changed = self._changed_paths()
        for path in changed:
            with self.subTest(path=path):
                for prefix in self.FORBIDDEN_CHANGE_PREFIXES:
                    self.assertFalse(
                        path.startswith(prefix),
                        f"forbidden path changed: {path}",
                    )
                self.assertFalse(
                    self._is_lockfile(path), f"lockfile changed: {path}"
                )

    # -- synthetic predicate proofs (green on base and change alike) -------

    def test_predicate_rejects_out_of_scope_paths(self) -> None:
        rejected = [
            "api/app/main.py",
            "worker/worker_media.py",
            "worker/ubuntu_worker_entrypoint.py",
            ".github/workflows/quality-integration.yml",
            "package-lock.json",
            "deploy/worker/ubuntu/requirements-runtime.lock.txt",
            "specs/698-something/spec.md",
        ]
        for path in rejected:
            with self.subTest(path=path):
                allowed = self._matches(path, self.ALLOWED_CHANGE_PREFIXES)
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
            "tests/test_699b_rtsp_recorder.py",
            "tests/test_699_recorder_lifecycle.py",
            "worker/recorder.py",
            "worker/recorder_rtsp.py",
            "deploy/worker/ubuntu/worker.env.example",
            "deploy/worker/ubuntu/road-worker.env.example",
            "scripts/quality/build_exact_artifacts.py",
            "scripts/quality/validate_exact_artifacts.py",
            "scripts/ci/validate_sdd.py",
            "specs/699-rtsp-recorder/spec.md",
            "specs/699-rtsp-recorder/plan.md",
            "specs/699-rtsp-recorder/tasks.md",
        ]
        for path in admitted:
            with self.subTest(path=path):
                self.assertTrue(
                    self._matches(path, self.ALLOWED_CHANGE_PREFIXES),
                    f"admitted path wrongly rejected: {path}",
                )
                self.assertFalse(
                    any(
                        path.startswith(prefix)
                        for prefix in self.FORBIDDEN_CHANGE_PREFIXES
                    ),
                    f"admitted path wrongly forbidden: {path}",
                )


if __name__ == "__main__":
    unittest.main()
