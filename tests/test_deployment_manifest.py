from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/release/validate_deployment_manifest.py"
spec = importlib.util.spec_from_file_location("validate_deployment_manifest_targets", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def payload(target: str) -> dict[str, object]:
    return {
        "schema": "sea_speed_deployment_manifest_v1",
        "deliveryId": f"{target}-deployment",
        "target": target,
        "sourceCommit": "a" * 40,
        "previousVersion": "unmanaged-baseline",
        "artifactSha256": "b" * 64,
        "installedAt": "2026-08-15T00:00:00+00:00",
        "checks": [{"name": "runtime", "status": "passed"}],
        "rollbackTarget": "unmanaged-baseline",
        "runtimeVerified": True,
        "state": "runtime_verified",
    }


class DeploymentManifestTests(unittest.TestCase):
    def test_existing_vps_and_windows_v1_manifests_remain_valid(self) -> None:
        module.validate(payload("vps"))
        module.validate(payload("windows-worker"))

    def test_ubuntu_worker_target_is_explicitly_valid(self) -> None:
        module.validate(payload("ubuntu-worker"))

    def test_unknown_target_fails_closed(self) -> None:
        with self.assertRaises(SystemExit):
            module.validate(payload("generic-worker"))


if __name__ == "__main__":
    unittest.main()
