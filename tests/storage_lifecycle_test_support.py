from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "deploy/worker/ubuntu/manage-storage.py"
COMMON = ROOT / "deploy/worker/ubuntu/storage_lifecycle_common.py"
INVENTORY = ROOT / "deploy/worker/ubuntu/storage_lifecycle_inventory.py"
APPLY = ROOT / "deploy/worker/ubuntu/storage_lifecycle_apply.py"
INSTALLER = ROOT / "deploy/worker/ubuntu/install-storage-lifecycle.sh"
SERVICE = ROOT / "deploy/worker/ubuntu/sea-speed-worker-storage-audit.service.template"
TIMER = ROOT / "deploy/worker/ubuntu/sea-speed-worker-storage-audit.timer.template"
DOC = ROOT / "docs/operations/UBUNTU_WORKER_STORAGE_LIFECYCLE.md"

ACTIVE = "a" * 40
RETAINED = "b" * 40
PINNED = "c" * 40
CANDIDATE = "d" * 40
OTHER = "e" * 40

TEST_RUNNER = """
import os
import runpy
import stat
import sys
from pathlib import Path

script = Path(sys.argv[1])
sys.path.insert(0, str(script.parent))
import storage_lifecycle_common as common

def require_fixture_mode(path, mode):
    info = path.stat()
    if stat.S_IMODE(info.st_mode) != mode:
        raise common.LifecycleError(
            f"protected fixture file must be mode {mode:o}: {path}"
        )

def quality_marker_valid_fixture(release, commit):
    marker = release / "quality-approved"
    try:
        info = marker.stat()
        expected = f"source_commit={commit}\\nquality_check=quality-integration"
        return (
            marker.is_file()
            and not marker.is_symlink()
            and stat.S_IMODE(info.st_mode) == 0o644
            and marker.read_text(encoding="utf-8").strip() == expected
        )
    except OSError:
        return False

common.require_root_owned_file = require_fixture_mode
common.quality_marker_valid = quality_marker_valid_fixture
os.geteuid = lambda: 0
sys.argv = [str(script), *sys.argv[2:]]
runpy.run_path(str(script), run_name="__main__")
"""


class StorageFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.install_root = root / "install"
        self.unit_file = root / "sea-speed-worker.service"
        self.plan_file = self.install_root / "storage/cleanup-plan.json"
        self.bin_dir = root / "bin"
        self.bin_dir.mkdir(parents=True)
        self.env = dict(os.environ)
        self.env["PATH"] = f"{self.bin_dir}:{self.env.get('PATH', '')}"
        self.env["TEST_ACTIVE_SHA"] = ACTIVE
        self._write_systemctl_stub()
        self._prepare_layout()

    def _write_systemctl_stub(self) -> None:
        script = self.bin_dir / "systemctl"
        script.write_text(
            "#!/usr/bin/env bash\n"
            "set -eu\n"
            "if [[ \"${1:-}\" == \"is-active\" ]]; then exit 0; fi\n"
            "if [[ \"${1:-}\" == \"show\" ]]; then "
            "echo \"/opt/sea-speed-worker/releases/${TEST_ACTIVE_SHA}/venv/bin/python\"; exit 0; fi\n"
            "exit 3\n",
            encoding="utf-8",
        )
        script.chmod(0o755)

    def _release(self, commit: str, mtime: float) -> Path:
        release = self.install_root / "releases" / commit
        (release / "source").mkdir(parents=True)
        (release / "source-commit").write_text(f"{commit}\n", encoding="utf-8")
        marker = release / "quality-approved"
        marker.write_text(
            f"source_commit={commit}\nquality_check=quality-integration\n",
            encoding="utf-8",
        )
        marker.chmod(0o644)
        (release / "source/payload.txt").write_text(commit, encoding="utf-8")
        os.utime(release, (mtime, mtime))
        return release

    def _prepare_layout(self) -> None:
        now = time.time()
        for commit, days_old in (
            (ACTIVE, 60),
            (RETAINED, 1),
            (PINNED, 50),
            (CANDIDATE, 45),
        ):
            self._release(commit, now - days_old * 86400)

        runtime = self.install_root / "shared/runtime"
        runtime.mkdir(parents=True)
        (runtime / "active-source-commit").write_text(f"{ACTIVE}\n", encoding="utf-8")
        self.unit_file.write_text(
            f"ExecStart={self.install_root}/releases/{ACTIVE}/venv/bin/python worker.py\n",
            encoding="utf-8",
        )

        storage = self.install_root / "storage"
        storage.mkdir(parents=True)
        pins = storage / "protected-releases"
        pins.write_text(f"# active is protected separately\n{PINNED}\n", encoding="utf-8")
        pins.chmod(0o600)

        events = self.install_root / "shared/output/events"
        events.mkdir(parents=True)
        self.old_event = events / "old-event.jpg"
        self.old_event.write_bytes(b"old-event")
        old = now - 40 * 86400
        os.utime(self.old_event, (old, old))
        self.new_event = events / "new-event.jpg"
        self.new_event.write_bytes(b"new-event")
        self.event_symlink = events / "unsafe.jpg"
        self.event_symlink.symlink_to(self.old_event)

        updater = self.install_root / "updater"
        updater.mkdir(parents=True)
        self.staging = updater / "staging.ABC123"
        self.staging.mkdir()
        (self.staging / "checkout.txt").write_text("stale", encoding="utf-8")
        os.utime(self.staging, (old, old))
        self.unknown_updater = updater / "do-not-delete"
        self.unknown_updater.write_text("preserve", encoding="utf-8")
        os.utime(self.unknown_updater, (old, old))

    def command(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-c", TEST_RUNNER, str(MANAGER), *args],
            cwd=ROOT,
            env=self.env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def create_plan(self) -> subprocess.CompletedProcess[str]:
        return self.command(
            "plan",
            "--install-root",
            str(self.install_root),
            "--unit-file",
            str(self.unit_file),
            "--plan-file",
            str(self.plan_file),
            "--keep-releases",
            "1",
            "--release-min-age-days",
            "14",
            "--event-retention-days",
            "30",
            "--updater-temp-retention-days",
            "7",
        )

    def apply(self, expected: str = ACTIVE) -> subprocess.CompletedProcess[str]:
        return self.command(
            "apply",
            "--install-root",
            str(self.install_root),
            "--plan-file",
            str(self.plan_file),
            "--expected-active",
            expected,
        )
