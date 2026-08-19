from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
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
    def v3(self) -> dict[str, object]:
        approved = ["deploy/vps/deploy.sh", "scripts/release/build_release_manifest.py"]
        payload: dict[str, object] = {
            "schema": "sea_speed_release_manifest_v3",
            "deliveryId": "vps-aaaaaaaaaaaa-aaaaaaaaaaaa",
            "component": "vps",
            "canonicalIssue": 229,
            "pullRequest": 230,
            "sourceCommit": "a" * 40,
            "baseCommit": "b" * 40,
            "outcomeContractHash": "c" * 64,
            "changeContractHash": "d" * 64,
            "delegationId": "prod-autonomy-v1",
            "policyVersion": "1.0.0",
            "policyHash": "e" * 64,
            "policyDecisionId": "f" * 64,
            "approvedScopeHash": "",
            "approvedFiles": approved,
            "actualFiles": list(approved),
            "artifacts": [{"path": "dist/vps.tar.gz", "sha256": "1" * 64, "sizeBytes": 123}],
            "evidence": {
                "policyDecisionSha256": "2" * 64,
                "exactArtifactsManifestSha256": "3" * 64,
                "qualityEvidenceSha256": "4" * 64,
            },
            "createdAt": "2026-08-19T00:00:00+00:00",
            "state": "ready_for_deployment",
        }
        binding = {
            "canonicalIssue": 229,
            "pullRequest": 230,
            "sourceCommit": "a" * 40,
            "baseCommit": "b" * 40,
            "outcomeContractHash": "c" * 64,
            "changeContractHash": "d" * 64,
            "approvedFiles": approved,
        }
        payload["approvedScopeHash"] = digest(binding)
        return payload

    def test_v3_release_manifest_binds_policy_decision_and_scope(self) -> None:
        payload = self.v3()
        RELEASE_VALIDATOR.validate(payload)
        payload["actualFiles"] = ["deploy/vps/deploy.sh"]
        with self.assertRaises(SystemExit):
            RELEASE_VALIDATOR.validate(payload)

    def test_v3_rejects_comment_authorization_evidence(self) -> None:
        payload = self.v3()
        payload["evidence"]["productionAuthorizationSha256"] = "5" * 64
        with self.assertRaises(SystemExit):
            RELEASE_VALIDATOR.validate(payload)

    def test_ready_for_deployment_requires_artifact(self) -> None:
        payload = self.v3()
        payload["artifacts"] = []
        with self.assertRaises(SystemExit):
            RELEASE_VALIDATOR.validate(payload)

    def test_historical_v2_release_manifest_remains_readable(self) -> None:
        approved = ["deploy/vps/deploy.sh"]
        payload: dict[str, object] = {
            "schema": "sea_speed_release_manifest_v2",
            "deliveryId": "vps-historical",
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
            "actualFiles": approved,
            "artifacts": [],
            "evidence": {"productionAuthorizationSha256": "f" * 64},
            "createdAt": "2026-08-15T00:00:00+00:00",
            "state": "validated",
        }
        payload["approvedScopeHash"] = digest({
            "canonicalIssue": 172, "pullRequest": 173, "sourceCommit": "a" * 40, "baseCommit": "b" * 40,
            "outcomeContractHash": "c" * 64, "changeContractHash": "d" * 64, "approvedFiles": approved,
        })
        RELEASE_VALIDATOR.validate(payload)

    def test_legacy_v1_windows_release_manifest_remains_readable(self) -> None:
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

    def test_historical_deployment_manifest_windows_target_remains_readable(self) -> None:
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

    def test_new_release_builder_rejects_windows_worker_component(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/release/build_release_manifest.py", "--component", "windows-worker"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stdout)


if __name__ == "__main__":
    unittest.main()
