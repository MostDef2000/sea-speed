from __future__ import annotations

import argparse
import importlib.util
import tempfile
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


BUILD = load_module("build_release_manifest", ROOT / "scripts/release/build_release_manifest.py")
RELEASE_VALIDATOR = load_module("validate_release_manifest", ROOT / "scripts/release/validate_release_manifest.py")
DEPLOY_VALIDATOR = load_module("validate_deployment_manifest", ROOT / "scripts/release/validate_deployment_manifest.py")


class ReleaseManifestTests(unittest.TestCase):
    def test_release_manifest_scope_and_artifact_are_verified(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "worker.zip"
            artifact.write_bytes(b"worker-package")
            args = argparse.Namespace(
                component="windows-worker",
                issue=24,
                source_commit="a" * 40,
                base_commit="b" * 40,
                file=["worker/a.py", "worker/a.py", "worker/b.cmd"],
                artifact=[str(artifact)],
                state="packaged",
            )
            payload = BUILD.build_manifest(args)
            self.assertEqual(payload["approvedFiles"], ["worker/a.py", "worker/b.cmd"])
            self.assertEqual(payload["issue"], 24)
            self.assertEqual(len(payload["artifacts"]), 1)
            RELEASE_VALIDATOR.validate(payload)

            payload["approvedFiles"].append("worker/z.py")
            with self.assertRaises(SystemExit):
                RELEASE_VALIDATOR.validate(payload)

    def test_deployment_manifest_requires_consistent_runtime_state(self) -> None:
        payload = {
            "schema": "sea_speed_deployment_manifest_v1",
            "deliveryId": "windows-worker-aaaaaaaaaaaa",
            "target": "windows-worker",
            "sourceCommit": "a" * 40,
            "previousVersion": "b" * 40,
            "artifactSha256": "c" * 64,
            "installedAt": "2026-08-02T00:00:00+00:00",
            "checks": [{"name": "worker_process", "status": "passed"}],
            "rollbackTarget": "b" * 40,
            "runtimeVerified": True,
            "state": "runtime_verified",
        }
        DEPLOY_VALIDATOR.validate(payload)
        payload["checks"][0]["status"] = "failed"
        with self.assertRaises(SystemExit):
            DEPLOY_VALIDATOR.validate(payload)


if __name__ == "__main__":
    unittest.main()
