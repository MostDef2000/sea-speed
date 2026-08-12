from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "0123456789abcdef0123456789abcdef01234567"
WORKFLOW_POLICY = ROOT / "scripts/quality/validate_workflow_policy.py"


def load_workflow_policy():
    spec = importlib.util.spec_from_file_location("sea_speed_workflow_policy", WORKFLOW_POLICY)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load workflow policy validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class QualityArchitectureTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
        )

    def test_contracts_properties_fuzz_and_workflow_policy(self) -> None:
        for command in (
            ("scripts/quality/validate_quality_contracts.py",),
            ("scripts/quality/validate_workflow_policy.py",),
            ("scripts/quality/test_properties.py",),
            ("scripts/quality/test_fuzz_recovery.py",),
        ):
            result = self.run_script(*command)
            self.assertIn("passed" if "test_" in command[0] else "valid", result.stdout.lower())

    def test_workflow_policy_rejects_mutable_and_dangerous_workflows(self) -> None:
        policy = load_workflow_policy()
        valid = """name: test
on: workflow_dispatch
permissions:
  contents: read
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262
"""
        policy.validate_workflow_source(valid, "valid.yml")

        invalid_sources = {
            "mutable action": valid.replace("11d5960a326750d5838078e36cf38b85af677262", "v4"),
            "write-all": valid.replace("permissions:\n  contents: read", "permissions: write-all"),
            "dangerous trigger": valid.replace("on: workflow_dispatch", "on:\n  pull_request_target:"),
            "download pipe": valid + "      - run: curl https://example.invalid/tool | bash\n",
            "missing permissions": valid.replace("permissions:\n  contents: read\n", ""),
        }
        for name, source in invalid_sources.items():
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    policy.validate_workflow_source(source, f"{name}.yml")

    def test_exact_artifacts_are_deterministic_and_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first"
            second = Path(temp_dir) / "second"
            self.run_script("scripts/quality/build_exact_artifacts.py", "--source-commit", COMMIT, "--output-dir", str(first))
            self.run_script("scripts/quality/build_exact_artifacts.py", "--source-commit", COMMIT, "--output-dir", str(second))
            for component in ("vps", "edge"):
                filename = f"sea-speed-{component}-{COMMIT}.tar.gz"
                self.assertEqual((first / filename).read_bytes(), (second / filename).read_bytes())
            self.assertEqual((first / "exact-artifacts.json").read_bytes(), (second / "exact-artifacts.json").read_bytes())

            manifest = json.loads((first / "exact-artifacts.json").read_text(encoding="utf-8"))
            vps = next(artifact for artifact in manifest["artifacts"] if artifact["component"] == "vps")
            vps_paths = {entry["path"] for entry in vps["files"]}
            self.assertIn("frontend/sea-speed/cameras/index.html", vps_paths)

            self.run_script("scripts/quality/validate_exact_artifacts.py", "--manifest", str(first / "exact-artifacts.json"))

    def test_quality_evidence_binds_artifact_digests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            exact = Path(temp_dir) / "exact"
            evidence = Path(temp_dir) / "quality-evidence.json"
            self.run_script("scripts/quality/build_exact_artifacts.py", "--source-commit", COMMIT, "--output-dir", str(exact))
            self.run_script(
                "scripts/quality/build_quality_evidence.py",
                "--source-commit", COMMIT,
                "--artifacts-manifest", str(exact / "exact-artifacts.json"),
                "--output", str(evidence),
            )
            self.run_script(
                "scripts/quality/validate_quality_evidence.py",
                "--evidence", str(evidence),
                "--artifacts-manifest", str(exact / "exact-artifacts.json"),
            )
            data = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertEqual(data["source_commit"], COMMIT)
            self.assertFalse(data["deployment"]["automatic_from_main"])
            self.assertEqual(data["contracts"]["target_media_mode"], "edge_v2")


if __name__ == "__main__":
    unittest.main()
