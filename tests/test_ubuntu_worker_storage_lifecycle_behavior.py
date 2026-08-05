from __future__ import annotations

import json
import stat
import tempfile
import unittest
from pathlib import Path

from storage_lifecycle_test_support import ACTIVE, CANDIDATE, PINNED, RETAINED, OTHER, StorageFixture

class UbuntuWorkerStorageLifecycleBehaviorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = StorageFixture(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_plan_is_dry_run_and_protects_active_pinned_and_rollback_release(self) -> None:
        result = self.fixture.create_plan()
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(self.fixture.plan_file.read_text(encoding="utf-8"))
        paths = {item["path"] for item in plan["items"]}

        self.assertIn(str(self.fixture.install_root / "releases" / CANDIDATE), paths)
        self.assertIn(str(self.fixture.old_event), paths)
        self.assertIn(str(self.fixture.staging), paths)
        self.assertNotIn(str(self.fixture.install_root / "releases" / ACTIVE), paths)
        self.assertNotIn(str(self.fixture.install_root / "releases" / PINNED), paths)
        self.assertNotIn(str(self.fixture.install_root / "releases" / RETAINED), paths)
        self.assertNotIn(str(self.fixture.new_event), paths)
        self.assertNotIn(str(self.fixture.event_symlink), paths)
        self.assertNotIn(str(self.fixture.unknown_updater), paths)
        self.assertTrue((self.fixture.install_root / "releases" / CANDIDATE).exists())
        self.assertEqual(stat.S_IMODE(self.fixture.plan_file.stat().st_mode), 0o600)
        self.assertEqual(plan["active_commit"], ACTIVE)
        self.assertEqual(plan["retained_rollback_candidates"], [RETAINED])
        self.assertEqual(len(plan["plan_id"]), 64)

    def test_apply_deletes_only_prevalidated_plan_items(self) -> None:
        self.assertEqual(self.fixture.create_plan().returncode, 0)
        result = self.fixture.apply()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)

        self.assertFalse((self.fixture.install_root / "releases" / CANDIDATE).exists())
        self.assertFalse(self.fixture.old_event.exists())
        self.assertFalse(self.fixture.staging.exists())
        self.assertTrue((self.fixture.install_root / "releases" / ACTIVE).exists())
        self.assertTrue((self.fixture.install_root / "releases" / PINNED).exists())
        self.assertTrue((self.fixture.install_root / "releases" / RETAINED).exists())
        self.assertTrue(self.fixture.new_event.exists())
        self.assertTrue(self.fixture.unknown_updater.exists())
        self.assertEqual(report["active_commit"], ACTIVE)
        self.assertEqual(report["summary"]["deleted_count"], 3)

    def test_apply_fails_without_deletion_when_active_commit_changes(self) -> None:
        self.assertEqual(self.fixture.create_plan().returncode, 0)
        marker = self.fixture.install_root / "shared/runtime/active-source-commit"
        marker.write_text(f"{OTHER}\n", encoding="utf-8")
        result = self.fixture.apply()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.fixture.install_root / "releases" / CANDIDATE).exists())
        self.assertTrue(self.fixture.old_event.exists())
        self.assertTrue(self.fixture.staging.exists())

    def test_apply_fails_closed_when_any_fingerprint_changes(self) -> None:
        self.assertEqual(self.fixture.create_plan().returncode, 0)
        self.fixture.old_event.write_bytes(b"changed-after-plan")
        result = self.fixture.apply()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("fingerprint changed", result.stderr)
        self.assertTrue((self.fixture.install_root / "releases" / CANDIDATE).exists())
        self.assertTrue(self.fixture.old_event.exists())
        self.assertTrue(self.fixture.staging.exists())

