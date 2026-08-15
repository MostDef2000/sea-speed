from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RELEASE_VALIDATOR = load_module("validate_release_manifest", ROOT / "scripts/release/validate_release_manifest.py")
DEPLOY_VALIDATOR = load_module("validate_deployment_manifest", ROOT / "scripts/release/validate_deployment_manifest.py")


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class ReleaseManifestTests(unittest.TestCase):
    def v2(self) -> dict[str, object]:
        approved = ["deploy/vps/deploy.sh", "scripts/release/build_release_manifest.py"]
        payload: dict[str, object] = {
            "schema": "sea_speed_release_manifest_v2",
            "deliveryId": "vps-aaaaaaaaaaaa-aaaaaaaaaaaa",
            "component": "vps",
            "canonicalIssue": 172,
            "pullRequest": 173,
            "sourceCommit": "a" * 40,
            "baseCommit": "b" * 40,
            "outcomeContractHash": "c" * 64,
            "changeContractHash": "d" * 64,
            "authorizationFingerprint": "e" * 64,
            "approvedScopeHash": "",
            "approvedFiles": approved,
            "actualFiles": list(approved),
            "artifacts": [{"path": "dist/vps.tar.gz", "sha256": "f" * 64, "sizeBytes": 123}],
            "evidence": {
                "productionAuthorizationSha256": "1" * 64,
                "exactArtifactsManifestSha256": "2" * 64,
                "qualityEvidenceSha256": "3" * 64,
            },
            "createdAt": "2026-08-15T00:00:00+00:00",
            "state": "ready_for_deployment",
        }
        binding = {
            "canonicalIssue": 172,
            "pullRequest": 173,
            "sourceCommit": "a" * 40,
            "baseCommit": "b" * 40,
            "outcomeContractHash": "c" * 64,
            "changeContractHash": "d" * 64,
            "approvedFiles": approved,
        }
        payload["approvedScopeHash"] = digest(binding)
        return payload

    def test_v2_release_manifest_binds_approved_and_actual_scope(self) -> None:
        payload = self.v2()
        RELEASE_VALIDATOR.validate(payload)
        payload["actualFiles"] = ["deploy/vps/deploy.sh"]
        with self.assertRaises(SystemExit):
            RELEASE_VALIDATOR.validate(payload)

    def test_ready_for_deployment_requires_artifact(self) -> None:
        payload = self.v2()
        payload["artifacts"] = []
        with self.assertRaises(SystemExit):
            RELEASE_VALIDATOR.validate(payload)

    def test_legacy_v1_release_manifest_remains_readable(self) -> None:
        approved = ["worker/a.py"]
        payload = {
            "schema": "sea_speed_release_manifest_v1",
            "deliveryId": "worker-legacy",
            "component": "windows-worker",
            "issue": 24,
            "sourceCommit": "a" * 40,
            "baseCommit": "b" * 40,
            "approvedScopeHash": digest({"baseCommit": "b" * 40, "sourceCommit": "a" * 40, "approvedFiles": approved}),
            "approvedFiles": approved,
            "artifacts": [],
            "createdAt": "2026-08-02T00:00:00+00:00",
            "state": "validated",
        }
        RELEASE_VALIDATOR.validate(payload)

    def test_deployment_manifest_accepts_all_three_targets(self) -> None:
        for target in ("vps", "ubuntu-worker", "windows-worker"):
            payload = {
                "schema": "sea_speed_deployment_manifest_v1",
                "deliveryId": f"{target}-aaaaaaaa",
                "target": target,
                "sourceCommit": "a" * 40,
                "previousVersion": "b" * 40,
                "artifactSha256": "c" * 64,
                "installedAt": "2026-08-02T00:00:00+00:00",
                "checks": [{"name": "runtime", "status": "passed"}],
                "rollbackTarget": "b" * 40,
                "runtimeVerified": True,
                "state": "runtime_verified",
            }
            DEPLOY_VALIDATOR.validate(payload)


if __name__ == "__main__":
    unittest.main()
