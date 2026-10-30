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
from support import markdown_docs

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
        self.assertIn("allowed root is missing or unsafe", source)

    def test_protected_files_require_root_ownership_and_exact_mode(self) -> None:
        source = COMMON.read_text(encoding="utf-8")
        self.assertIn("info.st_uid != 0", source)
        self.assertIn("stat.S_IMODE(info.st_mode) != mode", source)
        self.assertIn("root-owned mode", source)

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
        # SS twins (issue #398 wave 6): the runtime-UNKNOWN status is pinned to
        # the document preamble; the never-deletes guarantee and the
        # worker.env secret boundary must co-locate in the Safety model
        # section; the --apply-plan flag must appear inside the Apply-an-
        # approved-plan section's fenced command (the only place apply is
        # documented).
        source = DOC.read_text(encoding="utf-8")
        preamble = markdown_docs.sections(source)[0]
        self.assertIn("Runtime remains `UNKNOWN`", preamble[0] + preamble[1])
        safety = markdown_docs.section_titled(source, "safety model")
        self.assertIsNotNone(safety)
        self.assertIn("never deletes automatically", safety[1])
        self.assertIn("does not read `worker.env`", safety[1])
        apply_section = markdown_docs.section_titled(source, "apply an approved plan")
        self.assertIsNotNone(apply_section)
        apply_blocks = [
            block
            for block in markdown_docs.fenced_blocks(apply_section[1])
            if any("--apply-plan" in line for line in block)
        ]
        self.assertEqual(len(apply_blocks), 1)


if __name__ == "__main__":
    unittest.main()
