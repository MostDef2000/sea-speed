from __future__ import annotations

import subprocess
import sys
import unittest

from storage_lifecycle_test_support import (
    APPLY,
    COMMON,
    DOC,
    INSTALLER,
    INVENTORY,
    MANAGER,
    SERVICE,
    TIMER,
)

class UbuntuWorkerStorageLifecycleContractTests(unittest.TestCase):
    def test_python_and_shell_syntax(self) -> None:
        subprocess.run([sys.executable, "-m", "py_compile", str(MANAGER), str(COMMON), str(INVENTORY), str(APPLY)], check=True)
        subprocess.run(["bash", "-n", str(INSTALLER)], check=True)

    def test_shared_lock_and_two_phase_apply_are_required(self) -> None:
        source = "\n".join(path.read_text(encoding="utf-8") for path in (MANAGER, COMMON, INVENTORY, APPLY))
        self.assertIn('updater_root / "update.lock"', source)
        self.assertIn("LOCK_EX | fcntl.LOCK_NB", source)
        self.assertIn("plan_id", source)
        self.assertIn("--expected-active", source)
        self.assertIn("active commit changed after planning", source)
        self.assertIn("fingerprint changed", source)

    def test_destructive_scope_is_narrow(self) -> None:
        source = "\n".join(path.read_text(encoding="utf-8") for path in (MANAGER, COMMON, INVENTORY, APPLY))
        self.assertIn('install_root / "releases"', source)
        self.assertIn('install_root / "shared/output/events"', source)
        self.assertIn('install_root / "updater"', source)
        self.assertIn("EVENT_SUFFIXES", source)
        self.assertNotIn('shared/config', source)
        self.assertNotIn('shared/models', source)
        self.assertNotIn('shared/datasets', source)
        self.assertNotIn('shutil.rmtree(install_root', source)

    def test_audit_timer_cannot_apply_or_delete(self) -> None:
        service = SERVICE.read_text(encoding="utf-8")
        timer = TIMER.read_text(encoding="utf-8")
        installer = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("manage-storage.py inventory", service)
        self.assertNotIn(" apply ", service)
        self.assertIn("OnUnitActiveSec=24h", timer)
        self.assertIn('systemctl enable "$audit_timer"', installer)
        self.assertNotIn("systemctl start", installer)
        self.assertNotIn("systemctl restart", installer)
        self.assertIn("AUDIT_ONLY automatic_deletion=false", installer)

    def test_documentation_preserves_runtime_and_secret_boundaries(self) -> None:
        source = DOC.read_text(encoding="utf-8")
        self.assertIn("Runtime remains `UNKNOWN`", source)
        self.assertIn("does not read `worker.env`", source)
        self.assertIn("never deletes automatically", source)
        self.assertIn("--apply-plan", source)


if __name__ == "__main__":
    unittest.main()
